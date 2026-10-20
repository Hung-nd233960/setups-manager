import json
import sys

import pytest

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


def test_check_commands_do_not_import_textual():
    import subprocess
    import sys

    code = (
        "import sys; from setups_manager.cli import main; "
        "from setups_manager.registry import REGISTRY; main(['list']); "
        "REGISTRY.clear(); main(['fix', '--list']); "  # empty: no real checks run
        "print(any(m.startswith('textual') for m in sys.modules))"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert out.stdout.strip().endswith("False")


def register_fixable():
    py = sys.executable

    @check("stale", "setup", "always warns")
    def stale(ctx):
        yield Result("fine here", Status.OK)
        yield Result("plain", Status.WARN, fix=Fix("Say", [py, "-c", "print('fixed')"]))
        yield Result(
            "risky",
            Status.WARN,
            fix=Fix("Say twice", [py, "-c", "print('twice')"], confirm=True),
        )
        yield Result("manual", Status.WARN, fix=Fix("By hand"))


def test_fix_list_shows_keys_and_skips_manual_fixes(registry, capsys):
    register_fixable()
    assert main(["fix", "--list"]) == 0
    out = capsys.readouterr().out
    assert "stale:1  plain" in out
    assert "stale:2  risky" in out
    assert "(asks first)" in out
    assert "manual" not in out


def test_fix_runs_plain_fix_and_rechecks(registry, capsys):
    register_fixable()
    assert main(["fix", "stale:1"]) == 0
    out = capsys.readouterr().out
    assert "fixed" in out
    assert "exit 0" in out
    assert "== setup" in out  # the re-check output


def test_fix_confirm_needs_yes_and_runs_nothing_without_it(registry, capsys):
    register_fixable()
    assert main(["fix", "stale:1", "stale:2"]) == 2
    out = capsys.readouterr().out
    assert "nothing was run" in out
    assert "fixed" not in out
    assert main(["fix", "stale:2", "--yes"]) == 0
    assert "twice" in capsys.readouterr().out


def test_fix_unknown_or_manual_key_exits_2(registry, capsys):
    register_fixable()
    assert main(["fix", "stale:3"]) == 2  # manual fix: shown, never run
    assert main(["fix", "stale:9"]) == 2
    assert "No automatic fix" in capsys.readouterr().err
    with pytest.raises(SystemExit) as e:
        main(["fix", "nosuch:0"])
    assert e.value.code == 2


def test_fix_failing_command_exits_1(registry, capsys):
    @check("bad", "setup", "fails")
    def bad(ctx):
        yield Result("t", Status.WARN, fix=Fix("Fail", [sys.executable, "-c", "exit(3)"]))

    assert main(["fix", "bad:0"]) == 1
    assert "exit 3" in capsys.readouterr().out
