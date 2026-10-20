"""Python hygiene: conda base stays empty, the pre-built uv envs are on Python 3.13."""

import re
from collections.abc import Iterator

from setups_manager import shell
from setups_manager.context import Context
from setups_manager.model import Fix, Result, Status
from setups_manager.registry import check

ENVS = ("docs", "ds")
PYTHON = "3.13"


@check("conda", "python", "Conda base stays empty")
def conda(ctx: Context) -> Iterator[Result]:
    envs = shell.run(["conda", "env", "list"])
    if envs.missing:
        yield Result("conda is not installed", Status.SKIP)
        return
    names = [
        line
        for line in envs.out.splitlines()
        if line.strip() and not line.startswith("#")
    ]
    if len(names) > 1:
        yield Result(
            f"conda has {len(names)} envs (expected only base)",
            Status.WARN,
            fix=Fix("Review with 'conda env list'"),
        )
    else:
        yield Result("conda: base only", Status.OK)
    listing = shell.run(["conda", "list", "-n", "base"]).out
    # the channel column says pypi for pip installs; conda-pypi itself is conda tooling
    pip_installed = [
        line for line in listing.splitlines() if re.search(r"\spypi\s*$", line)
    ]
    if pip_installed:
        fix = Fix("Remove them: base must stay clean (use uv envs instead)")
        yield Result(
            f"conda base has {len(pip_installed)} pip-installed packages",
            Status.WARN,
            fix=fix,
        )
    else:
        yield Result("conda base: no pip packages", Status.OK)


@check("envs", "python", f"Pre-built uv envs on Python {PYTHON}")
def envs(ctx: Context) -> Iterator[Result]:
    found = False
    for name in ENVS:
        project = ctx.envs / name
        if not (project / "pyproject.toml").is_file():
            continue
        found = True
        out = shell.run(["uv", "run", "--project", str(project), "python", "--version"])
        version = out.out.strip().removeprefix("Python ")
        if version.startswith(PYTHON):
            yield Result(f"envs/{name} on Python {version}", Status.OK)
        else:
            fix = Fix("Re-sync the env", ["uv", "sync", "--project", str(project)])
            yield Result(
                f"envs/{name} runs Python '{version or '?'}'",
                Status.WARN,
                out.err.strip(),
                fix,
            )
    if not found:
        yield Result(f"no pre-built envs in {ctx.envs}", Status.SKIP)
