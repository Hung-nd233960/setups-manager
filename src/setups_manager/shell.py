"""Run external commands without raising: a missing tool or a timeout is just an outcome."""

import shutil
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

NOT_FOUND = 127
TIMED_OUT = 124


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


@dataclass(frozen=True)
class Exit:
    """The last item `stream` yields: the exit code (127 when the tool is missing)."""

    code: int


def stream(cmd: list[str], *, cwd: Path | None = None) -> Iterator[str | Exit]:
    """Yield output lines (stdout and stderr merged) as they arrive, then one `Exit`.

    The end is a typed item, not a text line, so no output can be mistaken for it.
    """
    exe = shutil.which(cmd[0])
    if exe is None:
        yield f"{cmd[0]}: not found"
        yield Exit(NOT_FOUND)
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
        yield Exit(NOT_FOUND)
        return
    assert proc.stdout is not None
    with proc:
        for line in proc.stdout:
            yield line.rstrip("\r\n")
    yield Exit(proc.returncode)
