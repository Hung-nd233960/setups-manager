import sys

from setups_manager import shell


def test_stream_yields_lines_then_exit():
    lines = list(shell.stream([sys.executable, "-c", "print('a'); print('b')"]))
    assert lines == ["a", "b", shell.Exit(0)]


def test_stream_output_that_looks_like_an_exit_is_just_a_line():
    lines = list(shell.stream([sys.executable, "-c", "print('exit 0')"]))
    assert lines == ["exit 0", shell.Exit(0)]


def test_stream_merges_stderr_and_reports_failure():
    code = "import sys; print('out'); print('err', file=sys.stderr); sys.exit(3)"
    lines = list(shell.stream([sys.executable, "-c", code]))
    assert set(lines[:-1]) == {"out", "err"}
    assert lines[-1] == shell.Exit(3)


def test_stream_missing_tool():
    lines = list(shell.stream(["definitely-not-a-real-tool-xyz"]))
    assert lines[-1] == shell.Exit(shell.NOT_FOUND)
    assert "not found" in str(lines[0])
