# Setups Manager

Checks this machine against the [Setups](https://github.com/Hung-nd233960/Setups) conventions and says how to fix what is off. A command line plus a Textual TUI.

## Usage

```powershell
setups check                    # every check; exit 1 if something needs attention
setups check --quick            # skip the slow ones (cache sizes, online updates)
setups check --group repos      # or --only vscode; repeatable
setups check --json             # for tools and agents
setups list                     # the checks, by group
setups fix --list               # results with a fix command, each with a key like repos:2
setups fix repos:2 [--yes]      # run that fix, then re-check (fixes that ask first need --yes)
setups projects [--json]        # project folders with VS Code profile and git state
setups tui                      # terminal UI: Dashboard, New project and Projects tabs
```

`setups tui` is for people at a keyboard (agents use the commands above and must never start it). Keys: `r` re-run checks (follows the Quick switch), `R` run all including slow ones, `f` run the selected row's fix (also the Run fix button; fixes that ask first show the exact command in a dialog), `n` New project, `q` quit. Fix output streams into a log under the detail panel and the owning check is re-run afterwards. Manual fixes only show their label. The Projects tab lists each project folder (profile, branch, uncommitted, unpushed, last commit); with the table focused, `o` opens the project in VS Code, `p` sets its profile (names from `new-project`), `g` refreshes. The New project tab is a form over `new-project`: it reads the rules from `new-project --options-json`, shows the exact command it will run, and streams its output.

Install the command (once): `uv tool install --editable .`. On Windows, `Setups\windows\maintain.ps1` runs `setups check` and adds `-Clean` / `-Update`.

Each result has a status (`ok`, `warn`, `error`, `skip`), a title, a detail and usually a **fix**: a label and, when it can be automated, a command. Fixes marked `confirm` are destructive or outward-facing (push, prune, upgrade) and must be agreed to first. `setups check` never changes anything itself; `setups fix <key>` runs one fix on request. It never prompts: a fix that asks first runs only with `--yes`, otherwise nothing runs and the exit code is 2.

| Group | Checks |
|---|---|
| system | disk space, cache sizes (slow), dead PATH entries |
| setup | linked config folders, lint defaults in `~`, git ignore and line endings, Claude Code stub and format hook, VS Code (through Setups' `setup.py --check --json`) |
| python | conda base stays empty, pre-built uv envs on Python 3.13 |
| repos | Setups, Setups-private, envs, CLI guides: uncommitted or unpushed work |
| updates | winget (Windows), rustup (slow, online) |

## How it fits together

```text
cli.py · tui/            presentation only (tui/: app, dashboard, new_project, projects, widgets)
runner.py                select checks, run them in parallel, stream or collect results
registry.py              @check(id, group, description, slow=, platforms=)
checks/*.py              one module per area; each check yields Result(title, status, detail, fix)
actions.py               fixable results and running a fix (shared by `setups fix` and the TUI)
projects.py              project folders: VS Code profile, git state, set profile, open
model.py · context.py    Result / Fix / Status / row_key; where things live (SETUPS_DIR, NEW_PROJECT_DIR)
shell.py                 run tools without raising; stream() yields live output lines
newproject.py            new-project options, validation and command builder
```

Rules that already live in Setups stay there: the VS Code check calls `common/vscode/setup.py --check --json` instead of re-implementing it.

## Roadmap

1. **TUI (Textual), done:** dashboard of results that fill in as checks finish, re-run, and a New project form over `new-project`.
2. **Fixes and Projects, done:** `setups fix` and the dashboard's `f` run a result's fix (a dialog first for `confirm` fixes); the Projects tab and `setups projects` show each project's VS Code profile and git state.
3. **VS Code and maintenance:** settings diff viewer, extension drift, clean/update with live logs.
4. **SSH:** run `setups check --json` on a trusted host and show it next to the local results.

## Development

```powershell
uv run pytest
uv run setups check --quick
```

TUI tests use Textual's `App.run_test()` (headless). Never launch `setups tui` from a script or agent.
