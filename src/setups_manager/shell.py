"""Run external commands without raising: a missing tool or a timeout is just an outcome."""

import shutil
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

NOT_FOUND = 127
TIMED_OUT = 124
EXIT_PREFIX = "exit "


@dataclass(frozen=True)
class Output:
    code: int
    out: str
    err: str

    @property
    def ok(self) -> bool:
        return self.code == 0

    @property
    def missing(self) -> bool:
        return self.code == NOT_FOUND


def run(cmd: list[str], *, cwd: Path | None = None, timeout: float = 120) -> Output:
    # which() also finds .cmd/.bat shims on Windows (npm, code) that a bare name misses
    exe = shutil.which(cmd[0])
    if exe is None:
        return Output(NOT_FOUND, "", f"{cmd[0]}: not found")
    try:
        done = subprocess.run(
            [exe, *cmd[1:]],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return Output(TIMED_OUT, "", f"{cmd[0]}: no answer after {timeout:.0f} s")
    except OSError as e:
        return Output(NOT_FOUND, "", f"{cmd[0]}: {e}")
    return Output(done.returncode, done.stdout, done.stderr)


def stream(cmd: list[str], *, cwd: Path | None = None) -> Iterator[str]:
    """Yield output lines (stdout and stderr merged) as they arrive.

    The last item is always the sentinel line ``exit <code>`` (127 when the tool is
    missing). Use `exit_code` to read it.
    """
    exe = shutil.which(cmd[0])
    if exe is None:
        yield f"{cmd[0]}: not found"
        yield f"{EXIT_PREFIX}{NOT_FOUND}"
        return
    try:
        proc = subprocess.Popen(
            [exe, *cmd[1:]],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
    except OSError as e:
        yield f"{cmd[0]}: {e}"
        yield f"{EXIT_PREFIX}{NOT_FOUND}"
        return
    assert proc.stdout is not None
    with proc:
        for line in proc.stdout:
            yield line.rstrip("\r\n")
    yield f"{EXIT_PREFIX}{proc.returncode}"


def exit_code(line: str) -> int | None:
    """The exit code if `line` is the sentinel that ends `stream`, else None."""
    if line.startswith(EXIT_PREFIX) and line[len(EXIT_PREFIX) :].lstrip("-").isdigit():
        return int(line[len(EXIT_PREFIX) :])
    return None
