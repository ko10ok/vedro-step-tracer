"""
Трассируемые функции для unit-тестов дерева вызовов.

Этот файл сам является "целевой директорией" (``target_dirs``), которую
трейсер отслеживает в тестах: функции ниже разнообразны по форме — одиночный
вызов, транзитная обёртка-кандидат на схлопывание, внутренние локальные
переменные, мутация чужого контейнера по ссылке, трёхуровневая цепочка для
проверки exclude_functions и функции с "опасными" значениями (сокет,
переменная-кандидат на var-scoped исключение) для exclude_value_types.
"""

import asyncio
import socket
from typing import Dict, List


def leaf_sum(a: int, b: int) -> int:
    return a + b


def _build_payload(user_id: int) -> Dict[str, object]:
    return {"user_id": user_id, "status": "active"}


def fetch_user(user_id: int) -> Dict[str, object]:
    payload = _build_payload(user_id)
    return payload


def passthrough_wrapper(user_id: int) -> Dict[str, object]:
    """Транзитная обёртка — кандидат на collapse_passthrough."""
    return fetch_user(user_id)


def sum_with_locals(n: int) -> int:
    total = 0
    for i in range(n):
        total += i
    return total


def mutate_history(history: List[int], value: int) -> None:
    history.append(value)


def middle_call(a: int, b: int) -> int:
    return leaf_sum(a, b)


def outer_call(a: int, b: int) -> int:
    return middle_call(a, b)


def holds_a_socket() -> int:
    """
    Держит ``socket.socket`` в локальной переменной — попадает под дефолтное
    exclude_value_types (см. exclude.DEFAULT_EXCLUDED_VALUE_TYPES).
    Сокет закрывается сразу же — переменная остаётся в locals фрейма до
    выхода из функции, этого достаточно для фиксации трейсером.
    """
    sock = socket.socket()
    sock.close()
    return 42


def void_twice(n: int) -> None:
    """Два отдельных вызова функции, возвращающей None, — не async-резюмы."""
    void_call(n)
    void_call(n)


def void_call(n: int) -> None:
    total = 0
    for i in range(n):
        total += i


async def async_leaf(delay: float) -> str:
    """Корутина с единственным await — её длительность должна включать ожидание."""
    await asyncio.sleep(delay)
    return "ok"


async def async_returns_none(delay: float) -> None:
    await asyncio.sleep(delay)


async def async_twice(delay: float) -> None:
    """Два отдельных await-вызова одной корутины — два разных фрейма."""
    await async_returns_none(delay)
    await async_returns_none(delay)


def run_with_pipe_var(x: int) -> int:
    """
    Локальная ``process`` — кандидат на var-scoped исключение (exclude.var)
    по имени и функции: само значение здесь обычное (не ОС-ресурс), важно
    лишь то, что var-правило матчит по имени+функции независимо от типа.
    Аргумент ``x``, вложенный вызов ``leaf_sum`` и возврат должны
    по-прежнему трассироваться как обычно.
    """
    process = {"pid": 123}
    return leaf_sum(x, process["pid"])
