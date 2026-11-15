"""Слой трейсинга: модель узлов, sys.settrace-трейсер и пост-обработка дерева."""

from .nodes import RootStep, StepNode, VarKind, VarNode, safe_copy
from .tracer import FunctionTracer
from .tree import collapse_tree, collect_max_duration

__all__ = (
    "RootStep", "StepNode", "VarKind", "VarNode", "safe_copy",
    "FunctionTracer", "collapse_tree", "collect_max_duration",
)
