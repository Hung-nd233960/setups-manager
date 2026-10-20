"""All checks. Importing this package registers them, group by group, in display order."""

from setups_manager.checks import (  # noqa: F401
    claude,
    links,
    python_envs,
    repos,
    system,
    updates,
    vscode,
)
