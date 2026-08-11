"""Phase 0 scaffold checks.

Deliberately thin. Their job is to give CI something real to run so the negative
test can prove the guards actually fail, not to pre-empt later phases.
"""

from __future__ import annotations

from pathlib import Path

import build
import tools
from tools import validate as validate_mod

ROOT = Path(__file__).resolve().parent.parent


def test_package_imports() -> None:
    assert isinstance(tools.__version__, str)


def test_build_emits_a_page(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(build, "DIST", tmp_path / "dist")
    dist = build.build()
    index = dist / "index.html"
    assert index.exists()
    assert "<!doctype html>" in index.read_text(encoding="utf-8")


def test_build_is_idempotent(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """A rebuild must not accumulate stale output."""
    monkeypatch.setattr(build, "DIST", tmp_path / "dist")
    dist = build.build()
    (dist / "stale.html").write_text("removed on rebuild", encoding="utf-8")
    build.build()
    assert not (dist / "stale.html").exists()


def test_validate_reports_empty_registry_honestly() -> None:
    """With no checks registered, validate() must return no failures.

    It must not report success it has not earned, either; main() says so in words.
    """
    assert validate_mod.validate() == []


def test_docs_referenced_by_readme_exist() -> None:
    """Broken doc links in the README are a real 404 on a public repo."""
    for rel in (
        "docs/DATA_CONTRACT.md",
        "docs/sources/PROVENANCE.md",
        "PLAN.md",
        "CLAUDE.md",
        "LICENSE",
    ):
        assert (ROOT / rel).exists(), f"README links to missing {rel}"


def test_case_sensitive_doc_names() -> None:
    """macOS resolves PLAN.md to plan.md; Linux CI does not.

    The repo shipped with lowercase filenames while every reference used uppercase,
    which works locally and 404s in CI. Assert the real on-disk names.
    """
    names = {p.name for p in ROOT.iterdir()}
    assert "PLAN.md" in names
    assert "CLAUDE.md" in names
    assert "README.md" in names
