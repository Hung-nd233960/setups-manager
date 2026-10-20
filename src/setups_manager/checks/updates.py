"""Available updates (online, so slow)."""

import re
from collections.abc import Iterator

from setups_manager import shell
from setups_manager.context import Context
from setups_manager.model import Fix, Result, Status
from setups_manager.registry import check

# a winget upgrade table row: name ... id  installed  available  winget
WINGET_ROW = re.compile(r"^\S.*\s\d[\d.]+\s+\d[\d.]+\s+winget\s*$")


@check("winget", "updates", "App updates from winget", slow=True, platforms=("win32",))
def winget(ctx: Context) -> Iterator[Result]:
    out = shell.run(["winget", "upgrade", "--accept-source-agreements"], timeout=180)
    if out.missing:
        yield Result("winget is not installed", Status.SKIP)
        return
    rows = [line.strip() for line in out.out.splitlines() if WINGET_ROW.match(line)]
    if not rows:
        yield Result("winget: up to date", Status.OK)
        return
    upgrade = [
        "winget",
        "upgrade",
        "--all",
        "--silent",
        "--accept-package-agreements",
        "--accept-source-agreements",
    ]
    fix = Fix("Upgrade all apps", upgrade, confirm=True)
    yield Result(
        f"winget: {len(rows)} upgrade(s) available", Status.WARN, "\n".join(rows), fix
    )


@check("rustup", "updates", "Rust toolchain updates", slow=True)
def rustup(ctx: Context) -> Iterator[Result]:
    out = shell.run(["rustup", "check"], timeout=120)
    if out.missing:
        yield Result("rustup is not installed", Status.SKIP)
        return
    available = [
        line.strip() for line in out.out.splitlines() if "Update available" in line
    ]
    if available:
        fix = Fix("Update the toolchain", ["rustup", "update"], confirm=True)
        yield Result("rustup: update available", Status.WARN, "\n".join(available), fix)
    else:
        yield Result("rustup: up to date", Status.OK)
