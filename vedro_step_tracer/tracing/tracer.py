"""FunctionTracer — сбор дерева вызовов через sys.settrace()."""

import fnmatch
import os
import sys
from typing import Any, Callable, Dict, List, Optional, Set, Union

from .. import settings
from .nodes import StepNode, VarNode, safe_copy

__all__ = ("FunctionTracer",)


def _fingerprint(value: Any) -> tuple:
    """
    Дешёвый отпечаток значения для обнаружения изменений.

    Сравнения по ``id`` недостаточно: контейнер может наполняться на месте
    уже после того, как его зафиксировали. Так ведёт себя, например,
    ``history`` у моков — список возвращается пустым, а записи дописываются
    в него позже, и ``id`` при этом не меняется. Поэтому к идентичности
    добавляется размер: для sized-контейнеров он ловит дописывание, для
    остальных типов отпечаток вырождается в прежнее сравнение по ``id``.
    """
    size = None
    if isinstance(value, (list, dict, set, frozenset, tuple, str, bytes, bytearray)):
        try:
            size = len(value)
        except BaseException:
            size = None
    return (id(value), size)

# ═══════════════════════════════════════════════════════════════════════════════
# FunctionTracer — sys.settrace обёртка
# ═══════════════════════════════════════════════════════════════════════════════


class FunctionTracer:
    """
    Трейсер на основе sys.settrace().
    Отслеживает call/return событий для функций из целевых директорий.

    Помимо построения дерева вызовов, при каждом входе и выходе из функции
    (на любом уровне вложенности, не только в шаге теста) сравнивает текущее
    состояние scope (атрибутов self сценария) и локальных переменных
    вызывающей функции с ранее зафиксированным снимком и последовательно
    добавляет новые/изменённые переменные (VarNode) в дерево — непосредственно
    перед следующим вложенным вызовом или в момент выхода из функции. Это
    даёт последовательный (не блочный) вывод: значения появляются в дереве
    точно в том порядке, в котором были собраны/изменены.
    """

    # Имена «функций», которые никогда не попадают в дерево вызовов:
    # синтетические конструкции интерпретатора.
    _SKIPPED_NAMES = frozenset((
        "<lambda>", "<listcomp>", "<dictcomp>", "<setcomp>", "<genexpr>", "<module>",
    ))

    def __init__(self, target_dirs: List[str],
                 initial_self_vars: Optional[Dict[str, Any]] = None,
                 scenario_self: Any = None,
                 step_name: str = "",
                 exclude_paths: Optional[List[str]] = None,
                 exclude_functions: Optional[List[str]] = None) -> None:
        self.target_dirs = [os.path.abspath(d) for d in target_dirs]
        # Файлы и функции внутри target_dirs, которые не должны порождать
        # узлы дерева (шум вроде обёрток над docker SDK). Исключение
        # означает «не создавать узел для вызовов из этого файла», а не
        # «перестать следить за тем, что он вызвал»: вложенные целевые
        # вызовы остаются в дереве и прицепляются к ближайшему не
        # исключённому предку (см. _global_trace).
        self.exclude_paths: List[str] = list(exclude_paths or [])
        self.exclude_functions: Set[str] = set(exclude_functions or [])
        self.call_stack: List[StepNode] = []
        self.root_children: List[Union[StepNode, VarNode]] = []
        self._old_trace: Optional[Callable] = None
        self._active = False
        # Экземпляр сценария. Обычно захватывается из фрейма самого шага (см.
        # _global_trace), но шаг может вообще не звать код из target_dirs
        # (проверки, присваивания) — тогда без экземпляра scope-переменные
        # такого шага остались бы несобранными.
        self.scenario_self: Any = scenario_self
        # Имя метода шага — по нему опознаётся его фрейм.
        self._step_name = step_name
        self._step_frame: Any = None  # фрейм функции шага (given_/when_/then_)

        # Кэш решений «файл целевой?»: co_filename переиспользуется
        # интерпретатором для всех вызовов из одного модуля, а сама проверка
        # (abspath + перебор целевых директорий) выполняется на каждый вызов
        # в процессе — без кэша это заметная часть накладных расходов.
        self._target_file_cache: Dict[str, bool] = {}

        # Снимки состояния для последовательной фиксации переменных:
        # scope (self сценария) — общий на весь шаг, ключ -> отпечаток значения.
        self._initial_self_vars: Dict[str, Any] = initial_self_vars or {}
        self._self_snapshot: Dict[str, tuple] = {
            k: _fingerprint(v) for k, v in self._initial_self_vars.items()
        }
        # locals функции шага (root-уровень, не self) — ключ -> отпечаток значения.
        self._root_locals_snapshot: Dict[str, tuple] = {}
        # locals каждой активной вложенной функции — id(frame) -> {ключ: отпечаток}.
        self._locals_snapshots: Dict[int, Dict[str, tuple]] = {}
        # фреймы активных вызовов, синхронизированы с call_stack по индексам.
        self._active_frames: List[Any] = []

    def start(self) -> None:
        """Установить трейсинг."""
        self.call_stack = []
        self.root_children = []
        self._active_frames = []
        self._locals_snapshots = {}
        self._root_locals_snapshot = {}
        self._self_snapshot = {k: _fingerprint(v) for k, v in self._initial_self_vars.items()}
        self._old_trace = sys.gettrace()
        self._active = True
        sys.settrace(self._global_trace)

    def stop(self) -> List[Union[StepNode, VarNode]]:
        """Снять трейсинг, зафиксировать финальные scope/locals и вернуть дерево вызовов."""
        self._active = False
        sys.settrace(self._old_trace)
        self._old_trace = None
        # Финальный сбор («на выходе» из шага): любые scope/locals изменения,
        # сделанные после последнего вложенного вызова, попадают в конец дерева.
        self._emit_scope_diff(self.root_children)
        self._emit_locals_diff(self._step_frame, self.root_children, self._root_locals_snapshot)
        return self.root_children

    @property
    def step_locals(self) -> Dict[str, Any]:
        """Локальные переменные функции шага (без self и приватных)."""
        if self._step_frame is None:
            return {}
        try:
            loc = self._step_frame.f_locals
        except (AttributeError, ValueError):
            return {}
        return {
            k: v for k, v in loc.items()
            if k not in settings.FILTERED_KEYS and not k.startswith("_") and k != "self"
        }

    def _is_target_file(self, filename: str) -> bool:
        """
        Проверить, принадлежит ли файл целевым директориям и не исключён ли он
        (с кэшем по имени файла — решение одинаково для всего модуля).
        """
        cached = self._target_file_cache.get(filename)
        if cached is not None:
            return cached
        if not filename:
            result = False
        else:
            abs_path = os.path.abspath(filename)
            in_target = any(abs_path.startswith(d) for d in self.target_dirs)
            result = in_target and not self._is_excluded_path(abs_path)
        self._target_file_cache[filename] = result
        return result

    def _is_excluded_path(self, abs_path: str) -> bool:
        """Совпадает ли путь с одним из glob-паттернов exclude_paths."""
        for pattern in self.exclude_paths:
            normalized = pattern.lstrip("/")
            if fnmatch.fnmatch(abs_path, pattern) or fnmatch.fnmatch(abs_path, f"*/{normalized}"):
                return True
        return False

    def _global_trace(self, frame: Any, event: str, arg: Any) -> Optional[Callable]:
        """
        Глобальный trace-callback: вызывается интерпретатором на входе в
        КАЖДЫЙ новый фрейм процесса.

        Локальный трейсинг (события line/return/exception внутри фрейма)
        включается только для вызовов из целевых директорий: для остального
        кода — сторонних библиотек, самого vedro, тела сценария — возвращаем
        None, и интерпретатор не генерирует по нему события вовсе. Вложенные
        целевые вызовы при этом не теряются: сюда всё равно приходит call на
        каждый новый фрейм, независимо от того, кто его породил.
        """
        if not self._active or event != "call":
            return None

        code = frame.f_code
        # Фрейм самого шага сценария: он не в target_dirs и в дерево вызовов не
        # попадает, но именно из него берутся экземпляр сценария и его locals.
        # Сравнение имён дёшево, а после захвата ветка больше не выполняется.
        if self._step_frame is None and code.co_name == self._step_name:
            self._capture_step_frame(frame)

        if not self._is_target_file(code.co_filename):
            return None

        func_name = code.co_name
        # Магические методы и синтетические конструкции в дерево не попадают,
        # поэтому и следить за их фреймами не нужно.
        if func_name in self._SKIPPED_NAMES:
            return None
        if func_name.startswith("__") and func_name.endswith("__"):
            return None
        # Исключённая функция: узел не создаём и фрейм в стек не кладём,
        # поэтому её вложенные целевые вызовы станут детьми ближайшего
        # не исключённого предка.
        if func_name in self.exclude_functions:
            return None

        self._handle_call(frame)
        # Из событий внутри фрейма нужен только return: построчный трейсинг
        # целевой функции стоит дорого и ничего не даёт дереву вызовов.
        frame.f_trace_lines = False
        return self._local_trace

    def _capture_step_frame(self, frame: Any) -> None:
        """Запомнить фрейм шага и экземпляр сценария из него."""
        step_self = frame.f_locals.get("self")
        if step_self is None or not hasattr(type(step_self), "subject"):
            return
        self._step_frame = frame
        if self.scenario_self is None:
            self.scenario_self = step_self

    def _local_trace(self, frame: Any, event: str, arg: Any) -> Optional[Callable]:
        """Локальный trace-callback целевого фрейма: интересен только возврат."""
        if event == "return" and self._active:
            self._handle_return(frame, arg)
        return self._local_trace

    # ── Последовательная фиксация scope/locals ──────────────────────────────

    def _emit_scope_diff(self, target_children: List[Union[StepNode, VarNode]]) -> None:
        """Сравнить текущие атрибуты self сценария со снимком и дописать новые/изменённые."""
        if self.scenario_self is None:
            return
        current_dict = getattr(self.scenario_self, "__dict__", {})
        for key, value in current_dict.items():
            if key.startswith("_"):
                continue
            cur_fp = _fingerprint(value)
            prev_fp = self._self_snapshot.get(key)
            if prev_fp is None:
                target_children.append(VarNode(key, safe_copy(value), kind="scope"))
                self._self_snapshot[key] = cur_fp
            elif prev_fp != cur_fp:
                target_children.append(VarNode(key, safe_copy(value), kind="scope_changed"))
                self._self_snapshot[key] = cur_fp

    def _emit_locals_diff(self, frame: Any, target_children: List[Union[StepNode, VarNode]],
                          snapshot: Dict[str, tuple]) -> None:
        """Сравнить локальные переменные фрейма со снимком и дописать новые/изменённые."""
        if frame is None:
            return
        try:
            loc = frame.f_locals
        except (AttributeError, ValueError):
            return
        for key, value in loc.items():
            if key in settings.FILTERED_KEYS or key.startswith("__"):
                continue
            cur_fp = _fingerprint(value)
            prev_fp = snapshot.get(key)
            if prev_fp is None or prev_fp != cur_fp:
                target_children.append(VarNode(key, safe_copy(value), kind="local"))
                snapshot[key] = cur_fp

    def _flush_before_call(self) -> None:
        """
        Перед созданием нового узла вызова — зафиксировать все новые/изменённые
        scope- и locals-переменные, накопленные с прошлой проверки, в дереве
        того владельца, в котором сейчас выполняется код (родительский вызов
        или, на верхнем уровне, сам шаг теста).
        """
        if self.call_stack:
            parent = self.call_stack[-1]
            owner_frame = self._active_frames[-1] if self._active_frames else None
            snapshot = self._locals_snapshots.setdefault(id(owner_frame), {}) \
                if owner_frame is not None else {}
            self._emit_scope_diff(parent.children)
            self._emit_locals_diff(owner_frame, parent.children, snapshot)
        else:
            self._emit_scope_diff(self.root_children)
            self._emit_locals_diff(self._step_frame, self.root_children, self._root_locals_snapshot)

    def _handle_call(self, frame: Any) -> None:
        """
        Обработка входа в функцию из целевой директории.

        Вызывается только для фреймов, прошедших фильтрацию в _global_trace:
        файл лежит в target_dirs, имя функции не служебное.
        """
        func_name = frame.f_code.co_name

        # Перед созданием нового узла — сбор состояния «на входе» в текущую
        # функцию (см. докстроку класса).
        self._flush_before_call()

        # Определяем модуль относительно целевых директорий
        filename = frame.f_code.co_filename
        module = self._get_relative_module(filename)

        # Определяем имя класса для методов
        display_name = func_name
        if "self" in frame.f_locals:
            cls_name = type(frame.f_locals["self"]).__name__
            display_name = f"{cls_name} ▸ {func_name}"
        elif "cls" in frame.f_locals:
            cls_obj = frame.f_locals["cls"]
            cls_name = cls_obj.__name__ if hasattr(cls_obj, "__name__") else str(cls_obj)
            display_name = f"{cls_name} ▸ {func_name}"

        level = len(self.call_stack) + 2  # +2 потому что L1 — это vedro step
        node = StepNode(name=display_name, module=module, level=level, orig_name=func_name,
                        filename=filename, lineno=frame.f_code.co_firstlineno)

        # Сохраняем имена аргументов функции
        code = frame.f_code
        arg_count = code.co_argcount + code.co_kwonlyargcount
        node.arg_names = list(code.co_varnames[:arg_count])

        # Аргументы фиксируем сразу «на входе» — это первые элементы
        # последовательности children этого узла.
        own_snapshot: Dict[str, tuple] = {}
        for name in node.arg_names:
            if name in settings.FILTERED_KEYS or name.startswith("_"):
                continue
            if name not in frame.f_locals:
                continue
            value = frame.f_locals[name]
            node.children.append(VarNode(name, safe_copy(value), kind="arg"))
            own_snapshot[name] = _fingerprint(value)
        self._locals_snapshots[id(frame)] = own_snapshot

        if self.call_stack:
            self.call_stack[-1].children.append(node)
        else:
            self.root_children.append(node)

        self.call_stack.append(node)
        self._active_frames.append(frame)

    def _handle_return(self, frame: Any, return_value: Any) -> None:
        """
        Обработка выхода из функции.

        Вызывается только для фреймов, попавших в дерево (_local_trace
        назначается лишь целевым, неслужебным вызовам).
        """
        func_name = frame.f_code.co_name

        if not self.call_stack:
            return

        current = self.call_stack[-1]
        if current._orig_name != func_name:
            # Несовпадение — возможно пропущенный call (lambda, comprehension)
            # Ищем в стеке
            for i in range(len(self.call_stack) - 1, -1, -1):
                if self.call_stack[i]._orig_name == func_name:
                    # Закрываем все промежуточные
                    while len(self.call_stack) > i + 1:
                        orphan = self.call_stack.pop()
                        orphan_frame = self._active_frames.pop() if self._active_frames else None
                        if orphan_frame is not None:
                            self._locals_snapshots.pop(id(orphan_frame), None)
                        orphan.close("ERROR", {})
                    current = self.call_stack[-1]
                    break
            else:
                return

        # Сбор состояния «на выходе» из функции: любые локальные переменные и
        # scope-изменения, сделанные после последнего вложенного вызова.
        own_snapshot = self._locals_snapshots.get(id(frame), {})
        self._emit_locals_diff(frame, current.children, own_snapshot)
        self._emit_scope_diff(current.children)
        self._locals_snapshots.pop(id(frame), None)

        # Собираем locals (для обратной совместимости — используется, например,
        # для сопоставления имён аргументов при построении узла).
        local_vars = self._collect_locals(frame)

        # Сокращаем return_value для хранения
        current.close("PASS", local_vars, return_value)
        self.call_stack.pop()
        if self._active_frames:
            self._active_frames.pop()

    def _collect_locals(self, frame: Any) -> Dict[str, Any]:
        """Собрать локальные переменные, отфильтровав служебные."""
        result = {}
        for key, value in frame.f_locals.items():
            if key in settings.FILTERED_KEYS:
                continue
            if key.startswith("__"):
                continue
            # Пропускаем слишком тяжёлые объекты — сохраняем repr
            try:
                result[key] = value
            except Exception:
                result[key] = "<unserializable>"
        return result

    def _get_relative_module(self, filename: str) -> str:
        """Получить относительный путь модуля."""
        abs_path = os.path.abspath(filename)
        for d in self.target_dirs:
            if abs_path.startswith(d):
                rel = os.path.relpath(abs_path, os.path.dirname(d))
                return rel.replace(".py", "").replace(os.sep, ".")
        return os.path.basename(filename).replace(".py", "")
