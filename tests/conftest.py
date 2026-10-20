import sys
from pathlib import Path

import pytest
from setups_manager.context import Context
from setups_manager.registry import REGISTRY


def make_ctx(root: Path, platform: str = sys.platform) -> Context:
    home = root / "home"
    setups = home / "Setups"
    return Context(
        home=home,
        setups=setups,
        private=home / "Setups-private",
        envs=home / "envs",
        guides=home / "Documents" / "CLI-guides",
        projects=root / "projects",
        platform=platform,
    )


@pytest.fixture
def ctx(tmp_path: Path) -> Context:
    return make_ctx(tmp_path)


@pytest.fixture
def registry():
    """An empty registry for the test; the real checks come back afterwards."""
    saved = dict(REGISTRY)
    REGISTRY.clear()
    yield REGISTRY
    REGISTRY.clear()
    REGISTRY.update(saved)
