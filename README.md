# Setups Manager

Check and manage the Setups machine configuration (CLI now, Textual TUI next).

## Setup

```powershell
uv sync
```

## Usage

```powershell
uv run setups-manager --help
```

## Development

```powershell
uv run pytest
uv add <package>          # runtime dependency
uv add --dev <package>    # development-only dependency
```

Install as a command on this machine: `uv tool install --editable .`
