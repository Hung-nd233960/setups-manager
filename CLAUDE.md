# Setups Manager

Python package with a command-line entry point, managed with uv (Python 3.13).

- Run: `uv run setups-manager`. Test: `uv run pytest`.
- Dependencies: `uv add <pkg>` (dev only: `uv add --dev <pkg>`). Never `pip install`.
- Layout: code in `src/setups_manager/`, tests in `tests/` (one test file per module).
- Formatting, lint, spelling and type checks run automatically after each edit (ruff, typos, ty). Fix what they report. Full pass: `ruff check . ; ty check`.
- Keep README usage in sync with the CLI. Commit in small steps.
- VS Code profile: Python, in `.vscode/profile`. If the work changes (e.g. notebooks arrive), switch with `vsc --set <profile>` (`vsc --list` shows them); never open VS Code windows unless asked.
