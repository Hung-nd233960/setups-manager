# Setups Manager

Python package with a command-line entry point, managed with uv (Python 3.13). It checks the machine against the Setups conventions; the README has the architecture and roadmap.

- Run: `uv run setups check --quick` (installed globally as `setups`). Test: `uv run pytest`.
- Dependencies: `uv add <pkg>` (dev only: `uv add --dev <pkg>`). Never `pip install`.
- Layout: code in `src/setups_manager/`, checks in `src/setups_manager/checks/` (one module per area), tests in `tests/`.
- **This repo is public: no personal facts in code, tests or docs** (hostnames, usernames beyond path conventions, emails, project names). Anything personal the tool needs comes from a config file in Setups-private at run time.
- **Checks are read-only.** They inspect and report; any change belongs in a `Fix` command. Mark a fix `confirm=True` when it is destructive or outward-facing (push, prune, uninstall, upgrade).
- New check: a function in the right `checks/` module, decorated with `@check(id, group, description)`; `slow=True` if it walks big folders or goes online; `platforms=` if OS-specific. Yield one `Result` per thing checked. Add a test with a temporary `Context` (`tests/conftest.py`), never against the real machine.
- Run tools through `shell.run`, which never raises. Do not duplicate rules that Setups scripts own (VS Code goes through `setup.py --json`).
- UI code (CLI now, Textual next) holds no logic: everything it can do must also work from `setups check --json`.
- Formatting, lint, spelling and type checks run automatically after each edit (ruff, typos, ty). Fix what they report. Full pass: `ruff check . ; ty check`.
- Keep README usage in sync with the CLI. Commit in small steps.
- VS Code profile: Python, in `.vscode/profile`. If the work changes (e.g. notebooks arrive), switch with `vsc --set <profile>` (`vsc --list` shows them); never open VS Code windows unless asked.
