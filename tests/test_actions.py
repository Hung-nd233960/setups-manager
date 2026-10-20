import sys

import pytest
from setups_manager import actions, shell
from setups_manager.model import Fix, Result, Status


def results():
    return [
        Result("fine", Status.OK, check="a"),
        Result("manual", Status.WARN, fix=Fix("Do by hand"), check="a"),
        Result("auto", Status.WARN, fix=Fix("Run", ["tool"]), check="a"),
        Result("ok with fix", Status.OK, fix=Fix("Run", ["tool"]), check="b"),
        Result("bad", Status.ERROR, fix=Fix("Run", ["x"], confirm=True), check="b"),
    ]


def test_fixable_keeps_only_runnable_fixes_with_dashboard_keys():
    targets = actions.fixable(results())
    assert [(t.key, t.result.title) for t in targets] == [
        ("a:2", "auto"),
        ("b:1", "bad"),
    ]


def test_run_fix_streams_lines_then_exit():
    fix = Fix("Say", [sys.executable, "-c", "print('fixed')"])
    [target] = actions.fixable([Result("t", Status.WARN, fix=fix, check="c")])
    items = list(actions.run_fix(target))
    assert items[0] == "fixed"
    assert isinstance(items[-1], shell.Exit)
    assert items[-1].code == 0


def test_run_fix_without_command_is_refused():
    target = actions.FixTarget("c:0", Result("t", Status.WARN, fix=Fix("Manual")))
    with pytest.raises(ValueError):
        actions.run_fix(target)
