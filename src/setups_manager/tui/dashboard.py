"""Dashboard tab: every check's results, filling in as the checks finish."""

import subprocess
from collections import Counter
from typing import ClassVar

from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Label, Static, Switch
from textual.worker import get_current_worker

from setups_manager import actions, runner, shell
from setups_manager.context import Context
from setups_manager.model import Result, Status, row_key
from setups_manager.registry import Check
from setups_manager.tui.widgets import ConfirmScreen, LogPanel

SYMBOLS = {
    Status.OK: ("✓ ok", "green"),
    Status.WARN: ("⚠ warn", "yellow"),
    Status.ERROR: ("✗ error", "bold red"),
    Status.SKIP: ("– skip", "dim"),  # noqa: RUF001  (en dash, as the plan asks)
}


def status_cell(status: Status) -> Text:
    label, style = SYMBOLS[status]
    return Text(label, style=style)


def summary_line(results: list[Result]) -> str:
    counts = Counter(r.status for r in results)
    parts = [
        f"{counts[Status.OK]} ok",
        f"{counts[Status.WARN]} warn",
        f"{counts[Status.ERROR]} error",
    ]
    if counts[Status.SKIP]:
        parts.append(f"{counts[Status.SKIP]} skip")
    return " · ".join(parts)


def detail_text(result: Result) -> str:
    lines = [f"{result.title}  [{result.status}]"]
    if result.detail:
        lines.append(result.detail)
    if result.fix:
        ask = " (asks first)" if result.fix.confirm else ""
        lines.append(f"Fix: {result.fix.label}{ask}")
        if result.fix.command:
            lines.append("  $ " + " ".join(result.fix.command))
    return "\n".join(lines)


class DashboardPane(Vertical):
    BINDINGS: ClassVar[list[BindingType]] = [Binding("f", "fix", "Run fix")]

    def __init__(self, ctx: Context, checks: list[Check] | None = None) -> None:
        super().__init__(id="dashboard")
        self.ctx = ctx
        self.fixed_checks = checks  # None: ask the registry on every run
        self._generation = 0
        self._order: list[Check] = []
        self._done: dict[str, list[Result]] = {}
        self._finished = 0
        self._by_key: dict[str, Result] = {}
        self.fixing = False  # one fix at a time

    def compose(self) -> ComposeResult:
        with Horizontal(id="dashboard-bar"):
            yield Label("Quick (skip slow checks)")
            yield Switch(True, id="quick-switch")
            yield Static("", id="progress", markup=False)
        yield DataTable(id="checks-table", cursor_type="row", zebra_stripes=True)
        yield Static("", id="summary", markup=False)
        yield Static(
            "Select a row to see its detail and fix.", id="detail", markup=False
        )
        with Horizontal(id="fix-bar"):
            yield Button("Run fix", id="fix-btn", variant="primary")
            yield Static("", id="fix-status", markup=False)
        yield LogPanel(id="fix-log")

    def on_mount(self) -> None:
        table = self.query_one("#checks-table", DataTable)
        table.add_column("Status", width=9)
        table.add_column("Check", width=14)
        table.add_column("Title")
        self.run_checks()

    # -- selecting checks -------------------------------------------------

    def checks_for(self, quick: bool) -> list[Check]:
        checks = (
            list(self.fixed_checks)
            if self.fixed_checks is not None
            else runner.select(self.ctx)
        )
        return [c for c in checks if not (quick and c.slow)]

    def run_checks(self, quick: bool | None = None) -> None:
        """Start a run. `quick=None` follows the Quick switch."""
        if quick is None:
            quick = self.query_one("#quick-switch", Switch).value
        self._generation += 1
        self._order = self.checks_for(quick)
        self._done = {}
        self._finished = 0
        self._redraw()
        self._run_worker_checks(self._generation, self._order)

    # -- the worker thread ------------------------------------------------

    @work(thread=True, exclusive=True)
    def _run_worker_checks(self, generation: int, checks: list[Check]) -> None:
        worker = get_current_worker()
        for batch in runner.iter_results(checks, self.ctx):
            if worker.is_cancelled:
                return
            self.app.call_from_thread(self._on_batch, generation, batch)
        if not worker.is_cancelled:
            self.app.call_from_thread(self._on_done, generation)

    def _on_batch(self, generation: int, batch: list[Result]) -> None:
        if generation != self._generation:
            return  # a newer run replaced this one
        self._finished += 1
        if batch:
            self._done[batch[0].check] = batch
        self._redraw()

    def _on_done(self, generation: int) -> None:
        if generation != self._generation:
            return
        self._finished = len(self._order)
        self._redraw()

    # -- drawing ----------------------------------------------------------

    def all_results(self) -> list[Result]:
        return [r for c in self._order for r in self._done.get(c.id, [])]

    def _redraw(self) -> None:
        table = self.query_one("#checks-table", DataTable)
        row = table.cursor_row
        table.clear()
        self._by_key = {}
        running = self._finished < len(self._order)
        for check in self._order:
            if check.id in self._done:
                for i, r in enumerate(self._done[check.id]):
                    key = row_key(r, i)
                    self._by_key[key] = r
                    table.add_row(status_cell(r.status), check.id, r.title, key=key)
            elif running:
                table.add_row(
                    Text("… running", style="dim"),
                    check.id,
                    Text(check.description, style="dim"),
                    key=f"{check.id}:running",
                )
        if table.row_count:
            table.move_cursor(row=min(row, table.row_count - 1))
        total = len(self._order)
        progress = self.query_one("#progress", Static)
        if running:
            progress.update(f"Running checks: {self._finished}/{total}")
        else:
            progress.update(f"Done: {total} checks")
        self.query_one("#summary", Static).update(summary_line(self.all_results()))
        self._show_detail(table)

    def _show_detail(self, table: DataTable) -> None:
        detail = self.query_one("#detail", Static)
        if not table.row_count:
            detail.update("No checks.")
            return
        cell_key = table.coordinate_to_cell_key(table.cursor_coordinate)
        result = self._by_key.get(cell_key.row_key.value or "")
        detail.update(detail_text(result) if result else "Still running…")
        self._update_fix_button(self.selected_target())

    @on(DataTable.RowHighlighted, "#checks-table")
    def _highlighted(self, event: DataTable.RowHighlighted) -> None:
        self._show_detail(event.data_table)

    # -- running a fix ----------------------------------------------------

    def selected_target(self) -> actions.FixTarget | None:
        """The selected row as a runnable fix; None for manual fixes and other rows."""
        table = self.query_one("#checks-table", DataTable)
        if not table.row_count:
            return None
        key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
        result = self._by_key.get(key or "")
        if result is None:
            return None
        # fixable() is the one place that decides what may run
        return next(iter(actions.fixable([result])), None)

    def _update_fix_button(self, target: actions.FixTarget | None) -> None:
        button = self.query_one("#fix-btn", Button)
        button.display = target is not None  # manual fixes get no run button
        button.disabled = self.fixing

    def action_fix(self) -> None:
        if self.fixing:
            self.notify("A fix is already running.", severity="warning")
            return
        target = self.selected_target()
        if target is None:
            self.notify("This row has no fix that can run.", severity="warning")
            return
        command = subprocess.list2cmdline(target.command)
        if target.fix.confirm:
            self.app.push_screen(
                ConfirmScreen(f"{target.fix.label}?", "$ " + command),
                lambda ok: self._start_fix(target) if ok else None,
            )
        else:
            self._start_fix(target)

    @on(Button.Pressed, "#fix-btn")
    def _fix_pressed(self) -> None:
        self.action_fix()

    def _start_fix(self, target: actions.FixTarget) -> None:
        if self.fixing:
            return
        self.fixing = True
        log = self.query_one("#fix-log", LogPanel)
        log.clear()
        log.add_line("$ " + subprocess.list2cmdline(target.command))
        self.query_one("#fix-status", Static).update(f"Running {target.key}…")
        self._update_fix_button(target)
        check = next((c for c in self._order if c.id == target.result.check), None)
        self._run_fix_worker(target, check, self._generation)

    @work(thread=True, exclusive=True, group="fix")
    def _run_fix_worker(
        self, target: actions.FixTarget, check: Check | None, generation: int
    ) -> None:
        log = self.query_one("#fix-log", LogPanel)
        code = 1
        for item in actions.run_fix(target):
            if isinstance(item, shell.Exit):
                code = item.code
            else:
                self.app.call_from_thread(log.add_line, item)
        # the fix may have worked: ask the owning check again
        fresh = runner.run_one(check, self.ctx) if check else None
        self.app.call_from_thread(self._fix_finished, target, code, fresh, generation)

    def _fix_finished(
        self,
        target: actions.FixTarget,
        code: int,
        fresh: list[Result] | None,
        generation: int,
    ) -> None:
        self.fixing = False
        self.query_one("#fix-status", Static).update(
            f"{target.key}: fix exited {code}"
            + ("" if fresh is None else "; check re-run")
        )
        if fresh is not None and generation == self._generation:
            self._done[target.result.check] = fresh
        self._redraw()
