# Setups Manager

Checks this machine against the [Setups](https://github.com/Hung-nd233960/Setups) conventions and says how to fix what is off. A command line now; a Textual TUI is next.

## Usage

```powershell
setups check                    # every check; exit 1 if something needs attention
setups check --quick            # skip the slow ones (cache sizes, online updates)
setups check --group repos      # or --only vscode; repeatable
setups check --json             # for tools and agents
setups list                     # the checks, by group
```

Install the command (once): `uv tool install --editable .`. On Windows, `Setups\windows\maintain.ps1` runs `setups check` and adds `-Clean` / `-Update`.

Each result has a status (`ok`, `warn`, `error`, `skip`), a title, a detail and usually a **fix**: a label and, when it can be automated, a command. Fixes marked `confirm` are destructive or outward-facing (push, prune, upgrade) and must be agreed to first. `setups check` never changes anything itself.

| Group | Checks |
|---|---|
| system | disk space, cache sizes (slow), dead PATH entries |
| setup | linked config folders, lint defaults in `~`, git ignore and line endings, Claude Code stub and format hook, VS Code (through Setups' `setup.py --check --json`) |
| python | conda base stays empty, pre-built uv envs on Python 3.13 |
| repos | Setups, Setups-private, envs, CLI guides: uncommitted or unpushed work |
| updates | winget (Windows), rustup (slow, online) |

## How it fits together

```text
cli.py / (TUI next)      presentation only
runner.py                select checks, run them in parallel, stream or collect results
registry.py              @check(id, group, description, slow=, platforms=)
checks/*.py              one module per area; each check yields Result(title, status, detail, fix)
model.py · context.py    Result / Fix / Status; where things live (SETUPS_DIR, NEW_PROJECT_DIR)
shell.py                 run tools without raising: missing tool or timeout is an outcome
```

Rules that already live in Setups stay there: the VS Code check calls `common/vscode/setup.py --check --json` instead of re-implementing it.

## Roadmap

1. **TUI (Textual):** dashboard of results that fill in as checks finish, re-run, and a New project form over `new-project`.
2. **Fixes:** run a result's fix from the TUI (with a confirmation for `confirm` fixes); Projects view with each project's VS Code profile and git state.
3. **VS Code and maintenance:** settings diff viewer, extension drift, clean/update with live logs.
4. **SSH:** run `setups check --json` on a trusted host and show it next to the local results.

## Development

```powershell
uv run pytest
uv run setups check --quick
```
