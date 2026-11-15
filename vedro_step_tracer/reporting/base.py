"""Общий интерфейс рендерера отчёта.

Каждый формат отчёта (stdout, html, в перспективе — pycharm) реализует
``render_document`` и получает на вход одни и те же данные: имя сценария и
список его шагов с собранными деревьями вызовов.
"""

from abc import ABC, abstractmethod
from typing import List

from ..tracing import RootStep

__all__ = ("BaseReportRenderer",)


class BaseReportRenderer(ABC):
    """Базовый рендерер отчёта по результатам трейсинга сценария."""

    @abstractmethod
    def render_document(self, scenario_name: str, steps: List[RootStep],
                        scenario_path: str = "") -> str:
        """Отрендерить отчёт по сценарию целиком.

        :param scenario_name: subject сценария (человекочитаемое имя).
        :param steps: шаги сценария с деревьями вызовов.
        :param scenario_path: путь к файлу сценария (может не использоваться).
        :return: готовый текст отчёта в формате конкретного рендерера.
        """
        raise NotImplementedError()
