"""Рендеринг значений переменных и возвратов в HTML."""

from typing import Any, Union

from rich.console import Console

from ..shorten import Chunk, max_line_len, max_str_len, shorten_bytes, shorten_lines, str_note
from ..secrets import mask_secrets
from ..unwrap import unwrap_async
from .escaping import esc

__all__ = (
    "html_value", "html_str", "html_dict", "html_list", "html_object",
    "html_preview", "needs_return_block", "render_html_rich",
)

# Максимальная длина однострочного превью значения в заголовке блока.
_HTML_PREVIEW_LEN = 80


def render_html_rich(value: Any) -> str:
    console = Console(
        force_terminal=False,
        no_color=True,
    )
    with console.capture() as capture:
        console.print(value)

    lines = capture.get().split("\n")

    colored_lines = [line.rstrip() for line in lines]
    return '\n' + "\n".join(colored_lines) + '\n'


def html_preview(value: Any) -> str:
    """Короткое однострочное превью значения для заголовка блока вызова."""
    value, _ = unwrap_async(value)
    if value is None:
        return "None"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, bytes):
        s = repr(value)
    elif hasattr(value, "__rich__") or hasattr(value, "__rich_console__"):
        s = render_html_rich(value)
    elif isinstance(value, str):
        s = mask_secrets(value).replace("\n", "⏎")
    elif isinstance(value, dict):
        if not value:
            s = "{}"
        else:
            keys_preview = ", ".join(str(k) for k in list(value)[:3])
            s = "{ " + keys_preview + (", …" if len(value) > 3 else "") + " }"
    elif isinstance(value, (list, tuple)):
        ob, cb = ("[", "]") if isinstance(value, list) else ("(", ")")
        s = ob + cb if not value else f"{ob}…{len(value)} items…{cb}"
    else:
        try:
            s = str(value)
        except Exception:
            s = f"<{type(value).__name__}>"
        s = s.replace("\n", "⏎")
    s = s.strip()
    if len(s) > _HTML_PREVIEW_LEN:
        s = s[:_HTML_PREVIEW_LEN - 1] + "…"
    return s


def needs_return_block(value: Any) -> bool:
    """Нужен ли развёрнутый блок возврата помимо превью в заголовке."""
    if value is None:
        return False
    if isinstance(value, (bool, int, float)):
        return False
    if isinstance(value, str):
        return len(value) > _HTML_PREVIEW_LEN or "\n" in value
    return True


def html_value(value: Any, depth: int = 0) -> str:
    """Рекурсивно рендерит значение как HTML с подсветкой типов (тема терминала)."""
    if depth > 10:
        return '<span class="v-dim">…</span>'

    value, async_note = unwrap_async(value)
    if async_note:
        return (f'<span class="v-dim">[{async_note}]</span> ' +
                html_value(value, depth + 1))

    if value is None:
        return '<span class="v-none">None</span>'
    if hasattr(value, "__rich__") or hasattr(value, "__rich_console__"):
        return _html_chunks(render_html_rich(value), max_line_len(), "v-str")
    if isinstance(value, bool):
        return f'<span class="v-bool">{value}</span>'
    if isinstance(value, (int, float)):
        return f'<span class="v-num">{esc(value)}</span>'
    if isinstance(value, bytes):
        return f'<span class="v-str">{esc(shorten_bytes(value))}</span>'
    if isinstance(value, str):
        return html_str(value)
    if isinstance(value, dict):
        return html_dict(value, depth)
    if isinstance(value, (list, tuple)):
        return html_list(value, depth)
    return html_object(value)


def _html_chunk(chunk: Chunk) -> str:
    """
    Одна физическая строка с обратимым сокращением.

    Скрытый хвост остаётся в документе: клик по `…` раскрывает строку
    целиком, поиск по отчёту находит текст и в свёрнутом виде.
    """
    head = esc(chunk.head).replace("\n", "<br>")
    if not chunk.shortened:
        return head
    hidden = esc(chunk.hidden).replace("\n", "<br>")
    tail = esc(chunk.tail).replace("\n", "<br>")
    return (
        f'{head}<span class="v-cut">'
        f'<span class="v-cut-dots" title="Показать полностью">…</span>'
        f'<span class="v-cut-rest">{hidden}</span>'
        f'</span>{tail}'
    )


def _html_chunks(text: str, limit: int, css_class: str) -> str:
    """Построчное обратимое сокращение многострочного текста."""
    chunks = shorten_lines(text, limit)
    body = "<br>".join(_html_chunk(chunk) for chunk in chunks)
    rendered = f'<span class="{css_class}">{body}</span>'
    if any(chunk.shortened for chunk in chunks):
        rendered += f' <span class="v-size">{esc(str_note(len(text)))}</span>'
    return rendered


def html_str(value: str, shortable: bool = True) -> str:
    value = mask_secrets(value)
    if not shortable:
        escaped = esc(value).replace("\n", "<br>")
        return f'<span class="v-str">{escaped}</span>'
    chunks = shorten_lines(value, max_str_len())
    body = "<br>".join(_html_chunk(chunk) for chunk in chunks)
    rendered = f'<span class="v-str">\'{body}\'</span>'
    if any(chunk.shortened for chunk in chunks):
        rendered += f' <span class="v-size">{esc(str_note(len(value)))}</span>'
    return rendered


def html_dict(d: dict, depth: int) -> str:
    if not d:
        return '<span class="v-dim">{}</span>'
    preview = ", ".join(str(k) for k in list(d)[:3])
    if len(d) > 3:
        preview += ", …"
    parts = [
        f'<details class="v-fold" open>'
        f'<summary><span class="v-brace">{{</span>'
        f'<span class="v-fold-hint"> {esc(preview)} </span>'
        f'</summary><div class="v-body">'
    ]
    for k, v in d.items():
        v_html = html_value(v, depth + 1)
        parts.append(
            f'<div class="v-entry"><span class="v-key">{esc(k)}</span>'
            f'<span class="v-dim">:</span> {v_html}</div>'
        )
    parts.append('</div><span class="v-brace">}</span></details>')
    return "".join(parts)


def html_list(lst: Union[list, tuple], depth: int) -> str:
    is_list = isinstance(lst, list)
    ob, cb = ("[", "]") if is_list else ("(", ")")
    if not lst:
        return f'<span class="v-dim">{ob}{cb}</span>'
    if (len(lst) <= 3 and
            all(isinstance(v, (str, int, float, bool, type(None))) for v in lst)):
        items = [html_value(v, depth + 1) for v in lst]
        return (f'<span class="v-wrap"><span class="v-brace">{ob}</span>' +
                '<span class="v-dim">, </span>'.join(items) +
                f'<span class="v-brace">{cb}</span></span>')
    hint = f"{len(lst)} items"
    parts = [
        f'<details class="v-fold" open>'
        f'<summary><span class="v-brace">{esc(ob)}</span>'
        f'<span class="v-fold-hint"> {hint} </span>'
        f'</summary><div class="v-body">'
    ]
    for i, v in enumerate(lst):
        v_html = html_value(v, depth + 1)
        parts.append(f'<div class="v-entry"><span class="v-dim">[{i}]</span> {v_html}</div>')
    parts.append(f'</div><span class="v-brace">{esc(cb)}</span></details>')
    return "".join(parts)


def html_object(value: Any) -> str:
    s = None
    try:
        s = value.__str__()
    except BaseException:
        pass

    if s is not None:
        return _html_chunks(s, max_line_len(), "v-obj")

    obj_dict = getattr(value, "__dict__", None)
    if obj_dict and isinstance(obj_dict, dict):
        cls_name = type(value).__name__
        return f'<span class="v-obj">{esc(cls_name)}</span>{html_dict(obj_dict, 1)}'

    try:
        s = repr(value)
    except BaseException:
        s = f"<{type(value).__name__}>"
    return _html_chunks(s, max_line_len(), "v-obj")
