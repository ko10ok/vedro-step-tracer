"""Форматирование значений и линий дерева для stdout-отчёта (rich-markup)."""

from typing import Any, List, Optional, Tuple, Union

from rich.console import Console
from rich.markup import escape as markup_escape

from ..shorten import (
    Chunk,
    max_line_len,
    max_str_len,
    shorten_bytes,
    shorten_lines,
    str_note,
)
from ..unwrap import unwrap_async

__all__ = (
    "markup_value", "markup_rich", "markup_str", "markup_dict", "markup_list",
    "markup_object", "get_style", "get_level_color",
    "LEVEL_STYLES", "LEVEL_COLORS", "INDENT", "DATA_GAP",
)


def markup_value(value: Any, cont_prefix: str, depth: int = 0) -> str:
    """
    Рекурсивно форматирует значение как rich-markup строку.
    cont_prefix — строка-префикс для строк-продолжений (вертикали дерева).
    """
    if depth > 10:
        return "[dim]…[/dim]"

    value, async_note = unwrap_async(value)
    if async_note:
        return (f"[dim]\\[{async_note}][/dim] " +
                markup_value(value, cont_prefix, depth + 1))

    if value is None:
        return "[magenta]None[/magenta]"
    if hasattr(value, "__rich__") or hasattr(value, "__rich_console__"):
        return markup_rich(value, cont_prefix)
    if isinstance(value, bool):
        return f"[magenta]{value}[/magenta]"
    if isinstance(value, (int, float)):
        return f"[blue]{value}[/blue]"
    if isinstance(value, bytes):
        return f"[green]{markup_escape(shorten_bytes(value))}[/green]"
    if isinstance(value, str):
        return markup_str(value, cont_prefix)
    if isinstance(value, dict):
        return markup_dict(value, cont_prefix, depth)
    if isinstance(value, (list, tuple)):
        return markup_list(value, cont_prefix, depth)
    # Произвольный объект
    return markup_object(value, cont_prefix)


def _markup_chunks(text: str, limit: int, cont_prefix: str, style: str) -> str:
    """
    Отрисовать текст построчно, обрезав каждую физическую строку по лимиту.

    Скрытая часть в терминале теряется — полная версия доступна в
    HTML-артефакте, где `…` раскрывается по клику.
    """
    chunks = shorten_lines(text, limit)
    shortened = any(chunk.shortened for chunk in chunks)
    lines = [_markup_chunk(chunk, style) for chunk in chunks]
    rendered = ("\n" + cont_prefix).join(lines)
    if shortened:
        rendered += f" [dim]{markup_escape(str_note(len(text)))}[/dim]"
    return rendered


def _markup_chunk(chunk: Chunk, style: str) -> str:
    body = markup_escape(chunk.head)
    if chunk.shortened:
        body += f"[/{style}][dim]…[/dim][{style}]" + markup_escape(chunk.tail)
    return f"[{style}]{body}[/{style}]"


def markup_rich(renderable: Any, cont_prefix: str, color: bool = False) -> str:
    console = Console(
        force_terminal=color,
        no_color=not color,
    )
    with console.capture() as capture:
        console.print(renderable)

    text = "\n".join(line.rstrip() for line in capture.get().split("\n"))
    return _markup_chunks(text, max_line_len(), cont_prefix, "dim white")


def markup_str(value: str, cont_prefix: str) -> str:
    """Строка: зелёная, с маскировкой паролей и поддержкой многострочности."""
    if "://" in value and "@" in value:
        try:
            from urllib.parse import urlparse, urlunparse
            parsed = urlparse(value)
            if parsed.password:
                replaced = parsed._replace(
                    netloc=(f"{parsed.username}:***@{parsed.hostname}" +
                            (f":{parsed.port}" if parsed.port else ""))
                )
                value = urlunparse(replaced)
        except Exception:
            pass
    if "\n" in value:
        return _markup_chunks(value, max_str_len(), cont_prefix, "green")
    chunk = shorten_lines(value, max_str_len())[0]
    body = _markup_chunk(chunk, "green")
    rendered = f"[green]'[/green]{body}[green]'[/green]"
    if chunk.shortened:
        rendered += f" [dim]{markup_escape(str_note(len(value)))}[/dim]"
    return rendered


def markup_dict(d: dict, cont_prefix: str, depth: int) -> str:
    """Словарь: разворачиваем рекурсивно через фигурные скобки."""
    if not d:
        return "[dim]{}[/dim]"
    items = list(d.items())
    indent = cont_prefix + "    "
    parts = []
    for k, v in items:
        v_str = markup_value(v, indent, depth + 1)
        parts.append(
            f"\n{indent}[yellow]{markup_escape(str(k))}[/yellow][dim]:[/dim] {v_str}"
        )
    return "[dim]{[/dim]" + "".join(parts) + f"\n{cont_prefix}[dim]}}[/dim]"


def markup_list(lst: Union[list, tuple], cont_prefix: str, depth: int) -> str:
    """Список/кортеж: короткие простые — в строку, остальные — разворачиваем."""
    is_list = isinstance(lst, list)
    br_open = "\\[" if is_list else "("
    br_close = "]" if is_list else ")"
    if not lst:
        return f"[dim]{br_open}{br_close}[/dim]"
    # Короткие списки примитивов — inline
    if (len(lst) <= 3 and
            all(isinstance(v, (str, int, float, bool, type(None))) for v in lst)):
        items = [markup_value(v, cont_prefix, depth + 1) for v in lst]
        return (f"[dim]{br_open}[/dim]" +
                "[dim], [/dim]".join(items) +
                f"[dim]{br_close}[/dim]")
    # Разворачиваем
    indent = cont_prefix + "    "
    parts = []
    for i, v in enumerate(lst):
        v_str = markup_value(v, indent, depth + 1)
        idx = markup_escape(f"[{i}]")
        parts.append(f"\n{indent}[dim]{idx}[/dim] {v_str}")
    return (f"[dim]{br_open}[/dim]" +
            "".join(parts) +
            f"\n{cont_prefix}[dim]{br_close}[/dim]")


def markup_object(value: Any, cont_prefix: str) -> str:
    """Произвольный объект — рендер через __dict__ или __str__/repr."""
    # Пробуем str() — у объектов может быть кастомный __str__ с переносами
    s = None
    try:
        s = value.__str__()
    except BaseException:
        pass

    # str() успешен — рендерим построчно, обрезая каждую физическую строку
    if s is not None:
        return _markup_chunks(s, max_line_len(), cont_prefix, "dim white")

    # str() не удался — пробуем рендер через __dict__
    obj_dict = getattr(value, '__dict__', None)
    if obj_dict and isinstance(obj_dict, dict):
        cls_name = type(value).__name__
        header = f"[dim white]{markup_escape(cls_name)}[/dim white]"
        return header + markup_dict(obj_dict, cont_prefix, depth=1)

    # Последний fallback — repr() или имя класса
    try:
        s = repr(value)
    except BaseException:
        s = f"<{type(value).__name__}>"

    return _markup_chunks(s, max_line_len(), cont_prefix, "dim white")


LEVEL_STYLES: List[Optional[Tuple[str, Optional[str], Optional[str]]]] = [
    None,                  # L0 placeholder
    ("║", None, None),     # L1 — корневой шаг (vedro step)
    ("┃", "┣━", "┗━"),     # L2
    ("│", "├─", "└─"),     # L3
    ("┊", "├╴", "└╴"),     # L4
    ("╎", "├╴", "└╴"),     # L5
    ("╎", "├╴", "└╴"),     # L6
    ("╎", "├╴", "└╴"),     # L7+
]

# Яркость линий уменьшается с глубиной вложенности (RGB grey)
LEVEL_COLORS: List[Optional[str]] = [
    None,                   # L0
    None,                   # L1 — без обёртки (plain)
    "rgb(170,170,170)",     # L2
    "rgb(120,120,120)",     # L3
    "rgb(90,90,90)",        # L4
    "rgb(72,72,72)",        # L5
    "rgb(60,60,60)",        # L6
    "rgb(52,52,52)",        # L7+
]


def get_style(level: int) -> Tuple[str, Optional[str], Optional[str]]:
    idx = min(level, len(LEVEL_STYLES) - 1)
    style = LEVEL_STYLES[idx]
    if style is None:
        return ("║", None, None)
    return style


def get_level_color(level: int) -> Optional[str]:
    idx = min(level, len(LEVEL_COLORS) - 1)
    return LEVEL_COLORS[idx]


INDENT = "  "
DATA_GAP = "  "
