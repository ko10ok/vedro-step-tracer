"""
Прогон "шага" через ``FunctionTracer`` напрямую, без запуска самого vedro —
unit-уровень: проверяем построение дерева по сигналам call/return, а не
интеграцию с событиями сценария (это уже e2e-сьюты).
"""

import os
from typing import Any, Callable, Dict, List, Optional, Union

from vedro_step_tracer.tracing import FunctionTracer, collapse_tree
from vedro_step_tracer.tracing.nodes import StepNode, VarNode

__all__ = ("FakeStepSelf", "run_step",)

# target_dirs трейсера — сама эта директория: все функции в
# unit/contexts/*.py (кроме этого файла) считаются трассируемыми.
_TARGET_DIR = os.path.dirname(os.path.abspath(__file__))


class FakeStepSelf:
    """
    Минимальная замена ``vedro.Scenario``.

    Трейсеру для захвата scope-переменных достаточно, чтобы класс объекта,
    из метода которого вызывается шаг, имел атрибут ``subject``
    (см. ``FunctionTracer._capture_step_frame``) — остальное поведение
    ``vedro.Scenario`` (параметризация, discovery и т.п.) здесь не нужно.
    """

    subject = "unit scenario"


def run_step(step: Callable[[Any], None],
            scenario: Optional[Any] = None,
            exclude_paths: Optional[List[str]] = None,
            exclude_functions: Optional[List[str]] = None,
            collapse: bool = True) -> List[Union[StepNode, VarNode]]:
    """
    Выполнить ``step(scenario)`` под трейсером и вернуть дерево вызовов.

    ``step`` — обычная функция с первым параметром ``self`` (роль "метода
    шага"), которая вызывает трассируемые функции из ``unit/contexts``.
    Снимок ``self`` до шага берётся так же, как это делает сам плагин в
    ``on_step_run`` — чтобы уже существующие атрибуты не считались новыми.
    """
    scenario = scenario if scenario is not None else FakeStepSelf()
    initial_self_vars = dict(vars(scenario))
    tracer = FunctionTracer(
        [_TARGET_DIR],
        initial_self_vars=initial_self_vars,
        scenario_self=scenario,
        step_name=step.__name__,
        exclude_paths=exclude_paths,
        exclude_functions=exclude_functions,
    )
    tracer.start()
    try:
        step(scenario)
    finally:
        call_tree = tracer.stop()
    return collapse_tree(call_tree, passthrough=collapse) if collapse else call_tree


def call_names(children: List[Union[StepNode, VarNode]]) -> List[str]:
    """Имена всех StepNode дерева в порядке обхода (depth-first)."""
    names: List[str] = []
    for item in children:
        if isinstance(item, StepNode):
            names.append(item.name)
            names.extend(call_names(item.children))
    return names


def all_var_nodes(children: List[Union[StepNode, VarNode]]) -> List[VarNode]:
    """
    Все VarNode дерева, независимо от глубины.

    Scope-диф, сделанный внутри вызова, фиксируется как ребёнок именно
    того вызова, который успел измениться до возврата (см.
    ``FunctionTracer._handle_return``), а не как ребёнок корня шага —
    поэтому плоский обход по верхнему уровню их не находит.
    """
    nodes: List[VarNode] = []
    for item in children:
        if isinstance(item, VarNode):
            nodes.append(item)
        else:
            nodes.extend(all_var_nodes(item.children))
    return nodes
