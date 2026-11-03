"""Обвязка HTML-страницы отчёта: шапка сценария, навигация по шагам, тулбар."""

from typing import List

from ...tracing import RootStep
from ..status import PLAIN_STATUS_EMOJI, status_class
from .escaping import esc

__all__ = ("render_header", "render_nav",)


def _render_path(scenario_path: str) -> str:
    """Путь к файлу сценария с кнопкой копирования (см. render_copy_button)."""
    if not scenario_path:
        return ""
    return (
        '<div class="term-path">'
        f'<span class="term-path-text">{esc(scenario_path)}</span>'
        f'<button type="button" class="tb-copy-btn" data-copy="{esc(scenario_path)}" '
        'onclick="tracerCopyPath(this)" title="Скопировать путь к файлу">📋</button>'
        '</div>'
    )


def render_header(scenario_name: str, steps: List[RootStep], scenario_path: str = "") -> str:
    """Шапка отчёта: статус сценария, его имя, суммарная длительность и путь."""
    failed = any(s.status == "FAIL" for s in steps)
    status_emoji = "❌" if failed else "✅"
    status_text = "FAILED" if failed else "PASSED"
    st_cls = "st-fail" if failed else "st-pass"

    total_duration = sum(s.duration or 0.0 for s in steps)
    meta_parts = [f'⏱ <b>{total_duration:.2f}s</b>']
    meta_html = '<span class="sep">·</span>'.join(meta_parts)

    return (
        '<div class="term-header">'
        f'<span class="term-badge {st_cls}">{status_emoji} {status_text}</span>'
        f'<span class="term-title">{esc(scenario_name)}</span>'
        f'<span class="term-meta">{meta_html}</span>'
        f'{_render_path(scenario_path)}'
        '</div>'
    )


def _render_toolbar() -> str:
    """
    Панель поиска/фильтра и разворачивания — часть правой колонки (.term-nav),
    отображается там же, где список шагов, чтобы не занимать место в основном
    содержимом отчёта.
    """
    return (
        '<div class="tracer-toolbar">'
        '<div class="tracer-search-box">'
        '<span class="tracer-search-icon">🔎</span>'
        '<input type="text" id="tracer-search-input" '
        'placeholder="Поиск…" autocomplete="off">'
        '<label title="Скрыть вызовы и переменные, не содержащие совпадение '
        '(вложенность сохраняется: если вложенный элемент содержит совпадение — '
        'показывается путь до него и он сам)">'
        '<input type="checkbox" id="tracer-search-filter"> Скрывать несовпадающие'
        '</label>'
        '</div>'
        '<div class="tracer-toolbar-group">'
        '<button type="button" class="term-nav-copy" id="tracer-toggle-calls">'
        '▾ Развернуть все вызовы</button>'
        '<button type="button" class="term-nav-copy" id="tracer-toggle-vars">'
        '▾ Развернуть все переменные</button>'
        '</div>'
        '</div>'
    )


def render_nav(steps: List[RootStep]) -> str:
    """Правая колонка: тулбар, список шагов-якорей и кнопка копирования для LLM."""
    nav_links_html = ""
    copy_llm_btn = ""
    if len(steps) > 1:
        nav_links = []
        for i, root in enumerate(steps, start=1):
            nav_cls = status_class(root.status)
            nav_links.append(
                f'<a href="#step-{i}" class="{nav_cls}" title="{esc(root.name)}">'
                f'{PLAIN_STATUS_EMOJI.get(root.status, "○")} {i}. {esc(root.name)}</a>'
            )
        nav_links_html = (
            f'<div class="term-nav-title">Шаги · {len(steps)}</div>'
            f'{"".join(nav_links)}'
        )
        copy_llm_btn = (
            '<button type="button" class="term-nav-copy" id="copy-for-llm" '
            'title="Скопировать полный текст трейсинга для LLM">📋 Скопировать для LLM</button>'
        )

    return (
        '<nav class="term-nav">'
        f'{_render_toolbar()}'
        f'{nav_links_html}'
        f'{copy_llm_btn}'
        '</nav>'
    )
