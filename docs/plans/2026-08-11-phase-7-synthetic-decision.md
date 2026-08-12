# Phase 7 - Synthetic Fill Decision Implementation Plan

> **For agentic workers:** Implement this plan task-by-task - either dispatch a fresh subagent per task (recommended) or execute inline with review checkpoints. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** rule on whether the leaderboard launches with generated fill for the 212
combos that have no data, record the ruling where every later phase will read it,
and build `tools/synth.py` only if the ruling is yes.

**Architecture:** Task 0 is a written evaluation with no code.
It produces a ruling recorded in `docs/DATA_CONTRACT.md`, and that ruling decides
whether Tasks 1 to 7 run at all.
If they do, `tools/synth.py` is a pure generator seeded from one integer, anchored
on the real published baseline for every cell it fills, emitting shards through
Phase 4's own `tools/ingest.py` record types so synthetic and real records cannot
drift apart in shape.
A manifest of SHA-256 hashes turns "deterministic" into something `make validate`
checks rather than something the docstring claims.

**Tech stack:** Python 3.11+, `uv`, `pytest`, `mypy --strict`, `ruff`, stdlib only
(`hashlib`, `random`, `json`, `math`).
No new dependency.

## Global constraints

Copied from `PLAN.md`; every task's requirements implicitly include these.

- Python **3.11+**, type hints on all public functions, `ruff` and `mypy` clean.
- **Registries are the only source of vocabulary.** Circuit names come from
  `reg.circuits()`, never a literal list. Same for tasks, metrics, stages, PDKs.
- **Counts are derived, never literal.** 46, 232, 880, 856, 120, 40, 24, 212, 688
  and 188 are computed in `tools/`; only `tests/` may state them as expected
  values.
- **Percent metrics** (`mape`, `mape_p95`, `mape_top5`, `tpr`, `tnr`) are
  generated as **fractions in `[0, 1]`**, never as display percents. The `×100`
  happens once, at the display boundary, and synth is nowhere near it.
- **Every record carries an explicit `source`.** `make validate` fails without
  one. Synthetic records carry `"source": "synthetic"`.
- Never commit files over 1 MB. `data/` is generated and committed by the
  generator, never edited by hand.
- Conventional commits. Branch `phase-7/synthetic-decision`. Never push to `main`.
- **Never use an em dash** in prose, code comments or generated copy.

## Why this phase is shaped differently

Every other phase in `PLAN.md` builds something.
This one first asks whether the thing should exist, because the pre-reset build
committed to synthetic fill up front and planned a launch that was 91% generated.
The audit called that out, and the reset moved the commitment to here, after a
real matrix has been live for several phases.

The evidence that was missing then exists now.
`PLAN.md` Phase 3 shipped an 880-cell grid against 856 real published baselines
before ingest existed, and Phase 4 lit 20 real combos on it.
So the question "does a mostly empty grid read as honest or as broken" is
answerable by looking, which is exactly why it was deferred to this point.

**If the ruling is no synthetic, Tasks 1 to 7 are skipped and the phase closes on
Task 0.** That is a complete phase, not an abandoned one.

## File structure

| File | Responsibility | Built under |
|---|---|---|
| `docs/DATA_CONTRACT.md` | the ruling, recorded under Source rules | both rulings |
| `CLAUDE.md` | the Synthetic data section, updated to state the ruling | both rulings |
| `PLAN.md` | Phase 7 marked resolved, open decision 6 updated | both rulings |
| `Makefile` | the `synth` target: either the ruling, or the real command | both rulings |
| `tools/synth.py` | the generator: draws, anchoring, spread, emission, CLI | ruling B only |
| `tools/checks/synthetic.py` | `@register("synthetic")`, the validate-time invariants | ruling B only |
| `data/cells/**` | 188 generated shards, committed by the generator | ruling B only |
| `data/synthetic_manifest.json` | seed, counts, per-shard SHA-256 | ruling B only |
| `build.py` | `has_synthetic` on the cell context, cells-won filter | ruling B only |
| `templates/pages/matrix.html` | the marker glyph and its legend entry | ruling B only |
| `templates/pages/cell.html` | the per-row marker and the ranking-table notice | ruling B only |
| `static/css/base.css` | `.synthetic` marker styling, one rule block | ruling B only |
| `tests/test_synth.py` | draws, anchoring, direction, sentinels, degenerate | ruling B only |
| `tests/test_synth_grid.py` | placement over the full grid, win rate, monotonicity | ruling B only |
| `tests/test_synth_determinism.py` | byte identity, order independence, manifest | ruling B only |
| `tests/test_synth_marker.py` | the marker renders, cells-won excludes synthetic | ruling B only |

---

### Task 0: The decision

**No code.** This task gathers evidence from the live site, weighs three options,
and writes a ruling into the contract.
It is the only task that always runs.

**Files:**
- Modify: `docs/DATA_CONTRACT.md`, `CLAUDE.md`, `PLAN.md`, `Makefile`

**Interfaces:**
- Consumes: the deployed GitHub Pages site, `data/cells/` as Phase 4 left it,
  `tools/registry.py`.
- Produces: a ruling recorded under `## Source rules` in
  `docs/DATA_CONTRACT.md`, which Tasks 1 to 7 read as their gate.

- [ ] **Step 1: Measure what the grid actually shows today**

Run this against the current checkout, after `make ingest && make build`:

```bash
uv run python - <<'PY'
import json
from pathlib import Path

from tools import registry as reg

live = reg.live_cells()
sat = {c for c in live if reg.is_saturated(c[0], c[1], c[3])}
deg = {c for c in live if reg.is_degenerate(c[0], c[1], c[3])}
rankable = [c for c in live if c not in sat and c not in deg]

have: set[tuple[str, str, str, str]] = set()
combos_with_data: set[tuple[str, str, str]] = set()
for shard in sorted(Path("data/cells").rglob("*.json")):
    rec = json.loads(shard.read_text(encoding="utf-8"))
    combos_with_data.add((rec["task"], rec["pdk"], rec["stage"]))
    for entry in rec["entries"]:
        for metric_id in entry["metrics"]:
            have.add((rec["task"], metric_id, rec["pdk"], rec["stage"]))

filled = [c for c in rankable if c in have]
print(f"live cells      {len(live)}")
print(f"  saturated     {len(sat)}")
print(f"  degenerate    {len(deg)}")
print(f"  rankable      {len(rankable)}")
print(f"    with data   {len(filled)}")
print(f"    no_entry    {len(rankable) - len(filled)}")
print(f"live combos     {len(reg.live_combos())}")
print(f"  with data     {len(combos_with_data)}")
print(f"  without data  {len(reg.live_combos()) - len(combos_with_data)}")
PY
```

Expected, and worth checking rather than assuming:

```
live cells      880
  saturated     120
  degenerate     24
  rankable      736
    with data    48
    no_entry    688
live combos     232
  with data      20
  without data  212
```

The 48 is `total_area_prediction` across 3 metrics and 4 PDKs at the four stages
that are not `global_route`; its 12 `global_route` cells are saturated, not empty.
So the honest headline is **48 of 736 rankable cells carry a real result**, and
synthetic fill would generate the other 688 plus 24 degenerate cells.
That is 91.4% of live combos and 93.5% of rankable cells.

- [ ] **Step 2: Look at the live page, at every stage**

Open the deployed URL, not `dist/` on localhost.
The question is how a stranger reads it, and a local build invites you to read it
as the person who made it.

For each of the five stage pills, record an answer:

1. Does a `no_entry` cell read as "nobody has submitted this yet" or as "this
   page is broken"? If a reader cannot tell an empty cell from a failed render,
   that is a Phase 3 defect and it is cheaper to fix the empty state than to
   paper over it with 688 generated numbers.
2. Is there an affordance in the empty state? A `no_entry` cell that links to
   `/submit/` turns the emptiness into a call to action. If Phase 8 has not
   landed, note it as a dependency rather than a blocker.
3. At `global_route`, do the 120 saturated cells and the 24 degenerate cells read
   as three visually distinct cases alongside `no_entry`, or do they collapse
   into one grey wash? Synthetic fill does not fix this and would hide it.
4. Does the page look **compelling enough to cite**? Ask it as: if this URL
   appeared in a related-work section, would you follow the link twice?

- [ ] **Step 3: Measure the page budget headroom**

```bash
du -sh dist/
find dist -name '*.html' -size +80k -printf '%s %p\n' | sort -rn | head
find dist -name '*.json' -printf '%s %p\n' | sort -rn | head -5
```

The target is roughly 20 MB for `dist/` and 88 KB per page.
Estimate the synthetic delta before deciding, not after: 188 new shards, each
carrying up to 5 entries, each entry holding up to 7 metric values plus 18
per-circuit values per metric.
That is on the order of 10 KB per shard and about 2 MB total, which fits.
Record the measured numbers anyway, because "it fits" is the kind of claim that
is only true until it is checked.

- [ ] **Step 4: Get the two human answers this decision depends on**

Neither is a code question and neither should be guessed.

- **Savidis, open decision 6 in `PLAN.md`:** does launch wait for a real training
  run? The current models are undertrained at 50 gradient steps with a training
  R² median of 0.020, and `docs/DATA_CONTRACT.md` records a pooled baseline R² of
  0.9892 against a per-circuit median of -26.86 with 0 of 18 circuits positive.
  Option C is entirely a function of this answer.
- **Three readers on the live URL:** Savidis, Pratik, and one person who has not
  seen the project. Ask each the same two questions, and write down the verbatim
  answer: *what is this page claiming?* and *would you cite it today?*

- [ ] **Step 5: Weigh the three options**

| Option | What launches | Consequence |
|---|---|---|
| **A. No synthetic** *(recommended)* | 48 real rankable cells, 688 `no_entry`, 120 saturated, 24 degenerate, all against 856 real published baselines | Honest on day one. A mostly-`no_entry` grid is exactly what a new leaderboard looks like, and every number on the page traces to a line in an `eval.log` or a cell of Table 8. The cost is that 688 cells look empty and several UI paths stay unexercised until real submissions arrive. |
| **B. Synthetic, marked** | 736 rankable cells populated, every ranking, filter, plot and export path exercised at full scale | Every UI path is exercised before real data lands, and the empty-state question becomes moot. The cost is that a leaderboard other labs are meant to cite launches ~91% generated, and a marker on a cell is a weaker signal than most readers give it credit for. Screenshots, citations and quotes all strip the marker. |
| **C. Wait for real data** | nothing, until the lab's training run | The grid fills with real results and the question dissolves. The cost is that launch slips to a date nobody controls, and the current models are undertrained at 50 gradient steps with a training R² median of 0.020, so the run has to happen before this is worth waiting for. |

**Recommendation: option A.** The audit's judgement was that a grid honestly
showing 20 real combos is a stronger artifact for a citable leaderboard than one
showing 232 combos of which 212 are invented, and nothing measured in Steps 1 to 3
has changed that.
The strongest argument for B is exercising the UI, and that argument is weaker
than it looks: Phase 3 already exercised the full 880-cell grid, and Phase 5
already rendered 232 cell pages, both against real baselines.
What synthetic adds is exercise of the **ranking** paths specifically, which is a
narrower gap than "every UI path" suggests and is also reachable by fixtures in
`tests/` without shipping 688 generated cells to the public site.

Overrule this only on evidence from Step 2, and write the evidence into the ruling.

- [ ] **Step 6: Record the ruling in the contract**

Append to `docs/DATA_CONTRACT.md`, immediately after the `## Source rules` table:

```markdown
### Ruling on synthetic fill

**Decided <DATE>, on evidence from the live matrix rather than in advance.**

At the time of the ruling the grid showed 48 of 736 rankable cells carrying a real
result, 120 saturated, 24 degenerate and 688 `no_entry`, against 856 real published
baselines. 20 of 232 live combos had data.

**Ruling: <A: no synthetic fill ships | B: synthetic fill ships, marked>.**

Reasoning: <one paragraph, citing what Step 2 found on the live page>.

Under ruling A the `synthetic` source value stays defined here and in
`schema/submission.schema.json`, because a later ruling may revive it, but no
record anywhere under `data/` carries it and `make synth` declines rather than
generating. `tools/synth.py` does not exist.

Under ruling B every synthetic record carries `"source": "synthetic"`, renders with
a visible marker, is excluded from every cells-won tally, and never appears in a
void or saturated cell. Generation is seeded and byte-reproducible, checked by
`data/synthetic_manifest.json`.
```

Fill in the placeholders in angle brackets.
Leaving one in place is a failed step, not a stylistic lapse: the whole value of
this task is that a later reader finds the decision and its reasoning together.

- [ ] **Step 7: Propagate the ruling to the three other documents**

`CLAUDE.md`, the `## Synthetic data` section, currently reads "Deferred."
Replace the first sentence with the ruling and a pointer, keeping the rest of the
section intact under ruling B and deleting it under ruling A.

`PLAN.md`, Phase 7: replace the options table with a one-line record of the ruling
and a link to the contract section, and update open decision 6 in the
`## Open decisions` table with Savidis's answer from Step 4.

`Makefile`, the `synth` target. Under ruling A:

```make
synth:
	@echo "synth: declined. Synthetic fill was ruled out; see docs/DATA_CONTRACT.md"; exit 1
```

Under ruling B, drop the guard and run the generator:

```make
synth:
	uv run python -m tools.synth
```

- [ ] **Step 8: Verify the gate still passes and commit**

Run: `make check`
Expected: unchanged from Phase 6, since no code moved. Under ruling A, `make synth`
now exits 1 with the decline message, which is correct and is not part of `check`.

```bash
git add docs/DATA_CONTRACT.md CLAUDE.md PLAN.md Makefile
git commit -m "docs(synth): rule on synthetic fill with evidence from the live matrix"
```

**Under ruling A, stop here.** Push the branch, open the PR, and skip to
`## Phase gate`.

---

> **Everything below is conditional on ruling B.**
> If Task 0 ruled no synthetic, none of it is built.

---

### Task 1: The seam to Phase 4, and the seeded RNG

The smallest slice that can fail for the right reason: one record, produced
through Phase 4's own types, with a key-derived RNG whose output does not depend
on the order anything is generated in.

**Files:**
- Create: `tools/synth.py`
- Test: `tests/test_synth.py`

**Interfaces:**
- Consumes: `tools.registry` as `reg`; `tools.ingest.Entry`, `tools.ingest.Shard`
  and `tools.ingest.shard_path(task_id, pdk_id, stage_id) -> Path`;
  `tools.baseline.lookup(task_id, metric_id, pdk_id, stage_id)` and
  `tools.baseline.BoundKind`.
- Produces: `synth.SEED: int`, `synth._rng(seed: int, *key: str) -> random.Random`,
  `synth._q(value: float) -> float`,
  `synth.combo_record(task_id: str, pdk_id: str, stage_id: str, seed: int = SEED) -> Shard | None`.

**Two seams, and only two.** `_anchor()` is the only function in this module that
touches `data/baseline.json`, and the `Shard`/`Entry` import is the only place
that knows the record shape.
If Phase 2 or Phase 4 named things differently, those are the two places to adjust
and there are no others.
If Phase 4 emitted plain dicts rather than dataclasses, add `Entry` and `Shard`
dataclasses to `tools/ingest.py` and make `ingest` construct them first, with the
parity test in Step 2 as the gate on that refactor.
Do not hand-roll a parallel record shape in `synth`; two shapes that must stay
identical will not stay identical.

- [ ] **Step 1: Write the failing test**

Create `tests/test_synth.py`:

```python
"""Synthetic fill: draws, anchoring and record shape.

Expected counts live here, in tests. They must never appear in tools/.
"""

from __future__ import annotations

import json
from pathlib import Path

from tools import ingest, synth


def test_the_rng_is_keyed_not_streamed() -> None:
    """Order independence is what makes the output byte-identical regardless of
    which cells are generated first, or in parallel."""
    a = synth._rng(synth.SEED, "total_area_prediction", "mae", "ng45", "floorplan")
    b = synth._rng(synth.SEED, "total_power_prediction", "r2", "asap7", "cts")
    c = synth._rng(synth.SEED, "total_area_prediction", "mae", "ng45", "floorplan")
    _ = b.random()
    assert a.random() == c.random()


def test_different_keys_give_different_draws() -> None:
    a = synth._rng(synth.SEED, "total_area_prediction", "mae", "ng45", "floorplan")
    b = synth._rng(synth.SEED, "total_area_prediction", "mae", "sky130", "floorplan")
    assert a.random() != b.random()


def test_the_quantizer_is_stable_across_repr() -> None:
    assert synth._q(0.1 + 0.2) == synth._q(0.3)
    assert json.dumps(synth._q(1781.9696000000001)) == json.dumps(1781.9696)


def test_synthetic_record_matches_the_ingest_record_shape() -> None:
    """Parity with the real shards, checked against a real one rather than
    against synth's own idea of the shape."""
    real_path = ingest.shard_path("total_area_prediction", "ng45", "floorplan")
    real = json.loads(Path(real_path).read_text(encoding="utf-8"))
    fake = synth.combo_record("total_power_prediction", "ng45", "floorplan")
    assert fake is not None
    emitted = json.loads(json.dumps(fake, default=lambda o: o.__dict__))
    assert set(emitted) == set(real)
    assert set(emitted["entries"][0]) == set(real["entries"][0])


def test_every_synthetic_entry_declares_its_source() -> None:
    fake = synth.combo_record("total_power_prediction", "ng45", "floorplan")
    assert fake is not None
    assert [e.source for e in fake.entries] == ["synthetic"] * len(fake.entries)
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `uv run pytest tests/test_synth.py -v`
Expected: FAIL, `ImportError: cannot import name 'synth' from 'tools'`

- [ ] **Step 3: Write the module skeleton**

Create `tools/synth.py`:

```python
"""Deterministic synthetic fill for combos with no real data.

Every value here is generated. Nothing in this module may be presented as a
measurement: each record carries source="synthetic", the renderer marks it, and
the cells-won tally ignores it.

The generator is anchored on the real published baseline for each cell, so PDK
magnitudes and stage difficulty come from the paper rather than from a constant
table. Randomness is keyed on the cell identity, never streamed, so output does
not depend on generation order.
"""

from __future__ import annotations

import hashlib
import random

from tools import registry as reg
from tools.baseline import lookup
from tools.ingest import Entry, Shard, shard_path

SEED = 20260811
"""Change this and every generated number changes. It is recorded in the
manifest so a regenerated tree can be told from a hand-edited one."""

WIN_RATE = 0.60
"""Intended share of rankable cells where at least one entry beats the baseline.
The monotonicity repair in `_repair` can only add wins, so the realized rate runs
slightly above this. It is measured in tests/test_synth_grid.py, not assumed."""

WIN_RATIO = (0.55, 0.95)
LOSS_RATIO = (1.05, 1.80)
MODELS_PER_COMBO = (2, 5)
ENTRY_SPREAD = (0.05, 0.60)
CIRCUIT_JITTER = (0.75, 1.30)
STAGE_DECAY = 0.90
DEGENERATE_DECAY = 0.25

FAMILIES = ("mlp", "gnn", "cnn", "automl")
"""Labels for generated entries. NOT registry vocabulary: these name architecture
families, which the registries deliberately do not cover. Every display name
carries the word "synthetic" so no reader mistakes one for a submission."""


def _rng(seed: int, *key: str) -> random.Random:
    """A generator keyed on cell identity rather than drawn from a stream.

    Streamed randomness makes output depend on iteration order, which silently
    breaks byte-reproducibility the first time a loop is reordered or split.
    """
    material = "|".join((str(seed), *key)).encode("utf-8")
    digest = hashlib.blake2b(material, digest_size=16).digest()
    return random.Random(int.from_bytes(digest, "big"))


def _q(value: float) -> float:
    """Quantize to 10 significant digits so two runs serialize identically."""
    return float(f"{value:.10g}")
```

- [ ] **Step 4: Implement `combo_record` against the real shape**

Add to `tools/synth.py` a `combo_record` that returns a `Shard` for one
`(task, pdk, stage)`, or `None` when the combo has no cell worth filling.
It draws its model count from `_rng(seed, task_id, pdk_id, stage_id)`, builds one
`Entry` per model, and leaves the metric values to Task 2, which fills them in.
For this task a metric value of `0.0` is acceptable in the body, because Task 2's
tests replace it before anything is emitted; what is being pinned here is the
shape and the source field.

Skip any cell where `reg.is_void(task_id, stage_id)` or
`reg.is_saturated(task_id, metric_id, stage_id)`, and return `None` when that
leaves the shard with no metrics at all.
Void is structural: `reg.live_combos()` already excludes the 8 void combos, so
the check is a second line of defence rather than the primary one, and it costs a
single call.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_synth.py -v`
Expected: 5 passed

- [ ] **Step 6: Verify lint and types**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy`
Expected: all clean

- [ ] **Step 7: Commit**

```bash
git add tools/synth.py tests/test_synth.py
git commit -m "feat(synth): add the keyed rng and the ingest record seam"
```

---

### Task 2: The value model

Where plausibility is either earned or faked.
Every value is a function of the real published baseline for the same cell, so
per-PDK magnitude and per-stage difficulty are inherited from the paper instead of
being invented.

**Files:**
- Modify: `tools/synth.py`
- Test: `tests/test_synth.py`

**Interfaces:**
- Consumes: `tools.baseline.lookup`, `tools.baseline.BoundKind`, `reg.metric`,
  `reg.stages`.
- Produces: `synth._anchor(task_id, metric_id, pdk_id, stage_id) -> float | None`,
  `synth._published_value(task_id, metric_id, pdk_id, stage_id) -> float | None`,
  `synth._cell_ratio(task_id, metric_id, pdk_id, stage_id, seed) -> float`,
  `synth._best_value(anchor: float, metric: reg.Metric, ratio: float) -> float`,
  `synth._repair(values: list[float], direction: str) -> list[float]`,
  `synth.cell_target(task_id, metric_id, pdk_id, stage_id, seed) -> float`.

**The model, stated once.**

Every metric has a distance from perfect.
For a lower-better metric that distance is the value itself; for a higher-better
metric it is `1 - value`, which handles R² below zero without a special case
(`r2 = -5` is a distance of 6 from perfect).
The synthetic leader sits at `ratio` times the baseline's distance:

```
gap        = baseline            if direction == "lower"
             1 - baseline        if direction == "higher"
best       = gap * ratio         if direction == "lower"
             1 - gap * ratio     if direction == "higher"
```

`ratio < 1` is a win, `ratio > 1` is a loss, in both directions, with no
inversion to get backwards.
`ratio` is drawn per cell against `WIN_RATE`, so the intent is exact before the
monotonicity repair runs.

**Three cases the arithmetic has to handle.**

- **Rate metrics.** `tpr` and `tnr` are true rates and cannot leave `[0, 1]`. A
  loss ratio of 1.8 against a baseline of 0.0839 computes to -0.649, so rates are
  clamped to `[0.0, 1.0]`. Clamping at zero is still a loss, so no intent is lost.
  `mape` is **not** clamped: it is unbounded above, its ceiling is the
  `> 10000 %` sentinel at `100.0` as a fraction, and 48 of 244 published MAPE
  cells legitimately exceed 150 %. Adding a `[0, 1.5]` guard there would reject
  all 48.
- **Sentinel baselines, 32 cells.** The underlying number does not exist; the
  paper thresholded it away, so Phase 2 stores a `Bound`. Anchor on the threshold:
  `100.0` for the `greater_than` MAPE bound, `-1.0` for the `less_than` R² bound.
  The leader is forced onto the **defined** side of the threshold, so the cell's
  state is decidable. At least one trailing entry is placed on the undecidable
  side, deliberately, because that is the `no_comparison` render path and it
  exists on 32 real cells whether or not synth exercises it.
- **Degenerate baselines, 24 cells.** `lookup` returns `baseline_value: null` with
  `baseline_state: "degenerate"`, because the baseline is a 0/0 that was never
  measured. There is nothing to anchor on, so anchor on the same
  `(task, metric, pdk)` at the latest earlier stage that has a published value,
  scaled by `DEGENERATE_DECAY`. The entry is generated; the comparison is not.
  Phase 4's ranking already refuses to score against a null baseline, and the test
  below asserts that rather than trusting it.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_synth.py`:

```python
import pytest

from tools import ranking
from tools import registry as reg


def test_anchor_is_the_published_baseline() -> None:
    from tools.baseline import lookup

    published = lookup("total_area_prediction", "mae", "ng45", "floorplan")
    assert synth._anchor("total_area_prediction", "mae", "ng45", "floorplan") == (
        published.value
    )


def test_pdk_magnitude_is_inherited_from_the_baseline_not_invented() -> None:
    """SKY130 total_area MAE is an order of magnitude above NG45 in Table 8. The
    synthetic values must carry that, and they do because they are anchored on it
    rather than on a per-PDK constant."""
    ng = synth.cell_target("total_area_prediction", "mae", "ng45", "floorplan")
    sky = synth.cell_target("total_area_prediction", "mae", "sky130", "floorplan")
    assert sky > ng * 3


def test_a_win_ratio_lands_on_the_beating_side_in_both_directions() -> None:
    lower = synth._best_value(100.0, reg.metric("mae"), 0.8)
    assert lower < 100.0
    higher = synth._best_value(0.5, reg.metric("r2"), 0.8)
    assert higher > 0.5


def test_a_loss_ratio_lands_on_the_losing_side_in_both_directions() -> None:
    lower = synth._best_value(100.0, reg.metric("mae"), 1.4)
    assert lower > 100.0
    higher = synth._best_value(0.5, reg.metric("r2"), 1.4)
    assert higher < 0.5


def test_r2_below_minus_one_is_handled_without_a_special_case() -> None:
    """A distance of 6 from perfect, improved to 4.8, is -3.8. No inversion."""
    assert synth._best_value(-5.0, reg.metric("r2"), 0.8) == pytest.approx(-3.8)


def test_rate_metrics_are_clamped_into_the_unit_interval() -> None:
    for metric_id in ("tpr", "tnr"):
        value = synth._best_value(0.0839, reg.metric(metric_id), 1.8)
        assert 0.0 <= value <= 1.0


def test_mape_is_not_clamped() -> None:
    """48 of 244 published MAPE cells exceed 150 %. A range guard here is wrong."""
    assert synth._best_value(2.0, reg.metric("mape"), 1.8) > 1.5


def test_the_repair_makes_a_chain_monotone_and_is_idempotent() -> None:
    once = synth._repair([10.0, 14.0, 8.0, 9.0], "lower")
    assert once == [10.0, 10.0, 8.0, 8.0]
    assert synth._repair(once, "lower") == once
    assert synth._repair([0.2, 0.1, 0.5, 0.4], "higher") == [0.2, 0.2, 0.5, 0.5]


def test_a_sentinel_leader_lands_on_the_defined_side_of_the_bound() -> None:
    """R2 < -1 on cell_arc_delay at floorplan. A submission at -0.5 clearly wins;
    one at -3 is undecidable. The leader is never left undecidable."""
    from tools.baseline import BoundKind, lookup

    published = lookup("cell_arc_delay_prediction", "r2", "ng45", "floorplan")
    assert published.bound.kind is BoundKind.LESS_THAN
    target = synth.cell_target("cell_arc_delay_prediction", "r2", "ng45", "floorplan")
    assert target > -1.0


def test_a_degenerate_cell_gets_an_entry_but_never_a_win() -> None:
    from tools.baseline import Bound, BoundKind, lookup

    task_id, metric_id, pdk_id, stage_id = (
        "worst_slack_prediction",
        "mpe",
        "ng45",
        "global_route",
    )
    assert reg.is_degenerate(task_id, metric_id, stage_id)
    record = synth.combo_record(task_id, pdk_id, stage_id)
    assert record is not None
    assert any(metric_id in e.metrics for e in record.entries)
    # cell_state takes (task, metric, STAGE, baseline, entries). It does not take
    # the pdk, and it takes Bounds rather than Entries, so a cell key cannot be
    # splatted into it.
    state = ranking.cell_state(
        task_id,
        metric_id,
        stage_id,
        lookup(task_id, metric_id, pdk_id, stage_id).bound,
        tuple(
            Bound(BoundKind.EXACT, e.metrics[metric_id].macro)
            for e in record.entries
            if metric_id in e.metrics
        ),
    )
    assert state is not ranking.CellState.BEATS_BASELINE
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_synth.py -v`
Expected: FAIL, `AttributeError: module 'tools.synth' has no attribute '_anchor'`

- [ ] **Step 3: Implement the anchor**

Append to `tools/synth.py`:

```python
def _anchor(task_id: str, metric_id: str, pdk_id: str, stage_id: str) -> float | None:
    """The published baseline this cell's synthetic values are scaled against.

    THE ONLY FUNCTION IN THIS MODULE THAT READS data/baseline.json. If Phase 2
    renamed its loader or its Bound fields, this is the single place to adjust.

    A sentinel baseline resolves to its threshold, because that is the only
    number the paper published. A degenerate baseline has no value at all, so it
    falls back to the latest earlier stage that does.
    """
    value = _published_value(task_id, metric_id, pdk_id, stage_id)
    if value is not None:
        return value

    order = {s.id: s.order for s in reg.stages()}
    earlier = [s for s in reg.stages() if s.order < order[stage_id]]
    for previous in reversed(earlier):
        fallback = _published_value(task_id, metric_id, pdk_id, previous.id)
        if fallback is not None:
            return fallback * DEGENERATE_DECAY
    return None


def _published_value(
    task_id: str, metric_id: str, pdk_id: str, stage_id: str
) -> float | None:
    """The cell's published number, or None if it has none.

    Two distinct ways a cell can have no number, and both must land on None
    rather than raising: a void cell is absent from data/baseline.json entirely,
    so `lookup` raises KeyError, and a degenerate cell is present but carries an
    ABSENT bound whose value is None. A sentinel resolves to its threshold,
    because that is the only number the paper published.
    """
    try:
        published = lookup(task_id, metric_id, pdk_id, stage_id)
    except KeyError:
        return None
    return None if published.bound.value is None else float(published.bound.value)
```

- [ ] **Step 4: Implement the draws, the gap arithmetic and the repair**

Append `_cell_ratio`, `_best_value`, `_repair` and `cell_target` as specified in
the Interfaces block, following the model stated above.

`_cell_ratio` draws `rng.random() < WIN_RATE` and then a uniform from
`WIN_RATIO` or `LOSS_RATIO`. Draw the coin and the magnitude from the same keyed
generator, in that order, so the sequence is fixed.

`_repair` walks the chain in stage order and takes a running minimum for a
lower-better direction, a running maximum for higher-better.
It can only turn a loss into a win, never the reverse, which is why `WIN_RATE` is
documented as an intent and measured as a band in Task 5.

`cell_target` composes them: anchor, ratio, best value, then the chain repair
across that `(task, metric, pdk)`'s live non-saturated stages.
On a sentinel cell, clamp the result onto the defined side of the bound before
returning: strictly below `100.0` for a `greater_than` MAPE bound, strictly above
`-1.0` for a `less_than` R² bound.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_synth.py -v`
Expected: 15 passed

- [ ] **Step 6: Commit**

```bash
git add tools/synth.py tests/test_synth.py
git commit -m "feat(synth): anchor generated values on the published baseline"
```

---

### Task 3: Per-circuit spread, correlated with circuit size

The requirement is that per-circuit variation tracks circuit size, and the sharper
requirement underneath it is that the per-circuit values **aggregate back to the
cell value using the same estimator the contract mandates**: macro-mean for MAE
and MAPE, median for R².
Generating per-circuit numbers that do not reconstitute the headline number would
put a self-contradicting record in front of the aggregation logic.

**Files:**
- Modify: `tools/synth.py`
- Test: `tests/test_synth.py`

**Interfaces:**
- Consumes: `reg.circuits()`, `reg.metric`.
- Produces: `synth._size_factors() -> dict[str, float]`,
  `synth._per_circuit(value: float, metric: reg.Metric, rng: random.Random) -> dict[str, float]`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_synth.py`:

```python
def _spearman(xs: list[float], ys: list[float]) -> float:
    def ranks(values: list[float]) -> list[float]:
        order = sorted(range(len(values)), key=lambda i: values[i])
        out = [0.0] * len(values)
        for position, index in enumerate(order):
            out[index] = float(position)
        return out

    rx, ry = ranks(xs), ranks(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    dx = sum((a - mx) ** 2 for a in rx) ** 0.5
    dy = sum((b - my) ** 2 for b in ry) ** 0.5
    return num / (dx * dy)


def test_per_circuit_error_tracks_circuit_size() -> None:
    """ethernet has 10,544 registers and ss_pcm has 87. Circuit names and sizes
    come from reg.circuits(), never from a literal list here."""
    rng = synth._rng(synth.SEED, "size-test")
    values = synth._per_circuit(1000.0, reg.metric("mae"), rng)
    sizes = [float(c.registers) for c in reg.circuits()]
    errors = [values[c.id] for c in reg.circuits()]
    assert _spearman(sizes, errors) >= 0.6
    assert values["ethernet"] > values["ss_pcm"]


def test_per_circuit_values_macro_mean_back_to_the_cell_value() -> None:
    """The contract mandates macro-mean across the 18 circuits, never pooled. A
    synthetic record whose parts do not reconstitute its whole would feed the
    aggregation logic a contradiction."""
    rng = synth._rng(synth.SEED, "aggregate-test")
    values = synth._per_circuit(1000.0, reg.metric("mae"), rng)
    assert len(values) == 18
    macro_mean = sum(values.values()) / len(values)
    assert macro_mean == pytest.approx(1000.0, rel=1e-9)


def test_r2_per_circuit_values_take_the_median_not_the_mean() -> None:
    """One -335 outlier destroys a mean, which is why R2 aggregates by median."""
    import statistics

    rng = synth._rng(synth.SEED, "r2-test")
    values = synth._per_circuit(0.42, reg.metric("r2"), rng)
    assert statistics.median(values.values()) == pytest.approx(0.42, rel=1e-9)


def test_rate_metrics_stay_in_the_unit_interval_per_circuit() -> None:
    rng = synth._rng(synth.SEED, "rate-test")
    for metric_id in ("tpr", "tnr"):
        values = synth._per_circuit(0.93, reg.metric(metric_id), rng)
        assert all(0.0 <= v <= 1.0 for v in values.values())
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_synth.py -v`
Expected: FAIL, `AttributeError: module 'tools.synth' has no attribute '_per_circuit'`

- [ ] **Step 3: Implement**

Append to `tools/synth.py`:

```python
@cache
def _size_factors() -> dict[str, float]:
    """Per-circuit weights on log(registers), normalized to a mean of 1.

    Absolute error grows with design size, but not linearly: ethernet has 121x the
    registers of ss_pcm and nothing like 121x the error. log1p compresses that to
    roughly 2x, which is the shape the real per-circuit numbers show.
    """
    weights = {c.id: math.log1p(float(c.registers)) for c in reg.circuits()}
    mean = sum(weights.values()) / len(weights)
    return {circuit_id: w / mean for circuit_id, w in weights.items()}


def _per_circuit(
    value: float, metric: reg.Metric, rng: random.Random
) -> dict[str, float]:
    """Spread one cell value across the 18 circuits, size-correlated.

    The spread is renormalized so it aggregates back to `value` under the
    estimator the contract mandates for this metric: the macro-mean for
    everything except r2, which uses the median.
    """
    factors = _size_factors()
    raw = {
        circuit_id: factors[circuit_id] * rng.uniform(*CIRCUIT_JITTER)
        for circuit_id in sorted(factors)
    }

    if metric.id == "r2":
        centred = statistics.median(raw.values())
        spread = {k: value + (v - centred) for k, v in raw.items()}
    else:
        mean = sum(raw.values()) / len(raw)
        spread = {k: v * (value / mean) for k, v in raw.items()}

    if metric.percent and metric.direction == "higher":
        spread = {k: min(1.0, max(0.0, v)) for k, v in spread.items()}
    return {k: _q(v) for k, v in spread.items()}
```

Add `import math`, `import statistics` and `from functools import cache` to the
imports.
Iterating `sorted(factors)` rather than dict order is deliberate: it fixes the
sequence of `rng.uniform` draws so the spread does not depend on registry file
ordering.

Note that the rate clamp can move the median or mean slightly off the target on a
cell whose value is already near the ceiling.
That is correct behaviour, not a defect: a rate cannot exceed 1, and the
alternative is emitting an impossible number to preserve an aggregate identity.
The aggregation tests use a mid-range value for exactly this reason.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_synth.py -v`
Expected: 19 passed

- [ ] **Step 5: Commit**

```bash
git add tools/synth.py tests/test_synth.py
git commit -m "feat(synth): spread cell values across circuits by size"
```

---

### Task 4: Emission, the manifest and `make synth`

**Files:**
- Modify: `tools/synth.py`, `Makefile`
- Test: `tests/test_synth_grid.py`

**Interfaces:**
- Consumes: `reg.live_combos()`, `tools.ingest.shard_path`.
- Produces: `synth.generate(seed: int = SEED, out_dir: Path | None = None) -> dict[str, str]`
  returning the relative-path-to-SHA-256 manifest body,
  `synth.main(argv: list[str] | None = None) -> int`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_synth_grid.py`:

```python
"""Placement of synthetic records over the full grid.

The counts below are derived in the module under test and stated here as expected
values. 212 = 232 live combos - 20 with real data. 24 of those 212 are
global_route combos whose every cell is saturated, so 188 shards are written.
688 = 736 rankable cells - 48 with real data; the 24 degenerate cells take entries
too, for 712 cells carrying synthetic records.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import ranking, synth
from tools import registry as reg


@pytest.fixture(scope="module")
def generated(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("synth")
    synth.generate(out_dir=out)
    return out


def _cells(out: Path) -> dict[tuple[str, str, str, str], list[dict[str, object]]]:
    found: dict[tuple[str, str, str, str], list[dict[str, object]]] = {}
    for shard in sorted(out.rglob("*.json")):
        rec = json.loads(shard.read_text(encoding="utf-8"))
        for entry in rec["entries"]:
            for metric_id, value in entry["metrics"].items():
                key = (rec["task"], metric_id, rec["pdk"], rec["stage"])
                found.setdefault(key, []).append({"entry": entry, "value": value})
    return found


def test_no_synthetic_record_lands_in_a_void_or_saturated_cell(generated: Path) -> None:
    for task_id, metric_id, pdk_id, stage_id in _cells(generated):
        assert not reg.is_void(task_id, stage_id), (task_id, stage_id)
        assert not reg.is_saturated(task_id, metric_id, stage_id)


def test_every_empty_rankable_cell_is_filled(generated: Path) -> None:
    filled = set(_cells(generated))
    rankable = [
        c
        for c in reg.live_cells()
        if not reg.is_saturated(c[0], c[1], c[3]) and not reg.is_degenerate(c[0], c[1], c[3])
    ]
    empty = [c for c in rankable if c[0] != "total_area_prediction"]
    assert len(empty) == 688
    assert set(empty) <= filled


def test_all_twenty_four_degenerate_cells_take_an_entry(generated: Path) -> None:
    filled = set(_cells(generated))
    degenerate = [c for c in reg.live_cells() if reg.is_degenerate(c[0], c[1], c[3])]
    assert len(degenerate) == 24
    assert set(degenerate) <= filled


def test_the_shard_count_is_the_derived_one(generated: Path) -> None:
    assert len(list(generated.rglob("*.json"))) == 188


def test_the_realized_win_rate_lands_in_the_intended_band(generated: Path) -> None:
    """WIN_RATE is an intent. The monotonicity repair can only turn a loss into a
    win, so the realized rate runs at or above it. Sentinel cells are excluded:
    their leader is forced onto the defined side, so they are wins by rule."""
    from tools.baseline import Bound, BoundKind, lookup

    wins = total = 0
    for key, rows in _cells(generated).items():
        if reg.is_degenerate(key[0], key[1], key[3]):
            continue
        try:
            published = lookup(*key)
        except KeyError:
            continue
        if published.bound.kind is not BoundKind.EXACT:
            continue
        total += 1
        task_id, metric_id, pdk_id, stage_id = key
        state = ranking.cell_state(
            task_id,
            metric_id,
            stage_id,
            published.bound,
            tuple(Bound(BoundKind.EXACT, r["value"]["macro"]) for r in rows),
        )
        if state is ranking.CellState.BEATS_BASELINE:
            wins += 1
    rate = wins / total
    assert synth.WIN_RATE <= rate <= 0.72, f"realized win rate {rate:.3f}"


def test_error_decreases_monotonically_across_stages(generated: Path) -> None:
    cells = _cells(generated)
    order = {s.id: s.order for s in reg.stages()}
    for task_id, metric_id in reg.metric_rows():
        for pdk in reg.pdks():
            chain = [
                (order[s.id], min(float(r["value"]) for r in cells[(task_id, metric_id, pdk.id, s.id)]))
                for s in reg.stages()
                if (task_id, metric_id, pdk.id, s.id) in cells
            ]
            values = [v for _, v in sorted(chain)]
            direction = reg.metric(metric_id).direction
            expected = sorted(values, reverse=direction == "lower")
            assert values == expected, (task_id, metric_id, pdk.id)


def test_percent_metrics_are_generated_as_fractions(generated: Path) -> None:
    """tpr and tnr are true rates and cannot leave [0, 1]; a percent-stored value
    would land in 58.9 to 100. MAPE gets no range guard: 48 real cells exceed
    150 % and a ceiling would reject all of them."""
    for key, rows in _cells(generated).items():
        metric = reg.metric(key[1])
        if metric.percent and metric.direction == "higher":
            for row in rows:
                assert 0.0 <= float(row["value"]) <= 1.0, key


def test_the_manifest_covers_every_shard(generated: Path) -> None:
    manifest = json.loads((generated / "synthetic_manifest.json").read_text())
    shards = {
        str(p.relative_to(generated))
        for p in generated.rglob("*.json")
        if p.name != "synthetic_manifest.json"
    }
    assert set(manifest["sha256"]) == shards
    assert manifest["seed"] == synth.SEED
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_synth_grid.py -v`
Expected: FAIL, `AttributeError: module 'tools.synth' has no attribute 'generate'`

- [ ] **Step 3: Implement `generate` and the CLI**

`generate` iterates `reg.live_combos()`, skips any combo that already has a real
shard on disk, calls `combo_record`, and writes each non-`None` result to
`shard_path(...)` relative to `out_dir`.
Serialize with `json.dumps(payload, indent=2, sort_keys=True) + "\n"` and
`encoding="utf-8"`; `sort_keys` is what makes the bytes independent of dict
insertion order.
Hash each written file with `hashlib.sha256` and write
`data/synthetic_manifest.json` last, carrying `seed`, `shard_count`, `cell_count`
and the `sha256` map.

`main` takes `--seed` and `--out`, defaulting to `SEED` and `data/`, prints the
shard and cell counts, and returns 0.
End the module with `if __name__ == "__main__": raise SystemExit(main())`.
Running this module as `__main__` is safe, unlike `tools/validate.py`, because
`synth` registers nothing into a shared dict.

- [ ] **Step 4: Wire up the Makefile**

Replace the `synth` guard, which currently says the module does not exist yet:

```make
synth:
	uv run python -m tools.synth
```

- [ ] **Step 5: Run the tests and the target**

Run: `uv run pytest tests/test_synth_grid.py -v && make synth`
Expected: 9 passed; `make synth` reports 188 shards and 712 cells.

If `test_the_realized_win_rate_lands_in_the_intended_band` fails high, the repair
is adding more wins than expected; lower `WIN_RATE` until the realized rate lands
in the band and leave the band alone.
Widening the band to accommodate the code is how a guard becomes decorative.

- [ ] **Step 6: Commit**

```bash
git add tools/synth.py Makefile data/cells data/synthetic_manifest.json tests/test_synth_grid.py
git commit -m "feat(synth): emit 188 shards with a reproducibility manifest"
```

---

### Task 5: The validate check

**Files:**
- Create: `tools/checks/synthetic.py`
- Modify: `tools/checks/__init__.py`
- Test: `tests/test_synth_grid.py`

**Interfaces:**
- Consumes: `tools.checks.register`, `tools.registry`, `data/cells/`,
  `data/synthetic_manifest.json`.
- Produces: `synthetic.check() -> list[str]`, registered as `"synthetic"`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_synth_grid.py`:

```python
def test_the_check_passes_on_the_committed_tree() -> None:
    from tools.checks import synthetic

    assert synthetic.check() == []


def test_the_check_rejects_a_record_with_no_source(tmp_path: Path) -> None:
    from tools.checks import synthetic

    shard = tmp_path / "cells" / "x" / "ng45" / "cts.json"
    shard.parent.mkdir(parents=True)
    shard.write_text(
        json.dumps(
            {
                "task": "total_power_prediction",
                "pdk": "ng45",
                "stage": "cts",
                "entries": [{"model_id": "m", "metrics": {"mae": 1.0}}],
            }
        )
    )
    assert synthetic.check(root=tmp_path) != []


def test_the_check_rejects_a_synthetic_record_in_a_saturated_cell(tmp_path: Path) -> None:
    from tools.checks import synthetic

    shard = tmp_path / "cells" / "x" / "ng45" / "global_route.json"
    shard.parent.mkdir(parents=True)
    shard.write_text(
        json.dumps(
            {
                "task": "total_power_prediction",
                "pdk": "ng45",
                "stage": "global_route",
                "entries": [
                    {"model_id": "m", "source": "synthetic", "metrics": {"mae": 1.0}}
                ],
            }
        )
    )
    assert synthetic.check(root=tmp_path) != []


def test_the_check_rejects_manifest_drift(tmp_path: Path) -> None:
    """A hand-edited value under data/ is exactly what this catches."""
    from tools.checks import synthetic

    synth.generate(out_dir=tmp_path)
    victim = next(p for p in sorted(tmp_path.rglob("*.json")) if p.name != "synthetic_manifest.json")
    victim.write_text(victim.read_text().replace("synthetic", "synthetic ", 1))
    assert synthetic.check(root=tmp_path) != []
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_synth_grid.py -v`
Expected: FAIL, `ImportError: cannot import name 'synthetic' from 'tools.checks'`

- [ ] **Step 3: Implement the check**

Create `tools/checks/synthetic.py` with
`check(root: Path = DATA_DIR) -> list[str]`, decorated `@register("synthetic")`,
returning one message per violation and `[]` on success.
It walks every shard under `root / "cells"` and reports:

1. any entry with no `source` key, or a `source` outside
   `{"paper", "synthetic", "submission"}` - this is the contract's universal rule
   and it applies to real records too, so the walk is not filtered by source
2. a synthetic entry on a cell where `reg.is_void` or `reg.is_saturated` is true
3. a synthetic `tpr` or `tnr` outside `[0, 1]`, which is the 100x percent error
   caught outright; **no MAPE range check**, because 48 real cells legitimately
   exceed 150 %
4. a synthetic entry on a degenerate cell whose ranked state is `beats_baseline`
5. a SHA-256 in `synthetic_manifest.json` that does not match the file on disk,
   or a shard present on disk and absent from the manifest

Import it from `tools/checks/__init__.py` alongside the existing checks, at the
bottom of the file with `# noqa: E402,F401`, so it registers on package import.
It must never be run as `__main__`: a second copy of the module registers into a
different `CHECKS` dict and validation passes having done nothing.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_synth_grid.py -v && uv run eda-validate`
Expected: 13 passed; validate reports one more check than Phase 6 did, 0 failures.

- [ ] **Step 5: Commit**

```bash
git add tools/checks/synthetic.py tools/checks/__init__.py tests/test_synth_grid.py
git commit -m "feat(validate): add the synthetic placement and manifest check"
```

---

### Task 6: The visible marker and the cells-won exclusion

Synthetic entries drive a cell's **state**, because exercising the ranking paths
at scale is the entire argument for generating them.
They never drive the **tally**, because a cells-won count is a claim about
measured results.

**Files:**
- Modify: `build.py`, `templates/pages/matrix.html`, `templates/pages/cell.html`,
  `static/css/base.css`
- Test: `tests/test_synth_marker.py`

**Interfaces:**
- Consumes: the Phase 3 cell context dict, `tools.ranking`.
- Produces: `has_synthetic: bool` on every cell context; a `cells_won` tally
  computed over non-synthetic entries only.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_synth_marker.py`:

```python
"""The marker, and the tally that ignores it."""

from __future__ import annotations

from pathlib import Path

import build

DIST = Path("dist")


def test_every_synthetic_cell_carries_the_marker_class() -> None:
    context = build.matrix_context()
    marked = [c for c in context["cells"] if c["has_synthetic"]]
    assert len(marked) == 712
    assert all("synthetic" in c["classes"] for c in marked)


def test_cells_won_ignores_synthetic_entries() -> None:
    """A cells-won tally is a claim about measured results. 48 rankable cells hold
    real entries, so the tally can never exceed that however many are generated."""
    context = build.matrix_context()
    assert context["cells_won"] <= 48


def test_the_rendered_matrix_shows_the_marker_and_its_legend() -> None:
    html = (DIST / "index.html").read_text(encoding="utf-8")
    assert html.count('class="cell synthetic') >= 1
    assert "synthetic" in html.lower()
    assert "legend" in html.lower()


def test_a_synthetic_cell_page_says_so_above_the_ranking() -> None:
    page = DIST / "cell" / "total_power_prediction" / "ng45" / "floorplan" / "index.html"
    html = page.read_text(encoding="utf-8")
    assert "synthetic" in html.lower()
    assert html.index("synthetic") < html.index("<table")
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_synth_marker.py -v`
Expected: FAIL, `KeyError: 'has_synthetic'`

- [ ] **Step 3: Implement**

In `build.py`, set `has_synthetic` on each cell context from
`any(e.source == "synthetic" for e in entries)`, append `"synthetic"` to the cell's
class list when it is true, and compute `cells_won` over
`[e for e in entries if e.source != "synthetic"]`.

In `templates/pages/matrix.html`, render a glyph inside a marked cell and add one
legend row explaining it.
The glyph runs alongside the state colour, not instead of it, so the four states
stay distinguishable without colour and the marker is a fifth channel rather than
a replacement for one.

In `templates/pages/cell.html`, render a notice above the ranking table whenever
the cell has any synthetic entry, and mark the individual rows.
Above the table, not below: a reader who stops at the first number must have seen
it.

In `static/css/base.css`, one rule block for `.synthetic`, using existing custom
properties.
Do not introduce a new colour; the marker is a glyph and a border treatment, so it
survives greyscale printing and a colourblind reader.

- [ ] **Step 4: Run the tests**

Run: `make build && uv run pytest tests/test_synth_marker.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add build.py templates static/css/base.css tests/test_synth_marker.py
git commit -m "feat(synth): mark generated cells and exclude them from cells-won"
```

---

### Task 7: Determinism, and the whole gate

The claim "seeded and deterministic" is worth exactly as much as the test that
runs it twice.

**Files:**
- Test: `tests/test_synth_determinism.py`

**Interfaces:**
- Consumes: `tools.synth.generate`.
- Produces: nothing.

- [ ] **Step 1: Write the tests**

Create `tests/test_synth_determinism.py`:

```python
"""Same seed, same bytes. Run twice, diff.

A generator that is deterministic in intent and not in fact produces a diff on
every rebuild, which trains everyone to ignore diffs under data/.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from tools import synth


def _tree(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*.json"))
    }


def test_two_runs_with_the_same_seed_are_byte_identical(tmp_path: Path) -> None:
    first, second = tmp_path / "a", tmp_path / "b"
    synth.generate(out_dir=first)
    synth.generate(out_dir=second)
    assert _tree(first) == _tree(second)


def test_a_different_seed_changes_the_output(tmp_path: Path) -> None:
    first, second = tmp_path / "a", tmp_path / "b"
    synth.generate(out_dir=first)
    synth.generate(seed=synth.SEED + 1, out_dir=second)
    assert _tree(first) != _tree(second)


def test_generating_one_combo_alone_matches_generating_the_whole_grid(
    tmp_path: Path,
) -> None:
    """Keyed randomness, not a stream. If this fails, some draw is reading from a
    generator shared across cells and the output depends on iteration order."""
    whole = tmp_path / "whole"
    synth.generate(out_dir=whole)
    alone = synth.combo_record("cell_arc_slew_prediction", "asap7", "cts")
    assert alone is not None
    from tools.ingest import shard_path

    on_disk = (whole / shard_path("cell_arc_slew_prediction", "asap7", "cts").name)
    assert on_disk.exists()


@pytest.mark.parametrize("run", [1, 2])
def test_regeneration_leaves_the_working_tree_clean(run: int) -> None:
    """data/ is committed, so a nondeterministic generator shows up as a dirty
    tree. This is the same assertion the phase gate makes with git."""
    import subprocess

    subprocess.run(["make", "synth"], check=True, capture_output=True)
    diff = subprocess.run(
        ["git", "diff", "--stat", "--", "data/"], check=True, capture_output=True, text=True
    )
    assert diff.stdout == ""
```

- [ ] **Step 2: Run and confirm determinism holds**

Run: `uv run pytest tests/test_synth_determinism.py -v`
Expected: 5 passed.
A failure here means some draw is reading from a shared stream rather than from
`_rng(seed, *key)`. Find it before doing anything else; every other guarantee in
this phase rests on it.

- [ ] **Step 3: Run the full gate**

Run: `make check`
Expected: ruff clean, mypy clean, validate reports 0 failures across all
registered checks, every test passes, `make build` completes under 60 s.

Then confirm the budget did not move:

```bash
du -sh dist/
find dist -name '*.html' -size +88k | head
```

Expected: `dist/` well under 20 MB, and no page over 88 KB.

- [ ] **Step 4: Commit and open the PR**

```bash
git add tests/test_synth_determinism.py
git commit -m "test(synth): assert byte-identical output across runs"
git push -u origin phase-7/synthetic-decision
gh pr create --title "Phase 7: synthetic fill decision" --body "Rules on synthetic fill with evidence from the live matrix, and records the ruling in docs/DATA_CONTRACT.md."
```

---

## Phase gate

**Under ruling A**, the phase is complete when all of these hold:

```bash
make check
make synth   # must exit 1 with the decline message
```

- [ ] the ruling and its reasoning are recorded under `## Source rules` in
      `docs/DATA_CONTRACT.md`, with a date and no unfilled placeholder
- [ ] `CLAUDE.md`, `PLAN.md` and the `Makefile` all state the same ruling
- [ ] open decision 6 in `PLAN.md` carries Savidis's answer or an explicit deferral
- [ ] `tools/synth.py` does not exist, and no record under `data/` carries
      `"source": "synthetic"`
- [ ] `make check` passes unchanged

**Under ruling B**, add all of these:

```bash
make synth && make validate && make build && make test
git diff --exit-code -- data/    # regeneration must leave the tree clean
```

- [ ] 188 shards written, covering all 212 combos with no real data except the 24
      whose every cell is saturated
- [ ] 688 empty rankable cells filled, plus all 24 degenerate cells, for 712
- [ ] **zero synthetic records in void or saturated cells**
- [ ] every record carries an explicit `source`, and `make validate` fails when one
      does not
- [ ] `tpr` and `tnr` land in `[0, 1]`; no range guard exists on MAPE
- [ ] error is monotone across stages on every `(task, metric, pdk)` chain, in the
      metric's own direction
- [ ] per-circuit spread correlates with `reg.circuits()` registers at Spearman
      >= 0.6, and macro-means (or, for R², medians) back to the cell value
- [ ] the realized win rate is in `[WIN_RATE, 0.72]`, measured not assumed
- [ ] no degenerate cell ranks `beats_baseline`; no sentinel leader is left on the
      undecidable side of its bound
- [ ] two runs at the same seed are byte-identical; a different seed differs
- [ ] every synthetic cell renders a marker, and `cells_won` never exceeds 48
- [ ] `dist/` under 20 MB, no page over 88 KB

## Review prompt

```
Ruling A: use a plan auditor on the diff. The only question that matters is
whether the ruling is recorded somewhere a later phase will actually find it.
Check docs/DATA_CONTRACT.md, CLAUDE.md, PLAN.md and the Makefile agree, that the
date and reasoning are present rather than placeholder text, and that no record
under data/ carries "source": "synthetic". Report only contradictions between the
four documents.

Ruling B: use a data-integrity reviewer on tools/synth.py, tools/checks/synthetic.py
and the generated tree. Assume a reader who takes a screenshot of one cell and
puts it in a paper.

Verify, by running code rather than by reading it:
- no synthetic record sits in any of the 40 void or 120 saturated cells
- every generated tpr and tnr is in [0, 1], and no range guard was added to mape
- the 24 degenerate cells carry entries and none of them rank beats_baseline
- all 32 sentinel cells have a leader on the defined side of the bound
- per-circuit values macro-mean back to their cell value, and R2 medians back
- two runs at the same seed produce identical bytes, and generating a single combo
  in isolation matches that combo inside a whole-grid run
- the cells-won tally is computed over non-synthetic entries only

Then apply each of these mutations and confirm the suite fails on each:
1. delete the is_saturated guard in the emission loop
2. multiply every generated percent metric by 100
3. replace the keyed _rng with a single module-level random.Random
4. drop the "source" key from one generated entry

Report any mutation that does NOT fail the suite, and any place where a generated
number could be mistaken for a measured one. Do not report style preferences.
```
