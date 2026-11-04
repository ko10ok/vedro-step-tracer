"""Модель дерева вызовов: переменные, вызовы функций и шаги сценария."""

import copy
import time
from typing import Any, Dict, List, Optional, Union

__all__ = ("VarKind", "VarNode", "StepNode", "RootStep", "safe_copy",)

# Виды переменных, фиксируемых последовательно по мере появления (см.
# FunctionTracer): аргумент функции, локальная переменная внутри функции,
# новый атрибут scope (self сценария) и изменённый атрибут scope.
# Определяют маркер отображения и минимальный уровень verbosity, при
# котором переменная показывается (см. TreeWriter._KIND_MARKER/_KIND_MIN_VERBOSITY).
VarKind = str  # "arg" | "local" | "scope" | "scope_changed"


def safe_copy(value: Any) -> Any:
    """
    Скопировать значение в момент фиксации снимка, чтобы последующие мутации
    исходного объекта (например, переиспользуемого словаря/списка) не влияли
    на уже отображённые/сохранённые данные.
    """
    try:
        return copy.deepcopy(value)
    except Exception:
        try:
            return copy.copy(value)
        except Exception:
            return value


class VarNode:
    """Переменная, зафиксированная на уровне владельца (последовательно, в момент появления)."""
    __slots__ = ("key", "value", "level", "kind")

    def __init__(self, key: str, value: Any, level: int = 0, kind: VarKind = "local") -> None:
        self.key = key
        self.value = value
        self.level = level
        self.kind = kind


class StepNode:
    """Узел дерева вызовов — одна функция."""
    __slots__ = (
        "name", "_orig_name", "module", "level", "status", "duration",
        "flags", "children", "started_at", "local_vars", "return_value",
        "arg_names", "filename", "lineno",
    )

    def __init__(self, name: str, module: str, level: int, orig_name: str = "",
                 filename: str = "", lineno: int = 0) -> None:
        self.name = name
        self._orig_name = orig_name or name
        self.module = module
        # Файл и строка определения функции — для перехода к исходнику
        # из дерева тестов IDE (см. reporting/teamcity/writer.py).
        self.filename = filename
        self.lineno = lineno
        self.level = level
        self.status: str = "NOT_RUN"
        self.duration: Optional[float] = None
        self.flags: List[str] = []
        self.children: List[Union["StepNode", VarNode]] = []
        self.started_at: float = time.perf_counter()
        self.local_vars: Dict[str, Any] = {}
        self.return_value: Any = None
        self.arg_names: List[str] = []

    def close(self, status: str, local_vars: Dict[str, Any],
              return_value: Any = None) -> None:
        self.status = status
        self.duration = time.perf_counter() - self.started_at
        self.local_vars = local_vars
        self.return_value = return_value
        if self.duration > 2.0:
            self.flags.append("🐢")

# ═══════════════════════════════════════════════════════════════════════════════
# RootStep — корневой шаг (vedro step)
# ═══════════════════════════════════════════════════════════════════════════════


class RootStep:
    """Представляет один шаг сценария vedro (given_, when_, then_)."""
    __slots__ = ("name", "status", "duration", "flags", "call_tree", "started_at",
                 "failure_source", "failure_error", "failure_trace",
                 "filename", "lineno")

    def __init__(self, name: str) -> None:
        self.name = name
        # Файл сценария и строка определения метода шага — для перехода
        # к исходнику из дерева тестов IDE (заполняет плагин).
        self.filename: str = ""
        self.lineno: int = 0
        self.status: str = "NOT_RUN"
        self.duration: Optional[float] = None
        self.flags: List[str] = []
        # call_tree — последовательность вызовов (StepNode) и собранных по
        # мере появления scope-переменных (VarNode) в порядке возникновения
        # (см. FunctionTracer._emit_scope_diff/_emit_locals_diff).
        self.call_tree: List[Union[StepNode, VarNode]] = []
        self.started_at: float = time.perf_counter()
        self.failure_source: Optional[str] = None
        self.failure_error: Optional[str] = None
        # Тот же traceback, что и в failure_source, но plain text — для
        # выжимки, копируемой кнопкой «Скопировать для LLM».
        self.failure_trace: Optional[str] = None

    def close(self, status: str) -> None:
        self.status = status
        self.duration = time.perf_counter() - self.started_at
        if self.duration > 2.0:
            self.flags.append("🐢")
