# Phase 3 - Matrix Page Implementation Plan

> **For agentic workers:** Implement this plan task-by-task - either dispatch a fresh subagent per task (recommended) or execute inline with review checkpoints. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** put a real, useful page on GitHub Pages that renders all 880 live cells against 856 published baselines, before ingest, synthetic fill or any guard exists.

**Architecture:** `build.py` loads the Phase 1 registries and the Phase 2 baseline, asks `tools/matrix.py` for a fully computed context, renders `templates/pages/matrix.html` through Jinja2 into `dist/index.html`, and copies `static/` alongside it.
Templates hold loops and conditionals only.
Every number, every state string and every display label is computed in Python and arrives in the context dict already formatted.
One vanilla JS file switches stages as a progressive enhancement over a page that is complete without it.

**Tech stack:** Python 3.11+, `uv`, Jinja2, `pytest`, `mypy --strict`, `ruff`, vanilla JS, CSS custom properties, `lychee`, `pa11y-ci`.

## Global constraints

Copied from `PLAN.md` and `CLAUDE.md`; every task's requirements implicitly include these.

- Python **3.11+**, type hints on all public functions, `ruff` and `mypy` clean.
- **Registries are the only source of vocabulary.** No task, metric, stage, PDK or circuit id is written as a literal in `build.py`, in a template, in a stylesheet or in JavaScript. The five cell states are not registry vocabulary; they are a code-level enum and may be named in CSS.
- **Counts are derived, never literal.** Phase 1 ships an AST scan over `tools/` for the bare integers `46 232 880 856 120 24 40 920`, and it now also has to pass on `build.py`. `tests/` may assert them as expected values.
- **Percent metrics** (`mape`, `mape_p95`, `mape_top5`, `tpr`, `tnr`) are stored as fractions. The `x100` happens **exactly once, in this phase, in `tools/matrix.format_bound`**, and nowhere else. Not in a template, not in JavaScript, not in a second helper.
- **Every record carries an explicit `source`.** In this phase every value on the page is `paper`.
- `dist/` targets **~20 MB** and **no page exceeds 88 KB**. This phase measures that rather than assuming it, because the matrix is the single largest page the site will ever serve.
- CSS custom properties for all colour; both themes implement the same variable contract.
- Conventional commits. Branch `phase-3/matrix`. Never push to `main`.
- **Never use an em dash** in prose, code comments or generated copy.

## Inherited interfaces

Locked. If a signature below is wrong, adapt in one import line rather than reaching around it.

**Phase 1, `tools/registry.py`**

```python
reg.tasks() / metrics() / stages() / pdks() / circuits()   # tuples, stages IN ORDER
reg.task(id) / metric(id) / stage(id) / pdk(id)            # KeyError on unknown
reg.is_void(task_id, stage_id) -> bool
reg.is_degenerate(task_id, metric_id, stage_id) -> bool
reg.is_saturated(task_id, metric_id, stage_id) -> bool
reg.precision(task_id, metric_id) -> int                   # DISPLAY decimal places
reg.metric_rows() -> tuple[tuple[str, str], ...]           # 46
reg.live_combos() -> tuple[tuple[str, str, str], ...]      # 232, (task, pdk, stage)
reg.live_cells() -> tuple[tuple[str, str, str, str], ...]  # 880, (task, metric, pdk, stage)
```

`reg.stages()` is returned in `order`, so the stage strip is rendered straight from it and never sorted again.

**Phase 2, `tools/baseline.py`**

```python
@dataclass(frozen=True) class Bound: kind: BoundKind; value: float | None
# kind in {"exact", "greater_than", "less_than", "absent"}; value is None iff "absent"
bl.baseline(task_id, metric_id, pdk_id, stage_id) -> Baseline   # KeyError on a void cell
bl.baselines() -> dict[CellKey, Baseline]
Baseline.bound: Bound ; Baseline.baseline_state: str ; Baseline.source: str
```

A sentinel is a one-sided bound **in storage units**: `> 10000 %` is `Bound("greater_than", 100.0)` and `< -1` is `Bound("less_than", -1.0)`.
A sentinel always points **away** from the good direction, so `greater_than` only ever sits on a lower-is-better metric.
A degenerate cell is `Bound("absent", None)`.
A void cell has no entry at all, and `bl.baseline` raises for it.

The Phase 5 plan lists this function as `baseline.bound_for(...)`.
That is the same lookup under a different name; Phase 2 is authoritative and this phase calls `bl.baseline(...).bound`.

## What this phase de-risks

Read this before writing code. It is why the phase exists at this position in the plan rather than last.

- the 880-cell grid at real scale, including layout, scroll behaviour and page weight
- saturation, degeneracy and sentinels, which are three distinct visual cases that are easy to conflate into one grey cell
- the stage strip and the void rows, which are the two places the registry's structure becomes visible to a reader
- the percent boundary, exercised against 324 real published percent cells rather than against a fixture
- contrast and keyboard navigation, in both themes, against a page that actually has content

There are no submissions yet, so every live cell renders `no_entry` or `saturated`.
That is the point.
A grid that renders 856 real baselines correctly with zero entries is a working artifact; a grid that renders entries correctly but mistypes its baselines is not.

## Four traps, each of which produces a page that looks right

**A `<td>` per void cell is not "structurally absent".** Void is a `(task, stage)` fact, so at `floorplan` the two wirelength tasks contribute no rows at all: the floorplan panel has 36 metric rows, not 46. An empty cell in a 46-row table is a data gap, which is a different claim from "this measurement does not exist". The floorplan panel carries a short generated note naming the absent tasks, so the reader is told rather than left to notice.

**Percent inversion raises nothing.** If the `x100` lands twice, or lands at ingest instead of display, every MAPE cell reads `baseline_leads` and every TPR/TNR cell reads `beats_baseline`. Both are believable for models documented as undertrained. The defence is that exactly one function multiplies, it is called from exactly one place, and a test pins `Bound("exact", 0.1243)` rendering as `12.43 %` against the CSV's own printed string.

**"Degenerate cells never print a number" cannot be tested by counting digits.** The paper's own text for those cells is `No positive or negative error, n_p = n_n = 0`, which contains a digit, and the marker this phase renders is `0/0`, which contains two. The test asserts the structured fact instead: the bound kind is `absent`, the cell carries `data-baseline="degenerate"`, and its rendered text equals the one declared marker constant rather than any formatted number.

**A missing context key renders as nothing.** Jinja2's default `Undefined` prints an empty string, so a template reading `cell.stat` when `build.py` set `cell.state` produces 880 blank cells and no error. `StrictUndefined` is set on the environment in Task 1 and turns that entire class of bug into a build failure.

## The page

One document, five stage panels, 880 cells.

| Panel | Metric rows | Cells |
|---|---|---|
| floorplan | 36 | 144 |
| global_place | 46 | 184 |
| detailed_place | 46 | 184 |
| cts | 46 | 184 |
| global_route | 46 | 184 |

Rows are `(task, metric)` with the task label carried once per task on a `rowspan`ed `<th scope="rowgroup">`.
Columns are the four PDKs, in registry order.
Without JavaScript all five panels render stacked, each under its own caption, and the page is complete.
With JavaScript the stage strip unhides itself and collapses the page to one panel.

## Page weight, measured

The cap is a real constraint here, not a formality, so it was measured against the real CSV before this plan was written.

| Variant | Grid bytes |
|---|---|
| task label repeated on every row | 84.6 KiB |
| task label on a `rowspan`, plus a redundant `cell` class on every `<td>` | 78.8 KiB |
| **task label on a `rowspan`, state class only** | **74.4 KiB** |

Chrome (head, header, stage strip, legend, footer) adds roughly 5 KiB, so `dist/index.html` lands near **80 KiB against an 88 KiB cap**.

The margin is thin and it is thin in a direction that matters.
The same grid with every cell reading `matches_baseline` instead of `no_entry` measures **88.0 KiB of grid alone**, because the state class and the visually hidden state label both get longer.
So this page fits today and will not fit once the grid is populated with the longer state names.
The documented lever, to be taken in Phase 4 when it is measured again rather than pre-emptively now, is to move the stage panels to one page each at `/stage/<id>/`, which cuts `index.html` to 184 cells.
Task 6 asserts the cap so the day it is crossed is a red build and not a slow page.

## File structure

| File | Responsibility |
|---|---|
| `build.py` | the only module with side effects: load, compute, render, copy assets |
| `tools/matrix.py` | all computation for the grid: states, formatting, rows, panels, legend |
| `templates/base.html` | the shell: `{% block title %}`, `{% block head %}`, `{% block content %}` |
| `templates/pages/matrix.html` | loops and conditionals only |
| `static/css/base.css` | every rule; every colour a `var()` |
| `static/css/themes/drexel.css` | navy, gold, serif headings |
| `static/css/themes/neutral.css` | near-white ground, one accent, dense headers |
| `static/js/matrix.js` | stage switching, vanilla, one file, progressive enhancement |
| `tests/conftest.py` | the session-scoped `site` fixture, built once |
| `tests/test_matrix.py` | context, grid, states, palette, strip, budget |
| `pyproject.toml` | mypy picks up `build.py` |

Two things land in CI for free the moment this phase does, and both are expected rather than surprising:

- `.github/workflows/a11y.yml` triggers on `templates/**`, `static/css/**`, `static/js/**` and `build.py`, so **pa11y runs for the first time on this PR**, across both themes.
- `.github/workflows/codeql.yml` detects JavaScript by `git ls-files '*.js'` and adds an `analyze (javascript-typescript)` leg the moment `static/js/matrix.js` exists. That is a new check context on the PR. Branch protection currently requires seven contexts and this is an eighth, so it reports but does not gate until Phase 9 re-derives the required list.

---

### Task 1: The render skeleton and a real file in dist/

The smallest thing that puts bytes on Pages: an environment, a shell, one page, two themes, and a fixture that builds the site once per test session.

**Files:**
- Create: `build.py`, `templates/base.html`, `templates/pages/matrix.html`
- Create: `static/css/base.css`, `static/css/themes/drexel.css`, `static/css/themes/neutral.css`
- Create: `tests/conftest.py`, `tests/test_matrix.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: `tools.registry`.
- Produces: `build.BASE_PATH: str`, `build.selected_theme() -> str`, `build.environment() -> Environment`, `build.build(dist: Path | None = None) -> Path`, `build.main() -> int`.

- [ ] **Step 1: Write the failing tests**

Create `tests/conftest.py`:

```python
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
```

Create `tests/test_matrix.py`:

```python
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
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `uv run pytest tests/test_matrix.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'build'`

- [ ] **Step 3: Write build.py**

Create `build.py`:

```python
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
```

`matrix.panels()` does not exist yet. Task 2 writes it; for this task create `tools/matrix.py` containing only:

```python
"""Everything the matrix template is not allowed to do.

Pure functions. Task 2 fills these in; the signature does not change.
"""

from __future__ import annotations


def panels() -> tuple[object, ...]:
    return ()
```

- [ ] **Step 4: Write the shell and the page**

Create `templates/base.html`:

```jinja
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{% block title %}EDA-Schema leaderboard{% endblock %}</title>
<link rel="stylesheet" href="{{ base_path }}static/css/theme.css">
<link rel="stylesheet" href="{{ base_path }}static/css/base.css">
{% block head %}{% endblock %}
</head>
<body>
<a class="skip" href="#main">Skip to the matrix</a>
<header class="site-header">
<h1>EDA-Schema leaderboard</h1>
<p class="tagline">Published baselines from EDA-Schema-V2, arXiv:2605.06952.</p>
</header>
<main id="main">
{% block content %}{% endblock %}
</main>
<footer class="site-footer">
<p>Baseline values are the paper's Table 8. Source: <a href="https://arxiv.org/abs/2605.06952">arXiv:2605.06952</a>.</p>
</footer>
{% block scripts %}{% endblock %}
</body>
</html>
```

The theme is linked before `base.css` so a theme cannot accidentally win a specificity tie against a rule it is supposed to feed.

Create `templates/pages/matrix.html` as a skeleton this task can render; Task 3 fills the grid in:

```jinja
{% extends "base.html" %}
{% block content %}
<p class="intro">No submissions yet. Every cell shows the value the paper published for that baseline.</p>
{% endblock %}
```

- [ ] **Step 5: Write base.css and both themes**

Create `static/css/base.css` with the shell rules only for now. Every colour is a `var()`; a literal here renders correctly in one theme and illegibly in the other:

```css
/*
 * Base stylesheet. The only file that USES custom properties; the themes in
 * static/css/themes/ are the only files that DEFINE them. Phase 9 derives the
 * contract by diffing those two sets, so a colour literal here is a hole in it.
 */

*, *::before, *::after { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--ground);
  color: var(--text);
  font-family: var(--font-body);
  line-height: 1.45;
}

h1, h2, h3, caption { font-family: var(--font-heading); }

a { color: var(--link); }
a:visited { color: var(--link-visited); }

:focus-visible { outline: 3px solid var(--focus); outline-offset: 2px; }

.site-header, .site-footer, .intro { padding: 0.75rem 1rem; }
.site-footer { color: var(--text-muted); border-top: 1px solid var(--border); }
.tagline { color: var(--text-muted); margin: 0.25rem 0 0; }

.skip {
  position: absolute;
  left: -9999px;
  background: var(--accent);
  color: var(--accent-ink);
  padding: 0.5rem 0.75rem;
}
.skip:focus { left: 0.5rem; top: 0.5rem; z-index: 10; }

/* Visually hidden but announced. Used once per cell to carry the state name,
   which is otherwise only in the colour and the glyph. */
.vh {
  position: absolute;
  width: 1px;
  height: 1px;
  margin: -1px;
  padding: 0;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
  border: 0;
}
```

Create `static/css/themes/drexel.css`. Every ratio in a comment was computed with the WCAG 2.1 relative-luminance formula, and Phase 9 recomputes them from this file rather than trusting the comment:

```css
/*
 * Drexel. Navy #07294D, gold #FFC600, serif headings.
 *
 * Light ground on purpose. The matrix is 880 numeric cells and the brand navy
 * is chrome, not canvas: header band, table header, pill ink, focus ring. The
 * gold has exactly one job, the active stage pill, where navy on gold is
 * 9.30:1.
 *
 * The --state-*-key values are the shared four-state palette and are byte
 * identical in every theme.
 */

:root {
  --drexel-navy: #07294d;
  --drexel-gold: #ffc600;

  --font-body: ui-sans-serif, system-ui, "Helvetica Neue", Arial, sans-serif;
  --font-heading: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
  --font-mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, monospace;

  --ground: #ffffff;
  --surface: #f5f7fa;
  --surface-raised: #ffffff;
  --border: #c8d2de;          /* hairline, decorative */
  --border-strong: #78859a;   /* 3.48:1 on --surface, carries meaning */

  --text: #0b1f33;            /* 16.69:1 on --ground */
  --text-muted: #4a5a6b;      /* 6.60:1 on --surface */
  --link: #0a4c8c;            /* 8.66:1 on --ground */
  --link-visited: #5b3a8c;    /* 8.65:1 on --ground */

  --accent: var(--drexel-navy);
  --accent-ink: #ffffff;      /* 14.65:1 on --accent */
  --focus: var(--drexel-navy);

  --pill-bg: #e7ebf0;
  --pill-ink: var(--drexel-navy);         /* 12.24:1 on --pill-bg */
  --pill-active-bg: var(--drexel-gold);
  --pill-active-ink: var(--drexel-navy);  /* 9.30:1 on --pill-active-bg */

  --table-header-bg: var(--drexel-navy);
  --table-header-ink: #ffffff;            /* 14.65:1 */
  --table-header-pad: 0.55rem 0.7rem;
  --table-row-alt: #f0f3f7;
  --table-cell-pad: 0.45rem 0.6rem;

  --void-ink: #7f8d9e;        /* 3.38:1 on --ground */

  /* Shared four-state data palette. Okabe-Ito hues darkened until each clears
     3:1 on its own surface. IDENTICAL in every theme. */
  --state-beats-key: #007a5e;
  --state-matches-key: #0072b2;
  --state-leads-key: #c04a00;
  --state-none-key: #6b6b6b;
  --state-saturated-key: #5b6770;

  --state-beats-bg: #e3f3ec;
  --state-beats-ink: #10513c;      /* 8.08:1 ink, 4.64:1 key */
  --state-matches-bg: #e4eef7;
  --state-matches-ink: #0b4a75;    /* 7.94:1 ink, 4.41:1 key */
  --state-leads-bg: #fbe9de;
  --state-leads-ink: #8a3b00;      /* 6.58:1 ink, 4.22:1 key */
  --state-none-bg: #f2f4f6;
  --state-none-ink: #40505f;       /* 7.53:1 ink, 4.83:1 key */
  --state-saturated-bg: #e8eaed;
  --state-saturated-ink: #3f4a55;  /* 7.50:1 ink, 4.81:1 key */
}
```

Create `static/css/themes/neutral.css` with the same variable names and these values. The five `--state-*-key` lines are byte identical to drexel's, and Phase 9 asserts that equality:

```css
/*
 * Neutral. Near-white ground, near-black text, one accent, dense table headers.
 *
 * The restraint is the design: this is the theme for a reader who came to look
 * at 880 numbers, so nothing competes with them. One accent (#005ea2) does
 * links, focus and the active stage pill.
 */

:root {
  --font-body: ui-sans-serif, system-ui, "Helvetica Neue", Arial, sans-serif;
  --font-heading: ui-sans-serif, system-ui, "Helvetica Neue", Arial, sans-serif;
  --font-mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, monospace;

  --ground: #ffffff;
  --surface: #fafafa;
  --surface-raised: #ffffff;
  --border: #d4d4d4;
  --border-strong: #8a8a8a;   /* 3.31:1 on --surface */

  --text: #171717;            /* 17.93:1 on --ground */
  --text-muted: #525252;      /* 7.49:1 on --surface */
  --link: #005ea2;            /* 6.72:1 on --ground */
  --link-visited: #6b2fa0;    /* 8.27:1 on --ground */

  --accent: #005ea2;
  --accent-ink: #ffffff;      /* 6.72:1 on --accent */
  --focus: #005ea2;

  --pill-bg: #efefef;
  --pill-ink: #171717;               /* 15.59:1 on --pill-bg */
  --pill-active-bg: #005ea2;
  --pill-active-ink: #ffffff;        /* 6.72:1 */

  --table-header-bg: #efefef;
  --table-header-ink: #171717;       /* 15.59:1 */
  --table-header-pad: 0.25rem 0.5rem;
  --table-row-alt: #f5f5f5;
  --table-cell-pad: 0.3rem 0.5rem;

  --void-ink: #8e8e8e;        /* 3.28:1 on --ground */

  --state-beats-key: #007a5e;
  --state-matches-key: #0072b2;
  --state-leads-key: #c04a00;
  --state-none-key: #6b6b6b;
  --state-saturated-key: #5b6770;

  --state-beats-bg: #eaf6f1;
  --state-beats-ink: #0f5140;      /* 8.34:1 ink, 4.80:1 key */
  --state-matches-bg: #e8f1f8;
  --state-matches-ink: #0b4a75;    /* 8.16:1 ink, 4.54:1 key */
  --state-leads-bg: #fcede3;
  --state-leads-ink: #8a3b00;      /* 6.79:1 ink, 4.35:1 key */
  --state-none-bg: #f4f4f4;
  --state-none-ink: #4a4a4a;       /* 8.06:1 ink, 4.85:1 key */
  --state-saturated-bg: #eaeaea;
  --state-saturated-ink: #454545;  /* 7.97:1 ink, 4.82:1 key */
}
```

- [ ] **Step 6: Put build.py under the type checker**

In `pyproject.toml`, extend the mypy target list Phase 1 set:

```toml
[tool.mypy]
python_version = "3.11"
strict = true
warn_unreachable = true
files = ["tools", "tests", "build.py"]
```

The `Makefile` needs no change. Its `build` target already runs `uv run python build.py` and stops skipping the moment the file exists, and `check` already depends on `build`.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run pytest tests/test_matrix.py -v && uv run mypy && uv run ruff check .`
Expected: 4 passed, mypy clean, ruff clean.

- [ ] **Step 8: Look at it**

Run: `make serve` and open `http://localhost:8000/`
Expected: a titled page with the header, the intro line and the footer, in the drexel theme. This is the last step in the phase where looking at it is optional.

- [ ] **Step 9: Commit**

```bash
git add build.py tools/matrix.py templates static/css tests/conftest.py tests/test_matrix.py pyproject.toml
git commit -m "feat(build): render a themed shell page into dist"
```

---

### Task 2: The cell context, computed in Python

Everything the template is forbidden to do.
This is the task that owns the percent boundary, the sentinel rendering and the degenerate marker, and all three are pure functions testable without rendering a byte of HTML.

**Files:**
- Modify: `tools/matrix.py`
- Test: `tests/test_matrix.py`

**Interfaces:**
- Consumes: `tools.registry`, `tools.baseline`.
- Produces: `matrix.Cell`, `matrix.NO_ENTRY`, `matrix.SATURATED`, `matrix.STATE_LABELS`, `matrix.DEGENERATE_MARKER`, `matrix.format_bound(task_id, metric_id, bound) -> str`, `matrix.cell(task_id, metric_id, pdk_id, stage_id) -> Cell`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_matrix.py`, adding `from tools import baseline as bl`, `from tools import matrix` and `from tools import registry as reg` to the imports at the top:

```python
def test_a_plain_value_formats_at_the_registry_precision() -> None:
    """MAE on a design-level task is 2dp; on cell_arc_delay it is 4dp, which is
    the ground truth Phase 6's plausibility layer keys on."""
    assert matrix.format_bound(
        "total_area_prediction", "mae", bl.Bound("exact", 1781.97)
    ) == "1,781.97"
    assert matrix.format_bound(
        "cell_arc_delay_prediction", "mae", bl.Bound("exact", 0.0)
    ) == "0.0000"


def test_a_percent_metric_is_multiplied_by_one_hundred_here_and_only_here() -> None:
    """Storage is a fraction, display is a percent. Table 8 prints 12.43 %, and
    data/baseline.json holds 0.1243. This is the single conversion point in the
    project."""
    assert matrix.format_bound(
        "total_area_prediction", "mape", bl.Bound("exact", 0.1243)
    ) == "12.43 %"


def test_a_rate_at_its_ceiling_renders_as_one_hundred_percent() -> None:
    assert matrix.format_bound(
        "worst_slack_prediction", "tpr", bl.Bound("exact", 1.0)
    ) == "100.00 %"


def test_an_upper_sentinel_renders_its_comparator() -> None:
    """The paper thresholded the number away, so the cell shows a bound. A bare
    10,000.00 % would assert a measurement nobody made."""
    text = matrix.format_bound(
        "net_arc_delay_prediction", "mape", bl.Bound("greater_than", 100.0)
    )
    assert text.startswith(">")
    assert text == "> 10,000.00 %"


def test_a_lower_sentinel_renders_its_comparator() -> None:
    text = matrix.format_bound(
        "net_arc_delay_prediction", "r2", bl.Bound("less_than", -1.0)
    )
    assert text == "< -1.000"


def test_a_degenerate_bound_renders_the_marker_and_never_a_number() -> None:
    """0/0 is not 0. Formatting an absent bound as 0.00 would publish a baseline
    the paper explicitly says was never measured."""
    assert matrix.format_bound(
        "worst_slack_prediction", "mpe", bl.Bound("absent", None)
    ) == matrix.DEGENERATE_MARKER


def test_saturation_comes_from_the_registry_not_from_the_value() -> None:
    """A cell at global route with a 0.00 baseline is saturated because of where
    it sits, not because of what it says. total_wirelength also sits at global
    route and is NOT saturated, and its baseline MAE there is 13,698.67."""
    assert matrix.cell(
        "total_area_prediction", "mae", "ng45", "global_route"
    ).state == matrix.SATURATED
    live = matrix.cell("total_wirelength_prediction", "mae", "ng45", "global_route")
    assert live.state == matrix.NO_ENTRY
    assert live.display == "13,698.67"


def test_a_saturated_rate_is_still_saturated_at_one_hundred_percent() -> None:
    """16 of the 120 saturated cells are tpr/tnr at their ceiling. An
    is-the-error-near-zero test returns false on every one of them."""
    assert matrix.cell(
        "worst_slack_prediction", "tpr", "ng45", "global_route"
    ).state == matrix.SATURATED


def test_degeneracy_is_reported_separately_from_state() -> None:
    """State is about submissions; baseline_kind is about the paper. Collapsing
    them loses the difference between 'nobody has entered' and 'there is nothing
    to enter against'."""
    entry = matrix.cell("worst_slack_prediction", "mpe", "ng45", "global_route")
    assert entry.state == matrix.NO_ENTRY
    assert entry.baseline_kind == "degenerate"
    assert entry.display == matrix.DEGENERATE_MARKER


def test_the_three_baseline_kinds_partition_the_live_cells() -> None:
    """856 published, of which 32 are sentinels, plus 24 degenerate."""
    kinds = [matrix.cell(*key).baseline_kind for key in reg.live_cells()]
    assert kinds.count("sentinel") == 32
    assert kinds.count("degenerate") == 24
    assert kinds.count("published") == 824
    assert len(kinds) == 880


def test_a_void_cell_has_no_context_at_all() -> None:
    with pytest.raises(KeyError):
        matrix.cell("total_wirelength_prediction", "mae", "ng45", "floorplan")
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_matrix.py -v`
Expected: FAIL, `AttributeError: module 'tools.matrix' has no attribute 'format_bound'`

- [ ] **Step 3: Implement**

Replace `tools/matrix.py`:

```python
"""Everything the matrix template is not allowed to do.

Pure functions. build.py calls panels() once and renders the result; the
template loops over it and reads attributes. No formatting, no arithmetic and no
registry lookup happens inside a template.

THE PERCENT BOUNDARY LIVES HERE. Everything under data/ stores a percent-format
metric as a fraction, and format_bound multiplies by 100 exactly once on its way
to the screen. There is no second multiplication anywhere in the project, and
adding one makes every MAPE cell read as a loss and every TPR cell as a win, in
silence. See docs/DATA_CONTRACT.md, "Percent storage - the single authoritative
rule".
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache

from tools import baseline as bl
from tools import registry as reg

# The two cell states this phase can produce. Phase 4 introduces the full
# CellState enum with the three comparison states and replaces the one call in
# _state() below; nothing else changes.
NO_ENTRY = "no_entry"
SATURATED = "saturated"

STATE_LABELS = {
    NO_ENTRY: "No entry",
    SATURATED: "Saturated",
}

PUBLISHED = "published"
SENTINEL = "sentinel"
DEGENERATE = "degenerate"

# What a cell prints when the paper measured nothing. Table 8's own words are
# "No positive or negative error, n_p = n_n = 0", which the legend carries in
# full; the cell carries the short form. It is deliberately not "0.00" and
# deliberately not blank: one asserts a measurement, the other asserts a gap.
DEGENERATE_MARKER = "0/0"

COMPARATOR = {"greater_than": ">", "less_than": "<"}

PERCENT_SCALE = 100


@dataclass(frozen=True, slots=True)
class Cell:
    """One rendered cell.

    `state` is about submissions and drives the colour and the glyph.
    `baseline_kind` is about the paper and drives the three distinct baseline
    treatments. They are separate because a cell can be both `no_entry` and
    `degenerate`, and rendering those two facts through one channel loses the
    difference between "nobody has entered" and "there is nothing to enter
    against".
    """

    task: str
    metric: str
    pdk: str
    stage: str
    state: str
    state_label: str
    baseline_kind: str
    display: str


def format_bound(task_id: str, metric_id: str, bound: bl.Bound) -> str:
    """One bound as the string a reader sees.

    The ONLY place a percent-format metric is multiplied by 100, and the only
    place a sentinel's comparator is attached. A sentinel renders as its
    comparator plus its threshold, never as a bare number: the paper thresholded
    the underlying value away, so printing it without the comparator would claim
    a measurement that does not exist.
    """
    if bound.kind == "absent":
        return DEGENERATE_MARKER

    value = bound.value
    if value is None:
        raise ValueError(f"{task_id}/{metric_id}: a non-absent bound has no value")

    spec = reg.metric(metric_id)
    if spec.percent:
        value *= PERCENT_SCALE

    text = f"{value:,.{reg.precision(task_id, metric_id)}f}"
    if spec.percent:
        text = f"{text} %"

    comparator = COMPARATOR.get(bound.kind)
    return text if comparator is None else f"{comparator} {text}"


def _baseline_kind(bound: bl.Bound) -> str:
    if bound.kind == "absent":
        return DEGENERATE
    return SENTINEL if bound.kind in COMPARATOR else PUBLISHED


def _state(task_id: str, metric_id: str, stage_id: str) -> str:
    """Saturation is a stage-and-task rule, never a predicate over values.

    Phase 4 replaces this with ranking.cell_state once entries exist. Until then
    a cell is saturated or it is empty, because there is nothing to rank.
    """
    if reg.is_saturated(task_id, metric_id, stage_id):
        return SATURATED
    return NO_ENTRY


def cell(task_id: str, metric_id: str, pdk_id: str, stage_id: str) -> Cell:
    """One live cell. Raises KeyError on a void cell, via the baseline loader."""
    bound = bl.baseline(task_id, metric_id, pdk_id, stage_id).bound
    state = _state(task_id, metric_id, stage_id)
    return Cell(
        task=task_id,
        metric=metric_id,
        pdk=pdk_id,
        stage=stage_id,
        state=state,
        state_label=STATE_LABELS[state],
        baseline_kind=_baseline_kind(bound),
        display=format_bound(task_id, metric_id, bound),
    )
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_matrix.py -v`
Expected: 15 passed.

- [ ] **Step 5: Commit**

```bash
git add tools/matrix.py tests/test_matrix.py
git commit -m "feat(matrix): compute cell state, percent display and sentinel bounds"
```

---

### Task 3: The 880-cell grid

Five panels, 36 rows at floorplan and 46 everywhere else, and the void rows absent rather than empty.

**Files:**
- Modify: `tools/matrix.py`, `templates/pages/matrix.html`
- Test: `tests/test_matrix.py`

**Interfaces:**
- Consumes: `matrix.cell`, `reg.stages`, `reg.tasks`, `reg.pdks`.
- Produces: `matrix.Row`, `matrix.Panel`, `matrix.panels() -> tuple[Panel, ...]`, and the rendered contract `tbody td` with exactly one `state-<id>` class.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_matrix.py`, adding `import re` to the imports:

```python
CELL_RE = re.compile(r'<td class="state-([a-z_]+)"')


def test_the_grid_holds_one_cell_element_per_live_cell(index_html: str) -> None:
    """Derived from the registry, not from a literal in the template."""
    assert len(CELL_RE.findall(index_html)) == len(reg.live_cells())
    assert len(reg.live_cells()) == 880


def test_every_cell_carries_exactly_one_state_class(index_html: str) -> None:
    """A cell with two state classes renders in whichever colour lost the
    cascade, which is a coin toss that looks deliberate."""
    for found in CELL_RE.findall(index_html):
        assert found in {matrix.NO_ENTRY, matrix.SATURATED}
    assert '<td class="state-' in index_html
    assert re.search(r'<td class="state-\w+ state-', index_html) is None


def test_the_panels_are_the_registry_stages_in_order() -> None:
    assert tuple(p.stage_id for p in matrix.panels()) == tuple(
        s.id for s in reg.stages()
    )
    assert [s.order for s in reg.stages()] == [1, 2, 3, 4, 5]


def test_the_void_rows_are_structurally_absent_not_empty() -> None:
    """Void is a (task, stage) fact, so the two wirelength tasks contribute no
    rows at all at floorplan. An empty <td> would say the measurement is missing;
    an absent row says it does not exist."""
    floorplan = matrix.panels()[0]
    assert floorplan.stage_id == "floorplan"
    tasks_present = {row.task_id for row in floorplan.rows}
    assert "total_wirelength_prediction" not in tasks_present
    assert "interconnect_length_prediction" not in tasks_present
    assert len(tasks_present) == 10


def test_the_per_panel_cell_counts_match_the_partition() -> None:
    """144 + 184 * 4 = 880. Asserting only the total would pass while a void row
    moved from floorplan to another stage."""
    counts = [sum(len(row.cells) for row in p.rows) for p in matrix.panels()]
    assert counts == [144, 184, 184, 184, 184]
    assert sum(counts) == 880


def test_the_saturated_cells_are_all_in_the_last_panel() -> None:
    per_panel = [
        sum(1 for row in p.rows for c in row.cells if c.state == matrix.SATURATED)
        for p in matrix.panels()
    ]
    assert per_panel == [0, 0, 0, 0, 120]


def test_the_task_label_is_carried_once_per_task(index_html: str) -> None:
    """46 rows per panel, 12 task labels. Repeating the label on every row costs
    6 KiB against an 88 KB cap, which this page cannot spare."""
    spans = [row.task_rowspan for row in matrix.panels()[1].rows]
    assert sum(1 for n in spans if n) == 12
    assert sum(spans) == 46
    assert index_html.count('scope="rowgroup"') == 58


def test_no_cell_renders_a_python_repr_or_a_non_number(index_html: str) -> None:
    """The failure this catches is a None that reached a format string and a
    context key the template read but build.py never set."""
    for token in ("None", "nan", "NaN", "undefined", "null", "Undefined"):
        assert token not in index_html
    assert "<td class=\"state-no_entry\"></td>" not in index_html
```

`58` is `12 + 10 + 12 * 4 - 12`, which is the twelve task labels on four full panels plus ten on floorplan. Write it as the literal in the test and let the assertion be the check; the template derives it.

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_matrix.py -v`
Expected: FAIL, `AttributeError: module 'tools.matrix' has no attribute 'panels'` on the panel tests and `AssertionError: 0 == 880` on the grid count.

- [ ] **Step 3: Build the rows and panels**

Append to `tools/matrix.py`:

```python
@dataclass(frozen=True, slots=True)
class Row:
    """One metric row within one stage panel.

    `task_rowspan` is the number of rows the task label spans, and it is 0 on
    every row after the first of its task. The template renders the label header
    only when it is non-zero, which is a conditional rather than a computation.
    """

    task_id: str
    task_label: str
    task_rowspan: int
    metric_id: str
    metric_label: str
    cells: tuple[Cell, ...]


@dataclass(frozen=True, slots=True)
class Panel:
    """One stage. Rendered as one table, captioned with the stage transition."""

    stage_id: str
    stage_label: str
    caption: str
    void_tasks: tuple[str, ...]
    rows: tuple[Row, ...]


@cache
def panels() -> tuple[Panel, ...]:
    """The whole grid, in registry order.

    Driven from reg.stages(), reg.tasks() and each task's own metric list, so a
    row exists because the registry says the cell is live and never because a
    template iterated something convenient.
    """
    built: list[Panel] = []
    for stage in reg.stages():
        rows: list[Row] = []
        for task in reg.tasks():
            if reg.is_void(task.id, stage.id):
                continue
            for index, metric_id in enumerate(task.metrics):
                rows.append(
                    Row(
                        task_id=task.id,
                        task_label=task.label,
                        task_rowspan=len(task.metrics) if index == 0 else 0,
                        metric_id=metric_id,
                        metric_label=reg.metric(metric_id).label,
                        cells=tuple(
                            cell(task.id, metric_id, p.id, stage.id)
                            for p in reg.pdks()
                        ),
                    )
                )
        built.append(
            Panel(
                stage_id=stage.id,
                stage_label=stage.label,
                caption=stage.table8_label,
                void_tasks=tuple(
                    reg.task(t).label for t in stage.void_tasks
                ),
                rows=tuple(rows),
            )
        )
    return tuple(built)
```

- [ ] **Step 4: Render the grid**

Replace the content block in `templates/pages/matrix.html`. Loops and conditionals only; every string it prints was computed in `tools/matrix.py`:

```jinja
{% extends "base.html" %}
{% block content %}
<p class="intro">No submissions yet. Every cell shows the value the paper published for that baseline.</p>
{% for panel in panels %}
<section class="panel" id="stage-{{ panel.stage_id }}" data-stage-panel="{{ panel.stage_id }}" aria-labelledby="caption-{{ panel.stage_id }}" tabindex="0">
<table>
<caption id="caption-{{ panel.stage_id }}">{{ panel.caption }}</caption>
{% if panel.void_tasks %}
<tr class="void-note"><td colspan="6">Not estimated at this stage, so these tasks have no rows here: {{ panel.void_tasks | join(", ") }}. Cells are not yet placed, so there is no half-perimeter wirelength to measure.</td></tr>
{% endif %}
<thead>
<tr><th scope="col">Task</th><th scope="col">Metric</th>{% for pdk in pdks %}<th scope="col">{{ pdk.label }}</th>{% endfor %}</tr>
</thead>
<tbody>
{% for row in panel.rows %}
<tr>{% if row.task_rowspan %}<th scope="rowgroup" rowspan="{{ row.task_rowspan }}">{{ row.task_label }}</th>{% endif %}<th scope="row">{{ row.metric_label }}</th>{% for cell in row.cells %}<td class="state-{{ cell.state }}"{% if cell.baseline_kind != "published" %} data-baseline="{{ cell.baseline_kind }}"{% endif %}>{{ cell.display }}<span class="vh">{{ cell.state_label }}</span></td>{% endfor %}</tr>
{% endfor %}
</tbody>
</table>
</section>
{% endfor %}
{% endblock %}
```

The cell line is deliberately unwrapped.
Jinja preserves the whitespace between tags, and 880 cells of indentation is 4 KiB of a budget with 8 KiB of headroom.

Pass `pdks` into the context. In `build.py`'s `_render_matrix`:

```python
template.render(
    base_path=BASE_PATH,
    panels=matrix.panels(),
    pdks=reg.pdks(),
)
```

and add `from tools import registry as reg` to `build.py`'s imports.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_matrix.py -v`
Expected: 23 passed.

- [ ] **Step 6: Commit**

```bash
git add tools/matrix.py templates/pages/matrix.html build.py tests/test_matrix.py
git commit -m "feat(matrix): render all 880 live cells across five stage panels"
```

---

### Task 4: The palette, the glyph channel and the three baseline cases

Colour is one channel and it is not available to every reader.
Windows high contrast mode strips background colour outright, so the glyph is not decoration: it is the channel that survives.

**Files:**
- Modify: `static/css/base.css`, `templates/pages/matrix.html`, `tools/matrix.py`
- Test: `tests/test_matrix.py`

**Interfaces:**
- Consumes: the theme variable contract.
- Produces: a legend in the context (`matrix.legend() -> tuple[LegendItem, ...]`), and the CSS contract `.state-<id>::before` carrying a distinct glyph per state.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_matrix.py`:

```python
CSS = Path(__file__).resolve().parent.parent / "static" / "css" / "base.css"
GLYPH_RE = re.compile(r"\.state-([a-z_]+)::before\s*\{[^}]*content:\s*\"([^\"]*)\"")


def test_every_state_has_a_glyph_and_no_two_states_share_one() -> None:
    """Four states distinguishable WITHOUT colour. If two states share a glyph,
    the second channel is decorative and a colourblind reader is back to one."""
    glyphs = dict(GLYPH_RE.findall(CSS.read_text(encoding="utf-8")))
    assert len(glyphs) == 5, glyphs
    assert len(set(glyphs.values())) == 5, glyphs
    assert set(glyphs) == {
        "beats_baseline",
        "matches_baseline",
        "baseline_leads",
        matrix.NO_ENTRY,
        matrix.SATURATED,
    }


def test_the_glyph_colour_comes_from_the_state_key_variable() -> None:
    """The --state-*-key values are the shared palette. A glyph painted with the
    ink colour instead would drift from the legend."""
    css = CSS.read_text(encoding="utf-8")
    for key in ("beats", "matches", "leads", "none", "saturated"):
        assert f"var(--state-{key}-key)" in css


def test_saturated_degenerate_and_sentinel_are_three_distinct_treatments(
    index_html: str,
) -> None:
    """The three cases are easy to conflate into one grey cell, and conflating
    them tells a reader that an unmeasurable baseline and a perfect one are the
    same thing."""
    assert 'data-baseline="degenerate"' in index_html
    assert 'data-baseline="sentinel"' in index_html
    assert index_html.count('data-baseline="degenerate"') == 24
    assert index_html.count('data-baseline="sentinel"') == 32
    css = CSS.read_text(encoding="utf-8")
    assert '[data-baseline="degenerate"]' in css
    assert '[data-baseline="sentinel"]' in css


def test_no_sentinel_cell_prints_a_bare_number(index_html: str) -> None:
    """Every sentinel keeps its comparator all the way to the page."""
    sentinels = re.findall(
        r'<td class="state-\w+" data-baseline="sentinel">([^<]*)<', index_html
    )
    assert len(sentinels) == 32
    assert all(text.startswith((">", "&gt;", "<", "&lt;")) for text in sentinels)


def test_every_degenerate_cell_prints_the_marker(index_html: str) -> None:
    degenerate = re.findall(
        r'<td class="state-\w+" data-baseline="degenerate">([^<]*)<', index_html
    )
    assert len(degenerate) == 24
    assert set(degenerate) == {matrix.DEGENERATE_MARKER}


def test_the_legend_names_every_state_and_both_baseline_cases() -> None:
    ids = [item.id for item in matrix.legend()]
    assert len(ids) == len(set(ids))
    assert matrix.SATURATED in ids
    assert matrix.DEGENERATE in ids
    assert matrix.SENTINEL in ids
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_matrix.py -v`
Expected: FAIL, `AssertionError: {}` on the glyph test, because `base.css` has no state rules yet.

- [ ] **Step 3: Write the state rules**

Append to `static/css/base.css`:

```css
/* ---- the grid ---- */

.panel { overflow-x: auto; padding: 0 1rem 1.5rem; }
.panel table { border-collapse: collapse; width: 100%; }
.panel caption { text-align: left; padding: 0.6rem 0; font-size: 1.1rem; }

.panel thead th {
  position: sticky;
  top: 0;
  background: var(--table-header-bg);
  color: var(--table-header-ink);
  padding: var(--table-header-pad);
  text-align: right;
}
.panel thead th:first-child, .panel thead th:nth-child(2) { text-align: left; }

.panel tbody th {
  text-align: left;
  padding: var(--table-cell-pad);
  background: var(--surface);
  color: var(--text);
  font-weight: 600;
  border-block-end: 1px solid var(--border);
  vertical-align: top;
}
.panel tbody th[scope="rowgroup"] { background: var(--table-row-alt); }

.panel tbody td {
  padding: var(--table-cell-pad);
  text-align: right;
  border: 1px solid var(--border);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.void-note td {
  padding: var(--table-cell-pad);
  color: var(--text-muted);
  border-inline-start: 4px solid var(--void-ink);
  text-align: left;
  white-space: normal;
}

/* ---- the four data states, plus saturated ----
 *
 * Two channels, always. The background carries the colour and the ::before
 * glyph carries the shape, because a colourblind reader loses the first and a
 * high contrast mode strips it entirely. The glyph is generated rather than
 * written into the markup: 880 inline spans would cost 8 KiB of an 88 KB page.
 */

.panel tbody td::before {
  margin-inline-end: 0.4em;
  font-weight: 700;
  speak: never;
}

.state-beats_baseline { background: var(--state-beats-bg); color: var(--state-beats-ink); }
.state-beats_baseline::before { content: "\25B2"; color: var(--state-beats-key); }

.state-matches_baseline { background: var(--state-matches-bg); color: var(--state-matches-ink); }
.state-matches_baseline::before { content: "\003D"; color: var(--state-matches-key); }

.state-baseline_leads { background: var(--state-leads-bg); color: var(--state-leads-ink); }
.state-baseline_leads::before { content: "\25BC"; color: var(--state-leads-key); }

.state-no_entry { background: var(--state-none-bg); color: var(--state-none-ink); }
.state-no_entry::before { content: "\00B7"; color: var(--state-none-key); }

.state-saturated { background: var(--state-saturated-bg); color: var(--state-saturated-ink); }
.state-saturated::before { content: "\25C6"; color: var(--state-saturated-key); }

/* ---- the two baseline cases that are NOT states ----
 *
 * Orthogonal to the state above, and rendered through a different channel on
 * purpose. A degenerate cell has no baseline to compare against; a sentinel has
 * a threshold instead of a value. Neither is a verdict about a submission.
 */

td[data-baseline="degenerate"] {
  outline: 2px dotted var(--void-ink);
  outline-offset: -3px;
  font-style: italic;
}

td[data-baseline="sentinel"] {
  font-family: var(--font-mono);
  border-inline-start: 3px solid var(--border-strong);
}

/* ---- legend ---- */

.legend { display: flex; flex-wrap: wrap; gap: 1rem; padding: 0 1rem 1rem; margin: 0; }
.legend div { display: flex; gap: 0.4rem; align-items: baseline; }
.legend dt { padding: 0.1rem 0.5rem; border: 1px solid var(--border); }
.legend dd { margin: 0; color: var(--text-muted); }
```

The three comparison states have no cells on the page yet.
They are styled now anyway, because pa11y can only test a colour it can see, and a state that first renders in Phase 4 would otherwise ship unreviewed.
Phase 9's contrast check computes all five from this file regardless of what the page currently contains, which is the other half of that defence.

- [ ] **Step 4: Add the legend to the context and the page**

Append to `tools/matrix.py`:

```python
@dataclass(frozen=True, slots=True)
class LegendItem:
    """One legend row. `id` doubles as the class the swatch carries, so the
    swatch is painted by the same rule as the cells it explains and the two
    cannot drift."""

    id: str
    label: str
    explanation: str


@cache
def legend() -> tuple[LegendItem, ...]:
    return (
        LegendItem(NO_ENTRY, STATE_LABELS[NO_ENTRY], "No submission for this cell yet."),
        LegendItem(
            SATURATED,
            STATE_LABELS[SATURATED],
            "The tool estimate already matches the detailed route value, so this"
            " cell can be tied but not beaten and is never ranked.",
        ),
        LegendItem(
            DEGENERATE,
            DEGENERATE_MARKER,
            "The paper reports no positive or negative error, n_p = n_n = 0."
            " That is an undefined quantity, not a value of zero, so there is no"
            " baseline to compare against.",
        ),
        LegendItem(
            SENTINEL,
            "> or <",
            "The paper published a threshold rather than a value, so the true"
            " number is not recoverable from any source we have.",
        ),
    )
```

In `templates/pages/matrix.html`, above the panels:

```jinja
<dl class="legend">
{% for item in legend %}
<div><dt class="state-{{ item.id }}">{{ item.label }}</dt><dd>{{ item.explanation }}</dd></div>
{% endfor %}
</dl>
```

and pass `legend=matrix.legend()` in `_render_matrix`.

The degenerate and sentinel legend entries carry no `state-` class in CSS, so their `dt` renders unstyled by the state rules and styled by `.legend dt`. That is correct: neither is a state.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_matrix.py -v`
Expected: 29 passed.

- [ ] **Step 6: Commit**

```bash
git add static/css/base.css tools/matrix.py templates/pages/matrix.html build.py tests/test_matrix.py
git commit -m "feat(matrix): add the colourblind-safe state palette and glyph channel"
```

---

### Task 5: The stage strip

Real buttons, real `aria-pressed`, and a page that is complete before the script runs.

**Files:**
- Modify: `templates/pages/matrix.html`, `static/css/base.css`, `build.py`
- Create: `static/js/matrix.js`
- Test: `tests/test_matrix.py`

**Interfaces:**
- Consumes: `reg.stages()`.
- Produces: the DOM contract `button.stage-pill[data-stage][aria-pressed]` inside `[data-stage-strip]`, and `section[data-stage-panel]`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_matrix.py`:

```python
PILL_RE = re.compile(
    r'<button class="stage-pill" type="button" data-stage="([a-z_]+)"'
    r' aria-pressed="(true|false)"'
)


def test_the_stage_pills_are_real_buttons_in_registry_order(index_html: str) -> None:
    """A div with a click handler is not a button: it is not focusable, it does
    not fire on Enter or Space, and it announces as nothing."""
    found = PILL_RE.findall(index_html)
    assert [stage for stage, _ in found] == [s.id for s in reg.stages()]


def test_exactly_one_pill_is_pressed(index_html: str) -> None:
    pressed = [stage for stage, state in PILL_RE.findall(index_html) if state == "true"]
    assert pressed == [reg.stages()[0].id]


def test_every_pill_targets_a_panel_that_exists(index_html: str) -> None:
    panels = set(re.findall(r'data-stage-panel="([a-z_]+)"', index_html))
    assert panels == {stage for stage, _ in PILL_RE.findall(index_html)}
    assert len(panels) == 5


def test_no_panel_is_hidden_in_the_markup(index_html: str) -> None:
    """Without JavaScript the page must be complete. Shipping four panels with a
    hidden attribute and unhiding them in a script means a reader with a blocked
    script sees one fifth of the grid and no way to reach the rest."""
    assert "data-stage-panel" in index_html
    assert not re.search(r"<section[^>]*data-stage-panel[^>]*\shidden", index_html)


def test_the_strip_itself_is_hidden_until_the_script_runs(index_html: str) -> None:
    """The inverse rule for a control: a button that does nothing without
    JavaScript should not be offered."""
    assert re.search(r"<div[^>]*data-stage-strip[^>]*\shidden", index_html)


def test_the_script_names_no_registry_vocabulary() -> None:
    """Stage ids reach JavaScript through data attributes only. A stage id
    written into a script is a second copy of the registry that nothing checks."""
    js = (Path(__file__).resolve().parent.parent / "static" / "js" / "matrix.js")
    text = js.read_text(encoding="utf-8")
    for stage in reg.stages():
        assert stage.id not in text
    for pdk in reg.pdks():
        assert pdk.id not in text
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_matrix.py -v`
Expected: FAIL, `AssertionError: [] == ['floorplan', ...]` - the strip is not rendered yet.

- [ ] **Step 3: Render the strip**

In `templates/pages/matrix.html`, above the legend:

```jinja
<div class="stage-strip" data-stage-strip role="group" aria-label="Stage transition" hidden>
{% for stage in stages %}
<button class="stage-pill" type="button" data-stage="{{ stage.id }}" aria-pressed="{{ "true" if loop.first else "false" }}">{{ stage.label }}</button>
{% endfor %}
</div>
```

and pass `stages=reg.stages()` in `_render_matrix`.

Add the `<script>` to the page, deferred so it never blocks the grid:

```jinja
{% block scripts %}
<script src="{{ base_path }}static/js/matrix.js" defer></script>
{% endblock %}
```

- [ ] **Step 4: Write the switcher**

Create `static/js/matrix.js`:

```js
/*
 * Stage switching for the matrix.
 *
 * A progressive enhancement over a page that is already complete: the markup
 * ships all five stage panels visible and the control hidden, and this script
 * reverses that. If it fails to load, a reader scrolls five captioned tables
 * instead of clicking between them, which is a worse experience and not a
 * broken one.
 *
 * No stage id appears in this file. The vocabulary lives in data/registry/ and
 * reaches here only through the data attributes build.py rendered, so a stage
 * added or renamed upstream cannot leave a stale copy behind.
 */

(function () {
  "use strict";

  const strip = document.querySelector("[data-stage-strip]");
  const panels = Array.from(document.querySelectorAll("[data-stage-panel]"));
  if (!strip || panels.length === 0) {
    return;
  }

  const buttons = Array.from(strip.querySelectorAll("button[data-stage]"));
  if (buttons.length === 0) {
    return;
  }

  function show(stageId) {
    panels.forEach(function (panel) {
      panel.hidden = panel.dataset.stagePanel !== stageId;
    });
    buttons.forEach(function (button) {
      button.setAttribute(
        "aria-pressed",
        button.dataset.stage === stageId ? "true" : "false"
      );
    });
  }

  function stageFromHash() {
    const requested = window.location.hash.replace(/^#stage-/, "");
    return buttons.some(function (button) {
      return button.dataset.stage === requested;
    })
      ? requested
      : buttons[0].dataset.stage;
  }

  buttons.forEach(function (button) {
    button.addEventListener("click", function () {
      const stageId = button.dataset.stage;
      show(stageId);
      // replaceState, not a hash assignment: assigning scrolls the panel under
      // the sticky header, and it fills the back button with stage switches.
      window.history.replaceState(null, "", "#stage-" + stageId);
    });
  });

  window.addEventListener("hashchange", function () {
    show(stageFromHash());
  });

  strip.hidden = false;
  show(stageFromHash());
})();
```

- [ ] **Step 5: Style the strip**

Append to `static/css/base.css`:

```css
.stage-strip { display: flex; flex-wrap: wrap; gap: 0.4rem; padding: 0.75rem 1rem; }

.stage-pill {
  font: inherit;
  padding: 0.4rem 0.9rem;
  border: 1px solid var(--border-strong);
  border-radius: 999px;
  background: var(--pill-bg);
  color: var(--pill-ink);
  cursor: pointer;
}

.stage-pill[aria-pressed="true"] {
  background: var(--pill-active-bg);
  color: var(--pill-active-ink);
  border-color: var(--pill-active-bg);
  font-weight: 700;
}
```

The pressed pill differs by weight as well as colour, so the active stage is legible without it.

- [ ] **Step 6: Run the tests, then use it**

Run: `uv run pytest tests/test_matrix.py -v`
Expected: 35 passed.

Run: `make serve` and open `http://localhost:8000/`
Expected: five pills, one active; clicking each swaps the panel; the URL gains `#stage-<id>`; reloading on that URL lands on the same stage; tabbing reaches every pill and Space activates it. Then disable JavaScript and reload: five stacked tables, no pills.

- [ ] **Step 7: Commit**

```bash
git add static/js/matrix.js static/css/base.css templates/pages/matrix.html build.py tests/test_matrix.py
git commit -m "feat(matrix): switch stages from a real button strip, JS optional"
```

---

### Task 6: The budget, the timing and the whole gate

The three assertions that turn "it looks fine" into something CI can hold.

**Files:**
- Test: `tests/test_matrix.py`

**Interfaces:**
- Consumes: the built site.
- Produces: nothing.

- [ ] **Step 1: Write the tests**

Append to `tests/test_matrix.py`:

```python
PAGE_CAP_BYTES = 88 * 1024
BUILD_CAP_SECONDS = 60


def test_no_page_exceeds_the_budget(site: Path) -> None:
    """Measured, not assumed. The grid was 74.4 KiB when this phase shipped and
    the same grid with every cell reading matches_baseline measures 88.0 KiB, so
    this assertion is expected to bite in Phase 4. When it does, the fix is one
    page per stage at /stage/<id>/, not a bigger number here."""
    oversized = {
        str(path.relative_to(site)): path.stat().st_size
        for path in site.rglob("*.html")
        if path.stat().st_size > PAGE_CAP_BYTES
    }
    assert oversized == {}


def test_the_build_completes_inside_a_minute(tmp_path: Path) -> None:
    started = time.perf_counter()
    build.build(tmp_path / "timed")
    assert time.perf_counter() - started < BUILD_CAP_SECONDS


def test_the_site_is_reproducible(tmp_path: Path) -> None:
    """Two builds, byte identical. A build that varies run to run turns every
    deploy diff into noise and hides a real change inside it."""
    first = (build.build(tmp_path / "a") / "index.html").read_bytes()
    second = (build.build(tmp_path / "b") / "index.html").read_bytes()
    assert first == second


def test_every_asset_the_page_links_exists(site: Path, index_html: str) -> None:
    """lychee catches this in CI, but only on a PR that touched a watched path.
    A local assertion fails in the same second the link breaks."""
    refs = re.findall(r'(?:href|src)="([^"]+)"', index_html)
    internal = [r for r in refs if not r.startswith(("http", "#", "mailto:"))]
    assert internal, "the page links no local assets"
    for ref in internal:
        assert (site / ref.lstrip("/")).is_file(), ref
```

Add `import time` to the imports.

- [ ] **Step 2: Run them**

Run: `uv run pytest tests/test_matrix.py -v`
Expected: 39 passed. If the budget test fails, print the size first (`du -b dist/index.html`) and reduce markup rather than raising the cap.

- [ ] **Step 3: Run the external gates**

```bash
make build
npx --yes lychee dist/
uv run python -m http.server -d dist 8080 &
npx --yes pa11y-ci --config .pa11yci.json
THEME=neutral uv run python build.py && npx --yes pa11y-ci --config .pa11yci.json
```

Expected: lychee reports zero broken links; pa11y-ci passes WCAG2AA on both themes.
`.pa11yci.json` already points at `http://localhost:8080/`, which is this page, so no config change is needed in this phase.

- [ ] **Step 4: Run the full gate and show the output**

Run: `make check`
Expected: `lint`, `typecheck`, `validate` (2 checks, 0 failures), `test` and `build` all pass, ending in `check passed`.

Do not report this task complete from reading the code. Paste the output.

- [ ] **Step 5: Commit**

```bash
git add tests/test_matrix.py
git commit -m "test(matrix): assert the page budget, the build time and asset links"
```

---

### Task 7: Ship it, click it, and pin the open decision

The exit criterion for this phase is not "the build succeeded".
It is a live URL that a human has used.

**Files:**
- Test: `tests/test_matrix.py`
- Modify: `PLAN.md`

**Interfaces:**
- Consumes: everything above.
- Produces: a deployed page.

- [ ] **Step 1: Pin the twelve cells that are optimal at CTS**

This is **open decision 3 in `PLAN.md`, and it is not resolved here.**
Twelve cells are already at the theoretical optimum at `CTS` and can only be tied, never beaten.
The saturation rule is anchored on `global_route`, so it does not cover them, and once submissions exist they will render as permanently `baseline_leads`.

Verified against `docs/sources/table8_baseline.csv`, they are exactly:

| Task | Metric | PDKs | Published |
|---|---|---|---|
| `total_area_prediction` | `r2` | all four | 1.000 |
| `total_power_prediction` | `r2` | ng45, ihp130, asap7 | 1.000 |
| `cell_arc_delay_prediction` | `mae` | ihp130, asap7 | 0.0000 |
| `worst_slack_prediction` | `tpr` | ng45, asap7 | 100.00 % |
| `worst_slack_prediction` | `mpe` | asap7 | 0.00 |

Four options, for the maintainer and not for this phase: extend saturation to any baseline-optimal cell, add a sixth state, accept the twelve, or defer until Phase 4 shows what a real submission does to them.
Pin the current behaviour so whichever ruling lands has to change a test on purpose:

```python
def test_the_cts_optimal_cells_are_not_saturated_yet() -> None:
    """PLAN.md open decision 3, deliberately unresolved.

    Twelve cells are at the theoretical optimum at CTS and can only be tied. The
    saturation rule is anchored on global_route, so it does not reach them and
    they will render as permanently baseline_leads once entries exist. This test
    pins today's behaviour rather than endorsing it: a ruling that extends
    saturation must change this test, and it will not pass by accident.
    """
    optimal = [
        ("total_area_prediction", "r2", "ng45"),
        ("total_area_prediction", "r2", "sky130"),
        ("total_area_prediction", "r2", "ihp130"),
        ("total_area_prediction", "r2", "asap7"),
        ("total_power_prediction", "r2", "ng45"),
        ("total_power_prediction", "r2", "ihp130"),
        ("total_power_prediction", "r2", "asap7"),
        ("cell_arc_delay_prediction", "mae", "ihp130"),
        ("cell_arc_delay_prediction", "mae", "asap7"),
        ("worst_slack_prediction", "tpr", "ng45"),
        ("worst_slack_prediction", "tpr", "asap7"),
        ("worst_slack_prediction", "mpe", "asap7"),
    ]
    assert len(optimal) == 12
    for task_id, metric_id, pdk_id in optimal:
        entry = matrix.cell(task_id, metric_id, pdk_id, "cts")
        assert not reg.is_saturated(task_id, metric_id, "cts")
        assert entry.state == matrix.NO_ENTRY
```

Run: `uv run pytest tests/test_matrix.py -v`
Expected: 40 passed.

- [ ] **Step 2: Open the PR**

```bash
git add tests/test_matrix.py
git commit -m "test(matrix): pin the twelve CTS-optimal cells pending a ruling"
git push -u origin phase-3/matrix
gh pr create --title "Phase 3: the matrix page" --body "Renders all 880 live cells against 856 published baselines into dist/index.html, with five stage panels, a colourblind-safe state palette on a glyph channel, and stage switching as a progressive enhancement. Void rows are structurally absent, the 24 degenerate cells print a marker rather than a number, and the 32 sentinel cells keep their comparator. Percent metrics are multiplied by 100 in exactly one function. First PR to exercise the a11y workflow, and it adds a CodeQL javascript-typescript leg."
```

- [ ] **Step 3: Watch every check**

Run: `gh pr checks --watch`
Expected: `size`, `analyze (python)`, `analyze (javascript-typescript)`, `lint`, `typecheck`, `validate`, `test`, `build`, `pa11y (drexel)`, `pa11y (neutral)` and `lychee` all green.
The two pa11y legs and the JavaScript CodeQL leg are running for the first time in this repository's history, so read their logs rather than only their status.

- [ ] **Step 4: Merge and deploy**

```bash
gh pr merge --squash
gh run watch
curl -sI https://jiwanizakir.github.io/eda-schema-leaderboard/ | head -1
```

Expected: `HTTP/2 200`.

- [ ] **Step 5: Click through all five stages, as a human**

Open the live URL and check, in both themes:

- every stage pill switches the grid, and the pressed one is obvious without relying on its colour
- the floorplan panel is visibly shorter than the others and says why
- the 24 degenerate cells read `0/0` and are visually distinct from the saturated cells around them
- the 32 sentinel cells read `> 10,000.00 %` or `< -1.000`, never a bare number
- no cell is blank, and none reads `None`, `NaN` or `nan`
- Tab reaches the skip link, every pill and each panel's scroll region, and the focus ring is visible on all of them
- the page is usable at 320 px wide, where the panels scroll horizontally rather than the page

**This step is the phase's exit criterion.** A green build is not a substitute for it.

- [ ] **Step 6: Record what the live page settled**

In `PLAN.md`, under Phase 3, note the measured page weight and whether open decision 3 still reads the same way against a real grid.
Leave the decision open unless the maintainer ruled on it; recording an opinion as a resolution is how the first build acquired three documents that disagreed.

---

## Phase gate

Every item must pass before Phase 4 starts.

```bash
make check
```

- [ ] `dist/index.html` contains exactly 880 cell elements, counted from `reg.live_cells()` and never from a literal in a template
- [ ] every cell carries exactly one `state-<id>` class, and it is one of the registry-derived states
- [ ] the 40 void cells are structurally absent: floorplan has 36 metric rows and the two wirelength tasks contribute none
- [ ] per-panel counts assert 144 / 184 / 184 / 184 / 184, not just the 880 total
- [ ] the 24 degenerate cells print the marker and never a formatted number, and carry `data-baseline="degenerate"`
- [ ] the 32 sentinel cells keep their comparator and carry `data-baseline="sentinel"`
- [ ] saturated, degenerate and sentinel are three distinct visual treatments, asserted from the shipped CSS
- [ ] all five states have a distinct glyph, and no two share one
- [ ] percent metrics are multiplied by 100 in exactly one function: `0.1243` renders `12.43 %`
- [ ] zero cells render `undefined`, `NaN`, `null` or an empty string
- [ ] the stage pills are real `<button>` elements with `aria-pressed`, in registry order, exactly one pressed
- [ ] no panel is `hidden` in the markup and the strip is, so the page is complete without JavaScript
- [ ] `static/js/matrix.js` contains no stage, PDK, task or metric id
- [ ] no page exceeds 88 KB, and `make build` completes in under 60 s
- [ ] two builds are byte identical
- [ ] `lychee dist/` reports zero broken links
- [ ] `pa11y-ci` passes WCAG2AA on both `THEME=drexel` and `THEME=neutral`
- [ ] no count literal appears in `tools/` or `build.py`
- [ ] **the page is live on GitHub Pages and a human has clicked through all five stages in both themes**

## Review prompt

```
Use a frontend reviewer on dist/, static/css/, static/js/matrix.js and
templates/ against PLAN.md Phase 3 and docs/DATA_CONTRACT.md.

Check, in both themes:
- contrast is at least 4.5:1 for the text of every cell state, and at least
  3:1 for each state's glyph key colour, computed from the shipped CSS rather
  than from the comments in it
- every state is distinguishable without colour, and no two states share a glyph
- the table is keyboard navigable: the skip link works, every stage pill is
  reachable and operable by Space and Enter, each scrollable panel is focusable,
  and the focus ring is visible on all of them
- the stage pills are real buttons carrying aria-pressed, exactly one pressed
- the page is complete and usable with JavaScript disabled

Then confirm the three cases that are easy to conflate are NOT rendered
identically: a saturated cell, a degenerate cell and a sentinel cell. Name the
channel that separates each pair. Confirm no sentinel renders as a bare number
and no degenerate cell renders as 0.00.

Independently of the test suite, verify that the x100 for percent metrics
happens in exactly one function, that no template or JavaScript file performs
any arithmetic on a value, and that no stage, PDK, task or metric id appears in
a stylesheet or a script.

Report only WCAG AA failures, case conflations and correctness gaps. Do not
report style preferences.
```
