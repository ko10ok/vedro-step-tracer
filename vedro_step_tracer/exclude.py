"""
Исключение значений из глубокого снимка (``safe_copy``) по типу, имени типа,
модулю, предикату, regex или по конкретной переменной в конкретной функции.

Зачем. Объекты, которые держат ОС-ресурсы (пайпы, сокеты, транспорты
asyncio, ssl), либо не копируются (``copy.deepcopy``/``copy.copy`` падают),
либо копируются поверхностно и всё равно делят с оригиналом внутренние
ссылки. Текущий ``safe_copy`` в этом случае как последний fallback отдаёт
сам оригинальный объект — и дерево трейса держит на него ссылку до конца
жизни шага (или дольше), что продлевает жизнь объекта и может сломать
порядок финализации при выходе из интерпретатора (``Exception ignored in:
... __del__ ...``).

Элемент списка правил (``exclude_value_types``/``extra_exclude_value_types``
в конфиге) — любое из:

* ``type`` или ``(type, ...)`` — проверка через ``isinstance``. Самый
  быстрый вариант и единственный, которым заданы дефолты: достаточно
  публичных ABC (``asyncio.BaseTransport``, ``asyncio.AbstractEventLoop``),
  чтобы поймать и приватные платформенные подклассы
  (``_UnixReadPipeTransport``, ``_UnixSelectorEventLoop`` и т.п.).
* ``str`` — точное совпадение с ``type(value).__name__``.
* ``re.Pattern`` — ``.search()`` по ``f"{module}.{qualname}"`` типа значения.
* произвольный ``callable`` (в т.ч. ``lambda``) — предикат ``fn(value)``.
* :func:`module` — явно помеченное исключение по префиксу модуля
  (``type(value).__module__``), без двусмысленности с именем типа.
* :func:`var` — конкретная переменная по имени, опционально только в
  указанной функции и/или модуле — остальной вызов продолжает трейситься
  как обычно (не то же самое, что ``exclude_functions``, которое убирает
  вызов целиком).

Правила раскладываются по типу один раз, при старте (см.
``ValueExcludeRules.compile``): пустая категория правил (например, нет ни
одного regex) не участвует в проверке каждого значения вообще — поэтому
без пользовательских правил эффективно выполняется один ``isinstance()``
на значение.
"""

import asyncio
import re
import socket
import ssl
from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Pattern, Sequence, Tuple, Union

__all__ = (
    "ModuleRule", "VarRule", "ExcludeRule",
    "module", "var",
    "DEFAULT_EXCLUDED_VALUE_TYPES",
    "ValueExcludeRules",
    "EXCLUDED_PLACEHOLDER",
)


@dataclass(frozen=True)
class ModuleRule:
    """Исключение по префиксу модуля типа значения (см. :func:`module`)."""
    prefix: str


@dataclass(frozen=True)
class VarRule:
    """Исключение конкретной переменной по имени (см. :func:`var`)."""
    name: str
    function: Optional[str] = None
    module: Optional[str] = None


def module(prefix: str) -> ModuleRule:
    """
    Исключить любое значение, чей тип определён в модуле ``prefix`` или его
    подмодуле (сравнение по префиксу строки, например ``module("ssl")``
    поймает и ``ssl.SSLSocket``, объявленный прямо в ``ssl``).
    """
    return ModuleRule(prefix)


def var(name: str, function: Optional[str] = None, module: Optional[str] = None) -> VarRule:
    """
    Исключить одну конкретную переменную по имени — опционально только
    внутри функции ``function`` (сравнение с «сырым» именем, без имени
    класса) и/или модуля ``module`` (как в ``StepNode.module``), а не любое
    значение такого типа во всём трейсе.
    """
    return VarRule(name=name, function=function, module=module)


ExcludeRule = Union[type, Tuple[type, ...], str, Pattern, Callable[[Any], bool], ModuleRule, VarRule]

# Дефолты заданы только типами — самая быстрая проверка (один isinstance по
# кортежу). Публичные ABC ловят и приватные платформенные реализации:
# asyncio.BaseTransport — все транспорты (pipe/subprocess/socket, в т.ч.
# `_UnixReadPipeTransport`, `_UnixSubprocessTransport`, ...);
# asyncio.AbstractEventLoop — цикл событий (в т.ч. `_UnixSelectorEventLoop`).
DEFAULT_EXCLUDED_VALUE_TYPES: Tuple[type, ...] = (
    asyncio.BaseTransport,
    asyncio.AbstractEventLoop,
    asyncio.subprocess.Process,
    ssl.SSLSocket,
    ssl.SSLObject,
    socket.socket,
)

# Значение-заглушка, которым заменяется исключённое значение в дереве трейса
# — не хранит ссылку на оригинал и не требует copy.
EXCLUDED_PLACEHOLDER = "<excluded from trace>"


def _qualified_name(value: Any) -> str:
    cls = type(value)
    return f"{cls.__module__}.{cls.__qualname__}"


class ValueExcludeRules:
    """
    Скомпилированный (разложенный по категориям) набор правил исключения
    значений. Строится один раз в плагине из
    ``exclude_value_types + extra_exclude_value_types`` и передаётся в
    ``FunctionTracer`` — так каждая проверка значения не парсит список
    правил заново.
    """
    __slots__ = ("_types", "_names", "_patterns", "_predicates", "_modules", "_vars")

    def __init__(self, rules: Sequence[ExcludeRule] = ()) -> None:
        types: List[type] = []
        names: List[str] = []
        patterns: List[Pattern] = []
        predicates: List[Callable[[Any], bool]] = []
        modules: List[str] = []
        var_rules: List[VarRule] = []

        for rule in rules:
            if isinstance(rule, VarRule):
                var_rules.append(rule)
            elif isinstance(rule, ModuleRule):
                modules.append(rule.prefix)
            elif isinstance(rule, type):
                types.append(rule)
            elif isinstance(rule, tuple) and rule and all(isinstance(r, type) for r in rule):
                types.extend(rule)
            elif isinstance(rule, str):
                names.append(rule)
            elif isinstance(rule, re.Pattern):
                patterns.append(rule)
            elif callable(rule):
                predicates.append(rule)
            # неопознанное правило молча игнорируется — не должно падать
            # весь прогон из-за опечатки в пользовательском конфиге.

        # Пустая категория = не участвует в проверке вообще (см. excluded()).
        self._types: Optional[Tuple[type, ...]] = tuple(types) if types else None
        self._names: Optional[frozenset] = frozenset(names) if names else None
        self._patterns: List[Pattern] = patterns
        self._predicates: List[Callable[[Any], bool]] = predicates
        self._modules: Tuple[str, ...] = tuple(modules)
        self._vars: List[VarRule] = var_rules

    def excluded(self, value: Any, var_name: str = "", function: str = "", module: str = "") -> bool:
        """Проверить значение (и, для var-правил, его имя/контекст вызова)."""
        if self._types is not None and isinstance(value, self._types):
            return True

        if self._names is not None or self._patterns or self._modules:
            type_obj = type(value)
            if self._names is not None and type_obj.__name__ in self._names:
                return True
            if self._modules and any(type_obj.__module__.startswith(p) for p in self._modules):
                return True
            if self._patterns:
                qualified = _qualified_name(value)
                for pattern in self._patterns:
                    if pattern.search(qualified):
                        return True

        if self._predicates:
            for predicate in self._predicates:
                try:
                    if predicate(value):
                        return True
                except Exception:
                    continue

        if self._vars and var_name:
            for rule in self._vars:
                if rule.name != var_name:
                    continue
                if rule.function is not None and rule.function != function:
                    continue
                if rule.module is not None and rule.module != module:
                    continue
                return True

        return False
