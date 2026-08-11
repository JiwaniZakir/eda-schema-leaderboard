"""Render the static site into dist/.

One of the two places side effects are allowed, the other being CLI entry points.
Computation belongs in tools/; templates hold loops and conditionals only.

Scaffold state: emits a placeholder page so the deploy and size-guard workflows
have something real to act on. Phase 6 replaces this with the Jinja2 render.
"""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"

PLACEHOLDER = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EDA-Schema Leaderboard</title>
</head>
<body>
<h1>EDA-Schema Leaderboard</h1>
<p>Scaffold. The matrix lands in Phase 6.</p>
</body>
</html>
"""


def build() -> Path:
    """Render the site. Returns the output directory."""
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)
    (DIST / "index.html").write_text(PLACEHOLDER, encoding="utf-8")
    return DIST


def main() -> int:
    dist = build()
    files = sum(1 for p in dist.rglob("*") if p.is_file())
    size_kb = sum(p.stat().st_size for p in dist.rglob("*") if p.is_file()) / 1024
    print(f"build: {files} files, {size_kb:.1f} KB -> {dist.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
