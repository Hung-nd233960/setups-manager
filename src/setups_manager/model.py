"""What a check reports: a status, a one-line title and, when something is off, a fix."""

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
