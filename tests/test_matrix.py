"""The matrix page: context, grid, states, palette, stage strip, budget.

Expected values and counts live here, in tests. They must never appear in
build.py or tools/.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import build


def test_the_build_writes_an_index(site: Path) -> None:
    assert (site / "index.html").is_file()


def test_the_stylesheets_are_copied(site: Path) -> None:
    assert (site / "static" / "css" / "base.css").is_file()
    assert (site / "static" / "css" / "theme.css").is_file()


def test_the_theme_source_files_are_not_published(site: Path) -> None:
    """One theme ships, renamed to theme.css. Copying the whole themes directory
    would publish the theme nobody selected and let a page link the wrong one."""
    assert not (site / "static" / "css" / "themes").exists()


def test_an_unknown_theme_fails_the_build_loudly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A typo in THEME must not silently fall back to the default. A site that
    deployed with the wrong brand and exited 0 is worse than one that failed."""
    monkeypatch.setenv("THEME", "not_a_theme")
    with pytest.raises(SystemExit):
        build.selected_theme()
