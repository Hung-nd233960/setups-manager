"""Dashboard tab: every check's results, filling in as the checks finish."""

from collections import Counter

from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Label, Static, Switch
from textual.worker import get_current_worker

from setups_manager import runner
from setups_manager.context import Context
from setups_manager.model import Result, Status
from setups_manager.registry import Check

SYMBOLS = {
    Status.OK: ("✓ ok", "green"),
    Status.WARN: ("⚠ warn", "yellow"),
    Status.ERROR: ("✗ error", "bold red"),
    Status.SKIP: ("– skip", "dim"),  # noqa: RUF001  (en dash, as the plan asks)
}


def status_cell(status: Status) -> Text:
    label, style = SYMBOLS[status]
    return Text(label, style=style)


def row_key(result: Result, index: int) -> str:
    return f"{result.check}:{index}"


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
    def __init__(self, ctx: Context, checks: list[Check] | None = None) -> None:
        super().__init__(id="dashboard")
        self.ctx = ctx
        self.fixed_checks = checks  # None: ask the registry on every run
        self._generation = 0
        self._order: list[Check] = []
        self._done: dict[str, list[Result]] = {}
        self._finished = 0
        self._by_key: dict[str, Result] = {}

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

    @on(DataTable.RowHighlighted, "#checks-table")
    def _highlighted(self, event: DataTable.RowHighlighted) -> None:
        self._show_detail(event.data_table)
