"""Конфиг плагина (vedro PluginConfig)."""

from typing import List, Optional

from vedro.core import PluginConfig

from .exclude import DEFAULT_EXCLUDED_VALUE_TYPES, ExcludeRule
from .plugin import VedroStepTracerPlugin
from .report_types import ReportType
from .test_status import TestStatus

__all__ = ("VedroStepTracer", "ReportType", "TestStatus",)


class VedroStepTracer(PluginConfig):
    plugin = VedroStepTracerPlugin

    # Директории для отслеживания (относительно рабочей папки)
    target_dirs: List[str] = ["helpers", "contexts", "interfaces"]

    # Файлы внутри target_dirs, вызовы из которых не попадают в дерево
    # (glob-паттерны, например "interfaces/api_client.py").
    # Исключение означает «не создавать узел для вызовов из этого файла»:
    # вложенные целевые вызовы сохраняются и прицепляются к ближайшему
    # не исключённому предку.
    exclude_paths: List[str] = []

    # Имена функций, которые не попадают в дерево (по тому же правилу).
    exclude_functions: List[str] = []

    # Правила исключения ЗНАЧЕНИЙ переменных из снимка (а не вызовов целиком)
    # — объекты вроде пайпов/сокетов/транспортов asyncio/ssl не копируются
    # безопасно и не должны оставаться живыми ссылками в дереве трейса дольше
    # шага. По умолчанию — уже найденные проблемные типы (см.
    # exclude.DEFAULT_EXCLUDED_VALUE_TYPES); можно переопределить
    # целиком, если дефолты не подходят. Подробности и все варианты правил
    # (тип, имя типа, module(), regex, callable, var()) — см. docs/exclude.md.
    exclude_value_types: List[ExcludeRule] = list(DEFAULT_EXCLUDED_VALUE_TYPES)

    # Дополнительные правила поверх exclude_value_types — тот же набор
    # возможностей, без необходимости переписывать базовый список целиком.
    extra_exclude_value_types: List[ExcludeRule] = []

    # Куда сохранять файловые отчёты (используется только при непустом save_to_dir)
    output_dir: str = "logs/traces"

    # Сохранять отчёт в директорию артефактов сценария (.vedro/artifacts,
    # раскладка plugins.artifacted) — рядом с prompt-файлами и дампами.
    # Файл пишется напрямую, артефактом vedro не прикрепляется: в результате
    # сценария остаётся одна строка со ссылкой на отчёт.
    attach_artifacts: bool = True

    # Формат(ы) файлового отчёта: ReportType.HTML (по умолчанию, та же
    # вёрстка со схлопываемыми секциями и подсветкой значений),
    # ReportType.MARKDOWN (тот же порядок блоков, но простой Markdown с
    # <details>/<summary> вместо HTML-вёрстки значений — удобно смотреть
    # прямо в GitLab/GitHub UI без скачивания файла) либо оба сразу:
    # report_formats = [ReportType.HTML, ReportType.MARKDOWN].
    # ReportType — не enum, а строковые константы, поэтому значения можно
    # задавать и напрямую текстом (без учёта регистра), например из
    # переменной окружения в CI: report_formats = os.environ['FORMATS'].split(',').
    report_formats: List[str] = [ReportType.HTML]

    # События, по которым сохранять отчёт в output_dir: "failed" и/или "passed".
    # При --tr файл пишется всегда.
    save_to_dir: List[str] = [TestStatus.FAILED]

    # Печатать полное дерево трейса в stdout. По умолчанию выключено: отчёт
    # уходит в артефакт, а в stdout остаётся только ссылка на него. Полное
    # дерево печатается при явном --tr.
    print_to_stdout: bool = False

    # Максимальная длина строкового значения перед сокращением.
    # Применяется к каждой физической строке отдельно.
    max_str_len: int = 1000

    # Максимальная длина одной физической строки в выводе нестандартного
    # объекта (рендер через __str__/repr/rich, например HTTP-трейс).
    max_line_len: int = 1000

    # Схлопывать транзитные цепочки вызовов: обёртка без собственных
    # переменных, с одним вложенным вызовом и тем же возвращаемым объектом
    # печаталась отдельным уровнем с тем же значением. Схлопывание без
    # потерь — имена звеньев остаются в хлебной крошке
    # "SomeProject ▸ load_data → DataClient ▸ fetch".
    collapse_passthrough: bool = True

    # ID job'а GitLab CI (например, job_id = os.environ.get('CI_JOB_ID')).
    # По умолчанию не заполнен (локальный запуск). Его наличие используется
    # для автоопределения запуска в GitLab CI, если флаг --tr-gitlab не
    # передан явно.
    job_id: str = ""

    # Паттерн ссылки на артефакт GitLab CI с плейсхолдерами {job_id} и {path},
    # например:
    # "https://gitlab.example.com/group/SomeProject/-/jobs/{job_id}/artifacts/file/{path}"
    # Используется для ссылки на Trace report только если job_id заполнен
    # (запуск в GitLab CI); при локальном запуске ссылка формируется через локальный file:// путь.
    artifact_url_pattern: str = ""

    # Корень проекта на хостовой машине, подставляемый в хостовые ссылки
    # на файлы (см. gitlab.to_host_path). По умолчанию берётся из
    # переменной окружения HOST_PROJECT_ROOT_DIRECTORY; пустая строка
    # (как в CI, так и при локальном запуске без переменной) означает, что
    # хостовые ссылки не строятся — путь остаётся как есть.
    host_project_root_directory: str = ""

    # Подпуть рабочей директории относительно корня репозитория,
    # используемый при формировании хостовых и артефактных ссылок.
    # Пустая строка означает, что рабочая директория — корень репозитория.
    workdir_subpath: str = ""

    # Удалять ранее сохранённые отчёты из output_dir перед прогоном.
    # Иначе директория копится от запуска к запуску, и среди старых файлов
    # трудно найти отчёт текущего прогона. Удаляются только файлы активного
    # формата (report_format) в самой output_dir, без рекурсии
    # (см. filenames.cleanup_reports).
    cleanup_before: bool = True

    # Выводить дерево шагов service-сообщениями TeamCity — тогда шаги и
    # вложенные вызовы видны деревом в тест-раннере PyCharm (встроенный
    # репортёр vedro сообщает IDE только о сценариях).
    # None — определять автоматически: выбран репортёр `-r pycharm` либо
    # прогон идёт под IDE/TeamCity (см. teamcity_env_vars).
    teamcity: Optional[bool] = None

    # Переменные окружения, наличие которых означает запуск под
    # PyCharm/TeamCity (используются при teamcity = None).
    teamcity_env_vars: List[str] = ["PYCHARM_HOSTED", "TEAMCITY_VERSION", "PYCHARM_HELPERS_DIR"]

    # Рисовать глифы дерева ("║  ┃  │  ├╴ ") перед строками в режиме TeamCity.
    # False — печатать только заголовки и содержимое: внутри развёрнутого
    # узла вложенность видна и без них, а отступы съедают ширину под значения.
    teamcity_tree_prefix: bool = False
