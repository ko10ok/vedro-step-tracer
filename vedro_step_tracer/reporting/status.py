"""Отображение статуса шага/вызова в разных форматах отчётов."""

from typing import Dict

__all__ = ("STATUS_EMOJI", "PLAIN_STATUS_EMOJI", "status_class",)

# Статусы с rich-разметкой — для вывода в stdout.
STATUS_EMOJI: Dict[str, str] = {
    "PASS": "[green]✔[/green]",
    "FAIL": "[red]✗[/red]",
    "ERROR": "[red]✗[/red]",
    "SKIP": "[yellow]○[/yellow]",
    "NOT_RUN": "[dim]○[/dim]",
}

# Те же статусы без разметки — для HTML и для дерева тестов PyCharm.
PLAIN_STATUS_EMOJI: Dict[str, str] = {
    "PASS": "✔",
    "FAIL": "✗",
    "ERROR": "✗",
    "SKIP": "○",
    "NOT_RUN": "○",
}


def status_class(status: str) -> str:
    return f"st-{status.lower()}"
