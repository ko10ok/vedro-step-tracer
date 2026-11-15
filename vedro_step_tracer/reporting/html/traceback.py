"""Рендеринг исходного кода из traceback упавшего шага (по примеру flakyzavr)."""

import itertools
from types import TracebackType
from typing import Callable, List, Optional

from ..source import compact_bounds, dedent_lines, get_full_function_lines, iter_tb_frames, read_file_lines
from .escaping import esc

__all__ = ("render_tb_html", "render_error_text",)


_tb_frame_counter = itertools.count(1)


def render_code_rows(lines: List[str], start_line: int, lineno: int) -> str:
    """Отрендерить список строк кода как HTML-разметку с подсветкой упавшей строки."""
    rows = []
    for offset, code_line in enumerate(lines):
        line_no = start_line + offset
        is_failed_line = (line_no == lineno)
        row_cls = "tb-row tb-row-fail" if is_failed_line else "tb-row"
        marker = "›" if is_failed_line else ""
        code_html = esc(code_line) if code_line.strip() else "&nbsp;"
        rows.append(
            f'<div class="{row_cls}">'
            f'<span class="tb-marker">{marker}</span>'
            f'<span class="tb-lineno">{line_no}</span>'
            f'<span class="tb-code">{code_html}</span>'
            '</div>'
        )
    return "".join(rows)


def render_frame_file_header(display_name: str, lineno: int, with_toggle: bool) -> str:
    """
    Рендерит заголовок кадра с путём к файлу и кнопкой «скопировать путь».

    Кнопка нужна, потому что при выделении текста мышью в заголовке (рядом
    с иконками/отступами) в буфер часто попадают лишние пробелы — явная
    кнопка копирует ровно путь к файлу, без обвязки.
    """
    cls = "tb-frame-file tb-frame-file-with-toggle" if with_toggle else "tb-frame-file"
    return (
        f'<div class="{cls}">'
        f'<span class="tb-frame-path">{esc(display_name)}:{lineno}</span>'
        f'<button type="button" class="tb-copy-btn" data-copy="{esc(display_name)}" '
        'onclick="tracerCopyPath(this)" title="Скопировать путь к файлу">📋</button>'
        '</div>'
    )


def list_code_html(tb: TracebackType, scenario_path: str,
                   path_mapper: Optional[Callable[[str], str]] = None) -> str:
    """
    Отрендерить фрагмент исходного кода одного кадра traceback как HTML.

    Если кадр относится к файлу текущего сценария — показываем весь шаг
    (функцию) целиком с подсветкой упавшей строки, с возможностью свернуть
    отображение до нескольких строк рядом с падением и развернуть обратно.
    Для промежуточных файлов (helpers/contexts/interfaces, сторонние
    библиотеки и т.д.) — только саму упавшую строку, без лишнего контекста.

    `path_mapper` преобразует путь внутри контейнера в путь на хостовой
    машине (см. VedroStepTracerPlugin._to_host_path) — используется только
    для отображения заголовка файла, поиск исходников идёт по «сырому» пути.
    """
    f_code = tb.tb_frame.f_code
    filename = f_code.co_filename
    firstlineno = f_code.co_firstlineno
    lineno = tb.tb_lineno
    display_name = path_mapper(filename) if path_mapper is not None else filename

    file_lines = read_file_lines(filename)
    if file_lines is None:
        return (
            '<div class="tb-frame">'
            f'{render_frame_file_header(display_name, lineno, with_toggle=False)}'
            '</div>'
        )

    is_scenario_file = bool(scenario_path) and scenario_path in filename

    if not is_scenario_file:
        # Промежуточный файл — только упавшая строка, без контекста и без переключателя
        start = max(lineno - 1, 0)
        end = min(lineno, len(file_lines))
        compact_lines = dedent_lines(file_lines[start:end])
        rows_html = render_code_rows(compact_lines, start + 1, lineno)
        return (
            '<div class="tb-frame">'
            f'{render_frame_file_header(display_name, lineno, with_toggle=False)}'
            f'<div class="tb-frame-code">{rows_html}</div>'
            '</div>'
        )

    # Файл текущего сценария — показываем шаг (функцию) целиком
    full = get_full_function_lines(tb.tb_frame)
    if full is not None:
        full_lines, full_start = full
    else:
        full_start = max(firstlineno, 1)
        full_lines = file_lines[full_start - 1:]

    compact_start, compact_end = compact_bounds(lineno, len(file_lines))
    compact_lines = dedent_lines(file_lines[compact_start:compact_end])

    full_rows_html = render_code_rows(dedent_lines(full_lines), full_start, lineno)
    compact_rows_html = render_code_rows(compact_lines, compact_start + 1, lineno)

    frame_id = f"tbf-{next(_tb_frame_counter)}"
    toggle = (
        f'<input type="checkbox" id="{frame_id}" class="tb-toggle" checked>'
        f'<label for="{frame_id}" class="tb-toggle-btn" title="Свернуть/развернуть контекст">'
        '<span class="tb-toggle-label-full">▾ Свернуть</span>'
        '<span class="tb-toggle-label-compact">▸ Показать функцию целиком</span>'
        '</label>'
    )

    return (
        '<div class="tb-frame">'
        f'{toggle}'
        f'{render_frame_file_header(display_name, lineno, with_toggle=True)}'
        f'<div class="tb-frame-code tb-frame-code-full">{full_rows_html}</div>'
        f'<div class="tb-frame-code tb-frame-code-compact">{compact_rows_html}</div>'
        '</div>'
    )


def render_tb_html(tb: Optional[TracebackType], scenario_path: str,
                   path_mapper: Optional[Callable[[str], str]] = None) -> str:
    """Рекурсивно отрендерить весь стек traceback (каждый кадр — отдельный блок кода)."""
    if tb is None:
        return ""
    return "".join(
        list_code_html(frame, scenario_path, path_mapper)
        for frame in iter_tb_frames(tb)
    )


def render_error_text(error: BaseException) -> str:
    """Класс и сообщение исходной ошибки (данные берутся из ExcInfo самого vedro)."""
    message = str(error)
    return f"{type(error).__name__}: {message}" if message else type(error).__name__
