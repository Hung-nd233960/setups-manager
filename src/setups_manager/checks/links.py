"""What the link scripts put in place: linked config folders, lint defaults, git setup."""

import os
from collections.abc import Iterator
from pathlib import Path

from setups_manager import shell
from setups_manager.context import Context
from setups_manager.model import Fix, Result, Status
from setups_manager.registry import check

LINT_FILES = (
    ".editorconfig",
    "ruff.toml",
    "biome.json",
    ".prettierrc.json",
    ".yamllint.yaml",
    ".taplo.toml",
    ".markdownlint-cli2.jsonc",
    "typos.toml",
)


def relink(ctx: Context) -> Fix:
    return Fix("Re-run the link script", ctx.link_script())


def linked_folders(ctx: Context) -> dict[Path, Path]:
    """Link -> target in Setups, as link.ps1 / link.sh create them."""
    common = ctx.setups / "common"
    if ctx.windows:
        return {
            Path(os.environ["LOCALAPPDATA"]) / "nvim": common / "nvim",
            Path(os.environ["APPDATA"]) / "yazi" / "config": common / "yazi",
        }
    config = Path(os.environ.get("XDG_CONFIG_HOME") or ctx.home / ".config")
    linux = ctx.setups / "linux"
    return {
        config / "nvim": common / "nvim",
        config / "yazi": common / "yazi",
        config / "helix": common / "helix",
        config / "starship.toml": common / "starship" / "starship.toml",
        config / "fish": linux / "fish",
        config / "kitty": linux / "kitty",
        config / "btop": linux / "btop",
        config / "zellij": linux / "zellij",
        config / "git" / "ignore": common / "git" / "ignore",
    }


def points_to(link: Path, target: Path) -> bool:
    is_link = link.is_symlink() or link.is_junction()
    return is_link and link.resolve() == target.resolve()


@check("links", "setup", "Config folders linked from Setups")
def links(ctx: Context) -> Iterator[Result]:
    for link, target in linked_folders(ctx).items():
        if points_to(link, target):
            yield Result(f"{link} -> Setups", Status.OK)
        else:
            yield Result(
                f"{link} is missing or not linked",
                Status.WARN,
                f"expected a link to {target}",
                relink(ctx),
            )


@check("lint-configs", "setup", "Lint and format defaults in the home folder")
def lint_configs(ctx: Context) -> Iterator[Result]:
    source = ctx.setups / "common" / "lint"
    stale = [
        name
        for name in LINT_FILES
        if not (ctx.home / name).is_file()
        or (ctx.home / name).read_bytes() != (source / name).read_bytes()
    ]
    if stale:
        yield Result(
            "home lint configs out of sync with Setups",
            Status.WARN,
            ", ".join(stale),
            relink(ctx),
        )
    else:
        yield Result("home lint configs match Setups", Status.OK)


@check("git", "setup", "Git global ignore and line endings")
def git(ctx: Context) -> Iterator[Result]:
    ignore = ctx.home / ".config" / "git" / "ignore"
    repo_ignore = ctx.setups / "common" / "git" / "ignore"
    if ignore.is_file() and ignore.read_bytes() == repo_ignore.read_bytes():
        yield Result("global gitignore matches Setups", Status.OK)
    else:
        yield Result(
            "global gitignore missing or out of date",
            Status.WARN,
            str(ignore),
            relink(ctx),
        )
    autocrlf = shell.run(["git", "config", "--global", "core.autocrlf"]).out.strip()
    if autocrlf == "input":
        yield Result("core.autocrlf = input (LF in repos)", Status.OK)
    else:
        yield Result(
            f"core.autocrlf = {autocrlf or 'unset'}",
            Status.WARN,
            "expected input",
            relink(ctx),
        )
