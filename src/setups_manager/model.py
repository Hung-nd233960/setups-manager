"""What a check reports: a status, a one-line title and, when something is off, a fix."""

from collections import Counter
from dataclasses import asdict, dataclass
from enum import StrEnum


class Status(StrEnum):
    OK = "ok"
    WARN = "warn"  # something to look at; the machine still works
    ERROR = "error"  # the check itself could not run properly
    SKIP = "skip"  # does not apply here (tool not installed, folder absent)

    @property
    def needs_attention(self) -> bool:
        return self in (Status.WARN, Status.ERROR)


@dataclass(frozen=True)
class Fix:
    """How to resolve a result. Without a command, only the user can (label says how)."""

    label: str
    command: list[str] | None = None
    confirm: bool = False  # destructive or outward-facing: ask before running


@dataclass(frozen=True)
class Result:
    title: str
    status: Status
    detail: str = ""
    fix: Fix | None = None
    check: str = ""  # id of the check that produced it, filled in by the runner

    def to_dict(self) -> dict:
        return asdict(self) | {"status": str(self.status)}


def row_key(result: Result, index: int) -> str:
    """Stable id of a result: its check and its position among that check's results.

    The dashboard rows and `setups fix <key>` use the same key.
    """
    return f"{result.check}:{index}"


def keyed(results: list[Result]) -> list[tuple[str, Result]]:
    """Each result with its `row_key`, counting positions per check."""
    seen: Counter[str] = Counter()
    out = []
    for r in results:
        out.append((row_key(r, seen[r.check]), r))
        seen[r.check] += 1
    return out
