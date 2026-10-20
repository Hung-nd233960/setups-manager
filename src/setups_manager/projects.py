"""The projects folder: each project's VS Code profile and git state."""

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path

from setups_manager import shell
from setups_manager.context import Context


@dataclass(frozen=True)
class Project:
    path: Path
    profile: str | None  # from .vscode/profile
    branch: str | None  # None: not a git repo
    dirty: int  # uncommitted paths
    ahead: int | None  # commits not pushed; None: no upstream
    last_commit: str | None  # ISO date

    @property
    def name(self) -> str:
        return self.path.name

    def to_dict(self) -> dict:
        return asdict(self) | {"path": str(self.path), "name": self.name}


def git(path: Path, *args: str) -> shell.Output:
    return shell.run(["git", "-C", str(path), *args])


def read_profile(path: Path) -> str | None:
    try:
        text = (path / ".vscode" / "profile").read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return text or None


def inspect(path: Path) -> Project:
    profile = read_profile(path)
    if not (path / ".git").exists():
        return Project(path, profile, None, 0, None, None)
    branch = git(path, "rev-parse", "--abbrev-ref", "HEAD")
    ahead = git(path, "rev-list", "--count", "@{u}..HEAD")
    last = git(path, "log", "-1", "--format=%cs")
    return Project(
        path=path,
        profile=profile,
        branch=(branch.out.strip() or None) if branch.ok else None,
        dirty=len(git(path, "status", "--porcelain").out.splitlines()),
        ahead=int(ahead.out.strip() or 0) if ahead.ok else None,
        last_commit=(last.out.strip() or None) if last.ok else None,
    )


def list_projects(ctx: Context) -> list[Project]:
    """Immediate subfolders of the projects root, newest last commit first."""
    if not ctx.projects.is_dir():
        return []
    folders = sorted(
        p for p in ctx.projects.iterdir() if p.is_dir() and not p.name.startswith(".")
    )
    with ThreadPoolExecutor(max_workers=8) as pool:
        found = list(pool.map(inspect, folders))
    # ISO dates sort as text; folders without commits go last
    return sorted(found, key=lambda p: p.last_commit or "", reverse=True)


def set_profile(path: Path, profile: str) -> Iterator[str | shell.Exit]:
    """`vsc --set <profile> <path>`: writes the .vscode/profile marker."""
    return shell.stream(["vsc", "--set", profile, str(path)])


def open_project(path: Path) -> shell.Output:
    """`vsc <path>`: opens the folder in its profile (a VS Code window appears)."""
    return shell.run(["vsc", str(path)])
