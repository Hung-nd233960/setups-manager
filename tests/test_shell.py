import sys

from setups_manager import shell


def test_stream_yields_lines_then_exit_sentinel():
    lines = list(shell.stream([sys.executable, "-c", "print('a'); print('b')"]))
    assert lines == ["a", "b", "exit 0"]
    assert shell.exit_code(lines[-1]) == 0
    assert shell.exit_code("a") is None


def test_stream_merges_stderr_and_reports_failure():
    code = "import sys; print('out'); print('err', file=sys.stderr); sys.exit(3)"
    lines = list(shell.stream([sys.executable, "-c", code]))
    assert set(lines[:-1]) == {"out", "err"}
    assert shell.exit_code(lines[-1]) == 3


def test_stream_missing_tool():
    lines = list(shell.stream(["definitely-not-a-real-tool-xyz"]))
    assert lines[-1] == "exit 127"
    assert "not found" in lines[0]
