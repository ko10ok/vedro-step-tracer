"""
Единая логика сокращения длинных значений для всех рендереров.

В дереве (`tracing/`) всегда лежит полное значение — сокращение живёт только
в слое отображения. Причина: в HTML сокращение обратимо (скрытый хвост
раскрывается по клику), а в терминале и тест-раннере IDE — нет.

Поэтому функции модуля не возвращают готовую строку, а отдают структуру
:class:`Chunk` (видимая голова, скрытая середина, видимый хвост). Рендерер
сам решает, выбросить скрытую часть (terminal/teamcity/llm) или спрятать её
под раскрывающийся элемент (html).

Правила сокращения:

1. Стандартные контейнеры (``dict``/``list``/``tuple``) обходятся рекурсивно
   самими рендерерами — структура не режется, сокращаются только
   строки-листья.
2. Один набор лимитов применяется ко всем типам значений (``str``, ``bytes``,
   нестандартные объекты): ``max_line_len`` на каждую физическую строку,
   ``max_lines``/``max_total_len`` на всё значение целиком.
3. ``bytes`` — отдаются как ``[bytes, 672 bytes, preview=...]``.
4. Нестандартные объекты (рендер через ``__str__``/``repr``/rich) режутся
   теми же лимитами, что и строки; многострочная структура сохраняется.
"""

from typing import List, NamedTuple

from .. import settings

__all__ = (
    "Chunk", "shorten_line", "shorten_lines", "shorten_bytes", "str_note",
    "max_line_len", "max_hidden_len", "max_total_len", "max_lines",
    "max_collection_items", "chunks_truncated", "TAIL_RATIO",
)

# Какая доля лимита остаётся видимой в хвосте значения: начало важнее конца,
# но конец позволяет узнать, чем значение закончилось (скобка, подпись и т.п.).
TAIL_RATIO = 10


class Chunk(NamedTuple):
    """Одна физическая строка, разбитая на видимую и скрытую части."""

    head: str
    hidden: str
    tail: str

    @property
    def shortened(self) -> bool:
        return bool(self.hidden)

    @property
    def total(self) -> int:
        return len(self.head) + len(self.hidden) + len(self.tail)

    def flat(self) -> str:
        """Текст без скрытой части — для рендереров без раскрытия."""
        if not self.hidden:
            return self.head
        return f"{self.head}…{self.tail}"


def max_line_len() -> int:
    """Текущий лимит длины одной физической строки любого значения."""
    return settings.MAX_LINE_LEN


def max_hidden_len() -> int:
    """Текущий предел скрытой (раскрываемой) части одной строки."""
    return settings.MAX_HIDDEN_LEN


def max_total_len() -> int:
    """Текущий предел суммарной длины текста одного значения."""
    return settings.MAX_TOTAL_LEN


def max_lines() -> int:
    """Текущий предел числа физических строк одного значения."""
    return settings.MAX_LINES


def max_collection_items() -> int:
    """Текущий предел числа элементов dict/list, попадающих в отчёт."""
    return settings.MAX_COLLECTION_ITEMS


def shorten_line(text: str, limit: int) -> Chunk:
    """Разбить одну строку на видимую голову, скрытую середину и хвост."""
    if limit <= 0 or len(text) <= limit:
        return Chunk(text, "", "")
    tail_len = max(1, limit // TAIL_RATIO)
    head_len = limit - tail_len
    hidden = text[head_len:len(text) - tail_len]
    hidden_limit = max_hidden_len()
    if len(hidden) > hidden_limit:
        hidden = hidden[:hidden_limit]
    return Chunk(text[:head_len], hidden, text[len(text) - tail_len:])


def shorten_lines(text: str, limit: int) -> List[Chunk]:
    """Разбить многострочный текст: лимит применяется к каждой строке отдельно."""
    total_limit = max_total_len()
    lines_limit = max_lines()
    if len(text) > total_limit:
        text = text[:total_limit]
    lines = text.split("\n", lines_limit)
    if len(lines) > lines_limit:
        lines = lines[:lines_limit]
    return [shorten_line(line, limit) for line in lines]


def chunks_truncated(text: str, chunks: List[Chunk]) -> bool:
    """Потерян ли при сокращении хоть какой-то текст исходного значения."""
    if not chunks:
        return bool(text)
    retained = sum(chunk.total for chunk in chunks) + (len(chunks) - 1)
    return retained < len(text)


def str_note(total_chars: int, type_name: str = "str") -> str:
    """Подпись о реальном размере сокращённого значения."""
    return f"[{type_name}, {total_chars} chars]"


def shorten_bytes(value: bytes, limit: int = -1) -> str:
    """
    Компактное представление ``bytes``: ``[bytes, 672 bytes, preview=...]``.

    Короткие значения отдаются как обычный ``repr`` — подпись о размере для
    них лишний шум. Бинарные данные нечитаемы, поэтому показывается только
    сигнатура начала (``\\x89PNG`` и т.п.); длина превью — общий ``max_line_len``.
    """
    limit = max_line_len() if limit < 0 else limit
    try:
        raw = repr(value)
    except BaseException:
        raw = f"<{type(value).__name__}>"
    if len(raw) <= limit:
        return raw
    return f"[bytes, {len(value)} bytes, preview={raw[:limit]}…]"
