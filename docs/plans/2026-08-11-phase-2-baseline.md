# Phase 2 - Baseline Implementation Plan

> **For agentic workers:** Implement this plan task-by-task - either dispatch a fresh subagent per task (recommended) or execute inline with review checkpoints. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** turn Table 8 into `data/baseline.json`, one entry per live cell, with the percent rule and the sentinel rule applied exactly once and in one place.

**Architecture:** `tools/baseline.py` joins `docs/sources/table8_baseline.csv` onto the Phase 1 registries on `table8_label`, converts each published cell into a `Bound`, and emits a deterministic `data/baseline.json`.
All four dimensions join with zero unmatched, verified, so this is a mechanical join and not a research task.
A separate `tools/checks/baseline.py` registers into `tools.checks` so `make validate` covers it, and it verifies the committed file two ways: against a fresh build from the CSV, and against the registry's own structural rules.

**Tech stack:** Python 3.11+, `uv`, `pytest`, `mypy --strict`, `ruff`. Standard library `csv`, `json` and `decimal` only; no new dependency.

## Global constraints

Copied from `PLAN.md` and `CLAUDE.md`; every task's requirements implicitly include these.

- Python **3.11+**, type hints on all public functions, `ruff` and `mypy` clean.
- **The registry is the only source of vocabulary.** No task, metric, stage or PDK id appears as a literal in `tools/baseline.py` or `tools/checks/baseline.py`. Selection is by registry attribute (`metric.percent`, `metric.direction`) or by registry predicate (`reg.is_void`, `reg.is_degenerate`, `reg.is_saturated`).
- **Counts are derived, never literal.** Phase 1 ships `tests/test_registry.py::test_no_count_literal_appears_in_tools`, which greps every `.py` under `tools/` for the bare integers `46 232 880 856 120 24 40 920`. It strips comments but **not docstrings**, so a docstring reading "the 24 degenerate cells" fails the suite. In `tools/`, name these sets, never count them.
- **Percent metrics are stored as a fraction in `[0, 1]`.** The `x100` happens at the display boundary only. The CSV is the one source that arrives in display units, so it is divided by 100 on read.
- **`make check` is the gate.** Run it and show the output before claiming a task is done.
- Conventional commits. Branch `phase-2/baseline`. Never push to `main`.
- **Never use an em dash** in prose, code comments or generated copy.

## Source of truth

`docs/sources/table8_baseline.csv`, 920 rows, columns `task,metric,stage_transition,pdk,value,kind,src_line`.
`docs/DATA_CONTRACT.md` rules the two conventions this phase implements: "Published sentinels" and "Percent storage - the single authoritative rule".

Everything below was verified against the CSV before being written down.

| Fact | Verified value |
|---|---|
| CSV rows | 920 |
| `kind` split | 856 `VAL`, 40 `VOID`, 24 `DEGENERATE` |
| Distinct join labels | 12 task, 11 metric, 5 stage, 4 pdk - all exactly the Appendix A `table8_label` values, zero unmatched |
| `VOID` rows | `Total wirelength (u m)` 12, `Interconnect length (u m)` 28, all at `floorplan to detailed route` |
| `DEGENERATE` rows | `MPE` 12 and `MNE` 12, across the three slack tasks, all at `global route to detailed route` |
| `> 10000 %` sentinels | 20, every one on `MAPE` |
| `< -1` sentinels | 12, every one on `R^2`, all in the three arc tasks |
| Values carrying a thousands separator | 44 |
| Values carrying a `%` suffix | exactly the five percent metrics, 324 rows, no others |
| Numeric percent values above 1.0 | 250 of 304, so the CSV is unambiguously in display units |
| `TPR`/`TNR` display range | 8.39 to 100.00, so 0.0839 to 1.0000 stored |
| `MAPE` family display range | 0.00 to 1134.69 plus the 20 sentinels, so **no upper guard is possible** |
| Saturated cells at their optimum | 120 of 120, zero exceptions |

Two figures in `docs/DATA_CONTRACT.md` read oddly until you know the subset each uses, so record it here rather than re-deriving it under time pressure.
"211 of its 252 percent values exceed 1.0" counts `MAPE`, `TPR` and `TNR` only, and counts the 20 sentinels as above the threshold.
"48 of 244 published MAPE cells legitimately exceed 150 %" counts the whole MAPE family (`MAPE`, `MAPE P95`, `MAPE TOP5`), of which 28 numeric cells exceed 150 % and 20 are sentinels.
Both reconcile exactly. Neither is wrong.

## File structure

| File | Responsibility |
|---|---|
| `tools/baseline.py` | `Bound`, `Baseline`, `parse_bound`, the CSV join, deterministic emit, the loader, `eda-baseline` |
| `tools/checks/baseline.py` | the `baseline` check registered into `tools.checks` |
| `data/baseline.json` | 880 generated entries, committed, never edited by hand |
| `tests/test_baseline.py` | parsing, the join, the emit, the loader, paper spot-checks |
| `tests/test_baseline_check.py` | the check's own assertions, and the mutations it must catch |
| `pyproject.toml` | the `eda-baseline` console script |
| `Makefile` | `make baseline` |

## What is stored, and why it is 880 and not 856

`data/baseline.json` carries **one entry per live cell**, so its key set is `reg.live_cells()` exactly.

```
920 CSV rows
 - 40 VOID       the cell does not exist, so it is absent from the file entirely
 = 880 entries   of which 856 are published and 24 are degenerate
```

At `indent=2` the emitted file is roughly 300 KB, well inside the repository's 1 MB per-file limit, so it is committed rather than generated in CI.

A `VOID` row is dropped.
A `DEGENERATE` row is kept with `baseline_state: "degenerate"` and a `Bound` of kind `absent`, so a renderer can never print `0.00` for a quantity that was never measured, and Phase 4 can never award `beats_baseline` against it.

---

### Task 1: The Bound type and value parsing

The whole phase's correctness lives in one pure function.
It is isolated first, with no I/O and no registry lookup, so its tests are unambiguous.

**Files:**
- Create: `tools/baseline.py`
- Test: `tests/test_baseline.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `baseline.BoundKind`, `baseline.Bound(kind: BoundKind, value: float | None)`, `baseline.parse_bound(raw: str, *, percent: bool) -> Bound`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_baseline.py`:

```python
"""The published baseline: parsing, the join, the emit and the loader.

Expected values and counts live here, in tests. They must never appear in tools/.
"""

from __future__ import annotations

import pytest

from tools import baseline as bl


def test_a_plain_value_parses_through_its_thousands_separator() -> None:
    assert bl.parse_bound("1,781.97", percent=False) == bl.Bound(bl.BoundKind.EXACT, 1781.97)


def test_a_percent_value_is_divided_by_one_hundred() -> None:
    """The CSV is in DISPLAY units. Storage is a fraction. Inverting this makes
    every MAPE cell render baseline_leads and every TPR/TNR cell render
    beats_baseline, with no error raised anywhere."""
    assert bl.parse_bound("12.43 %", percent=True) == bl.Bound(bl.BoundKind.EXACT, 0.1243)


def test_the_percent_conversion_carries_no_float_noise() -> None:
    """Decimal, not float, division. `12.43 / 100` in binary floating point is
    0.12429999999999999, and 69 of the published cells land like that. The CSV
    holds decimal strings, so scale them as decimals and cross to float once."""
    assert repr(bl.parse_bound("22.51 %", percent=True).value) == "0.2251"


def test_a_rate_at_one_hundred_percent_becomes_exactly_one() -> None:
    assert bl.parse_bound("100.00 %", percent=True) == bl.Bound(bl.BoundKind.EXACT, 1.0)


def test_the_upper_sentinel_becomes_a_greater_than_bound() -> None:
    """The paper thresholded the underlying number away, so it does not exist and
    must never be invented. The threshold converts like any other percent."""
    assert bl.parse_bound("> 10000 %", percent=True) == bl.Bound(bl.BoundKind.GREATER_THAN, 100.0)


def test_the_lower_sentinel_becomes_a_less_than_bound() -> None:
    assert bl.parse_bound("< -1", percent=False) == bl.Bound(bl.BoundKind.LESS_THAN, -1.0)


def test_a_negative_value_parses_as_an_exact_bound() -> None:
    assert bl.parse_bound("-0.402", percent=False) == bl.Bound(bl.BoundKind.EXACT, -0.402)


def test_an_empty_value_is_rejected_rather_than_defaulted() -> None:
    """VOID and DEGENERATE rows arrive empty. Silently yielding 0.0 here would
    publish a fabricated baseline for a cell the paper never measured."""
    with pytest.raises(ValueError):
        bl.parse_bound("", percent=False)


def test_percent_comes_from_the_registry_not_from_the_suffix() -> None:
    """The trailing '%' is a formatting artifact of the table. The registry's
    metric.percent flag is the rule, and it is what the caller passes."""
    assert bl.parse_bound("12.43 %", percent=False) == bl.Bound(bl.BoundKind.EXACT, 12.43)
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `uv run pytest tests/test_baseline.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'tools.baseline'`

- [ ] **Step 3: Implement**

Create `tools/baseline.py`:

```python
"""The published Table 8 baseline, one entry per live cell.

Generated by joining docs/sources/table8_baseline.csv onto data/registry/ on the
table8_label of each dimension. Nothing here is transcribed by hand.

Two conversions happen on read, here and nowhere else:

  * a percent-format metric is DIVIDED by 100, because the CSV is the one source
    that arrives in display units while everything under data/ stores a fraction.
    See docs/DATA_CONTRACT.md, "Percent storage - the single authoritative rule".
  * a published sentinel becomes a one-sided Bound, never a value with a display
    override. The paper thresholded the underlying number away, so it does not
    exist in any source we have.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "docs" / "sources" / "table8_baseline.csv"
BASELINE_PATH = ROOT / "data" / "baseline.json"

PAPER = "paper"
PUBLISHED = "published"
DEGENERATE = "degenerate"

_PERCENT_SCALE = Decimal(100)

class BoundKind(StrEnum):
    """The four shapes a published baseline can take.

    An enum rather than a `Literal` alias because this value crosses a JSON
    boundary. `data/baseline.json` stores it as text, and reading it back into a
    `Literal` yields a bare `str` that nothing validates at runtime, so a drifted
    or corrupted kind degrades into a silently-False `==`. `BoundKind(raw)`
    raises at the parse boundary instead.

    That distinction is load-bearing rather than stylistic: the ABSENT check is
    what stops a comparison being drawn against a degenerate 0/0 baseline, and a
    silent False there awards `beats_baseline` against a baseline that was never
    measured. StrEnum is a `str` subclass, so the emitted JSON is unchanged.
    """

    EXACT = "exact"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    ABSENT = "absent"


@dataclass(frozen=True, slots=True)
class Bound:
    """What the paper published about one cell's baseline, as a one-sided fact.

    Phase 4's ranking consumes this, so the shape is a contract rather than an
    implementation detail.

    EXACT        `value` is the number. Every comparison is decidable.
    GREATER_THAN the true value is strictly ABOVE `value`. Published as
                 "> 10000 %".
    LESS_THAN    the true value is strictly BELOW `value`. Published as "< -1".
    ABSENT       no baseline was ever measured; `value` is None. This is the 0/0
                 case, not a value of zero, and nothing may be scored as beating
                 it.

    `value` is None if and only if `kind` is ABSENT.

    A sentinel always points AWAY from the good direction: the baseline is known
    to be worse than the bound, never better. So GREATER_THAN only ever appears
    on a lower-is-better metric and LESS_THAN only on a higher-is-better one,
    and a submission on the defined side of the threshold is a decidable win:

      greater_than, lower-is-better  -> a submission at or below `value` wins;
                                        anything above it is `no_comparison`
      less_than, higher-is-better    -> a submission at or above `value` wins;
                                        anything below it is `no_comparison`
      absent                         -> always `no_comparison`

    That invariant is asserted in tools/checks/baseline.py rather than assumed.
    """

    kind: BoundKind
    value: float | None


def parse_bound(raw: str, *, percent: bool) -> Bound:
    """Turn one Table 8 cell into a Bound.

    `percent` comes from the metric registry, never from the presence of a "%" in
    the string. The suffix is a formatting artifact of the table; the registry is
    the rule, and the two must not be allowed to drift.

    Scaling is decimal, not binary. The CSV holds decimal strings, so dividing as
    Decimal and crossing to float once keeps the emitted JSON free of artifacts
    like 0.12429999999999999.
    """
    text = raw.strip()
    if not text:
        raise ValueError("empty baseline value: a cell with no published number")

    kind = BoundKind.EXACT
    if text.startswith(">"):
        kind, text = BoundKind.GREATER_THAN, text[1:]
    elif text.startswith("<"):
        kind, text = BoundKind.LESS_THAN, text[1:]

    number = Decimal(text.strip().removesuffix("%").strip().replace(",", ""))
    if percent:
        number /= _PERCENT_SCALE
    return Bound(kind=kind, value=float(number))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_baseline.py -v`
Expected: 9 passed

- [ ] **Step 5: Verify lint and types**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy`
Expected: all clean

- [ ] **Step 6: Commit**

```bash
git add tools/baseline.py tests/test_baseline.py
git commit -m "feat(baseline): add the Bound type and Table 8 value parsing"
```

---

### Task 2: The registry-driven join

The loop is driven from `reg.live_cells()`, not from the CSV.
That way a published cell missing from the table is a hard error instead of a silent gap, and the emitted key set is the 880 by construction rather than by coincidence.

**Files:**
- Modify: `tools/baseline.py`
- Test: `tests/test_baseline.py`

**Interfaces:**
- Consumes: `tools.registry` (`tasks`, `metrics`, `stages`, `pdks`, `metric`, `live_cells`, `is_degenerate`).
- Produces: `baseline.Baseline`, `baseline.build() -> tuple[Baseline, ...]`, `baseline.published_sentinel_keys() -> frozenset[tuple[str, str, str, str]]`.

- [ ] **Step 1: Write the failing tests**

Add `import csv` and `from tools import registry as reg` to the import block at the **top** of `tests/test_baseline.py`, then append:

```python
def _csv_rows() -> list[dict[str, str]]:
    with bl.CSV_PATH.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_build_emits_one_entry_per_live_cell() -> None:
    assert len(bl.build()) == 880


def test_the_keys_are_exactly_the_live_cells() -> None:
    """Not a count. The set, both directions."""
    assert {e.key for e in bl.build()} == set(reg.live_cells())


def test_void_cells_are_absent_entirely_rather_than_null() -> None:
    """A void cell does not exist. Emitting it with a null value would put it back
    into the 880 and make the matrix render a structural hole as a data gap."""
    voids = [r for r in _csv_rows() if r["kind"] == "VOID"]
    assert len(voids) == 40
    keys = {e.key for e in bl.build()}
    for task_id, _metric, _pdk, stage_id in keys:
        assert not reg.is_void(task_id, stage_id)


def test_degenerate_cells_carry_an_absent_bound() -> None:
    degenerate = [e for e in bl.build() if e.baseline_state == bl.DEGENERATE]
    assert len(degenerate) == 24
    for entry in degenerate:
        assert entry.bound == bl.Bound(bl.BoundKind.ABSENT, None)
        assert reg.is_degenerate(entry.task, entry.metric, entry.stage)


def test_published_cells_all_carry_a_number() -> None:
    published = [e for e in bl.build() if e.baseline_state == bl.PUBLISHED]
    assert len(published) == 856
    for entry in published:
        assert entry.bound.value is not None
        assert entry.bound.kind != "absent"


def test_every_entry_is_sourced_from_the_paper() -> None:
    assert {e.source for e in bl.build()} == {bl.PAPER}


def test_every_csv_row_is_either_consumed_or_void() -> None:
    """The join is checked from the CSV side too, so a row the registry does not
    know about cannot be silently skipped."""
    labels = {
        (t.table8_label, m.table8_label, s.table8_label, p.table8_label)
        for t in reg.tasks()
        for m in reg.metrics()
        for s in reg.stages()
        for p in reg.pdks()
    }
    unconsumed = 0
    for row in _csv_rows():
        key = (row["task"], row["metric"], row["stage_transition"], row["pdk"])
        assert key in labels, f"CSV row does not join: {key}"
        if row["kind"] == "VOID":
            unconsumed += 1
    assert unconsumed == 40


def test_the_sentinel_key_set_is_derived_from_the_raw_csv() -> None:
    """Twenty upper sentinels, all MAPE. Twelve lower sentinels, all R2. Derived
    by scanning the raw value strings, which is a different route than
    parse_bound takes, so a sentinel demoted to an exact value is caught."""
    assert len(bl.published_sentinel_keys()) == 32
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_baseline.py -v`
Expected: FAIL, `AttributeError: module 'tools.baseline' has no attribute 'build'`

- [ ] **Step 3: Implement**

Append to `tools/baseline.py`. Add `import csv` and `from functools import cache` and `from tools import registry as reg` to the imports:

```python
CellKey = tuple[str, str, str, str]


@dataclass(frozen=True, slots=True)
class Baseline:
    """One live cell's published baseline."""

    task: str
    metric: str
    pdk: str
    stage: str
    baseline_state: str
    bound: Bound
    source: str
    src_line: int

    @property
    def key(self) -> CellKey:
        return (self.task, self.metric, self.pdk, self.stage)


LabelKey = tuple[str, str, str, str]


@cache
def _csv_index() -> dict[LabelKey, dict[str, str]]:
    """The CSV, indexed on (task, metric, stage, pdk) table8 labels."""
    with CSV_PATH.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    index: dict[LabelKey, dict[str, str]] = {}
    for row in rows:
        key = (row["task"], row["metric"], row["stage_transition"], row["pdk"])
        if key in index:
            raise ValueError(f"duplicate Table 8 row for {key}")
        index[key] = row
    return index


@cache
def _label_key_index() -> dict[CellKey, LabelKey]:
    """Cell ids to the labels that join them onto the CSV."""
    task_label = {t.id: t.table8_label for t in reg.tasks()}
    metric_label = {m.id: m.table8_label for m in reg.metrics()}
    stage_label = {s.id: s.table8_label for s in reg.stages()}
    pdk_label = {p.id: p.table8_label for p in reg.pdks()}
    return {
        (task_id, metric_id, pdk_id, stage_id): (
            task_label[task_id],
            metric_label[metric_id],
            stage_label[stage_id],
            pdk_label[pdk_id],
        )
        for task_id, metric_id, pdk_id, stage_id in reg.live_cells()
    }


@cache
def published_sentinel_keys() -> frozenset[CellKey]:
    """Cells the paper published as a threshold rather than a number.

    Derived by scanning the raw value strings, deliberately by a different route
    than parse_bound takes. A sentinel silently demoted to an exact value is then
    caught by disagreement rather than confirmed by a shared reading.
    """
    rows = _csv_index()
    return frozenset(
        cell_key
        for cell_key, label_key in _label_key_index().items()
        if rows[label_key]["value"].strip().startswith((">", "<"))
    )


def build() -> tuple[Baseline, ...]:
    """One Baseline per live cell, in registry order.

    Driven from reg.live_cells() rather than from the CSV, so the emitted key set
    is the live set by construction and a published cell the table does not carry
    raises instead of quietly vanishing.
    """
    rows = _csv_index()
    entries: list[Baseline] = []

    for cell_key, label_key in _label_key_index().items():
        task_id, metric_id, pdk_id, stage_id = cell_key
        try:
            row = rows[label_key]
        except KeyError:
            raise KeyError(f"no Table 8 row for {label_key}") from None

        if row["kind"] == "VOID":
            raise ValueError(
                f"the registry says this cell is live, Table 8 says VOID: {cell_key}"
            )

        degenerate = reg.is_degenerate(task_id, metric_id, stage_id)
        if degenerate != (row["kind"] == "DEGENERATE"):
            raise ValueError(
                f"degeneracy disagrees between the registry and Table 8: {cell_key}"
            )

        bound = (
            Bound(kind=BoundKind.ABSENT, value=None)
            if degenerate
            else parse_bound(row["value"], percent=reg.metric(metric_id).percent)
        )
        entries.append(
            Baseline(
                task=task_id,
                metric=metric_id,
                pdk=pdk_id,
                stage=stage_id,
                baseline_state=DEGENERATE if degenerate else PUBLISHED,
                bound=bound,
                source=PAPER,
                src_line=int(row["src_line"]),
            )
        )
    return tuple(entries)
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_baseline.py -v`
Expected: 17 passed

- [ ] **Step 5: Commit**

```bash
git add tools/baseline.py tests/test_baseline.py
git commit -m "feat(baseline): join Table 8 onto the registry on table8_label"
```

---

### Task 3: Deterministic emit

`data/baseline.json` is committed, because the site build and CI both read it and it derives from a committed CSV.
It is generated, never hand-edited, and a test proves the committed bytes are what the generator currently produces.

**Files:**
- Modify: `tools/baseline.py`, `pyproject.toml`, `Makefile`
- Create: `data/baseline.json`
- Test: `tests/test_baseline.py`

**Interfaces:**
- Consumes: `baseline.build`.
- Produces: `baseline.to_json(entries: tuple[Baseline, ...]) -> str`, `baseline.main() -> int`, the `eda-baseline` console script, the `make baseline` target.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_baseline.py`:

```python
def test_regeneration_is_byte_identical() -> None:
    assert bl.to_json(bl.build()) == bl.to_json(bl.build())


def test_the_committed_file_matches_a_fresh_build() -> None:
    """data/baseline.json is generated, never edited. If this fails, either the
    CSV moved or somebody typed into the file."""
    assert bl.BASELINE_PATH.read_text(encoding="utf-8") == bl.to_json(bl.build())


def test_the_emitted_json_carries_no_float_noise() -> None:
    """A reviewer diffing this file against the paper must see 0.1243 where the
    paper says 12.43 %, not 0.12429999999999999."""
    text = bl.BASELINE_PATH.read_text(encoding="utf-8")
    assert "0000000" not in text
    assert "9999999" not in text
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_baseline.py -v`
Expected: FAIL, `AttributeError: module 'tools.baseline' has no attribute 'to_json'`

- [ ] **Step 3: Implement the emitter**

Append to `tools/baseline.py`, and add `import json` to the imports:

```python
def to_json(entries: tuple[Baseline, ...]) -> str:
    """Serialize deterministically.

    Order is registry order, taken from build(), so the file reads in the same
    sequence as the matrix and a diff stays local to what actually changed.
    """
    payload = {
        "generated_from": CSV_PATH.relative_to(ROOT).as_posix(),
        "cells": [
            {
                "task": entry.task,
                "metric": entry.metric,
                "pdk": entry.pdk,
                "stage": entry.stage,
                "baseline_state": entry.baseline_state,
                "bound": {"kind": entry.bound.kind, "value": entry.bound.value},
                "source": entry.source,
                "src_line": entry.src_line,
            }
            for entry in entries
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    """Regenerate data/baseline.json. Entry point for `eda-baseline`."""
    entries = build()
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_PATH.write_text(to_json(entries), encoding="utf-8")
    print(
        f"baseline: wrote {len(entries)} cells to "
        f"{BASELINE_PATH.relative_to(ROOT).as_posix()}"
    )
    return 0
```

- [ ] **Step 4: Wire up the entry point**

In `pyproject.toml`, extend the `[project.scripts]` block Phase 1 restored:

```toml
[project.scripts]
eda-validate = "tools.validate:main"
eda-baseline = "tools.baseline:main"
```

In the `Makefile`, add `baseline` to the `.PHONY` line and add the target above `validate`:

```make
baseline:
	@if [ ! -f tools/baseline.py ]; then echo "baseline: tools/baseline.py does not exist yet (Phase 2)"; exit 1; fi; uv run eda-baseline
```

`baseline` is deliberately **not** a dependency of `check`. Regenerating a tracked file as a side effect of the gate would let a drifting CSV silently rewrite committed data instead of failing. `test_the_committed_file_matches_a_fresh_build` is the detector, and it reports rather than repairs.

- [ ] **Step 5: Generate the file**

Run: `make baseline`
Expected: `baseline: wrote 880 cells to data/baseline.json`

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/test_baseline.py -v`
Expected: 20 passed

- [ ] **Step 7: Commit**

```bash
git add tools/baseline.py pyproject.toml Makefile data/baseline.json tests/test_baseline.py
git commit -m "feat(baseline): emit data/baseline.json deterministically"
```

---

### Task 4: The loader and the paper spot-checks

Everything downstream reads baselines through one function.
The spot-checks pin real numbers from the paper so a plausible-looking regression in the join has to survive a comparison with the printed table.

**Files:**
- Modify: `tools/baseline.py`
- Test: `tests/test_baseline.py`

**Interfaces:**
- Consumes: `data/baseline.json`.
- Produces: `baseline.baselines() -> dict[CellKey, Baseline]`, `baseline.lookup(task_id, metric_id, pdk_id, stage_id) -> Baseline` raising `KeyError` on an unknown or void cell.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_baseline.py`:

```python
def test_the_loader_round_trips_the_builder() -> None:
    assert bl.baselines() == {e.key: e for e in bl.build()}


def test_lookup_rejects_a_void_cell() -> None:
    """Void cells are absent by design. A silent default here would resurrect the
    40 cells the paper says do not exist."""
    with pytest.raises(KeyError):
        bl.lookup("total_wirelength_prediction", "mae", "ng45", "floorplan")


def test_total_area_mae_ng45_floorplan_matches_table_8() -> None:
    """Table 8 prints 1,781.97. MAE is not a percent metric, so it is stored
    as-is."""
    entry = bl.lookup("total_area_prediction", "mae", "ng45", "floorplan")
    assert entry.bound == bl.Bound(bl.BoundKind.EXACT, 1781.97)
    assert entry.baseline_state == bl.PUBLISHED
    assert entry.source == bl.PAPER


def test_total_area_mape_ng45_floorplan_is_stored_as_a_fraction() -> None:
    """Table 8 prints 12.43 %."""
    entry = bl.lookup("total_area_prediction", "mape", "ng45", "floorplan")
    assert entry.bound == bl.Bound(bl.BoundKind.EXACT, 0.1243)


def test_worst_slack_tpr_ng45_cts_is_exactly_one() -> None:
    """Table 8 prints 100.00 %. A rate at its ceiling, which is why saturation is
    a stage rule and not an is-the-error-near-zero test."""
    entry = bl.lookup("worst_slack_prediction", "tpr", "ng45", "cts")
    assert entry.bound == bl.Bound(bl.BoundKind.EXACT, 1.0)


def test_total_wirelength_mae_ng45_global_route_is_still_live() -> None:
    """The two wirelength tasks are the reason saturation excludes them. At
    global route their baseline error is nowhere near zero."""
    entry = bl.lookup("total_wirelength_prediction", "mae", "ng45", "global_route")
    assert entry.bound == bl.Bound(bl.BoundKind.EXACT, 13698.67)
    assert not reg.is_saturated("total_wirelength_prediction", "mae", "global_route")


def test_net_arc_delay_mape_ng45_floorplan_is_an_upper_sentinel() -> None:
    """Table 8 prints "> 10000 %". Stored as a bound at 100.0, which is 10000 %
    as a fraction, with no invented underlying value."""
    entry = bl.lookup("net_arc_delay_prediction", "mape", "ng45", "floorplan")
    assert entry.bound == bl.Bound(bl.BoundKind.GREATER_THAN, 100.0)


def test_net_arc_delay_r2_ng45_floorplan_is_a_lower_sentinel() -> None:
    """Table 8 prints "< -1". R2 is not a percent metric, so no scaling."""
    entry = bl.lookup("net_arc_delay_prediction", "r2", "ng45", "floorplan")
    assert entry.bound == bl.Bound(bl.BoundKind.LESS_THAN, -1.0)


def test_worst_slack_mpe_ng45_global_route_has_no_baseline() -> None:
    """Table 8 prints "No positive or negative error, n_p = n_n = 0". That is a
    0/0, not a zero, and nothing may be scored as beating it."""
    entry = bl.lookup("worst_slack_prediction", "mpe", "ng45", "global_route")
    assert entry.baseline_state == bl.DEGENERATE
    assert entry.bound == bl.Bound(bl.BoundKind.ABSENT, None)
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_baseline.py -v`
Expected: FAIL, `AttributeError: module 'tools.baseline' has no attribute 'baselines'`

- [ ] **Step 3: Implement**

Append to `tools/baseline.py`:

```python
@cache
def baselines() -> dict[CellKey, Baseline]:
    """Read data/baseline.json. The only read path for published baselines.

    Void cells are absent from the mapping, because they are absent from the file
    and from the grid.
    """
    payload = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    entries: dict[CellKey, Baseline] = {}
    for row in payload["cells"]:
        entry = Baseline(
            task=row["task"],
            metric=row["metric"],
            pdk=row["pdk"],
            stage=row["stage"],
            baseline_state=row["baseline_state"],
            bound=Bound(kind=row["bound"]["kind"], value=row["bound"]["value"]),
            source=row["source"],
            src_line=row["src_line"],
        )
        if entry.key in entries:
            raise ValueError(f"duplicate baseline entry for {entry.key}")
        entries[entry.key] = entry
    return entries


def lookup(task_id: str, metric_id: str, pdk_id: str, stage_id: str) -> Baseline:
    """Look up one cell. Raises KeyError on an unknown or void cell, deliberately.

    A default here would fabricate a baseline for a cell the paper never
    published, and the leaderboard's central claim is a comparison against it.

    This is the ONE accessor. Callers that want only the published bound write
    `lookup(...).bound`; there is no second `bound_for` entry point, because two
    names for one lookup is how Phases 3 through 8 came to disagree about which
    one existed. `lookup` rather than `baseline` so the call does not stutter as
    `baseline.baseline(...)` at every site.
    """
    key = (task_id, metric_id, pdk_id, stage_id)
    try:
        return baselines()[key]
    except KeyError:
        raise KeyError(f"no baseline for {key!r}; void cells are absent") from None
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_baseline.py -v`
Expected: 29 passed

- [ ] **Step 5: Commit**

```bash
git add tools/baseline.py tests/test_baseline.py
git commit -m "feat(baseline): add the typed loader and pin ten Table 8 cells"
```

---

### Task 5: The baseline check

Two independent layers.
The first compares the committed file against a fresh build, which catches any drift in the file.
The second restates the rules from the registry, which catches a wrong `build()` that the first layer would happily confirm.

**Files:**
- Create: `tools/checks/baseline.py`
- Modify: `tools/checks/__init__.py`
- Test: `tests/test_baseline_check.py`

**Interfaces:**
- Consumes: `tools.baseline`, `tools.registry`, `tools.checks.register`.
- Produces: `baseline.check() -> list[str]`, registered as `"baseline"` in `tools.checks.CHECKS`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_baseline_check.py`:

```python
"""The baseline check, and the mutations it must catch.

Written against the registry and the raw CSV rather than against tools/baseline.py,
so a shared misreading cannot self-confirm.
"""

from __future__ import annotations

from tools import baseline as bl
from tools import registry as reg
from tools.checks import CHECKS
from tools.checks import baseline as check_mod


def test_the_check_is_registered() -> None:
    assert "baseline" in CHECKS


def test_the_check_passes_on_the_committed_data() -> None:
    assert check_mod.check() == []


def test_the_partition_of_stored_states() -> None:
    """Assert the partition, not the total. 880 stays correct while degenerate
    and published are swapped."""
    entries = bl.baselines()
    assert len(entries) == 880
    published = [e for e in entries.values() if e.baseline_state == bl.PUBLISHED]
    degenerate = [e for e in entries.values() if e.baseline_state == bl.DEGENERATE]
    assert len(published) == 856
    assert len(degenerate) == 24


def test_sentinel_bounds_point_away_from_the_good_direction() -> None:
    """20 greater_than, every one on a lower-is-better metric. 12 less_than,
    every one on a higher-is-better metric. That asymmetry is what makes a
    submission on the defined side of the threshold a decidable win."""
    upper = [e for e in bl.baselines().values() if e.bound.kind is bl.BoundKind.GREATER_THAN]
    lower = [e for e in bl.baselines().values() if e.bound.kind is bl.BoundKind.LESS_THAN]
    assert len(upper) == 20
    assert len(lower) == 12
    assert all(reg.metric(e.metric).direction == "lower" for e in upper)
    assert all(reg.metric(e.metric).direction == "higher" for e in lower)


def test_rates_are_stored_in_the_unit_interval() -> None:
    """tpr and tnr are true rates, so the assertion is free and it catches a
    100x error outright: a percent-stored rate lands in 8.39 to 100."""
    rates = [
        e
        for e in bl.baselines().values()
        if reg.metric(e.metric).percent and reg.metric(e.metric).direction == "higher"
    ]
    assert len(rates) == 80
    values = [e.bound.value for e in rates]
    assert all(v is not None and 0.0 <= v <= 1.0 for v in values)


def test_the_mape_family_has_no_ceiling() -> None:
    """MAPE is unbounded above. Its largest published cell is Cell Arc Slew at
    IHP130 floorplan, 1134.69 %, which is 11.3469 stored, and 20 more sit at the
    sentinel. A [0, 1] or [0, 1.5] guard here would reject published data."""
    family = [
        e
        for e in bl.baselines().values()
        if reg.metric(e.metric).percent and reg.metric(e.metric).direction == "lower"
    ]
    over_one = [
        e
        for e in family
        if e.bound.kind is bl.BoundKind.EXACT and e.bound.value is not None and e.bound.value > 1.0
    ]
    assert len(over_one) == 33


def test_saturated_cells_are_published_at_their_optimum() -> None:
    """The registry says saturation is a stage rule. The paper's numbers agree on
    all 120, with zero exceptions. This is the one place those two independent
    statements are compared."""
    saturated = [
        e
        for e in bl.baselines().values()
        if reg.is_saturated(e.task, e.metric, e.stage)
    ]
    assert len(saturated) == 120
    for entry in saturated:
        optimum = 1.0 if reg.metric(entry.metric).direction == "higher" else 0.0
        assert entry.bound == bl.Bound(bl.BoundKind.EXACT, optimum), entry.key
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_baseline_check.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'tools.checks.baseline'`

- [ ] **Step 3: Implement the check**

Create `tools/checks/baseline.py`:

```python
"""data/baseline.json must agree with the paper and with the registry.

Two layers, deliberately independent:

  1. the committed file against a fresh build from the CSV, which catches drift
     in the file
  2. the registry's own rules restated over the loaded entries, which catches a
     wrong builder that layer 1 would confirm rather than detect

No count is written as a literal. Every expected set comes from tools.registry.
"""

from __future__ import annotations

from tools import baseline as bl
from tools import registry as reg
from tools.checks import register


@register("baseline")
def check() -> list[str]:
    failures: list[str] = []
    entries = bl.baselines()

    fresh = {entry.key: entry for entry in bl.build()}
    for key in sorted(fresh.keys() - entries.keys()):
        failures.append(f"{key}: built from the CSV but missing from baseline.json")
    for key in sorted(entries.keys() - fresh.keys()):
        failures.append(f"{key}: in baseline.json but not built from the CSV")
    for key in sorted(entries.keys() & fresh.keys()):
        if entries[key] != fresh[key]:
            failures.append(
                f"{key}: committed {entries[key]} does not match the CSV {fresh[key]}"
            )

    expected = set(reg.live_cells())
    for key in sorted(expected - entries.keys()):
        failures.append(f"{key}: live cell missing from baseline.json")
    for key in sorted(entries.keys() - expected):
        failures.append(f"{key}: baseline.json carries a cell that is not live")

    sentinels = bl.published_sentinel_keys()
    for key in sorted(entries):
        entry = entries[key]
        task_id, metric_id, _pdk_id, stage_id = key
        spec = reg.metric(metric_id)

        if entry.source != bl.PAPER:
            failures.append(f"{key}: source is {entry.source!r}, expected {bl.PAPER!r}")

        degenerate = reg.is_degenerate(task_id, metric_id, stage_id)
        if degenerate != (entry.baseline_state == bl.DEGENERATE):
            failures.append(f"{key}: baseline_state disagrees with the registry")

        if degenerate:
            if entry.bound != bl.Bound(bl.BoundKind.ABSENT, None):
                failures.append(f"{key}: a degenerate cell must carry an absent bound")
            continue

        value = entry.bound.value
        if entry.bound.kind is bl.BoundKind.ABSENT or value is None:
            failures.append(f"{key}: a published cell must carry a value")
            continue

        # A sentinel always points AWAY from the good direction, so a submission
        # on the defined side of the threshold is a decidable win. Reading the
        # sentinel set straight off the raw CSV text is a different route than
        # parse_bound takes, so a demotion to an exact value is caught here.
        is_sentinel = entry.bound.kind in (bl.BoundKind.GREATER_THAN, bl.BoundKind.LESS_THAN)
        if key in sentinels and not is_sentinel:
            failures.append(f"{key}: published as a sentinel, stored as an exact value")
        if is_sentinel and key not in sentinels:
            failures.append(f"{key}: stored as a bound, published as a plain value")
        if entry.bound.kind is bl.BoundKind.GREATER_THAN and spec.direction != "lower":
            failures.append(f"{key}: greater_than bound on a higher-is-better metric")
        if entry.bound.kind is bl.BoundKind.LESS_THAN and spec.direction != "higher":
            failures.append(f"{key}: less_than bound on a lower-is-better metric")

        # A rate genuinely cannot exceed 1, so this assertion is free and catches
        # a percent-stored value outright. Do NOT extend it to the lower-is-better
        # percent metrics: MAPE is unbounded above and a ceiling would reject
        # published cells. See docs/DATA_CONTRACT.md, "How to guard it".
        if spec.percent and spec.direction == "higher" and not 0.0 <= value <= 1.0:
            failures.append(f"{key}: rate {value} is outside the unit interval")

        if reg.is_saturated(task_id, metric_id, stage_id):
            optimum = 1.0 if spec.direction == "higher" else 0.0
            if entry.bound != bl.Bound(bl.BoundKind.EXACT, optimum):
                failures.append(
                    f"{key}: the registry says saturated, the paper published {value}"
                )

    return failures
```

Register it by appending to the import block at the foot of `tools/checks/__init__.py`:

```python
from tools.checks import baseline as _baseline  # noqa: E402,F401
from tools.checks import registry_csv as _registry_csv  # noqa: E402,F401
```

- [ ] **Step 4: Run the tests and the validator**

Run: `uv run pytest tests/test_baseline_check.py -v && uv run eda-validate`
Expected: 7 passed; `validate: 2 checks, 0 failures`, exit 0

- [ ] **Step 5: Commit**

```bash
git add tools/checks/baseline.py tools/checks/__init__.py tests/test_baseline_check.py
git commit -m "feat(validate): check baseline.json against the CSV and the registry"
```

---

### Task 6: Mutation regressions

The gate on the phase.
Each mutation is a mistake that would ship believable numbers, and each must make `check()` return a message naming the actual problem, not just a generic drift complaint.

**Files:**
- Test: `tests/test_baseline_check.py`

**Interfaces:**
- Consumes: `tools.baseline`, `tools.checks.baseline`.
- Produces: nothing.

- [ ] **Step 1: Write the tests**

Add `json`, `shutil`, `Callable`/`Iterator` from `collections.abc`, `Path` from `pathlib`, `Any` from `typing` and `pytest` to the import block at the **top** of `tests/test_baseline_check.py`, then append:

```python
@pytest.fixture
def mutable_baseline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    dest = tmp_path / "baseline.json"
    shutil.copyfile(bl.BASELINE_PATH, dest)
    monkeypatch.setattr(bl, "BASELINE_PATH", dest)
    bl.baselines.cache_clear()
    yield dest
    bl.baselines.cache_clear()


def _rewrite(path: Path, mutate: Callable[[list[dict[str, Any]]], None]) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    mutate(payload["cells"])
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    bl.baselines.cache_clear()


def test_a_rate_stored_in_display_units_is_caught(mutable_baseline: Path) -> None:
    """The inversion this whole phase exists to prevent. It raises nothing and
    every TPR and TNR cell silently renders beats_baseline."""

    def mutate(cells: list[dict[str, Any]]) -> None:
        for cell in cells:
            spec = reg.metric(cell["metric"])
            if spec.percent and spec.direction == "higher":
                assert cell["bound"]["value"] is not None
                cell["bound"]["value"] *= 100

    _rewrite(mutable_baseline, mutate)
    messages = check_mod.check()
    assert any("outside the unit interval" in m for m in messages)


def test_a_sentinel_demoted_to_an_exact_value_is_caught(
    mutable_baseline: Path,
) -> None:
    """Inventing the number the paper thresholded away."""

    def mutate(cells: list[dict[str, Any]]) -> None:
        for cell in cells:
            if cell["bound"]["kind"] == "greater_than":
                cell["bound"]["kind"] = "exact"

    _rewrite(mutable_baseline, mutate)
    messages = check_mod.check()
    assert any("published as a sentinel" in m for m in messages)


def test_a_degenerate_cell_stored_as_zero_is_caught(mutable_baseline: Path) -> None:
    """0/0 is not 0. Storing it as 0 hands every submission an automatic win on
    those cells."""

    def mutate(cells: list[dict[str, Any]]) -> None:
        for cell in cells:
            if cell["baseline_state"] == bl.DEGENERATE:
                cell["bound"] = {"kind": "exact", "value": 0.0}

    _rewrite(mutable_baseline, mutate)
    messages = check_mod.check()
    assert any("absent bound" in m for m in messages)


def test_a_void_cell_present_in_the_file_is_caught(mutable_baseline: Path) -> None:
    """A void cell does not exist. Reinstating it turns a structural hole into a
    rankable cell with a fabricated baseline."""

    def mutate(cells: list[dict[str, Any]]) -> None:
        cells.append(
            {
                "task": "total_wirelength_prediction",
                "metric": "mae",
                "pdk": "ng45",
                "stage": "floorplan",
                "baseline_state": bl.PUBLISHED,
                "bound": {"kind": "exact", "value": 0.0},
                "source": bl.PAPER,
                "src_line": 20,
            }
        )

    _rewrite(mutable_baseline, mutate)
    messages = check_mod.check()
    assert any("not live" in m for m in messages)


def test_a_missing_live_cell_is_caught(mutable_baseline: Path) -> None:
    def mutate(cells: list[dict[str, Any]]) -> None:
        del cells[0]

    _rewrite(mutable_baseline, mutate)
    messages = check_mod.check()
    assert any("missing from baseline.json" in m for m in messages)


def test_a_hand_edited_value_is_caught(mutable_baseline: Path) -> None:
    """data/baseline.json is generated. Typing into it must not survive."""

    def mutate(cells: list[dict[str, Any]]) -> None:
        for cell in cells:
            if cell["bound"]["kind"] == "exact":
                cell["bound"]["value"] = 0.5
                return

    _rewrite(mutable_baseline, mutate)
    messages = check_mod.check()
    assert any("does not match the CSV" in m for m in messages)
```

- [ ] **Step 2: Run and confirm every mutation is caught**

Run: `uv run pytest tests/test_baseline_check.py -v`
Expected: 13 passed. A failure here means that rule has no verification.

- [ ] **Step 3: Run the full gate**

Run: `make check`
Expected: lint clean, mypy clean, `validate: 2 checks, 0 failures`, all tests pass, build skipped for Phase 3.

- [ ] **Step 4: Commit and open the PR**

```bash
git add tests/test_baseline_check.py
git commit -m "test(baseline): pin the six mutations that would ship believable numbers"
git push -u origin phase-2/baseline
gh pr create --title "Phase 2: baseline" --body "Generates data/baseline.json from docs/sources/table8_baseline.csv by joining on table8_label. Percent metrics are divided by 100 on read; published sentinels become one-sided Bounds rather than invented values; the 40 void cells are absent and the 24 degenerate cells carry an absent bound. Adds a baseline check to make validate."
```

---

## Phase gate

Every item must pass before Phase 3 starts.

```bash
make check
```

- [ ] `data/baseline.json` carries exactly 880 entries, and its key set equals `reg.live_cells()` both directions
- [ ] the partition asserts: 856 published, 24 degenerate, 40 void absent from the file
- [ ] every entry carries `"source": "paper"`; no baseline is synthetic
- [ ] percent metrics are stored as fractions: `12.43 %` round-trips to `0.1243`, not `12.43` and not `1243.0`
- [ ] `tpr`/`tnr` all land in `[0, 1]`; 80 cells, none outside
- [ ] **no** ceiling guard exists on the MAPE family; 33 published cells legitimately exceed 1.0 stored
- [ ] 20 `greater_than` bounds, every one on a lower-is-better metric; 12 `less_than`, every one on a higher-is-better metric
- [ ] no sentinel is stored as an exact value, and no plain value is stored as a bound
- [ ] all 24 degenerate cells carry `Bound("absent", None)` and `baseline_state: "degenerate"`
- [ ] all 120 saturated cells are published at their optimum, checked against the registry's stage rule
- [ ] the committed file is byte-identical to a fresh `make baseline`
- [ ] the emitted JSON carries no float artifacts
- [ ] no count literal appears anywhere in `tools/`, docstrings included
- [ ] `eda-validate` reports `2 checks, 0 failures`
- [ ] all six mutations are caught

## Review prompt

```
Use the data-integrity subagent to review tools/baseline.py, tools/checks/baseline.py
and data/baseline.json against docs/DATA_CONTRACT.md and this plan.

Spot-check ten randomly chosen cells across different tasks, metrics, stages and
PDKs against docs/sources/table8_baseline.csv, and confirm each stored value is
that number with the documented transformations applied and nothing else. At
least three must be percent metrics and at least two must be sentinels.

Then verify, independently of the test suite:
- the divide-by-100 is applied to exactly the five percent metrics and to no
  others, exactly once, and only on the CSV read path
- neither sentinel form is stored as a value with a display override, and neither
  threshold was reconstructed into an invented number
- the 40 void cells are absent from the file rather than null, and the 24
  degenerate cells are present with a null value
- no range guard exists on the MAPE family, and the tpr/tnr guard selects those
  two metrics by registry attribute rather than by name

Finally apply each of these mutations to a COPY of the repo and confirm make check
fails: multiply every tpr/tnr value by 100; change one greater_than bound to
exact; set a degenerate cell's bound to exact 0.0; add a total_wirelength
floorplan cell; delete one entry. Report any mutation that does NOT fail.

Report only correctness gaps and unguarded values. Do not report style
preferences.
```
