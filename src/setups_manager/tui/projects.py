"""Projects tab: every project folder with its VS Code profile and git state."""

from pathlib import Path
from typing import ClassVar

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Label, Select, Static

from setups_manager import newproject, projects, shell
from setups_manager.context import Context
from setups_manager.newproject import Options
from setups_manager.tui.widgets import LogPanel

NONE = "—"
PROFILE_NOTE = (
    "VS Code links the folder the next time setup.py runs with VS Code closed, "
    "or right away when you open it with o."
)


class ProfileScreen(ModalScreen[str | None]):
    """Pick a VS Code profile; dismisses with the name, or None when cancelled."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "cancel", "Cancel")]

    def __init__(self, project: str, profiles: list[str], current: str | None) -> None:
        super().__init__()
        self.project = project
        self.profiles = profiles
        self.current = current if current in profiles else profiles[0]

    def compose(self) -> ComposeResult:
        with Vertical(id="profile-box"):
            yield Label(f"VS Code profile for {self.project}", markup=False)
            yield Select(
                [(p, p) for p in self.profiles],
                allow_blank=False,
                value=self.current,
                id="profile-select",
            )
            with Horizontal(id="profile-buttons"):
                yield Button("Cancel", id="profile-cancel")
                yield Button("Set profile", id="profile-ok", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "profile-ok":
            self.dismiss(str(self.query_one("#profile-select", Select).value))
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ProjectsPane(Vertical):
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("o", "open_project", "Open in VS Code"),
        Binding("p", "set_profile", "Set profile"),
        Binding("g", "reload", "Refresh"),
    ]

    def __init__(self, ctx: Context) -> None:
        super().__init__(id="projects")
        self.ctx = ctx
        self.busy = False  # one profile change or open at a time
        self._keep_status = False  # the next reload must not hide a message
        self._found: dict[str, projects.Project] = {}

    def compose(self) -> ComposeResult:
        yield DataTable(id="projects-table", cursor_type="row", zebra_stripes=True)
        yield Static("", id="projects-status", markup=False)
        yield LogPanel(id="projects-log")

    def on_mount(self) -> None:
        table = self.query_one("#projects-table", DataTable)
        table.add_column("Project", width=24)
        table.add_column("Profile", width=14)
        table.add_column("Branch", width=12)
        table.add_column("Uncommitted", width=12)
        table.add_column("Unpushed", width=9)
        table.add_column("Last commit")
        self.action_reload()

    # -- loading ----------------------------------------------------------

    def action_reload(self) -> None:
        self._status("Reading projects…")
        self._load()

    @work(thread=True, exclusive=True, group="load")
    def _load(self) -> None:
        found = projects.list_projects(self.ctx)
        self.app.call_from_thread(self._loaded, found)

    def _loaded(self, found: list[projects.Project]) -> None:
        table = self.query_one("#projects-table", DataTable)
        row = table.cursor_row
        table.clear()
        self._found = {}
        for p in found:
            key = str(p.path)
            self._found[key] = p
            table.add_row(
                p.name,
                p.profile or NONE,
                p.branch or NONE,
                str(p.dirty) if p.branch else NONE,
                NONE if p.ahead is None else str(p.ahead),
                p.last_commit or NONE,
                key=key,
            )
        if table.row_count:
            table.move_cursor(row=min(row, table.row_count - 1))
        if self._keep_status:
            self._keep_status = False
        else:
            self._status(f"{len(found)} projects in {self.ctx.projects}")

    def _status(self, text: str) -> None:
        self.query_one("#projects-status", Static).update(text)

    def selected(self) -> projects.Project | None:
        table = self.query_one("#projects-table", DataTable)
        if not table.row_count:
            return None
        key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
        return self._found.get(key or "")

    # -- open in VS Code --------------------------------------------------

    def action_open_project(self) -> None:
        project = self.selected()
        if project is None or self.busy:
            return
        self.busy = True
        self._status(f"Opening {project.name} in VS Code…")
        self._open(project.path)

    @work(thread=True, exclusive=True, group="act")
    def _open(self, path: Path) -> None:
        out = projects.open_project(path)
        message = (
            f"Opened {path.name} in VS Code."
            if out.ok
            else f"vsc failed: {out.err.strip() or out.out.strip()}"
        )
        self.app.call_from_thread(self._finished, message, False)

    # -- set profile ------------------------------------------------------

    def action_set_profile(self) -> None:
        project = self.selected()
        if project is None or self.busy:
            return
        self.busy = True
        self._status("Reading the profile list…")
        self._load_profiles(project)

    @work(thread=True, exclusive=True, group="act")
    def _load_profiles(self, project: projects.Project) -> None:
        opts = newproject.load_options()  # new-project owns the profile names
        self.app.call_from_thread(self._ask_profile, project, opts)

    def _ask_profile(self, project: projects.Project, opts: Options | None) -> None:
        if opts is None:
            self._finished("new-project is not installed, so profiles are unknown.")
            return

        def chosen(profile: str | None) -> None:
            if profile is None:
                self._finished("Profile change cancelled.")
            else:
                self._status(f"Setting {project.name} to {profile}…")
                self._run_set_profile(project, profile)

        self.app.push_screen(
            ProfileScreen(project.name, opts.profiles, project.profile), chosen
        )

    @work(thread=True, exclusive=True, group="act")
    def _run_set_profile(self, project: projects.Project, profile: str) -> None:
        log = self.query_one("#projects-log", LogPanel)
        self.app.call_from_thread(log.clear)
        code = 1
        for item in projects.set_profile(project.path, profile):
            if isinstance(item, shell.Exit):
                code = item.code
            else:
                self.app.call_from_thread(log.add_line, item)
        message = (
            f"{project.name}: profile set to {profile}. {PROFILE_NOTE}"
            if code == 0
            else f"{project.name}: vsc --set failed (exit {code})."
        )
        self.app.call_from_thread(self._finished, message, code == 0)

    def _finished(self, message: str, reload: bool = False) -> None:
        self.busy = False
        self._status(message)
        if reload:
            self._keep_status = True  # only the table changes
            self._load()
