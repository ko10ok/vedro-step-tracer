"""
Vedro plugin: автоматический трейсинг вызовов функций из helpers/, contexts/, interfaces/.

Использует sys.settrace() для перехвата всех вызовов и возвратов из целевых
директорий, собирает локальные переменные и возвращаемые значения, выводит
иерархическое дерево по спецификации формата вывода шагов теста.

Структура пакета:
  * ``settings``  — изменяемые в рантайме настройки (лимит длины строк);
  * ``tracing``   — модель дерева, sys.settrace-трейсер, пост-обработка;
  * ``reporting`` — рендереры отчётов: ``terminal`` (stdout) и ``html``;
  * ``gitlab``    — специфика GitLab CI: секции лога, ссылки на артефакты;
  * ``plugin`` / ``config`` — интеграция с vedro.
"""

from . import exclude
from .config import ReportType, VedroStepTracer
from .plugin import VedroStepTracerPlugin

__all__ = (
    "VedroStepTracer", "VedroStepTracerPlugin", "ReportType", "exclude",
)
