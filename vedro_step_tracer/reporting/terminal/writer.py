"""TreeWriter — потоковый рендеринг дерева шагов в текст для stdout."""

from io import StringIO
from typing import Any, List, Optional

from rich.console import Console
from rich.markup import escape as markup_escape

from ... import gitlab as gitlab_ci
from ...tracing import RootStep, StepNode, VarNode
from ..base import BaseReportRenderer
from ..status import STATUS_EMOJI
from .markup import INDENT, get_level_color, get_style, markup_value

__all__ = ("TreeWriter",)


class TreeWriter(BaseReportRenderer):
    """Потоковый writer для рендеринга дерева шагов."""

    # Маркер и минимальный уровень verbosity, при котором переменная данного
    # вида показывается (см. VarNode.kind).
    _KIND_MARKER = {"arg": "→", "local": "·", "scope": "⇒", "scope_changed": "⇒"}
    _KIND_MIN_VERBOSITY = {"arg": 2, "local": 3, "scope": 1, "scope_changed": 1}

    def __init__(self, verbosity: int = 1, color: bool = True, gitlab: bool = False) -> None:
        self.verbosity = verbosity
        self._color = color
        self._gitlab = gitlab
        self._console: Optional[Console] = None
        self._gl_sections = gitlab_ci.SectionIdGenerator()

    def _make_console(self, buf: StringIO) -> Console:
        return Console(
            file=buf,
            markup=True,
            highlight=False,
            force_terminal=self._color,
            no_color=not self._color,
            width=10000,
        )

    def _require_console(self) -> Console:
        """Консоль текущего рендера; создаётся в render_scenario/render_step."""
        if self._console is None:
            raise RuntimeError("Console is not initialized: render_scenario() was not called")
        return self._console

    # ── GitLab-секции ────────────────────────────────────────────────────────

    def _gl_next_id(self) -> str:
        return self._gl_sections.next_id()

    def _write_raw(self, text: str) -> None:
        """Записать сырой текст в буфер, минуя rich-markup."""
        if self._console is not None:
            self._console.file.write(text)

    def _gl_section_start(self, section_id: str, collapsed: bool = True) -> None:
        """Записать маркер начала GitLab-секции (сразу перед заголовком)."""
        self._write_raw(gitlab_ci.section_start(section_id, collapsed))

    def _gl_section_end(self, section_id: str) -> None:
        """Записать маркер конца GitLab-секции."""
        self._write_raw(gitlab_ci.section_end(section_id))

    def render_document(self, scenario_name: str, steps: List[RootStep],
                        scenario_path: str = "") -> str:
        """Реализация BaseReportRenderer: путь к сценарию в stdout не нужен."""
        return self.render_scenario(scenario_name, steps)

    def render_scenario(self, scenario_name: str, steps: List[RootStep]) -> str:
        buf = StringIO()
        self._console = self._make_console(buf)
        for root_step in steps:
            self._render_root_step(root_step)
        return buf.getvalue()

    def render_step(self, root: RootStep) -> str:
        buf = StringIO()
        self._console = self._make_console(buf)
        self._render_root_step(root)
        return buf.getvalue()

    def _render_root_step(self, root: RootStep) -> None:
        console = self._require_console()
        emoji = STATUS_EMOJI.get(root.status, "[dim]○[/dim]")
        head = f" {emoji} [cyan]{markup_escape(root.name)}[/cyan]"
        if root.duration is not None:
            head += f"  [dim white]⏱️ {root.duration:.2f}s[/dim white]"
        if root.flags:
            head += "  " + " ".join(root.flags)
        console.print(head)

        # Дерево вызовов и последовательно собранные scope/locals переменные
        # перемешаны в call_tree в порядке появления (см. FunctionTracer) —
        # рендерим единым проходом, без отдельных блоков.
        if root.call_tree:
            l1_vert = get_style(1)[0]
            l1_prefix = " " + l1_vert + INDENT
            # Пустая строка-разделитель нужна только вокруг вызовов (StepNode);
            # между соседними переменными (VarNode) разделитель не добавляется.
            last_kind: Optional[str] = None
            for child in root.call_tree:
                if isinstance(child, StepNode):
                    if last_kind is not None:
                        console.print(f" {l1_vert}")
                    last_kind = "step"
                    self._render_step(child, parent_prefix=l1_prefix, level=2, is_top=True)
                elif isinstance(child, VarNode):
                    if self.verbosity < self._KIND_MIN_VERBOSITY.get(child.kind, 1):
                        continue
                    if last_kind == "step":
                        console.print(f" {l1_vert}")
                    last_kind = "var"
                    self._render_parent_var(child, l1_prefix)

        console.print()

    def _render_step(self, node: StepNode, parent_prefix: str, level: int,
                     is_top: bool = False) -> None:
        console = self._require_console()
        vertical, connector, closer = get_style(level)
        color = get_level_color(level)
        if color:
            colored_vert = f"[{color}]{markup_escape(vertical)}[/{color}]"
            colored_conn = f"[{color}]{markup_escape(connector)}[/{color}]"
        else:
            colored_vert = f"[dim]{markup_escape(vertical)}[/dim]"
            colored_conn = f"[dim]{markup_escape(connector)}[/dim]"
        own_prefix = parent_prefix + colored_vert + INDENT

        # Заголовок
        emoji = STATUS_EMOJI.get(node.status, "[dim]○[/dim]")
        module_hint = ""
        if node.module:
            module_hint = f" [dim white]({markup_escape(node.module)})[/dim white]"
        head = (f"{parent_prefix}{colored_conn} "
                f"{emoji} [cyan]{markup_escape(node.name)}[/cyan]{module_hint}")
        if node.duration is not None and node.duration >= 0.001:
            head += f"  [dim white]⏱️ {node.duration:.2f}s[/dim white]"
        if node.flags:
            head += "  " + " ".join(node.flags)

        # GitLab: секция для всего вызова функции
        step_sid = None
        if self._gitlab:
            step_sid = self._gl_next_id()
            self._gl_section_start(step_sid)

        console.print(head)

        last_kind: Optional[str] = None

        # Дочерние вызовы и последовательно собранные аргументы/локальные
        # переменные этой функции перемешаны в node.children в порядке
        # появления (см. FunctionTracer) — единый проход, без блоков.
        # Пустая строка-разделитель нужна только вокруг вызовов (StepNode);
        # между соседними переменными (VarNode) разделитель не добавляется.
        for child in node.children:
            if isinstance(child, StepNode):
                if last_kind is not None:
                    console.print(own_prefix)
                last_kind = "step"
                self._render_step(child, own_prefix, level + 1, is_top=False)
            elif isinstance(child, VarNode):
                if self.verbosity < self._KIND_MIN_VERBOSITY.get(child.kind, 1):
                    continue
                if last_kind == "step":
                    console.print(own_prefix)
                last_kind = "var"
                self._render_parent_var(child, own_prefix)

        # Возвращаемое значение
        show_return = (
            (self.verbosity >= 1) or
            (self.verbosity >= 0 and is_top)
        )
        if show_return and node.return_value is not None:
            if last_kind is not None:
                console.print(own_prefix)
            ret_sid = None
            if self._gitlab:
                ret_sid = self._gl_next_id()
                # Возвращаемое значение всегда должно быть развёрнуто сразу
                # при раскрытии родительской секции вызова, поэтому секция
                # создаётся не свёрнутой (collapsed=False).
                self._gl_section_start(ret_sid, collapsed=False)
                console.print(f"{own_prefix}[dim]↲[/dim]")
            self._render_var("", node.return_value, own_prefix, marker="↲")
            if ret_sid is not None:
                self._gl_section_end(ret_sid)

        if step_sid is not None:
            self._gl_section_end(step_sid)

    def _render_var(self, key: str, value: Any, prefix: str, marker: str = "·",
                    collapse_value: bool = False) -> None:
        """Рендерит переменную с rich-markup.

        Если collapse_value=True и включён режим GitLab, значение
        оборачивается в отдельную свёрнутую по умолчанию секцию: заголовок
        (ключ) остаётся видимым, а значение появляется на следующей строке
        только при разворачивании — с сохранением отступов и маркировки
        вложенности (cont_prefix).
        """
        console = self._require_console()
        cont_prefix = prefix + "  "

        if key:
            head = (f"{prefix}[dim]{markup_escape(marker)}[/dim] "
                    f"[yellow]{markup_escape(key)}[/yellow][dim]:[/dim]")
        else:
            head = f"{prefix}[dim]{markup_escape(marker)}[/dim]"

        if collapse_value and self._gitlab:
            var_sid = self._gl_next_id()
            self._gl_section_start(var_sid, collapsed=True)
            console.print(head)
            markup_val = markup_value(value, cont_prefix, depth=0)
            console.print(f"{cont_prefix}{markup_val}")
            self._gl_section_end(var_sid)
        else:
            markup_val = markup_value(value, cont_prefix, depth=0)
            console.print(f"{head} {markup_val}")

    def _render_parent_var(self, var_node: VarNode, prefix: str) -> None:
        """
        Рендерит переменную, последовательно зафиксированную трейсером
        (аргумент, локальная переменная или scope self сценария — новая либо
        изменённая). Маркер и цвет зависят от var_node.kind. В режиме GitLab
        значение каждой переменной сворачивается индивидуально.
        """
        marker = self._KIND_MARKER.get(var_node.kind, "·")
        if var_node.kind == "scope_changed":
            self._render_changed_var(var_node.key, var_node.value, prefix,
                                     collapse_value=self._gitlab)
        else:
            self._render_var(var_node.key, var_node.value, prefix, marker=marker,
                             collapse_value=self._gitlab)

    def _render_changed_var(self, key: str, value: Any, prefix: str,
                            collapse_value: bool = False) -> None:
        """Рендерит изменённую переменную — ключ выделен оранжевым."""
        console = self._require_console()
        cont_prefix = prefix + "  "
        head = (f"{prefix}[dim]⇒[/dim] "
                f"[bright_yellow]{markup_escape(key)}[/bright_yellow][dim]:[/dim]")

        if collapse_value and self._gitlab:
            var_sid = self._gl_next_id()
            self._gl_section_start(var_sid, collapsed=True)
            console.print(head)
            markup_val = markup_value(value, cont_prefix, depth=0)
            console.print(f"{cont_prefix}{markup_val}")
            self._gl_section_end(var_sid)
        else:
            markup_val = markup_value(value, cont_prefix, depth=0)
            console.print(f"{head} {markup_val}")
