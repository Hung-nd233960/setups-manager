# Build plan: setups-manager phases 1–4

This plan is written for an AI agent (Claude Sonnet) who builds the rest of setups-manager without the conversation that designed it. Read it fully before writing code. Work phase by phase, in order; each phase ends with a verification step and commits. When the plan and the code disagree, the code is the truth for what exists today and this plan is the truth for what to build next; when something here turns out to be wrong (an API that does not exist, a path that moved), stop and ask the user rather than improvising around it.

## 0. Ground rules

### Environment (Windows 11 laptop, also Linux hosts)

- Read `C:\Users\DELL\Documents\CLI-guides\cli-guide-agents.md` before running shell commands. Two shells exist: Git Bash (text work) and PowerShell 7 (Windows work). Bare `python` is conda base: never use it; use `uv run`.
- Python 3.13, uv only. Add dependencies with `uv add <pkg>` / `uv add --dev <pkg>` inside the project. Never `pip install`.
- A PostToolUse hook formats and lints every file you edit (ruff, ty, typos, markdownlint, Biome, Prettier). Fix what it reports. When the hook reformats a file, re-read it before editing the same region. A lint error that names a symbol you are about to add in the next edit is expected; check that it is gone after that edit.
- Markdown is lint-only: ATX `#` headings, `-` list markers, blank lines around headings/lists/fences, a language on every fenced block, no skipped heading levels.

### Safety

- **Never launch the TUI interactively** (`setups tui` blocks the agent's shell forever). Test it only through Textual's `App.run_test()`. When a phase needs a manual look, ask the user to run `setups tui` and report back.
- **Checks stay read-only.** Anything that changes the machine is a `Fix` command or an action, run only on an explicit user action. Fixes with `confirm=True` (push, prune, uninstall, upgrade, force-overwrite) always go through a confirmation dialog in the TUI and require `--yes` on the CLI.
- **Tests never touch the real machine.** Use a temporary `Context` (`tests/conftest.py: make_ctx`) and fake checks (the `registry` fixture). Patch `setups_manager.shell.run` / the new `shell.stream` for anything that would call a real tool.
- **This repo is public.** No personal facts in code, tests or docs: no hostnames, emails, real project names. Anything personal (phase 4's host list) is read at run time from Setups-private.
- Do not `git push`, create repos, or change other repos' remotes without asking. Commit locally, in small steps, each message ending with the attribution line the session gives you.
- Changes to the Setups repo (`C:\Users\DELL\Setups`) are allowed where a task says so; commit them there separately.

### Definition of done for every task

1. Code + tests written; `uv run pytest` passes.
2. `uv run ruff check .` and `uv run --with ty ty check` are clean.
3. README and CLAUDE.md updated if behaviour or commands changed.
4. Committed.

## 1. What exists today (phase 0)

### This repo: `D:\projects\setups-manager`

Installed globally with `uv tool install --editable .` as the command `setups`. Public: `github.com/Hung-nd233960/setups-manager`.

| File | Role |
|---|---|
| `src/setups_manager/model.py` | `Status` (ok, warn, error, skip; `.needs_attention`), `Fix(label, command: list[str] \| None, confirm: bool)`, `Result(title, status, detail, fix, check)` with `to_dict()` |
| `src/setups_manager/context.py` | `Context(home, setups, private, envs, guides, projects, platform)`, `Context.detect()` (honours `SETUPS_DIR`, `NEW_PROJECT_DIR`), `.windows`, `.link_script()` |
| `src/setups_manager/shell.py` | `run(cmd, cwd=, timeout=) -> Output(code, out, err)`; never raises; `.ok`, `.missing` (exit 127 = tool not found, 124 = timeout). Resolves `.cmd` shims via `shutil.which` |
| `src/setups_manager/registry.py` | `GROUPS = ("system", "setup", "python", "repos", "updates")`, `Check(id, group, description, fn, slow, platforms)`, `REGISTRY`, decorator `@check(...)` |
| `src/setups_manager/runner.py` | `select(ctx, ids, groups, quick)`, `run_one`, `iter_results(checks, ctx)` (yields each check's results as it finishes, thread pool), `run_all` (ordered) |
| `src/setups_manager/checks/*.py` | `system` (disk, caches, path), `links` (links, lint-configs, git), `claude`, `vscode`, `python_envs` (conda, envs), `repos`, `updates` (winget, rustup) |
| `src/setups_manager/cli.py` | `setups check [--json] [--quick] [--group G] [--only ID]`, `setups list` |
| `tests/` | `conftest.py` (`make_ctx`, `ctx`, `registry` fixtures), `test_runner.py`, `test_checks.py`, `test_cli.py` |

`setups check --json` prints `{"summary": {"ok": n, "warn": n, "error": n, "skip": n}, "results": [Result.to_dict(), ...]}`; exit 1 when anything needs attention.

### Tools this project drives (owned by the Setups repo, do not re-implement their rules)

| Tool | Where | What matters here |
|---|---|---|
| VS Code setup | `C:\Users\DELL\Setups\common\vscode\setup.py` (stdlib-only, also runs on servers) | `--check --json` (results `{status: ok\|drift\|missing\|extra\|skip\|warn\|failed, subject, detail}`), `--diff` (unified diff of live settings vs repo), `--prune`, `--force`, `--server`. Creating profiles / linking projects needs VS Code closed (reports `skip` otherwise) |
| Profiles | `C:\Users\DELL\Setups\common\vscode\profiles.json` | `{"base": [...], "profiles": {name: {"icon", "extensions", "extends"?}}}`. Profile names today: Python, Data Science, Web, Docs, Rust (plus the implicit Default) |
| `new-project` | `C:\Users\DELL\Setups\common\tools\new-project` (separate uv tool) | `new-project <py\|data\|report\|web> <name> [--dir D] [--description T] [--engine quarto\|typst\|latex] [--profile P] [--open] [--no-git] [--no-sync]`. Name must match `^[a-z][a-z0-9]*(-[a-z0-9]+)*$`. Default dir: `$NEW_PROJECT_DIR`, else `D:\projects`, else `~/Projects` |
| `vsc` | same package as `new-project` | `vsc [dir]` opens a folder in its profile (reads `.vscode/profile`), `vsc --set <profile> [dir]` writes the marker, `vsc --list` |
| `maintain.ps1` | `C:\Users\DELL\Setups\windows\maintain.ps1` | No flags: runs `setups check`. `-Clean`: prune caches. `-Update`: winget/uv tools/rustup/cargo/npm upgrades |
| Link scripts | `Setups\windows\link.ps1`, `Setups\linux\link.sh` | Idempotent; the usual fix for setup drift (`ctx.link_script()`) |

## 2. Target architecture

```text
┌──────────── presentation (no logic) ─────────────┐
│ cli.py: check · list · fix · projects ·           │
│         new-options                               │
│ tui/:   app.py + one screen/pane per tab          │
└──────────────────────┬───────────────────────────┘
                       │ imports
┌──────────────────────▼───────────────────────────┐
│ core                                              │
│  runner.py, registry.py, checks/   (exist)        │
│  shell.py   + stream(cmd) for live output   (P1)  │
│  newproject.py  options + command builder   (P1)  │
│  actions.py     fixable results, run a fix  (P2)  │
│  projects.py    list projects, set profile  (P2)  │
│  maintenance.py clean/update per platform   (P3)  │
│  hosts.py       remote checks over SSH      (P4)  │
└──────────────────────┬───────────────────────────┘
                       │ subprocess
   setup.py · new-project · vsc · git · maintain.ps1 · ssh
```

Rules:

- Every TUI capability has a core function with unit tests, and where it makes sense a CLI command (agents use the CLI; they never run the TUI).
- The TUI never blocks its event loop: checks, fixes and commands run in Textual thread workers and push updates back with `App.call_from_thread`.
- Commands are always `list[str]` (no shell strings), run through `shell.run` / `shell.stream`.

## 3. Phase 1: TUI shell, Dashboard, New project

### 1.1 Dependencies and entry point

- `uv add textual`; `uv add --dev pytest-asyncio`. Record nothing by hand: uv writes `pyproject.toml` and `uv.lock`. Print `textual.__version__` once and use APIs that exist in that version (check the Textual docs or `help()` when unsure; do not guess signatures).
- In `pyproject.toml` add `[tool.pytest.ini_options] asyncio_mode = "auto"`.
- CLI: add subcommand `setups tui` that imports `setups_manager.tui.app` lazily (keep `setups check` fast and free of Textual imports) and runs `SetupsApp().run()`.

### 1.2 Core: streaming commands (`shell.stream`)

Add to `shell.py`:

```python
def stream(cmd: list[str], *, cwd: Path | None = None) -> Iterator[str]:
    """Yield output lines (stdout and stderr merged) as they arrive; the last item is
    a sentinel line 'exit <code>' (127 when the tool is missing)."""
```

Implementation: `subprocess.Popen([exe, *cmd[1:]], stdout=PIPE, stderr=STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1)`, resolve `exe` with `shutil.which` like `run`. Strip trailing newlines. If you prefer a small result object over the sentinel string, do that instead, but keep it simple and tested. Tests: a real call to `sys.executable -c "print('a'); print('b')"` (that is safe: it is the test's own interpreter), and a missing tool.

### 1.3 Core: New project options (`newproject.py`)

Avoid hard-coding new-project's rules twice. First, in the **Setups repo**, give new-project a machine-readable description:

- `new-project --options-json` prints `{"types": {id: description}, "engines": ["quarto", "typst", "latex"], "default_engine": "quarto", "profiles": [...names incl. "Default"], "type_profiles": {"py": "Python", ...}, "default_dir": "...", "name_pattern": "^[a-z]..."}` and exits 0. Source of each value: `TYPES`, the `--engine` choices, `vscode.names()`, `vscode.TYPE_PROFILES`, `default_root()`, `NAME_RE.pattern` in `new_project/cli.py` / `vscode.py`. Because `type` and `name` are required positionals, handle `--options-json` before `parse_args` (check `argv` first) or make it a separate tiny parser. Add a test in new-project if it has a tests folder; otherwise verify by running it. Commit in Setups.

Then in this repo, `newproject.py`:

```python
@dataclass(frozen=True)
class Options:  # parsed from new-project --options-json
    types: dict[str, str]; engines: list[str]; default_engine: str
    profiles: list[str]; type_profiles: dict[str, str]
    default_dir: Path; name_pattern: str

def load_options() -> Options | None          # None when new-project is not installed
@dataclass(frozen=True)
class Request:
    type: str; name: str; directory: Path | None = None; description: str = ""
    engine: str | None = None; profile: str | None = None
    git: bool = True; sync: bool = True; open: bool = False
def validate(req: Request, opts: Options) -> list[str]   # human-readable problems, [] if fine
def command(req: Request) -> list[str]                   # the new-project argv
```

`validate` checks: known type; name matches `name_pattern`; engine only for `report`; profile known; target `(directory or default_dir) / name` does not exist or is empty. `command` omits flags that equal defaults. Expose on the CLI as `setups new-options` (prints the options JSON) only if useful for testing; it is optional.

Tests: `validate` and `command` with a hand-written `Options` (no subprocess); `load_options` with `shell.run` patched to return sample JSON and to return `missing`.

### 1.4 TUI layout (`src/setups_manager/tui/`)

```text
tui/
  __init__.py
  app.py          SetupsApp: header, TabbedContent (Dashboard, New project), footer, theme
  dashboard.py    DashboardPane
  new_project.py  NewProjectPane
  widgets.py      shared: ConfirmScreen (ModalScreen[bool]), LogPanel (RichLog wrapper)
  app.tcss        styles
```

- Theme: `self.theme = "catppuccin-mocha"` if that theme exists in the installed Textual, else leave the default.
- App bindings: `q` quit, `r` re-run checks, `n` focus New project tab, `?` help (Textual's built-in key panel is fine).
- `SetupsApp.__init__(self, ctx: Context | None = None, checks: list[Check] | None = None)`. Default `Context.detect()` and `select(ctx)`. Tests pass a temp context and fake checks.

### 1.5 Dashboard

- A `DataTable` with columns: status, check, title. One row per `Result`, row key `f"{result.check}:{index}"` (index within that check's results). Status cell shows a symbol + word (`✓ ok`, `⚠ warn`, `✗ error`, `– skip`), styled by status.
- On mount and on `r`: clear, then run checks in a thread worker (`@work(thread=True, exclusive=True)`), iterating `runner.iter_results`, and add rows through `self.app.call_from_thread(...)` as each check finishes. Show a progress line: `Running checks: 7/13`. Keep rows grouped in `select` order: either insert in order when all are done, or keep a placeholder row per check (`… running`) that gets replaced. Placeholder rows are nicer: implement them.
- A "Quick" switch (default on) that skips slow checks; a separate key `R` runs everything.
- A detail panel below the table shows the selected row's detail and its fix (label, command, "asks first" when `confirm`). No running fixes yet (phase 2).
- A summary line: `24 ok · 2 warn · 0 error`.

### 1.6 New project pane

- Form widgets: Type (`Select` from `Options.types`), Name (`Input` with live validation against `name_pattern`), Engine (`Select`, enabled only for `report`), Profile (`Select`, default follows Type via `type_profiles` until the user changes it), Description (`Input`), Directory (`Input`, placeholder = default dir), switches: git, uv sync (only meaningful for py/data), open in VS Code afterwards.
- A read-only preview line showing the exact command (`newproject.command`), updated on every change.
- A Create button, disabled while `validate` returns problems; problems are listed under the form.
- Create runs the command with `shell.stream` in a thread worker and appends lines to a `LogPanel`. On exit 0 show "Created <path>" and a button "Open in VS Code" (`vsc <path>`; opening a window is fine here because the user asked for it). On failure keep the form filled.
- If `load_options()` returns None, the pane shows "new-project is not installed" with the install command from the Setups README instead of the form.

### 1.7 Tests for phase 1

- `tests/test_shell.py`, `tests/test_newproject.py` (see above).
- `tests/test_tui.py` with Textual's pilot, fake registry and temp context:
  - Dashboard fills one row per fake result and shows the summary; `r` re-runs (count fake check calls).
  - A crashing fake check shows an error row and does not stop the others.
  - New project: invalid name disables Create and lists the problem; changing Type to report enables Engine; preview shows the expected argv. Patch `load_options` with a fixed `Options`; patch `shell.stream` so Create "runs" a fake command and the log shows its lines.
- Give widgets stable ids (`#checks-table`, `#np-name`, `#np-create`, …) so tests and CSS can target them.

### 1.8 Verify and commit

- `uv run pytest`, ruff, ty clean.
- Ask the user to run `setups tui` and check: theme, table fills progressively, New project form behaves. Fix what they report.
- Update README (Usage: `setups tui`; Roadmap: mark phase 1 done) and CLAUDE.md (TUI layout, "never run the TUI; use run_test").
- Commits (suggested): "shell.stream", "newproject options and command builder" (+ the Setups commit for `--options-json`), "TUI: app shell and dashboard", "TUI: new project form", "docs".

## 4. Phase 2: Fixes and Projects

### 2.1 Core: `actions.py`

```python
@dataclass(frozen=True)
class FixTarget:
    key: str            # f"{check}:{index}", same as the dashboard row key
    result: Result      # result.fix is not None and result.fix.command is not None

def fixable(results: list[Result]) -> list[FixTarget]
def run_fix(target: FixTarget) -> Iterator[str]   # shell.stream(target.result.fix.command)
```

Only results that need attention and have a command are fixable; manual fixes (command None) are shown, never run.

### 2.2 CLI: `setups fix`

- `setups fix --list [--quick]`: runs the checks and prints the fixable results with their key, label, command and whether they need confirmation.
- `setups fix <key>... [--yes]`: re-runs the checks that own those keys, then runs each matching fix, streaming output. A fix with `confirm=True` runs only with `--yes`; without it, print what would run and exit 2. Never prompt interactively (agents call this).
- After the fixes, re-run the affected checks and print their new status.
- Tests with fake checks whose fix command is `[sys.executable, "-c", "print('fixed')"]`.

### 2.3 TUI: running fixes

- Dashboard: key `f` (and a button in the detail panel) runs the selected row's fix. `confirm=True` opens `ConfirmScreen` showing the exact command; Cancel does nothing. Output streams into a `LogPanel` under the detail panel. When the fix ends, re-run that row's check and update its rows.
- Manual fixes show their label in the detail panel with no run button.
- Block a second fix while one runs (disable the key/button; `exclusive=True` worker).

### 2.4 Core: `projects.py`

```python
@dataclass(frozen=True)
class Project:
    path: Path; profile: str | None        # from .vscode/profile
    branch: str | None; dirty: int; ahead: int | None; last_commit: str | None  # ISO date
def list_projects(ctx: Context) -> list[Project]   # immediate subfolders of ctx.projects
def set_profile(path: Path, profile: str) -> Iterator[str]   # vsc --set <profile> <path>
def open_project(path: Path) -> shell.Output                 # vsc <path>
```

Git facts via `shell.run(["git", "-C", path, ...])` (`rev-parse --abbrev-ref HEAD`, `status --porcelain`, `rev-list --count @{u}..HEAD`, `log -1 --format=%cs`); non-git folders get None/0. CLI: `setups projects [--json]`. Tests with temp git repos (see `test_checks.py` for the git identity fixture).

### 2.5 TUI: Projects tab

- `DataTable`: name, profile (or `—`), branch, uncommitted, unpushed, last commit. Sorted by last commit, newest first.
- Actions on the selected project: `o` open in VS Code, `p` set profile (modal with a `Select` of profile names from `Options.profiles`), `g` refresh.
- After a profile change, remind in the status line that VS Code links the folder next time `setup.py` runs with VS Code closed, or right away when opened with `o`.

### 2.6 Verify and commit

Same as 1.8. Ask the user to try one non-confirm fix and one confirm fix (cancel it) in the TUI.

## 5. Phase 3: VS Code and Maintenance tabs

### 3.1 VS Code tab

- Shows only the `vscode` check's results (reuse the dashboard table widget with a filter, do not duplicate it).
- "Show settings diff": runs `setup.py --diff` (`[sys.executable, <ctx.setups>/common/vscode/setup.py, "--diff"]`) and renders the output with Rich `Syntax(..., "diff")` in a scrollable panel. Empty output means "no differences".
- Buttons: "Run setup" (plain `setup.py`; warn first that profiles and project links need VS Code closed; detect it with the same `tasklist` / `pgrep` logic as `setup.py`, put that helper in `shell.py` as `vscode_running()` with a test that patches `shell.run`), "Prune extensions" (`--prune`, confirm), "Overwrite local settings" (`--force`, confirm, mention that a backup is kept).
- Keep the instruction "move what you want into `settings.jsonc` in the Setups repo" visible next to the diff; the TUI does not edit repo files.

### 3.2 Core: `maintenance.py`

```python
@dataclass(frozen=True)
class Task:
    id: str; label: str; command: list[str]; confirm: bool = True
def tasks(ctx: Context) -> list[Task]
```

Windows: `clean` = `pwsh -NoProfile -File <setups>\windows\maintain.ps1 -Clean`, `update` = same with `-Update`. Linux: `clean` = `uv cache prune` (add `conda clean --all -y` when conda exists), `update` = `uv tool upgrade --all`, `rustup update` (one Task each; skip tools that are missing). Tests per platform with temp contexts (`make_ctx(..., platform="linux")`).

### 3.3 Maintenance tab

- One button per task, each confirms first (show the command), output streams into a `LogPanel`, the tab's status line shows the exit code. After a task, offer "Re-run checks".
- Long tasks (winget can take minutes) must not freeze the UI; a running task disables the other buttons.

### 3.4 Verify and commit

Same as 1.8; ask the user to run the diff viewer and cancel a maintenance task at the confirm step.

## 6. Phase 4: SSH hosts

### 4.1 Host list (private, outside this repo)

- File: `<ctx.private>/setups-manager/hosts.toml` (Setups-private is a private repo; do not create or commit this file yourself: ask the user for the host names, then they or you create it in Setups-private with their approval).

```toml
[[host]]
name = "workstation"      # label shown in the TUI
ssh = "user@hostname"     # anything `ssh` accepts, incl. ~/.ssh/config aliases
```

- Missing file: the Hosts tab explains where to create it, with the example above.

### 4.2 Core: `hosts.py`

```python
@dataclass(frozen=True)
class Host:
    name: str; ssh: str
def load_hosts(ctx: Context) -> list[Host]                 # tomllib; [] when the file is missing
def remote_check(host: Host, quick: bool = True) -> list[Result] | Result
```

`remote_check` runs `ssh -o BatchMode=yes -o ConnectTimeout=8 <host.ssh> setups check --json [--quick]` through `shell.run` (timeout ~120 s). BatchMode means no password prompts: auth must already work with keys. Exit 1 with valid JSON is normal (warnings). Map errors to one `Result` with status error: unreachable (ssh exit 255), `setups` not installed on the host (`command not found` / exit 127 in stderr; fix label: "Install setups-manager on the host: clone it and `uv tool install --editable`"), unparsable output. Remote fixes are **shown, never run** from the laptop. Tests patch `shell.run`.

Note: on Linux hosts `setups` must be on the PATH of a non-interactive SSH session (`~/.local/bin` is usually there for uv tools; if not, the README should say so).

### 4.3 Hosts tab

- One row per host: name, summary (`ok/warn/error` counts) or the connection error, checked at (time). `c` checks the selected host, `C` checks all (in parallel workers). Selecting a host shows its results in the same table widget as the dashboard (read-only, no fix button).

### 4.4 Verify and commit

Same as 1.8. The user verifies against a real host; ask them to install setups-manager there first (`git clone` + `uv tool install --editable`).

## 7. Final documentation pass

After phase 4 (or after any phase the user decides is the last):

- `README.md`: usage for every command (`check`, `list`, `fix`, `projects`, `tui`), the tabs, the hosts file location (without real host names), roadmap state.
- `CLAUDE.md`: module map (core vs tui), the rules from section 0 that apply to future work.
- Setups repo (separate commit there): README monthly check-up paragraph mentions `setups tui`; nothing else.
- CLI guides (`C:\Users\DELL\Documents\CLI-guides`, local repo without remote): the human guide gets a `setups tui` line in the tools table; the agent guide's machine-health row gets `setups fix <key> [--yes]` and "never run `setups tui`". Rebuild with `pwsh -File C:\Users\DELL\Documents\CLI-guides\build.ps1` and commit there.

## 8. Ask the user instead of guessing

- The SSH host names and `ssh` targets (phase 4), and permission to add `hosts.toml` to Setups-private.
- Whether `setups` with no subcommand should open the TUI (current plan: no, it prints help; agents must never land in the TUI by accident).
- Anything that needs pushing, publishing, or changing another repo beyond what a task above names.
- Any Textual API in this plan that does not exist in the installed version.
