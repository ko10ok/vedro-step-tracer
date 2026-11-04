"""Имена файлов отчётов: санитизация и очистка старых отчётов.

Имя отчёта строится из subject сценария, а там встречается что угодно —
двоеточия, слэши, кавычки. Такие символы ломают путь (`/`), несовместимы с
Windows/сетевыми ФС (`:`, `?`, `*`, `"`, `<`, `>`, `|`) и требуют
экранирования в ссылках, которые печатаются в терминал и в GitLab CI.
Поэтому имя всегда приводится к безопасному виду.
"""

import os
import re
from typing import List

__all__ = ("sanitize_filename", "cleanup_reports",)

# Символы, недопустимые в именах файлов хотя бы на одной из целевых ФС,
# плюс управляющие символы.
_UNSAFE_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')
# Пробельные последовательности схлопываются в одно подчёркивание: имена
# отчётов часто попадают в ссылки, где пробелы приходится экранировать.
_SPACE_RE = re.compile(r"\s+")
_UNDERSCORE_RE = re.compile(r"_{2,}")

_FALLBACK_NAME = "scenario"


def sanitize_filename(name: str, max_length: int = 80) -> str:
    """
    Привести произвольную строку к безопасному имени файла (без расширения).

    Небезопасные символы и пробелы заменяются подчёркиванием, повторы
    схлопываются, точки и подчёркивания по краям убираются (имя, начинающееся
    с точки, скрыто в файловых менеджерах). Пустой результат заменяется на
    ``scenario``, чтобы отчёт не превратился в файл без имени.
    """
    cleaned = _UNSAFE_RE.sub("_", name)
    cleaned = _SPACE_RE.sub("_", cleaned)
    cleaned = _UNDERSCORE_RE.sub("_", cleaned)
    cleaned = cleaned.strip("._ ")
    if max_length > 0:
        cleaned = cleaned[:max_length].strip("._ ")
    return cleaned or _FALLBACK_NAME


def cleanup_reports(output_dir: str, suffix: str = ".html") -> List[str]:
    """
    Удалить ранее сохранённые отчёты из директории вывода.

    Удаляются только файлы с нужным расширением и только в самой директории
    (без рекурсии): она может быть смонтирована рядом с другими артефактами,
    и сносить её целиком небезопасно. Возвращает список удалённых путей;
    ошибки доступа игнорируются — очистка не должна ронять прогон тестов.
    """
    removed: List[str] = []
    try:
        entries = os.listdir(output_dir)
    except OSError:
        return removed

    for entry in entries:
        if not entry.endswith(suffix):
            continue
        path = os.path.join(output_dir, entry)
        if not os.path.isfile(path):
            continue
        try:
            os.remove(path)
        except OSError:
            continue
        removed.append(path)
    return removed
