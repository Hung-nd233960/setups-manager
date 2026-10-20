"""Widgets shared by the tabs."""

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, RichLog


class LogPanel(RichLog):
    """Scrolling plain-text log for streamed command output."""

    def __init__(self, **kwargs) -> None:
        super().__init__(wrap=True, markup=False, highlight=False, **kwargs)
        self.history: list[str] = []  # plain text of everything added (for tests)

    def add_line(self, line: str) -> None:
        self.history.append(line)
        self.write(line)


class ConfirmScreen(ModalScreen[bool]):
    """Ask before something destructive; dismisses with True (confirm) or False."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "cancel", "Cancel")]

    def __init__(self, message: str, detail: str = "") -> None:
        super().__init__()
        self.message = message
        self.detail = detail

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-box"):
            yield Label(self.message, id="confirm-message", markup=False)
            if self.detail:
                yield Label(self.detail, id="confirm-detail", markup=False)
            with Horizontal(id="confirm-buttons"):
                yield Button("Cancel", id="confirm-cancel")
                yield Button("Confirm", id="confirm-ok", variant="warning")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm-ok")

    def action_cancel(self) -> None:
        self.dismiss(False)
