"""LlmTextRenderer — компактная plain-text выжимка отчёта для передачи LLM.

Зачем отдельный рендерер, а не сбор текста из готовой HTML-страницы:
в HTML значения переменных и возвраты лежат внутри свёрнутых ``<details>``,
а браузер не отдаёт текст скрытых элементов (``innerText`` возвращает только
отрендеренное). Поэтому текст собирается на стороне Python — из того же
дерева вызовов, что и HTML, — и встраивается в страницу готовой строкой
(см. HtmlTreeWriter._render_llm_payload).

Уровень детализации — verbosity=2: scope сценария, аргументы вызовов и
возвращаемые значения, но без локальных переменных, которые сильно раздувают
текст, почти не добавляя смысла.
"""

from typing import List

from ...tracing import RootStep
from ..base import BaseReportRenderer
from ..terminal import TreeWriter
from .traceback import render_failure_text

__all__ = ("LlmTextRenderer",)

# scope + аргументы + возвраты, без локальных переменных (см. модульный docstring).
_LLM_VERBOSITY = 2


class LlmTextRenderer(BaseReportRenderer):
    """Рендерит сценарий в plain text: шапка, дерево вызовов, секция падения."""

    def __init__(self, verbosity: int = _LLM_VERBOSITY) -> None:
        self._verbosity = verbosity

    def render_document(self, scenario_name: str, steps: List[RootStep],
                        scenario_path: str = "") -> str:
        parts = [self._render_header(scenario_name, steps, scenario_path)]

        # Цвет выключен намеренно: ANSI-последовательности в тексте для LLM —
        # это шум, который к тому же съедает контекст.
        tree = TreeWriter(verbosity=self._verbosity, color=False).render_scenario(
            scenario_name, steps,
        )
        parts.append(tree.rstrip("\n"))

        failures = [
            render_failure_text(step.name, step.failure_error or "", step.failure_trace or "")
            for step in steps if step.status == "FAIL"
        ]
        if failures:
            parts.append("")
            parts.extend(failures)

        return "\n".join(parts) + "\n"

    def _render_header(self, scenario_name: str, steps: List[RootStep],
                       scenario_path: str) -> str:
        failed = any(step.status == "FAIL" for step in steps)
        total_duration = sum(step.duration or 0.0 for step in steps)

        lines = [
            "=== Test Trace Report ===",
            f"Сценарий: {scenario_name}",
            f"Статус: {'FAILED' if failed else 'PASSED'}",
            f"Длительность: {total_duration:.2f}s",
        ]
        if scenario_path:
            lines.append(f"Файл: {scenario_path}")
        lines.append("")
        lines.append(
            "Легенда: ⇒ scope сценария · → аргумент вызова · ↲ возвращаемое значение"
        )
        lines.append("")
        return "\n".join(lines)
