"""Where things live. Defaults follow the Setups conventions; SETUPS_DIR and
NEW_PROJECT_DIR override them as they do for the link scripts and new-project."""

import os
import sys
from dataclasses import dataclass
from pathlib import Path


def projects_root(home: Path) -> Path:
    """Same rule as new-project: $NEW_PROJECT_DIR, else D:\\projects, else ~/Projects."""
    if env := os.environ.get("NEW_PROJECT_DIR"):
        return Path(env)
    windows_default = Path(r"D:\projects")
    return windows_default if windows_default.is_dir() else home / "Projects"


@dataclass(frozen=True)
class Context:
    home: Path
    setups: Path
    private: Path  # Setups-private, cloned next to Setups
    envs: Path  # pre-built uv envs
    guides: Path  # CLI guides
    projects: Path
    platform: str  # sys.platform

    @classmethod
    def detect(cls) -> "Context":
        home = Path.home()
        setups = Path(os.environ.get("SETUPS_DIR") or home / "Setups")
        return cls(
            home=home,
            setups=setups,
            private=setups.parent / "Setups-private",
            envs=home / "envs",
            guides=home / "Documents" / "CLI-guides",
            projects=projects_root(home),
            platform=sys.platform,
        )

    @property
    def windows(self) -> bool:
        return self.platform == "win32"

    def link_script(self) -> list[str]:
        """Re-runs this OS's link script: the usual fix for setup drift."""
        if self.windows:
            return [
                "pwsh",
                "-NoProfile",
                "-File",
                str(self.setups / "windows" / "link.ps1"),
            ]
        return ["bash", str(self.setups / "linux" / "link.sh")]
