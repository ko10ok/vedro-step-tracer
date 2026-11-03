"""GitLab CI-специфика: схлопываемые секции лога и ссылки на артефакты."""

import os
import time
from typing import Optional
from urllib.parse import quote

__all__ = (
    "SectionIdGenerator", "section_start", "section_end",
    "to_host_path", "to_relative_path", "to_artifact_url", "make_terminal_link",
)


class SectionIdGenerator:
    """Выдаёт уникальные идентификаторы секций в пределах одного отчёта."""

    def __init__(self, prefix: str = "tr") -> None:
        self._prefix = prefix
        self._counter = 0

    def next_id(self) -> str:
        self._counter += 1
        return f"{self._prefix}{self._counter}"


def section_start(section_id: str, collapsed: bool = True) -> str:
    """Маркер начала схлопываемой секции GitLab CI (пишется перед заголовком)."""
    ts = int(time.time())
    opts = "[collapsed=true]" if collapsed else ""
    return f"\033[0Ksection_start:{ts}:{section_id}{opts}\r\033[0K"


def section_end(section_id: str) -> str:
    """Маркер конца схлопываемой секции GitLab CI."""
    ts = int(time.time())
    return f"\033[0Ksection_end:{ts}:{section_id}\r\033[0K\n"


def to_host_path(filepath: str, project_root: str, workdir_subpath: str) -> str:
    """
    Преобразовать путь в рабочей директории в путь на хостовой машине.

    Если задан `HOST_PROJECT_ROOT_DIRECTORY`, к корню проекта на хосте
    добавляются подпуть рабочей директории и относительный путь к файлу.
    """
    host_root = os.environ.get("HOST_PROJECT_ROOT_DIRECTORY")
    if not host_root:
        return filepath
    try:
        rel_path = os.path.relpath(filepath, project_root)
    except ValueError:
        return filepath
    if rel_path.startswith(".."):
        return filepath
    return os.path.join(host_root, workdir_subpath, rel_path)


def to_relative_path(filepath: str, project_root: str) -> str:
    """
    Преобразовать путь внутри контейнера в путь относительно рабочей
    директории (workdir) тестов — `project_root`.

    Используется для блока с кодом из traceback: там удобнее видеть короткий
    путь относительно workdir, а не абсолютный путь на хосте. Файлы вне
    workdir (например, сторонние библиотеки) остаются нетронутыми
    (абсолютный путь как есть).
    """
    try:
        rel_path = os.path.relpath(filepath, project_root)
    except ValueError:
        return filepath
    if rel_path.startswith(".."):
        return filepath
    return rel_path


def to_artifact_url(filepath: str, project_root: str, job_id: str,
                    url_pattern: str, workdir_subpath: str) -> Optional[str]:
    """
    Построить ссылку на прикреплённый артефакт GitLab CI (job_id известен —
    сборка запущена именно в GitLab CI).

    Паттерн задаётся переменной окружения PROJECT_ARTIFACT_PATTERN (см.
    VedroStepTracer.artifact_url_pattern) с плейсхолдерами {job_id} и {path},
    например:
    "https://gitlab.example.com/group/SomeProject/-/jobs/{job_id}/artifacts/file/{path}"

    Если job_id или паттерн не заданы (локальный запуск) — возвращает None,
    и вызывающий код должен использовать локальную file:// ссылку.
    """
    if not job_id or not url_pattern:
        return None
    try:
        rel_path = os.path.relpath(filepath, project_root)
    except ValueError:
        return None
    if rel_path.startswith(".."):
        return None
    artifact_path = os.path.join(workdir_subpath, rel_path)
    try:
        return url_pattern.format(job_id=job_id, path=artifact_path)
    except (KeyError, IndexError):
        return None


def make_terminal_link(path: str) -> str:
    """
    Вернуть путь как file:// URI, чтобы терминал сам распознал его как
    кликабельную ссылку на файл.

    Изначально использовалась OSC 8 hyperlink escape-последовательность
    (ESC]8;;URI ESC\\ TEXT ESC]8;;ESC\\), но репортёр vedro выводит
    extra_details через rich/logging-конвейер, который не пропускает
    "сырые" управляющие последовательности — в терминале виден только
    обычный текст без ссылки.

    Более надёжный кроссплатформенный вариант — просто вывести сам file://
    URI: большинство терминалов (Terminal.app и iTerm2 на macOS; GNOME
    Terminal, Konsole, kitty, VS Code на Linux) автоматически подсвечивают
    и делают кликабельными строки, распознанные как URL, без необходимости
    в OSC 8.
    """
    abs_path = os.path.abspath(path)
    return "file://" + quote(abs_path, safe="/:")
