"""Чтение исходного кода по кадрам traceback — общее для всех форматов отчёта.

Модуль намеренно не знает ни про HTML, ни про терминал: он только достаёт
строки кода и границы фрагмента, а разметку добавляет конкретный рендерер
(см. reporting/html/traceback.py и reporting/llm/traceback.py).
"""

import inspect
from types import TracebackType
from typing import Any, List, Optional, Tuple

__all__ = (
    "dedent_lines", "get_full_function_lines", "read_file_lines",
    "iter_tb_frames", "compact_bounds",
)

# Сколько строк кода показывать вокруг упавшей строки в свёрнутом виде.
_COMPACT_BEFORE = 2
_COMPACT_AFTER = 3


def dedent_lines(lines: List[str]) -> List[str]:
    """
    Убирает общий для всех строк отступ (аналог textwrap.dedent), чтобы
    вложенный код (например, метод внутри класса) не начинался с большого
    количества пустых пробелов слева — так фрагмент читается заметно проще.
    """
    indents = [len(line) - len(line.lstrip(" ")) for line in lines if line.strip()]
    if not indents:
        return lines
    min_indent = min(indents)
    if min_indent == 0:
        return lines
    return [line[min_indent:] if len(line) >= min_indent else line.lstrip(" ")
            for line in lines]


def get_full_function_lines(frame: Any) -> Optional[Tuple[List[str], int]]:
    """
    Получить исходный код всей функции, в которой находится кадр, целиком
    (через inspect, с учётом декораторов и т.п.). Возвращает список строк
    (без завершающих переносов) и номер первой строки.
    """
    try:
        source_lines, start_line = inspect.getsourcelines(frame)
    except (OSError, TypeError):
        return None
    return [line.rstrip("\n") for line in source_lines], start_line


def read_file_lines(filename: str) -> Optional[List[str]]:
    """Прочитать файл построчно; None, если файл недоступен (напр. <string>)."""
    try:
        with open(filename, "r") as code_file:
            return code_file.read().splitlines()
    except OSError:
        return None


def compact_bounds(lineno: int, total_lines: int) -> Tuple[int, int]:
    """Границы (start, end) короткого фрагмента вокруг упавшей строки."""
    start = max(lineno - _COMPACT_BEFORE, 0)
    end = min(lineno + _COMPACT_AFTER, total_lines)
    return start, end


def iter_tb_frames(tb: Optional[TracebackType]) -> List[TracebackType]:
    """Развернуть цепочку traceback в список кадров (от внешнего к упавшему)."""
    frames: List[TracebackType] = []
    current = tb
    while current is not None:
        frames.append(current)
        current = current.tb_next
    return frames
