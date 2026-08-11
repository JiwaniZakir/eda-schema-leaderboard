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


def test_checks_actually_register() -> None:
    """Registration must land in the dict main() reads.

    Regression test for a real bug: `python -m tools.validate` runs the module as
    __main__, so tools.checks registered into a second, unrelated CHECKS dict and
    validation reported success having run nothing. The Makefile now calls the
    eda-validate entry point instead.
    """
    import tools.checks  # noqa: F401

    assert validate_mod.CHECKS, "no checks registered; validation would be a no-op"
    assert "baseline-csv" in validate_mod.CHECKS


def test_validate_passes_on_current_data() -> None:
    import tools.checks  # noqa: F401

    failures = validate_mod.validate()
    assert failures == [], "\n".join(str(f) for f in failures)


def test_validate_main_fails_loudly_on_empty_registry(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """An empty registry is a failure, not a pass."""
    monkeypatch.setattr(validate_mod, "CHECKS", {})
    assert validate_mod.main() == 1


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
