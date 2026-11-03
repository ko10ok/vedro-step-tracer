"""TeamCityTreeWriter — дерево шагов как service-сообщения TeamCity.

Нужен для запуска тестов из PyCharm: встроенный репортёр vedro
(``-r pycharm``) сообщает IDE только о сценариях, поэтому шаги и вложенные
вызовы в дереве тестов не видны. Этот рендерер дописывает недостающую
иерархию: сценарий — suite, шаги и вызовы внутри — вложенные suite/test,
а собранные трейсером значения печатаются как вывод соответствующего узла.

Почему строки дополнительно префиксуются глифами дерева
(``┣━``/``┃``/``├─``): в узле-родителе раннер показывает вывод всех
потомков подряд, а service-сообщения с заголовками вложенных вызовов
в консоль не попадают — их разбирает и скрывает сам раннер. Без префиксов
и текстовых заголовков значения разных вызовов сливались бы в один
неразличимый поток. Заголовок вызова печатается ДО открытия его узла,
поэтому он виден в родителе и не дублирует имя самого узла.

Префиксы отключаются флагом ``tree_prefix=False`` (конфиг
``teamcity_tree_prefix``): при работе с узлами по одному вложенность видна
и без глифов, а отступы съедают ширину под длинные значения. Заголовки
вызовов и разделители при этом сохраняются.

Сообщения выводятся после того, как репортёр закрыл свой узел сценария
(ScenarioReportedEvent), поэтому конфликта с ``-r pycharm`` нет: наши suite
не пересекаются с его testStarted/testFinished.
"""

from io import StringIO
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from rich.console import Console
from rich.markup import escape as markup_escape

from ...tracing import RootStep, StepNode, VarNode
from ..base import BaseReportRenderer
from ..status import PLAIN_STATUS_EMOJI
from ..terminal.markup import INDENT, get_style, markup_value
from .messages import file_location, test_failed, test_finished, test_started, test_suite_finished, test_suite_started

__all__ = ("TeamCityTreeWriter",)

# Префикс корневого suite: узел сценария от встроенного репортёра называется
# так же, и без пометки два одинаковых имени в дереве путают.
_ROOT_PREFIX = "🔎 trace: "

# scope + аргументы + возвраты, без локальных переменных: в дереве тестов
# они превращаются в стену текста (см. TreeWriter._KIND_MIN_VERBOSITY).
_DEFAULT_VERBOSITY = 2

_KIND_MARKER = {"arg": "→", "local": "·", "scope": "⇒", "scope_changed": "⇒"}
_KIND_MIN_VERBOSITY = {"arg": 2, "local": 3, "scope": 1, "scope_changed": 1}

# Отступ содержимого шага от его заголовка, когда глифы дерева отключены.
# Не накапливается по глубине: узлы разворачивают по одному, и вложенность
# видна по самому дереву тестов, а не по ширине отступа.
_PLAIN_INDENT = "  "

# Длительность меньше миллисекунды в заголовке — только шум.
_MIN_SHOWN_DURATION = 0.001


class TeamCityTreeWriter(BaseReportRenderer):
    """Рендерит дерево шагов в поток service-сообщений TeamCity."""

    def __init__(self, verbosity: int = _DEFAULT_VERBOSITY,
                 tree_prefix: bool = True,
                 path_resolver: Optional[Callable[[str], str]] = None) -> None:
        self.verbosity = verbosity
        # Глифы дерева перед строками (см. докстроку модуля). Их отключают,
        # когда узлы разворачивают по одному: внутри самого узла вложенность
        # и так видна, а отступы съедают ширину под значения.
        self.tree_prefix = tree_prefix
        # Путь внутри контейнера → путь на хосте: файл открывает IDE на
        # хостовой машине, а трейсер видит пути смонтированных томов.
        self.path_resolver = path_resolver
        self._lines: List[str] = []
        # Счётчик имён узлов: IDE склеивает одноимённые узлы одного прогона.
        self._name_counts: Dict[str, int] = {}

    def _location(self, filename: str, lineno: int = 0) -> str:
        """locationHint для узла дерева — переход к исходнику по F4."""
        if not filename:
            return ""
        if self.path_resolver is not None:
            filename = self.path_resolver(filename)
        return file_location(filename, lineno)

    def render_document(self, scenario_name: str, steps: List[RootStep],
                        scenario_path: str = "") -> str:
        self._lines = []
        self._name_counts = {}

        root_name = _ROOT_PREFIX + scenario_name
        self._write(test_suite_started(root_name, self._location(scenario_path)))
        for step in steps:
            self._render_root_step(step)
        self._write(test_suite_finished(root_name))
        # Ведущий перевод строки обязателен: раннер распознаёт service-сообщение
        # только с начала строки, а предыдущий вывод (например, список
        # сценариев) вполне может остаться незавершённым.
        return "\n" + "\n".join(self._lines) + "\n"

    # ── Узлы дерева ─────────────────────────────────────────────────────────

    def _render_root_step(self, step: RootStep) -> None:
        emoji = PLAIN_STATUS_EMOJI.get(step.status, "○")
        name = f"{emoji} {step.name}"
        # Заголовок шага в выводе сценария — до открытия узла (см. докстроку).
        head_pad = " " if self.tree_prefix else ""
        self._write_text(f"{head_pad}{name}{_duration_hint(step.duration)}")

        failure = None
        if step.status == "FAIL":
            failure = (step.failure_error or "Step failed",
                       _failure_details(step.failure_trace or ""))

        has_children = any(isinstance(c, StepNode) for c in step.call_tree)
        # Уровень 1 — вертикаль корневого шага, дети начинаются со второго.
        own_prefix = (" " + get_style(1)[0] + INDENT) if self.tree_prefix else _PLAIN_INDENT
        location = self._location(step.filename, step.lineno)
        with self._node(name, has_children, step.duration, failure, location):
            self._render_children(step.call_tree, own_prefix, level=2)

    def _render_step_node(self, node: StepNode, parent_prefix: str, level: int) -> None:
        vertical, connector, _ = get_style(level)
        # Без глифов отступ не накапливается: заголовки вызовов любой глубины
        # стоят по левому краю, отступ в два пробела отделяет от заголовка
        # только его собственное содержимое.
        own_prefix = (parent_prefix + vertical + INDENT) if self.tree_prefix else _PLAIN_INDENT

        emoji = PLAIN_STATUS_EMOJI.get(node.status, "○")
        module = f" ({node.module})" if node.module else ""
        name = f"{emoji} {node.name}{module}"
        head = f"{parent_prefix}{connector or '·'} " if self.tree_prefix else ""
        self._write_text(f"{head}{name}{_duration_hint(node.duration)}")

        failure = ("Call failed", "") if node.status == "FAIL" else None
        has_children = any(isinstance(c, StepNode) for c in node.children)

        with self._node(name, has_children, node.duration, failure,
                        self._location(node.filename, node.lineno)):
            last_kind = self._render_children(node.children, own_prefix, level + 1)
            if node.return_value is not None:
                # Возврат отделяется пустой строкой от аргументов и вложенных
                # вызовов: это итог вызова, а не ещё одна его переменная.
                if last_kind is not None:
                    self._write_text(own_prefix.rstrip())
                self._write_value(own_prefix, "↲", "", node.return_value)

    def _render_children(self, children: List[Union[StepNode, VarNode]],
                         prefix: str, level: int) -> Optional[str]:
        """
        Вызовы и переменные идут вперемешку — в порядке появления.

        Пустая строка-разделитель ставится только вокруг вызовов: между
        соседними переменными она лишь растягивает вывод. Возвращает вид
        последнего отрисованного потомка (или None, если детей не было) —
        по нему вызывающий решает, нужен ли разделитель перед возвратом.
        """
        last_kind: Optional[str] = None
        for child in children:
            if isinstance(child, StepNode):
                if last_kind is not None:
                    self._write_text(prefix.rstrip())
                last_kind = "step"
                self._render_step_node(child, prefix, level)
            elif isinstance(child, VarNode):
                if self.verbosity < _KIND_MIN_VERBOSITY.get(child.kind, 1):
                    continue
                if last_kind == "step":
                    self._write_text(prefix.rstrip())
                last_kind = "var"
                self._write_value(prefix, _KIND_MARKER.get(child.kind, "·"),
                                  child.key, child.value)
        return last_kind

    # ── Вывод ───────────────────────────────────────────────────────────────

    def _node(self, name: str, is_suite: bool, duration: Optional[float],
              failure: Optional[Tuple[str, str]], location: str = "") -> "_NodeContext":
        return _NodeContext(self, name, is_suite, duration, failure, location)

    def _write(self, line: str) -> None:
        """Записать строку как есть (service-сообщение)."""
        self._lines.append(line)

    def _write_text(self, line: str) -> None:
        """Записать строку обычного вывода узла."""
        self._lines.append(_neutralize(line))

    def _write_value(self, prefix: str, marker: str, key: str, value: Any) -> None:
        """Значение переменной или возврата — с префиксом своего уровня."""
        if key:
            head = f"{prefix}{marker} {markup_escape(key)}:"
        else:
            head = f"{prefix}{marker}"
        # Строки-продолжения многострочного значения выравниваются под ключом
        # и тоже несут префикс уровня — иначе в общем выводе родителя они
        # выглядели бы принадлежащими другому вызову.
        cont_prefix = prefix + "  "
        rendered = _render_markup(f"{head} {markup_value(value, cont_prefix, depth=0)}")
        self._write_text(rendered)

    def unique_name(self, name: str) -> str:
        """Уникализировать имя узла: повторы нумеруются суффиксом ``#N``."""
        seen = self._name_counts.get(name, 0) + 1
        self._name_counts[name] = seen
        return name if seen == 1 else f"{name} #{seen}"


class _NodeContext:
    """
    Контекст узла дерева: открывает suite/test, гарантированно закрывает.

    Узлы с вложенными вызовами обязаны быть suite — только suite образует
    иерархию в протоколе по именам (см. messages.py).
    """

    def __init__(self, writer: TeamCityTreeWriter, name: str, is_suite: bool,
                 duration: Optional[float], failure: Optional[Tuple[str, str]],
                 location: str = "") -> None:
        self._writer = writer
        self._is_suite = is_suite
        # Протокол TeamCity не принимает duration у suite, а IDE меряет
        # wall-clock между testSuiteStarted/testSuiteFinished — все наши
        # service-сообщения печатаются разом в конце сценария, поэтому в
        # дереве оказывалось время рендера отчёта, а не шага. Переносим
        # настоящую длительность в имя узла.
        if is_suite:
            name = f"{name}{_duration_hint(duration)}"
        self._name = writer.unique_name(name)
        self._duration = duration or 0.0
        self._failure = failure
        self._location = location

    def __enter__(self) -> "_NodeContext":
        if self._is_suite:
            self._writer._write(test_suite_started(self._name, self._location))
        else:
            self._writer._write(test_started(self._name, self._location))
        return self

    def __exit__(self, *exc_info: Any) -> None:
        if self._is_suite:
            # У suite нет собственного статуса: он агрегируется по детям,
            # поэтому падение обозначается вложенным упавшим тестом.
            if self._failure is not None:
                message, details = self._failure
                fail_name = self._writer.unique_name("💥 failure")
                self._writer._write(test_started(fail_name, self._location))
                self._writer._write(test_failed(fail_name, message, details))
                self._writer._write(test_finished(fail_name, 0.0))
            self._writer._write(test_suite_finished(self._name))
            return
        if self._failure is not None:
            message, details = self._failure
            self._writer._write(test_failed(self._name, message, details))
        self._writer._write(test_finished(self._name, self._duration))


def _failure_details(trace: str) -> str:
    """
    Отделить traceback от текста ошибки пустой строкой.

    Раннер печатает message и details подряд, а сообщение об ошибке само
    бывает многострочным (например, список несовпавших полей) — без отбивки
    заголовок traceback выглядит его продолжением.
    """
    if not trace:
        return ""
    return "\n" + trace.lstrip("\n")


def _duration_hint(duration: Optional[float]) -> str:
    if duration is None or duration < _MIN_SHOWN_DURATION:
        return ""
    return f"  ⏱ {duration:.2f}s"


def _neutralize(text: str) -> str:
    """
    Обезвредить текст, похожий на service-сообщение.

    Значение переменной вполне может содержать ``##teamcity[...]`` (например,
    захваченный лог чужого прогона), а раннер разбирает такие строки в
    обычном выводе и ломает дерево. Экранирование здесь не поможет — оно
    работает только внутри атрибутов, поэтому разрывается сам префикс.
    """
    return text.replace("##teamcity[", "##_teamcity[")


def _render_markup(markup: str) -> str:
    """
    Развернуть rich-разметку в обычный текст.

    Цвет и ANSI-коды в дереве тестов не нужны, а форматирование вложенных
    структур делает как раз rich, поэтому разметка рендерится, а не
    выбрасывается.
    """
    buf = StringIO()
    console = Console(file=buf, markup=True, highlight=False,
                      force_terminal=False, no_color=True, width=10000)
    console.print(markup)
    return buf.getvalue().rstrip("\n")
