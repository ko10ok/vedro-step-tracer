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
2. ``str`` — лимит ``max_str_len`` применяется к каждой физической строке
   отдельно (переносы разделяют).
3. ``bytes`` — отдаются как ``[bytes, 672 bytes, preview=...]``.
4. Нестандартные объекты (рендер через ``__str__``/``repr``/rich) — отдельный
   лимит ``max_line_len`` на каждую физическую строку независимо;
   многострочная структура сохраняется целиком.
"""

from typing import List, NamedTuple

from .. import settings

__all__ = (
    "Chunk", "shorten_line", "shorten_lines", "shorten_bytes",
    "str_note", "max_str_len", "max_line_len",
    "TAIL_RATIO", "BYTES_PREVIEW_LEN",
)

# Какая доля лимита остаётся видимой в хвосте значения: начало важнее конца,
# но конец позволяет узнать, чем значение закончилось (скобка, подпись и т.п.).
TAIL_RATIO = 10

# Длина превью бинарных данных: читать их всё равно нельзя, важна только
# сигнатура начала.
BYTES_PREVIEW_LEN = 64


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


def max_str_len() -> int:
    """Текущий лимит длины строкового значения (на физическую строку)."""
    return settings.MAX_STR_LEN


def max_line_len() -> int:
    """Текущий лимит длины одной физической строки нестандартного объекта."""
    return settings.MAX_LINE_LEN


def shorten_line(text: str, limit: int) -> Chunk:
    """Разбить одну строку на видимую голову, скрытую середину и хвост."""
    if limit <= 0 or len(text) <= limit:
        return Chunk(text, "", "")
    tail_len = max(1, limit // TAIL_RATIO)
    head_len = limit - tail_len
    return Chunk(text[:head_len], text[head_len:len(text) - tail_len], text[len(text) - tail_len:])


def shorten_lines(text: str, limit: int) -> List[Chunk]:
    """Разбить многострочный текст: лимит применяется к каждой строке отдельно."""
    return [shorten_line(line, limit) for line in text.split("\n")]


def str_note(total_chars: int, type_name: str = "str") -> str:
    """Подпись о реальном размере сокращённого значения."""
    return f"[{type_name}, {total_chars} chars]"


def shorten_bytes(value: bytes, limit: int = -1) -> str:
    """
    Компактное представление ``bytes``: ``[bytes, 672 bytes, preview=...]``.

    Короткие значения отдаются как обычный ``repr`` — подпись о размере для
    них лишний шум. Превью намеренно короткое: бинарные данные нечитаемы,
    и смысл есть только в сигнатуре начала (``\\x89PNG`` и т.п.).
    """
    limit = BYTES_PREVIEW_LEN if limit < 0 else limit
    try:
        raw = repr(value)
    except BaseException:
        raw = f"<{type(value).__name__}>"
    if len(raw) <= limit:
        return raw
    return f"[bytes, {len(value)} bytes, preview={raw[:limit]}…]"
