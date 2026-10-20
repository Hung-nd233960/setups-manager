"""TUI tests run the app headless through Textual's pilot; nothing touches the machine."""

from pathlib import Path

from conftest import make_ctx
from textual.widgets import Button, DataTable, Input, Select, Static, Switch

from setups_manager import newproject, projects, shell
from setups_manager.model import Fix, Result, Status
from setups_manager.newproject import Options
from setups_manager.registry import Check
from setups_manager.tui.app import SetupsApp
from setups_manager.tui.dashboard import DashboardPane
from setups_manager.tui.new_project import NewProjectPane
from setups_manager.tui.projects import ProfileScreen, ProjectsPane
from setups_manager.tui.widgets import ConfirmScreen, LogPanel


def make_checks(calls: list[str]) -> list[Check]:
    def fine(ctx):
        calls.append("fine")
        yield Result("all good", Status.OK)

    def stale(ctx):
        calls.append("stale")
        yield Result("old", Status.WARN, "detail here", Fix("Do it", ["tool"], True))
        yield Result("older", Status.ERROR)

    def broken(ctx):
        calls.append("broken")
        raise RuntimeError("boom")
        yield

    def slow(ctx):
        calls.append("slow")
        yield Result("slow one", Status.SKIP)

    return [
        Check("fine", "system", "fine check", fine),
        Check("stale", "setup", "stale check", stale),
        Check("broken", "repos", "broken check", broken),
        Check("slow", "updates", "slow check", slow, slow=True),
    ]


async def settle(app, pilot):
    await pilot.pause()
    await app.workers.wait_for_complete()
    await pilot.pause()


def rows(app) -> list[tuple[str, str]]:
    table = app.query_one("#checks-table", DataTable)
    return [
        (str(table.get_row_at(i)[1]), str(table.get_row_at(i)[2]))
        for i in range(table.row_count)
    ]


def text(app, selector: str) -> str:
    return str(app.query_one(selector, Static).render())


async def test_dashboard_rows_summary_and_rerun(tmp_path):
    calls: list[str] = []
    app = SetupsApp(make_ctx(tmp_path), make_checks(calls))
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(app, pilot)
        assert rows(app) == [
            ("fine", "all good"),
            ("stale", "old"),
            ("stale", "older"),
            ("broken", "broken check"),
        ]
        assert "1 ok · 1 warn · 2 error" in text(app, "#summary")
        assert "Done: 3 checks" in text(app, "#progress")
        assert sorted(calls) == ["broken", "fine", "stale"]  # slow one skipped (Quick)
        await pilot.press("r")
        await settle(app, pilot)
        assert sorted(calls) == ["broken", "broken", "fine", "fine", "stale", "stale"]
        await pilot.press("R")
        await settle(app, pilot)
        assert calls.count("slow") == 1
        assert ("slow", "slow one") in rows(app)
        assert "1 skip" in text(app, "#summary")


async def test_crashing_check_is_an_error_row_and_others_still_run(tmp_path):
    app = SetupsApp(make_ctx(tmp_path), make_checks([]))
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(app, pilot)
        table = app.query_one("#checks-table", DataTable)
        assert [row.value for row in table.rows] == [
            "fine:0",
            "stale:0",
            "stale:1",
            "broken:0",
        ]
        assert "error" in str(table.get_row("broken:0")[0])
        table.move_cursor(row=3)
        await pilot.pause()
        assert "boom" in text(app, "#detail")


async def test_detail_shows_fix(tmp_path):
    app = SetupsApp(make_ctx(tmp_path), make_checks([]))
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(app, pilot)
        app.query_one("#checks-table", DataTable).move_cursor(row=1)
        await pilot.pause()
        detail = text(app, "#detail")
        assert "detail here" in detail
        assert "Fix: Do it (asks first)" in detail
        assert "$ tool" in detail


OPTS = Options(
    types={"py": "Python", "report": "Report"},
    engines=["quarto", "typst"],
    default_engine="quarto",
    profiles=["Default", "Python", "Docs"],
    type_profiles={"py": "Python", "report": "Docs"},
    default_dir=Path("projects"),
    name_pattern=r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$",
    uv_types=frozenset({"py"}),
)


async def test_new_project_validation_engine_and_preview(tmp_path, monkeypatch):
    app = SetupsApp(make_ctx(tmp_path), [])
    monkeypatch.setattr(newproject, "load_options", lambda: OPTS)
    async with app.run_test(size=(120, 50)) as pilot:
        await settle(app, pilot)
        create = app.query_one("#np-create", Button)
        assert create.disabled
        name = app.query_one("#np-name", Input)
        name.value = "Bad Name"
        await pilot.pause()
        assert create.disabled
        assert "name must" in text(app, "#np-problems")
        name.value = "my-tool"
        await pilot.pause()
        assert not create.disabled
        assert text(app, "#np-problems") == ""
        assert text(app, "#np-preview") == "$ new-project py my-tool"
        assert app.query_one("#np-engine", Select).disabled

        app.query_one("#np-type", Select).value = "report"
        await pilot.pause()
        assert not app.query_one("#np-engine", Select).disabled
        # the profile followed the type to its default, so no --profile flag
        assert app.query_one("#np-profile", Select).value == "Docs"
        assert text(app, "#np-preview") == "$ new-project report my-tool"
        app.query_one("#np-engine", Select).value = "typst"
        app.query_one("#np-git", Switch).value = False
        await pilot.pause()
        assert text(app, "#np-preview") == (
            "$ new-project report my-tool --engine typst --no-git"
        )
        pane = app.query_one(NewProjectPane)
        assert pane.request is not None
        assert pane.request.engine == "typst"


async def test_new_project_create_streams_output(tmp_path, monkeypatch):
    seen = []

    def fake_stream(cmd, *, cwd=None):
        seen.append(cmd)
        yield "scaffolding"
        yield "exit 0"  # ordinary output, not the end
        yield shell.Exit(0)

    app = SetupsApp(make_ctx(tmp_path), [])
    monkeypatch.setattr(newproject, "load_options", lambda: OPTS)
    monkeypatch.setattr(shell, "stream", fake_stream)
    async with app.run_test(size=(120, 50)) as pilot:
        await settle(app, pilot)
        app.query_one("#np-name", Input).value = "fresh"
        app.query_one("#np-dir", Input).value = str(tmp_path / "out")
        await pilot.pause()
        app.query_one("#np-create", Button).press()
        await settle(app, pilot)
        assert seen == [["new-project", "py", "fresh", "--dir", str(tmp_path / "out")]]
        log = " | ".join(app.query_one("#np-log", LogPanel).history)
        assert "scaffolding" in log
        assert "exit 0" in log
        assert text(app, "#np-result").startswith("Created ")
        assert app.query_one("#np-open-btn").has_class("shown")


async def test_new_project_failure_keeps_form(tmp_path, monkeypatch):
    monkeypatch.setattr(
        shell, "stream", lambda cmd, **kw: iter(["oops", shell.Exit(2)])
    )
    app = SetupsApp(make_ctx(tmp_path), [])
    monkeypatch.setattr(newproject, "load_options", lambda: OPTS)
    async with app.run_test(size=(120, 50)) as pilot:
        await settle(app, pilot)
        app.query_one("#np-name", Input).value = "fresh"
        await pilot.pause()
        app.query_one("#np-create", Button).press()
        await settle(app, pilot)
        assert "failed (exit 2)" in text(app, "#np-result")
        assert app.query_one("#np-name", Input).value == "fresh"
        assert not app.query_one("#np-create", Button).disabled


async def test_new_project_not_installed(tmp_path, monkeypatch):
    app = SetupsApp(make_ctx(tmp_path), [])
    monkeypatch.setattr(newproject, "load_options", lambda: None)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(app, pilot)
        assert "not installed" in text(app, "#np-missing")
        assert not app.query("#np-name")


async def test_confirm_screen_returns_choice(tmp_path):
    app = SetupsApp(make_ctx(tmp_path), [])
    results = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        app.push_screen(ConfirmScreen("Sure?", "$ tool"), results.append)
        await pilot.pause()
        await pilot.click("#confirm-ok")
        await pilot.pause()
        app.push_screen(ConfirmScreen("Sure?"), results.append)
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
    assert results == [True, False]


def fix_checks(calls: list[str], state: dict) -> list[Check]:
    """One check that warns until its fix has run, one whose fix asks first."""

    def tidy(ctx):
        calls.append("tidy")
        if state.get("fixed"):
            yield Result("tidy now", Status.OK)
        else:
            yield Result(
                "untidy", Status.WARN, "mess", Fix("Tidy up", ["tidy-tool", "--go"])
            )

    def risky(ctx):
        yield Result(
            "unpushed", Status.WARN, fix=Fix("Push it", ["git", "push"], confirm=True)
        )

    def manual(ctx):
        yield Result("by hand", Status.WARN, fix=Fix("Edit the file"))

    return [
        Check("tidy", "system", "tidy check", tidy),
        Check("risky", "setup", "risky check", risky),
        Check("manual", "python", "manual check", manual),
    ]


async def test_fix_runs_streams_and_rechecks(tmp_path, monkeypatch):
    calls: list[str] = []
    state: dict = {}
    seen = []

    def fake_stream(cmd, *, cwd=None):
        seen.append(cmd)
        state["fixed"] = True
        yield "tidying"
        yield shell.Exit(0)

    monkeypatch.setattr(shell, "stream", fake_stream)
    app = SetupsApp(make_ctx(tmp_path), fix_checks(calls, state))
    async with app.run_test(size=(120, 50)) as pilot:
        await settle(app, pilot)
        table = app.query_one("#checks-table", DataTable)
        table.focus()
        table.move_cursor(row=0)
        await pilot.pause()
        assert app.query_one("#fix-btn", Button).display
        await pilot.press("f")  # no confirmation for a plain fix
        await settle(app, pilot)
        assert seen == [["tidy-tool", "--go"]]
        log = " | ".join(app.query_one("#fix-log", LogPanel).history)
        assert "tidying" in log
        assert "fix exited 0" in text(app, "#fix-status")
        assert calls == ["tidy", "tidy"]  # only the owning check was re-run
        assert rows(app)[0] == ("tidy", "tidy now")
        assert "1 ok · 2 warn" in text(app, "#summary")


async def test_confirm_fix_cancelled_runs_nothing(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(
        shell, "stream", lambda cmd, **kw: seen.append(cmd) or iter([shell.Exit(0)])
    )
    app = SetupsApp(make_ctx(tmp_path), fix_checks([], {}))
    async with app.run_test(size=(120, 50)) as pilot:
        await settle(app, pilot)
        table = app.query_one("#checks-table", DataTable)
        table.focus()
        table.move_cursor(row=1)
        await pilot.pause()
        await pilot.press("f")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmScreen)
        assert "$ git push" in str(app.screen.query_one("#confirm-detail").render())
        await pilot.click("#confirm-cancel")
        await settle(app, pilot)
        assert seen == []
        assert not app.query_one(DashboardPane).fixing

        await pilot.press("f")
        await pilot.pause()
        await pilot.click("#confirm-ok")
        await settle(app, pilot)
        assert seen == [["git", "push"]]


async def test_manual_fix_has_no_run_button_and_second_fix_is_blocked(
    tmp_path, monkeypatch
):
    seen = []
    monkeypatch.setattr(
        shell, "stream", lambda cmd, **kw: seen.append(cmd) or iter([shell.Exit(0)])
    )
    app = SetupsApp(make_ctx(tmp_path), fix_checks([], {}))
    async with app.run_test(size=(120, 50)) as pilot:
        await settle(app, pilot)
        table = app.query_one("#checks-table", DataTable)
        table.focus()
        table.move_cursor(row=2)
        await pilot.pause()
        assert "Fix: Edit the file" in text(app, "#detail")
        assert not app.query_one("#fix-btn", Button).display
        await pilot.press("f")
        await settle(app, pilot)
        assert seen == []

        table.move_cursor(row=0)
        await pilot.pause()
        pane = app.query_one(DashboardPane)
        pane.fixing = True  # as if a fix were running
        await pilot.press("f")
        await settle(app, pilot)
        assert seen == []
        pane._update_fix_button(pane.selected_target())
        assert app.query_one("#fix-btn", Button).disabled


def make_project(ctx, name, profile=None):
    folder = ctx.projects / name
    folder.mkdir(parents=True)
    if profile:
        (folder / ".vscode").mkdir()
        (folder / ".vscode" / "profile").write_text(profile + "\n")
    return folder


def project_rows(app) -> list[tuple[str, ...]]:
    table = app.query_one("#projects-table", DataTable)
    return [tuple(str(c) for c in table.get_row_at(i)) for i in range(table.row_count)]


async def test_projects_tab_lists_folders(tmp_path):
    ctx = make_ctx(tmp_path)
    make_project(ctx, "alpha", "Python")
    make_project(ctx, "beta")
    app = SetupsApp(ctx, [])
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(app, pilot)
        # no git repos here: no branch, no counts
        assert project_rows(app) == [
            ("alpha", "Python", "—", "—", "—", "—"),
            ("beta", "—", "—", "—", "—", "—"),
        ]
        assert "2 projects" in text(app, "#projects-status")


async def test_projects_open_and_refresh(tmp_path, monkeypatch):
    ctx = make_ctx(tmp_path)
    folder = make_project(ctx, "alpha")
    opened = []

    def fake_open(path):
        opened.append(path)
        return shell.Output(0, "", "")

    monkeypatch.setattr(projects, "open_project", fake_open)
    app = SetupsApp(ctx, [])
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(app, pilot)
        app.query_one("#projects-table", DataTable).focus()
        await pilot.press("o")
        await settle(app, pilot)
        assert opened == [folder]
        assert "Opened alpha" in text(app, "#projects-status")
        make_project(ctx, "gamma")
        await pilot.press("g")
        await settle(app, pilot)
        assert [r[0] for r in project_rows(app)] == ["alpha", "gamma"]


async def test_projects_set_profile_flow(tmp_path, monkeypatch):
    ctx = make_ctx(tmp_path)
    folder = make_project(ctx, "alpha", "Python")
    seen = []

    def fake_set(path, profile):
        seen.append((path, profile))
        (path / ".vscode" / "profile").write_text(profile + "\n")
        yield "marker written"
        yield shell.Exit(0)

    monkeypatch.setattr(newproject, "load_options", lambda: OPTS)
    monkeypatch.setattr(projects, "set_profile", fake_set)
    app = SetupsApp(ctx, [])
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(app, pilot)
        app.query_one("#projects-table", DataTable).focus()

        await pilot.press("p")  # cancel first: nothing changes
        await settle(app, pilot)
        assert isinstance(app.screen, ProfileScreen)
        assert app.screen.query_one("#profile-select", Select).value == "Python"
        await pilot.click("#profile-cancel")
        await settle(app, pilot)
        assert seen == []
        assert not app.query_one(ProjectsPane).busy

        await pilot.press("p")
        await settle(app, pilot)
        app.screen.query_one("#profile-select", Select).value = "Docs"
        await pilot.click("#profile-ok")
        await settle(app, pilot)
        assert seen == [(folder, "Docs")]
        assert "marker written" in app.query_one("#projects-log", LogPanel).history
        status = text(app, "#projects-status")
        assert "profile set to Docs" in status
        assert "setup.py" in status  # the reminder survives the table reload
        assert project_rows(app)[0][1] == "Docs"


async def test_projects_set_profile_without_new_project(tmp_path, monkeypatch):
    ctx = make_ctx(tmp_path)
    make_project(ctx, "alpha")
    monkeypatch.setattr(newproject, "load_options", lambda: None)
    app = SetupsApp(ctx, [])
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(app, pilot)
        app.query_one("#projects-table", DataTable).focus()
        await pilot.press("p")
        await settle(app, pilot)
        assert "not installed" in text(app, "#projects-status")
        assert not isinstance(app.screen, ProfileScreen)
