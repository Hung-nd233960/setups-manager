"""Fixes that can be run: the results whose Fix carries a command."""

from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass

from setups_manager import shell
from setups_manager.model import Result, row_key


@dataclass(frozen=True)
class FixTarget:
    key: str  # same as the dashboard row key
    result: Result  # needs attention, and result.fix.command is set


def fixable(results: list[Result]) -> list[FixTarget]:
    """Results that need attention and have a command. Manual fixes are shown, never run."""
    seen: Counter[str] = Counter()  # next index per check
    targets = []
    for r in results:
        index = seen[r.check]
        seen[r.check] += 1
        if r.status.needs_attention and r.fix and r.fix.command:
            targets.append(FixTarget(row_key(r, index), r))
    return targets


def run_fix(target: FixTarget) -> Iterator[str | shell.Exit]:
    """Run the fix's command: output lines, then one `shell.Exit`."""
    command = target.result.fix.command if target.result.fix else None
    if not command:
        raise ValueError(f"{target.key} has no command to run")
    return shell.stream(command)
