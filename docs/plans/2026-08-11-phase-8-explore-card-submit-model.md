# Phase 8 - Explore, Card, Submit and Model Pages Implementation Plan

> **For agentic workers:** Implement this plan task-by-task - either dispatch a fresh subagent per task (recommended) or execute inline with review checkpoints. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ship the four remaining pages - `/explore/`, `/about/card/`, `/submit/` and `/model/?id=` - and the architecture renderer that the model page depends on.

**Architecture:** three of the four pages are rendered at build time from the registries, the baseline and the ingested shards, exactly like the matrix and cell pages. `/model/?id=` is the one exception: it is a single static shell hydrated in the browser from `dist/data/models/<id>.json`, because pre-rendering one page per submission grows without bound while the shell does not. Everything that has to be *correct* is computed in Python and emitted as data - the explore payload, the display strings, the architecture geometry, the guard badges - so `pytest` is the thing that checks it. The JavaScript scrolls, filters and draws; it never computes a number the site publishes.

**Tech stack:** Python 3.11+, `uv`, Jinja2, `markdown-it-py`, `pytest`, `mypy --strict`, `ruff`, vanilla ES modules, CSS custom properties.

## Global constraints

Copied from `PLAN.md`; every task's requirements implicitly include these.

- Python **3.11+**, type hints on all public functions, `ruff` and `mypy` clean.
- **Registries are the only source of vocabulary.** Never hardcode a task, PDK, stage, metric or circuit name outside `data/registry/`.
- **Counts are derived, never literal.** 46, 232, 880, 856, 120, 40, 24 are computed and asserted, never written into source.
- **Percent metrics** (`mape`, `mape_p95`, `mape_top5`, `tpr`, `tnr`) are stored as fractions in `[0, 1]`. The `x100` happens exactly once, at the display boundary, in **one** module. This phase adds the second consumer of that module, so Task 1 pins the "exactly one" with a test.
- **Every record carries an explicit `source`** (`paper`, `synthetic`, `submission`).
- Templates hold loops and conditionals only. All computation lands in the context dict from `build.py`.
- Vanilla JS, **one file per feature** in `static/js/`. Prefer a small focused new file over extending a large one. No framework, no bundler, no Node.
- **CSS custom properties for all colour.** Both themes implement the same variable contract.
- `dist/` targets **~20 MB**; the per-page budget is roughly **88 KB**. Measured, not assumed.
- Conventional commits. Branch `phase-8/explore-card-submit-model`. Never push to `main`.
- **Never use an em dash** in prose, code comments or generated copy.

## What this phase consumes

Locked interfaces from earlier phases. If a name below differs from what actually landed, adapt the import and say so in the PR body. Do not write a second implementation.

| From | Interface |
|---|---|
| Phase 1 | `tools/registry.py`: `reg.tasks()`, `reg.metrics()`, `reg.stages()`, `reg.pdks()`, `reg.circuits()`, `reg.task/metric/stage/pdk(id)`, `reg.is_void/is_degenerate/is_saturated`, `reg.precision(task, metric)`, `reg.metric_rows()`, `reg.live_combos()`, `reg.live_cells()` |
| Phase 2 | `data/baseline.json` and `Bound(kind: exact \| greater_than \| less_than \| absent, value: float \| None)` |
| Phase 3 | `build.py`, `templates/base.html`, `static/css/base.css`, `static/css/themes/*.css`, and the display formatter the matrix already uses |
| Phase 4 | `tools/ranking.py`, `tools/ckpt.py` (recovers tensor shapes without unpickling) |
| Phase 6 | `tools/guard/` and its per-layer results |

## File structure

| File | Responsibility |
|---|---|
| `tools/explore.py` | flat record rows, the filter specification, the compact payload |
| `tools/card.py` | `docs/CARD.yaml` loader; raises `CardError` on a missing required section |
| `tools/markdown.py` | one Markdown renderer, HTML and typographer both off |
| `tools/submission.py` | tiers, divisions and badges as data, keyed on guard layer ids |
| `tools/arch.py` | `Architecture`, `Layer`, `param_count`, `from_shapes` |
| `tools/archlayout.py` | block geometry; the renderer draws what this returns |
| `tools/modelpage.py` | per-model payloads, id validation, guard badge assembly |
| `docs/CARD.yaml` | the leaderboard card, eight required sections |
| `docs/SUBMISSION.md` | the submission guide `CLAUDE.md` referenced before it existed |
| `templates/pages/explore.html` | filter controls and the table shell |
| `templates/pages/card.html` | one loop over the card's sections |
| `templates/pages/submit.html` | rendered `SUBMISSION.md` plus generated tables |
| `templates/pages/model.html` | the hydration shell |
| `static/js/explore-filter.js` | pure selection over integer columns, no DOM |
| `static/js/virtual-table.js` | fixed-row-height windowed `<tbody>` |
| `static/js/explore.js` | wiring: fetch, controls, cross-check, render |
| `static/js/arch-render.js` | SVG from a precomputed layout |
| `static/js/model.js` | `?id=` hydration |
| `static/css/explore.css`, `static/css/arch.css` | layout only; colour via the variable contract |
| `tests/test_explore.py` | rows, five filter axes, payload, measured size |
| `tests/test_card.py` | required sections, licensing structure, build failure |
| `tests/test_submit.py` | guard-layer consistency, `predict.py` signature, links |
| `tests/test_arch_render.py` | params, overlap, degradation, badge provenance |
| `tests/test_pages.py` | the four pages build, links resolve, budgets hold |

---

### Task 1: The explore payload

`/explore/` is a flat table of every record. This task builds the rows and the payload, with no page yet, because the filter semantics and the payload budget are the two things that can be wrong in a way the eye will not catch.

Two decisions are made here and they are the reason this task exists separately.

**Display strings are formatted in Python, not in the browser.** Formatting a cell needs the per-`(task, metric)` precision, the `x100` for percent metrics and the sentinel rendering for the 32 bounded cells. Doing that in JavaScript would put a second implementation of the percent convention into the project, which is the exact failure the data contract spends a page warning about. 880 pre-formatted strings cost roughly 9 KB. That is the cheaper side of the trade by a wide margin.

**There is no posting-list index.** Five axes over 880 rows is a linear scan of 880 integer comparisons per keystroke, which is not measurable. An inverted index would be five times larger than the columns it accelerates.

**Files:**
- Create: `tools/explore.py`
- Test: `tests/test_explore.py`

**Interfaces:**
- Consumes: `tools.registry`, `data/baseline.json` via the Phase 2 loader, the Phase 4 shards, and the Phase 3 display formatter.
- Produces: `explore.AXES: tuple[str, ...]`, `explore.Row`, `explore.rows() -> tuple[Row, ...]`, `explore.filter_rows(rows: Sequence[Row], **active: str) -> tuple[Row, ...]`, `explore.payload(rows: Sequence[Row]) -> dict[str, Any]`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_explore.py`:

```python
"""The flat record table behind /explore/.

filter_rows is the SPECIFICATION for static/js/explore-filter.js. These tests are
the only place either implementation is checked against an expectation, so there
is one test per filter axis and they assert partitions rather than totals.
"""

from __future__ import annotations

import json

from tools import explore
from tools import registry as reg


def test_every_live_cell_has_a_baseline_row() -> None:
    """The row count is derived from the registry, never written down."""
    paper = explore.filter_rows(explore.rows(), source="paper")
    assert len(paper) == len(reg.live_cells())


def test_sources_partition_the_row_set() -> None:
    all_rows = explore.rows()
    seen: set[int] = set()
    for source in {r.source for r in all_rows}:
        selected = explore.filter_rows(all_rows, source=source)
        ids = {id(r) for r in selected}
        assert not (ids & seen), f"{source} overlaps another source"
        seen |= ids
    assert len(seen) == len(all_rows)


def test_filter_by_task() -> None:
    all_rows = explore.rows()
    for task in reg.tasks():
        selected = explore.filter_rows(all_rows, task=task.id)
        assert selected, task.id
        assert {r.task for r in selected} == {task.id}
    assert sum(
        len(explore.filter_rows(all_rows, task=t.id)) for t in reg.tasks()
    ) == len(all_rows)


def test_filter_by_metric() -> None:
    all_rows = explore.rows()
    for metric in reg.metrics():
        selected = explore.filter_rows(all_rows, metric=metric.id)
        assert selected, metric.id
        assert {r.metric for r in selected} == {metric.id}


def test_filter_by_pdk() -> None:
    all_rows = explore.rows()
    for pdk in reg.pdks():
        selected = explore.filter_rows(all_rows, pdk=pdk.id)
        assert selected, pdk.id
        assert {r.pdk for r in selected} == {pdk.id}
    assert sum(
        len(explore.filter_rows(all_rows, pdk=p.id)) for p in reg.pdks()
    ) == len(all_rows)


def test_filter_by_stage() -> None:
    """Floorplan carries fewer rows than the other four, because the two
    wirelength tasks are void there. A stage filter that returns equal counts
    everywhere is matching on a prefix."""
    all_rows = explore.rows()
    counts = {
        s.id: len(explore.filter_rows(all_rows, stage=s.id)) for s in reg.stages()
    }
    assert all(counts.values())
    assert counts["floorplan"] < counts["global_place"]


def test_filter_by_source() -> None:
    all_rows = explore.rows()
    for source in {r.source for r in all_rows}:
        selected = explore.filter_rows(all_rows, source=source)
        assert {r.source for r in selected} == {source}


def test_filters_compose_across_axes() -> None:
    all_rows = explore.rows()
    both = explore.filter_rows(
        all_rows, task="total_area_prediction", pdk="ng45", source="paper"
    )
    assert both
    assert {(r.task, r.pdk, r.source) for r in both} == {
        ("total_area_prediction", "ng45", "paper")
    }


def test_an_unknown_axis_raises_rather_than_matching_everything() -> None:
    import pytest

    with pytest.raises(KeyError):
        explore.filter_rows(explore.rows(), circuit="ac97_ctrl")


def test_no_row_displays_undefined_nan_or_null() -> None:
    for row in explore.rows():
        assert row.display
        assert row.display.lower() not in {"nan", "none", "null", "undefined"}


def test_degenerate_rows_never_print_a_number() -> None:
    """A degenerate cell is 0/0, not zero. Printing 0.00 there would claim a
    measurement the paper explicitly says does not exist."""
    degenerate = [
        r for r in explore.rows() if reg.is_degenerate(r.task, r.metric, r.stage)
    ]
    assert degenerate
    for row in degenerate:
        assert row.value is None
        assert not any(ch.isdigit() for ch in row.display)


def test_payload_counts_agree_with_the_filter() -> None:
    """These counts are what static/js/explore-filter.js checks itself against on
    every page load. If they are wrong the runtime cross-check is worthless."""
    all_rows = explore.rows()
    data = explore.payload(all_rows)
    for axis in explore.AXES:
        for code, (value, _label) in enumerate(data["axes"][axis]):
            assert data["counts"][axis][code] == len(
                explore.filter_rows(all_rows, **{axis: value})
            )


def test_payload_columns_are_all_the_same_length() -> None:
    data = explore.payload(explore.rows())
    lengths = {name: len(col) for name, col in data["columns"].items()}
    assert len(set(lengths.values())) == 1, lengths
    assert next(iter(lengths.values())) == len(explore.rows())


def test_payload_codes_index_their_vocabulary() -> None:
    data = explore.payload(explore.rows())
    for axis in explore.AXES:
        size = len(data["axes"][axis])
        assert all(0 <= code < size for code in data["columns"][axis])


def test_payload_size_is_measured_not_assumed() -> None:
    """Printed so the number is visible in the run, asserted so it cannot creep.
    Run with -s to read it."""
    encoded = json.dumps(explore.payload(explore.rows()), separators=(",", ":"))
    kib = len(encoded.encode("utf-8")) / 1024
    print(f"explore payload: {kib:.1f} KiB")
    assert kib < 120


def test_percent_conversion_has_exactly_one_home() -> None:
    """The single highest-risk convention in the project. This phase adds the
    second consumer of the formatter, which is exactly when a convenience copy
    gets made."""
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "tools"
    pattern = re.compile(r"(\*\s*100(?!\d))|(100\s*\*)|(/\s*100(?!\d))")
    offenders = sorted(
        path.name
        for path in root.rglob("*.py")
        if pattern.search(
            "\n".join(line.split("#", 1)[0] for line in path.read_text().splitlines())
        )
    )
    assert len(offenders) <= 1, f"percent conversion is in more than one module: {offenders}"
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `uv run pytest tests/test_explore.py -v`
Expected: FAIL, `ImportError: cannot import name 'explore' from 'tools'`

- [ ] **Step 3: Implement the rows**

Create `tools/explore.py`:

```python
"""The flat record table behind /explore/.

One row per (task, metric, pdk, stage, entry): the published baseline for every
live cell, plus one row per submission entry. The five filter axes are the five
dimensions a reader already knows from the matrix, plus source.

Every string this module emits is display-ready. Formatting happens here, in
Python, because it needs the per-(task, metric) precision, the percent
convention and the sentinel bounds, and a second implementation of any of those
in the browser is how the percent bug comes back.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from tools import baseline, display
from tools import registry as reg

AXES: tuple[str, ...] = ("task", "metric", "pdk", "stage", "source")


@dataclass(frozen=True, slots=True)
class Row:
    task: str
    metric: str
    pdk: str
    stage: str
    source: str
    entry: str
    state: str
    value: float | None
    display: str


def _baseline_rows() -> list[Row]:
    """One row per live cell. 856 carry a published number, 24 are degenerate."""
    out: list[Row] = []
    for task_id, metric_id, pdk_id, stage_id in reg.live_cells():
        bound = baseline.lookup(task_id, metric_id, pdk_id, stage_id).bound
        degenerate = reg.is_degenerate(task_id, metric_id, stage_id)
        out.append(
            Row(
                task=task_id,
                metric=metric_id,
                pdk=pdk_id,
                stage=stage_id,
                source="paper",
                entry="Table 8 baseline",
                state="saturated"
                if reg.is_saturated(task_id, metric_id, stage_id)
                else ("degenerate" if degenerate else "baseline"),
                value=None if degenerate else bound.value,
                display=display.display_bound(task_id, metric_id, bound),
            )
        )
    return out
```

`_submission_rows()` walks the Phase 4 shards and emits one row per entry per metric, with `state` taken from `tools.ranking` so the explore table and the matrix can never disagree about who won. `rows()` concatenates the two and is `@cache`d.

- [ ] **Step 4: Implement the filter and the payload**

```python
def filter_rows(all_rows: Sequence[Row], **active: str) -> tuple[Row, ...]:
    """Select rows matching every named axis.

    An axis absent from `active`, or passed as the empty string, is
    unconstrained. An axis that is not one of AXES raises, deliberately: a
    silently ignored filter name returns the whole table, which reads as a
    working filter that happens to match everything.

    THIS IS THE SPECIFICATION for static/js/explore-filter.js. That file is a
    transcription of this loop over integer columns, and it checks itself against
    the counts emitted by payload() on every page load.
    """
    unknown = set(active) - set(AXES)
    if unknown:
        raise KeyError(f"unknown filter axis {sorted(unknown)}")
    return tuple(
        row
        for row in all_rows
        if all(getattr(row, axis) == want for axis, want in active.items() if want)
    )


def _axis_vocabularies(all_rows: Sequence[Row]) -> dict[str, list[tuple[str, str]]]:
    """(value, label) pairs per axis, in registry order for the four grid axes.

    Registry order matters: stages read floorplan to global_route, not
    alphabetically, and a select box that reorders them misrepresents a sequence
    the reader is meant to follow.
    """
    present = {axis: {getattr(r, axis) for r in all_rows} for axis in AXES}
    return {
        "task": [(t.id, t.label) for t in reg.tasks() if t.id in present["task"]],
        "metric": [(m.id, m.label) for m in reg.metrics() if m.id in present["metric"]],
        "pdk": [(p.id, p.label) for p in reg.pdks() if p.id in present["pdk"]],
        "stage": [(s.id, s.label) for s in reg.stages() if s.id in present["stage"]],
        "source": [(s, SOURCE_LABELS[s]) for s in SOURCE_ORDER if s in present["source"]],
    }


def payload(all_rows: Sequence[Row]) -> dict[str, Any]:
    """Column-oriented and dictionary-encoded, because 880 repetitions of
    "total_negative_slack_prediction" is most of what a naive row-of-objects
    payload weighs."""
    axes = _axis_vocabularies(all_rows)
    codes = {
        axis: {value: i for i, (value, _) in enumerate(axes[axis])} for axis in AXES
    }
    entries = _vocabulary(r.entry for r in all_rows)
    states = _vocabulary(r.state for r in all_rows)
    return {
        "version": 1,
        "axes": axes,
        "entries": entries.values,
        "states": states.values,
        "columns": {
            **{
                axis: [codes[axis][getattr(r, axis)] for r in all_rows]
                for axis in AXES
            },
            "entry": [entries.code[r.entry] for r in all_rows],
            "state": [states.code[r.state] for r in all_rows],
            "value": [r.value for r in all_rows],
            "display": [r.display for r in all_rows],
        },
        "counts": {
            axis: [
                len(filter_rows(all_rows, **{axis: value})) for value, _ in axes[axis]
            ]
            for axis in AXES
        },
        "cell_href": "/cell/{task}/{pdk}/{stage}/",
    }
```

`counts` is computed by calling `filter_rows` itself. That is the point: it makes the number the browser checks against the output of the function these tests pin, so the JavaScript filter is verified against the Python specification on every page load without a Node test runner in the repo.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_explore.py -v -s`
Expected: 17 passed, and a printed payload size in the 30 to 40 KiB range

- [ ] **Step 6: Verify lint and types**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy`
Expected: all clean

- [ ] **Step 7: Commit**

```bash
git add tools/explore.py tests/test_explore.py
git commit -m "feat(explore): add the flat record table, filter spec and payload"
```

---

### Task 2: The explore page

Three JavaScript files, each one feature. `explore-filter.js` is pure selection with no DOM access, `virtual-table.js` is a windowed `<tbody>` that knows nothing about the data, and `explore.js` wires them to the controls.

**Files:**
- Create: `templates/pages/explore.html`, `static/js/explore-filter.js`, `static/js/virtual-table.js`, `static/js/explore.js`, `static/css/explore.css`
- Modify: `build.py`
- Test: `tests/test_explore.py`

**Interfaces:**
- Consumes: `tools.explore.payload`.
- Produces: `dist/explore/index.html`, `dist/data/explore.json`. `explore-filter.js` exports `AXES`, `selectRows(columns, active)`, `crossCheck(payload)`. `virtual-table.js` exports `class VirtualTable`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_explore.py`:

```python
def test_explore_page_is_built(built_dist) -> None:
    assert (built_dist / "explore" / "index.html").is_file()
    assert (built_dist / "data" / "explore.json").is_file()


def test_the_page_ships_no_row_markup(built_dist) -> None:
    """Rows are rendered by virtual-table.js from the payload. If they are also
    in the HTML the page carries the table twice and the budget is gone."""
    html = (built_dist / "explore" / "index.html").read_text(encoding="utf-8")
    assert html.count("<tr") <= 2, "header row and nothing else"


def test_every_filter_axis_has_a_labelled_control(built_dist) -> None:
    html = (built_dist / "explore" / "index.html").read_text(encoding="utf-8")
    for axis in explore.AXES:
        assert f'id="filter-{axis}"' in html, axis
        assert f'for="filter-{axis}"' in html, f"{axis} has no label"


def test_the_table_declares_its_true_row_count(built_dist) -> None:
    """aria-rowcount is what keeps a virtualized table traversable. Without it
    assistive technology reports only the rows currently in the DOM."""
    html = (built_dist / "explore" / "index.html").read_text(encoding="utf-8")
    assert f'aria-rowcount="{len(explore.rows())}"' in html


def test_javascript_needs_no_bundler(built_dist) -> None:
    """A bare specifier is the thing that would require one. Relative and root
    paths resolve natively."""
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "static" / "js"
    for path in root.glob("*.js"):
        for spec in re.findall(r"""\bfrom\s+["']([^"']+)["']""", path.read_text()):
            assert spec.startswith(("./", "../", "/")), f"{path.name} imports {spec}"


def test_the_filter_module_touches_no_dom(built_dist) -> None:
    """It is a transcription of a Python function. Keeping it DOM-free is what
    keeps that claim checkable by reading it."""
    from pathlib import Path

    source = (
        Path(__file__).resolve().parent.parent / "static" / "js" / "explore-filter.js"
    ).read_text()
    for forbidden in ("document", "window", "innerHTML"):
        assert forbidden not in source, forbidden
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_explore.py -v`
Expected: FAIL, `fixture 'built_dist' not found`, or `FileNotFoundError` on `dist/explore/index.html` once the fixture exists

If Phase 3 did not already add a `built_dist` fixture, create `tests/conftest.py`:

```python
"""Shared fixtures.

built_dist renders the whole site once per session into a temp directory. Tests
read files out of it rather than out of dist/, so a stale dist/ from a previous
run can never make a test pass.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

import build


@pytest.fixture(scope="session")
def built_dist(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    dest = tmp_path_factory.mktemp("dist")
    build.build_site(dest)
    yield dest
```

- [ ] **Step 3: Write the filter module**

Create `static/js/explore-filter.js`:

```js
// Pure selection over the integer columns emitted by tools/explore.py.
//
// No DOM access lives in this file, deliberately. It is the one part of
// /explore/ that has to stay provably equivalent to a Python function, and the
// repo has no Node test runner, so the equivalence is maintained two ways: the
// file is small enough to read against tools.explore.filter_rows, and
// crossCheck() re-derives every single-axis count and compares it to the number
// Python computed at build time.

export const AXES = ["task", "metric", "pdk", "stage", "source"];

const UNCONSTRAINED = -1;

/**
 * Row indices matching every constrained axis, ascending.
 *
 * @param {Object<string, number[]>} columns
 * @param {Object<string, number>} active axis to code, or -1 for unconstrained
 * @returns {number[]}
 */
export function selectRows(columns, active) {
  const constrained = AXES.filter((axis) => active[axis] !== UNCONSTRAINED);
  const total = columns.task.length;
  const out = [];
  for (let i = 0; i < total; i += 1) {
    let keep = true;
    for (const axis of constrained) {
      if (columns[axis][i] !== active[axis]) {
        keep = false;
        break;
      }
    }
    if (keep) {
      out.push(i);
    }
  }
  return out;
}

/** An `active` map with every axis unconstrained. */
export function noFilter() {
  return Object.fromEntries(AXES.map((axis) => [axis, UNCONSTRAINED]));
}

/**
 * Compare this module against the counts tools/explore.py computed with
 * filter_rows. Returns a list of disagreements; empty means the two agree.
 *
 * Roughly 35 single-axis passes over the row set, which is not measurable, and
 * it runs on every page load. Prefer failing loudly: explore.js renders an error
 * banner instead of the table if this returns anything.
 */
export function crossCheck(payload) {
  const problems = [];
  for (const axis of AXES) {
    const expected = payload.counts[axis];
    for (let code = 0; code < expected.length; code += 1) {
      const active = noFilter();
      active[axis] = code;
      const got = selectRows(payload.columns, active).length;
      if (got !== expected[code]) {
        const value = payload.axes[axis][code][0];
        problems.push(`${axis}=${value}: browser ${got}, build ${expected[code]}`);
      }
    }
  }
  return problems;
}
```

- [ ] **Step 4: Write the virtual table**

Create `static/js/virtual-table.js`:

```js
// A fixed-row-height windowed <tbody>. One file, no dependencies, no knowledge
// of what a row contains.
//
// 880 rows do not need this. Submissions do: the row count grows with every
// entry and the page budget does not.
//
// The two spacer rows are what keep the scrollbar honest without absolute
// positioning, which would take the rows out of the table's layout and break
// column alignment.

export class VirtualTable {
  /**
   * @param {{scroller: HTMLElement, tbody: HTMLElement, rowHeight: number,
   *          overscan?: number, renderRow: (index: number) => HTMLTableRowElement,
   *          columnCount: number}} options
   */
  constructor({ scroller, tbody, rowHeight, overscan = 8, renderRow, columnCount }) {
    this.scroller = scroller;
    this.tbody = tbody;
    this.rowHeight = rowHeight;
    this.overscan = overscan;
    this.renderRow = renderRow;
    this.columnCount = columnCount;
    this.indices = [];
    this.frame = 0;
    this.scroller.addEventListener("scroll", () => this.schedule(), { passive: true });
    window.addEventListener("resize", () => this.schedule(), { passive: true });
  }

  setRows(indices) {
    this.indices = indices;
    this.scroller.scrollTop = 0;
    this.render();
  }

  schedule() {
    if (this.frame) return;
    this.frame = window.requestAnimationFrame(() => {
      this.frame = 0;
      this.render();
    });
  }

  spacer(height) {
    const tr = document.createElement("tr");
    tr.setAttribute("aria-hidden", "true");
    tr.className = "virtual-spacer";
    const td = document.createElement("td");
    td.colSpan = this.columnCount;
    td.style.height = `${height}px`;
    tr.appendChild(td);
    return tr;
  }

  render() {
    const total = this.indices.length;
    const windowRows = Math.ceil(this.scroller.clientHeight / this.rowHeight);
    const first = Math.max(
      0,
      Math.floor(this.scroller.scrollTop / this.rowHeight) - this.overscan,
    );
    const last = Math.min(total, first + windowRows + this.overscan * 2);

    const frag = document.createDocumentFragment();
    frag.appendChild(this.spacer(first * this.rowHeight));
    for (let slot = first; slot < last; slot += 1) {
      const tr = this.renderRow(this.indices[slot]);
      // +2 because aria-rowindex is 1-based and the header occupies row 1.
      tr.setAttribute("aria-rowindex", String(slot + 2));
      frag.appendChild(tr);
    }
    frag.appendChild(this.spacer((total - last) * this.rowHeight));
    this.tbody.replaceChildren(frag);
  }
}
```

- [ ] **Step 5: Write the wiring, the template and the CSS**

`static/js/explore.js` fetches `/data/explore.json`, runs `crossCheck` and bails to a visible banner if it disagrees, builds the five `<select>` elements' options from `payload.axes` with the count appended to each label, and rebuilds rows on `change`. Rows are built with `document.createElement` and `textContent` only. Never `innerHTML`: entry names come from submissions, which are untrusted input, and this is the page that renders the most of them.

`templates/pages/explore.html` extends `base.html` and contains the five labelled selects, a live region for the result count, the table head, an empty `<tbody>`, and a `<noscript>` block linking to the matrix and to `/data/explore.json`. It carries `aria-rowcount` from the context dict. No loop over rows.

`static/css/explore.css` sets `--explore-row-height` and the scroller height. Every colour is an existing theme variable; this file introduces none.

- [ ] **Step 6: Wire it into build.py**

`build.py` gains one call that renders the template and writes `dist/data/explore.json` with `json.dumps(..., separators=(",", ":"))`. Compact separators are worth about 15 percent here and cost nothing.

- [ ] **Step 7: Run the tests**

Run: `uv run pytest tests/test_explore.py -v`
Expected: 23 passed

- [ ] **Step 8: Click through it**

Run: `make serve` and open `http://localhost:8000/explore/`
Check: all five filters narrow the table, the count updates, no console error, and scrolling to the bottom reaches the last row rather than empty space.

- [ ] **Step 9: Commit**

```bash
git add templates/pages/explore.html static/js/explore-filter.js static/js/virtual-table.js static/js/explore.js static/css/explore.css build.py tests/test_explore.py tests/conftest.py
git commit -m "feat(explore): add the flat table with five filters and virtual scroll"
```

---

### Task 3: The leaderboard card

`/about/card/` is rendered from `docs/CARD.yaml`, and **a missing required section fails the build**. Not a warning, not a placeholder section. A card with a hole in it is worse than no card, because a reader assumes the omission is a considered answer.

The licensing section is the one with real consequences, and it is the reason this task validates structure rather than prose. Three licences apply and they are not the same licence: this repository is MIT, the benchmark results data is CC-BY-4.0, and the lab's analysis code is CC BY-NC-SA 4.0 and is deliberately **not vendored** because NonCommercial and ShareAlike are both incompatible with MIT. That last fact has to survive every future edit of the card, so it is checked as a field rather than looked for in a paragraph.

**Files:**
- Create: `docs/CARD.yaml`, `tools/card.py`, `tools/markdown.py`, `templates/pages/card.html`
- Modify: `build.py`, `pyproject.toml`
- Test: `tests/test_card.py`

**Interfaces:**
- Consumes: `docs/CARD.yaml`, `tools.registry` for the counts the card quotes.
- Produces: `card.REQUIRED_SECTIONS: tuple[str, ...]`, `card.CardError`, `card.load_card(path: Path = CARD_PATH) -> Card`, `card.context(card: Card) -> dict[str, Any]`, `markdown.render(text: str) -> str`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_card.py`:

```python
"""The leaderboard card, and the rule that an incomplete one stops the build."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from tools import card, markdown
from tools import registry as reg


def test_every_required_section_is_present() -> None:
    loaded = card.load_card()
    assert tuple(s.id for s in loaded.sections) == card.REQUIRED_SECTIONS


def test_a_missing_section_fails_the_build(tmp_path: Path) -> None:
    """THE POINT OF THIS TASK. A card that silently renders seven of eight
    sections looks complete to every reader who does not know there were eight."""
    dest = tmp_path / "CARD.yaml"
    shutil.copy(card.CARD_PATH, dest)
    raw = yaml.safe_load(dest.read_text(encoding="utf-8"))
    raw["sections"] = [s for s in raw["sections"] if s["id"] != "limitations"]
    dest.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    with pytest.raises(card.CardError) as excinfo:
        card.load_card(dest)
    assert "limitations" in str(excinfo.value)


def test_an_empty_section_body_fails_too(tmp_path: Path) -> None:
    """Present but blank is the same hole with a heading over it."""
    dest = tmp_path / "CARD.yaml"
    shutil.copy(card.CARD_PATH, dest)
    raw = yaml.safe_load(dest.read_text(encoding="utf-8"))
    for section in raw["sections"]:
        if section["id"] == "uses":
            section["body"] = "   \n"
    dest.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    with pytest.raises(card.CardError, match="uses"):
        card.load_card(dest)


def test_the_error_names_every_problem_not_just_the_first(tmp_path: Path) -> None:
    dest = tmp_path / "CARD.yaml"
    shutil.copy(card.CARD_PATH, dest)
    raw = yaml.safe_load(dest.read_text(encoding="utf-8"))
    raw["sections"] = [
        s for s in raw["sections"] if s["id"] not in {"uses", "maintenance"}
    ]
    dest.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    with pytest.raises(card.CardError) as excinfo:
        card.load_card(dest)
    assert "uses" in str(excinfo.value)
    assert "maintenance" in str(excinfo.value)


def test_licensing_declares_all_three_licences() -> None:
    """Structured, not prose. The three-licence situation is the thing most
    likely to be flattened by a well-meaning edit."""
    licensing = next(s for s in card.load_card().sections if s.id == "licensing")
    by_spdx = {entry.spdx: entry for entry in licensing.licences}
    assert set(by_spdx) == {"MIT", "CC-BY-4.0", "CC-BY-NC-SA-4.0"}
    for entry in licensing.licences:
        assert entry.subject and entry.url


def test_the_noncommercial_code_is_recorded_as_not_vendored() -> None:
    """docs/sources/PROVENANCE.md exists because copying that file in would pull
    NonCommercial and ShareAlike onto an MIT repository."""
    licensing = next(s for s in card.load_card().sections if s.id == "licensing")
    upstream = next(e for e in licensing.licences if e.spdx == "CC-BY-NC-SA-4.0")
    assert upstream.vendored is False


def test_the_card_quotes_counts_from_the_registry() -> None:
    """A card is a citable document. Its numbers come from the same derivation
    as the grid, so they cannot drift apart."""
    context = card.context(card.load_card())
    assert context["counts"]["live_cells"] == len(reg.live_cells())
    assert context["counts"]["live_combos"] == len(reg.live_combos())
    assert context["counts"]["metric_rows"] == len(reg.metric_rows())


def test_every_required_section_reaches_the_page(built_dist) -> None:
    """The loader can be right while the template loops over the wrong list."""
    html = (built_dist / "about" / "card" / "index.html").read_text(encoding="utf-8")
    for section_id in card.REQUIRED_SECTIONS:
        assert f'id="card-{section_id}"' in html, section_id


def test_markdown_never_emits_a_dash_the_house_style_forbids() -> None:
    """markdown-it's typographer turns -- into an en dash and --- into an em
    dash. It is off, and this is the test that keeps it off."""
    rendered = markdown.render("baseline -- model --- entry")
    assert "—" not in rendered
    assert "–" not in rendered


def test_markdown_does_not_pass_raw_html_through() -> None:
    rendered = markdown.render("<script>alert(1)</script>")
    assert "<script>" not in rendered


def test_no_em_dash_in_the_documents_this_phase_authors() -> None:
    root = Path(__file__).resolve().parent.parent
    for name in ("docs/CARD.yaml", "docs/SUBMISSION.md"):
        text = (root / name).read_text(encoding="utf-8")
        assert "—" not in text, name
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_card.py -v`
Expected: FAIL, `ImportError: cannot import name 'card' from 'tools'`

- [ ] **Step 3: Add the one dependency**

In `pyproject.toml`, add `markdown-it-py>=3.0` to `dependencies`. It is pure Python, MIT, and has no transitive weight worth mentioning. It is the only new dependency in this phase, and it earns its place by letting `docs/SUBMISSION.md` be a single source that humans read on GitHub and the site renders at `/submit/`.

Run: `uv sync --all-extras`

- [ ] **Step 4: Write the Markdown renderer**

Create `tools/markdown.py`:

```python
"""One Markdown renderer for the whole site.

Two options are off on purpose.

`html` is off because these documents are repo-controlled, so this is not a
sanitiser, but a stray unclosed tag in a file a human edits should not be able to
break the structure of the page around it.

`typographer` is off because it rewrites `--` as an en dash and `---` as an em
dash. This project does not use em dashes, and a renderer that inserts them into
prose that never contained one is the hardest kind of style violation to find.
"""

from __future__ import annotations

from functools import cache

from markdown_it import MarkdownIt


@cache
def _parser() -> MarkdownIt:
    return MarkdownIt(
        "commonmark", {"html": False, "linkify": False, "typographer": False}
    )


def render(text: str) -> str:
    """Markdown to HTML. Safe to call on every section of every document."""
    return _parser().render(text)
```

- [ ] **Step 5: Write the card loader**

Create `tools/card.py`:

```python
"""docs/CARD.yaml, loaded and validated.

A missing required section raises. It is never a warning and never a rendered
placeholder, because a card is read as a set of considered answers and an
omission is indistinguishable from a deliberate one.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from tools import markdown
from tools import registry as reg

CARD_PATH = Path(__file__).resolve().parent.parent / "docs" / "CARD.yaml"

REQUIRED_TOP_LEVEL: tuple[str, ...] = (
    "name",
    "version",
    "updated",
    "citation",
    "contacts",
)

# Datasheets-for-datasets order, trimmed to what a benchmark leaderboard can
# actually answer. `limitations` is not in the canonical list and is required
# here anyway: this project documents an undertrained baseline, a pooled-versus
# -macro-mean estimator mismatch and six open decisions, and a card that omits
# them would be advertising rather than documentation.
REQUIRED_SECTIONS: tuple[str, ...] = (
    "motivation",
    "composition",
    "collection_process",
    "uses",
    "limitations",
    "distribution",
    "licensing",
    "maintenance",
)


class CardError(Exception):
    """docs/CARD.yaml is incomplete. Raised at build time and never caught."""


@dataclass(frozen=True, slots=True)
class Licence:
    subject: str
    spdx: str
    url: str
    vendored: bool


@dataclass(frozen=True, slots=True)
class Section:
    id: str
    title: str
    body: str
    html: str
    licences: tuple[Licence, ...]


@dataclass(frozen=True, slots=True)
class Card:
    name: str
    version: str
    updated: str
    citation: str
    contacts: tuple[str, ...]
    sections: tuple[Section, ...]


def load_card(path: Path = CARD_PATH) -> Card:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    problems: list[str] = []

    for key in REQUIRED_TOP_LEVEL:
        if not raw.get(key):
            problems.append(f"missing or empty top-level key: {key}")

    found = {s["id"]: s for s in raw.get("sections", []) if "id" in s}
    for section_id in REQUIRED_SECTIONS:
        section = found.get(section_id)
        if section is None:
            problems.append(f"missing required section: {section_id}")
        elif not str(section.get("body", "")).strip():
            problems.append(f"required section has an empty body: {section_id}")
        elif not str(section.get("title", "")).strip():
            problems.append(f"required section has no title: {section_id}")

    problems.extend(_licensing_problems(found.get("licensing")))

    if problems:
        raise CardError(
            f"{path} is incomplete:\n  " + "\n  ".join(problems)
        )
    ...
```

`_licensing_problems` requires a non-empty `licences` list, every entry carrying `subject`, `spdx`, `url` and `vendored`, and the `CC-BY-NC-SA-4.0` entry carrying `vendored: false`. Sections are returned in `REQUIRED_SECTIONS` order regardless of file order, so reordering the YAML cannot reorder the page.

`context()` returns the card plus a `counts` dict built from `reg.live_cells()`, `reg.live_combos()` and `reg.metric_rows()`, so every number the card publishes comes from the same derivation as the grid.

- [ ] **Step 6: Write docs/CARD.yaml**

Eight sections with real content, not headings awaiting text. Shape:

```yaml
name: EDA-Schema Leaderboard
version: "0.1"
updated: "2026-08-11"
citation: >-
  Kolluru et al., EDA-Schema-V2: a graph-based schema for chip design data,
  arXiv:2605.06952.
contacts:
  - Drexel ICE Laboratory
sections:
  - id: motivation
    title: Motivation
    body: |
      Table 8 of the EDA-Schema-V2 paper publishes a baseline for every
      combination of twelve prediction tasks, four PDKs and five stage
      transitions. It is a strong baseline and, until now, a static one: a lab
      with a better model had nowhere to say so in a form another lab could
      check.
      ...
  - id: licensing
    title: Licensing
    body: |
      Three licences apply and they are not interchangeable.
      ...
    licences:
      - subject: Site code, templates and build tooling
        spdx: MIT
        url: https://github.com/JiwaniZakir/eda-schema-leaderboard/blob/main/LICENSE
        vendored: true
      - subject: Benchmark results data and submitted entries
        spdx: CC-BY-4.0
        url: https://creativecommons.org/licenses/by/4.0/
        vendored: true
      - subject: >-
          The lab's baseline analysis code, read as a specification and
          reimplemented rather than copied
        spdx: CC-BY-NC-SA-4.0
        url: https://creativecommons.org/licenses/by-nc-sa/4.0/
        vendored: false
```

The `limitations` body states the four that a citing reader needs: the baseline is row-pooled while ingested models are macro-mean, the seed models are undertrained at 50 gradient steps with a training R2 median of 0.020, 32 cells carry a thresholded sentinel rather than a value so some comparisons are undecidable, and 24 cells have no measured baseline at all.

- [ ] **Step 7: Write the template and wire the build**

`templates/pages/card.html` is one loop over `sections`, emitting `<section id="card-{{ section.id }}">` with `{{ section.html | safe }}`. The licensing section additionally loops `section.licences` into a table. No conditionals beyond `{% if section.licences %}`.

`build.py` calls `card.load_card()` without a `try`. An incomplete card raises `CardError` and the build exits non-zero, which is the requirement.

- [ ] **Step 8: Run the tests**

Run: `uv run pytest tests/test_card.py -v`
Expected: 11 passed

- [ ] **Step 9: Prove the build actually fails**

The test asserts `CardError`. This checks that nothing between the loader and the exit code swallows it.

```bash
cp docs/CARD.yaml /tmp/CARD.yaml.bak
python - <<'PY'
import yaml, pathlib
p = pathlib.Path("docs/CARD.yaml")
raw = yaml.safe_load(p.read_text())
raw["sections"] = [s for s in raw["sections"] if s["id"] != "maintenance"]
p.write_text(yaml.safe_dump(raw, sort_keys=False))
PY
uv run python build.py; echo "exit=$?"
cp /tmp/CARD.yaml.bak docs/CARD.yaml
```

Expected: `CardError: ... missing required section: maintenance`, `exit=1`

- [ ] **Step 10: Commit**

```bash
git add pyproject.toml uv.lock tools/card.py tools/markdown.py docs/CARD.yaml templates/pages/card.html build.py tests/test_card.py
git commit -m "feat(card): render the leaderboard card and fail the build on a missing section"
```

---

### Task 4: The submission guide

This creates `docs/SUBMISSION.md`, which `CLAUDE.md` has referenced since before the reset without the file existing. That broken reference is the reason this task is in the phase.

The guide has two kinds of content. The prose is written once, in Markdown, and rendered at `/submit/`. The parts that must agree with the guard - the tiers, the divisions and the badge criteria - are **data** in `tools/submission.py`, keyed on the guard layer ids from Phase 6, and rendered into both the page and the tests. Prose that describes a guard drifts from the guard. Data that names guard layer ids fails a test the moment a layer is renamed.

**Files:**
- Create: `docs/SUBMISSION.md`, `tools/submission.py`, `templates/pages/submit.html`
- Modify: `build.py`
- Test: `tests/test_submit.py`

**Interfaces:**
- Consumes: `tools.guard.LAYERS`, `tools.markdown.render`.
- Produces: `submission.TIERS`, `submission.DIVISIONS`, `submission.BADGES`, `submission.PREDICT_SIGNATURE: str`, `submission.context() -> dict[str, Any]`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_submit.py`:

```python
"""The submission guide, and the rule that it cannot describe a guard that is
not there."""

from __future__ import annotations

import re
from pathlib import Path

from tools import guard, submission

DOC = Path(__file__).resolve().parent.parent / "docs" / "SUBMISSION.md"


def test_the_document_exists() -> None:
    """CLAUDE.md referenced this file before it existed. It exists now."""
    assert DOC.is_file()
    assert DOC.read_text(encoding="utf-8").strip()


def test_every_tier_requires_only_guard_layers_that_exist() -> None:
    """The consistency test. Renaming a guard layer in Phase 6 must break this,
    not silently leave the published criteria describing a layer that is gone."""
    known = set(guard.LAYERS)
    for tier in submission.TIERS:
        assert set(tier.requires) <= known, f"{tier.id} names {set(tier.requires) - known}"


def test_every_division_requires_only_guard_layers_that_exist() -> None:
    known = set(guard.LAYERS)
    for division in submission.DIVISIONS:
        assert set(division.requires) <= known, division.id


def test_the_closed_division_is_strictly_stricter_than_open() -> None:
    """If closed did not require more, the division would be decoration."""
    closed = next(d for d in submission.DIVISIONS if d.id == "closed")
    open_ = next(d for d in submission.DIVISIONS if d.id == "open")
    assert set(open_.requires) < set(closed.requires)


def test_tiers_are_ordered_by_strictness() -> None:
    """A reader takes the order as the ladder. It has to be one."""
    required = [set(tier.requires) for tier in submission.TIERS]
    for lower, higher in zip(required, required[1:], strict=False):
        assert lower <= higher


def test_the_split_overlap_layer_binds_in_every_division() -> None:
    """Train/test overlap is the one thing no division excuses. An open division
    that permitted it would let a lookup table lead the board."""
    for division in submission.DIVISIONS:
        assert "split_overlap" in division.requires, division.id


def test_every_tier_division_and_badge_id_appears_in_the_document() -> None:
    """Data and prose in one file each, checked against one another. This is what
    stops the page and the guide describing different schemes."""
    text = DOC.read_text(encoding="utf-8")
    for item in (*submission.TIERS, *submission.DIVISIONS, *submission.BADGES):
        assert item.id in text, f"{item.id} is defined in code but not documented"


def test_the_predict_signature_is_documented_verbatim() -> None:
    """The signature is a contract with a runner. A paraphrase of it in the guide
    is a submission that fails on upload."""
    text = DOC.read_text(encoding="utf-8")
    for line in ("def load(", "def predict(", "FEATURES"):
        assert line in text, line
    assert submission.PREDICT_SIGNATURE in text


def test_the_guide_says_the_runner_never_unpickles() -> None:
    """The single hardest rule in the project. A submitter who does not know it
    ships a checkpoint we will refuse to read."""
    text = DOC.read_text(encoding="utf-8").lower()
    assert "weights_only" in text
    assert "tensor shapes" in text


def test_no_dangling_internal_link_in_the_guide() -> None:
    """lychee checks dist/ in CI. This checks the source, so a broken link fails
    on the machine that wrote it."""
    root = Path(__file__).resolve().parent.parent
    text = DOC.read_text(encoding="utf-8")
    for target in re.findall(r"\]\((?!https?:|mailto:|#)([^)#]+)", text):
        assert (root / "docs" / target).resolve().exists(), target


def test_the_submit_page_renders_the_generated_tables(built_dist) -> None:
    html = (built_dist / "submit" / "index.html").read_text(encoding="utf-8")
    for item in (*submission.TIERS, *submission.DIVISIONS, *submission.BADGES):
        assert f'id="{item.id}"' in html or item.label in html, item.id
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_submit.py -v`
Expected: FAIL, `ImportError: cannot import name 'submission' from 'tools'`

- [ ] **Step 3: Write tools/submission.py**

```python
"""Verification tiers, divisions and badges.

Every one of these names a guard layer from tools/guard/. That is deliberate: a
tier is a claim about which checks ran, and a claim that is not keyed on the
check it describes is a claim nothing can falsify.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tools import guard


@dataclass(frozen=True, slots=True)
class Tier:
    id: str
    label: str
    requires: tuple[str, ...]
    reproduced: bool
    description: str


@dataclass(frozen=True, slots=True)
class Division:
    id: str
    label: str
    requires: tuple[str, ...]
    rule: str


@dataclass(frozen=True, slots=True)
class Badge:
    id: str
    label: str
    criterion: str


TIERS: tuple[Tier, ...] = (
    Tier(
        id="self-reported",
        label="Self-reported",
        requires=("feature_stage", "split_overlap", "division", "plausibility"),
        reproduced=False,
        description=(
            "The numbers are as submitted. Every static guard passed, but no code "
            "of yours was executed, so nothing here has been reproduced."
        ),
    ),
    Tier(
        id="reproduced",
        label="Reproduced",
        requires=(
            "feature_stage",
            "split_overlap",
            "division",
            "plausibility",
            "runnability",
        ),
        reproduced=True,
        description=(
            "Your predict.py ran on our runner against the smoke slice and "
            "returned the reported metrics within tolerance."
        ),
    ),
    Tier(
        id="verified",
        label="Verified",
        requires=tuple(guard.LAYERS),
        reproduced=True,
        description=(
            "Reproduced on the full canonical test split by a maintainer. This is "
            "the only tier that is not self-service."
        ),
    ),
)

DIVISIONS: tuple[Division, ...] = (
    Division(
        id="open",
        label="Open",
        requires=("split_overlap",),
        rule=(
            "Any features, any additional data, any model. One rule survives: no "
            "row of the test split may appear in your training data."
        ),
    ),
    Division(
        id="closed",
        label="Closed",
        requires=("feature_stage", "split_overlap", "division", "plausibility"),
        rule=(
            "The canonical split, only attributes available at your submitted "
            "stage, and one target per cell. This is the comparable division."
        ),
    ),
)

BADGES: tuple[Badge, ...] = (
    Badge(
        id="beats-baseline",
        label="Beats baseline",
        criterion=(
            "At least one cell where the entry outperforms the published Table 8 "
            "baseline in that metric's own direction. Awarded from the ranking, "
            "never claimed by a submitter."
        ),
    ),
    Badge(
        id="optimal-tie",
        label="Optimal tie",
        criterion=(
            "matches_baseline on a saturated cell. Tying is the best achievable "
            "outcome on those cells, so it is recorded as an achievement rather "
            "than folded into a loss."
        ),
    ),
    Badge(
        id="closed-division",
        label="Closed division",
        criterion="Every guard layer the closed division requires passed.",
    ),
    Badge(
        id="reproduced",
        label="Reproduced",
        criterion="The runnability layer executed predict.py on our runner.",
    ),
)

PREDICT_SIGNATURE = "def predict(model: Any, rows: Sequence[dict[str, float]]) -> list[float]:"
```

- [ ] **Step 4: Write docs/SUBMISSION.md**

The document covers, in this order:

**What a submission is.** A directory with `submission.yaml`, `predict.py`, and a `weights/` URL pointing at a GitHub Release or Hugging Face. Nothing over 1 MB in the repository.

**The `predict.py` contract**, verbatim, because the runner imports it by these names:

```python
"""predict.py - the entry point every submission provides."""

from collections.abc import Sequence
from typing import Any

# Every attribute you read, spelled as Table 1 of the paper spells it.
# The feature_stage guard checks each name against the stage you are submitting
# for and rejects the submission if any attribute is not available there.
FEATURES: tuple[str, ...] = (
    "Netlist.total_cells",
    "Netlist.total_hpwl",
)


def load(weights_dir: str) -> Any:
    """Load your model. Called exactly once, before any call to predict."""


def predict(model: Any, rows: Sequence[dict[str, float]]) -> list[float]:
    """One prediction per row, in the same order, the same length as rows.

    Values are in the target's own unit. Never a percentage, never z-scored.
    Percent-format metrics are computed by the scorer from these raw numbers, so
    a prediction that arrives pre-scaled is wrong by a factor of a hundred and
    nothing downstream can detect it.
    """
```

**The runner.** No network. Read-only mount. Ten minutes of wall clock on the smoke slice. The failure of the runnability layer is a tier ceiling, not a rejection: the entry still lands as `self-reported`.

**Checkpoints are never unpickled.** We read tensor shapes out of the zip with a restricted reader that returns an inert placeholder for every foreign global, so no code inside a checkpoint executes. `weights_only=True` is not the mechanism, and asking us to pass `weights_only=False` is asking for arbitrary code execution on the runner. Ship weights your own `load()` can read; we only introspect shapes for the architecture diagram, and a checkpoint we cannot introspect renders without one rather than being rejected.

**The four ways an entry is rejected**, one per blocking guard layer, each with the message the guard prints.

**Divisions**, **tiers** and **badges**, each naming the ids in `tools/submission.py` so the consistency test binds.

**What we do not rank.** Saturated cells are never ranked. Degenerate cells carry no baseline, so an entry there is shown without a comparison rather than as an automatic win. Sentinel cells are beatable only from the defined side of the threshold; anything else renders as no comparison rather than a guess.

**The MPE and MNE sort.** Ranked on `mpe` ascending first, then `mne`. An optimistic slack prediction hides a real timing violation, and that is the failure with silicon consequences. A model that predicts wildly pessimistic slack scores `mpe = 0` and leads that cell while placing last on `mae` in the same grid, which is why the plausibility layer flags exactly that shape.

- [ ] **Step 5: Write the template and wire the build**

`templates/pages/submit.html` renders `{{ guide_html | safe }}` from `markdown.render(DOC.read_text())`, then three tables looped from `tiers`, `divisions` and `badges`, each row carrying `id="{{ item.id }}"`. The guard layer ids in the `requires` column are rendered as text, not links, because `/submit/` is the page that defines them.

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/test_submit.py -v`
Expected: 11 passed

- [ ] **Step 7: Check the links for real**

Run: `uv run python build.py && lychee --no-progress --accept 200,206,429 dist/submit/ docs/SUBMISSION.md`
Expected: 0 errors

- [ ] **Step 8: Commit**

```bash
git add docs/SUBMISSION.md tools/submission.py templates/pages/submit.html build.py tests/test_submit.py
git commit -m "feat(submit): add the submission guide, tiers, divisions and badges"
```

---

### Task 5: Architecture description and layout geometry

The phase gate names three things about the architecture renderer: the lab's MLP renders as 41 to 64 to 32 to 16 to 1 with 5,313 parameters, a GNN with pooling renders without overlap, and a 40-layer model degrades rather than overflowing. All three are geometry, and geometry computed in the browser cannot be checked by `pytest`.

So the geometry is computed in Python. `static/js/arch-render.js` draws the rectangles this task produces and calculates nothing.

**One renderer, four families.** `Architecture` is a family string and a list of layers. Nothing in the layout branches on the family; a graph convolution and a dense layer differ only in `kind`, which selects a colour variable. That is what makes one renderer serve MLP, GNN, CNN and AutoML honestly rather than by four code paths sharing a filename.

**Files:**
- Create: `tools/arch.py`, `tools/archlayout.py`, `tests/fixtures/arch/mlp_lab.json`, `tests/fixtures/arch/gnn_pool.json`, `tests/fixtures/arch/cnn_small.json`, `tests/fixtures/arch/automl_stack.json`
- Test: `tests/test_arch_render.py`

**Interfaces:**
- Consumes: `tools.ckpt` tensor shapes.
- Produces: `arch.Layer`, `arch.Architecture`, `arch.layer_params(layer) -> int`, `arch.param_count(arch) -> int`, `arch.load(path) -> Architecture`, `arch.from_shapes(shapes, family) -> Architecture`; `archlayout.Block`, `archlayout.Layout`, `archlayout.layout(arch) -> Layout`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_arch_render.py`:

```python
"""The architecture renderer's geometry, computed in Python so it is testable.

Every fixture is a real architecture. The lab's MLP is the one recovered from a
checkpoint; the other three are the shapes the other families actually take.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import pytest

from tools import arch, archlayout

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "arch"


def _load(name: str) -> arch.Architecture:
    return arch.load(FIXTURES / f"{name}.json")


def test_the_labs_mlp_is_41_64_32_16_1() -> None:
    layers = _load("mlp_lab").layers
    assert [layer.units for layer in layers] == [41, 64, 32, 16, 1]


def test_the_labs_mlp_has_5313_parameters() -> None:
    """41*64 + 64  = 2688
       64*32 + 32  = 2080
       32*16 + 16  =  528
       16*1  +  1  =   17
       -------------------
                     5313

    hparams.yaml reports in_features: 7 and params: 0 for every layer. Both are
    wrong. This number comes from the tensor shapes and nowhere else."""
    assert arch.param_count(_load("mlp_lab")) == 5313


def test_per_layer_parameter_counts_are_right_individually() -> None:
    """A total can be right while two layers are wrong in opposite directions."""
    layers = _load("mlp_lab").layers
    assert [arch.layer_params(layer) for layer in layers] == [0, 2688, 2080, 528, 17]


def test_the_input_layer_carries_no_parameters() -> None:
    first = _load("mlp_lab").layers[0]
    assert first.kind == "input"
    assert arch.layer_params(first) == 0


def test_shapes_recovered_from_a_checkpoint_rebuild_the_same_architecture() -> None:
    """A PyTorch Linear stores its weight as (out_features, in_features). Reading
    it the other way round yields 7 -> 41, which is the exact lie hparams.yaml
    tells, so the orientation is asserted rather than trusted."""
    shapes = [
        ("net.0.weight", (64, 41)),
        ("net.0.bias", (64,)),
        ("net.2.weight", (32, 64)),
        ("net.2.bias", (32,)),
        ("net.4.weight", (16, 32)),
        ("net.4.bias", (16,)),
        ("net.6.weight", (1, 16)),
        ("net.6.bias", (1,)),
    ]
    rebuilt = arch.from_shapes(shapes, family="mlp")
    assert [layer.units for layer in rebuilt.layers] == [41, 64, 32, 16, 1]
    assert arch.param_count(rebuilt) == 5313


def test_a_transposed_read_is_rejected_rather_than_rendered() -> None:
    with pytest.raises(ValueError, match="in_features"):
        arch.from_shapes(
            [("net.0.weight", (64, 41)), ("net.2.weight", (32, 41))], family="mlp"
        )


@pytest.mark.parametrize(
    "name", ["mlp_lab", "gnn_pool", "cnn_small", "automl_stack"]
)
def test_one_layout_function_serves_every_family(name: str) -> None:
    """The gate says one renderer, four families. This is that claim, tested."""
    result = archlayout.layout(_load(name))
    assert len(result.blocks) == len(_load(name).layers)
    assert result.total_params == arch.param_count(_load(name))


@pytest.mark.parametrize(
    "name", ["mlp_lab", "gnn_pool", "cnn_small", "automl_stack"]
)
def test_no_two_blocks_overlap(name: str) -> None:
    """Every pair, not only adjacent pairs. Adjacent-only passes on a layout that
    wraps a later block back over an earlier one."""
    blocks = archlayout.layout(_load(name)).blocks
    for left, right in itertools.combinations(blocks, 2):
        assert left.x + left.w <= right.x or right.x + right.w <= left.x, (
            f"{left.name} overlaps {right.name}"
        )


def test_the_gnn_pooling_layer_occupies_its_own_column() -> None:
    """Pooling carries no parameters, which is exactly why it is easy to collapse
    into its neighbour and produce an overlap only this family shows."""
    result = archlayout.layout(_load("gnn_pool"))
    pool = next(b for b in result.blocks if b.kind == "pool")
    assert pool.params == 0
    assert pool.w > 0
    neighbours = [b for b in result.blocks if b is not pool]
    for other in neighbours:
        assert pool.x + pool.w <= other.x or other.x + other.w <= pool.x


def test_block_height_is_proportional_to_layer_width() -> None:
    """64 units must draw exactly twice as tall as 32. An eyeballed scale that is
    merely monotonic tells the reader nothing quantitative."""
    blocks = {b.units: b.h for b in archlayout.layout(_load("mlp_lab")).blocks}
    assert blocks[64] == pytest.approx(2 * blocks[32])
    assert blocks[32] == pytest.approx(2 * blocks[16])
    assert blocks[41] == pytest.approx(blocks[64] * 41 / 64)


def test_a_one_unit_layer_is_clamped_to_a_visible_height() -> None:
    """The only deviation from proportionality, and it is deliberate: a
    sub-pixel output block reads as a missing layer."""
    blocks = archlayout.layout(_load("mlp_lab")).blocks
    assert blocks[-1].units == 1
    assert blocks[-1].h == archlayout.MIN_BLOCK_H


def _deep(layer_count: int) -> arch.Architecture:
    """A real stack, not a placeholder: widths cycle the way a deep residual
    encoder's do, so the height scale is exercised as well as the pitch."""
    layers = [arch.Layer(name="input", kind="input", units=41)]
    previous = 41
    for i in range(layer_count - 2):
        units = 16 + (i % 5) * 16
        layers.append(
            arch.Layer(
                name=f"fc{i}",
                kind="dense",
                units=units,
                in_units=previous,
                bias=True,
            )
        )
        previous = units
    layers.append(
        arch.Layer(name="out", kind="dense", units=1, in_units=previous, bias=True)
    )
    return arch.Architecture(family="mlp", layers=tuple(layers))


def test_forty_layers_stay_inside_the_canvas() -> None:
    result = archlayout.layout(_deep(40))
    assert len(result.blocks) == 40
    for block in result.blocks:
        assert block.x >= 0
        assert block.x + block.w <= result.view_w
        assert block.y >= 0
        assert block.y + block.h <= result.view_h


def test_forty_layers_do_not_overlap_either() -> None:
    blocks = archlayout.layout(_deep(40)).blocks
    for left, right in itertools.combinations(blocks, 2):
        assert left.x + left.w <= right.x or right.x + right.w <= left.x


def test_deep_layouts_drop_labels_rather_than_letting_them_collide() -> None:
    """The graceful part of degrading gracefully. Names move to the per-block
    title, which hover and assistive technology both reach."""
    assert archlayout.layout(_load("mlp_lab")).labels_visible is True
    assert archlayout.layout(_deep(40)).labels_visible is False


def test_block_width_never_exceeds_the_column_pitch() -> None:
    """The invariant the whole no-overlap property rests on. Asserted directly so
    a future change to BLOCK_FILL or MAX_BLOCK_W cannot break it quietly."""
    for count in (2, 5, 12, 40, 120):
        result = archlayout.layout(_deep(max(count, 3)))
        pitch = (result.view_w - 2 * archlayout.MARGIN_X) / len(result.blocks)
        for block in result.blocks:
            assert block.w < pitch


def test_an_empty_architecture_raises_rather_than_rendering_nothing() -> None:
    with pytest.raises(ValueError):
        archlayout.layout(arch.Architecture(family="mlp", layers=()))
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_arch_render.py -v`
Expected: FAIL, `ImportError: cannot import name 'arch' from 'tools'`

- [ ] **Step 3: Write the fixtures**

`tests/fixtures/arch/mlp_lab.json` is the lab's fixed MLP, the architecture `tools/ckpt.py` recovers from all 360 checkpoints:

```json
{
  "family": "mlp",
  "layers": [
    { "name": "input", "kind": "input", "units": 41 },
    { "name": "fc1", "kind": "dense", "units": 64, "in_units": 41, "bias": true },
    { "name": "fc2", "kind": "dense", "units": 32, "in_units": 64, "bias": true },
    { "name": "fc3", "kind": "dense", "units": 16, "in_units": 32, "bias": true },
    { "name": "out", "kind": "dense", "units": 1, "in_units": 16, "bias": true }
  ]
}
```

`gnn_pool.json` is two graph convolutions, a global mean pool that preserves feature width, and a dense head. `cnn_small.json` carries two `conv` layers with a `kernel` and a pooling layer. `automl_stack.json` is a wider search-produced stack with a normalisation layer, which is the family most likely to contain a `kind` the renderer has not seen.

- [ ] **Step 4: Write tools/arch.py**

```python
"""Architecture description and parameter counting.

One description serves MLP, GNN, CNN and AutoML. Only the layer list differs, and
nothing in this module or in the layout branches on family.

Parameter counts come from tensor shapes. hparams.yaml reports in_features: 7
where the trained weight is (64, 41), and params: 0 for every layer, so it is not
a source for anything here.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

FAMILIES: frozenset[str] = frozenset({"mlp", "gnn", "cnn", "automl"})

# Kinds that carry weights, and what shape those weights take.
#   dense, graph : in_units * units, plus units biases when bias is set
#   conv         : kernel * in_units * units, plus units biases
# input, pool, activation, dropout and norm carry none. A kind this module does
# not know raises rather than silently counting zero, because a silent zero is a
# published parameter count that is quietly too small.
_WEIGHTLESS: frozenset[str] = frozenset(
    {"input", "pool", "activation", "dropout", "norm"}
)


@dataclass(frozen=True, slots=True)
class Layer:
    name: str
    kind: str
    units: int
    in_units: int = 0
    kernel: int = 0
    bias: bool = False


@dataclass(frozen=True, slots=True)
class Architecture:
    family: str
    layers: tuple[Layer, ...]


def layer_params(layer: Layer) -> int:
    if layer.kind in {"dense", "graph"}:
        return layer.in_units * layer.units + (layer.units if layer.bias else 0)
    if layer.kind == "conv":
        weights = layer.kernel * layer.in_units * layer.units
        return weights + (layer.units if layer.bias else 0)
    if layer.kind in _WEIGHTLESS:
        return 0
    raise ValueError(f"unknown layer kind {layer.kind!r}")


def param_count(architecture: Architecture) -> int:
    return sum(layer_params(layer) for layer in architecture.layers)
```

`from_shapes` reads `(name, shape)` pairs from `tools/ckpt.py`, takes each `*.weight` of rank 2 as `(out_features, in_features)`, asserts that consecutive layers chain - `in_features` of layer *n+1* equals `out_features` of layer *n* - and raises `ValueError` naming `in_features` when they do not. That check is what catches a transposed read, which is the failure mode that produces a plausible-looking 7-input diagram.

- [ ] **Step 5: Write tools/archlayout.py**

```python
"""Geometry for the architecture renderer.

Computed here so pytest can check it. static/js/arch-render.js draws these
rectangles and computes nothing, because geometry produced in the browser is
geometry no gate can assert on.

Coordinates are viewBox units. The SVG scales to its container, so the canvas is
a fixed 960 by 320 regardless of viewport.
"""

from __future__ import annotations

from dataclasses import dataclass

from tools.arch import Architecture, layer_params, param_count

VIEW_W = 960
VIEW_H = 320
MARGIN_X = 24
MARGIN_Y = 20
# Of the column pitch. The remaining 38 percent is the connector gap, and it is
# what makes non-overlap a property of the construction rather than a check:
# block width is a fraction of pitch, so the gap between block i and block i+1 is
# pitch - width, which is positive for every layer count.
BLOCK_FILL = 0.62
MAX_BLOCK_W = 96
# A one-unit output layer would otherwise draw sub-pixel and read as missing.
MIN_BLOCK_H = 6
# Below this pitch, names collide. They move to the per-block title instead.
LABEL_MIN_PITCH = 34


@dataclass(frozen=True, slots=True)
class Block:
    name: str
    kind: str
    units: int
    params: int
    x: float
    y: float
    w: float
    h: float


@dataclass(frozen=True, slots=True)
class Layout:
    view_w: int
    view_h: int
    blocks: tuple[Block, ...]
    labels_visible: bool
    total_params: int


def layout(architecture: Architecture) -> Layout:
    count = len(architecture.layers)
    if count == 0:
        raise ValueError("an architecture needs at least one layer")

    pitch = (VIEW_W - 2 * MARGIN_X) / count
    block_w = min(MAX_BLOCK_W, pitch * BLOCK_FILL)
    widest = max(layer.units for layer in architecture.layers)
    usable_h = VIEW_H - 2 * MARGIN_Y

    blocks = []
    for i, layer in enumerate(architecture.layers):
        height = max(MIN_BLOCK_H, usable_h * layer.units / widest)
        blocks.append(
            Block(
                name=layer.name,
                kind=layer.kind,
                units=layer.units,
                params=layer_params(layer),
                x=MARGIN_X + pitch * i + (pitch - block_w) / 2,
                y=(VIEW_H - height) / 2,
                w=block_w,
                h=height,
            )
        )

    return Layout(
        view_w=VIEW_W,
        view_h=VIEW_H,
        blocks=tuple(blocks),
        labels_visible=pitch >= LABEL_MIN_PITCH,
        total_params=param_count(architecture),
    )
```

Worked through for the two cases the gate names. Five layers gives pitch 182.4 and width 96, so the gap is 86.4 and the last block's right edge is 892.8 against a 960 canvas. Forty layers gives pitch 22.8 and width 14.14, so the gap is 8.66, the last right edge is 931.7, and labels switch off because 22.8 is below 34. Heights for the MLP are 179.375, 280, 140, 70 and the clamped 6.

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/test_arch_render.py -v`
Expected: 21 passed

- [ ] **Step 7: Commit**

```bash
git add tools/arch.py tools/archlayout.py tests/fixtures/arch tests/test_arch_render.py
git commit -m "feat(arch): add the architecture description and layout geometry"
```

---

### Task 6: The model page and the SVG renderer

`/model/?id=` is one static shell hydrated from JSON. Pre-rendering one page per submission grows with every entry while the shell does not, and the record count is what makes static generation counterproductive here.

Two untrusted inputs meet on this page and both are handled at the boundary. The **model id** comes from the query string, so it is checked against the index before anything is fetched; a value that is not in the index renders a not-found state and issues no request. The **model name and description** come from a submission, so every string reaches the DOM through `textContent`. `innerHTML` appears nowhere in either file, and a test asserts that.

**Files:**
- Create: `tools/modelpage.py`, `templates/pages/model.html`, `static/js/arch-render.js`, `static/js/model.js`, `static/css/arch.css`
- Modify: `build.py`, `static/css/themes/*.css`
- Test: `tests/test_arch_render.py`

**Interfaces:**
- Consumes: `tools.arch`, `tools.archlayout`, `tools.guard`, the Phase 4 shards.
- Produces: `modelpage.MODEL_ID_RE`, `modelpage.validate_id(model_id) -> str`, `modelpage.model_payload(entry) -> dict[str, Any]`, `modelpage.index_payload() -> list[dict[str, Any]]`; `dist/model/index.html`, `dist/data/models/index.json`, `dist/data/models/<id>.json`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_arch_render.py`:

```python
def test_model_ids_are_constrained_to_a_safe_shape() -> None:
    """The id arrives in a query string and becomes part of a fetch path. Every
    id we emit is checked here, so the browser can trust its own index."""
    from tools import modelpage

    for good in ("lab-mlp-v1", "drexel_ice.baseline", "a"):
        assert modelpage.validate_id(good) == good
    for bad in ("../secrets", "a/b", "", "A-Model", "x" * 65, "-leading"):
        with pytest.raises(ValueError):
            modelpage.validate_id(bad)


def test_every_emitted_model_id_is_valid() -> None:
    from tools import modelpage

    for entry in modelpage.index_payload():
        assert modelpage.validate_id(entry["id"]) == entry["id"]


def test_the_model_payload_carries_precomputed_geometry() -> None:
    """If the browser computed this, none of the geometry tests above would be
    testing what ships."""
    from tools import modelpage

    payloads = [modelpage.model_payload(e) for e in modelpage.index_payload()]
    with_arch = [p for p in payloads if p["architecture"] is not None]
    assert with_arch, "at least the lab's seed entry has a recovered architecture"
    for payload in with_arch:
        layout = payload["architecture"]["layout"]
        assert layout["blocks"]
        assert all({"x", "y", "w", "h"} <= set(b) for b in layout["blocks"])
        assert layout["total_params"] > 0


def test_the_feature_legality_badge_comes_from_the_guard(monkeypatch) -> None:
    """NEVER HARDCODED. The badge is a claim that a check ran and passed, and a
    literal 'pass' in a template is that claim with nothing behind it."""
    from tools import guard, modelpage

    entry = modelpage.index_payload()[0]
    assert modelpage.model_payload(entry)["guard"]["feature_stage"]["status"] == "pass"

    def failing(*args: object, **kwargs: object) -> guard.LayerResult:
        return guard.LayerResult(
            layer="feature_stage",
            status="fail",
            detail="net.length is not available at floorplan",
        )

    monkeypatch.setattr(guard.LAYERS["feature_stage"], "run", failing)
    flipped = modelpage.model_payload(entry)["guard"]["feature_stage"]
    assert flipped["status"] == "fail"
    assert "net.length" in flipped["detail"]


def test_no_badge_status_is_written_as_a_literal_in_the_template() -> None:
    from pathlib import Path

    template = (
        Path(__file__).resolve().parent.parent
        / "templates"
        / "pages"
        / "model.html"
    ).read_text()
    assert "pass" not in template.lower().replace("passive", "")


def test_the_renderer_never_uses_innerhtml() -> None:
    """Model names and descriptions are submitted by strangers and this is the
    page that renders the most of them."""
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "static" / "js"
    for name in ("model.js", "arch-render.js"):
        source = (root / name).read_text()
        assert "innerHTML" not in source, name
        assert "outerHTML" not in source, name


def test_the_renderer_takes_every_colour_from_the_variable_contract() -> None:
    """No literal colour in the drawing code, in either direction: the diagram
    has to change with the theme."""
    from pathlib import Path

    source = (
        Path(__file__).resolve().parent.parent / "static" / "js" / "arch-render.js"
    ).read_text()
    for literal in ("#", "rgb(", "hsl("):
        assert literal not in source, literal


def test_both_themes_declare_every_architecture_variable() -> None:
    import re
    from pathlib import Path

    themes = sorted(
        (Path(__file__).resolve().parent.parent / "static" / "css" / "themes").glob(
            "*.css"
        )
    )
    assert len(themes) >= 2
    declared = [
        set(re.findall(r"(--arch-[a-z0-9-]+)\s*:", path.read_text()))
        for path in themes
    ]
    assert declared[0], "no architecture variables declared at all"
    assert all(names == declared[0] for names in declared), {
        path.name: sorted(names) for path, names in zip(themes, declared, strict=True)
    }


def test_the_model_shell_is_one_page_not_one_per_model(built_dist) -> None:
    assert (built_dist / "model" / "index.html").is_file()
    assert (built_dist / "data" / "models" / "index.json").is_file()
    assert not list((built_dist / "model").glob("*/index.html"))
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_arch_render.py -v`
Expected: FAIL, `ImportError: cannot import name 'modelpage' from 'tools'`

- [ ] **Step 3: Write tools/modelpage.py**

```python
"""Payloads for the client-hydrated /model/ page.

One shell, one index, one file per model. Pre-rendering a page per submission
grows without bound; the shell does not.

The guard block in every payload is produced by RUNNING the guard, not by reading
a field a submitter set. A badge is a claim that a check passed, and a claim that
does not come from the check is decoration.
"""

from __future__ import annotations

import re
from typing import Any

from tools import arch, archlayout, guard

# Lowercase, dot, dash and underscore. The id lands in a fetch path, so the
# shape is constrained at emission and re-checked in the browser against the
# index before any request is made.
MODEL_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


def validate_id(model_id: str) -> str:
    if not MODEL_ID_RE.fullmatch(model_id):
        raise ValueError(f"unsafe model id {model_id!r}")
    return model_id
```

`model_payload` assembles the entry's metadata, its per-cell results, `guard` as `{layer_id: {"status": ..., "detail": ...}}` from `guard.LAYERS`, and `architecture` as `{"family": ..., "layers": [...], "layout": asdict(archlayout.layout(a))}`, or `None` when no checkpoint was introspectable. A model whose checkpoint could not be read renders without a diagram and says so, rather than being dropped.

- [ ] **Step 4: Write the SVG renderer**

Create `static/js/arch-render.js`:

```js
// One renderer for MLP, GNN, CNN and AutoML. Only the layer list differs.
//
// It draws the geometry tools/archlayout.py computed and calculates nothing:
// a coordinate produced here is a coordinate no phase gate can assert on.
//
// Every colour is a CSS custom property, so the diagram follows the theme. No
// literal colour appears in this file and a test enforces that.

const SVG_NS = "http://www.w3.org/2000/svg";

function el(name, attributes) {
  const node = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attributes)) {
    node.setAttribute(key, String(value));
  }
  return node;
}

function describe(layout) {
  const shape = layout.blocks.map((b) => b.units).join(" to ");
  return `Architecture diagram: ${shape}, ${layout.total_params} parameters.`;
}

/**
 * @param {HTMLElement} container
 * @param {{view_w: number, view_h: number, blocks: Array, labels_visible: boolean,
 *          total_params: number}} layout
 */
export function renderArchitecture(container, layout) {
  const svg = el("svg", {
    viewBox: `0 0 ${layout.view_w} ${layout.view_h}`,
    preserveAspectRatio: "xMidYMid meet",
    role: "img",
    "aria-label": describe(layout),
    class: "arch-diagram",
  });

  for (let i = 0; i < layout.blocks.length - 1; i += 1) {
    const from = layout.blocks[i];
    const to = layout.blocks[i + 1];
    svg.appendChild(
      el("line", {
        class: "arch-connector",
        x1: from.x + from.w,
        y1: layout.view_h / 2,
        x2: to.x,
        y2: layout.view_h / 2,
      }),
    );
  }

  for (const block of layout.blocks) {
    const group = el("g", { class: `arch-block arch-block-${block.kind}` });
    group.appendChild(
      el("rect", { x: block.x, y: block.y, width: block.w, height: block.h, rx: 2 }),
    );
    const title = el("title", {});
    title.textContent = `${block.name}: ${block.units} units, ${block.params} parameters`;
    group.appendChild(title);
    if (layout.labels_visible) {
      const label = el("text", {
        class: "arch-label",
        x: block.x + block.w / 2,
        y: block.y + block.h + 14,
        "text-anchor": "middle",
      });
      label.textContent = `${block.name} (${block.units})`;
      group.appendChild(label);
    }
    svg.appendChild(group);
  }

  container.replaceChildren(svg, layerTable(layout));
  return svg;
}
```

`layerTable` builds a visually hidden `<table>` of name, kind, units and parameters. A diagram that exists only as a picture is a diagram half the audience cannot read, and it costs six lines.

`static/css/arch.css` maps `.arch-block-dense rect { fill: var(--arch-block-dense); }` and the same for `graph`, `conv` and the weightless kinds, plus `--arch-connector` and `--arch-label`. Both theme files gain the same five variables, which the test above pins.

- [ ] **Step 5: Write the hydration**

`static/js/model.js` reads `?id=`, fetches `/data/models/index.json`, and only fetches `/data/models/<id>.json` if the id is present in that index. Not found renders a message and a link back to `/explore/`. Every string goes in through `textContent`. The guard badges are rendered from `payload.guard`, one badge per layer, with the status class taken from the payload rather than from any decision made in the browser.

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/test_arch_render.py -v`
Expected: 29 passed

- [ ] **Step 7: Look at it**

Run: `make serve` and open `http://localhost:8000/model/?id=<the seed entry id>`
Check: the diagram shows five blocks stepping down in height, the label under each reads `fc1 (64)` and so on, the parameter total reads 5,313, and the badges reflect the guard. Then open `/model/?id=../../etc/passwd` and confirm the page reports an unknown model and issues no second request.

- [ ] **Step 8: Commit**

```bash
git add tools/modelpage.py templates/pages/model.html static/js/arch-render.js static/js/model.js static/css/arch.css static/css/themes build.py tests/test_arch_render.py
git commit -m "feat(model): add the hydrated model page and the architecture renderer"
```

---

### Task 7: Wiring, budgets and links

The four pages exist. This task connects them to the rest of the site, measures what they weigh, and proves every link resolves.

**Files:**
- Modify: `build.py`, `templates/base.html`, `.pa11yci.json`
- Test: `tests/test_pages.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `dist/explore/`, `dist/about/card/`, `dist/submit/`, `dist/model/`, `dist/data/`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pages.py`:

```python
"""The four Phase 8 pages, measured and linked."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PAGES = (
    "explore/index.html",
    "about/card/index.html",
    "submit/index.html",
    "model/index.html",
)


@pytest.mark.parametrize("page", PAGES)
def test_the_page_is_built(built_dist: Path, page: str) -> None:
    assert (built_dist / page).is_file()


@pytest.mark.parametrize("page", PAGES)
def test_every_internal_link_resolves(built_dist: Path, page: str) -> None:
    """lychee runs over dist/ in CI. This runs on the machine that wrote the
    link, which is where a broken one is cheapest to fix."""
    html = (built_dist / page).read_text(encoding="utf-8")
    for href in re.findall(r'href="(/[^"#?]*)', html):
        target = built_dist / href.lstrip("/")
        assert target.is_file() or (target / "index.html").is_file(), (
            f"{page} links to {href}, which does not exist"
        )


@pytest.mark.parametrize("page", PAGES)
def test_the_page_is_within_budget(built_dist: Path, page: str) -> None:
    """88 KB. Printed as well as asserted, so the run shows the headroom rather
    than only the failure. Run with -s to read it."""
    size = (built_dist / page).stat().st_size
    print(f"{page}: {size / 1024:.1f} KiB")
    assert size <= 88 * 1024


def test_the_lazily_fetched_payloads_are_measured(built_dist: Path) -> None:
    """These are not page weight, because nothing blocks on them, but they are
    dist/ weight and dist/ has a 20 MB target."""
    total = 0
    for path in sorted((built_dist / "data").rglob("*.json")):
        size = path.stat().st_size
        total += size
        print(f"{path.relative_to(built_dist)}: {size / 1024:.1f} KiB")
    print(f"total data payload: {total / 1024:.1f} KiB")
    assert total <= 2 * 1024 * 1024


def test_every_new_page_is_reachable_from_the_nav(built_dist: Path) -> None:
    """A page nothing links to is a page nobody finds. /model/ is deliberately
    absent: it is reached from a cell page, not from the nav."""
    home = (built_dist / "index.html").read_text(encoding="utf-8")
    for href in ("/explore/", "/about/card/", "/submit/"):
        assert href in home, href


def test_the_matrix_still_renders_every_live_cell(built_dist: Path) -> None:
    """A regression guard on the phase, not a new requirement. Adding four pages
    and a nav entry has no business changing the grid."""
    from tools import registry as reg

    html = (built_dist / "index.html").read_text(encoding="utf-8")
    assert html.count('class="cell') == len(reg.live_cells())


def test_no_page_ships_a_bare_module_specifier(built_dist: Path) -> None:
    for page in PAGES:
        html = (built_dist / page).read_text(encoding="utf-8")
        for src in re.findall(r'<script[^>]+src="([^"]+)"', html):
            assert src.startswith(("/", "./")), f"{page} loads {src}"
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_pages.py -v`
Expected: FAIL on the nav test and on at least one link, because `base.html` has no entries for the new pages yet

- [ ] **Step 3: Add the nav entries**

`templates/base.html` gains `/explore/`, `/about/card/` and `/submit/`. `/model/` stays out: it is reached from a cell page's entry list, and a nav link to a page that needs a query string to say anything is a link to an error state.

- [ ] **Step 4: Extend the accessibility matrix**

Add the four new URLs to `.pa11yci.json` so the a11y workflow covers them in both themes. `/model/` needs a real id in its query string to render anything, so it goes in as `/model/?id=<seed id>`.

- [ ] **Step 5: Run the tests with sizes shown**

Run: `uv run pytest tests/test_pages.py -v -s`
Expected: 15 passed, with a printed size table

- [ ] **Step 6: Run the whole gate**

Run: `make check`
Expected: ruff clean, mypy clean, `eda-validate` reporting 0 failures, all tests passing, build succeeding

- [ ] **Step 7: Check links across the whole site**

Run: `lychee --no-progress --accept 200,206,429 dist/ docs/ ./*.md`
Expected: 0 errors

- [ ] **Step 8: Check the size of what shipped**

```bash
du -sh dist/
find dist -type f -printf '%s\t%p\n' | sort -rn | head -10
```

Expected: `dist/` comfortably inside the 20 MB target, and nothing surprising in the top ten

- [ ] **Step 9: Commit and open the PR**

```bash
git add build.py templates/base.html .pa11yci.json tests/test_pages.py
git commit -m "feat(pages): wire explore, card, submit and model into the site"
git push -u origin phase-8/explore-card-submit-model
gh pr create --title "Phase 8: explore, card, submit and model pages" --body "Adds /explore/ with five filters over a compact column-oriented payload, /about/card/ rendered from docs/CARD.yaml with a build-failing required-section check, /submit/ backed by the new docs/SUBMISSION.md, and the client-hydrated /model/?id= page with the architecture renderer. Layout geometry and display formatting are computed in Python so pytest checks what ships."
```

---

## Phase gate

Every item must pass before Phase 9 starts.

```bash
make check
lychee --no-progress --accept 200,206,429 dist/ docs/ ./*.md
```

- [ ] `/explore/` loads every record: the paper rows equal `len(reg.live_cells())`, derived
- [ ] each of the five filter axes has its own passing test, and the axes partition the rows
- [ ] the browser filter cross-checks itself against the build-time counts on every load
- [ ] the explore payload size is **printed** and under 120 KiB
- [ ] `/about/card/` renders all eight required sections, and every id reaches the HTML
- [ ] deleting a section makes `build.py` **exit non-zero**, demonstrated, not asserted only
- [ ] the licensing section declares MIT, CC-BY-4.0 and CC-BY-NC-SA-4.0, with the last marked `vendored: false`
- [ ] `docs/SUBMISSION.md` exists, and `CLAUDE.md`'s reference to it resolves
- [ ] every tier, division and badge names only guard layers that exist in `tools/guard/`
- [ ] the `predict.py` signature appears verbatim in the guide
- [ ] the lab's MLP renders as 41 to 64 to 32 to 16 to 1 with **5,313** parameters, per layer as well as in total
- [ ] the GNN-with-pooling fixture has no overlapping pair of blocks
- [ ] the 40-layer fixture stays inside the canvas, does not overlap, and drops its labels
- [ ] block height is proportional to layer width, asserted as an exact ratio
- [ ] the feature-legality badge flips when the guard is made to fail, and no status literal sits in the template
- [ ] `innerHTML` appears in neither `model.js` nor `arch-render.js`
- [ ] both theme files declare the same set of `--arch-*` variables
- [ ] no page exceeds 88 KB, sizes printed
- [ ] every internal link on the four pages resolves, in pytest and in lychee
- [ ] no em dash in `docs/CARD.yaml`, `docs/SUBMISSION.md` or any new template

## Review prompt

```
Use a frontend reviewer and a security reviewer on the Phase 8 diff.

Frontend: check /explore/, /about/card/, /submit/ and /model/?id= in both themes.
Contrast >= 4.5:1 on every cell state and every guard badge. The virtualized
table must be keyboard reachable and must report its true row count to assistive
technology, not just the rows currently in the DOM. The architecture diagram must
be readable without colour and must have a non-visual equivalent. Report only
WCAG AA failures.

Security: /model/ takes its id from a query string and renders submitted strings.
Confirm the id cannot reach a fetch path without first matching an entry in the
index, that no submitted string reaches the DOM other than through textContent,
and that the Markdown renderer cannot emit raw HTML from a document. Then confirm
the feature-legality badge is produced by running the guard rather than by
reading a field a submitter controls. Report only exploitable gaps.

Correctness: confirm tools/explore.py is the only place a percent metric is
scaled for display in this diff, that static/js/explore-filter.js is a faithful
transcription of tools.explore.filter_rows, and that no geometry is computed in
static/js/arch-render.js. Report only correctness and requirement gaps, not style.
```


