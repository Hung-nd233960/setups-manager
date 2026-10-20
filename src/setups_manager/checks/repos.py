"""The config repos: nothing uncommitted, nothing unpushed (as of the last fetch)."""

from collections.abc import Iterator
from pathlib import Path

from setups_manager import shell
from setups_manager.context import Context
from setups_manager.model import Fix, Result, Status
from setups_manager.registry import check


def git(repo: Path, *args: str) -> shell.Output:
    return shell.run(["git", "-C", str(repo), *args])


@check("repos", "repos", "Config repos committed and pushed")
def repos(ctx: Context) -> Iterator[Result]:
    for repo in (ctx.setups, ctx.private, ctx.envs, ctx.guides):
        if not (repo / ".git").exists():
            yield Result(
                f"{repo} is not a git repo",
                Status.WARN,
                fix=Fix(f"Clone or init {repo.name}"),
            )
            continue
        dirty = len(git(repo, "status", "--porcelain").out.splitlines())
        upstream = git(repo, "rev-parse", "--abbrev-ref", "@{u}")
        ahead = (
            int(git(repo, "rev-list", "--count", "@{u}..HEAD").out.strip() or 0)
            if upstream.ok
            else None
        )
        detail = (
            f"uncommitted: {dirty}, unpushed: {'no remote' if ahead is None else ahead}"
        )
        if dirty:
            fix = Fix(f'Commit or discard the changes (git -C "{repo}" status)')
            yield Result(
                f"{repo}: {dirty} uncommitted change(s)", Status.WARN, detail, fix
            )
        elif ahead:
            fix = Fix(
                f"Push {ahead} commit(s)",
                ["git", "-C", str(repo), "push"],
                confirm=True,
            )
            yield Result(
                f"{repo}: {ahead} commit(s) not pushed", Status.WARN, detail, fix
            )
        else:
            yield Result(f"{repo}: clean", Status.OK, detail)
