"""VedroStepTracerPlugin — интеграция трейсера с событиями vedro."""

import os
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Type

from vedro.core import Dispatcher, Plugin
from vedro.events import (
    ArgParsedEvent,
    ArgParseEvent,
    CleanupEvent,
    ConfigLoadedEvent,
    ScenarioFailedEvent,
    ScenarioPassedEvent,
    ScenarioReportedEvent,
    ScenarioRunEvent,
    StepFailedEvent,
    StepPassedEvent,
    StepRunEvent,
)
from . import gitlab, settings
from .exclude import DEFAULT_EXCLUDED_VALUE_TYPES, ValueExcludeRules
from .filenames import cleanup_reports, sanitize_filename
from .reporting.base import BaseReportRenderer
from .reporting.html import HtmlTreeWriter
from .reporting.html.traceback import render_error_text, render_tb_html
from .reporting.llm import render_tb_text
from .reporting.markdown import MarkdownTreeWriter
from .reporting.teamcity import TeamCityTreeWriter
from .reporting.terminal import TreeWriter
from .report_types import ReportType
from .test_status import TestStatus
from .tracing import FunctionTracer, RootStep, collapse_tree

if TYPE_CHECKING:
    from .config import VedroStepTracer

__all__ = ("VedroStepTracerPlugin",)

# Расширения файлов для каждого формата отчёта (артефакт / output_dir).
# ReportType — не enum, а строковые константы (см. report_types.py), поэтому
# ключи здесь — обычные нормализованные (lower-case) строки.
_FORMAT_EXTENSIONS: Dict[str, str] = {
    ReportType.HTML: "html",
    ReportType.MARKDOWN: "md",
}
_ARTIFACT_NAMES: Dict[str, str] = {
    fmt: f"vedro-step-tracer.{ext}" for fmt, ext in _FORMAT_EXTENSIONS.items()
}
_VALID_REPORT_FORMATS = frozenset(_FORMAT_EXTENSIONS)

_REPORT_EVENTS = frozenset((TestStatus.FAILED, TestStatus.PASSED))
_SAVE_TO_DIR_DEFAULT = [TestStatus.FAILED]


def _parse_save_to_dir(value: Any) -> List[str]:
    """
    Нормализовать ``save_to_dir`` в список событий.

    Принимает список/кортеж строк, строку через запятую или bool (для
    обратной совместимости: ``True`` == ``["failed"]``, ``False`` == ``[]``).
    Неизвестные значения игнорируются, повторы убираются.
    """
    if value is None:
        return list(_SAVE_TO_DIR_DEFAULT)
    if isinstance(value, bool):
        return list(_SAVE_TO_DIR_DEFAULT) if value else []
    if isinstance(value, str):
        raw = value.split(",")
    else:
        try:
            raw = list(value)
        except TypeError:
            return list(_SAVE_TO_DIR_DEFAULT)

    events: List[str] = []
    for item in raw:
        if isinstance(item, bool):
            if item and TestStatus.FAILED not in events:
                events.append(TestStatus.FAILED)
            continue
        name = str(item).strip().lower()
        if not name:
            continue
        if name in ("1", "true", "yes", "on"):
            name = TestStatus.FAILED
        elif name in ("0", "false", "no", "off"):
            continue
        if name in _REPORT_EVENTS and name not in events:
            events.append(name)
    return events


class VedroStepTracerPlugin(Plugin):
    """
    Плагин vedro для автоматического трейсинга вызовов функций
    из helpers/, contexts/, interfaces/ во время выполнения тестовых шагов.
    """

    def __init__(self, config: Type["VedroStepTracer"]) -> None:
        super().__init__(config)
        self._enabled: bool = getattr(config, "enabled", True)
        self._output_dir: str = getattr(config, "output_dir", "logs/traces")
        self._target_dirs: List[str] = getattr(
            config, "target_dirs",
            ["helpers", "contexts", "interfaces"]
        )
        self._print_to_stdout: bool = getattr(config, "print_to_stdout", False)
        self._max_line_len: int = getattr(config, "max_line_len", 1000)
        self._max_hidden_len: int = getattr(config, "max_hidden_len", 20_000)
        self._max_total_len: int = getattr(config, "max_total_len", 50_000)
        self._max_lines: int = getattr(config, "max_lines", 1_000)
        self._max_collection_items: int = getattr(config, "max_collection_items", 1_000)
        self._attach_artifacts: bool = getattr(config, "attach_artifacts", True)
        self._save_to_dir_events: List[str] = _parse_save_to_dir(
            getattr(config, "save_to_dir", _SAVE_TO_DIR_DEFAULT)
        )
        self._save_to_dir: bool = bool(self._save_to_dir_events)
        # Формат(ы) файлового отчёта — ReportType.HTML/MARKDOWN либо просто
        # текст "html"/"markdown" без учёта регистра (см. VedroStepTracer.report_formats).
        self._report_formats: List[str] = self._parse_report_formats(
            getattr(config, "report_formats", [ReportType.HTML])
        )
        self._collapse_passthrough: bool = getattr(config, "collapse_passthrough", True)
        self._exclude_paths: List[str] = list(getattr(config, "exclude_paths", []) or [])
        self._exclude_functions: List[str] = list(getattr(config, "exclude_functions", []) or [])
        # Правила исключения значений (см. VedroStepTracer.exclude_value_types) —
        # базовый список (по умолчанию уже найденные проблемные типы) и
        # пользовательский поверх него, скомпилированные один раз при старте.
        self._exclude_value_rules: ValueExcludeRules = ValueExcludeRules(
            list(getattr(config, "exclude_value_types", DEFAULT_EXCLUDED_VALUE_TYPES) or [])
            + list(getattr(config, "extra_exclude_value_types", []) or [])
        )
        # job_id по умолчанию не заполнен (локальный запуск); в CI конфиг
        # проекта должен передавать его из переменной окружения, например:
        # job_id = os.environ.get('CI_JOB_ID'). Наличие job_id означает,
        # что мы выполняемся в GitLab CI.
        self._job_id: str = getattr(config, "job_id", "") or ""
        # Паттерн ссылки на артефакт GitLab CI с плейсхолдерами {job_id} и
        # {path}. По умолчанию берётся из переменной окружения
        # PROJECT_ARTIFACT_PATTERN (см. VedroStepTracer.artifact_url_pattern).
        self._artifact_url_pattern: str = getattr(config, "artifact_url_pattern", "") or (
            os.environ.get("PROJECT_ARTIFACT_PATTERN", "")
        )
        # Корень проекта на хостовой машине. По умолчанию берётся из
        # переменной окружения HOST_PROJECT_ROOT_DIRECTORY (см.
        # VedroStepTracer.host_project_root_directory).
        self._host_project_root_directory: str = getattr(
            config, "host_project_root_directory", ""
        ) or os.environ.get("HOST_PROJECT_ROOT_DIRECTORY", "")
        # Подпуть рабочей директории относительно корня репозитория
        # (см. VedroStepTracer.workdir_subpath).
        self._workdir_subpath: str = getattr(config, "workdir_subpath", "")
        # Очистка старых отчётов перед прогоном (см. VedroStepTracer.cleanup_before).
        self._cleanup_before: bool = getattr(config, "cleanup_before", True)
        # Режим вывода для тест-раннера PyCharm (см. VedroStepTracer.teamcity).
        self._teamcity_config: Optional[bool] = getattr(config, "teamcity", None)
        self._teamcity_env_vars: List[str] = getattr(
            config, "teamcity_env_vars",
            ["PYCHARM_HOSTED", "TEAMCITY_VERSION", "PYCHARM_HELPERS_DIR"],
        )
        self._teamcity: bool = False
        # Глифы дерева в выводе TeamCity (см. VedroStepTracer.teamcity_tree_prefix).
        self._teamcity_tree_prefix: bool = getattr(config, "teamcity_tree_prefix", True)

        settings.set_max_line_len(self._max_line_len)
        settings.set_max_hidden_len(self._max_hidden_len)
        settings.set_max_total_len(self._max_total_len)
        settings.set_max_lines(self._max_lines)
        settings.set_max_collection_items(self._max_collection_items)

        self._project_root: str = ""
        self._tracer: Optional[FunctionTracer] = None
        self._current_root_step: Optional[RootStep] = None
        self._scenario_steps: List[RootStep] = []
        self._scenario_name: str = ""
        self._scenario_path: str = ""
        # Класс сценария — нужен, чтобы найти строку определения метода шага.
        self._scenario_cls: Any = None
        self._writer: TreeWriter = TreeWriter(verbosity=1, color=True)
        self._html_writer: HtmlTreeWriter = HtmlTreeWriter()
        self._markdown_writer: MarkdownTreeWriter = MarkdownTreeWriter()
        self._report_writers: Dict[str, BaseReportRenderer] = {
            ReportType.HTML: self._html_writer,
            ReportType.MARKDOWN: self._markdown_writer,
        }
        self._teamcity_writer: TeamCityTreeWriter = TeamCityTreeWriter()
        self._interactive: bool = False
        self._verbosity: int = 1
        self._scenario_failed: bool = False
        self._scenario_instance: Any = None
        self._self_snapshot_before: Dict[str, Any] = {}
        self._report_saved: bool = False
        # Ссылки на сохранённые отчёты (формат, ссылка) — печатаются в stdout
        # один раз в конце сценария (см. on_scenario_reported). Обычно одна
        # запись (один активный формат), две — только при report_format="both".
        self._report_links: List[Tuple[str, str]] = []
        # Результаты упавших сценариев — для итоговой сводки в конце прогона
        # (ссылки на отчёты читаются на CleanupEvent, когда Artifacted уже
        # дописал пути артефактов в extra_details).
        self._failed_results: List[Any] = []
        # Индекс параметризации текущего сценария (None — не параметризован).
        self._scenario_index: Optional[int] = None
        # Директория артефактов vedro (см. on_config_loaded).
        self._artifacts_dir: Optional[Path] = None

    def subscribe(self, dispatcher: Dispatcher) -> None:
        dispatcher.listen(ConfigLoadedEvent, self.on_config_loaded)
        dispatcher.listen(ArgParseEvent, self.on_arg_parse)
        dispatcher.listen(ArgParsedEvent, self.on_arg_parsed)
        dispatcher.listen(ScenarioRunEvent, self.on_scenario_run)
        dispatcher.listen(StepRunEvent, self.on_step_run)
        dispatcher.listen(StepPassedEvent, self.on_step_passed)
        dispatcher.listen(StepFailedEvent, self.on_step_failed)
        dispatcher.listen(ScenarioFailedEvent, self.on_scenario_failed)
        dispatcher.listen(ScenarioPassedEvent, self.on_scenario_passed)
        dispatcher.listen(ScenarioReportedEvent, self.on_scenario_reported)
        dispatcher.listen(CleanupEvent, self.on_cleanup)

    async def on_config_loaded(self, event: ConfigLoadedEvent) -> None:
        """
        Запоминаем раскладку артефактов vedro.

        Отчёт кладётся в ту же директорию, что и артефакты сценария, поэтому
        нужны её настройки: корень проекта и artifacts_dir плагина Artifacted.
        """
        config = event.config
        project_dir = Path(getattr(config, "project_dir", os.getcwd())).resolve()
        artifacted = getattr(getattr(config, "Plugins", None), "Artifacted", None)
        if artifacted is None or not getattr(artifacted, "save_artifacts", True):
            self._artifacts_dir = None
            return
        artifacts_dir = Path(getattr(artifacted, "artifacts_dir", ".vedro/artifacts"))
        if not artifacts_dir.is_absolute():
            artifacts_dir = (project_dir / artifacts_dir).resolve()
        self._artifacts_dir = artifacts_dir

    async def on_arg_parse(self, event: ArgParseEvent) -> None:
        """Регистрируем флаг --tr для интерактивного вывода."""
        event.arg_parser.add_argument(
            "--tr",
            nargs="?",
            type=int,
            const=1,
            default=None,
            metavar="LEVEL",
            help=(
                "Интерактивный трейс вызовов. Уровни: "
                "0=только return из target_dirs, "
                "1=return + scope (default), "
                "2=scope + args/return всех уровней, "
                "3=всё (scope + args + locals + return)"
            )
        )
        event.arg_parser.add_argument(
            "--tr-no-color",
            action="store_true",
            default=False,
            help="Отключить ANSI-раскраску в выводе трейса"
        )
        event.arg_parser.add_argument(
            "--tr-teamcity",
            action="store_true",
            default=None,
            help=(
                "Выводить дерево шагов service-сообщениями TeamCity, чтобы шаги "
                "и вложенные вызовы были видны деревом в тест-раннере PyCharm. "
                "Если флаг не передан — определяется автоматически по выбранному "
                "репортёру `-r pycharm` и переменным окружения IDE "
                "(см. VedroStepTracer.teamcity)."
            )
        )
        event.arg_parser.add_argument(
            "--tr-gitlab",
            action="store_true",
            default=None,
            help=(
                "Добавить маркеры схлопываемых секций GitLab CI. "
                "Каждый вызов функции, секция аргументов, результата и scope "
                "оборачиваются в section_start/section_end. "
                "Если флаг не передан — определяется автоматически по "
                "наличию job_id в конфиге (см. VedroStepTracer.job_id)."
            )
        )

    async def on_arg_parsed(self, event: ArgParsedEvent) -> None:
        """Определяем корень проекта и читаем флаг --tr."""
        tr_value = getattr(event.args, "tr", None)
        tr_gitlab_arg = getattr(event.args, "tr_gitlab", None)
        # Флаг явно не передан — определяем режим GitLab CI автоматически
        # по наличию job_id (заполняется в конфиге проекта из CI_JOB_ID).
        # Этот флаг влияет только на формат вывода (маркеры
        # section_start/section_end для схлопывания в GitLab CI), но не
        # должен сам по себе включать вывод шагов на успешных сценариях —
        # для этого нужен явный --tr.
        gitlab = tr_gitlab_arg if tr_gitlab_arg is not None else bool(self._job_id)
        self._interactive = tr_value is not None
        self._verbosity = tr_value if tr_value is not None else 1
        no_color = getattr(event.args, "tr_no_color", False)
        self._writer = TreeWriter(verbosity=self._verbosity, color=not no_color, gitlab=gitlab)
        self._teamcity = self._detect_teamcity(event)
        self._teamcity_writer = TeamCityTreeWriter(
            verbosity=self._verbosity if tr_value is not None else 2,
            tree_prefix=self._teamcity_tree_prefix,
            path_resolver=self._to_host_path,
        )

        self._project_root = os.getcwd()
        # Резолвим целевые директории в абсолютные пути
        self._target_dirs = [
            os.path.join(self._project_root, d) for d in self._target_dirs
        ]
        # Директория для файловых отчётов нужна только в режиме save_to_dir:
        # по умолчанию отчёт уходит артефактом сценария.
        if self._save_to_dir:
            output_path = os.path.join(self._project_root, self._output_dir)
            os.makedirs(output_path, exist_ok=True)

            # Чистим отчёты прошлых прогонов до того, как появится первый новый:
            # иначе в директории вперемешку лежат отчёты разных запусков.
            if self._cleanup_before:
                for fmt in self._report_formats:
                    cleanup_reports(output_path, suffix=f".{_FORMAT_EXTENSIONS[fmt]}")

    def _detect_teamcity(self, event: ArgParsedEvent) -> bool:
        """
        Нужен ли вывод service-сообщениями TeamCity.

        Приоритет: явный флаг --tr-teamcity, затем значение из конфига, затем
        автоопределение — выбран репортёр `-r pycharm` (его регистрирует сам
        vedro) либо в окружении есть переменные, которые выставляет
        PyCharm/TeamCity.
        """
        if getattr(event.args, "tr_teamcity", None):
            return True
        if self._teamcity_config is not None:
            return self._teamcity_config
        reporters = getattr(event.args, "reporters", None) or []
        if "pycharm" in reporters:
            return True
        return any(os.environ.get(name) for name in self._teamcity_env_vars)

    async def on_scenario_run(self, event: ScenarioRunEvent) -> None:
        """Начало сценария — сбрасываем состояние."""
        self._scenario_steps = []
        self._current_root_step = None
        self._scenario_failed = False
        self._report_saved = False
        self._report_links = []
        scenario = event.scenario_result.scenario
        self._scenario_name = getattr(scenario, "subject", "") or scenario.__class__.__name__
        # Индекс параметризации: у всех запусков одного шаблона одинаковый
        # subject, и в большом логе их невозможно различить.
        self._scenario_index = getattr(scenario, "template_index", None)
        self._scenario_path = str(getattr(scenario, "path", ""))
        self._scenario_cls = getattr(scenario, "_orig_scenario", None) or type(scenario)
        self._scenario_instance = None
        self._self_snapshot_before = {}

    async def on_step_run(self, event: StepRunEvent) -> None:
        """Начало шага — устанавливаем трейсинг."""
        step_name = event.step_result.step_name
        self._current_root_step = RootStep(name=step_name)
        self._current_root_step.filename = self._scenario_path
        self._current_root_step.lineno = self._step_lineno(step_name)

        # Снимок self сценария до выполнения шага
        if self._scenario_instance is not None:
            self._self_snapshot_before = dict(getattr(self._scenario_instance, "__dict__", {}))
        else:
            self._self_snapshot_before = {}

        # Запускаем трейсер — передаём снимок self «до шага», чтобы трейсер
        # не считал уже существующие атрибуты сценария новыми и последовательно
        # фиксировал только реально новые/изменённые внутри этого шага
        # (см. FunctionTracer._emit_scope_diff).
        self._tracer = FunctionTracer(self._target_dirs,
                                      initial_self_vars=self._self_snapshot_before,
                                      scenario_self=self._scenario_instance,
                                      step_name=step_name,
                                      exclude_paths=self._exclude_paths,
                                      exclude_functions=self._exclude_functions,
                                      exclude_value_rules=self._exclude_value_rules)
        self._tracer.start()

    async def on_step_passed(self, event: StepPassedEvent) -> None:
        """Шаг успешен — собираем результаты трейсинга."""
        self._finalize_step("PASS", event.step_result)

    async def on_step_failed(self, event: StepFailedEvent) -> None:
        """Шаг упал — собираем результаты трейсинга."""
        self._scenario_failed = True
        self._finalize_step("FAIL", event.step_result)

    def _finalize_step(self, status: str, step_result: Any) -> None:
        """Завершить трейсинг шага и сохранить результат."""
        if self._tracer is None or self._current_root_step is None:
            return

        # Останавливаем трейсер (внутри также дописывает в call_tree
        # финальные scope/locals изменения, накопленные после последнего
        # вложенного вызова — см. FunctionTracer.stop()).
        call_tree = self._tracer.stop()

        # Захватываем scenario_self из трейсера (если удалось)
        scenario_self = self._tracer.scenario_self
        if scenario_self is not None:
            self._scenario_instance = scenario_self

        self._tracer = None

        # Закрываем корневой шаг
        self._current_root_step.close(status)
        self._current_root_step.call_tree = collapse_tree(
            call_tree, passthrough=self._collapse_passthrough,
        )

        # Для упавшего шага сохраняем исходный код в месте падения и текст
        # ошибки — нужны только для HTML-отчёта (в терминале traceback уже
        # выводит сам vedro).
        if status == "FAIL":
            exc_info = getattr(step_result, "exc_info", None)
            if exc_info is not None:
                self._current_root_step.failure_source = render_tb_html(
                    exc_info.traceback, self._scenario_path, self._to_relative_path
                )
                self._current_root_step.failure_trace = render_tb_text(
                    exc_info.traceback, self._scenario_path, self._to_relative_path
                )
                self._current_root_step.failure_error = render_error_text(exc_info.value)

        self._scenario_steps.append(self._current_root_step)

        # Ничего не пишем в stdout прямо сейчас — трейс должен выводиться
        # только если сценарий в итоге упал (см. on_scenario_reported),
        # поэтому просто копим шаги и выводим всё разом в конце.

        self._current_root_step = None

    async def on_scenario_failed(self, event: ScenarioFailedEvent) -> None:
        """Сценарий упал — отчёт нужен всегда."""
        self._publish_report(event.scenario_result, failed=True)
        self._failed_results.append(event.scenario_result)

    async def on_scenario_passed(self, event: ScenarioPassedEvent) -> None:
        """Сценарий прошёл — отчёт нужен при --tr или для события passed."""
        if self._interactive or TestStatus.PASSED in self._save_to_dir_events:
            self._publish_report(event.scenario_result, failed=False)

    def _publish_report(self, scenario_result: Any, failed: bool) -> None:
        """
        Собрать отчёт и отдать его файлом: в директории артефактов сценария
        и/или в output_dir. В результате сценария остаётся только ссылка.

        Отчёт пишется напрямую, без ``scenario_result.attach``: артефакт vedro
        репортёр печатает отдельной строкой, и ссылка дублировалась бы.
        """
        if not self._scenario_steps or self._report_saved:
            return

        event = TestStatus.FAILED if failed else TestStatus.PASSED
        write_artifact = self._attach_artifacts and (self._interactive or failed)
        write_file = self._save_to_dir and (
            self._interactive or event in self._save_to_dir_events
        )
        if not (write_artifact or write_file):
            return

        self._report_saved = True
        self._report_links = []

        for fmt in self._report_formats:
            content = self._render_report(fmt)
            link = None

            if write_artifact:
                filepath = self._write_artifact(scenario_result, content, fmt)
                if filepath is not None:
                    link = self._report_link_for(str(filepath))

            if write_file:
                filepath = self._save_to_file(content, fmt)
                if filepath is not None:
                    link = self._report_link_for(filepath)

            if link:
                self._report_links.append((fmt, link))

        # Один активный формат — строка остаётся прежней (обратная
        # совместимость), несколько — формат указывается в скобках, чтобы
        # ссылки можно было различить.
        if len(self._report_links) == 1:
            _, link = self._report_links[0]
            scenario_result.add_extra_details(f"🔎 Trace report: {link}")
        else:
            for fmt, link in self._report_links:
                scenario_result.add_extra_details(f"🔎 Trace report ({fmt}): {link}")

    def _write_artifact(self, scenario_result: Any, content: str,
                       fmt: str) -> Optional[Path]:
        """
        Записать отчёт в директорию артефактов сценария.

        Путь повторяет раскладку плагина Artifacted
        (``<artifacts_dir>/<rel_path>/<started_at>-<name>-<index>/<файл>``),
        чтобы отчёт лежал рядом с остальными артефактами сценария и
        попадал в артефакты CI.
        """
        if self._artifacts_dir is None:
            return None
        scenario = getattr(scenario_result, "scenario", None)
        rel_path = getattr(scenario, "rel_path", None)
        if rel_path is None:
            return None

        started_at = str(getattr(scenario_result, "started_at", None) or 0).replace(".", "-")
        index = str(getattr(scenario, "template_index", None) or 0)
        name = getattr(scenario, "name", "")
        filepath = (self._artifacts_dir / Path(rel_path).with_suffix("") /
                    f"{started_at}-{name}-{index}" / _ARTIFACT_NAMES[fmt])
        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(content, encoding="utf-8")
        except OSError:
            return None
        return filepath

    def _report_link_for(self, filepath: str) -> str:
        """
        Ссылка на отчёт: артефакт GitLab CI, а при локальном запуске —
        кликабельная file:// ссылка на хостовый путь.
        """
        artifact_url = self._to_artifact_url(filepath)
        if artifact_url is not None:
            return artifact_url
        return self._make_terminal_link(self._to_host_path(filepath))

    async def on_scenario_reported(self, event: ScenarioReportedEvent) -> None:
        """Сценарий завершён — выводим накопленный трейс в stdout."""
        if not self._scenario_steps:
            return

        # Полное дерево в stdout печатается, только если это включено конфигом
        # и сценарий упал. По умолчанию отчёт уходит файлом в артефакты, а в
        # результате сценария остаётся ссылка на него.
        should_print = self._print_to_stdout and self._scenario_failed
        if self._teamcity:
            # В режиме тест-раннера шаги и значения показываются деревом, и
            # дублировать их текстом — только засорять консоль IDE. Дерево
            # выводится всегда: ради него режим и включают.
            # ScenarioReportedEvent приходит после того, как репортёр закрыл
            # свой узел сценария, поэтому наши suite с ним не пересекаются.
            sys.stdout.write(self._teamcity_writer.render_document(
                self._display_scenario_name(), self._scenario_steps, self._scenario_path,
            ))
            sys.stdout.flush()
        elif should_print:
            separator = "═" * 78
            run_hint = f" [{self._scenario_index}]" if self._scenario_index is not None else ""
            if self._scenario_failed:
                sys.stdout.write(f"\n\033[1;31m{separator}\n"
                                 f"❌ {self._scenario_name}{run_hint}\033[0m:\n\n")
            else:
                sys.stdout.write(f"\n\033[1;32m{separator}\n"
                                 f"✔ {self._scenario_name}{run_hint}\033[0m:\n\n")
            output = self._writer.render_scenario(self._scenario_name, self._scenario_steps)
            sys.stdout.write(output)
            sys.stdout.flush()

        # Сброс
        self._scenario_steps = []
        self._scenario_name = ""
        self._scenario_failed = False
        self._report_links = []

    def _display_scenario_name(self) -> str:
        """Имя сценария с индексом параметризации, если он есть."""
        if self._scenario_index is None:
            return self._scenario_name
        return f"{self._scenario_name} [{self._scenario_index}]"

    async def on_cleanup(self, event: CleanupEvent) -> None:
        """
        Конец прогона — компактная сводка упавших сценариев: в пачке из
        десятков сценариев иначе приходится отматывать весь лог, чтобы
        понять, что именно упало.

        Ссылка на отчёт здесь не повторяется — её уже печатает сам vedro
        строкой extra_details сразу под упавшим сценарием.
        """
        if not self._failed_results:
            return

        lines = [f"\n\033[1;31m❌ Failed scenarios: {len(self._failed_results)}\033[0m"]
        for scenario_result in self._failed_results:
            scenario = getattr(scenario_result, "scenario", None)
            subject = getattr(scenario, "subject", "") or getattr(scenario, "name", "?")
            index = getattr(scenario, "template_index", None)
            hint = f" [{index}]" if index is not None else ""
            lines.append(f"  • {subject}{hint}")
        sys.stdout.write("\n".join(lines) + "\n")
        sys.stdout.flush()

        self._failed_results = []

    def _save_to_file(self, content: str, fmt: str) -> Optional[str]:
        """Сохранить отчёт в лог-файл. Возвращает путь к файлу (в контейнере)."""
        output_path = os.path.join(self._project_root, self._output_dir)
        safe_name = sanitize_filename(self._scenario_name)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        # Индекс параметризации обязателен в имени: у всех запусков шаблона
        # одинаковый subject, и отчёты перетирали бы друг друга.
        index = f"_{self._scenario_index}" if self._scenario_index is not None else ""
        filename = f"{timestamp}_{safe_name}{index}.{_FORMAT_EXTENSIONS[fmt]}"
        filepath = os.path.join(output_path, filename)
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return filepath
        except OSError:
            return None

    def _render_report(self, fmt: str) -> str:
        """Собрать отчёт выбранного формата по накопленным шагам сценария."""
        scenario_path = self._to_host_path(self._scenario_path) if self._scenario_path else ""
        return self._report_writers[fmt].render_document(
            self._display_scenario_name(), self._scenario_steps,
            scenario_path=scenario_path,
        )

    @staticmethod
    def _parse_report_formats(report_formats: Any) -> List[str]:
        """
        Проверить и нормализовать ``report_formats`` конфига.

        ``ReportType`` — не enum, а строковые константы, поэтому значение
        принимается и как ``ReportType.HTML``, и просто текстом ("html",
        "HTML", "  Html ") без учёта регистра и пробелов по краям — удобно,
        когда формат приходит из переменной окружения CI. Одиночная строка
        (не список) тоже допустима. Неизвестное значение или пустой список —
        явная ошибка конфигурации, а не молчаливый откат к html: иначе
        опечатку сложно заметить.
        """
        if isinstance(report_formats, str):
            report_formats = [report_formats]

        formats: List[str] = []
        for fmt in (report_formats or []):
            if not isinstance(fmt, str):
                raise TypeError(
                    f"VedroStepTracer.report_formats: {fmt!r} — не строка, "
                    f"ожидается ReportType.HTML/ReportType.MARKDOWN или "
                    f"текст 'html'/'markdown'"
                )
            normalized = fmt.strip().lower()
            if normalized not in _VALID_REPORT_FORMATS:
                valid = ", ".join(sorted(_VALID_REPORT_FORMATS))
                raise ValueError(
                    f"VedroStepTracer.report_formats: недопустимое значение "
                    f"{fmt!r}, ожидается одно из: {valid}"
                )
            formats.append(normalized)

        if not formats:
            raise ValueError(
                "VedroStepTracer.report_formats: список форматов не может быть "
                "пустым, укажите хотя бы один из ReportType"
            )
        # Сохраняем порядок, но убираем дубли (на случай, если один формат
        # указали дважды).
        return list(dict.fromkeys(formats))

    def _to_host_path(self, filepath: str) -> str:
        """Путь внутри контейнера → путь на хостовой машине (см. gitlab.to_host_path)."""
        return gitlab.to_host_path(
            filepath, self._project_root, self._workdir_subpath,
            self._host_project_root_directory,
        )

    def _step_lineno(self, step_name: str) -> int:
        """Строка определения метода шага в классе сценария (0 — не найдена)."""
        method = getattr(self._scenario_cls, step_name, None)
        code = getattr(method, "__code__", None)
        return getattr(code, "co_firstlineno", 0) or 0

    def _to_artifact_url(self, filepath: str) -> Optional[str]:
        """Ссылка на артефакт GitLab CI, либо None при локальном запуске."""
        return gitlab.to_artifact_url(
            filepath, self._project_root, self._job_id,
            self._artifact_url_pattern, self._workdir_subpath,
        )

    def _to_relative_path(self, filepath: str) -> str:
        """Путь внутри контейнера → путь относительно workdir тестов."""
        return gitlab.to_relative_path(filepath, self._project_root)

    def _make_terminal_link(self, path: str) -> str:
        """Кликабельная file:// ссылка на отчёт для вывода в терминал."""
        return gitlab.make_terminal_link(path)
