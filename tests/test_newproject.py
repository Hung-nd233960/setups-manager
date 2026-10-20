import json
from pathlib import Path

from setups_manager import newproject, shell
from setups_manager.newproject import Options, Request, command, validate


def make_opts(default_dir: Path) -> Options:
    return Options(
        types={"py": "Python", "report": "Report"},
        engines=["quarto", "typst"],
        default_engine="quarto",
        profiles=["Default", "Python", "Docs"],
        type_profiles={"py": "Python", "report": "Docs"},
        default_dir=default_dir,
        name_pattern=r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$",
    )


def test_valid_request_has_no_problems(tmp_path):
    assert validate(Request("py", "my-tool"), make_opts(tmp_path)) == []


def test_validate_reports_each_problem(tmp_path):
    opts = make_opts(tmp_path)
    assert any("unknown type" in p for p in validate(Request("zz", "ok"), opts))
    assert any("name must" in p for p in validate(Request("py", "Bad_Name"), opts))
    assert any("name must" in p for p in validate(Request("py", ""), opts))
    assert any("engine" in p for p in validate(Request("py", "a", engine="typst"), opts))
    assert validate(Request("report", "a", engine="typst"), opts) == []
    assert any(
        "unknown engine" in p for p in validate(Request("report", "a", engine="x"), opts)
    )
    assert any("profile" in p for p in validate(Request("py", "a", profile="Nope"), opts))


def test_existing_target_must_be_empty(tmp_path):
    opts = make_opts(tmp_path)
    (tmp_path / "empty").mkdir()
    assert validate(Request("py", "empty"), opts) == []
    (tmp_path / "full").mkdir()
    (tmp_path / "full" / "f.txt").write_text("x")
    assert any("not empty" in p for p in validate(Request("py", "full"), opts))
    other = tmp_path / "elsewhere"
    (other / "full").mkdir(parents=True)
    (other / "full" / "f.txt").write_text("x")
    assert validate(Request("py", "full", directory=other), opts) != []


def test_command_omits_defaults():
    assert command(Request("py", "my-tool")) == ["new-project", "py", "my-tool"]


def test_command_with_everything():
    req = Request(
        "report",
        "paper",
        directory=Path("out"),
        description="A paper",
        engine="typst",
        profile="Docs",
        git=False,
        sync=False,
        open=True,
    )
    assert command(req) == [
        "new-project", "report", "paper", "--dir", "out", "--description", "A paper",
        "--engine", "typst", "--profile", "Docs", "--open", "--no-git", "--no-sync",
    ]  # fmt: skip


SAMPLE = {
    "types": {"py": "Python"},
    "engines": ["quarto"],
    "default_engine": "quarto",
    "profiles": ["Default", "Python"],
    "type_profiles": {"py": "Python"},
    "default_dir": "projects",
    "name_pattern": "^[a-z]+$",
}


def test_load_options_parses_new_project_output(monkeypatch):
    monkeypatch.setattr(
        shell, "run", lambda cmd, **kw: shell.Output(0, json.dumps(SAMPLE), "")
    )
    opts = newproject.load_options()
    assert opts is not None
    assert opts.default_dir == Path("projects")
    assert opts.types == {"py": "Python"}


def test_load_options_none_when_missing_or_garbled(monkeypatch):
    monkeypatch.setattr(
        shell, "run", lambda cmd, **kw: shell.Output(127, "", "not found")
    )
    assert newproject.load_options() is None
    monkeypatch.setattr(shell, "run", lambda cmd, **kw: shell.Output(0, "usage: x", ""))
    assert newproject.load_options() is None
