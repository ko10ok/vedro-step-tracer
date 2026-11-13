"""HtmlTreeWriter — рендеринг дерева шагов в самодостаточную HTML-страницу.

Правила раскрытия блоков по умолчанию:
  - шаги сценария (given/when/then) всегда показаны развёрнуто (не сворачиваются);
  - scope шага всегда развёрнут (и у упавшего, и у остальных шагов);
  - у УПАВШЕГО шага дерево вложенных вызовов, их аргументы, локальные
    переменные и возвращаемые значения — развёрнуты по умолчанию;
  - у ОСТАЛЬНЫХ шагов вложенные вызовы свёрнуты по умолчанию; при ручном
    разворачивании вызова — аргументы и возврат развёрнуты, а локальные
    переменные остаются свёрнутыми (нужен ещё один клик);
  - возвращаемое значение вызова всегда показано превью в заголовке блока.
"""

import json
from typing import Any, List, Optional

from ...tracing import RootStep, StepNode, VarNode, collect_max_duration
from ..base import BaseReportRenderer
from ..llm import LlmTextRenderer
from ..status import PLAIN_STATUS_EMOJI, status_class
from .assets import render_report
from .escaping import esc
from .layout import render_header, render_nav
from .palette import depth_colors, solid_node_bg
from .values import html_preview, html_value, needs_return_block

__all__ = ("HtmlTreeWriter",)


class HtmlTreeWriter(BaseReportRenderer):
    """
    Рендерит дерево шагов сценария в самодостаточную HTML-страницу
    в стиле терминала (тёмная тема, моноширинный шрифт, ANSI-подобная
    подсветка типов). Используется только для файлового отчёта, который
    создаётся при падении сценария — см. правила раскрытия блоков выше.
    """

    def __init__(self) -> None:
        # Максимальная длительность вызова во всём отчёте — используется для
        # масштабирования полоски относительной длительности (dur-bar).
        # Считается один раз в начале render_document().
        self._max_duration: float = 1.0

    @staticmethod
    def _duration_bar_color(pct: float) -> str:
        """Цвет полоски длительности: чем ближе к максимуму — тем "тревожнее"."""
        if pct >= 66:
            return "#f85149"
        if pct >= 33:
            return "#e3b341"
        return "#58a6ff"

    def _dur_group_html(self, duration: Optional[float]) -> str:
        """Группа «полоска + текст длительности», позиционируется в правом
        краю заголовка (summary) через CSS margin-left:auto — подальше от
        названия вызова/шага, чтобы не мешать чтению имени."""
        if duration is None or duration < 0.001:
            return ""
        pct = min(100.0, (duration / self._max_duration) * 100.0) if self._max_duration else 0.0
        color = self._duration_bar_color(pct)
        return (
            '<span class="dur-group">'
            f'<span class="dur-bar" title="{duration:.2f}s">'
            f'<span class="dur-bar-fill" style="width:{pct:.0f}%;--dc:{color}"></span></span>'
            f'<span class="v-dim">⏱ {duration:.2f}s</span>'
            '</span>'
        )

    def render_document(self, scenario_name: str, steps: List[RootStep],
                        scenario_path: str = "") -> str:
        self._max_duration = collect_max_duration(steps)

        body = "\n".join(
            self._render_root_step(root, i) for i, root in enumerate(steps, start=1)
        )
        body += "\n" + self._render_llm_payload(scenario_name, steps, scenario_path)
        return render_report(
            title=esc(scenario_name),
            header=render_header(scenario_name, steps, scenario_path),
            nav=render_nav(steps),
            body=body,
        )

    @staticmethod
    def _render_llm_payload(scenario_name: str, steps: List[RootStep],
                            scenario_path: str) -> str:
        """
        Готовая plain-text выжимка отчёта, встроенная в страницу для кнопки
        «Скопировать для LLM» (см. LlmTextRenderer).

        Текст рендерится здесь, а не собирается скриптом со страницы, потому
        что значения переменных и возвраты лежат в свёрнутых ``<details>``, а
        браузер не отдаёт текст скрытых элементов. Тег ``script`` не
        отображается, поэтому на внешний вид отчёта payload не влияет.
        """
        text = LlmTextRenderer().render_document(scenario_name, steps, scenario_path)
        # JSON вместо сырого текста: строка попадает внутрь тега как есть, и
        # только экранирование "<" гарантирует, что "</script>" в данных
        # трейса не оборвёт тег раньше времени.
        payload = json.dumps(text, ensure_ascii=False).replace("<", "\\u003c")
        return (f'<script id="tracer-llm-payload" type="application/json">'
                f'{payload}</script>')

    _KIND_MARKER = {"arg": "→", "local": "·", "scope": "⇒", "scope_changed": "⇒"}

    def _render_root_step(self, root: RootStep, index: int) -> str:
        emoji = PLAIN_STATUS_EMOJI.get(root.status, "○")
        st_cls = status_class(root.status)
        dur_group = self._dur_group_html(root.duration)
        flags = " ".join(esc(f) for f in root.flags)

        parts = [f'<details class="root-step {st_cls}" id="step-{index}" open>']
        parts.append(
            f'<summary><div class="root-header"><span class="status-icon status-icon-{st_cls}">{emoji}</span> '
            f'<span class="step-idx">{index:02d}</span>'
            f'<span class="step-name">{esc(root.name)}</span> '
            f'<span class="flags">{flags}</span>'
            f'{dur_group}</div></summary>'
        )
        parts.append('<div class="root-body">')

        # Дерево вызовов и последовательно собранные scope-переменные
        # перемешаны в call_tree в порядке появления (см. FunctionTracer) —
        # рендерим единым проходом, без отдельных блоков "locals"/"scope".
        if root.call_tree:
            parts.append('<div class="calls">')
            for child in root.call_tree:
                if isinstance(child, StepNode):
                    parts.append(self._render_step_node(child, is_failed_branch=False))
                elif isinstance(child, VarNode):
                    parts.append(self._render_single_var(child.key, child.value, child.kind))
            parts.append('</div>')

        if root.failure_source:
            parts.append(root.failure_source)
            parts.append(
                '<div class="traceback-error">'
                '<span class="traceback-error-icon">💥</span>'
                f'<code>{esc(root.failure_error or "")}</code>'
                '</div>'
            )

        parts.append('</div></details>')
        return "\n".join(parts)

    def _render_step_node(self, node: StepNode, is_failed_branch: bool) -> str:
        st_cls = status_class(node.status)
        emoji = PLAIN_STATUS_EMOJI.get(node.status, "○")
        module_html = (f'<span class="module">({esc(node.module)})</span>'
                       if node.module else "")
        dur_group = self._dur_group_html(node.duration)
        flags_html = " ".join(esc(f) for f in node.flags)

        ret_preview_html = ""
        if node.return_value is not None:
            ret_preview_html = (f'<span class="ret-preview">↲ '
                                f'{esc(html_preview(node.return_value))}</span>')

        open_attr = " open" if is_failed_branch else ""
        summary = (f'<summary><span class="status-icon status-icon-{st_cls}">{emoji}</span> '
                   f'<span class="step-name">{esc(node.name)}</span> '
                   f'{module_html} '
                   f'<span class="flags">{flags_html}</span> {ret_preview_html}'
                   f'{dur_group}</summary>')

        color_hex, color_rgb = depth_colors(node.level)
        solid_bg = solid_node_bg(color_rgb, node.level)
        style_attr = f' style="--nc:{color_hex};--ncrgb:{color_rgb};background:{solid_bg}"'

        body_parts: List[str] = []

        # Аргументы, вложенные вызовы и локальные переменные этой функции
        # перемешаны в node.children в порядке появления (см. FunctionTracer)
        # — единый проход, каждая переменная сворачивается индивидуально.
        if node.children:
            children_html = ['<div class="calls">']
            for child in node.children:
                if isinstance(child, StepNode):
                    children_html.append(self._render_step_node(child, is_failed_branch))
                elif isinstance(child, VarNode):
                    children_html.append(self._render_single_var(child.key, child.value, child.kind))
            children_html.append('</div>')
            body_parts.append("".join(children_html))

        if node.return_value is not None and needs_return_block(node.return_value):
            body_parts.append(
                '<div class="block return-block">'
                '<div class="block-title">↲ return</div>'
                '<div class="v-item-value-wrap">'
                f'<div class="block-body">{html_value(node.return_value)}</div>'
                '<button type="button" class="v-copy-btn" onclick="tracerCopyValue(this)" '
                'title="Скопировать значение">📋</button>'
                '</div>'
                '</div>'
            )

        return (f'<details class="node {st_cls}"{open_attr}{style_attr}>{summary}'
                f'<div class="node-body">{"".join(body_parts)}</div></details>')

    def _render_single_var(self, key: str, value: Any, kind: str = "local") -> str:
        """
        Переменная, зафиксированная последовательно трейсером (аргумент,
        локальная переменная, новый/изменённый атрибут scope). Каждая
        переменная сворачивается индивидуально: заголовок (маркер + ключ)
        виден всегда, значение показывается только при разворачивании.
        """
        marker = self._KIND_MARKER.get(kind, "·")
        css_kind = "scope-changed" if kind == "scope_changed" else kind
        key_html = (f'<span class="v-key">{esc(key)}</span>' if key else "")
        # scope-переменные (новые и изменённые атрибуты self сценария) в HTML
        # по умолчанию раскрыты — значение видно сразу без клика.
        open_attr = " open" if kind in ("scope", "scope_changed") else ""
        return (
            f'<details class="v-item v-item-{css_kind}"{open_attr}>'
            f'<summary><span class="v-marker">{esc(marker)}</span> {key_html}'
            f'<span class="v-dim">:</span></summary>'
            '<div class="v-item-value-wrap">'
            f'<div class="v-item-value">{html_value(value)}</div>'
            '<button type="button" class="v-copy-btn" onclick="tracerCopyValue(this)" '
            'title="Скопировать значение">📋</button>'
            '</div>'
            '</details>'
        )
