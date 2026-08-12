# Phase 5 - Cell Pages Implementation Plan

> **For agentic workers:** Implement this plan task-by-task - either dispatch a fresh subagent per task (recommended) or execute inline with review checkpoints. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** pre-render one page per live `(task, pdk, stage)` combo - 232 of them - each serving all of that task's metric rows, with the published baseline pinned above the ranking, filters, CSV and JSON export, and a predicted-versus-actual panel that degrades to the released PNG until raw predictions exist.

**Architecture:** `build.py` loops `reg.live_combos()`, asks `tools/cellpage.py` for a fully computed context object, and renders `templates/pages/cell.html` to `dist/cell/<task>/<pdk>/<stage>/index.html`. `tools/urls.py` owns the route, and both the matrix and the page writer call it, so a link and its target cannot drift. Templates hold loops and conditionals only. Two small vanilla JS files, one per feature, both progressive enhancements over a page that is complete without them.

**Tech stack:** Python 3.11+, `uv`, Jinja2, `pytest`, `mypy --strict`, `ruff`, vanilla JS, CSS custom properties, `lychee`, `pa11y-ci`.

## Global constraints

Copied from `PLAN.md`; every task's requirements implicitly include these.

- Python **3.11+**, type hints on all public functions, `ruff` and `mypy` clean.
- **Registries are the only source of vocabulary.** Never hardcode a task, PDK, stage, metric or circuit name outside `data/registry/`.
- **Counts are derived, never literal.** 46, 232, 880, 856, 120, 40, 24 are computed. `tests/` may assert them as expected values; `tools/` may not contain them. `tests/test_no_hardcoded_counts.py` from Phase 1 scans `tools/` and will fail this phase if a new module writes one down.
- **Percent metrics** (`mape`, `mape_p95`, `mape_top5`, `tpr`, `tnr`) are stored as fractions in `[0, 1]`. The `x100` happens **exactly once, at display**, and in this phase that means inside `cellpage.format_value` and nowhere else - not in a template, not in JavaScript.
- **Every record carries an explicit `source`** (`paper`, `synthetic`, `submission`).
- **Never commit files over 1 MB**, and never commit anything under `data/` by hand.
- `dist/` targets **~20 MB**, so the per-page budget is roughly **88 KB** across 232 cell pages. Measure it, do not assume it.
- CSS custom properties for all colour; both themes implement the same variable contract.
- Conventional commits. Branch `phase-5/cell-pages`. Never push to `main`.
- **Never use an em dash** in prose, code comments or generated copy.

## Inherited interfaces

This phase writes no vocabulary, no baseline and no ranking logic. It consumes what the four phases before it produced, and every signature below is treated as locked. If a phase named something differently, adapt in **one** import line at the top of `tools/cellpage.py` rather than reaching around it.

**Phase 1, `tools/registry.py`**

```python
reg.tasks() / metrics() / stages() / pdks() / circuits()   # tuples, stages in order
reg.task(id) / metric(id) / stage(id) / pdk(id)            # KeyError on unknown
reg.is_void(task_id, stage_id) -> bool
reg.is_degenerate(task_id, metric_id, stage_id) -> bool
reg.is_saturated(task_id, metric_id, stage_id) -> bool
reg.precision(task_id, metric_id) -> int                   # DISPLAY decimal places
reg.metric_rows() -> tuple[tuple[str, str], ...]           # 46
reg.live_combos() -> tuple[tuple[str, str, str], ...]      # 232, (task, pdk, stage)
reg.live_cells() -> tuple[tuple[str, str, str, str], ...]  # 880
```

**Phase 2, `data/baseline.json` and its reader**

```python
class BoundKind(StrEnum): EXACT | GREATER_THAN | LESS_THAN | ABSENT
@dataclass(frozen=True) class Bound: kind: BoundKind; value: float | None
baseline.lookup(task_id, metric_id, pdk_id, stage_id) -> Baseline   # .bound is the Bound
```

A sentinel is a **one-sided bound in storage units**: `> 10000 %` is `GREATER_THAN 100.0`, `< -1` is `LESS_THAN -1.0`. A degenerate cell is `ABSENT`. A void cell has no entry at all.

**Phase 3, the render skeleton**

`build.py` with a Jinja2 `Environment`, `templates/base.html` exposing `{% block title %}`, `{% block head %}` and `{% block content %}`, `templates/pages/matrix.html`, `static/css/base.css`, `static/css/themes/*.css`.

**Phase 4, ranking and shards**

```python
class Comparison(StrEnum): BETTER | EQUAL | WORSE | UNDECIDABLE
class CellState(StrEnum): BEATS_BASELINE | MATCHES_BASELINE | BASELINE_LEADS | NO_ENTRY | SATURATED
ranking.rank_key(metric_id, value) -> float          # always ascending, best first
ranking.compare(task_id, metric_id, challenger: Bound, incumbent: Bound) -> Comparison
ranking.cell_state(task_id, metric_id, stage_id, baseline: Bound, entries: tuple[Bound, ...]) -> CellState
shards.load(task_id, pdk_id, stage_id) -> tuple[Record, ...]
```

A `Record` carries `metric`, `model_id`, `model_label`, `source`, `value_macro`, `value_pooled` and `ranked_on`. **Only `total_area_prediction` has real data**, at 20 of the 232 combos. The other 212 pages render with zero entries, and that is a first-class case in this phase rather than an afterthought.

## Three traps this phase walks into

Named here because each one produces a page that looks right.

**A degenerate row still lists its entries.** `ranking.cell_state` returns `NO_ENTRY` when every entry is `UNDECIDABLE`, which is exactly what happens against an `ABSENT` baseline. A template that decides whether to render entries from the *state* hides real submissions on all 24 degenerate cells while showing "no submissions yet". The state colours the row; `entries` decides what is listed. These are two different questions and the context object answers them separately.

**"Degenerate cells never print a number" cannot be tested by looking for digits.** Table 8's own text for those cells is `No positive or negative error, n_p = n_n = 0`, which contains a `0`. A no-digits assertion fails on the paper's own words. The test asserts the structured facts instead: `baseline_kind == "absent"` and `baseline_value is None`.

**The matrix links per cell, the page exists per combo.** 880 links point at 232 pages, so every link carries a `#metric-<id>` fragment. A link test that only checks the file exists passes while every fragment is dead. `urls.metric_anchor` produces both the fragment and the `id` attribute, and the test asserts the anchor is present in the target file.

## File structure

| File | Responsibility |
|---|---|
| `tools/urls.py` | the route: `cell_url`, `metric_anchor`, `cell_output_path` |
| `tools/cellpage.py` | all computation for one page: rows, formatting, ranks, verdicts, payload |
| `tools/plots.py` | the predicted-versus-actual asset URL, and the CLI that collects the PNGs for the Release |
| `build.py` | modified: renders the 232 pages, accepts an output directory |
| `templates/pages/cell.html` | loops and conditionals only |
| `templates/pages/matrix.html` | modified: every cell becomes a link via `urls.cell_url` |
| `static/css/cell.css` | cell-page styling, every colour a `var()` |
| `static/js/cell-filters.js` | entry filtering, progressive enhancement |
| `static/js/cell-export.js` | CSV and JSON download from the inlined payload |
| `data/registry/metrics.json` | modified: `unit_kind` added |
| `tests/conftest.py` | the session-scoped `site` fixture, built once |
| `tests/linkutil.py` | stdlib HTML link extraction, shared by the link tests |
| `tests/test_cells.py` | routing, states, formatting, empty pages, budget, links |

---

### Task 1: The URL contract and 232 rendered pages

The vertical slice. One route module, one skeleton template, one build loop, and the two tests that matter most: every live combo has a page, and every matrix link lands on one.

**Files:**
- Create: `tools/urls.py`
- Create: `templates/pages/cell.html`
- Create: `tests/conftest.py` (extend it if Phase 3 already created one)
- Create: `tests/linkutil.py`, `tests/test_cells.py`
- Modify: `build.py`, `templates/pages/matrix.html`

**Interfaces:**
- Consumes: `reg.live_combos()`, `reg.is_void`, `reg.task/pdk/stage`, `reg.live_cells()`.
- Produces: `urls.BASE_PATH: str`, `urls.cell_url(task_id: str, pdk_id: str, stage_id: str, metric_id: str | None = None) -> str`, `urls.metric_anchor(metric_id: str) -> str`, `urls.cell_output_path(task_id: str, pdk_id: str, stage_id: str) -> PurePosixPath`, `build.build(dist: Path | None = None) -> Path`.

- [ ] **Step 1: Write the failing tests**

Create `tests/linkutil.py`:

```python
"""Link extraction for the link tests.

stdlib only. A regex over `href="..."` misses single-quoted attributes and
matches inside comments, and this is the only thing standing between the site
and 232 dead links.
"""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path

from tools import urls

_ATTR = {"a": "href", "link": "href", "img": "src", "script": "src"}


class _Collector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.found: list[str] = []
        self.ids: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        pairs = dict(attrs)
        element_id = pairs.get("id")
        if element_id:
            self.ids.add(element_id)
        key = _ATTR.get(tag)
        if key is None:
            return
        value = pairs.get(key)
        if value:
            self.found.append(value)


def _parse(path: Path) -> _Collector:
    parser = _Collector()
    parser.feed(path.read_text(encoding="utf-8"))
    parser.close()
    return parser


def links(path: Path) -> list[str]:
    return _parse(path).found


def anchors(path: Path) -> set[str]:
    return _parse(path).ids


def is_internal(href: str) -> bool:
    return not href.startswith(("http://", "https://", "mailto:", "data:", "#"))


def resolve(site: Path, href: str) -> Path:
    """Map one site-absolute href onto a file in the built site."""
    target = href.split("#", 1)[0].split("?", 1)[0]
    trailing_slash = target.endswith("/")
    relative = target.removeprefix(urls.BASE_PATH)
    candidate = site / relative if relative else site
    return candidate / "index.html" if trailing_slash or not relative else candidate
```

Create `tests/conftest.py`:

```python
"""Shared fixtures.

The site is built ONCE per session into a temp directory. Building per test
would run the 232-page render dozens of times; building into the repo's dist/
would make the assertions depend on whatever was last built by hand.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import build


@pytest.fixture(scope="session")
def site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build.build(tmp_path_factory.mktemp("dist"))
```

Create `tests/test_cells.py`:

```python
"""Cell pages: 232 combos, one page each, 880 metric rows across them.

Expected values live here, in tests. They must never appear in tools/.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests import linkutil
from tools import registry as reg
from tools import urls


def test_one_page_per_live_combo(site: Path) -> None:
    expected = {site / str(urls.cell_output_path(*c)) for c in reg.live_combos()}
    assert len(expected) == 232
    missing = sorted(str(p) for p in expected if not p.is_file())
    assert missing == []


def test_no_extra_pages_were_generated(site: Path) -> None:
    """A page for a void combo would be a page for a cell that does not exist."""
    found = {p.relative_to(site) for p in (site / "cell").rglob("index.html")}
    expected = {Path(str(urls.cell_output_path(*c))) for c in reg.live_combos()}
    assert found == expected


def test_cell_url_refuses_a_void_combo() -> None:
    with pytest.raises(KeyError):
        urls.cell_url("total_wirelength_prediction", "ng45", "floorplan")


def test_cell_url_refuses_a_metric_the_task_does_not_publish() -> None:
    """total_area publishes no MPE row. A link to one would be a dead anchor."""
    with pytest.raises(KeyError):
        urls.cell_url("total_area_prediction", "ng45", "cts", "mpe")


def test_every_matrix_cell_links_to_a_real_page_and_anchor(site: Path) -> None:
    """Zero 404s from the matrix, fragments included.

    The matrix and the page writer both call urls.cell_url, so this asserts the
    two agree rather than merely that some file exists.
    """
    hrefs = [h for h in linkutil.links(site / "index.html") if "/cell/" in h]
    assert len(hrefs) == 880

    cache: dict[Path, set[str]] = {}
    for href in hrefs:
        target = linkutil.resolve(site, href)
        assert target.is_file(), href
        assert "#" in href, f"a matrix link needs a metric anchor: {href}"
        fragment = href.split("#", 1)[1]
        ids = cache.setdefault(target, linkutil.anchors(target))
        assert fragment in ids, f"dead anchor: {href}"


def test_every_internal_link_on_every_page_resolves(site: Path) -> None:
    broken: list[str] = []
    for page in sorted(site.rglob("*.html")):
        for href in linkutil.links(page):
            if not linkutil.is_internal(href):
                continue
            assert href.startswith(urls.BASE_PATH), f"{page.name}: {href}"
            if not linkutil.resolve(site, href).is_file():
                broken.append(f"{page.relative_to(site)} -> {href}")
    assert broken == []
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `uv run pytest tests/test_cells.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'tools.urls'`

- [ ] **Step 3: Write the route module**

Create `tools/urls.py`:

```python
"""Every URL the site emits, in one module.

The matrix and the cell-page writer both call cell_url(). If they computed the
path separately, a change to one would leave the other pointing at a 404, and in
a static build a 404 is invisible until someone clicks it.

The matrix links per CELL and pages exist per COMBO, so a matrix link carries a
`#metric-<id>` fragment. metric_anchor() produces both that fragment and the id
attribute the template renders, for the same reason.
"""

from __future__ import annotations

import os
from pathlib import PurePosixPath

from tools import registry as reg

# Site root. A GitHub Pages project site is served under /<repo>/, so Phase 9
# sets SITE_BASE at deploy time. Everything internal is rendered relative to
# this one string, and cell_output_path strips it, so the two cannot disagree.
BASE_PATH: str = os.environ.get("SITE_BASE", "/")

ANCHOR_PREFIX = "metric-"


def metric_anchor(metric_id: str) -> str:
    """The id of one metric section, and the fragment that links to it."""
    reg.metric(metric_id)
    return f"{ANCHOR_PREFIX}{metric_id}"


def cell_url(
    task_id: str, pdk_id: str, stage_id: str, metric_id: str | None = None
) -> str:
    """Site-absolute URL of one cell page, with a trailing slash.

    Raises on a void combo and on a metric the task does not publish. Both are
    links the matrix must not be able to express, and raising here is what makes
    that structural rather than a convention.
    """
    reg.task(task_id)
    reg.pdk(pdk_id)
    reg.stage(stage_id)
    if reg.is_void(task_id, stage_id):
        raise KeyError(f"void combo has no page: {task_id} {pdk_id} {stage_id}")

    url = f"{BASE_PATH}cell/{task_id}/{pdk_id}/{stage_id}/"
    if metric_id is None:
        return url
    if metric_id not in reg.task(task_id).metrics:
        raise KeyError(f"{task_id} publishes no {metric_id} row")
    return f"{url}#{metric_anchor(metric_id)}"


def cell_output_path(task_id: str, pdk_id: str, stage_id: str) -> PurePosixPath:
    """Path under dist/ for that URL, derived FROM the URL and never in parallel."""
    url = cell_url(task_id, pdk_id, stage_id)
    return PurePosixPath(url.removeprefix(BASE_PATH)) / "index.html"
```

- [ ] **Step 4: Add the skeleton template**

Create `templates/pages/cell.html`. Task 3 fills in the rows; this is the shell the route test needs, and it already carries the metric anchors so the fragment assertion is exercised from the start:

```jinja
{% extends "base.html" %}

{% block title %}{{ page.task_label }} - {{ page.pdk_label }} - {{ page.stage_label }}{% endblock %}

{% block content %}
<nav class="breadcrumb" aria-label="Breadcrumb">
  <ol>
    <li><a href="{{ base_path }}">Matrix</a></li>
    <li aria-current="page">{{ page.task_label }}</li>
  </ol>
</nav>

<header class="cell-header">
  <h1>{{ page.task_label }}</h1>
  <dl class="combo">
    <div><dt>PDK</dt><dd>{{ page.pdk_label }}</dd></div>
    <div><dt>Predicting from</dt><dd>{{ page.stage_label }}</dd></div>
    <div><dt>Target unit</dt><dd>{{ page.task_unit }}</dd></div>
  </dl>
</header>

{% for row in page.rows %}
<section class="metric-row" id="{{ row.anchor }}" data-metric="{{ row.metric_id }}">
  <h2>{{ row.label }}</h2>
</section>
{% endfor %}
{% endblock %}
```

- [ ] **Step 5: Render the pages from build.py**

In `build.py`, give `build()` an output directory and add the loop. The page object comes from Task 2; for this task, pass a minimal namespace so the route is exercised end to end and the shape is already the one Task 2 fills:

```python
def build(dist: Path | None = None) -> Path:
    """Render the site. Returns the output directory."""
    out = Path(dist) if dist is not None else DIST
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    env = _environment()
    _render_matrix(env, out)
    written = _render_cell_pages(env, out)
    _copy_static(out)
    print(f"build: {written} cell pages")
    return out


def _render_cell_pages(env: Environment, out: Path) -> int:
    template = env.get_template("pages/cell.html")
    written = 0
    for task_id, pdk_id, stage_id in reg.live_combos():
        page = cellpage.page(task_id, pdk_id, stage_id)
        target = out / str(urls.cell_output_path(task_id, pdk_id, stage_id))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            template.render(page=page, base_path=urls.BASE_PATH),
            encoding="utf-8",
        )
        written += 1
    return written
```

Create `tools/cellpage.py` with only what this task needs - `page()` returning a frozen dataclass carrying `task_label`, `pdk_label`, `stage_label`, `task_unit`, `url` and a `rows` tuple of `(metric_id, label, anchor)`. Task 2 replaces the body; the signature does not change.

- [ ] **Step 6: Link every matrix cell**

In `templates/pages/matrix.html`, wrap each cell's content in an anchor. The href comes from the context dict, not from string building in the template:

```jinja
<td class="cell state-{{ cell.state }}" data-state="{{ cell.state }}">
  <a href="{{ cell.url }}">
    <span class="glyph" aria-hidden="true">{{ cell.glyph }}</span>
    <span class="visually-hidden">{{ cell.state_label }}</span>
  </a>
</td>
```

and in `build.py`'s matrix context, set `"url": urls.cell_url(task_id, pdk_id, stage_id, metric_id)` on every live cell.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run pytest tests/test_cells.py -v`
Expected: 6 passed. 232 pages exist, 880 matrix links resolve, every fragment lands on a real section id.

- [ ] **Step 8: Verify lint and types**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy`
Expected: all clean.

- [ ] **Step 9: Commit**

```bash
git add tools/urls.py tools/cellpage.py templates/pages/cell.html templates/pages/matrix.html build.py tests/conftest.py tests/linkutil.py tests/test_cells.py
git commit -m "feat(cells): route 232 cell pages and link every matrix cell to one"
```

---

### Task 2: The page context builder

Everything the template is not allowed to do. Rows, display strings, ranks, verdicts and the export payload, all computed here as pure functions and all testable without rendering a byte of HTML.

**Files:**
- Modify: `data/registry/metrics.json`, `tools/registry.py`
- Modify: `tools/cellpage.py`
- Test: `tests/test_cells.py`, `tests/test_registry.py`

**Interfaces:**
- Consumes: `reg.*`, `baseline.lookup`, `ranking.compare`, `ranking.rank_key`, `ranking.cell_state`, `shards.load`.
- Produces: `cellpage.Entry`, `cellpage.MetricRow`, `cellpage.CellPage`, `cellpage.page(task_id, pdk_id, stage_id) -> CellPage`, `cellpage.format_value(task_id, metric_id, value) -> str`, `cellpage.format_bound(task_id, metric_id, bound) -> str`, `cellpage.payload(page) -> str`.

- [ ] **Step 1: Write the failing registry test for `unit_kind`**

A metric row needs a unit, and the three families differ: `mae` carries the target's unit, `mape` is a percent, `r2` is dimensionless. Nothing in the registry says which, and a `{"r2"}` set literal in `tools/` would break the rule that registries are the only vocabulary. The field lands in the registry, where the truth belongs.

Append to `tests/test_registry.py`:

```python
UNIT_KINDS = {
    "mae": "target",
    "mape": "percent",
    "r2": "none",
    "mpe": "target",
    "mne": "target",
    "tpr": "percent",
    "tnr": "percent",
    "mae_p95": "target",
    "mape_p95": "percent",
    "mae_top5": "target",
    "mape_top5": "percent",
}


def test_every_metric_declares_a_unit_kind() -> None:
    assert {m.id: m.unit_kind for m in reg.metrics()} == UNIT_KINDS


def test_unit_kind_and_percent_cannot_drift() -> None:
    """Two fields encoding one fact. Pin them to each other or they diverge."""
    for m in reg.metrics():
        assert (m.unit_kind == "percent") == m.percent, m.id
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_registry.py -v`
Expected: FAIL, `TypeError: Metric.__init__() got an unexpected keyword argument 'unit_kind'`

- [ ] **Step 3: Add the field**

Add `"unit_kind"` to each of the 11 objects in `data/registry/metrics.json` per the table above, and to the `Metric` dataclass in `tools/registry.py`:

```python
@dataclass(frozen=True, slots=True)
class Metric:
    id: str
    label: str
    long_label: str
    table8_label: str
    direction: str
    bias: str | None
    percent: bool
    unit_kind: str
    precision: int
```

Run: `uv run pytest tests/test_registry.py -v` -> all pass.

- [ ] **Step 4: Write the failing context tests**

Append to `tests/test_cells.py`:

```python
from tools import cellpage
from tools.baseline import Bound, BoundKind


def _pages() -> list[cellpage.CellPage]:
    return [cellpage.page(*combo) for combo in reg.live_combos()]


def test_the_pages_carry_every_live_cell_exactly_once() -> None:
    """232 pages x that task's metric set is the 880-cell grid, re-derived."""
    seen = [
        (p.task_id, row.metric_id, p.pdk_id, p.stage_id)
        for p in _pages()
        for row in p.rows
    ]
    assert len(seen) == 880
    assert set(seen) == set(reg.live_cells())


def test_every_row_has_exactly_one_state_and_one_mode() -> None:
    states = {s.value for s in ranking.CellState}
    modes = {"ranked", "no_comparison", "not_ranked"}
    for page in _pages():
        for row in page.rows:
            assert row.state in states
            assert row.mode in modes


def test_the_partition_of_rows_matches_the_registry() -> None:
    """40 / 24 / 120 again, this time as rendered. A page that classified rows
    itself instead of asking the registry would drift from the matrix here."""
    rows = [(p, r) for p in _pages() for r in p.rows]
    degenerate = [r for _p, r in rows if r.baseline_kind == "absent"]
    saturated = [r for _p, r in rows if r.mode == "not_ranked"]
    sentinels = [
        r for _p, r in rows if r.baseline_kind in {"greater_than", "less_than"}
    ]
    assert len(degenerate) == 24
    assert len(saturated) == 120
    assert len(sentinels) == 32
    assert sum(1 for r in sentinels if r.baseline_kind == "greater_than") == 20
    assert sum(1 for r in sentinels if r.baseline_kind == "less_than") == 12


def test_degenerate_rows_carry_no_baseline_number() -> None:
    """Asserted structurally. A no-digits assertion on the rendered text fails,
    because Table 8's own wording for these cells contains 'n_p = n_n = 0'."""
    for page in _pages():
        for row in page.rows:
            if reg.is_degenerate(page.task_id, row.metric_id, page.stage_id):
                assert row.baseline_kind == "absent"
                assert row.baseline_value is None
                assert row.mode == "no_comparison"


def test_percent_metrics_are_scaled_once_at_display() -> None:
    """0.1243 stored is 12.43 % displayed. Twice gives 1243 %, never gives 0.12."""
    assert cellpage.format_value("total_area_prediction", "mape", 0.1243) == "12.43 %"
    assert cellpage.format_value("worst_slack_prediction", "tpr", 1.0) == "100.00 %"
    assert (
        cellpage.format_value("total_area_prediction", "mae", 1781.9696) == "1,781.97"
    )


def test_display_precision_comes_from_the_registry() -> None:
    assert (
        cellpage.format_value("cell_arc_delay_prediction", "mae", 0.00012345)
        == "0.0001"
    )
    assert cellpage.format_value("total_area_prediction", "r2", 0.98765) == "0.988"


def test_sentinel_bounds_render_as_bounds() -> None:
    over = Bound(BoundKind.GREATER_THAN, 100.0)
    under = Bound(BoundKind.LESS_THAN, -1.0)
    assert (
        cellpage.format_bound("cell_arc_delay_prediction", "mape", over)
        == "> 10,000.00 %"
    )
    assert cellpage.format_bound("cell_arc_delay_prediction", "r2", under) == "< -1.000"


def test_an_entry_ranks_on_the_basis_it_declares() -> None:
    """ranked_on: macro means macro, even when pooled flatters the entry. Picking
    the better of the two per entry would make the column meaningless, because
    the two are different estimators of different quantities."""
    record = shards.Record(
        metric="mae",
        model_id="m1",
        model_label="M1",
        source="submission",
        value_macro=1789.6,
        value_pooled=1.0,
        ranked_on="macro",
    )
    entry = cellpage.entry_from(record, "total_area_prediction", "mae")
    assert entry.value == 1789.6


def test_entries_are_listed_even_when_the_state_says_no_entry() -> None:
    """Against an absent baseline every comparison is UNDECIDABLE, and Phase 4's
    cell_state collapses that to NO_ENTRY. Deciding what to LIST from the state
    would hide real submissions on all 24 degenerate cells."""
    row = cellpage.metric_row(
        "worst_slack_prediction",
        "mpe",
        "ng45",
        "global_route",
        records=(
            shards.Record(
                metric="mpe",
                model_id="m1",
                model_label="M1",
                source="submission",
                value_macro=0.5,
                value_pooled=None,
                ranked_on="macro",
            ),
        ),
    )
    assert row.state == "no_entry"
    assert len(row.entries) == 1
    assert row.entries[0].verdict == "undecidable"


def test_saturated_rows_are_never_ranked() -> None:
    for page in _pages():
        for row in page.rows:
            if reg.is_saturated(page.task_id, row.metric_id, page.stage_id):
                assert row.mode == "not_ranked"
                assert all(e.rank is None for e in row.entries)


def test_the_payload_is_valid_json_with_no_nan() -> None:
    for page in _pages():
        data = json.loads(cellpage.payload(page))
        assert data["combo"]["task"] == page.task_id
        assert len(data["rows"]) == len(page.rows)


def test_the_payload_cannot_close_its_own_script_element() -> None:
    assert "</" not in cellpage.payload(
        cellpage.page("total_area_prediction", "ng45", "cts")
    )
```

- [ ] **Step 5: Run to verify they fail**

Run: `uv run pytest tests/test_cells.py -v`
Expected: FAIL, `AttributeError: module 'tools.cellpage' has no attribute 'MetricRow'`

- [ ] **Step 6: Implement the context builder**

Replace `tools/cellpage.py`:

```python
"""Everything one cell page needs, computed so the template can only loop.

Three things here are easy to get wrong and expensive to get wrong.

**A degenerate row still lists its entries.** ranking.cell_state returns NO_ENTRY
when every entry is UNDECIDABLE, which is exactly what happens against an absent
baseline. The state colours the row; `entries` decides what is listed. Reading
the first as the second hides real submissions on all 24 degenerate cells.

**The x100 for percent metrics happens in format_value and nowhere else.** Not in
the template, not in JavaScript, not in the export. Everything under data/ is a
fraction; every string a reader sees came through here.

**An entry ranks on the basis it declares.** Table 8's baseline is row-pooled and
our models are macro-mean, so the page shows both and ranks on the declared one.
Choosing per entry whichever number looks better would silently mix estimators.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from tools import baseline, ranking, registry as reg, shards, urls
from tools.baseline import Bound, BoundKind
from tools.plots import Plot, plot_for

NO_BASELINE = "not measured"
DEGENERATE_NOTE = "No positive or negative error, n_p = n_n = 0"
SATURATED_NOTE = (
    "The tool estimate has already converged on the detailed-route value here, "
    "so the baseline is at its optimum. This cell is never ranked."
)
BASELINE_PROVENANCE = (
    "Published baseline from Table 8 of arXiv:2605.06952, pooled across circuits."
)


@dataclass(frozen=True, slots=True)
class Entry:
    model_id: str
    model_label: str
    source: str
    value: float | None
    display: str
    pooled_display: str
    verdict: str
    rank: int | None


@dataclass(frozen=True, slots=True)
class MetricRow:
    metric_id: str
    label: str
    anchor: str
    unit: str
    direction: str
    state: str
    mode: str
    baseline_kind: str
    baseline_value: float | None
    baseline_display: str
    baseline_note: str
    entries: tuple[Entry, ...]
    undecidable: int


@dataclass(frozen=True, slots=True)
class CellPage:
    task_id: str
    task_label: str
    task_unit: str
    pdk_id: str
    pdk_label: str
    stage_id: str
    stage_label: str
    url: str
    rows: tuple[MetricRow, ...]
    entry_count: int
    all_saturated: bool
    plot: Plot | None
    provenance: str


def row_unit(task_id: str, metric_id: str) -> str:
    """Display unit for one metric row, from the registry's unit_kind."""
    kind = reg.metric(metric_id).unit_kind
    if kind == "percent":
        return "%"
    if kind == "none":
        return ""
    return reg.task(task_id).unit


def format_value(task_id: str, metric_id: str, value: float) -> str:
    """Storage units in, display string out.

    This function is the display boundary. Percent metrics are stored as
    fractions and multiplied by 100 exactly here; precision is per (task, metric)
    because the lab publishes five tasks at 4dp and everything else at 2 or 3.
    """
    metric = reg.metric(metric_id)
    scaled = value * 100.0 if metric.percent else value
    text = f"{scaled:,.{reg.precision(task_id, metric_id)}f}"
    return f"{text} %" if metric.percent else text


def format_bound(task_id: str, metric_id: str, bound: Bound) -> str:
    """A published baseline as a reader sees it, including the two sentinels.

    The sentinel string is derived rather than echoed from the paper, so the
    threshold a reader sees and the threshold the ranking used are the same
    number formatted once.
    """
    if bound.kind is BoundKind.ABSENT or bound.value is None:
        return NO_BASELINE
    text = format_value(task_id, metric_id, bound.value)
    if bound.kind is BoundKind.GREATER_THAN:
        return f"> {text}"
    if bound.kind is BoundKind.LESS_THAN:
        return f"< {text}"
    return text


def _ranking_value(record: shards.Record) -> float | None:
    """The number this record declares as its ranking basis."""
    return record.value_macro if record.ranked_on == "macro" else record.value_pooled


def entry_from(record: shards.Record, task_id: str, metric_id: str) -> Entry:
    value = _ranking_value(record)
    pooled = record.value_pooled
    return Entry(
        model_id=record.model_id,
        model_label=record.model_label,
        source=record.source,
        value=value,
        display=NO_BASELINE
        if value is None
        else format_value(task_id, metric_id, value),
        pooled_display=""
        if pooled is None
        else format_value(task_id, metric_id, pooled),
        verdict="",
        rank=None,
    )


def _ranked(
    task_id: str, metric_id: str, stage_id: str, bound: Bound, entries: list[Entry]
) -> tuple[Entry, ...]:
    """Sort best first and number them, ties sharing a rank.

    Direction lives in the registry and is read by ranking.rank_key, so nothing
    here has to remember that R2 inverts.
    """
    rankable = [e for e in entries if e.value is not None]
    unrankable = [e for e in entries if e.value is None]
    rankable.sort(key=lambda e: ranking.rank_key(metric_id, e.value or 0.0))

    ranked: list[Entry] = []
    previous: Entry | None = None
    for position, entry in enumerate(rankable, start=1):
        verdict = ranking.compare(
            task_id, metric_id, Bound(BoundKind.EXACT, entry.value), bound
        ).value
        tied = (
            previous is not None
            and ranking.compare(
                task_id,
                metric_id,
                Bound(BoundKind.EXACT, entry.value),
                Bound(BoundKind.EXACT, previous.value),
            )
            is ranking.Comparison.EQUAL
        )
        rank = previous.rank if tied and previous is not None else position
        entry = dataclasses.replace(entry, verdict=verdict, rank=rank)
        ranked.append(entry)
        previous = entry

    return tuple(ranked) + tuple(
        dataclasses.replace(e, verdict=ranking.Comparison.UNDECIDABLE.value)
        for e in unrankable
    )


def metric_row(
    task_id: str,
    metric_id: str,
    pdk_id: str,
    stage_id: str,
    records: tuple[shards.Record, ...] | None = None,
) -> MetricRow:
    if records is None:
        records = tuple(
            r for r in shards.load(task_id, pdk_id, stage_id) if r.metric == metric_id
        )
    bound = baseline.lookup(task_id, metric_id, pdk_id, stage_id).bound
    entries = [entry_from(r, task_id, metric_id) for r in records]

    if reg.is_saturated(task_id, metric_id, stage_id):
        mode, note = "not_ranked", SATURATED_NOTE
        placed = tuple(dataclasses.replace(e, verdict="", rank=None) for e in entries)
    else:
        placed = _ranked(task_id, metric_id, stage_id, bound, entries)
        if bound.kind is BoundKind.ABSENT:
            mode, note = "no_comparison", DEGENERATE_NOTE
        else:
            mode, note = "ranked", ""

    state = ranking.cell_state(
        task_id,
        metric_id,
        stage_id,
        bound,
        tuple(Bound(BoundKind.EXACT, e.value) for e in placed if e.value is not None),
    )
    metric = reg.metric(metric_id)
    return MetricRow(
        metric_id=metric_id,
        label=metric.long_label,
        anchor=urls.metric_anchor(metric_id),
        unit=row_unit(task_id, metric_id),
        direction=metric.direction,
        state=state.value,
        mode=mode,
        baseline_kind=bound.kind.value,
        baseline_value=bound.value,
        baseline_display=format_bound(task_id, metric_id, bound),
        baseline_note=note,
        entries=placed,
        undecidable=sum(1 for e in placed if e.verdict == "undecidable"),
    )


def page(task_id: str, pdk_id: str, stage_id: str) -> CellPage:
    task, pdk, stage = reg.task(task_id), reg.pdk(pdk_id), reg.stage(stage_id)
    records = shards.load(task_id, pdk_id, stage_id)
    rows = tuple(
        metric_row(
            task_id,
            metric_id,
            pdk_id,
            stage_id,
            tuple(r for r in records if r.metric == metric_id),
        )
        for metric_id in task.metrics
    )
    return CellPage(
        task_id=task_id,
        task_label=task.label,
        task_unit=task.unit,
        pdk_id=pdk_id,
        pdk_label=pdk.label,
        stage_id=stage_id,
        stage_label=stage.label,
        url=urls.cell_url(task_id, pdk_id, stage_id),
        rows=rows,
        entry_count=sum(len(r.entries) for r in rows),
        all_saturated=all(r.mode == "not_ranked" for r in rows),
        plot=plot_for(task_id, pdk_id, stage_id),
        provenance=BASELINE_PROVENANCE,
    )


def payload(cell_page: CellPage) -> str:
    """The page's own data as JSON, for the export buttons.

    allow_nan=False is load-bearing. json.dumps writes bare NaN and Infinity by
    default, which is not JSON and which JSON.parse rejects, so a non-number
    reaching this point fails the build instead of shipping a broken download.

    Both value forms are exported: `value` in storage units and `display` as the
    string on screen. Exporting one of them is how the x100 ambiguity gets back
    in through a spreadsheet.
    """
    data: dict[str, Any] = {
        "combo": {
            "task": cell_page.task_id,
            "pdk": cell_page.pdk_id,
            "stage": cell_page.stage_id,
            "unit": cell_page.task_unit,
        },
        "provenance": cell_page.provenance,
        "rows": [
            {
                "metric": row.metric_id,
                "label": row.label,
                "unit": row.unit,
                "direction": row.direction,
                "state": row.state,
                "mode": row.mode,
                "baseline_kind": row.baseline_kind,
                "baseline_value": row.baseline_value,
                "baseline_display": row.baseline_display,
                "entries": [
                    {
                        "model": e.model_id,
                        "label": e.model_label,
                        "source": e.source,
                        "value": e.value,
                        "display": e.display,
                        "rank": e.rank,
                        "verdict": e.verdict,
                    }
                    for e in row.entries
                ],
            }
            for row in cell_page.rows
        ],
    }
    text = json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    # A JSON string containing </script> would end the element early. Escaping
    # the three characters that can start one keeps the payload inert.
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
```

Add `import dataclasses` at the top with the other stdlib imports.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run pytest tests/test_cells.py tests/test_registry.py -v`
Expected: all pass, including the 880-cell re-derivation and the 24 / 120 / 32 partition.

- [ ] **Step 8: Commit**

```bash
git add data/registry/metrics.json tools/registry.py tools/cellpage.py tests/test_cells.py tests/test_registry.py
git commit -m "feat(cells): compute the cell page context, states and export payload"
```

---

### Task 3: The template and its stylesheet

The baseline pinned above the ranking, the three notices that must not be conflated, and the empty state that 212 of the 232 pages render.

**Files:**
- Modify: `templates/pages/cell.html`
- Create: `static/css/cell.css`
- Modify: `build.py`
- Test: `tests/test_cells.py`

**Interfaces:**
- Consumes: `cellpage.CellPage`.
- Produces: rendered HTML whose contract is `section.metric-row[data-metric][data-state][data-mode]`, `.baseline[data-baseline]` before `table.ranking`, and `tr[data-model][data-source][data-verdict]`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cells.py`:

```python
def _sections(html: str) -> list[str]:
    """Split a page into its metric-row sections, in document order."""
    return html.split('<section class="metric-row"')[1:]


def test_the_baseline_is_pinned_above_the_ranking_on_every_page(site: Path) -> None:
    for combo in reg.live_combos():
        html = (site / str(urls.cell_output_path(*combo))).read_text(encoding="utf-8")
        sections = _sections(html)
        assert len(sections) == len(reg.task(combo[0]).metrics)
        for section in sections:
            assert 'class="baseline"' in section
            if 'class="ranking"' in section:
                assert section.index('class="baseline"') < section.index(
                    'class="ranking"'
                )


def test_saturated_rows_render_the_notice_and_no_ranking(site: Path) -> None:
    for page in _pages():
        html = (
            site / str(urls.cell_output_path(page.task_id, page.pdk_id, page.stage_id))
        ).read_text()
        for section, row in zip(_sections(html), page.rows, strict=True):
            if row.mode != "not_ranked":
                continue
            assert 'data-mode="not_ranked"' in section
            assert "never ranked" in section
            assert 'class="ranking"' not in section
            assert "data-rank" not in section


def test_degenerate_rows_render_the_paper_note_and_no_comparison(site: Path) -> None:
    for page in _pages():
        html = (
            site / str(urls.cell_output_path(page.task_id, page.pdk_id, page.stage_id))
        ).read_text()
        for section, row in zip(_sections(html), page.rows, strict=True):
            if row.baseline_kind != "absent":
                continue
            assert 'data-baseline="absent"' in section
            assert "n_p = n_n = 0" in section
            assert cellpage.NO_BASELINE in section
            assert "vs baseline" not in section


def test_sentinel_rows_render_the_bound(site: Path) -> None:
    seen = 0
    for page in _pages():
        html = (
            site / str(urls.cell_output_path(page.task_id, page.pdk_id, page.stage_id))
        ).read_text()
        for section, row in zip(_sections(html), page.rows, strict=True):
            if row.baseline_kind not in {"greater_than", "less_than"}:
                continue
            seen += 1
            assert row.baseline_display in section
            assert "threshold" in section
    assert seen == 32


def test_an_undecidable_entry_says_so_rather_than_guessing() -> None:
    """A submission on the wrong side of a sentinel is neither a win nor a loss.
    Rendering it as a loss would be a fabrication."""
    html = render_row(
        cellpage.metric_row(
            "cell_arc_delay_prediction",
            "r2",
            "ng45",
            "cts",
            records=(
                shards.Record(
                    metric="r2",
                    model_id="m1",
                    model_label="M1",
                    source="submission",
                    value_macro=-3.0,
                    value_pooled=None,
                    ranked_on="macro",
                ),
            ),
        )
    )
    assert 'data-verdict="undecidable"' in html
    assert "no comparison" in html


def test_the_empty_pages_render_an_empty_state_not_a_broken_table(site: Path) -> None:
    empty = [c for c in reg.live_combos() if not shards.load(*c)]
    assert empty, "if every combo has data this test is obsolete, not passing"
    for combo in empty:
        html = (site / str(urls.cell_output_path(*combo))).read_text(encoding="utf-8")
        assert "No submissions yet" in html
        assert 'class="ranking"' not in html
        assert "<tbody></tbody>" not in html


def test_exactly_the_total_area_combos_carry_entries() -> None:
    populated = {c for c in reg.live_combos() if shards.load(*c)}
    assert {c[0] for c in populated} == {"total_area_prediction"}
    assert len(populated) == 20
    assert len(reg.live_combos()) - len(populated) == 212


def test_no_page_renders_a_python_repr_or_a_non_number(site: Path) -> None:
    """The failure this catches is a context key the template read but build.py
    never set, which Jinja2 renders as an empty string, and a None that reached
    a format string, which renders as 'None'."""
    for combo in reg.live_combos():
        html = (site / str(urls.cell_output_path(*combo))).read_text(encoding="utf-8")
        body = html.split('id="cell-payload"')[0]
        for poison in ("None", "NaN", "undefined", "Infinity", "object at 0x"):
            assert poison not in body, f"{combo}: {poison}"


def test_cell_css_declares_no_literal_colour() -> None:
    css = (ROOT / "static" / "css" / "cell.css").read_text(encoding="utf-8")
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css)
    assert "rgb(" not in css and "hsl(" not in css
```

`render_row` is a two-line helper in the test module that renders `templates/pages/cell.html` for a one-row page through the same Jinja2 environment `build.py` uses, so the test exercises the shipped template rather than a copy of it.

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_cells.py -v`
Expected: FAIL, `AssertionError` on `class="baseline"` - the skeleton template renders headings only.

- [ ] **Step 3: Write the template**

Replace the `{% for row in page.rows %}` block in `templates/pages/cell.html`:

```jinja
{% for row in page.rows %}
<section class="metric-row"
         id="{{ row.anchor }}"
         data-metric="{{ row.metric_id }}"
         data-state="{{ row.state }}"
         data-mode="{{ row.mode }}">
  <h2>{{ row.label }}{% if row.unit %} <span class="unit">({{ row.unit }})</span>{% endif %}</h2>

  <div class="baseline" data-baseline="{{ row.baseline_kind }}">
    <h3>Published baseline</h3>
    <p class="baseline-value">{{ row.baseline_display }}</p>
    {% if row.baseline_kind in ["greater_than", "less_than"] %}
    <p class="baseline-note">
      Table 8 reports this as a threshold, so the exact value does not exist.
      An entry on the other side of it is undecided, not a loss.
    </p>
    {% elif row.baseline_note %}
    <p class="baseline-note">{{ row.baseline_note }}</p>
    {% endif %}
  </div>

  {% if row.mode == "not_ranked" %}
  <p class="notice notice-saturated" role="note">{{ page.saturated_note }}</p>
  {% endif %}

  {% if row.entries %}
  <table class="ranking">
    <caption>
      {{ row.entries | length }} entries
      {% if row.undecidable %}, {{ row.undecidable }} undecided against the baseline{% endif %}
    </caption>
    <thead>
      <tr>
        {% if row.mode == "ranked" %}<th scope="col">Rank</th>{% endif %}
        <th scope="col">Model</th>
        <th scope="col">Source</th>
        <th scope="col">Value</th>
        <th scope="col">As published</th>
        {% if row.mode == "ranked" %}<th scope="col">vs baseline</th>{% endif %}
      </tr>
    </thead>
    <tbody>
      {% for entry in row.entries %}
      <tr data-model="{{ entry.model_id }}"
          data-source="{{ entry.source }}"
          data-verdict="{{ entry.verdict }}">
        {% if row.mode == "ranked" %}<td data-rank="{{ entry.rank }}">{{ entry.rank }}</td>{% endif %}
        <th scope="row">{{ entry.model_label }}</th>
        <td>{{ entry.source }}</td>
        <td class="value">{{ entry.display }}</td>
        <td class="value pooled">{{ entry.pooled_display }}</td>
        {% if row.mode == "ranked" %}
        <td class="verdict verdict-{{ entry.verdict }}">
          <span class="glyph" aria-hidden="true">{{ page.glyphs[entry.verdict] }}</span>
          {{ page.verdict_labels[entry.verdict] }}
        </td>
        {% endif %}
      </tr>
      {% endfor %}
      <tr class="filtered-empty" data-empty-when-filtered hidden>
        <td colspan="6">No entries match the current filters.</td>
      </tr>
    </tbody>
  </table>
  {% elif row.mode != "not_ranked" %}
  <p class="empty">No submissions yet for this metric.</p>
  {% endif %}
</section>
{% endfor %}

<footer class="provenance">
  <p>{{ page.provenance }}</p>
  <p>
    Entries are ranked on the macro-mean across the 18 circuits. The published
    figure is pooled across circuits and is shown beside it as "as published".
  </p>
</footer>
```

`page.glyphs` and `page.verdict_labels` are two constant dicts on `CellPage`, set in `cellpage.py`, so the template never maps a verdict to words itself:

```python
GLYPHS = {"better": "+", "equal": "=", "worse": "-", "undecidable": "?", "": ""}
VERDICT_LABELS = {
    "better": "beats baseline",
    "equal": "matches baseline",
    "worse": "baseline leads",
    "undecidable": "no comparison",
    "": "",
}
```

The glyph channel is not decoration. Four states have to be distinguishable without colour, and this is the same rule the matrix follows.

The empty-state copy deliberately links nowhere. `/submit/` does not exist until Phase 8, and a link to it would fail `lychee` and the internal-link test in this phase. Phase 8 adds the href.

- [ ] **Step 4: Write the stylesheet**

Create `static/css/cell.css`. Linked from `cell.html` only, so the matrix does not pay for rules it never uses:

```css
/* Cell page only.
 *
 * Every colour is a var() from the theme contract in static/css/themes/. A
 * literal here renders correctly in one theme and illegibly in the other, and
 * tests/test_cells.py asserts there are none.
 */

.cell-header .combo {
  display: flex;
  flex-wrap: wrap;
  gap: 1.5rem;
  margin: 0;
}

.cell-header .combo dt {
  color: var(--text-muted);
  font-size: 0.875rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.cell-header .combo dd {
  margin: 0;
  font-weight: 600;
}

.metric-row {
  margin-block: 2.5rem;
  border-top: 1px solid var(--border);
  padding-top: 1rem;
}

/* The baseline is pinned above the ranking structurally, and has to read that
   way too: it is the thing every row is measured against, not the first row. */
.baseline {
  background: var(--surface-raised);
  border-inline-start: 4px solid var(--accent);
  border-radius: 4px;
  padding: 0.75rem 1rem;
  margin-block: 1rem;
}

.baseline h3 {
  margin: 0;
  font-size: 0.8125rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
}

.baseline-value {
  margin: 0.25rem 0 0;
  font-size: 1.5rem;
  font-variant-numeric: tabular-nums;
}

.baseline-note {
  margin: 0.5rem 0 0;
  color: var(--text-muted);
  font-size: 0.875rem;
}

.baseline[data-baseline="absent"] .baseline-value {
  font-style: italic;
  color: var(--text-muted);
}

.notice {
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 0.75rem 1rem;
  background: var(--surface-raised);
}

.notice-saturated {
  border-inline-start: 4px solid var(--state-saturated);
}

table.ranking {
  width: 100%;
  border-collapse: collapse;
  margin-top: 1rem;
}

table.ranking caption {
  text-align: start;
  color: var(--text-muted);
  font-size: 0.875rem;
  padding-block-end: 0.5rem;
}

table.ranking th,
table.ranking td {
  border-bottom: 1px solid var(--border);
  padding: 0.5rem 0.75rem;
  text-align: start;
}

table.ranking .value {
  font-variant-numeric: tabular-nums;
  text-align: end;
}

.pooled {
  color: var(--text-muted);
}

.verdict .glyph {
  font-weight: 700;
  margin-inline-end: 0.25rem;
}

.verdict-better { color: var(--state-beats); }
.verdict-equal { color: var(--state-matches); }
.verdict-worse { color: var(--state-leads); }
.verdict-undecidable { color: var(--text-muted); }

.empty {
  color: var(--text-muted);
  font-style: italic;
}

@media (max-width: 40rem) {
  table.ranking { display: block; overflow-x: auto; }
}
```

If Phase 3 named a token differently, rename it here. This file is the only place these names appear outside the theme files.

- [ ] **Step 5: Link the stylesheet**

In `templates/pages/cell.html`:

```jinja
{% block head %}
<link rel="stylesheet" href="{{ base_path }}css/cell.css">
{% endblock %}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_cells.py -v`
Expected: all pass. The `seen == 32` assertion is the one to read carefully: it proves the sentinel branch fires on the exact 32 cells, not on a superset.

- [ ] **Step 7: Look at it**

Run: `make serve` and open, at minimum:

- `/cell/total_area_prediction/ng45/floorplan/` - populated, three metric rows
- `/cell/total_area_prediction/ng45/global_route/` - fully saturated
- `/cell/worst_slack_prediction/asap7/global_route/` - mixed: saturated MAE, degenerate MPE and MNE
- `/cell/cell_arc_delay_prediction/sky130/cts/` - a `< -1` sentinel
- `/cell/i2c` is not a page; try `/cell/jpeg` too and confirm the 404 rather than a blank render

Confirm the three notices do not read as the same thing.

- [ ] **Step 8: Commit**

```bash
git add templates/pages/cell.html static/css/cell.css build.py tests/test_cells.py
git commit -m "feat(cells): render the baseline above the ranking with distinct notices"
```

### Task 4: CSV and JSON export, written by the build

Each page ships its own data as two real files beside it, generated by `build.py` from the same objects the HTML was rendered from. Nothing is serialised in the browser, so nothing can drift from what the page shows.

**A correction to the File structure table above.** That table lists `static/js/cell-export.js`, "CSV and JSON download from the inlined payload". This task does not create it. A browser-side serialiser is a second implementation of the export format, in a second language, with no test runner in this repo to check it against the first. Writing both files at build time makes them byte-checkable in pytest and turns the download button into an `<a download>` with no JavaScript at all. The payload stays inlined, because Task 6's filter reads it, but it is no longer the source of a download.

**Files:**
- Modify: `tools/urls.py`, `tools/cellpage.py`, `build.py`, `templates/pages/cell.html`
- Test: `tests/test_cells.py`

**Interfaces:**
- Consumes: `cellpage.CellPage`, `cellpage.payload`, `urls.cell_url`.
- Produces: `urls.EXPORT_NAMES: dict[str, str]`, `urls.cell_export_url(task_id: str, pdk_id: str, stage_id: str, fmt: str) -> str`, `urls.cell_export_path(task_id: str, pdk_id: str, stage_id: str, fmt: str) -> PurePosixPath`, `cellpage.CSV_COLUMNS: tuple[str, ...]`, `cellpage.csv_text(cell_page: CellPage) -> str`, and `CellPage.json_url` / `CellPage.csv_url`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cells.py`:

```python
import csv
import io


def _inlined_payload(html: str) -> str:
    """The exact text inside the payload script element, unmodified."""
    start = html.index('id="cell-payload"')
    start = html.index(">", start) + 1
    return html[start : html.index("</script>", start)]


def test_every_page_ships_both_exports(site: Path) -> None:
    for combo in reg.live_combos():
        for fmt in ("json", "csv"):
            assert (site / str(urls.cell_export_path(*combo, fmt))).is_file(), combo


def test_cell_export_url_refuses_a_format_it_does_not_write() -> None:
    with pytest.raises(KeyError):
        urls.cell_export_url("total_area_prediction", "ng45", "cts", "xlsx")


def test_the_inlined_payload_and_the_json_file_are_byte_identical(site: Path) -> None:
    """The anti-drift assertion. One serialiser, two destinations, same bytes.

    If this ever fails, something between build.py and the template transformed
    the payload - Jinja2 autoescaping is the likely culprit - and the download
    and the page are no longer describing the same numbers.
    """
    for combo in reg.live_combos():
        html = (site / str(urls.cell_output_path(*combo))).read_text(encoding="utf-8")
        stored = (site / str(urls.cell_export_path(*combo, "json"))).read_text(
            encoding="utf-8"
        )
        assert _inlined_payload(html) == stored, combo


def test_the_json_export_parses_and_carries_no_nan(site: Path) -> None:
    for combo in reg.live_combos():
        text = (site / str(urls.cell_export_path(*combo, "json"))).read_text(
            encoding="utf-8"
        )
        for poison in ("NaN", "Infinity", "-Infinity"):
            assert poison not in text, combo
        data = json.loads(text)
        assert (
            data["combo"]["task"],
            data["combo"]["pdk"],
            data["combo"]["stage"],
        ) == combo


def _read_csv(site: Path, combo: tuple[str, str, str]) -> list[dict[str, str]]:
    text = (site / str(urls.cell_export_path(*combo, "csv"))).read_text(
        encoding="utf-8"
    )
    return list(csv.DictReader(io.StringIO(text)))


def test_the_csv_carries_one_baseline_row_per_metric_plus_every_entry(
    site: Path,
) -> None:
    for page in _pages():
        combo = (page.task_id, page.pdk_id, page.stage_id)
        rows = _read_csv(site, combo)
        baselines = [r for r in rows if r["record"] == "baseline"]
        entries = [r for r in rows if r["record"] == "entry"]
        assert len(baselines) == len(page.rows)
        assert len(entries) == page.entry_count
        assert {r["metric"] for r in baselines} == {r.metric_id for r in page.rows}


def test_the_csv_stores_a_fraction_and_displays_a_percent(site: Path) -> None:
    """The x100 trap, checked through the artifact a reader opens in a spreadsheet.

    Reformatting the stored column has to reproduce the display column exactly.
    That pins one scaling and one precision source for every exported number.
    """
    checked = 0
    for page in _pages():
        combo = (page.task_id, page.pdk_id, page.stage_id)
        for r in _read_csv(site, combo):
            if r["bound"] != "exact" or not r["value_stored"]:
                continue
            assert (
                cellpage.format_value(
                    page.task_id, r["metric"], float(r["value_stored"])
                )
                == r["value_display"]
            )
            checked += 1
    assert checked > 0


def test_the_csv_declares_which_unit_each_column_is_in(site: Path) -> None:
    """value_stored in a column labelled '%' is how the x100 gets back in."""
    for page in _pages():
        combo = (page.task_id, page.pdk_id, page.stage_id)
        for r in _read_csv(site, combo):
            percent = reg.metric(r["metric"]).percent
            assert r["stored_unit"] == ("fraction" if percent else r["display_unit"])
            if percent:
                assert r["display_unit"] == "%"


def test_the_csv_never_prints_a_number_for_a_degenerate_baseline(site: Path) -> None:
    seen = 0
    for page in _pages():
        combo = (page.task_id, page.pdk_id, page.stage_id)
        for r in _read_csv(site, combo):
            if r["record"] != "baseline" or r["bound"] != "absent":
                continue
            seen += 1
            assert r["value_stored"] == ""
            assert r["value_display"] == cellpage.NO_BASELINE
    assert seen == 24


def test_the_csv_keeps_a_thousands_separator_inside_one_field(site: Path) -> None:
    """1,781.97 is one value, not two columns. The csv module quotes it; a
    hand-rolled ','.join would silently shift every column after it."""
    rows = _read_csv(site, ("total_area_prediction", "ng45", "floorplan"))
    mae = next(r for r in rows if r["metric"] == "mae" and r["record"] == "baseline")
    assert "," in mae["value_display"]
    assert mae["value_stored"] == "1781.9696"


def test_no_javascript_serialises_an_export() -> None:
    """The export format has one implementation, in Python, and it is tested."""
    for path in sorted((ROOT / "static" / "js").glob("*.js")):
        source = path.read_text(encoding="utf-8")
        for forbidden in ("new Blob", "URL.createObjectURL", "text/csv"):
            assert forbidden not in source, f"{path.name} builds a download"
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_cells.py -v -k export or csv or payload`
Expected: FAIL, `AttributeError: module 'tools.urls' has no attribute 'cell_export_path'`

- [ ] **Step 3: Add the export routes**

Append to `tools/urls.py`:

```python
# The two export formats, and the filenames build.py writes them to. The dict is
# the vocabulary: an unknown format raises here rather than producing a link to
# a file nothing generates.
EXPORT_NAMES: dict[str, str] = {"json": "cell.json", "csv": "cell.csv"}


def cell_export_url(task_id: str, pdk_id: str, stage_id: str, fmt: str) -> str:
    """Site-absolute URL of one page's export. Siblings of its index.html."""
    return cell_url(task_id, pdk_id, stage_id) + EXPORT_NAMES[fmt]


def cell_export_path(
    task_id: str, pdk_id: str, stage_id: str, fmt: str
) -> PurePosixPath:
    """Path under dist/, derived FROM the URL for the same reason as the page."""
    return PurePosixPath(
        cell_export_url(task_id, pdk_id, stage_id, fmt).removeprefix(BASE_PATH)
    )
```

- [ ] **Step 4: Write the CSV serialiser**

Append to `tools/cellpage.py`, and add `csv`, `io` and `Iterator` to the imports:

```python
# One row per participant per metric: the published baseline first, then every
# entry. The baseline is a row rather than a column so a spreadsheet can sort on
# value_stored without leaving it behind.
CSV_COLUMNS: tuple[str, ...] = (
    "task",
    "pdk",
    "stage",
    "metric",
    "direction",
    "state",
    "mode",
    "record",
    "model",
    "source",
    "rank",
    "verdict",
    "bound",
    "value_stored",
    "stored_unit",
    "value_display",
    "display_unit",
)


def _stored(value: float | None) -> str:
    """A float as text, round-tripping and with no thousands separator.

    repr() gives the shortest string that reads back as the same float. The
    display column is the one with the commas in it, and mixing the two is how a
    spreadsheet ends up holding 1.78 instead of 1781.9696.
    """
    return "" if value is None else repr(value)


def _csv_rows(cell_page: CellPage) -> Iterator[dict[str, str]]:
    for row in cell_page.rows:
        percent = reg.metric(row.metric_id).percent
        common = {
            "task": cell_page.task_id,
            "pdk": cell_page.pdk_id,
            "stage": cell_page.stage_id,
            "metric": row.metric_id,
            "direction": row.direction,
            "state": row.state,
            "mode": row.mode,
            # Two unit columns, because the two value columns are in different
            # units. A single "unit: %" beside a fraction is the x100 bug
            # rewritten as a spreadsheet.
            "stored_unit": "fraction" if percent else row.unit,
            "display_unit": row.unit,
        }
        yield {
            **common,
            "record": "baseline",
            "model": "",
            "source": "paper",
            "rank": "",
            "verdict": "",
            "bound": row.baseline_kind,
            "value_stored": _stored(row.baseline_value),
            "value_display": row.baseline_display,
        }
        for entry in row.entries:
            yield {
                **common,
                "record": "entry",
                "model": entry.model_id,
                "source": entry.source,
                "rank": "" if entry.rank is None else str(entry.rank),
                "verdict": entry.verdict,
                "bound": BoundKind.EXACT.value,
                "value_stored": _stored(entry.value),
                "value_display": entry.display,
            }


def csv_text(cell_page: CellPage) -> str:
    """The page's rows as CSV. Same objects the HTML was rendered from."""
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(_csv_rows(cell_page))
    return buffer.getvalue()
```

Add `json_url: str` and `csv_url: str` to `CellPage`, set in `page()`:

```python
json_url = (urls.cell_export_url(task_id, pdk_id, stage_id, "json"),)
csv_url = (urls.cell_export_url(task_id, pdk_id, stage_id, "csv"),)
```

- [ ] **Step 5: Write the files from build.py**

`_render_cell_pages` gains three lines. The payload string is computed once and used twice, which is what makes the byte-identity test true by construction rather than by coincidence:

```python
def _render_cell_pages(env: Environment, out: Path) -> int:
    template = env.get_template("pages/cell.html")
    written = 0
    for task_id, pdk_id, stage_id in reg.live_combos():
        page = cellpage.page(task_id, pdk_id, stage_id)
        payload = cellpage.payload(page)
        target = out / str(urls.cell_output_path(task_id, pdk_id, stage_id))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            template.render(page=page, payload=payload, base_path=urls.BASE_PATH),
            encoding="utf-8",
        )
        for fmt, text in (("json", payload), ("csv", cellpage.csv_text(page))):
            out.joinpath(
                str(urls.cell_export_path(task_id, pdk_id, stage_id, fmt))
            ).write_text(text, encoding="utf-8")
        written += 1
    return written
```

- [ ] **Step 6: Add the download links and the payload element**

At the end of `{% block content %}` in `templates/pages/cell.html`, after the provenance footer:

```jinja
<section class="exports" aria-labelledby="exports-heading">
  <h2 id="exports-heading">Download this page's data</h2>
  <ul>
    <li><a href="{{ page.csv_url }}" download>CSV</a> - one row per baseline and per entry</li>
    <li><a href="{{ page.json_url }}" download>JSON</a> - the same data, nested by metric</li>
  </ul>
  <p class="exports-note">
    Every value appears twice. <code>value_stored</code> is the number the
    ranking used, and percent metrics are fractions there. <code>value_display</code>
    is the string on this page, already scaled and rounded.
  </p>
</section>

<script type="application/json" id="cell-payload">{{ payload | safe }}</script>
```

`| safe` is not a shortcut around escaping, it is the reason `cellpage.payload` escapes `<`, `>` and `&` itself. Autoescaping here would turn every `"` into `&quot;`, which `JSON.parse` rejects and which would break the byte-identity test on the first page. The payload element sits last so `test_no_page_renders_a_python_repr_or_a_non_number`, which splits the document at `id="cell-payload"`, still sees the whole body.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run pytest tests/test_cells.py -v`
Expected: all pass. `test_the_csv_stores_a_fraction_and_displays_a_percent` is the one to read: it checks several thousand exported numbers against the single display boundary.

- [ ] **Step 8: Open one export by hand**

```bash
uv run python build.py
head -4 dist/cell/total_area_prediction/ng45/floorplan/cell.csv
python -c "import json,pathlib;print(json.loads(pathlib.Path('dist/cell/worst_slack_prediction/asap7/global_route/cell.json').read_text())['rows'][1])"
```

Expected: the MAE baseline row reads `1781.9696` stored and `1,781.97` displayed, and the degenerate MPE row shows `"baseline_kind": "absent"` with a null value.

- [ ] **Step 9: Commit**

```bash
git add tools/urls.py tools/cellpage.py build.py templates/pages/cell.html tests/test_cells.py
git commit -m "feat(cells): write per-page CSV and JSON exports at build time"
```

---

### Task 5: The predicted-versus-actual panel, which has to degrade

The lab's results tree carries two figures per combo, `pred_vs_actual_grid.png` and `baseline_pred_vs_actual_grid.png`. They are the most informative thing on the page and none of them can be committed: each is over the 1 MB per-file cap that `size-guard.yml` enforces, and 20 combos means 40 of them. They ship as a GitHub Release and the page references them by URL, so `dist/` pays nothing.

Today the manifest does not exist, so **every one of the 232 pages takes the degraded branch**. That is the branch this task is really about. It is a conditional in the template and a `None` return, not a second template and not a rewrite later.

Task 2 already imports `Plot` and `plot_for` from `tools/plots.py` and stubs the module the way Task 1 stubbed `cellpage`. This task gives it a body; the signature does not change.

**Files:**
- Create: `tools/plots.py`
- Modify: `tools/cellpage.py`, `templates/pages/cell.html`, `static/css/cell.css`, `.gitignore`
- Test: `tests/test_cells.py`

**Interfaces:**
- Consumes: `reg.task/pdk/stage`, `reg.live_combos()`.
- Produces: `plots.Plot`, `plots.MANIFEST_PATH: Path`, `plots.manifest() -> Manifest`, `plots.plot_for(task_id: str, pdk_id: str, stage_id: str) -> Plot | None`, `plots.asset_name(task_id: str, pdk_id: str, stage_id: str, filename: str) -> str`, `plots.png_size(path: Path) -> tuple[int, int]`, `plots.collect(source: Path, out: Path, tag: str, repo: str) -> Path`, and `CellPage.plot_state` / `CellPage.plot_note`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cells.py`:

```python
from tools import plots


def test_no_manifest_means_no_figure_and_a_stated_reason(site: Path) -> None:
    """The state the site ships in today. 232 pages, zero broken figures."""
    assert not plots.MANIFEST_PATH.exists(), (
        "once the manifest lands, this test asserts the other branch"
    )
    for combo in reg.live_combos():
        html = (site / str(urls.cell_output_path(*combo))).read_text(encoding="utf-8")
        panel = html.split('class="plots"', 1)[1].split("</section>", 1)[0]
        assert 'data-plot="absent"' in panel
        assert "<img" not in panel
        assert "not published" in panel


def test_a_listed_combo_renders_two_figures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other branch, driven by a manifest rather than by a code path that
    only exists in a comment."""
    manifest = {
        "release_tag": "plots-v1",
        "release_url": "https://github.com/drexel-ice/eda-schema-leaderboard/releases/download/plots-v1/",
        "assets": [
            {
                "task": "total_area_prediction",
                "pdk": "ng45",
                "stage": "cts",
                "model": "total_area_prediction__ng45__cts__pred_vs_actual_grid.png",
                "baseline": "total_area_prediction__ng45__cts__baseline_pred_vs_actual_grid.png",
                "width": 1800,
                "height": 1200,
                "model_bytes": 1483920,
                "baseline_bytes": 1502301,
            }
        ],
    }
    path = tmp_path / "plots.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(plots, "MANIFEST_PATH", path)
    plots.manifest.cache_clear()
    plots._index.cache_clear()

    plot = plots.plot_for("total_area_prediction", "ng45", "cts")
    assert plot is not None
    assert plot.model_url.startswith("https://github.com/")
    assert plot.width == 1800 and plot.height == 1200
    assert plots.plot_for("total_area_prediction", "ng45", "floorplan") is None

    html = render_page(cellpage.page("total_area_prediction", "ng45", "cts"))
    assert html.count("<img") == 2
    assert 'data-plot="release"' in html
    assert 'loading="lazy"' in html
    assert plot.alt_model in html

    plots.manifest.cache_clear()
    plots._index.cache_clear()


def test_asset_names_survive_a_flat_release_namespace() -> None:
    """A Release has no directories. The source tree has 20 files called
    pred_vs_actual_grid.png, and uploading them unrenamed leaves one."""
    names = {
        plots.asset_name(task, pdk, stage, filename)
        for task, pdk, stage in reg.live_combos()
        for filename in (plots.MODEL_PLOT, plots.BASELINE_PLOT)
    }
    assert len(names) == len(reg.live_combos()) * 2


def test_a_manifest_cannot_name_a_combo_that_has_no_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """total_wirelength at floorplan is void. A figure for it would link nowhere."""
    path = tmp_path / "plots.json"
    path.write_text(
        json.dumps(
            {
                "release_tag": "t",
                "release_url": "https://example.invalid/",
                "assets": [
                    {
                        "task": "total_wirelength_prediction",
                        "pdk": "ng45",
                        "stage": "floorplan",
                        "model": "a.png",
                        "baseline": "b.png",
                        "width": 1,
                        "height": 1,
                        "model_bytes": 1,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(plots, "MANIFEST_PATH", path)
    plots.manifest.cache_clear()
    plots._index.cache_clear()
    with pytest.raises(KeyError):
        plots.plot_for("total_wirelength_prediction", "ng45", "floorplan")
    plots.manifest.cache_clear()
    plots._index.cache_clear()


def test_png_size_reads_the_header_without_a_dependency(tmp_path: Path) -> None:
    png = tmp_path / "t.png"
    png.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + (13).to_bytes(4, "big")
        + b"IHDR"
        + (1800).to_bytes(4, "big")
        + (1200).to_bytes(4, "big")
    )
    assert plots.png_size(png) == (1800, 1200)
    bad = tmp_path / "b.png"
    bad.write_bytes(b"not a png at all, twenty four bytes long.")
    with pytest.raises(ValueError):
        plots.png_size(bad)


def test_no_plot_asset_is_committed() -> None:
    """The reason these live in a Release. size-guard.yml caps a tracked file at
    1 MB and every one of these is bigger."""
    tracked = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True
    ).stdout.split(b"\0")
    assert not [f for f in tracked if f.endswith(b"pred_vs_actual_grid.png")]


def test_the_collector_writes_where_git_will_not_see_it() -> None:
    assert "build/" in (ROOT / ".gitignore").read_text(encoding="utf-8").split()
```

`render_page` is the sibling of Task 3's `render_row`: it renders `templates/pages/cell.html` for one `CellPage` through the same Jinja2 environment `build.py` uses.

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_cells.py -v -k plot or asset or png`
Expected: FAIL, `AttributeError: module 'tools.plots' has no attribute 'MANIFEST_PATH'` - Task 2's stub returns `None` and knows nothing else.

- [ ] **Step 3: Write the module**

Replace `tools/plots.py`:

```python
"""Where the predicted-versus-actual figures live, and how the page finds them.

The lab renders two PNGs per combo. Each is over the 1 MB per-file cap in
size-guard.yml, so they are never committed: `collect` gathers them into a flat
directory, `gh release upload` publishes them, and this module turns the manifest
that records the upload into a URL the page can reference. dist/ carries the
markup only.

Until that Release exists, plot_for returns None for every combo and the page
says why. That is the shipping state of this phase, not a placeholder: raw
per-circuit predictions are not published for 212 of the 232 combos at all.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import struct
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from tools import registry as reg

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH: Path = ROOT / "data" / "plots.json"

MODEL_PLOT = "pred_vs_actual_grid.png"
BASELINE_PLOT = "baseline_pred_vs_actual_grid.png"

EMPTY: dict[str, Any] = {"release_tag": "", "release_url": "", "assets": []}


@dataclass(frozen=True, slots=True)
class Plot:
    model_url: str
    baseline_url: str
    release_tag: str
    width: int
    height: int
    alt_model: str
    alt_baseline: str


def asset_name(task_id: str, pdk_id: str, stage_id: str, filename: str) -> str:
    """One combo's figure, named for a flat namespace.

    A GitHub Release has no directories. Twenty files called
    pred_vs_actual_grid.png uploaded to one Release leave one file, and the
    nineteen that vanished are the nineteen nobody notices.
    """
    return f"{task_id}__{pdk_id}__{stage_id}__{filename}"


def png_size(path: Path) -> tuple[int, int]:
    """Width and height from the IHDR chunk. No image library needed.

    The page sets width and height on the img so the figure reserves its space
    before it loads. Without them a 1800x1200 image shoves the ranking table
    down the screen mid-read.
    """
    header = path.read_bytes()[:24]
    if header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path} is not a PNG")
    width, height = struct.unpack(">II", header[16:24])
    return int(width), int(height)


@lru_cache(maxsize=1)
def manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.is_file():
        return EMPTY
    data: dict[str, Any] = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return data


@lru_cache(maxsize=1)
def _index() -> dict[tuple[str, str, str], dict[str, Any]]:
    return {(a["task"], a["pdk"], a["stage"]): a for a in manifest()["assets"]}


def plot_for(task_id: str, pdk_id: str, stage_id: str) -> Plot | None:
    asset = _index().get((task_id, pdk_id, stage_id))
    if asset is None:
        return None
    if reg.is_void(task_id, stage_id):
        raise KeyError(f"manifest lists a void combo: {task_id} {pdk_id} {stage_id}")

    task, pdk, stage = reg.task(task_id), reg.pdk(pdk_id), reg.stage(stage_id)
    where = f"{task.label} on {pdk.label}, predicting from {stage.label}"
    base = manifest()["release_url"].rstrip("/") + "/"
    return Plot(
        model_url=base + asset["model"],
        baseline_url=base + asset["baseline"],
        release_tag=manifest()["release_tag"],
        width=int(asset["width"]),
        height=int(asset["height"]),
        alt_model=(
            f"Scatter grid of predicted against actual {where}, one panel per "
            f"circuit. Points on the diagonal are exact predictions."
        ),
        alt_baseline=(
            f"The same grid for the published tool estimate, {where}. Shown "
            f"beside the model so the two are read at one scale."
        ),
    )


def collect(source: Path, out: Path, tag: str, repo: str) -> Path:
    """Gather every figure under `source` into `out` and write the manifest.

    Prints the gh commands rather than running them. A build tool that uploads
    to a Release on import is a build tool that can be surprised into it.
    """
    out.mkdir(parents=True, exist_ok=True)
    assets: list[dict[str, Any]] = []
    for task_id, pdk_id, stage_id in reg.live_combos():
        folder = source / task_id / f"{pdk_id}_{stage_id}"
        record: dict[str, Any] = {"task": task_id, "pdk": pdk_id, "stage": stage_id}
        for key, filename in (("model", MODEL_PLOT), ("baseline", BASELINE_PLOT)):
            origin = folder / filename
            if not origin.is_file():
                break
            name = asset_name(task_id, pdk_id, stage_id, filename)
            shutil.copyfile(origin, out / name)
            record[key] = name
            # Per asset, not per combo. One shared "bytes" key would silently
            # record the second file's size against both, and the checksum that
            # is supposed to prove which file was uploaded would prove nothing.
            record[f"{key}_bytes"] = origin.stat().st_size
            record[f"{key}_sha256"] = hashlib.sha256(origin.read_bytes()).hexdigest()
            if key == "model":
                record["width"], record["height"] = png_size(origin)
        else:
            assets.append(record)

    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(
            {
                "release_tag": tag,
                "release_url": f"https://github.com/{repo}/releases/download/{tag}/",
                "assets": assets,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"collected {len(assets)} combos into {out}")
    print(
        f"  gh release create {tag} --repo {repo} --notes 'predicted vs actual figures'"
    )
    print(f"  gh release upload {tag} --repo {repo} {out}/*.png")
    return MANIFEST_PATH
```

Give it a `if __name__ == "__main__":` block parsing `--source`, `--out` (default `build/plots`), `--tag` and `--repo` with `argparse`, and add `build/` to `.gitignore`. The default output is outside the tracked tree on purpose: 40 files at over 1 MB each inside it would trip `size-guard.yml` on the next PR, and by then they are in someone's commit.

- [ ] **Step 4: Add the two fields to the context**

In `tools/cellpage.py`:

```python
PLOT_NOTE = (
    "Per-circuit predictions are not published for this combination yet, so "
    "there is no predicted-versus-actual figure. The baseline above is "
    "measured independently of it and is unaffected."
)
```

`CellPage` gains `plot_state: str`, and `page()` sets `plot_state="release" if plot is not None else "absent"` alongside `plot_note=PLOT_NOTE`. The template asks for a string, never for `plot is None`, so the panel can grow a third source later without the template learning about it.

- [ ] **Step 5: Add the panel to the template**

Between the metric rows and the provenance footer in `templates/pages/cell.html`:

```jinja
<section class="plots" data-plot="{{ page.plot_state }}" aria-labelledby="plots-heading">
  <h2 id="plots-heading">Predicted versus actual</h2>
  {% if page.plot %}
  <div class="plot-pair">
    <figure>
      <img src="{{ page.plot.model_url }}" alt="{{ page.plot.alt_model }}"
           width="{{ page.plot.width }}" height="{{ page.plot.height }}"
           loading="lazy" decoding="async">
      <figcaption>Model predictions across the 18 circuits.</figcaption>
    </figure>
    <figure>
      <img src="{{ page.plot.baseline_url }}" alt="{{ page.plot.alt_baseline }}"
           width="{{ page.plot.width }}" height="{{ page.plot.height }}"
           loading="lazy" decoding="async">
      <figcaption>The published tool estimate, at the same scale.</figcaption>
    </figure>
  </div>
  <p class="plot-source">
    Full-size figures are published in release
    <a href="{{ page.plot.model_url }}">{{ page.plot.release_tag }}</a>.
  </p>
  {% else %}
  <p class="empty">{{ page.plot_note }}</p>
  {% endif %}
</section>
```

Both figures carry real alt text. A scatter grid is the argument the page is making, not decoration, so `alt=""` would be wrong; the alt strings are built in `plots.py` from the registry labels so they cannot describe a different combo than the one they sit on.

Add to `static/css/cell.css`:

```css
.plot-pair {
  display: grid;
  gap: 1rem;
  grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
}

.plot-pair figure {
  margin: 0;
}

.plot-pair img {
  max-width: 100%;
  height: auto;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--surface-raised);
}

.plot-pair figcaption {
  color: var(--text-muted);
  font-size: 0.875rem;
  padding-block-start: 0.25rem;
}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_cells.py -v`
Expected: all pass, with `test_no_manifest_means_no_figure_and_a_stated_reason` covering all 232 pages and `test_a_listed_combo_renders_two_figures` covering the branch none of them take yet.

- [ ] **Step 7: Rehearse the collection without uploading**

```bash
uv run python -m tools.plots --source ../eda-schema-experiments --tag plots-v1 --repo JiwaniZakir/eda-schema-leaderboard
git status --short          # data/plots.json only, nothing under build/
du -sh build/plots
```

Expected: 20 combos collected, `build/plots` well over 40 MB, and `git status` showing nothing from it. Then **do not commit `data/plots.json`** in this phase: the Release does not exist, so a manifest pointing at it would render 40 broken images. Delete it and let Phase 9 land the manifest with the upload.

- [ ] **Step 8: Commit**

```bash
git add tools/plots.py tools/cellpage.py templates/pages/cell.html static/css/cell.css .gitignore tests/test_cells.py
git commit -m "feat(cells): reference released figures and degrade when none exist"
```

---

### Task 6: Filtering the ranking table, in the browser, without trusting the browser

One vanilla file, `static/js/cell-filters.js`. It hides table rows and does nothing else: no sorting, no formatting, no arithmetic. Every number on the page was computed by `build.py` and this file must not be able to change one.

Two things make it honest rather than decorative. It **builds its own controls**, so a reader without JavaScript sees a complete page instead of widgets that do nothing. And it **cross-checks itself against build-time counts** carried in the payload before it filters anything, so a template change that renames a data attribute produces a visible banner rather than a filter that silently drops rows. That is the Phase 8 explore pattern applied one page down, and it is how this repo verifies JavaScript without a Node test runner.

Be honest about the current value: at most one entry exists per cell today, so the controls appear nowhere on the real site. What this task actually buys is the DOM contract, the empty-filtered state, and a `colspan` bug that reading the Task 3 template turns up.

**Files:**
- Create: `static/js/cell-filters.js`
- Modify: `tools/cellpage.py`, `templates/pages/cell.html`, `static/css/cell.css`, `build.py`
- Test: `tests/test_cells.py`

**Interfaces:**
- Consumes: `cellpage.MetricRow`, the payload from Task 4.
- Produces: `cellpage.filter_counts(row: MetricRow) -> dict[str, dict[str, int]]`, `MetricRow.columns: int`, a `counts` key on every payload row, and the DOM contract `tbody tr[data-model][data-source][data-verdict]`, `[data-visible-count]`, `[data-empty-when-filtered]`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cells.py`. The module accumulates stdlib imports across these tasks: `csv`, `io`, `json`, `re` and `subprocess` are all in use by now.

```python
JS = ROOT / "static" / "js" / "cell-filters.js"


def test_the_payload_counts_match_the_rows_it_ships_with() -> None:
    for page in _pages():
        data = json.loads(cellpage.payload(page))
        for row, sent in zip(page.rows, data["rows"], strict=True):
            for axis in ("source", "verdict"):
                assert sum(sent["counts"][axis].values()) == len(row.entries), (
                    row.metric_id
                )


def test_the_build_time_counts_match_the_rendered_rows(site: Path) -> None:
    """The cross-check the browser performs, performed here too. If these two
    ever disagree the banner fires in production, so it must be impossible."""
    for page in _pages():
        html = (
            site / str(urls.cell_output_path(page.task_id, page.pdk_id, page.stage_id))
        ).read_text(encoding="utf-8")
        for section, row in zip(_sections(html), page.rows, strict=True):
            for source, n in cellpage.filter_counts(row)["source"].items():
                assert section.count(f'data-source="{source}"') == n


def test_the_filtered_empty_row_spans_the_whole_table(site: Path) -> None:
    """A no_comparison table has four columns and a ranked one has six. One
    hardcoded colspan renders a stray cell on 24 degenerate rows."""
    for combo in reg.live_combos():
        html = (site / str(urls.cell_output_path(*combo))).read_text(encoding="utf-8")
        for section in _sections(html):
            if 'class="ranking"' not in section:
                continue
            headers = section.count('<th scope="col">')
            spans = {int(n) for n in re.findall(r'colspan="(\d+)"', section)}
            assert spans == {headers}, section[:200]


def test_every_ranking_table_carries_the_filter_contract(site: Path) -> None:
    for combo in reg.live_combos():
        html = (site / str(urls.cell_output_path(*combo))).read_text(encoding="utf-8")
        for section in _sections(html):
            if 'class="ranking"' not in section:
                continue
            assert "data-visible-count" in section
            assert "data-empty-when-filtered" in section
            assert 'aria-live="polite"' in section


def test_a_multi_entry_row_renders_one_tr_per_entry() -> None:
    """Filtering needs something to filter, and the real data has one model per
    cell. This is the shape the controls are written against."""
    records = tuple(
        shards.Record(
            metric="mae",
            model_id=f"m{i}",
            model_label=f"Model {i}",
            source="submission",
            value_macro=1000.0 + i,
            value_pooled=None,
            ranked_on="macro",
        )
        for i in range(3)
    )
    html = render_row(
        cellpage.metric_row(
            "total_area_prediction", "mae", "ng45", "cts", records=records
        )
    )
    assert html.count("<tr data-model=") == 3
    assert 'data-verdict="better"' in html or 'data-verdict="worse"' in html


def test_the_filter_script_is_loaded_locally_and_deferred(site: Path) -> None:
    html = (
        site / str(urls.cell_output_path("total_area_prediction", "ng45", "cts"))
    ).read_text(encoding="utf-8")
    tag = next(t for t in re.findall(r"<script[^>]*>", html) if "cell-filters.js" in t)
    assert "defer" in tag
    assert f'src="{urls.BASE_PATH}js/cell-filters.js"' in tag


def test_the_filter_script_computes_nothing() -> None:
    """Every number on the page came from build.py. The x100 for percent metrics
    happens in cellpage.format_value and this file must not be able to add one."""
    source = JS.read_text(encoding="utf-8")
    for forbidden in ("* 100", "toFixed", "parseFloat", "innerHTML", "sort("):
        assert forbidden not in source, f"cell-filters.js uses {forbidden}"


def test_the_filter_script_only_reads_attributes_the_page_renders(site: Path) -> None:
    source = JS.read_text(encoding="utf-8")
    used = set(re.findall(r"dataset\.(\w+)", source))
    html = (
        site / str(urls.cell_output_path("total_area_prediction", "ng45", "cts"))
    ).read_text(encoding="utf-8")
    for name in used:
        attribute = re.sub(r"([A-Z])", r"-\1", name).lower()
        assert f"data-{attribute}=" in html, (
            f"cell-filters.js reads a dead data-{attribute}"
        )
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_cells.py -v -k filter or colspan or span`
Expected: FAIL, `KeyError: 'counts'` on the payload test and `AssertionError: {6} != {4}` on the colspan test, which is the real bug this task found in the Task 3 template.

- [ ] **Step 3: Add the counts and the column count**

In `tools/cellpage.py`, add `columns: int` to `MetricRow` and set it from the mode, so the template asks for a number instead of deciding one:

```python
RANKED_COLUMNS = ("rank", "model", "source", "value", "pooled", "verdict")
UNRANKED_COLUMNS = ("model", "source", "value", "pooled")


def filter_counts(row: MetricRow) -> dict[str, dict[str, int]]:
    """What the browser must see once it has counted the rendered rows.

    Computed from the same objects the template renders, so a disagreement in
    the browser means the markup contract broke, not that the data moved.
    """
    return {
        "source": dict(Counter(e.source for e in row.entries)),
        "verdict": dict(Counter(e.verdict for e in row.entries)),
    }
```

`metric_row` sets `columns=len(RANKED_COLUMNS) if mode == "ranked" else len(UNRANKED_COLUMNS)`, and `payload` gains `"counts": filter_counts(row)` on each row dict. Import `Counter` from `collections`.

- [ ] **Step 4: Fix the caption and the empty row**

In `templates/pages/cell.html`, the ranking table's caption and its filtered-empty row:

```jinja
    <caption aria-live="polite">
      <span data-visible-count>{{ row.entries | length }}</span> of
      {{ row.entries | length }} entries shown
      {% if row.undecidable %}, {{ row.undecidable }} undecided against the baseline{% endif %}
    </caption>
```

```jinja
      <tr class="filtered-empty" data-empty-when-filtered hidden>
        <td colspan="{{ row.columns }}">No entries match the current filters.</td>
      </tr>
```

`aria-live` on the caption is why the count is announced when a filter changes. Without it a screen reader user changes a select and hears nothing.

- [ ] **Step 5: Write the filter**

Create `static/js/cell-filters.js`:

```javascript
/* Ranking-table filters.
 *
 * Progressive enhancement in the strict sense: this file creates every control
 * it uses, so a reader without JavaScript sees a complete page rather than dead
 * widgets. It hides rows and updates a count. It computes nothing - values,
 * ranks and verdicts were all rendered by build.py, and the x100 for percent
 * metrics happened once, in tools/cellpage.format_value.
 *
 * Before filtering anything it counts the rendered rows and compares that with
 * the build-time counts in the payload. A template change that renames a data
 * attribute produces a visible banner here instead of a filter that quietly
 * drops rows, which is the failure a static site never surfaces on its own.
 */
(() => {
  "use strict";

  const node = document.getElementById("cell-payload");
  if (!node) return;
  const payload = JSON.parse(node.textContent);
  const expected = new Map(payload.rows.map((row) => [row.metric, row.counts]));

  const MIN_ROWS = 2;

  const tally = (rows, key) => {
    const out = {};
    for (const row of rows) {
      const value = row.dataset[key];
      out[value] = (out[value] || 0) + 1;
    }
    return out;
  };

  const agrees = (a, b) => {
    const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
    for (const key of keys) {
      if ((a[key] || 0) !== (b[key] || 0)) return false;
    }
    return true;
  };

  const banner = (text) => {
    const p = document.createElement("p");
    p.className = "notice notice-broken";
    p.setAttribute("role", "status");
    p.textContent = text;
    return p;
  };

  const select = (id, label, values, onChange) => {
    const wrapper = document.createElement("p");
    wrapper.className = "filter";
    const caption = document.createElement("label");
    caption.setAttribute("for", id);
    caption.textContent = label;
    const control = document.createElement("select");
    control.id = id;
    for (const value of ["", ...values]) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = value === "" ? "All" : value;
      control.append(option);
    }
    control.addEventListener("change", () => onChange(control.value));
    wrapper.append(caption, control);
    return wrapper;
  };

  const search = (id, onInput) => {
    const wrapper = document.createElement("p");
    wrapper.className = "filter";
    const caption = document.createElement("label");
    caption.setAttribute("for", id);
    caption.textContent = "Model";
    const control = document.createElement("input");
    control.type = "search";
    control.id = id;
    control.addEventListener("input", () => onInput(control.value));
    wrapper.append(caption, control);
    return wrapper;
  };

  for (const section of document.querySelectorAll("section.metric-row")) {
    const table = section.querySelector("table.ranking");
    if (!table) continue;

    const rows = Array.from(table.querySelectorAll("tbody tr[data-model]"));
    if (rows.length < MIN_ROWS) continue;

    const counts = expected.get(section.dataset.metric);
    if (
      !counts ||
      !agrees(tally(rows, "source"), counts.source) ||
      !agrees(tally(rows, "verdict"), counts.verdict)
    ) {
      section.append(
        banner("Filters are unavailable: this table and the published data disagree."),
      );
      continue;
    }

    const empty = section.querySelector("[data-empty-when-filtered]");
    const shown = section.querySelector("[data-visible-count]");
    const state = { source: "", verdict: "", query: "" };

    const apply = () => {
      const needle = state.query.trim().toLowerCase();
      let visible = 0;
      for (const row of rows) {
        const label = row.querySelector("th").textContent.toLowerCase();
        const keep =
          (state.source === "" || row.dataset.source === state.source) &&
          (state.verdict === "" || row.dataset.verdict === state.verdict) &&
          (needle === "" || label.includes(needle));
        row.hidden = !keep;
        if (keep) visible += 1;
      }
      empty.hidden = visible !== 0;
      shown.textContent = String(visible);
    };

    const controls = document.createElement("div");
    controls.className = "filters";
    const id = section.id;
    controls.append(
      select(`${id}-source`, "Source", Object.keys(counts.source).sort(), (value) => {
        state.source = value;
        apply();
      }),
      select(`${id}-verdict`, "Versus baseline", Object.keys(counts.verdict).sort(), (value) => {
        state.verdict = value;
        apply();
      }),
      search(`${id}-model`, (value) => {
        state.query = value;
        apply();
      }),
    );
    table.before(controls);
  }
})();
```

Every string reaches the DOM through `textContent`. Model labels come from submissions, which are untrusted input, and this is a page that renders them.

- [ ] **Step 6: Load it and style the controls**

In the `{% block head %}` of `templates/pages/cell.html`:

```jinja
<script src="{{ base_path }}js/cell-filters.js" defer></script>
```

`defer` rather than a `DOMContentLoaded` listener: the script runs after parsing either way, and one mechanism is easier to verify than two. Add to `static/css/cell.css`:

```css
.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  align-items: end;
  margin-block-start: 1rem;
}

.filter {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  margin: 0;
}

.filter label {
  color: var(--text-muted);
  font-size: 0.8125rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.notice-broken {
  border-inline-start: 4px solid var(--state-leads);
}
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run pytest tests/test_cells.py -v`
Expected: all pass, including the colspan assertion that failed in Step 2.

- [ ] **Step 8: Drive it in a browser**

Run `make serve`, open `/cell/total_area_prediction/ng45/cts/` and confirm no controls appear, because one entry is nothing to filter. Then temporarily add two records to that shard, rebuild, and check:

- the three controls appear above the table, and only above tables with entries
- selecting a verdict updates the caption count and the count is announced
- filtering to zero rows shows the empty row, and clearing it restores all three
- every control is reachable and operable by keyboard alone
- with JavaScript disabled the page still renders every row, with no dead controls

Discard the temporary records before committing.

- [ ] **Step 9: Commit**

```bash
git add static/js/cell-filters.js tools/cellpage.py templates/pages/cell.html static/css/cell.css build.py tests/test_cells.py
git commit -m "feat(cells): filter the ranking table against build-time counts"
```

---

### Task 7: Weight, links and accessibility across 232 pages

The phase's own gate. Everything above is now measured rather than assumed, on the whole site rather than on one page.

**Files:**
- Modify: `.pa11yci.json`
- Test: `tests/test_cells.py`

**Interfaces:**
- Consumes: the built site.
- Produces: nothing at runtime. This task only asserts.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cells.py`:

```python
PAGE_BUDGET = 88 * 1024
SITE_BUDGET = 20 * 1024 * 1024


def test_no_cell_page_exceeds_the_page_budget(site: Path) -> None:
    """88 KB. The five heaviest are printed, so the run reports headroom rather
    than only failure. Read them with -s."""
    sizes = sorted(
        ((site / str(urls.cell_output_path(*combo))).stat().st_size, combo)
        for combo in reg.live_combos()
    )
    for size, combo in sizes[-5:]:
        print(f"{size / 1024:6.1f} KiB  {'/'.join(combo)}")
    worst_size, worst = sizes[-1]
    assert worst_size <= PAGE_BUDGET, (
        f"{'/'.join(worst)} is {worst_size / 1024:.1f} KiB"
    )


def test_the_exports_are_measured_as_site_weight(site: Path) -> None:
    """Not page weight - nothing blocks on them - but they are 464 files and
    dist/ has a budget."""
    total = 0
    for combo in reg.live_combos():
        for fmt in ("json", "csv"):
            total += (site / str(urls.cell_export_path(*combo, fmt))).stat().st_size
    print(f"exports: {total / 1024:.1f} KiB across {len(reg.live_combos()) * 2} files")
    assert total <= 4 * 1024 * 1024


def test_the_whole_site_is_within_budget(site: Path) -> None:
    total = sum(p.stat().st_size for p in site.rglob("*") if p.is_file())
    print(f"dist: {total / (1024 * 1024):.2f} MB")
    assert total <= SITE_BUDGET


def test_no_em_dash_reaches_the_rendered_site(site: Path) -> None:
    """A project rule, and generated copy is where it slips through.

    Written as an escape so this test can never be the thing that puts the
    character it forbids into the repository.
    """
    for page in sorted(site.rglob("*.html")):
        assert "\u2014" not in page.read_text(encoding="utf-8"), page.name


def test_every_page_declares_a_language_and_a_unique_title(site: Path) -> None:
    """232 pages titled 'EDA-Schema Leaderboard' are 232 identical tabs and 232
    identical search results."""
    titles: dict[str, str] = {}
    for combo in reg.live_combos():
        html = (site / str(urls.cell_output_path(*combo))).read_text(encoding="utf-8")
        assert "<html lang=" in html
        title = html.split("<title>")[1].split("</title>")[0]
        assert title not in titles, f"{combo} shares a title with {titles.get(title)}"
        titles[title] = "/".join(combo)


def test_every_page_has_exactly_one_h1_and_no_skipped_heading_level(site: Path) -> None:
    for combo in reg.live_combos():
        html = (site / str(urls.cell_output_path(*combo))).read_text(encoding="utf-8")
        levels = [int(n) for n in re.findall(r"<h([1-6])[ >]", html)]
        assert levels.count(1) == 1, combo
        for previous, current in zip(levels, levels[1:], strict=False):
            assert current <= previous + 1, f"{combo}: h{previous} then h{current}"
```

- [ ] **Step 2: Run to verify they fail or pass for a reason you checked**

Run: `uv run pytest tests/test_cells.py -v -s -k budget or title or heading or em_dash`
Expected: sizes printed. A budget test that passes on the first run is only useful if you read the printed number, so read it: a page at 20 KiB and a page at 87 KiB both pass and mean very different things about the next phase.

- [ ] **Step 3: Extend the accessibility matrix**

Add four cell pages to `.pa11yci.json`, one per rendering case, so the a11y workflow covers the cases this phase created rather than only the matrix:

```json
  "urls": [
    "http://localhost:8080/",
    "http://localhost:8080/cell/total_area_prediction/ng45/floorplan/",
    "http://localhost:8080/cell/total_area_prediction/ng45/global_route/",
    "http://localhost:8080/cell/worst_slack_prediction/asap7/global_route/",
    "http://localhost:8080/cell/cell_arc_delay_prediction/sky130/cts/"
  ]
```

That is populated, fully saturated, mixed saturated-and-degenerate, and a `< -1` sentinel. The empty state is covered by the second and third.

- [ ] **Step 4: Run the accessibility gate in both themes**

```bash
uv run python build.py
uv run python -m http.server -d dist 8080 &
npx pa11y-ci
kill %1
```

Expected: 0 errors on all five URLs. Any contrast failure is fixed in `static/css/themes/`, never by removing the glyph channel.

- [ ] **Step 5: Check every link on the site**

```bash
lychee --no-progress --accept 200,206,429 dist/
```

Expected: 0 errors. This is the whole-site version of the pytest link test: pytest proves the internal graph closes, lychee proves the external references resolve. There should be no external image references yet, because `data/plots.json` was deliberately not committed in Task 5.

- [ ] **Step 6: Measure what shipped**

```bash
du -sh dist/
find dist -type f -printf '%s\t%p\n' | sort -rn | head -10
find dist/cell -name index.html | wc -l
```

Expected: `dist/` well inside 20 MB, 232 cell pages, and nothing surprising at the top of the size list.

- [ ] **Step 7: Run the whole gate**

Run: `make check`
Expected: ruff clean, mypy clean, `eda-validate` reporting 0 failures, every test passing, build succeeding.

- [ ] **Step 8: Commit and open the PR**

```bash
git add .pa11yci.json tests/test_cells.py
git commit -m "test(cells): measure page weight, links and accessibility at full scale"
git push -u origin phase-5/cell-pages
gh pr create --title "Phase 5: cell pages" --body "232 pre-rendered cell pages, one per live combo, serving all 880 metric rows. The published baseline is pinned above the ranking on every row, with three visually distinct notices for saturated, degenerate and sentinel cells. Each page ships its own CSV and JSON, written by build.py so no serialiser runs in the browser. The predicted-versus-actual panel references a GitHub Release and degrades to a stated reason until one exists, which is every page today. Page weight, site weight, links and WCAG AA are all measured rather than assumed."
```

---

## Phase gate

Every item must pass before Phase 6 starts.

```bash
make check
lychee --no-progress --accept 200,206,429 dist/
npx pa11y-ci
```

- [ ] `len(reg.live_combos())` pages are generated, and no page exists for a void combo
- [ ] all 880 matrix links resolve, **fragments included**, and every `#metric-<id>` lands on a real section
- [ ] `urls.cell_url` raises on a void combo and on a metric the task does not publish
- [ ] the pages re-derive the 880-cell grid: 232 pages x their metric sets, asserted as a set
- [ ] the 40 / 24 / 120 partition holds as rendered, and 20 `greater_than` plus 12 `less_than` sentinels
- [ ] the published baseline is present and above the ranking on every metric row
- [ ] saturated rows render the notice, no ranking table and no rank attribute
- [ ] degenerate rows render `baseline_kind == "absent"`, `baseline_value is None` and no comparison column
- [ ] sentinel rows render the bound and state that the other side of it is undecided
- [ ] the three notices are not rendered identically, confirmed by a human
- [ ] 212 pages render the empty state, not an empty table, and exactly the 20 `total_area_prediction` combos carry entries
- [ ] percent metrics are scaled exactly once, in `cellpage.format_value`, and nowhere in a template or in JavaScript
- [ ] display precision comes from `reg.precision(task, metric)` on every rendered and exported number
- [ ] every page ships `cell.json` and `cell.csv`, and the inlined payload is **byte-identical** to the JSON file
- [ ] the CSV carries `value_stored` and `value_display` with their own unit columns, and reformatting the first reproduces the second
- [ ] no JavaScript file builds a download and no JavaScript file computes a number
- [ ] the filter cross-checks itself against build-time counts and shows a banner rather than filtering wrongly
- [ ] the filtered-empty row spans exactly the number of columns its table has
- [ ] the plot panel renders `data-plot="absent"` with a stated reason on all 232 pages, and two figures with real alt text when a manifest lists the combo
- [ ] no plot asset is tracked by git, and `build/` is gitignored
- [ ] no page exceeds 88 KB, sizes printed; `dist/` is under 20 MB
- [ ] zero broken links from `lychee`, zero errors from `pa11y-ci` on all five URLs, both themes
- [ ] no page renders `None`, `NaN`, `undefined`, `Infinity` or a Python repr
- [ ] no em dash in any template, stylesheet, script or rendered page

## Review prompt

```
Use a frontend reviewer and a data-integrity reviewer on the Phase 5 diff.

Frontend: open /cell/total_area_prediction/ng45/floorplan/ (populated),
/cell/total_area_prediction/ng45/global_route/ (fully saturated),
/cell/worst_slack_prediction/asap7/global_route/ (saturated MAE beside
degenerate MPE and MNE) and /cell/cell_arc_delay_prediction/sky130/cts/ (a
< -1 sentinel), in both themes. Confirm contrast >= 4.5:1 for every verdict and
state, that verdicts are distinguishable without colour, that the ranking table
and the filter controls are keyboard operable, and that the caption count is
announced when a filter changes. Then confirm the three cases - saturated,
degenerate and sentinel - do not read as the same thing, and that the 212 empty
pages read as a leaderboard awaiting entries rather than as a broken table.
Report only WCAG AA failures and case conflations.

Data integrity: pick ten cells across different tasks, PDKs and stages,
including at least one sentinel, one degenerate, one saturated and one populated
cell. For each, trace the rendered value and both exported values back to
docs/sources/table8_baseline.csv or to a line in an eval.log. Confirm every
percent metric was multiplied by 100 exactly once and that the multiplication
happens only in cellpage.format_value. Confirm no degenerate cell prints a
baseline number anywhere in the HTML, the CSV or the JSON, and that no entry is
ranked on a saturated cell. Confirm the inlined payload and cell.json are the
same bytes on a page you pick at random. Report only correctness gaps.

Do not report style preferences, and do not propose tests for cases the
registry makes unreachable.
```



