"""Plain-text выжимка отчёта для LLM (содержимое кнопки «Скопировать для LLM»)."""

from .traceback import render_failure_text, render_tb_text
from .writer import LlmTextRenderer

__all__ = ("LlmTextRenderer", "render_failure_text", "render_tb_text",)
