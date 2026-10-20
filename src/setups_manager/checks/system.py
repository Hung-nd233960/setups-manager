"""Disk space, cache sizes and PATH."""

import contextlib
import os
import shutil
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path

from setups_manager import shell
from setups_manager.context import Context
from setups_manager.model import Fix, Result, Status
from setups_manager.registry import check

MIN_FREE_PCT = 15
CACHE_WARN_MB = 2048
TEMP_WARN_MB = 5120


@check("disk", "system", "Free disk space")
def disk(ctx: Context) -> Iterator[Result]:
    if ctx.windows:
        mounts = [Path(f"{d}:\\") for d in "CD" if Path(f"{d}:\\").exists()]
    else:
        mounts = [Path("/"), ctx.home]
    seen = set()
    for mount in mounts:
        if (device := mount.stat().st_dev) in seen:
            continue
        seen.add(device)
        usage = shutil.disk_usage(mount)
        pct = round(usage.free / usage.total * 100)
        title = f"{mount} {usage.free / 2**30:.1f} GB free ({pct} %)"
        if pct < MIN_FREE_PCT:
            fix = Fix(
                "Free up space: prune caches (see the caches check), empty Downloads and the bin"
            )
            yield Result(title, Status.WARN, fix=fix)
        else:
            yield Result(title, Status.OK)


def folder_mb(path: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            with contextlib.suppress(OSError):  # vanished or locked while walking
                total += os.lstat(os.path.join(root, name)).st_size
    return total // 2**20


def cache_folders(ctx: Context) -> dict[str, Path]:
    uv = shell.run(["uv", "cache", "dir"]).out.strip()
    npm = shell.run(["npm", "config", "get", "cache"]).out.strip()
    local = Path(os.environ.get("LOCALAPPDATA") or ctx.home / ".cache")
    folders = {
        "uv cache": Path(uv) if uv else None,
        "conda pkgs": ctx.home / "miniforge3" / "pkgs",
        "cargo registry": ctx.home / ".cargo" / "registry",
        "npm cache": Path(npm) if npm else None,
        "Playwright browsers": (local if ctx.windows else ctx.home / ".cache")
        / "ms-playwright",
    }
    if ctx.windows:
        folders["Temp"] = Path(tempfile.gettempdir())
    return {name: path for name, path in folders.items() if path and path.is_dir()}


@check("caches", "system", "Package cache sizes", slow=True)
def caches(ctx: Context) -> Iterator[Result]:
    if ctx.windows:
        clean = Fix(
            "Prune package caches (uv, conda, npm, cargo downloads)",
            [
                "pwsh",
                "-NoProfile",
                "-File",
                str(ctx.setups / "windows" / "maintain.ps1"),
                "-Clean",
            ],
            confirm=True,
        )
    else:
        clean = Fix("Prune package caches: uv cache prune, conda clean --all")
    for name, path in cache_folders(ctx).items():
        mb = folder_mb(path)
        title = f"{name}: {mb} MB"
        if name == "Temp" and mb > TEMP_WARN_MB:
            fix = Fix("Close apps, then run Disk Cleanup or delete old files in %TEMP%")
            yield Result(title, Status.WARN, str(path), fix)
        elif name != "Temp" and mb > CACHE_WARN_MB:
            yield Result(title, Status.WARN, str(path), clean)
        else:
            yield Result(title, Status.OK, str(path))


def user_path() -> str:
    """The persistent PATH: the user part on Windows (what installers edit), else $PATH."""
    if sys.platform == "win32":
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            return str(winreg.QueryValueEx(key, "Path")[0])
    return os.environ.get("PATH", "")


@check("path", "system", "PATH entries that point nowhere")
def path(ctx: Context) -> Iterator[Result]:
    scope = "user PATH" if ctx.windows else "PATH"
    entries = [e for e in user_path().split(os.pathsep) if e]
    dead = [e for e in entries if not Path(os.path.expandvars(e)).exists()]
    if not dead:
        yield Result(f"{scope}: no dead entries", Status.OK)
        return
    where = "System > Environment Variables" if ctx.windows else "your shell profile"
    yield Result(
        f"{scope}: {len(dead)} folder(s) missing",
        Status.WARN,
        "\n".join(dead),
        Fix(f"Remove them in {where}"),
    )
