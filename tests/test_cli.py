import json

from setups_manager.cli import main
from setups_manager.model import Fix, Result, Status
from setups_manager.registry import check


def register_fakes():
    @check("fine", "system", "always ok")
    def fine(ctx):
        yield Result("all good", Status.OK)

    @check("stale", "setup", "always warns")
    def stale(ctx):
        yield Result(
            "out of date",
            Status.WARN,
            "detail line",
            Fix("Do it", ["tool", "--fix"], confirm=True),
        )


def test_list_shows_every_real_check(capsys):
    assert main(["list"]) == 0
    out = capsys.readouterr().out
    for check_id in ("disk", "links", "claude", "vscode", "repos"):
        assert check_id in out


def test_check_json_shape_and_exit_code(registry, capsys):
    register_fakes()
    assert main(["check", "--json"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["summary"] == {"ok": 1, "warn": 1, "error": 0, "skip": 0}
    stale = report["results"][1]
    assert stale["check"] == "stale"
    assert stale["status"] == "warn"
    assert stale["fix"] == {
        "label": "Do it",
        "command": ["tool", "--fix"],
        "confirm": True,
    }


def test_check_text_shows_fix_and_passes_when_all_ok(registry, capsys):
    register_fakes()
    main(["check"])
    out = capsys.readouterr().out
    assert "fix: Do it (asks first)" in out
    assert "$ tool --fix" in out
    assert main(["check", "--only", "fine"]) == 0
