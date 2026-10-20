"""The check registry. Check modules register their functions with @check."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from setups_manager.context import Context
from setups_manager.model import Result

GROUPS = ("system", "setup", "python", "repos", "updates")
ALL_PLATFORMS = ("win32", "linux")

type CheckFn = Callable[[Context], Iterable[Result]]


@dataclass(frozen=True)
class Check:
    id: str
    group: str
    description: str
    fn: CheckFn
    slow: bool = False  # walks big folders or goes online
    platforms: tuple[str, ...] = ALL_PLATFORMS


REGISTRY: dict[str, Check] = {}


def check(
    id: str,
    group: str,
    description: str,
    *,
    slow: bool = False,
    platforms: tuple[str, ...] = ALL_PLATFORMS,
) -> Callable[[CheckFn], CheckFn]:
    if group not in GROUPS:
        raise ValueError(f"unknown group {group!r}")

    def register(fn: CheckFn) -> CheckFn:
        if id in REGISTRY:
            raise ValueError(f"check {id!r} registered twice")
        REGISTRY[id] = Check(id, group, description, fn, slow, platforms)
        return fn

    return register
