"""Run external commands without raising: a missing tool or a timeout is just an outcome."""

import shutil
import subprocess
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
