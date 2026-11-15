"""Экранирование значений для безопасной вставки в HTML."""

import html
from typing import Any

__all__ = ("esc",)


def esc(value: Any) -> str:
    """Экранирует произвольное значение для безопасной вставки в HTML."""
    return html.escape(str(value), quote=True)
