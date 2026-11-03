"""
Трассируемые функции для unit-тестов дерева вызовов.

Этот файл сам является "целевой директорией" (``target_dirs``), которую
трейсер отслеживает в тестах: функции ниже разнообразны по форме — одиночный
вызов, транзитная обёртка-кандидат на схлопывание, внутренние локальные
переменные, мутация чужого контейнера по ссылке и трёхуровневая цепочка для
проверки exclude_functions.
"""

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
