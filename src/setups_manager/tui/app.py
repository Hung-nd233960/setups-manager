"""The Textual app: tabs over the same core the CLI uses. Never run this from an agent."""

from pathlib import Path
from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.theme import BUILTIN_THEMES
from textual.widgets import Footer, Header, TabbedContent, TabPane

from setups_manager.context import Context
from setups_manager.registry import Check
from setups_manager.tui.dashboard import DashboardPane
from setups_manager.tui.new_project import NewProjectPane

THEME = "catppuccin-mocha"


class SetupsApp(App):
    TITLE = "Setups Manager"
    CSS_PATH = Path(__file__).with_name("app.tcss")
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("q", "quit", "Quit"),
        Binding("r", "rerun(False)", "Re-run"),
        Binding("R", "rerun(True)", "Run all"),
        Binding("n", "new_project", "New project"),
    ]

    def __init__(
        self, ctx: Context | None = None, checks: list[Check] | None = None
    ) -> None:
        super().__init__()
        self.ctx = ctx or Context.detect()
        self.checks = checks  # None: the registry, filtered per run
        if THEME in BUILTIN_THEMES:
            self.theme = THEME

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent(id="tabs"):
            with TabPane("Dashboard", id="tab-dashboard"):
                yield DashboardPane(self.ctx, self.checks)
            with TabPane("New project", id="tab-new-project"):
                yield NewProjectPane()
        yield Footer()

    def action_rerun(self, everything: bool) -> None:
        # `r` follows the Quick switch; `R` runs the slow checks too
        self.query_one(DashboardPane).run_checks(quick=False if everything else None)
        self.query_one(TabbedContent).active = "tab-dashboard"

    def action_new_project(self) -> None:
        self.query_one(TabbedContent).active = "tab-new-project"
        self.call_after_refresh(self._focus_name)

    def _focus_name(self) -> None:
        for widget in self.query("#np-name"):
            widget.focus()
