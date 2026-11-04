"""Разворачивание завершённых async-объектов перед отображением.

``<Future finished result=True>`` ничего не говорит о результате вызова:
интересен сам результат. Разворачивание живёт в слое отображения — в дереве
остаётся исходный объект.
"""

import asyncio
from typing import Any, Tuple

__all__ = ("unwrap_async", "ASYNC_NOTE",)

ASYNC_NOTE = "Future"


def unwrap_async(value: Any) -> Tuple[Any, str]:
    """
    Вернуть ``(развёрнутое значение, пометка)``.

    Пометка пуста, если значение не является завершённым ``Future``/``Task``.
    Future с исключением не разворачивается: его repr уже несёт нужную
    информацию, а ``.result()`` выбросил бы исключение наружу.
    """
    if not isinstance(value, asyncio.Future):
        return value, ""
    if not value.done() or value.cancelled():
        return value, ""
    try:
        if value.exception() is not None:
            return value, ""
        return value.result(), ASYNC_NOTE
    except BaseException:
        return value, ""
