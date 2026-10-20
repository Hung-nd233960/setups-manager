import json
import os
import subprocess

import pytest
from setups_manager import projects, shell
from setups_manager.cli import main


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def git_identity(monkeypatch):
    for var in ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME"):
        monkeypatch.setenv(var, "Test")
    for var in ("GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL"):
        monkeypatch.setenv(var, "test@example.com")


def make_repo(root, name, date, profile=None):
    repo = root / name
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", "main")
    (repo / "a.txt").write_text("a\n")
    if profile:
        (repo / ".vscode").mkdir()
        (repo / ".vscode" / "profile").write_text(profile + "\n")
    git(repo, "add", "-A")
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-q", "-m", "init"],
        check=True,
        capture_output=True,
        env={**os.environ, "GIT_COMMITTER_DATE": f"{date}T12:00:00"},
    )
    return repo


def test_list_projects_git_facts_profile_and_order(ctx, git_identity):
    old = make_repo(ctx.projects, "old-one", "2024-01-05", profile="Python")
    make_repo(ctx.projects, "new-one", "2025-03-09")
    (old / "a.txt").write_text("changed\n")  # one uncommitted path
    (ctx.projects / "plain").mkdir()  # not a git repo
    (ctx.projects / "file.txt").write_text("x")  # not a folder
    (ctx.projects / ".hidden").mkdir()

    found = projects.list_projects(ctx)
    assert [p.name for p in found] == ["new-one", "old-one", "plain"]
    new, oldp, plain = found
    assert new.last_commit == "2025-03-09"
    assert (new.branch, new.dirty, new.ahead, new.profile) == ("main", 0, None, None)
    assert (oldp.dirty, oldp.profile, oldp.last_commit) == (1, "Python", "2024-01-05")
    assert (plain.branch, plain.dirty, plain.ahead, plain.last_commit) == (
        None,
        0,
        None,
        None,
    )


def test_ahead_counts_unpushed_commits(ctx, git_identity, tmp_path):
    repo = make_repo(ctx.projects, "tool", "2025-01-01")
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", str(remote))
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-q", "-u", "origin", "main")
    assert projects.inspect(repo).ahead == 0
    (repo / "b.txt").write_text("b\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "more")
    assert projects.inspect(repo).ahead == 1


def test_missing_projects_root_is_empty(ctx):
    assert projects.list_projects(ctx) == []


def test_set_profile_and_open_use_vsc(monkeypatch, tmp_path):
    seen = []

    def fake_stream(cmd, *, cwd=None):
        seen.append(cmd)
        yield shell.Exit(0)

    def fake_run(cmd, **kw):
        seen.append(cmd)
        return shell.Output(0, "", "")

    monkeypatch.setattr(shell, "stream", fake_stream)
    monkeypatch.setattr(shell, "run", fake_run)
    assert list(projects.set_profile(tmp_path, "Docs")) == [shell.Exit(0)]
    assert projects.open_project(tmp_path).ok
    assert seen == [
        ["vsc", "--set", "Docs", str(tmp_path)],
        ["vsc", str(tmp_path)],
    ]


def test_cli_projects_json_and_text(ctx, git_identity, monkeypatch, capsys):
    make_repo(ctx.projects, "tool", "2025-01-01", profile="Docs")
    monkeypatch.setattr("setups_manager.cli.Context.detect", lambda: ctx)
    assert main(["projects", "--json"]) == 0
    [item] = json.loads(capsys.readouterr().out)
    assert item["name"] == "tool"
    assert item["profile"] == "Docs"
    assert item["last_commit"] == "2025-01-01"
    assert main(["projects"]) == 0
    assert "tool" in capsys.readouterr().out
