"""Shared fixtures.

The site is built ONCE per session into a temp directory. Building per test
would render the grid dozens of times, and building into the repo's dist/ would
make every assertion depend on whatever was last built by hand.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import build


@pytest.fixture(scope="session")
def site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build.build(tmp_path_factory.mktemp("dist"))


@pytest.fixture(scope="session")
def index_html(site: Path) -> str:
    return (site / "index.html").read_text(encoding="utf-8")
