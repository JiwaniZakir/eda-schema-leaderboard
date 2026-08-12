"""Render the static site into dist/.

This is the only module in the project that has side effects. Everything it
renders was computed by a pure function in tools/, so the templates receive a
context dict that is already finished: no formatting, no arithmetic and no
vocabulary lookups happen inside a template.
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from tools import matrix

ROOT = Path(__file__).resolve().parent
TEMPLATE_DIR = ROOT / "templates"
STATIC_DIR = ROOT / "static"
THEME_DIR = STATIC_DIR / "css" / "themes"
DEFAULT_DIST = ROOT / "dist"

# A GitHub Pages project site is served under /<repo>/, so the deploy sets
# SITE_BASE. Phase 5 lifts this into tools/urls.py as BASE_PATH and every URL in
# the site is derived from that one string.
BASE_PATH = os.environ.get("SITE_BASE", "/")

DEFAULT_THEME = "drexel"


def selected_theme() -> str:
    """The theme named by THEME, validated against what is on disk.

    Raises rather than defaulting. An unknown name is a typo in a workflow, and
    a build that quietly shipped the wrong brand while exiting 0 is the failure
    mode this exists to prevent.
    """
    name = os.environ.get("THEME", DEFAULT_THEME)
    if not (THEME_DIR / f"{name}.css").is_file():
        available = ", ".join(sorted(p.stem for p in THEME_DIR.glob("*.css")))
        raise SystemExit(f"build: unknown THEME {name!r}; available: {available}")
    return name


def environment() -> Environment:
    """The Jinja2 environment.

    StrictUndefined is load-bearing. The default Undefined renders a missing key
    as an empty string, so a template reading cell.stat when the context carries
    cell.state produces a page full of blank cells and exits 0. Strict turns that
    into a build failure at the first cell.
    """
    return Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


def copy_assets(dist: Path, theme: str) -> None:
    """Copy static/ into the site, then the selected theme as theme.css.

    The themes directory itself is excluded. Publishing every theme would let a
    page link one that was never selected, and the a11y matrix would then test a
    stylesheet the deploy does not ship.
    """
    target = dist / "static"
    shutil.copytree(
        STATIC_DIR, target, ignore=shutil.ignore_patterns("themes"), dirs_exist_ok=True
    )
    shutil.copyfile(THEME_DIR / f"{theme}.css", target / "css" / "theme.css")


def build(dist: Path | None = None) -> Path:
    """Render the whole site. Returns the output directory."""
    out = DEFAULT_DIST if dist is None else dist
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    theme = selected_theme()
    env = environment()
    copy_assets(out, theme)
    _render_matrix(env, out)
    return out


def _render_matrix(env: Environment, out: Path) -> None:
    template = env.get_template("pages/matrix.html")
    (out / "index.html").write_text(
        template.render(base_path=BASE_PATH, panels=matrix.panels()),
        encoding="utf-8",
    )


def main() -> int:
    started = time.perf_counter()
    out = build()
    elapsed = time.perf_counter() - started
    print(f"build: wrote {out.relative_to(ROOT)} in {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
