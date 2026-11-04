"""Plain-text рендеринг traceback и ошибки для LLM-выжимки отчёта.

Структура повторяет HTML-версию по данным (те же кадры, тот же выбор
фрагмента кода), но подаётся линейно и без разметки: у LLM нет возможности
«развернуть» блок, поэтому всё, что в HTML спрятано под сворачивание,
здесь печатается сразу.

Порядок кадров — как в обычном Python-traceback (от внешнего вызова к месту
падения), чтобы формат был узнаваемым. Последний кадр дополнительно помечен
как место падения, а сама упавшая строка — маркером ``>``.
"""

from types import TracebackType
from typing import Callable, List, Optional

from ..source import compact_bounds, dedent_lines, get_full_function_lines, iter_tb_frames, read_file_lines

__all__ = ("render_tb_text", "render_failure_text",)

_INDENT = "  "


def _code_rows(lines: List[str], start_line: int, lineno: int,
               indent: str) -> List[str]:
    """Строки кода с номерами; упавшая строка помечена ``>``."""
    width = len(str(start_line + len(lines) - 1))
    rows = []
    for offset, code_line in enumerate(lines):
        line_no = start_line + offset
        marker = ">" if line_no == lineno else " "
        rows.append(f"{indent}{marker} {line_no:>{width}} | {code_line}")
    return rows


def _render_frame(tb: TracebackType, scenario_path: str, position: str,
                  path_mapper: Optional[Callable[[str], str]] = None) -> List[str]:
    """
    Один кадр traceback: заголовок с файлом/строкой/функцией и фрагмент кода.

    Для файла сценария показывается функция целиком (как в HTML, где она
    доступна по разворачиванию), для промежуточных файлов — только упавшая
    строка с небольшим контекстом.
    """
    frame_code = tb.tb_frame.f_code
    filename = frame_code.co_filename
    lineno = tb.tb_lineno
    display_name = path_mapper(filename) if path_mapper is not None else filename

    head = f"{_INDENT}{position} {display_name}:{lineno} in {frame_code.co_name}()"
    file_lines = read_file_lines(filename)
    if file_lines is None:
        return [head, f"{_INDENT}{_INDENT}<исходный код недоступен>"]

    is_scenario_file = bool(scenario_path) and scenario_path in filename
    if is_scenario_file:
        full = get_full_function_lines(tb.tb_frame)
        if full is not None:
            lines, start = full
        else:
            start = max(frame_code.co_firstlineno, 1)
            lines = file_lines[start - 1:]
    else:
        compact_start, compact_end = compact_bounds(lineno, len(file_lines))
        lines, start = file_lines[compact_start:compact_end], compact_start + 1

    return [head] + _code_rows(dedent_lines(lines), start, lineno, _INDENT + _INDENT)


def render_tb_text(tb: Optional[TracebackType], scenario_path: str,
                   path_mapper: Optional[Callable[[str], str]] = None) -> str:
    """Весь стек traceback как plain text (пустая строка, если стека нет)."""
    frames = iter_tb_frames(tb)
    if not frames:
        return ""

    lines: List[str] = ["Traceback (внешний вызов → место падения):"]
    last = len(frames) - 1
    for i, frame in enumerate(frames):
        position = "↯" if i == last else "·"
        lines.extend(_render_frame(frame, scenario_path, position, path_mapper))
        if i != last:
            lines.append("")
    return "\n".join(lines)


def render_failure_text(step_name: str, error: str, traceback_text: str) -> str:
    """
    Секция падения: сначала шаг и текст ошибки (самое важное — сверху, чтобы
    причину не приходилось искать в конце длинного стека), затем traceback
    с исходным кодом.
    """
    lines = [
        "=" * 60,
        f"FAILURE в шаге: {step_name}",
        "=" * 60,
        f"Ошибка: {error}" if error else "Ошибка: <неизвестна>",
    ]
    if traceback_text:
        lines.append("")
        lines.append(traceback_text)
    return "\n".join(lines)
