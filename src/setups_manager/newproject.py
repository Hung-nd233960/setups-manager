"""Options and command builder for `new-project`, which owns the rules.

The rules (types, engines, profiles, name pattern) are read from
`new-project --options-json` so they are never copied here.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from setups_manager import shell


@dataclass(frozen=True)
class Options:
    types: dict[str, str]
    engines: list[str]
    default_engine: str
    profiles: list[str]
    type_profiles: dict[str, str]
    default_dir: Path
    name_pattern: str
    uv_types: frozenset[str]  # the types where new-project runs `uv sync`


@dataclass(frozen=True)
class Request:
    type: str
    name: str
    directory: Path | None = None
    description: str = ""
    engine: str | None = None
    profile: str | None = None
    git: bool = True
    sync: bool = True
    open: bool = False


def parse_options(text: str) -> Options | None:
    try:
        data = json.loads(text)
        return Options(
            types=dict(data["types"]),
            engines=list(data["engines"]),
            default_engine=data["default_engine"],
            profiles=list(data["profiles"]),
            type_profiles=dict(data["type_profiles"]),
            default_dir=Path(data["default_dir"]),
            name_pattern=data["name_pattern"],
            uv_types=frozenset(data["uv_types"]),
        )
    except (ValueError, KeyError, TypeError):
        return None


def load_options() -> Options | None:
    """None when new-project is missing or too old to know --options-json."""
    out = shell.run(["new-project", "--options-json"], timeout=30)
    return parse_options(out.out) if out.ok else None


def target(req: Request, opts: Options) -> Path:
    return (req.directory or opts.default_dir) / req.name


def validate(req: Request, opts: Options) -> list[str]:
    """Human-readable problems; empty when the request is fine."""
    problems = []
    if req.type not in opts.types:
        problems.append(f"unknown type {req.type!r}")
    if not re.match(opts.name_pattern, req.name):
        problems.append(
            "name must be lowercase letters/digits in words joined by hyphens, "
            "e.g. ecg-hrv"
        )
    if req.engine is not None:
        if req.type != "report":
            problems.append("engine only applies to report projects")
        elif req.engine not in opts.engines:
            problems.append(f"unknown engine {req.engine!r}")
    if req.profile is not None and req.profile not in opts.profiles:
        problems.append(f"unknown profile {req.profile!r}")
    if req.name:
        path = target(req, opts)
        if path.exists() and (not path.is_dir() or any(path.iterdir())):
            problems.append(f"{path} already exists and is not empty")
    return problems


def command(req: Request) -> list[str]:
    """The new-project argv; flags that equal the defaults are left out."""
    cmd = ["new-project", req.type, req.name]
    if req.directory is not None:
        cmd += ["--dir", str(req.directory)]
    if req.description:
        cmd += ["--description", req.description]
    if req.engine is not None:
        cmd += ["--engine", req.engine]
    if req.profile is not None:
        cmd += ["--profile", req.profile]
    if req.open:
        cmd.append("--open")
    if not req.git:
        cmd.append("--no-git")
    if not req.sync:
        cmd.append("--no-sync")
    return cmd
