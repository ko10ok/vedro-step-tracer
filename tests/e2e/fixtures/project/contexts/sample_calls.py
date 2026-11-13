"""
Трассируемые функции — живут в ``contexts/``, то есть попадают под
``target_dirs`` плагина VedroStepTracer. Намеренно разнообразны:

- ``fetch_user`` вызывает два вложенных helper'а и собирает из их
  результатов словарь — проверяет обычное дерево с args/return на
  нескольких уровнях.
- ``passthrough_wrapper`` ничего не делает, кроме вызова ``fetch_user`` и
  возврата того же объекта — кандидат на схлопывание транзитной цепочки.
- ``long_value`` возвращает строку длиной 5000 символов — проверяет
  сокращение длинных значений в отчёте.
- ``mutate_in_place`` дописывает элемент в чужой список по ссылке (как
  ``mocked_response.Handler._history``) — проверяет, что диф по scope
  видит изменение контейнера без смены ``id``.
- ``summarize_user_ids`` копит локальную переменную в цикле — проверяет,
  что локальные переменные вызова (не scope self, не аргументы) тоже
  попадают в дерево.
"""

from typing import Dict, List


def _build_payload(user_id: int) -> Dict[str, object]:
    payload = {"user_id": user_id, "status": "active"}
    return payload


def _format_greeting(name: str) -> str:
    template = "Hello, {}!"
    return template.format(name)


def fetch_user(user_id: int) -> Dict[str, object]:
    payload = _build_payload(user_id)
    greeting = _format_greeting(f"user-{user_id}")
    payload["greeting"] = greeting
    return payload


def passthrough_wrapper(user_id: int) -> Dict[str, object]:
    """Транзитная обёртка — должна схлопнуться в хлебную крошку в дереве."""
    return fetch_user(user_id)


def long_value() -> str:
    return "x" * 5000


class BinaryMessage:
    """Аналог SormMessage: ``__str__`` содержит мегабайтный бинарный payload."""

    def __init__(self, data: bytes) -> None:
        self.data = data

    def __str__(self) -> str:
        return repr(self.data)


def binary_message() -> BinaryMessage:
    message = BinaryMessage(b"\x00\xff" * (1024 * 1024))
    return message


def big_bytes() -> bytes:
    return b"\x00\xff" * (1024 * 1024)


def multiline_text() -> str:
    line = "x" * 64
    return "\n".join(line for _ in range(32768))


def nested_big_payload() -> Dict[str, object]:
    return {"payload": multiline_text(), "meta": {"size": 2_000_000}}


def big_list() -> List[int]:
    return list(range(50_000))


def mutate_in_place(history: List[int], value: int) -> None:
    history.append(value)


def summarize_user_ids(user_ids: List[int]) -> int:
    """Накапливает локальную переменную в цикле — без аргументов-контейнеров."""
    total = 0
    for value in user_ids:
        total += value
    return total
