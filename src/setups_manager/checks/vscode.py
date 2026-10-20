"""VS Code, through Setups' own setup.py (--check --json), so the rules live in one place."""

import json
import shutil
import sys
from collections.abc import Iterator
from pathlib import Path

from setups_manager import shell
from setups_manager.context import Context
from setups_manager.model import Fix, Result, Status
from setups_manager.registry import check


def convert(item: dict, setup: list[str]) -> Result:
    """One setup.py result -> Result, with the setup.py call that resolves it."""
    status, subject, detail = item["status"], item["subject"], item["detail"]
    title = f"{subject}: {detail}" if detail and status == "ok" else subject
    detail = "" if status == "ok" else detail
    match status:
        case "ok":
            return Result(title, Status.OK)
        case "drift":
            fix = Fix(
                "Review with --diff, move what you want into the repo, then run setup.py --force",
                [*setup, "--diff"],
            )
            return Result(title, Status.WARN, detail, fix)
        case "extra":
            return Result(
                title,
                Status.WARN,
                detail,
                Fix(
                    "Uninstall the unlisted extensions",
                    [*setup, "--prune"],
                    confirm=True,
                ),
            )
        case "missing" | "skip":
            fix = Fix(
                "Run the VS Code setup (close VS Code first for profiles and project links)",
                setup,
            )
            return Result(title, Status.WARN, detail, fix)
        case "failed":
            return Result(title, Status.ERROR, detail)
        case _:
            return Result(title, Status.WARN, detail)


def setup_results(script: Path, extra: list[str]) -> Iterator[Result]:
    setup = [sys.executable, str(script), *extra]
    out = shell.run([*setup, "--check", "--json"], timeout=300)
    try:
        report = json.loads(out.out)
    except json.JSONDecodeError:
        yield Result(
            "VS Code check could not run",
            Status.ERROR,
            (out.err or out.out).strip()[-500:],
        )
        return
    for item in report["results"]:
        yield convert(item, setup)


@check("vscode", "setup", "VS Code settings, profiles, extensions and project links")
def vscode(ctx: Context) -> Iterator[Result]:
    script = ctx.setups / "common" / "vscode" / "setup.py"
    if shutil.which("code") is None:
        yield Result("VS Code is not installed here", Status.SKIP)
    else:
        yield from setup_results(script, [])
    if not ctx.windows:
        # Linux hosts serve Remote-SSH windows: the link script installs their remote settings
        yield from setup_results(script, ["--server"])
