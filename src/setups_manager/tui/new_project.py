"""New project tab: a form over `new-project`, with a live preview of the command."""

import subprocess
from pathlib import Path

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.validation import Regex
from textual.widgets import Button, Input, Label, Select, Static, Switch

from setups_manager import newproject, shell
from setups_manager.newproject import Options, Request
from setups_manager.tui.widgets import LogPanel

INSTALL_HINT = (
    "new-project is not installed (or too old for --options-json).\n"
    "Install it from the Setups repo:\n"
    "  uv tool install --editable common\\tools\\new-project --force"
)


def labelled(text: str, widget, *, classes: str = "np-row") -> Horizontal:
    return Horizontal(Label(text), widget, classes=classes)


class NewProjectPane(VerticalScroll):
    def __init__(self) -> None:
        super().__init__(id="new-project")
        self.opts: Options | None = None
        self.running = False
        self.created: Path | None = None
        self.request: Request | None = None
        self.problems: list[str] = []
        self._profile_touched = False

    def compose(self) -> ComposeResult:
        yield Static("Loading new-project options…", id="np-loading", markup=False)

    def on_mount(self) -> None:
        self._load_options()

    @work(thread=True)
    def _load_options(self) -> None:
        opts = newproject.load_options()
        self.app.call_from_thread(self._show, opts)

    async def _show(self, opts: Options | None) -> None:
        self.opts = opts
        await self.remove_children()
        if opts is None:
            await self.mount(Static(INSTALL_HINT, id="np-missing", markup=False))
            return
        first_type = next(iter(opts.types))
        await self.mount(
            labelled(
                "Type",
                Select(
                    [(f"{k} - {v}", k) for k, v in opts.types.items()],
                    allow_blank=False,
                    value=first_type,
                    id="np-type",
                ),
            ),
            labelled(
                "Name",
                Input(
                    placeholder="e.g. ecg-hrv",
                    validators=[Regex(opts.name_pattern)],
                    id="np-name",
                ),
            ),
            labelled(
                "Engine",
                Select(
                    [(e, e) for e in opts.engines],
                    allow_blank=False,
                    value=opts.default_engine,
                    disabled=True,
                    id="np-engine",
                ),
            ),
            labelled(
                "VS Code profile",
                Select(
                    [(p, p) for p in opts.profiles],
                    allow_blank=False,
                    value=opts.type_profiles.get(first_type, opts.profiles[0]),
                    id="np-profile",
                ),
            ),
            labelled("Description", Input(placeholder="one line", id="np-description")),
            labelled(
                "Directory", Input(placeholder=str(opts.default_dir), id="np-dir")
            ),
            Horizontal(
                Label("git"),
                Switch(True, id="np-git"),
                Label("uv sync"),
                Switch(True, id="np-sync"),
                Label("open in VS Code"),
                Switch(False, id="np-open"),
                classes="np-switches",
            ),
            Static("", id="np-preview", markup=False),
            Static("", id="np-problems", markup=False),
            Horizontal(
                Button("Create", id="np-create", variant="primary", disabled=True),
                Button("Open in VS Code", id="np-open-btn"),
                id="np-buttons",
            ),
            Static("", id="np-result", markup=False),
            LogPanel(id="np-log"),
        )
        self._update()

    # -- reading the form -------------------------------------------------

    def _default_profile(self, type_: str) -> str | None:
        return self.opts.type_profiles.get(type_) if self.opts else None

    def build_request(self) -> Request:
        assert self.opts is not None
        type_ = str(self.query_one("#np-type", Select).value)
        engine = str(self.query_one("#np-engine", Select).value)
        profile = str(self.query_one("#np-profile", Select).value)
        directory = self.query_one("#np-dir", Input).value.strip()
        uv_type = type_ in newproject.UV_TYPES
        return Request(
            type=type_,
            name=self.query_one("#np-name", Input).value.strip(),
            directory=Path(directory) if directory else None,
            description=self.query_one("#np-description", Input).value.strip(),
            engine=engine
            if type_ == "report" and engine != self.opts.default_engine
            else None,
            profile=profile if profile != self._default_profile(type_) else None,
            git=self.query_one("#np-git", Switch).value,
            sync=self.query_one("#np-sync", Switch).value or not uv_type,
            open=self.query_one("#np-open", Switch).value,
        )

    def _update(self) -> None:
        if self.opts is None or not self.query("#np-create"):
            return
        req = self.build_request()
        self.request = req
        self.problems = newproject.validate(req, self.opts)
        self.query_one("#np-preview", Static).update(
            "$ " + subprocess.list2cmdline(newproject.command(req))
        )
        self.query_one("#np-problems", Static).update(
            "\n".join(f"- {p}" for p in self.problems)
        )
        self.query_one("#np-create", Button).disabled = (
            bool(self.problems) or self.running
        )

    # -- reacting to changes ----------------------------------------------

    @on(Select.Changed, "#np-type")
    def _type_changed(self, event: Select.Changed) -> None:
        type_ = str(event.value)
        self.query_one("#np-engine", Select).disabled = type_ != "report"
        self.query_one("#np-sync", Switch).disabled = type_ not in newproject.UV_TYPES
        default = self._default_profile(type_)
        if default and not self._profile_touched:
            self.query_one("#np-profile", Select).value = default
        self._update()

    @on(Select.Changed, "#np-profile")
    def _profile_changed(self, event: Select.Changed) -> None:
        # the user has chosen their own profile once it differs from the type's default
        type_ = str(self.query_one("#np-type", Select).value)
        self._profile_touched = str(event.value) != self._default_profile(type_)
        self._update()

    @on(Select.Changed, "#np-engine")
    @on(Input.Changed)
    @on(Switch.Changed)
    def _field_changed(self) -> None:
        self._update()

    # -- creating ---------------------------------------------------------

    @on(Button.Pressed, "#np-create")
    def _create_pressed(self) -> None:
        if self.running or self.problems or self.opts is None:
            return
        req = self.build_request()
        self.running = True
        self.created = None
        self.query_one("#np-result", Static).update("")
        self.query_one("#np-open-btn", Button).remove_class("shown")
        log = self.query_one("#np-log", LogPanel)
        log.clear()
        log.add_line("$ " + subprocess.list2cmdline(newproject.command(req)))
        self._update()
        self._run_create(newproject.command(req), newproject.target(req, self.opts))

    @work(thread=True, exclusive=True)
    def _run_create(self, cmd: list[str], path: Path) -> None:
        log = self.query_one("#np-log", LogPanel)
        code = 1
        for line in shell.stream(cmd):
            exit_code = shell.exit_code(line)
            if exit_code is None:
                self.app.call_from_thread(log.add_line, line)
            else:
                code = exit_code
        self.app.call_from_thread(self._create_finished, code, path)

    def _create_finished(self, code: int, path: Path) -> None:
        self.running = False
        result = self.query_one("#np-result", Static)
        if code == 0:
            self.created = path
            result.update(f"Created {path}")
            self.query_one("#np-open-btn", Button).add_class("shown")
        else:
            result.update(f"new-project failed (exit {code}); the form is unchanged.")
        self._update()

    @on(Button.Pressed, "#np-open-btn")
    def _open_pressed(self) -> None:
        if self.created is not None:
            self._open_in_vscode(self.created)

    @work(thread=True)
    def _open_in_vscode(self, path: Path) -> None:
        out = shell.run(["vsc", str(path)])
        if not out.ok:
            message = f"vsc failed: {out.err.strip() or out.out.strip()}"
            self.app.call_from_thread(
                self.query_one("#np-result", Static).update, message
            )
