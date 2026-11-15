"""События трейсера для потребителей, которым нужен реальный масштаб времени.

Трейсер остаётся источником истины: он строит ``StepNode``-дерево и лишь
дополнительно публикует факты о входе/выходе из вызовов и о зафиксированных
переменных. События несут ссылки на уже готовые узлы, поэтому подписчик не
строит своё дерево и не может с ним разъехаться.

Порядок гарантируется трейсером: ``CallEntered`` приходит после того, как
узел влинкован в родителя и записаны аргументы; ``VarRecorded`` — сразу
после добавления переменной; ``CallReturned`` — после ``close()``, когда
статус, длительность и return уже финальные. События публикуются строго
LIFO, поэтому вложенность вызовов восстанавливается без дополнительной
информации.

Жизненный цикл шага и сценария публикуется не здесь: его владелец — плагин,
который получает соответствующие события vedro.
"""

from dataclasses import dataclass
from typing import Optional, Union

from .nodes import RootStep, StepNode, VarNode

__all__ = ("TraceEvent", "StepStarted", "CallEntered", "VarRecorded",
           "CallReturned", "StepFinished")


@dataclass(frozen=True)
class StepStarted:
    """Начало шага сценария (given_/when_/then_)."""

    step: RootStep


@dataclass(frozen=True)
class CallEntered:
    """Вход в трассируемую функцию.

    ``parent`` — узел-владелец, ``None`` означает верхний уровень шага.
    """

    node: StepNode
    parent: Optional[StepNode]


@dataclass(frozen=True)
class VarRecorded:
    """Переменная добавлена в дерево; ``owner`` — узел или корень шага."""

    owner: Optional[StepNode]
    var: VarNode


@dataclass(frozen=True)
class CallReturned:
    """Выход из трассируемой функции: узел уже закрыт."""

    node: StepNode


@dataclass(frozen=True)
class StepFinished:
    """Шаг сценария завершён."""

    step: RootStep


TraceEvent = Union[StepStarted, CallEntered, VarRecorded, CallReturned, StepFinished]
