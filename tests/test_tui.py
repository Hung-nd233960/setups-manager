"""TUI tests run the app headless through Textual's pilot; nothing touches the machine."""

from pathlib import Path

from conftest import make_ctx
from setups_manager import newproject, shell
from setups_manager.model import Fix, Result, Status
from setups_manager.newproject import Options
from setups_manager.registry import Check
from setups_manager.tui.app import SetupsApp
from setups_manager.tui.new_project import NewProjectPane
from setups_manager.tui.widgets import ConfirmScreen, LogPanel
from textual.widgets import Button, DataTable, Input, Select, Static, Switch


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
        log = " | ".join(app.query_one(LogPanel).history)
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
