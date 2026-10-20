"""Select checks and run them in parallel (most of the time is spent waiting on tools)."""

from collections.abc import Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace

import setups_manager.checks  # noqa: F401  (imports the check modules, which register themselves)
from setups_manager.context import Context
from setups_manager.model import Result, Status
from setups_manager.registry import GROUPS, REGISTRY, Check


def select(
    ctx: Context,
    ids: Iterable[str] | None = None,
    groups: Iterable[str] | None = None,
    quick: bool = False,
) -> list[Check]:
    """Checks for this platform in display order (group, then registration)."""
    checks = [c for c in REGISTRY.values() if ctx.platform in c.platforms]
    if ids:
        wanted = set(ids)
        if unknown := wanted - {c.id for c in checks}:
            raise ValueError(
                f"unknown check(s) on this platform: {', '.join(sorted(unknown))}"
            )
        checks = [c for c in checks if c.id in wanted]
    if groups:
        checks = [c for c in checks if c.group in set(groups)]
    if quick:
        checks = [c for c in checks if not c.slow]
    return sorted(checks, key=lambda c: GROUPS.index(c.group))


def run_one(check: Check, ctx: Context) -> list[Result]:
    try:
        results = list(check.fn(ctx))
    except Exception as e:  # a broken check must not hide the others
        results = [Result(check.description, Status.ERROR, f"check crashed: {e!r}")]
    return [replace(r, check=check.id) for r in results]


def iter_results(
    checks: list[Check], ctx: Context, workers: int = 8
) -> Iterator[list[Result]]:
    """Each check's results as soon as it finishes (for the TUI)."""
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run_one, c, ctx) for c in checks]
        for future in as_completed(futures):
            yield future.result()


def run_all(checks: list[Check], ctx: Context) -> list[Result]:
    """All results, in the order of `checks`."""
    order = {c.id: i for i, c in enumerate(checks)}
    results = [r for batch in iter_results(checks, ctx) for r in batch]
    return sorted(results, key=lambda r: order[r.check])
