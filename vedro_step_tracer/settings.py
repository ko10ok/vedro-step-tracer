"""
Изменяемые в рантайме настройки трейсера.

Значения читаются форматтерами через модуль (``settings.MAX_LINE_LEN``), а не
импортируются по имени: плагин переопределяет их из конфига при старте, и
импорт по имени зафиксировал бы значение по умолчанию.
"""

from typing import Set

__all__ = (
    "MAX_LINE_LEN", "MAX_HIDDEN_LEN", "MAX_TOTAL_LEN", "MAX_LINES",
    "MAX_COLLECTION_ITEMS", "FILTERED_KEYS",
    "set_max_line_len", "set_max_hidden_len", "set_max_total_len",
    "set_max_lines", "set_max_collection_items",
)

# Максимальная длина одной физической строки любого значения (str, bytes,
# нестандартный объект через __str__/repr/rich). Переносы строк разделяют:
# каждая линия режется независимо, структура сохраняется.
MAX_LINE_LEN: int = 1000

# Абсолютные пределы, защищающие от мегабайтных значений (например, 2 МБ
# бинарных данных в __str__ объекта): реверс нужен для обычных длинных
# значений, но весь бинарный payload в отчёт тянуть нельзя.
MAX_HIDDEN_LEN: int = 20_000   # скрытая (раскрываемая) часть одной строки
MAX_TOTAL_LEN: int = 50_000    # суммарная длина текста одного значения
MAX_LINES: int = 1_000         # число физических строк одного значения
MAX_COLLECTION_ITEMS: int = 1_000  # число элементов dict/list, попадающих в отчёт

# Служебные имена, которые никогда не попадают в дерево переменных.
FILTERED_KEYS: Set[str] = {"self", "__class__", "__builtins__"}


def set_max_line_len(value: int) -> None:
    """Переопределить лимит длины физической строки (из конфига)."""
    global MAX_LINE_LEN
    MAX_LINE_LEN = value


def set_max_hidden_len(value: int) -> None:
    """Переопределить предел скрытой части одной строки."""
    global MAX_HIDDEN_LEN
    MAX_HIDDEN_LEN = value


def set_max_total_len(value: int) -> None:
    """Переопределить предел суммарной длины текста одного значения."""
    global MAX_TOTAL_LEN
    MAX_TOTAL_LEN = value


def set_max_lines(value: int) -> None:
    """Переопределить предел числа физических строк одного значения."""
    global MAX_LINES
    MAX_LINES = value


def set_max_collection_items(value: int) -> None:
    """Переопределить предел числа элементов dict/list в отчёте."""
    global MAX_COLLECTION_ITEMS
    MAX_COLLECTION_ITEMS = value
