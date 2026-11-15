"""MarkdownTreeWriter — рендеринг дерева шагов в Markdown-отчёт.

По аналогии с HTML-отчётом (см. ``..html.writer.HtmlTreeWriter``): та же
последовательность блоков — шаги сценария по порядку, секция падения внутри
шага, где оно произошло — и те же схлопываемые секции (``<details>``),
только без HTML-вёрстки значений: внутри используется уже протестированный
plain-text рендер дерева вызовов (``TreeWriter`` из терминального отчёта, тот
же, что лежит в основе LLM-выжимки), но с максимальной детализацией —
markdown-отчёт является файловым артефактом, а не live stdout, поэтому
урезать по verbosity незачем (как и в HTML).

Секции шагов сценария всегда развёрнуты (``<details open>``), как и в HTML.
"""

from typing import List

from ...tracing import RootStep
from ..base import BaseReportRenderer
from ..llm.traceback import render_failure_text
from ..status import PLAIN_STATUS_EMOJI
from ..terminal import TreeWriter

__all__ = ("MarkdownTreeWriter",)

# Отчёт — файловый артефакт: показываем всё (scope + args + locals + return),
# без урезания по verbosity, как и HTML-отчёт.
_FULL_VERBOSITY = 3


class MarkdownTreeWriter(BaseReportRenderer):
    """Рендерит дерево шагов сценария в Markdown с схлопываемыми секциями."""

    def render_document(self, scenario_name: str, steps: List[RootStep],
                        scenario_path: str = "") -> str:
        parts = [self._render_header(scenario_name, steps, scenario_path)]
        for index, root in enumerate(steps, start=1):
            parts.append(self._render_root_step(root, index))
        return "\n".join(parts) + "\n"

    @staticmethod
    def _render_header(scenario_name: str, steps: List[RootStep],
                       scenario_path: str) -> str:
        failed = any(step.status == "FAIL" for step in steps)
        status_text = f"{PLAIN_STATUS_EMOJI['FAIL']} FAILED" if failed \
            else f"{PLAIN_STATUS_EMOJI['PASS']} PASSED"
        total_duration = sum(step.duration or 0.0 for step in steps)

        lines = [
            f"# 🔎 Trace report: {scenario_name}",
            "",
            f"**Status:** {status_text}  ",
            f"**Duration:** {total_duration:.2f}s  ",
        ]
        if scenario_path:
            lines.append(f"**File:** `{scenario_path}`  ")
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _render_root_step(root: RootStep, index: int) -> str:
        emoji = PLAIN_STATUS_EMOJI.get(root.status, "○")
        summary = f"{emoji} {index:02d}. {root.name}"
        if root.duration is not None:
            summary += f" ⏱ {root.duration:.2f}s"
        if root.flags:
            summary += " " + " ".join(root.flags)

        # Полное дерево вызовов — тем же рендерером, что и stdout/LLM-выжимка,
        # но без цвета (artefact-файл) и с максимальной детализацией.
        tree_text = TreeWriter(verbosity=_FULL_VERBOSITY, color=False) \
            .render_step(root).strip("\n")

        lines = [
            "<details open>",
            f"<summary>{summary}</summary>",
            "",
            "```",
            tree_text,
            "```",
        ]

        if root.failure_trace or root.failure_error:
            lines.append("")
            lines.append("```")
            lines.append(render_failure_text(
                root.name, root.failure_error or "", root.failure_trace or "",
            ).strip("\n"))
            lines.append("```")

        lines.append("")
        lines.append("</details>")
        lines.append("")
        return "\n".join(lines)
