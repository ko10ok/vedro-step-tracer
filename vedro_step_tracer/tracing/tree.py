"""Пост-обработка собранного дерева: схлопывание async-резюмов, метрики."""

import asyncio
from typing import Any, Dict, List, Optional, Union

from .nodes import RootStep, StepNode, VarNode

__all__ = (
    "is_async_intermediate", "collect_max_duration",
    "dedup_repeated_vars", "collapse_tree", "collapse_passthrough",
)

# ═══════════════════════════════════════════════════════════════════════════════
# Дедупликация повторных async-вызовов
# ═══════════════════════════════════════════════════════════════════════════════


def is_async_intermediate(return_value: Any) -> bool:
    """Проверяет, является ли return_value промежуточным async-результатом (не реальным возвратом)."""
    if return_value is None:
        return True
    if isinstance(return_value, asyncio.Future):
        return True
    if asyncio.iscoroutine(return_value):
        return True
    return False


def collect_max_duration(steps: List["RootStep"]) -> float:
    """
    Находит максимальную длительность среди всех шагов и вложенных вызовов
    во всём отчёте — используется для масштабирования полоски относительной
    длительности (dur-bar) в HTML-отчёте.
    """
    max_d = 0.0

    def walk(children: List[Union[StepNode, VarNode]]) -> None:
        nonlocal max_d
        for item in children:
            if isinstance(item, StepNode):
                if item.duration:
                    max_d = max(max_d, item.duration)
                walk(item.children)

    for root in steps:
        if root.duration:
            max_d = max(max_d, root.duration)
        if root.call_tree:
            walk(root.call_tree)

    return max_d or 1.0


def dedup_repeated_vars(
        children: List[Union[StepNode, VarNode]]) -> List[Union[StepNode, VarNode]]:
    """
    Убирает повторные VarNode с тем же kind+key и тем же значением, которые
    возникают при склейке нескольких async-резюмов одного и того же вызова
    (аргументы/локальные/scope-переменные при каждом resume фиксируются
    заново, даже если значение не изменилось). Оставляет только первое
    появление каждой пары (kind, key) с данным значением; если значение
    реально изменилось между резюмами — новая запись сохраняется.
    """
    if not children:
        return children
    result: List[Union[StepNode, VarNode]] = []
    seen: Dict[tuple, str] = {}
    for item in children:
        if isinstance(item, VarNode):
            dedup_key = (item.kind, item.key)
            try:
                value_repr = repr(item.value)
            except Exception:
                value_repr = None
            if value_repr is not None and seen.get(dedup_key) == value_repr:
                continue
            if value_repr is not None:
                seen[dedup_key] = value_repr
            result.append(item)
        else:
            result.append(item)
    return result


def collapse_tree(children: List[Union[StepNode, VarNode]],
                  passthrough: bool = True) -> List[Union[StepNode, VarNode]]:
    """
    Схлопывает последовательные вызовы одной и той же функции на одном уровне
    в одну запись (async-корутины триггерят call/return на каждый resume).
    Оставляет последний вызов (с финальным return value) и суммирует время.

    При ``passthrough=True`` дополнительно схлопываются транзитные цепочки
    вызовов (см. :func:`collapse_passthrough`).
    """
    if not children:
        return children

    result: List[Union[StepNode, VarNode]] = []
    i = 0
    while i < len(children):
        item = children[i]
        if not isinstance(item, StepNode):
            result.append(item)
            i += 1
            continue

        # Собираем все подряд идущие StepNode с тем же именем
        group = [item]
        j = i + 1
        while j < len(children):
            next_item = children[j]
            if isinstance(next_item, StepNode) and next_item.name == item.name:
                group.append(next_item)
                j += 1
            else:
                break

        if len(group) == 1:
            # Единственный вызов — рекурсивно схлопываем его children
            item.children = collapse_tree(item.children, passthrough)
            result.append(collapse_passthrough(item) if passthrough else item)
        else:
            # Проверяем: если промежуточные вызовы вернули None или async-объект
            # (Future, Task, coroutine), это async-резюмы — схлопываем.
            # Если вернули реальные значения — это отдельные вызовы.
            intermediates = group[:-1]
            is_async_resume = all(is_async_intermediate(n.return_value) for n in intermediates)

            if is_async_resume:
                # Async-резюмы — берём последний, суммируем время
                merged = group[-1]
                total_duration = sum(
                    (n.duration or 0) for n in group
                )
                merged.duration = total_duration if total_duration > 0 else None
                all_children: List[Union[StepNode, VarNode]] = []
                for node in group:
                    all_children.extend(node.children)
                merged.children = collapse_tree(
                    dedup_repeated_vars(all_children), passthrough,
                )
                result.append(collapse_passthrough(merged) if passthrough else merged)
            else:
                # Отдельные вызовы — сохраняем каждый
                for node in group:
                    node.children = collapse_tree(node.children, passthrough)
                    result.append(collapse_passthrough(node) if passthrough else node)

        i = j

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Схлопывание транзитных цепочек вызовов
# ═══════════════════════════════════════════════════════════════════════════════


def collapse_passthrough(node: StepNode) -> StepNode:
    """
    Схлопнуть цепочку транзитных вызовов в один узел.

    Транзитным считается вызов, который ничего не добавляет к отчёту: все его
    собственные дети, кроме ровно одного вложенного вызова, — это аргументы,
    которые повторяются у вложенного вызова с теми же значениями, и возвращает
    он ровно тот же объект, что и этот вложенный вызов. Такие обёртки печатали
    одно и то же значение на каждом уровне («ёлочки» в отчёте).

    Схлопывание без потерь: имена всех звеньев сохраняются в хлебной крошке
    ``SomeProject ▸ load_data → _execute_request → DataClient ▸ fetch``,
    значение по условию одно и то же, а аргументы видны у самого глубокого
    звена. У результата остаются файл и строка этого звена — там значение
    и рождается.
    """
    chain = [node.name]
    current = node
    while True:
        child = _single_call_child(current)
        if child is None:
            break
        if current.return_value is not child.return_value:
            break
        if current.status != child.status:
            break
        if not _args_subsumed(current, child):
            break
        chain.append(child.name)
        current = child

    if current is node:
        return node

    # Внешняя длительность включает вложенные вызовы — она и есть честное
    # время всей цепочки.
    current.duration = node.duration
    current.name = " → ".join(chain)
    _relevel(current, node.level)
    return current


def _single_call_child(node: StepNode) -> Optional[StepNode]:
    """Единственный вложенный вызов узла, если все остальные дети — аргументы."""
    call_child: Optional[StepNode] = None
    for child in node.children:
        if isinstance(child, StepNode):
            if call_child is not None:
                return None
            call_child = child
        elif child.kind != "arg":
            return None
    return call_child


def _args_subsumed(parent: StepNode, child: StepNode) -> bool:
    """
    Повторяются ли аргументы родителя у вложенного вызова с теми же значениями.

    Если да, схлопывание ничего не скрывает: те же значения останутся видны
    у самого глубокого звена цепочки. Сравнение по ``repr``, а не по
    идентичности: значения переменных сохраняются снимком (``safe_copy``),
    и один и тот же аргумент на разных уровнях — это разные объекты.
    """
    child_args = {_value_repr(c) for c in child.children
                  if isinstance(c, VarNode) and c.kind == "arg"}
    for item in parent.children:
        if isinstance(item, VarNode) and item.kind == "arg":
            own = _value_repr(item)
            if own is None or own not in child_args:
                return False
    return True


def _value_repr(var: VarNode) -> Optional[str]:
    try:
        return repr(var.value)
    except Exception:
        return None


def _relevel(node: StepNode, level: int) -> None:
    """Пересчитать уровни поддерева после схлопывания (влияет на цвета в HTML)."""
    delta = level - node.level
    if delta == 0:
        return

    def walk(item: Union[StepNode, VarNode]) -> None:
        item.level += delta
        if isinstance(item, StepNode):
            for child in item.children:
                walk(child)

    walk(node)
