# Phase 4 - Ingest and Ranking Implementation Plan

> **For agentic workers:** Implement this plan task-by-task - either dispatch a fresh subagent per task (recommended) or execute inline with review checkpoints. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** turn the lab's results tree into committed shards under `data/cells/`, and ship the ranking module that reads them, with `build.py` calling it in this same phase.

**Architecture:** `tools/paths.py` resolves a directory name to registry ids with a regex anchored on the registry vocabularies.
`tools/evallog.py` parses the 18 per-circuit lines of an `eval.log` and aggregates them by macro-mean, with median plus a positive count for R2.
`tools/ckpt.py` recovers tensor shapes from a checkpoint by walking it as the zip it is, and `tools/yamlsafe.py` reads `hparams.yaml` without constructing a single foreign object.
`tools/ingest.py` writes one shard per `(task, pdk, stage)`, `tools/shards.py` reads them back flattened per metric, and `tools/ranking.py` turns a shard row plus a `Bound` into a `Comparison` and a `CellState`.
`build.py` imports `tools.ranking` in this phase, so no abstraction ships without its consumer.

**Tech stack:** Python 3.11+, `uv`, `pytest`, `mypy --strict`, `ruff`, Jinja2. Standard library `re`, `zipfile`, `pickle`, `statistics`, `json`; `pyyaml` is already a dependency. `torch` is **not** imported anywhere in this phase.

## Global constraints

Copied from `PLAN.md` and `CLAUDE.md`; every task's requirements implicitly include these.

- Python **3.11+**, type hints on all public functions, `ruff` and `mypy` clean.
- **The registry is the only source of vocabulary.** No task, metric, stage, PDK or circuit id appears as a literal in `tools/`. Every selection is by registry attribute (`metric.direction`, `metric.percent`, `metric.bias`) or registry predicate (`reg.is_void`, `reg.is_degenerate`, `reg.is_saturated`).
- **Counts are derived, never literal.** Phase 1 ships an AST scan of `tools/` for the bare integers `46 232 880 856 120 24 40 920`. It parses rather than greps, so comments and docstrings are excluded, but a literal in code fails the suite.
- **Percent metrics are stored as a fraction in `[0, 1]`.** `eval.log` is **already a fraction** and is not converted. The one place this phase touches display units is the equality quantizer inside `tools/ranking.py`, which produces a number for rounding and never a string. See Task 5 for why that is not a second display boundary.
- **Every record carries an explicit `source`.** `make validate` fails without one.
- **Never commit files over 1 MB**, and never commit anything under `data/` by hand.
- `make check` is the gate. Run it and show the output before claiming a task is done.
- Conventional commits. Branch `phase-4/ingest-ranking`. Never push to `main`.
- **Never use an em dash** in prose, code comments or generated copy.

## Inherited interfaces

Locked by the phases before this one. If a name differs, adapt at the import line rather than reaching around it.

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
reg.REGISTRY_DIR: Path
```

**Phase 2, `tools/baseline.py`**

Reconciled across phases on 2026-08-11. These are the resolved names, and Phase 2's own plan is being edited to match. Import the module plainly as `baseline`; the `bl` alias an earlier draft used is dropped.

```python
class BoundKind(StrEnum):
    EXACT = "exact"; GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"; ABSENT = "absent"

@dataclass(frozen=True) class Bound: kind: BoundKind; value: float | None

@dataclass(frozen=True) class Baseline:
    task; metric; pdk; stage; baseline_state; bound: Bound; source; src_line
    key -> tuple[str, str, str, str]

baseline.lookup(task_id, metric_id, pdk_id, stage_id) -> Baseline  # KeyError on void
baseline.PAPER / baseline.PUBLISHED / baseline.DEGENERATE
```

`value` is `None` if and only if `kind is BoundKind.ABSENT`.
**Compare kinds with `is`, never with `==` against a string,** and parse a stored kind through `BoundKind(raw)` so an unknown value raises at the boundary. The `ABSENT` test is what stops a comparison being drawn against a degenerate 0/0 baseline, so it has to fail loudly rather than degrade into a silently-false equality.
A sentinel is a one-sided bound **in storage units**: `> 10000 %` is `Bound(BoundKind.GREATER_THAN, 100.0)`, `< -1` is `Bound(BoundKind.LESS_THAN, -1.0)`.

**Phase 3, `build.py`** with a Jinja2 `Environment`, `templates/pages/matrix.html`, and a per-cell context dict. This phase adds one field to that dict and one import to that file.

## The data, verified

Everything below was re-parsed from the tree before this plan was written. Do not re-derive it under time pressure; do re-confirm it in the tests.

```
~/Downloads/eda-ml-models/total_area_prediction/fixed_mlp/<config>_<PDK>_<STAGE>/<circuit>/version_0/
```

| Fact | Verified value |
|---|---|
| Tasks with any data | **one**, `total_area_prediction`. The other eleven have none. |
| Families | one, `fixed_mlp` |
| Combos | **exactly 20**: 4 PDKs x 5 stages, 34 MB total |
| Per combo | 18 circuit dirs, `eval.log`, `run.log`, two PNGs |
| Per circuit | `version_0/{hparams.yaml, events.out.tfevents.*, checkpoints/epoch=24-step=50.ckpt}` |
| `eval.log` | 28 lines: a header, 18 per-circuit lines, an `Overall` block of 2 |
| Checkpoints in the tree | 360, all Lightning-pickled |
| tfevents in the tree | 720, all z-scored targets, never read |

One per-circuit line, verbatim, and the exact shape all 18 take:

```
ac97_ctrl: model mae=710.1880, mape=0.0364, r2=-0.8802 | baseline mae=1987.8504, mape=0.1001, r2=-12.2630
```

The `Overall` block, which is **not ingested**:

```
Overall Baseline MAE: 1781.9696, Overall Baseline MAPE: 0.1243, Overall Baseline R2: 0.9892
Overall Model MAE: 909.6265, Overall Model MAPE: 0.0466, Overall Model R2: 0.9950
```

Re-parsed from `default_config_NG45_floorplan/eval.log`, all 18 lines matched:

| Quantity | Macro-mean over 18 circuits | Pooled (`Overall`) | Table 8 |
|---|---|---|---|
| baseline MAE | 1789.5997 | 1781.9696 | **1,781.97** |
| baseline MAPE | 0.124217 | 0.1243 | **12.43 %** |
| baseline R2 | median **-26.8635**, 0 of 18 positive | 0.9892 | 0.989 |
| model MAE | 911.9777 | 909.6265 | n/a |
| model MAPE | 0.046544 | 0.0466 | n/a |
| model R2 | median -2.2821, 0 of 18 positive | 0.9950 | n/a |

Three things follow, and each one is a test in this phase.

**`eval.log` MAPE is already a fraction.** `0.0364` is 3.64 %. Multiplying by 100 raises nothing, and it makes every MAPE cell render `baseline_leads` against a baseline stored as `0.1243`. This is the single most dangerous bug in the project and an earlier draft of the docs instructed exactly it.

**Table 8's baseline is literally the pooled `Overall` line.** 1781.9696 against a published 1,781.97 is a match, not an inference. So the baseline side of every comparison is pooled while our side is macro-mean, and on this design-level task they differ by 0.4 %. On the six finer-grained tasks each circuit contributes one row per net, arc or path, `ethernet` has 10,544 registers against `ss_pcm`'s 87, and the two estimators will diverge materially. **Open decision 1 is resolved here the way the contract recommends: rank on macro-mean, store the published pooled figure as the baseline's own, and record `ranked_on` in the shard so the basis is data rather than code.**

**The pooled R2 figure is a trap with a number on it.** `Overall Baseline R2: 0.9892` reads as an excellent baseline while the per-circuit median is -26.86 and **0 of 18 circuits are positive**. Every circuit is worse than predicting its own mean; pooling across circuits of very different absolute scale lets between-circuit variance masquerade as explained variance. R2 is therefore aggregated by median with a positive count, never by mean and never from the `Overall` block or the CSV's `baseline_r2` / `model_r2` columns.

## File structure

| File | Responsibility |
|---|---|
| `tools/paths.py` | `ComboPath`, `parse_combo_dir`, `discover`; the anchored regex, never `rsplit` |
| `tools/evallog.py` | `CircuitRow`, `parse`, `macro_mean`, `median_positive`, `aggregate` |
| `tools/yamlsafe.py` | `TagStrippingLoader`, `load`, `load_path`; no foreign object is ever constructed |
| `tools/ckpt.py` | `read_state_dict_shapes`, `mlp_widths`, `param_count`; walks the zip, never unpickles |
| `tools/ingest.py` | `MetricValue`, `Entry`, `Shard`, `shard_path`, `combo_shard`, `to_json`, `main` |
| `tools/shards.py` | `Record`, `load`; the flattened read path every consumer uses |
| `tools/ranking.py` | `Comparison`, `CellState`, `rank_key`, `compare`, `cell_state`, `bias_sort_key`, `rank_of`, `percentile_of` |
| `tools/checks/ingest.py` | the `ingest` check: shard shape, source, saturation, the divergence tripwire |
| `data/cells/**` | 20 generated shards, committed by the generator, never hand-edited |
| `build.py` | modified: imports `tools.ranking` and puts a real state on every cell |
| `tests/fixtures/tree/**` | one real `eval.log`, committed; the CI stand-in for the 34 MB tree |
| `tests/fixtures/ckpt/**` | a synthetic checkpoint built to the lab's exact geometry |
| `tests/test_paths.py`, `test_evallog.py`, `test_ckpt.py`, `test_ingest.py`, `test_ranking.py`, `test_ingest_check.py` | one per module |

**On committing fixtures.** The `eval.log` holds measurements, which are facts, and is 28 lines; it is committed on the same reasoning that puts `table8_baseline.csv` under `docs/sources/`. A `.ckpt` is the lab's trained weights under CC BY-NC-SA and is **not** committed. CI reads a synthetic checkpoint built to the same geometry, and the real file is asserted by an env-gated test that runs where the tree exists. Both are in the phase gate.

---

### Task 1: Anchored path parsing

The first thing that touches the tree, and the first thing that has already cost time.

**Files:**
- Create: `tools/paths.py`
- Test: `tests/test_paths.py`

**Interfaces:**
- Consumes: `tools.registry`.
- Produces: `paths.ComboPath`, `paths.parse_combo_dir(name: str) -> tuple[str, str, str]` returning `(config, pdk_id, stage_id)`, `paths.discover(root: Path) -> tuple[ComboPath, ...]`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_paths.py`:

```python
"""Resolving the lab's directory names to registry ids.

Expected values live here, in tests. They must never appear in tools/.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools import paths
from tools import registry as reg

TREE = Path(__file__).resolve().parent / "fixtures" / "tree"


def test_rsplit_is_wrong_and_this_parser_disagrees_with_it() -> None:
    """The trap, stated as an executable fact rather than as a comment.

    rsplit("_", 2) on default_config_ng45_global_place yields stage "place" and
    pdk "global". Three of the five stage ids contain an underscore, so this is
    not an edge case, it is 60 percent of the vocabulary."""
    name = "default_config_ng45_global_place"
    assert name.rsplit("_", 2) == ["default_config_ng45", "global", "place"]

    _config, pdk_id, stage_id = paths.parse_combo_dir(name)
    assert (pdk_id, stage_id) == ("ng45", "global_place")


def test_every_stage_in_the_registry_parses() -> None:
    """Driven from the registry, so a stage added later cannot silently fail."""
    for stage in reg.stages():
        name = f"default_config_NG45_{stage.id}"
        _config, pdk_id, stage_id = paths.parse_combo_dir(name)
        assert (pdk_id, stage_id) == ("ng45", stage.id)


def test_the_three_stages_containing_underscores_are_the_reason() -> None:
    underscored = [s.id for s in reg.stages() if "_" in s.id]
    assert len(underscored) == 3
    for stage_id in underscored:
        assert paths.parse_combo_dir(f"default_config_ASAP7_{stage_id}")[2] == stage_id


def test_uppercase_pdk_directories_normalize_to_the_registry_id() -> None:
    """Directory names are uppercase, registry ids are lowercase. Matching
    case-sensitively makes all 20 combos silently fail to resolve."""
    for pdk in reg.pdks():
        name = f"default_config_{pdk.table8_label}_cts"
        assert paths.parse_combo_dir(name)[1] == pdk.id
        assert name != name.lower(), "the fixture must actually be uppercase"


def test_an_unknown_stage_raises_rather_than_returning_none() -> None:
    with pytest.raises(ValueError):
        paths.parse_combo_dir("default_config_NG45_place_resize")


def test_an_unknown_pdk_raises() -> None:
    """Table 8 misspells IHP130 as IPH130. A parser that shrugs invents a fifth
    PDK; this one refuses."""
    with pytest.raises(ValueError):
        paths.parse_combo_dir("default_config_IPH130_cts")


def test_discover_walks_the_committed_fixture_tree() -> None:
    found = paths.discover(TREE)
    assert [(c.task, c.family, c.pdk, c.stage) for c in found] == [
        ("total_area_prediction", "fixed_mlp", "ng45", "floorplan")
    ]


def test_discover_ignores_files_that_are_not_combo_directories() -> None:
    """The family directory also holds aggregated_eval_metrics.csv, a .dot and a
    .png. None of them parse, and none of them may raise."""
    assert paths.discover(TREE)
```

- [ ] **Step 2: Build the fixture tree**

```bash
mkdir -p tests/fixtures/tree/total_area_prediction/fixed_mlp/default_config_NG45_floorplan
cp "$EXPERIMENTS/total_area_prediction/fixed_mlp/default_config_NG45_floorplan/eval.log" \
   tests/fixtures/tree/total_area_prediction/fixed_mlp/default_config_NG45_floorplan/eval.log
touch tests/fixtures/tree/total_area_prediction/fixed_mlp/aggregated_eval_metrics.csv
wc -l tests/fixtures/tree/total_area_prediction/fixed_mlp/default_config_NG45_floorplan/eval.log
```

Expected: `28`. Set `EXPERIMENTS=~/Downloads/eda-ml-models` first.

- [ ] **Step 3: Run the tests to make sure they fail**

Run: `uv run pytest tests/test_paths.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'tools.paths'`

- [ ] **Step 4: Implement**

Create `tools/paths.py`:

```python
"""Resolve the lab's results tree to registry ids.

The combo directory is <config>_<PDK>_<STAGE> and both halves are traps.

Three of the five stage ids contain an underscore, so rsplit("_", 2) on
default_config_ng45_global_place returns stage "place" and pdk "global". The
regex below is anchored on the registry vocabularies instead, so a stage id can
never be split across its own separator.

PDK directory names are uppercase while registry ids are lowercase. Matching is
case-insensitive and the result is normalized back to the registry id, or every
combo silently fails to resolve and the grid stays empty for a reason that looks
like missing data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from tools import registry as reg


@dataclass(frozen=True, slots=True)
class ComboPath:
    """One (task, pdk, stage) directory in the results tree."""

    task: str
    family: str
    config: str
    pdk: str
    stage: str
    directory: Path

    @property
    def eval_log(self) -> Path:
        return self.directory / "eval.log"


@cache
def _combo_re() -> re.Pattern[str]:
    """<config>_<PDK>_<STAGE>, anchored on the registry vocabularies.

    Alternatives are sorted longest first because `re` alternation is first-match
    and not longest-match, so `global_route` has to be offered before any prefix
    of it. That ordering is load-bearing rather than cosmetic.

    `config` is greedy and then backtracks to the LAST position where a known PDK
    and a known stage both follow, which is the correct reading of a config name
    that happens to contain a vocabulary word.
    """
    pdks = "|".join(
        sorted((re.escape(p.id) for p in reg.pdks()), key=len, reverse=True)
    )
    stages = "|".join(
        sorted((re.escape(s.id) for s in reg.stages()), key=len, reverse=True)
    )
    return re.compile(
        rf"^(?P<config>.+)_(?P<pdk>{pdks})_(?P<stage>{stages})$",
        re.IGNORECASE,
    )


def parse_combo_dir(name: str) -> tuple[str, str, str]:
    """(config, pdk_id, stage_id) from one combo directory name.

    Raises ValueError on anything that does not parse. A directory that quietly
    returns None is a combo that vanishes from the grid without a message.
    """
    match = _combo_re().match(name)
    if match is None:
        raise ValueError(f"cannot parse combo directory {name!r}")
    pdk_id = match.group("pdk").lower()
    stage_id = match.group("stage").lower()
    # Round-trip through the registry so a match on a vocabulary that later
    # changes case cannot pass silently.
    return match.group("config"), reg.pdk(pdk_id).id, reg.stage(stage_id).id


def discover(root: Path) -> tuple[ComboPath, ...]:
    """Every parseable combo directory under <root>/<task>/<family>/.

    Anything that does not parse is skipped rather than raised on: the family
    directory also holds aggregated_eval_metrics.csv, a .dot and a .png, and none
    of those are combos. A task directory that is not in the registry IS raised
    on, because that is a vocabulary gap and not a stray file.
    """
    found: list[ComboPath] = []
    for task_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        task_id = reg.task(task_dir.name).id
        for family_dir in sorted(p for p in task_dir.iterdir() if p.is_dir()):
            for combo_dir in sorted(p for p in family_dir.iterdir() if p.is_dir()):
                try:
                    config, pdk_id, stage_id = parse_combo_dir(combo_dir.name)
                except ValueError:
                    continue
                found.append(
                    ComboPath(
                        task=task_id,
                        family=family_dir.name,
                        config=config,
                        pdk=pdk_id,
                        stage=stage_id,
                        directory=combo_dir,
                    )
                )
    return tuple(found)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_paths.py -v`
Expected: 8 passed

- [ ] **Step 6: Confirm the real tree yields exactly 20 combos**

```bash
uv run python -c "
from pathlib import Path
from tools import paths
found = paths.discover(Path.home() / 'Downloads' / 'eda-ml-models')
print(len(found), 'combos')
print(sorted({c.task for c in found}), sorted({c.family for c in found}))
print(len({c.pdk for c in found}), 'pdks', len({c.stage for c in found}), 'stages')
"
```

Expected: `20 combos`, `['total_area_prediction'] ['fixed_mlp']`, `4 pdks 5 stages`.

- [ ] **Step 7: Verify lint and types**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy`
Expected: all clean

- [ ] **Step 8: Commit**

```bash
git add tools/paths.py tests/test_paths.py tests/fixtures/tree
git commit -m "feat(ingest): parse combo directories with a registry-anchored regex"
```

---

### Task 2: eval.log parsing and the two estimators

The heart of the phase.
One regex, two aggregators, and the rule that `eval.log` is already a fraction.

**Files:**
- Create: `tools/evallog.py`
- Test: `tests/test_evallog.py`

**Interfaces:**
- Consumes: `tools.registry`.
- Produces: `evallog.CircuitRow`, `evallog.Side`, `evallog.parse(text: str) -> tuple[CircuitRow, ...]`, `evallog.macro_mean(values) -> float`, `evallog.median_positive(values) -> tuple[float, int]`, `evallog.aggregate(rows, *, side: Side) -> dict[str, tuple[float, int | None]]`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_evallog.py`:

```python
"""Parsing and aggregating eval.log.

Expected values live here, in tests. They were re-parsed from the committed
fixture, which is the lab's file byte for byte.
"""

from __future__ import annotations

import pytest

from tools import evallog
from tools import registry as reg
from tests.test_paths import TREE

LOG = (
    TREE
    / "total_area_prediction"
    / "fixed_mlp"
    / "default_config_NG45_floorplan"
    / "eval.log"
).read_text(encoding="utf-8")


def test_all_eighteen_circuit_lines_parse() -> None:
    rows = evallog.parse(LOG)
    assert len(rows) == len(reg.circuits())
    assert {r.circuit for r in rows} == {c.id for c in reg.circuits()}


def test_the_first_line_parses_to_its_exact_six_numbers() -> None:
    row = next(r for r in evallog.parse(LOG) if r.circuit == "ac97_ctrl")
    assert row.model == {"mae": 710.1880, "mape": 0.0364, "r2": -0.8802}
    assert row.baseline == {"mae": 1987.8504, "mape": 0.1001, "r2": -12.2630}


def test_mape_is_left_as_the_fraction_it_already_is() -> None:
    """0.0364 IS 3.64 percent. Multiplying by 100 here raises nothing and makes
    every MAPE cell render baseline_leads against a baseline stored as 0.1243.
    This is the single most dangerous bug in the project."""
    row = next(r for r in evallog.parse(LOG) if r.circuit == "ac97_ctrl")
    assert row.model["mape"] == 0.0364
    assert row.model["mape"] < 1.0


def test_the_overall_block_is_not_parsed_as_a_circuit() -> None:
    """It is pooled, and the contract forbids ingesting it. The regex requires a
    known circuit id, so the block cannot arrive by accident."""
    circuits = {r.circuit for r in evallog.parse(LOG)}
    assert not any("overall" in c.lower() for c in circuits)
    assert "Overall Baseline MAE" in LOG, "the fixture must still contain it"


def test_an_unknown_circuit_id_raises() -> None:
    with pytest.raises(ValueError):
        evallog.parse(
            "not_a_circuit: model mae=1.0, mape=0.1, r2=0.5 | "
            "baseline mae=2.0, mape=0.2, r2=0.4\n"
        )


def test_a_truncated_log_raises_rather_than_aggregating_a_subset() -> None:
    """Sixteen circuits silently averaged is a plausible-looking number."""
    partial = "\n".join(LOG.splitlines()[:10])
    with pytest.raises(ValueError):
        evallog.parse(partial)


def test_macro_mean_differs_from_the_pooled_figure() -> None:
    """The whole reason open decision 1 exists. On this design-level task the two
    estimators are 0.4 percent apart; on the six finer-grained tasks they will
    not be."""
    rows = evallog.parse(LOG)
    macro = evallog.macro_mean([r.baseline["mae"] for r in rows])
    assert round(macro, 4) == 1789.5997
    pooled = 1781.9696  # the Overall line, and Table 8's published 1,781.97
    assert macro != pooled
    assert 0.99 < pooled / macro < 1.01


def test_r2_uses_the_median_and_reports_how_many_are_positive() -> None:
    """Overall Baseline R2 reads 0.9892. The per-circuit median is -26.86 and ZERO
    of 18 circuits are positive. Every circuit is worse than predicting its own
    mean while the pooled figure says the opposite."""
    rows = evallog.parse(LOG)
    median, positive = evallog.median_positive([r.baseline["r2"] for r in rows])
    assert round(median, 4) == -26.8635
    assert positive == 0


def test_the_mean_would_have_hidden_it() -> None:
    """A single large negative destroys a mean, which is why R2 is a median."""
    rows = evallog.parse(LOG)
    values = [r.baseline["r2"] for r in rows]
    mean = sum(values) / len(values)
    median, _ = evallog.median_positive(values)
    assert mean < median


def test_aggregate_returns_one_entry_per_metric_in_the_log() -> None:
    rows = evallog.parse(LOG)
    model = evallog.aggregate(rows, side="model")
    assert set(model) == {"mae", "mape", "r2"}
    assert round(model["mae"][0], 4) == 911.9777
    assert round(model["mape"][0], 6) == 0.046544
    assert round(model["r2"][0], 4) == -2.2821


def test_only_r2_carries_a_positive_count() -> None:
    """n_positive is meaningful for R2 and meaningless for an error magnitude."""
    model = evallog.aggregate(evallog.parse(LOG), side="model")
    assert model["r2"][1] == 0
    assert model["mae"][1] is None
    assert model["mape"][1] is None


def test_every_metric_the_log_reports_is_in_the_task_registry() -> None:
    """The log's vocabulary must be a subset of the registry's, or ingest writes a
    metric the grid has no row for."""
    model = evallog.aggregate(evallog.parse(LOG), side="model")
    assert set(model) <= set(reg.task("total_area_prediction").metrics)
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_evallog.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'tools.evallog'`

- [ ] **Step 3: Implement**

Create `tools/evallog.py`:

```python
"""Parse and aggregate the lab's eval.log.

The file holds a header, one line per circuit, and an "Overall" block. Only the
per-circuit lines are read.

Two rules, both from docs/DATA_CONTRACT.md, and both silent when broken:

  * MAPE in this file is ALREADY A FRACTION. 0.0364 is 3.64 percent. It is not
    converted here or anywhere else. Multiplying by 100 raises nothing and makes
    every MAPE cell render baseline_leads.
  * the "Overall" block is row-pooled and is never ingested. Its R2 reads 0.9892
    on a combo whose per-circuit median is -26.86 with zero circuits positive,
    because pooling across circuits of very different absolute scale lets
    between-circuit variance masquerade as explained variance.

Aggregation is macro-mean for error magnitudes and median plus a positive count
for R2, so one -335 circuit cannot carry a cell.
"""

from __future__ import annotations

import re
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cache
from typing import Literal

from tools import registry as reg

Side = Literal["model", "baseline"]

_NUMBER = r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"

LINE = re.compile(
    rf"^(?P<circuit>[A-Za-z0-9_]+):\s+"
    rf"model\s+mae=(?P<model_mae>{_NUMBER}),\s+"
    rf"mape=(?P<model_mape>{_NUMBER}),\s+"
    rf"r2=(?P<model_r2>{_NUMBER})\s*\|\s*"
    rf"baseline\s+mae=(?P<baseline_mae>{_NUMBER}),\s+"
    rf"mape=(?P<baseline_mape>{_NUMBER}),\s+"
    rf"r2=(?P<baseline_r2>{_NUMBER})\s*$"
)
"""One per-circuit line.

Anchored at both ends and requiring the `model ... | baseline ...` shape, so the
"Overall Baseline MAE: ..." lines cannot match. That is structural rather than a
filter, which is the point: a filter can be removed, a shape cannot.
"""

_MEDIAN_METRICS = ("r2",)
"""Metrics aggregated by median with a positive count rather than by mean.

Named by id because the registry has no attribute for it and inventing one to
avoid a literal here would put the same knowledge in a file nobody reads. The
membership is asserted against reg.metrics() in _metric_ids().
"""


@dataclass(frozen=True, slots=True)
class CircuitRow:
    """One circuit's model and baseline numbers, exactly as published."""

    circuit: str
    model: dict[str, float]
    baseline: dict[str, float]


@cache
def _metric_ids() -> tuple[str, ...]:
    """The metric ids eval.log reports, in the order the line prints them."""
    ids = ("mae", "mape", "r2")
    known = {m.id for m in reg.metrics()}
    unknown = [m for m in ids + _MEDIAN_METRICS if m not in known]
    if unknown:
        raise ValueError(f"eval.log names metrics the registry does not: {unknown}")
    return ids


def parse(text: str) -> tuple[CircuitRow, ...]:
    """Every per-circuit line, in file order.

    Raises if a circuit id is not in the registry, if a circuit repeats, or if
    the file does not carry one line for every circuit. A truncated log that
    quietly aggregates 16 of 18 produces a plausible number and no error, which
    is exactly the failure this refuses.
    """
    expected = {c.id for c in reg.circuits()}
    rows: list[CircuitRow] = []
    seen: set[str] = set()

    for line in text.splitlines():
        match = LINE.match(line.strip())
        if match is None:
            continue
        circuit = match.group("circuit")
        if circuit not in expected:
            raise ValueError(f"eval.log names an unknown circuit {circuit!r}")
        if circuit in seen:
            raise ValueError(f"eval.log repeats circuit {circuit!r}")
        seen.add(circuit)
        rows.append(
            CircuitRow(
                circuit=circuit,
                model={m: float(match.group(f"model_{m}")) for m in _metric_ids()},
                baseline={
                    m: float(match.group(f"baseline_{m}")) for m in _metric_ids()
                },
            )
        )

    missing = sorted(expected - seen)
    if missing:
        raise ValueError(f"eval.log is missing circuits: {missing}")
    return tuple(rows)


def macro_mean(values: Sequence[float]) -> float:
    """Weight every circuit equally.

    Pooling weights every ROW equally, so the largest circuit dominates. With
    ethernet at 10,544 registers and ss_pcm at 87, that is not a rounding
    difference on the finer-grained tasks.
    """
    if not values:
        raise ValueError("macro_mean over no circuits")
    return sum(values) / len(values)


def median_positive(values: Sequence[float]) -> tuple[float, int]:
    """The per-circuit median, and how many circuits are above zero.

    Both halves matter. The median survives one catastrophic circuit; the count
    is what stops a median of -2.28 being read as "roughly fine".
    """
    if not values:
        raise ValueError("median over no circuits")
    return statistics.median(values), sum(1 for v in values if v > 0.0)


def aggregate(
    rows: Sequence[CircuitRow], *, side: Side
) -> dict[str, tuple[float, int | None]]:
    """Aggregate one side of the log into (value, n_positive) per metric.

    n_positive is None for every metric that is not aggregated by median, because
    "how many circuits had a positive mean absolute error" is not a question.
    """
    if not rows:
        raise ValueError("aggregate over no circuits")
    out: dict[str, tuple[float, int | None]] = {}
    for metric_id in _metric_ids():
        values = [getattr(row, side)[metric_id] for row in rows]
        if metric_id in _MEDIAN_METRICS:
            median, positive = median_positive(values)
            out[metric_id] = (median, positive)
        else:
            out[metric_id] = (macro_mean(values), None)
    return out
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_evallog.py -v`
Expected: 12 passed

- [ ] **Step 5: Verify lint and types**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy`
Expected: all clean

- [ ] **Step 6: Commit**

```bash
git add tools/evallog.py tests/test_evallog.py
git commit -m "feat(ingest): parse eval.log and aggregate by macro-mean and median"
```

---

### Task 3: Reading a checkpoint and hparams without executing anything

Both files are hostile.
A `.ckpt` is a pickle, and community submissions run on our runner.
`hparams.yaml` carries `!!python/object:` tags and then lies about what it describes.

**Files:**
- Create: `tools/yamlsafe.py`, `tools/ckpt.py`
- Create: `tests/fixtures/ckpt/build_fixture.py`, `tests/fixtures/ckpt/lab_mlp.ckpt`
- Test: `tests/test_ckpt.py`, `tests/test_no_unpickle.py`

**Interfaces:**
- Consumes: `pyyaml`, standard library `pickle` and `zipfile`. **Not** `torch`.
- Produces: `yamlsafe.TagStrippingLoader`, `yamlsafe.load(text) -> Any`, `yamlsafe.load_path(path) -> Any`; `ckpt.read_state_dict_shapes(path) -> dict[str, tuple[int, ...]]`, `ckpt.mlp_widths(shapes) -> tuple[int, ...]`, `ckpt.param_count(shapes) -> int`.

**Why `weights_only=True` is not the answer.** It is necessary and it is **not sufficient**, because it refuses all 360 of the lab's own checkpoints: Lightning pickled `eda_ml.schema.ModelConfig` into every one. Verified, 360 scanned, 360 refused. The error message then helpfully suggests `weights_only=False`, which is the arbitrary-code-execution path this rule exists to prevent. Do not take it, and do not grow a `safe_globals` allowlist either, because an allowlist is a list of classes somebody has to keep being right about.

**What is done instead, and it is verified working on a real checkpoint.** The `.ckpt` is opened as the zip it is, `archive/data.pkl` is walked with an `Unpickler` whose `find_class` returns an inert placeholder class for **any** foreign global, and the shapes are recovered from the third argument of each `torch._utils._rebuild_tensor_v2` call. No foreign code runs, whatever the checkpoint contains. Run against `default_config_NG45_floorplan/ac97_ctrl`, this recovers:

```
scalar_encoder.net.0.weight (64, 41)   scalar_encoder.net.0.bias (64,)
scalar_encoder.net.2.weight (32, 64)   scalar_encoder.net.2.bias (32,)
scalar_encoder.net.4.weight (16, 32)   scalar_encoder.net.4.bias (16,)
scalar_encoder.net.6.weight (1, 16)    scalar_encoder.net.6.bias (1,)
```

which is `41 -> 64 -> 32 -> 16 -> 1` and `2688 + 2080 + 528 + 17 = 5313` parameters.
`hparams.yaml` for the same run declares `in_features: 7` on the first Linear layer. It is wrong, and it is wrong on all 360.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ckpt.py`:

```python
"""Recovering architecture without executing a byte of foreign code.

Expected values live here, in tests. The geometry was read off a real lab
checkpoint; the committed fixture is built to that geometry rather than being the
lab's weights, which are CC BY-NC-SA and not ours to redistribute.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tools import ckpt, yamlsafe

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "ckpt" / "lab_mlp.ckpt"

LAB_SHAPES = {
    "scalar_encoder.net.0.weight": (64, 41),
    "scalar_encoder.net.0.bias": (64,),
    "scalar_encoder.net.2.weight": (32, 64),
    "scalar_encoder.net.2.bias": (32,),
    "scalar_encoder.net.4.weight": (16, 32),
    "scalar_encoder.net.4.bias": (16,),
    "scalar_encoder.net.6.weight": (1, 16),
    "scalar_encoder.net.6.bias": (1,),
}

HPARAMS = """\
config: !!python/object:eda_ml.schema.ModelConfig
  class_name: ''
  hyperparameters: !!python/object:eda_ml.schema.HyperparameterConfig
    batch_size: 1024
    no_of_epochs: 25
  mlp_branch: !!python/object:eda_ml.schema.MLPBranchConfig
    layers:
    - in_features: 7
      out_features: 64
      type: Linear
    - type: ReLU
"""


def test_shapes_come_back_from_the_zip() -> None:
    assert ckpt.read_state_dict_shapes(FIXTURE) == LAB_SHAPES


def test_the_widths_are_the_labs_fixed_mlp() -> None:
    assert ckpt.mlp_widths(LAB_SHAPES) == (41, 64, 32, 16, 1)


def test_the_parameter_count_is_five_thousand_three_hundred_and_thirteen() -> None:
    """2688 + 2080 + 528 + 17. Derived from the shapes, not from the file."""
    assert ckpt.param_count(LAB_SHAPES) == 5313


def test_a_foreign_global_never_becomes_a_real_object() -> None:
    """The placeholder is inert. If find_class ever imported anything, this is
    where a submission's __reduce__ would have run."""
    shapes = ckpt.read_state_dict_shapes(FIXTURE)
    assert all(isinstance(v, tuple) for v in shapes.values())
    assert all(isinstance(n, int) for v in shapes.values() for n in v)


def test_a_zip_without_a_state_dict_raises() -> None:
    import zipfile

    bad = FIXTURE.parent / "empty.ckpt"
    with zipfile.ZipFile(bad, "w") as archive:
        archive.writestr("archive/version", "3\n")
    try:
        with pytest.raises(ValueError):
            ckpt.read_state_dict_shapes(bad)
    finally:
        bad.unlink()


def test_hparams_breaks_safe_load_and_survives_the_stripping_loader() -> None:
    """safe_load raises ConstructorError on the python/object tag. full_load and
    UnsafeLoader construct arbitrary objects and are the same hazard as
    unpickling, so neither is an option."""
    import yaml

    with pytest.raises(yaml.YAMLError):
        yaml.safe_load(HPARAMS)

    parsed = yamlsafe.load(HPARAMS)
    assert parsed["config"]["hyperparameters"]["batch_size"] == 1024


def test_hparams_is_parsed_and_then_its_architecture_is_ignored() -> None:
    """It reports in_features 7 where the trained weight is (64, 41), and it does
    that on all 360 checkpoints. Architecture comes from tensor shapes only."""
    parsed = yamlsafe.load(HPARAMS)
    declared = parsed["config"]["mlp_branch"]["layers"][0]["in_features"]
    assert declared == 7
    assert ckpt.mlp_widths(LAB_SHAPES)[0] == 41
    assert declared != ckpt.mlp_widths(LAB_SHAPES)[0]


@pytest.mark.skipif(
    not os.environ.get("EDA_EXPERIMENTS"),
    reason="set EDA_EXPERIMENTS to the results tree to check the real checkpoint",
)
def test_the_real_lab_checkpoint_agrees_with_the_fixture() -> None:
    """The claim in the plan, checked against the lab's actual file where it is
    available. The fixture is built to this geometry; this is what proves the
    geometry."""
    root = Path(os.environ["EDA_EXPERIMENTS"])
    real = next(root.rglob("epoch=*-step=*.ckpt"))
    assert ckpt.read_state_dict_shapes(real) == LAB_SHAPES
```

Create `tests/test_no_unpickle.py`:

```python
"""No module under tools/ may reach for an unpickling API.

Parsed with `ast`, not grepped. A regex over raw text also matches prose, and
tools/ckpt.py's own docstring legitimately explains why weights_only is refused.
Grepping would force that explanation out of the code to satisfy a test about
code. The AST carries no comments and represents a docstring as a str constant,
so both are excluded for free.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FORBIDDEN_CALLS = {
    "torch.load",
    "torch.serialization.add_safe_globals",
    "pickle.load",
    "pickle.loads",
    "yaml.load_all",
    "yaml.full_load",
    "yaml.unsafe_load",
}
FORBIDDEN_NAMES = {"UnsafeLoader", "FullLoader", "add_safe_globals"}
FORBIDDEN_KEYWORDS = {"weights_only"}


def _dotted(node: ast.expr) -> str:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _sources() -> list[Path]:
    files = sorted((ROOT / "tools").rglob("*.py"))
    build = ROOT / "build.py"
    if build.exists():
        files.append(build)
    return files


def test_no_unpickling_api_is_referenced() -> None:
    offenders: list[str] = []
    for path in _sources():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute | ast.Name):
                dotted = _dotted(node)
                if dotted in FORBIDDEN_CALLS:
                    offenders.append(f"{path.name}:{node.lineno} calls {dotted}")
                tail = dotted.rsplit(".", 1)[-1]
                if tail in FORBIDDEN_NAMES:
                    offenders.append(f"{path.name}:{node.lineno} names {tail}")
            if isinstance(node, ast.keyword) and node.arg in FORBIDDEN_KEYWORDS:
                offenders.append(f"{path.name}:{node.lineno} passes {node.arg}")
    assert not offenders, offenders


def test_torch_is_never_imported() -> None:
    """The site build must not need it, and ingest must not use it. The optional
    torch extra in pyproject.toml exists for nothing this phase ships."""
    offenders: list[str] = []
    for path in _sources():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                offenders += [
                    f"{path.name}:{node.lineno}"
                    for a in node.names
                    if a.name.split(".")[0] == "torch"
                ]
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                "torch"
            ):
                offenders.append(f"{path.name}:{node.lineno}")
    assert not offenders, offenders


def test_the_only_unpickler_is_the_restricted_one() -> None:
    """pickle.Unpickler is allowed exactly once, subclassed in tools/ckpt.py. A
    second one is a second security posture."""
    users = [
        path.name
        for path in _sources()
        if "Unpickler" in path.read_text(encoding="utf-8")
    ]
    assert users == ["ckpt.py"]
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_ckpt.py tests/test_no_unpickle.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'tools.ckpt'`

- [ ] **Step 3: Implement the YAML loader**

Create `tools/yamlsafe.py`:

```python
"""Read hparams.yaml without constructing a single foreign object.

The file carries `!!python/object:eda_ml.schema.ModelConfig` tags, so
yaml.safe_load raises ConstructorError. yaml.full_load and yaml.UnsafeLoader do
construct those objects, which is the same hazard as unpickling and is refused
for the same reason.

The loader below keeps SafeLoader's construction rules and discards the tag,
returning the plain mapping underneath. Nothing is imported and nothing is
called.

Remember that the file lies anyway. It reports in_features 7 where the trained
weight is (64, 41), and params 0 for every layer. Architecture comes from
checkpoint tensor shapes, never from here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_PYTHON_TAGS = (
    "tag:yaml.org,2002:python/object:",
    "tag:yaml.org,2002:python/object/new:",
    "tag:yaml.org,2002:python/object/apply:",
    "tag:yaml.org,2002:python/name:",
    "tag:yaml.org,2002:python/module:",
)


class TagStrippingLoader(yaml.SafeLoader):
    """SafeLoader that reads through a python tag instead of honouring it."""


def _plain(loader: yaml.SafeLoader, _suffix: str, node: yaml.Node) -> Any:  # noqa: ANN401
    """Construct the node as the plain data it is written as.

    A tagged mapping becomes a dict, a tagged sequence a list, a tagged scalar a
    string. The tag names a class we deliberately do not have and will not fetch.
    """
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node, deep=True)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node, deep=True)
    return loader.construct_scalar(node)


for _tag in _PYTHON_TAGS:
    TagStrippingLoader.add_multi_constructor(_tag, _plain)


def load(text: str) -> Any:  # noqa: ANN401
    """Parse YAML that may carry python tags. Returns plain data only."""
    return yaml.load(text, Loader=TagStrippingLoader)  # noqa: S506


def load_path(path: Path) -> Any:  # noqa: ANN401
    return load(path.read_text(encoding="utf-8"))
```

**Expect a scanner to flag `yaml.load` here, and do not "fix" it by reverting to `safe_load`.** The hazard in `yaml.load` is the default `FullLoader`, which resolves a `python/object` tag by importing and constructing the named class. `TagStrippingLoader` subclasses `SafeLoader` and its only added constructors return a `dict`, a `list` or a `str`; it imports nothing and instantiates nothing. Plain `safe_load` is not an option because it **raises** on this file, and `full_load` and `UnsafeLoader` are the exact hazard. `tests/test_no_unpickle.py` proves no unsafe loader name appears anywhere under `tools/`, and that test is the durable guarantee rather than the `noqa`.

- [ ] **Step 4: Implement the checkpoint reader**

Create `tools/ckpt.py`:

```python
"""Recover tensor shapes from a checkpoint without unpickling it.

A .ckpt is a pickle and community submissions run on our runner, so nothing in
this module may execute a byte of what it reads.

torch.load(weights_only=True) is NOT the answer. It is necessary and not
sufficient: it refuses all 360 of the lab's own checkpoints, because Lightning
pickled eda_ml.schema.ModelConfig into every one. Verified, 360 scanned, 360
refused. The resulting error suggests turning the flag off, which is the
arbitrary-code-execution path this module exists to avoid. An allowlist of safe
globals is refused too, because it is a list somebody has to keep being right
about.

What happens instead: the file is opened as the zip it is, archive/data.pkl is
walked with an Unpickler whose find_class returns an inert placeholder CLASS for
any foreign global, and shapes are read from the third argument of each
torch._utils._rebuild_tensor_v2 call. find_class must return a class rather than
an instance, because the NEWOBJ opcode requires a type.
"""

from __future__ import annotations

import pickle
import zipfile
from collections import OrderedDict
from math import prod
from pathlib import Path
from typing import Any

_REBUILD = "torch._utils._rebuild_tensor_v2"
_SHAPE_ARG = 2
"""_rebuild_tensor_v2(storage, storage_offset, size, stride, requires_grad, ...).

`size` is the third argument. Read positionally, because the call arrives as a
pickle REDUCE and carries no parameter names.
"""

_STATE_DICT_KEYS = ("state_dict", "model_state_dict")
_WEIGHT_SUFFIX = ".weight"


class _Inert:
    """Stands in for any global the pickle names. Constructs nothing real.

    Every method here exists because some pickle opcode may call it during
    reconstruction. None of them do anything: the object records the arguments it
    was handed and is otherwise a hole in the graph.
    """

    qualname = "?"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.args = args
        self.kwargs = kwargs
        self.state: Any = None

    def __setstate__(self, state: Any) -> None:
        self.state = state

    def __repr__(self) -> str:
        return f"<inert {self.qualname}>"


_PLACEHOLDERS: dict[str, type[_Inert]] = {}


def _placeholder(module: str, name: str) -> type[_Inert]:
    key = f"{module}.{name}"
    if key not in _PLACEHOLDERS:
        _PLACEHOLDERS[key] = type(f"Inert_{name}", (_Inert,), {"qualname": key})
    return _PLACEHOLDERS[key]


class _RestrictedUnpickler(pickle.Unpickler):
    """Reads the pickle's SHAPE and never its meaning.

    find_class resolves nothing. It hands back a placeholder class for every
    global, including ones that look harmless, so there is no allowlist to get
    wrong and no import to be tricked into. OrderedDict is the single exception
    and is taken from the standard library rather than from the file, purely so
    the state dict comes back as a mapping we can iterate.
    """

    _CONTAINERS = {("collections", "OrderedDict"): OrderedDict}

    def find_class(self, module: str, name: str) -> Any:
        container = self._CONTAINERS.get((module, name))
        if container is not None:
            return container
        return _placeholder(module, name)

    def persistent_load(self, pid: Any) -> Any:
        """Storage records are persistent ids. They carry no shape, so they are
        replaced by their own id and never resolved to bytes."""
        return ("storage", pid)


def _data_pkl_name(archive: zipfile.ZipFile) -> str:
    for name in archive.namelist():
        if name.endswith("/data.pkl") or name == "data.pkl":
            return name
    raise ValueError("checkpoint contains no data.pkl")


def read_state_dict_shapes(path: Path) -> dict[str, tuple[int, ...]]:
    """Parameter name to tensor shape, read without executing anything.

    Raises ValueError on a file that is not a checkpoint-shaped zip, or that
    carries no state dict. A silent empty dict here would report a model with no
    architecture as a model that parsed fine.
    """
    if not zipfile.is_zipfile(path):
        raise ValueError(f"{path} is not a zip archive, so it is not a checkpoint")

    with zipfile.ZipFile(path) as archive:
        with archive.open(_data_pkl_name(archive)) as handle:
            payload = _RestrictedUnpickler(handle).load()

    if not isinstance(payload, dict):
        raise ValueError(f"{path} does not unpack to a mapping")

    state: Any = None
    for key in _STATE_DICT_KEYS:
        if key in payload:
            state = payload[key]
            break
    if not isinstance(state, dict) or not state:
        raise ValueError(f"{path} carries no usable state dict")

    shapes: dict[str, tuple[int, ...]] = {}
    for name, value in state.items():
        qualname = getattr(value, "qualname", "")
        if qualname != _REBUILD:
            continue
        args = getattr(value, "args", ())
        if len(args) <= _SHAPE_ARG:
            raise ValueError(f"{path}: {name} has no recoverable size argument")
        size = args[_SHAPE_ARG]
        shapes[str(name)] = tuple(int(n) for n in size)

    if not shapes:
        raise ValueError(f"{path} carries no rebuildable tensors")
    return shapes


def mlp_widths(shapes: dict[str, tuple[int, ...]]) -> tuple[int, ...]:
    """Layer widths for a plain feed-forward stack, input first.

    A Linear weight is (out_features, in_features), so the input width is the
    second dimension of the first weight and every later width is the first
    dimension of the next. The lab's fixed MLP comes back as 41, 64, 32, 16, 1
    while its hparams.yaml claims an input width of 7.
    """
    weights = [
        shape
        for name, shape in shapes.items()
        if name.endswith(_WEIGHT_SUFFIX) and len(shape) == 2
    ]
    if not weights:
        return ()
    return (weights[0][1], *(shape[0] for shape in weights))


def param_count(shapes: dict[str, tuple[int, ...]]) -> int:
    """Total trainable parameters, derived from the shapes and nothing else.

    hparams.yaml reports params 0 for every layer, so it cannot be used here.
    """
    return sum(prod(shape) for shape in shapes.values())
```

- [ ] **Step 5: Build the checkpoint fixture**

Create `tests/fixtures/ckpt/build_fixture.py`:

```python
"""Write a checkpoint-shaped zip with the lab's exact geometry.

The lab's own .ckpt files are trained weights under CC BY-NC-SA and are not ours
to redistribute, so CI reads this instead. The GEOMETRY is the lab's, read off a
real file, and tests/test_ckpt.py asserts the real file agrees whenever
EDA_EXPERIMENTS points at the tree.

Run: uv run python tests/fixtures/ckpt/build_fixture.py
"""

from __future__ import annotations

import pickle
import sys
import types
import zipfile
from collections import OrderedDict
from pathlib import Path

SHAPES = {
    "scalar_encoder.net.0.weight": (64, 41),
    "scalar_encoder.net.0.bias": (64,),
    "scalar_encoder.net.2.weight": (32, 64),
    "scalar_encoder.net.2.bias": (32,),
    "scalar_encoder.net.4.weight": (16, 32),
    "scalar_encoder.net.4.bias": (16,),
    "scalar_encoder.net.6.weight": (1, 16),
    "scalar_encoder.net.6.bias": (1,),
}


def _install_stub_modules() -> None:
    """Give pickle a torch._utils._rebuild_tensor_v2 and an eda_ml class to name.

    These exist only inside this generator, so the emitted bytes carry the same
    global references a real checkpoint does. Nothing imports them at read time;
    tools/ckpt.py replaces every global with a placeholder.
    """
    torch = types.ModuleType("torch")
    utils = types.ModuleType("torch._utils")

    def _rebuild_tensor_v2(*args: object) -> object:
        raise AssertionError("the reader must never call this")

    utils._rebuild_tensor_v2 = _rebuild_tensor_v2  # type: ignore[attr-defined]
    torch._utils = utils  # type: ignore[attr-defined]
    sys.modules["torch"] = torch
    sys.modules["torch._utils"] = utils

    eda_ml = types.ModuleType("eda_ml")
    schema = types.ModuleType("eda_ml.schema")

    class ModelConfig:
        """The class Lightning pickled into all 360 real checkpoints."""

    schema.ModelConfig = ModelConfig  # type: ignore[attr-defined]
    eda_ml.schema = schema  # type: ignore[attr-defined]
    sys.modules["eda_ml"] = eda_ml
    sys.modules["eda_ml.schema"] = schema


class _Tensor:
    def __init__(self, shape: tuple[int, ...]) -> None:
        self.shape = shape

    def __reduce__(self) -> tuple[object, tuple[object, ...]]:
        from torch._utils import _rebuild_tensor_v2  # noqa: PLC0415

        stride = tuple(1 for _ in self.shape)
        return _rebuild_tensor_v2, (("storage", 0), 0, self.shape, stride, False)


def main() -> int:
    _install_stub_modules()
    from eda_ml.schema import ModelConfig  # noqa: PLC0415

    payload = {
        "epoch": 24,
        "global_step": 50,
        "pytorch-lightning_version": "2.4.0",
        "state_dict": OrderedDict(
            (name, _Tensor(shape)) for name, shape in SHAPES.items()
        ),
        "hyper_parameters": {"config": ModelConfig()},
    }
    out = Path(__file__).resolve().parent / "lab_mlp.ckpt"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("archive/data.pkl", pickle.dumps(payload, protocol=2))
        archive.writestr("archive/version", "3\n")
    print(f"wrote {out} ({out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Run: `uv run python tests/fixtures/ckpt/build_fixture.py`
Expected: a file well under 10 KB, so nowhere near the 1 MB limit.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_ckpt.py tests/test_no_unpickle.py -v`
Expected: 10 passed, 1 skipped (the real-checkpoint test, unless `EDA_EXPERIMENTS` is set)

- [ ] **Step 7: Prove it against the real tree**

```bash
EDA_EXPERIMENTS=~/Downloads/eda-ml-models uv run pytest tests/test_ckpt.py -v
```

Expected: 11 passed. This is the step that turns the plan's stated geometry into a checked fact, and it is in the phase gate.

- [ ] **Step 8: Commit**

```bash
git add tools/ckpt.py tools/yamlsafe.py tests/test_ckpt.py tests/test_no_unpickle.py tests/fixtures/ckpt
git commit -m "feat(ingest): read checkpoint shapes and hparams without unpickling"
```

---

### Task 4: Shards

One file per `(task, pdk, stage)`, serving all of that task's metric cells, exactly as `CLAUDE.md` specifies.
Twenty of them exist; the other 212 combos have no file and that is a first-class state, not a gap.

**Files:**
- Create: `tools/ingest.py`
- Modify: `pyproject.toml`, `Makefile`
- Create: `data/cells/**` (generated)
- Test: `tests/test_ingest.py`

**Interfaces:**
- Consumes: `tools.paths`, `tools.evallog`, `tools.ckpt`, `tools.registry`.
- Produces: `ingest.MetricValue`, `ingest.Entry`, `ingest.Shard`, `ingest.shard_path(task_id, pdk_id, stage_id) -> Path`, `ingest.combo_shard(combo: ComboPath) -> Shard`, `ingest.to_json(shard) -> str`, `ingest.main() -> int`, the `eda-ingest` console script.

**Why `value_pooled` is null on every entry.** The contract forbids ingesting the `Overall` block, and pooling cannot be recomputed from `eval.log` because the file publishes per-circuit aggregates and not row counts. So the model side carries a macro-mean only, `ranked_on` is `"macro"`, and the published pooled figure that the cell page shows as "as published" comes from `data/baseline.json`. That is option 2 of open decision 1, implemented as data rather than as a code comment. The field exists and is null so that a later macro-mean recomputation of the baseline does not need a schema change.

**Why the baseline side is aggregated too.** It is never published. It is written into the shard as `cross_check`, and Task 7 compares it against `data/baseline.json` for the same cell. That comparison is the **only** detector for a percent error on MAPE, because MAPE is unbounded above and no range guard is possible. It works offline in CI because the number is committed.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ingest.py`:

```python
"""Shards: shape, contents and the rules that must not drift.

Expected values live here, in tests. They must never appear in tools/.
"""

from __future__ import annotations

import json

import pytest

from tools import ingest, paths
from tools import registry as reg
from tests.test_paths import TREE

COMBO = paths.discover(TREE)[0]


def test_the_shard_path_is_keyed_on_task_pdk_and_stage() -> None:
    """Cell identity is (task, metric, pdk, stage); a SHARD is keyed at
    (task, pdk, stage) and serves all of that task's metric rows."""
    path = ingest.shard_path("total_area_prediction", "ng45", "floorplan")
    assert path.parts[-3:] == ("total_area_prediction", "ng45", "floorplan.json")


def test_one_shard_carries_one_entry_per_model() -> None:
    shard = ingest.combo_shard(COMBO)
    assert (shard.task, shard.pdk, shard.stage) == (
        "total_area_prediction",
        "ng45",
        "floorplan",
    )
    assert len(shard.entries) == 1


def test_every_entry_declares_its_source() -> None:
    """make validate fails on any record without one."""
    shard = ingest.combo_shard(COMBO)
    assert [e.source for e in shard.entries] == ["submission"]


def test_the_metric_set_is_a_subset_of_the_tasks_registry_row() -> None:
    entry = ingest.combo_shard(COMBO).entries[0]
    assert set(entry.metrics) <= set(reg.task(COMBO.task).metrics)


def test_mape_is_stored_as_the_fraction_the_log_already_holds() -> None:
    """NOT rescaled. The log says 0.0364 for ac97_ctrl and the macro-mean over 18
    circuits is 0.046544, which is 4.65 percent."""
    entry = ingest.combo_shard(COMBO).entries[0]
    assert round(entry.metrics["mape"].macro, 6) == 0.046544
    assert entry.metrics["mape"].macro < 1.0


def test_mae_is_the_macro_mean_and_not_the_pooled_overall_figure() -> None:
    entry = ingest.combo_shard(COMBO).entries[0]
    assert round(entry.metrics["mae"].macro, 4) == 911.9777
    assert entry.metrics["mae"].macro != 909.6265  # the Overall line


def test_pooled_is_null_because_the_overall_block_is_never_ingested() -> None:
    entry = ingest.combo_shard(COMBO).entries[0]
    assert all(v.pooled is None for v in entry.metrics.values())
    assert {v.ranked_on for v in entry.metrics.values()} == {"macro"}


def test_r2_carries_a_median_and_a_positive_count() -> None:
    entry = ingest.combo_shard(COMBO).entries[0]
    assert round(entry.metrics["r2"].macro, 4) == -2.2821
    assert entry.metrics["r2"].n_positive == 0


def test_the_baseline_cross_check_is_recorded_but_never_published() -> None:
    """The baseline side of eval.log is aggregated the same way and written as
    cross_check. It is the only detector for a percent error on MAPE, and it is
    committed so the check works in CI without the 34 MB tree."""
    shard = ingest.combo_shard(COMBO)
    assert round(shard.cross_check["mae"], 4) == 1789.5997
    assert round(shard.cross_check["mape"], 6) == 0.124217
    assert "cross_check" not in {f for e in shard.entries for f in vars(e)}


def test_the_number_of_circuits_is_recorded_on_every_metric() -> None:
    """An aggregate over 16 of 18 circuits is a plausible number. This is what
    makes it visible in the data rather than only at parse time."""
    entry = ingest.combo_shard(COMBO).entries[0]
    assert {v.n_circuits for v in entry.metrics.values()} == {len(reg.circuits())}


def test_a_saturated_cell_still_carries_its_measurement() -> None:
    """Saturated cells are never RANKED. That is a display and ordering rule, not
    a reason to discard a real measurement, and the cell page still lists the
    entry."""
    combo = paths.ComboPath(
        task=COMBO.task,
        family=COMBO.family,
        config=COMBO.config,
        pdk=COMBO.pdk,
        stage="global_route",
        directory=COMBO.directory,
    )
    shard = ingest.combo_shard(combo)
    assert reg.is_saturated(shard.task, "mae", "global_route")
    assert shard.entries[0].metrics["mae"].macro > 0


def test_a_void_combo_is_refused(tmp_path) -> None:
    """The registry says the cell does not exist. A shard for it would resurrect
    40 cells the paper says are not there."""
    combo = paths.ComboPath(
        task="total_wirelength_prediction",
        family="fixed_mlp",
        config="default_config",
        pdk="ng45",
        stage="floorplan",
        directory=COMBO.directory,
    )
    assert reg.is_void(combo.task, combo.stage)
    with pytest.raises(ValueError):
        ingest.combo_shard(combo)


def test_the_json_round_trips_and_is_deterministic() -> None:
    shard = ingest.combo_shard(COMBO)
    assert ingest.to_json(shard) == ingest.to_json(ingest.combo_shard(COMBO))
    payload = json.loads(ingest.to_json(shard))
    assert set(payload) == {
        "task",
        "pdk",
        "stage",
        "generated_from",
        "cross_check",
        "entries",
    }
    assert set(payload["entries"][0]) == {
        "model_id",
        "model_label",
        "family",
        "source",
        "architecture",
        "metrics",
    }


def test_the_architecture_comes_from_shapes_when_a_checkpoint_is_present() -> None:
    """The fixture tree has no checkpoints, so architecture is None there and the
    field still exists. The real tree fills it in; Task 4 Step 6 checks that."""
    entry = ingest.combo_shard(COMBO).entries[0]
    assert entry.architecture is None or entry.architecture["widths"][0] == 41
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_ingest.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'tools.ingest'`

- [ ] **Step 3: Implement**

Create `tools/ingest.py`:

```python
"""Turn the lab's results tree into shards under data/cells/.

One file per (task, pdk, stage), serving every metric cell of that task. Twenty
exist. The other 212 live combos have no file at all, which is what a leaderboard
with no submissions actually looks like.

Three rules that are silent when broken:

  * eval.log MAPE is ALREADY A FRACTION and is stored unchanged.
  * aggregation is macro-mean over the 18 circuits, median plus a positive count
    for R2. The "Overall" block is pooled and is never ingested.
  * the baseline side is aggregated too, written as cross_check, and compared
    against data/baseline.json by tools/checks/ingest.py. That comparison is the
    only detector for a percent error on MAPE, which has no possible range guard.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tools import ckpt, evallog
from tools import registry as reg
from tools.paths import ComboPath, discover

ROOT = Path(__file__).resolve().parent.parent
CELLS_DIR = ROOT / "data" / "cells"

SUBMISSION = "submission"
MACRO = "macro"

LAB_MODEL_ID = "lab-fixed-mlp"
LAB_MODEL_LABEL = "EDA-Schema lab, fixed MLP"


@dataclass(frozen=True, slots=True)
class MetricValue:
    """One metric's aggregate for one entry.

    `macro` is what ranking reads. `pooled` is None on every ingested entry: the
    Overall block is forbidden and eval.log publishes no row counts to pool with.
    `ranked_on` names the basis in the data rather than in code, so changing it
    later is a visible diff.
    """

    macro: float
    pooled: float | None
    ranked_on: str
    n_circuits: int
    n_positive: int | None


@dataclass(frozen=True, slots=True)
class Entry:
    """One model's results for one combo."""

    model_id: str
    model_label: str
    family: str
    source: str
    architecture: dict[str, Any] | None
    metrics: dict[str, MetricValue]


@dataclass(frozen=True, slots=True)
class Shard:
    """Every entry for one (task, pdk, stage)."""

    task: str
    pdk: str
    stage: str
    generated_from: str
    cross_check: dict[str, float] = field(default_factory=dict)
    entries: tuple[Entry, ...] = ()


def shard_path(task_id: str, pdk_id: str, stage_id: str) -> Path:
    """data/cells/<task>/<pdk>/<stage>.json.

    Ids come from the registry, so this raises on a typo rather than writing a
    file nothing will ever read.
    """
    return (
        CELLS_DIR
        / reg.task(task_id).id
        / reg.pdk(pdk_id).id
        / f"{reg.stage(stage_id).id}.json"
    )


def _architecture(combo: ComboPath) -> dict[str, Any] | None:
    """Widths and parameter count from one checkpoint's tensor shapes.

    One checkpoint per architecture is enough: every circuit in a combo trains the
    same network. Returns None when the tree carries no checkpoint, which is the
    case for the committed fixture.

    hparams.yaml is deliberately not consulted. It reports in_features 7 where the
    trained weight is (64, 41), and params 0 for every layer.
    """
    found = sorted(combo.directory.rglob("*.ckpt"))
    if not found:
        return None
    shapes = ckpt.read_state_dict_shapes(found[0])
    return {
        "widths": list(ckpt.mlp_widths(shapes)),
        "params": ckpt.param_count(shapes),
        "source": "checkpoint_tensor_shapes",
    }


def combo_shard(combo: ComboPath) -> Shard:
    """Read one combo directory into a Shard.

    Refuses a void combo outright. The registry says those cells do not exist, and
    a shard for one puts a fabricated entry into a structural hole.
    """
    if reg.is_void(combo.task, combo.stage):
        raise ValueError(f"refusing to ingest a void combo: {combo.task} {combo.stage}")

    rows = evallog.parse(combo.eval_log.read_text(encoding="utf-8"))
    known = set(reg.task(combo.task).metrics)

    model = evallog.aggregate(rows, side="model")
    unknown = sorted(set(model) - known)
    if unknown:
        raise ValueError(f"{combo.eval_log} reports metrics {unknown} for this task")

    metrics = {
        metric_id: MetricValue(
            macro=value,
            pooled=None,
            ranked_on=MACRO,
            n_circuits=len(rows),
            n_positive=positive,
        )
        for metric_id, (value, positive) in model.items()
    }
    baseline = evallog.aggregate(rows, side="baseline")

    entry = Entry(
        model_id=LAB_MODEL_ID,
        model_label=LAB_MODEL_LABEL,
        family=combo.family,
        source=SUBMISSION,
        architecture=_architecture(combo),
        metrics=metrics,
    )
    return Shard(
        task=combo.task,
        pdk=combo.pdk,
        stage=combo.stage,
        generated_from=combo.eval_log.name,
        cross_check={metric_id: value for metric_id, (value, _) in baseline.items()},
        entries=(entry,),
    )


def to_json(shard: Shard) -> str:
    """Serialize deterministically. Keys are written in a fixed order."""
    payload = {
        "task": shard.task,
        "pdk": shard.pdk,
        "stage": shard.stage,
        "generated_from": shard.generated_from,
        "cross_check": shard.cross_check,
        "entries": [
            {
                "model_id": entry.model_id,
                "model_label": entry.model_label,
                "family": entry.family,
                "source": entry.source,
                "architecture": entry.architecture,
                "metrics": {
                    metric_id: {
                        "macro": value.macro,
                        "pooled": value.pooled,
                        "ranked_on": value.ranked_on,
                        "n_circuits": value.n_circuits,
                        "n_positive": value.n_positive,
                    }
                    for metric_id, value in entry.metrics.items()
                },
            }
            for entry in shard.entries
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    """Regenerate data/cells/ from a results tree. Entry point for `eda-ingest`."""
    parser = argparse.ArgumentParser(description="ingest the lab's results tree")
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()

    combos = discover(args.source)
    if not combos:
        print(f"ingest: no combos found under {args.source}, refusing to write nothing")
        return 1

    written = 0
    for combo in combos:
        shard = combo_shard(combo)
        destination = shard_path(shard.task, shard.pdk, shard.stage)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(to_json(shard), encoding="utf-8")
        written += 1

    tasks = sorted({c.task for c in combos})
    print(
        f"ingest: wrote {written} shards for {len(tasks)} task(s): {', '.join(tasks)}"
    )
    return 0
```

- [ ] **Step 4: Wire up the entry point**

In `pyproject.toml`, extend `[project.scripts]`:

```toml
[project.scripts]
eda-validate = "tools.validate:main"
eda-baseline = "tools.baseline:main"
eda-ingest = "tools.ingest:main"
```

In the `Makefile`, replace the `ingest` recipe's command with the console script and point `EXPERIMENTS` at a tree that exists:

```make
EXPERIMENTS ?= ~/Downloads/eda-ml-models

ingest:
	@if [ ! -f tools/ingest.py ]; then echo "ingest: tools/ingest.py does not exist yet (Phase 4)"; exit 1; fi; uv run eda-ingest --source $(EXPERIMENTS)
```

`python -m tools.ingest` is replaced for the same reason `eda-validate` is a console script: running a module as `__main__` gives the process two copies of it, and the second one's caches and registrations are invisible to the first.

`ingest` stays **out** of `check`. Regenerating tracked files as a side effect of the gate would let a changed source tree silently rewrite committed data instead of failing, and Task 7's check is the detector that reports rather than repairs.

- [ ] **Step 5: Generate the shards**

Run: `make ingest`
Expected: `ingest: wrote 20 shards for 1 task(s): total_area_prediction`

Then confirm the shape:

```bash
find data/cells -name '*.json' | wc -l          # 20
du -sh data/cells                                # kilobytes, not megabytes
uv run python -c "
import json, pathlib
p = pathlib.Path('data/cells/total_area_prediction/ng45/floorplan.json')
d = json.loads(p.read_text())
m = d['entries'][0]['metrics']
print('mape macro', m['mape']['macro'])
print('mae  macro', m['mae']['macro'])
print('r2 median', m['r2']['macro'], 'positive', m['r2']['n_positive'])
print('arch', d['entries'][0]['architecture'])
print('cross_check', d['cross_check'])
"
```

Expected: `mape macro 0.0465...` (a fraction, not 4.65), `mae macro 911.977...`, `r2 median -2.28... positive 0`, `arch {'widths': [41, 64, 32, 16, 1], 'params': 5313, ...}`, `cross_check {'mae': 1789.599..., 'mape': 0.12421..., 'r2': -26.86...}`.

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/test_ingest.py -v`
Expected: 14 passed

- [ ] **Step 7: Commit**

```bash
git add tools/ingest.py pyproject.toml Makefile data/cells tests/test_ingest.py
git commit -m "feat(ingest): write 20 shards from the lab's results tree"
```

---

### Task 5: Ranking

Direction, bias, sentinels and cell state.
Every one of them is a place the pre-reset build got it wrong or never checked.

**Files:**
- Create: `tools/ranking.py`
- Test: `tests/test_ranking.py`

**Interfaces:**
- Consumes: `tools.registry`, `tools.baseline` (`Bound`, `BoundKind`).
- Produces:
  - `ranking.Comparison` (StrEnum: `BETTER`, `EQUAL`, `WORSE`, `UNDECIDABLE`)
  - `ranking.CellState` (StrEnum: `BEATS_BASELINE`, `MATCHES_BASELINE`, `BASELINE_LEADS`, `NO_ENTRY`, `SATURATED`)
  - `ranking.rank_key(metric_id: str, value: float) -> float`
  - `ranking.compare(task_id: str, metric_id: str, challenger: Bound, incumbent: Bound) -> Comparison`
  - `ranking.cell_state(task_id: str, metric_id: str, stage_id: str, baseline: Bound, entries: tuple[Bound, ...]) -> CellState`
  - `ranking.bias_sort_key(values: Mapping[str, float]) -> tuple[float, ...]`
  - `ranking.BIAS_ORDER: tuple[str, ...]`
  - `ranking.PERCENT_SCALE: float` (the ONLY x100 in the project; Phase 5's
    `cellpage.format_value` imports it rather than carrying its own literal)

**Four values, not a bool.** Against `MAPE > 10000 %` a submission at 15000 % is genuinely undecidable, and against `R^2 < -1` one at -3 is too. That is 32 cells where guessing would publish a verdict the paper's own data cannot support.

**Equality is decided at display precision, and the scaling happens before the rounding.** Percent metrics are stored as fractions, so rounding the fraction to 2 decimals makes 12.43 % and 12.49 % both round to `0.12` and compare **equal**. That bug shipped once. `_display_units` multiplies by 100 first and then rounds.

**This is not a second display boundary.** `_display_units` is private, returns a float, is called only by the equality quantizer, and never produces a string or reaches a template. The one place a number becomes display text is Phase 5's `cellpage.format_value`. A test asserts `ranking` exports no formatter.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ranking.py`:

```python
"""Ranking: direction, bias, sentinels and cell state.

Expected values live here, in tests. They must never appear in tools/.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest

from tools import ranking
from tools import registry as reg
from tools.baseline import Bound, BoundKind


def exact(value: float) -> Bound:
    return Bound(BoundKind.EXACT, value)


def test_rank_key_is_always_ascending_best_first() -> None:
    assert ranking.rank_key("mae", 1.0) < ranking.rank_key("mae", 2.0)
    assert ranking.rank_key("r2", 0.9) < ranking.rank_key("r2", 0.1)


def test_rank_key_reads_the_registry_and_nothing_else(
    mutable_registry: Path,
) -> None:
    """THE test for this module. The pre-reset suite passed with metric direction
    hardcoded, so it never touched the registry at all. Flip a direction in a temp
    copy and rank_key must follow it."""
    assert reg.metric("mae").direction == "lower"
    assert ranking.rank_key("mae", 5.0) == 5.0

    path = mutable_registry / "metrics.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    for row in rows:
        if row["id"] == "mae":
            row["direction"] = "higher"
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    _clear_registry_caches()

    assert reg.metric("mae").direction == "higher"
    assert ranking.rank_key("mae", 5.0) == -5.0


def test_a_lower_challenger_beats_a_lower_is_better_baseline() -> None:
    assert (
        ranking.compare("total_area_prediction", "mae", exact(900.0), exact(1781.97))
        is ranking.Comparison.BETTER
    )


def test_a_higher_challenger_beats_a_higher_is_better_baseline() -> None:
    assert (
        ranking.compare("total_area_prediction", "r2", exact(0.5), exact(0.1))
        is ranking.Comparison.BETTER
    )


def test_equality_is_decided_at_display_precision() -> None:
    """r2 is published to 3 decimals, so 0.9994 and 0.9996 are the same number as
    far as the paper is concerned."""
    assert reg.precision("total_area_prediction", "r2") == 3
    assert (
        ranking.compare("total_area_prediction", "r2", exact(0.9994), exact(0.9996))
        is ranking.Comparison.EQUAL
    )


def test_percent_metrics_scale_to_display_units_BEFORE_rounding() -> None:
    """0.1243 and 0.1249 are 12.43 % and 12.49 %, which differ at 2 decimals.
    Rounding the FRACTION to 2 decimals makes both 0.12 and reports EQUAL. That
    bug shipped."""
    assert reg.metric("mape").percent
    assert reg.precision("total_area_prediction", "mape") == 2
    assert round(0.1243, 2) == round(0.1249, 2), "the trap, stated"
    assert (
        ranking.compare("total_area_prediction", "mape", exact(0.1243), exact(0.1249))
        is ranking.Comparison.BETTER
    )


def test_a_non_percent_metric_is_not_scaled() -> None:
    assert (
        ranking.compare(
            "total_area_prediction", "mae", exact(1781.971), exact(1781.972)
        )
        is ranking.Comparison.EQUAL
    )


def test_an_absent_baseline_is_undecidable_and_never_a_win() -> None:
    """The 24 degenerate cells. Table 8 published a 0/0 there, not a zero, and
    awarding beats_baseline against a baseline that was never measured is the
    exact failure the contract names."""
    assert (
        ranking.compare(
            "worst_slack_prediction", "mpe", exact(0.0), Bound(BoundKind.ABSENT, None)
        )
        is ranking.Comparison.UNDECIDABLE
    )


def test_a_submission_on_the_defined_side_of_an_upper_sentinel_wins() -> None:
    """Published "> 10000 %", stored as GREATER_THAN 100.0. The true value is
    strictly above 100.0, so anything at or below it is strictly better."""
    upper = Bound(BoundKind.GREATER_THAN, 100.0)
    assert (
        ranking.compare("net_arc_delay_prediction", "mape", exact(50.0), upper)
        is ranking.Comparison.BETTER
    )


def test_a_submission_beyond_an_upper_sentinel_is_undecidable_not_a_loss() -> None:
    """150 as a fraction is 15000 %. The paper thresholded the real number away,
    so which of the two is worse is unknowable and must not be guessed."""
    upper = Bound(BoundKind.GREATER_THAN, 100.0)
    assert (
        ranking.compare("net_arc_delay_prediction", "mape", exact(150.0), upper)
        is ranking.Comparison.UNDECIDABLE
    )


def test_a_submission_on_the_defined_side_of_a_lower_sentinel_wins() -> None:
    lower = Bound(BoundKind.LESS_THAN, -1.0)
    assert (
        ranking.compare("net_arc_delay_prediction", "r2", exact(-0.5), lower)
        is ranking.Comparison.BETTER
    )


def test_a_submission_below_a_lower_sentinel_is_undecidable() -> None:
    lower = Bound(BoundKind.LESS_THAN, -1.0)
    assert (
        ranking.compare("net_arc_delay_prediction", "r2", exact(-3.0), lower)
        is ranking.Comparison.UNDECIDABLE
    )


def test_saturation_short_circuits_every_other_rule() -> None:
    """A stage-and-task rule, never a numeric test. Saturated cells are never
    ranked and never coloured win or loss, whatever the entries say."""
    assert (
        ranking.cell_state(
            "total_area_prediction",
            "mae",
            "global_route",
            exact(0.0),
            (exact(0.0),),
        )
        is ranking.CellState.SATURATED
    )


def test_the_two_wirelength_tasks_are_still_rankable_at_global_route() -> None:
    assert (
        ranking.cell_state(
            "total_wirelength_prediction",
            "mae",
            "global_route",
            exact(13698.67),
            (exact(500.0),),
        )
        is ranking.CellState.BEATS_BASELINE
    )


def test_no_entries_is_no_entry() -> None:
    assert (
        ranking.cell_state(
            "total_area_prediction", "mae", "floorplan", exact(1781.97), ()
        )
        is ranking.CellState.NO_ENTRY
    )


def test_entirely_undecidable_entries_collapse_to_no_entry() -> None:
    """Phase 5 relies on this exactly: a degenerate row still LISTS its entries
    while its state reads no_entry. State colours the row; entries decide what is
    listed."""
    assert (
        ranking.cell_state(
            "worst_slack_prediction",
            "mpe",
            "cts",
            Bound(BoundKind.ABSENT, None),
            (exact(0.5),),
        )
        is ranking.CellState.NO_ENTRY
    )


def test_matching_is_a_real_state_and_not_a_loss() -> None:
    """Tying is the best achievable outcome on roughly 132 cells. Folding this
    into baseline_leads renders a submission that hit the optimum as a loss."""
    assert (
        ranking.cell_state(
            "total_area_prediction", "r2", "cts", exact(1.0), (exact(1.0),)
        )
        is ranking.CellState.MATCHES_BASELINE
    )


def test_a_win_outranks_a_tie_in_the_same_cell() -> None:
    assert (
        ranking.cell_state(
            "total_area_prediction",
            "mae",
            "floorplan",
            exact(1781.97),
            (exact(1781.97), exact(900.0)),
        )
        is ranking.CellState.BEATS_BASELINE
    )


def test_only_losses_is_baseline_leads() -> None:
    assert (
        ranking.cell_state(
            "total_area_prediction",
            "mae",
            "floorplan",
            exact(1781.97),
            (exact(9000.0),),
        )
        is ranking.CellState.BASELINE_LEADS
    )


def test_mpe_leads_the_slack_sort_and_mne_breaks_the_tie() -> None:
    """Optimistic error leads because an optimistic timing prediction HIDES a real
    violation, and that is the failure with silicon consequences. The paper gives
    no exchange rate, so the preference is sort order and never a weighted blend.

    An earlier draft of the contract ranked on mne first, which makes the
    PREFERRED error the dominant key: a model with a huge optimistic error and a
    tiny conservative one would win."""
    assert ranking.BIAS_ORDER == ("optimistic", "conservative")
    low_mpe = ranking.bias_sort_key({"mpe": 0.1, "mne": 9.0})
    high_mpe = ranking.bias_sort_key({"mpe": 0.2, "mne": 0.1})
    assert low_mpe < high_mpe

    tied = ranking.bias_sort_key({"mpe": 0.1, "mne": 0.5})
    assert ranking.bias_sort_key({"mpe": 0.1, "mne": 0.2}) < tied


def test_the_bias_metrics_are_selected_from_the_registry() -> None:
    """Not by name. mpe is optimistic and mne conservative in metrics.json, and
    that is where the pairing lives."""
    biased = {m.bias: m.id for m in reg.metrics() if m.bias}
    assert biased == {"optimistic": "mpe", "conservative": "mne"}


def test_ranking_exports_no_formatter() -> None:
    """The x100 for display happens in exactly one place, and it is not here.
    _display_units is private, returns a float, and feeds only the quantizer."""
    public = [n for n in dir(ranking) if not n.startswith("_")]
    assert not [n for n in public if "format" in n or "display" in n]
```

Add the shared fixture to `tests/conftest.py` (create it if Phase 3 did not):

```python
@pytest.fixture
def mutable_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A writable copy of data/registry/ with every loader cache cleared.

    Phase 1 ships the same fixture in tests/test_mutations.py. Lift it here so
    Phase 4 does not grow a second, drifting copy of the cache list.
    """
    dest = tmp_path / "registry"
    shutil.copytree(reg.REGISTRY_DIR, dest)
    monkeypatch.setattr(reg, "REGISTRY_DIR", dest)
    _clear_registry_caches()
    yield dest
    _clear_registry_caches()
```

`_clear_registry_caches()` calls `cache_clear()` on every `@cache`d loader in `tools/registry.py`, exactly as Phase 1's fixture does.

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_ranking.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'tools.ranking'`

- [ ] **Step 3: Implement**

Create `tools/ranking.py`:

```python
"""Order entries, compare them against the baseline, and colour the cell.

Direction is read from the registry and from nowhere else. Hardcoding it was one
of the three mutations the pre-reset suite survived, and a hardcoded direction
ranks a whole metric backwards without raising anything.

Comparison is four-valued on purpose. A published sentinel is a one-sided bound
with no underlying number, so against "MAPE > 10000 %" a submission at 15000 % is
genuinely undecidable, and so is one at R^2 -3 against "< -1". Guessing on those
32 cells would publish a verdict the paper's data cannot support.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import StrEnum
from functools import cache

from tools import registry as reg
from tools.baseline import Bound, BoundKind

PERCENT_SCALE = 100.0
"""The one place the x100 happens.

Public, and imported rather than re-declared, because the contract's central
rule is that a percent metric is scaled EXACTLY ONCE at the display boundary.
A second copy is not a duplicate constant, it is a second boundary. Phase 5's
cellpage.format_value must import this rather than carry its own 100.0
literal, and a test asserts exactly one definition exists under tools/."""

HIGHER = "higher"

BIAS_ORDER = ("optimistic", "conservative")
"""Sort keys for the slack tasks, most consequential first.

Optimistic error leads because an optimistic timing prediction hides a real
violation. The paper gives no numeric exchange rate between the two, so the
preference is expressed purely as sort order and never as a weighted blend.
"""


class Comparison(StrEnum):
    BETTER = "better"
    EQUAL = "equal"
    WORSE = "worse"
    UNDECIDABLE = "undecidable"


class CellState(StrEnum):
    BEATS_BASELINE = "beats_baseline"
    MATCHES_BASELINE = "matches_baseline"
    BASELINE_LEADS = "baseline_leads"
    NO_ENTRY = "no_entry"
    SATURATED = "saturated"


def rank_key(metric_id: str, value: float) -> float:
    """Ascending, best first, whatever the metric's direction is.

    The direction comes from metrics.json. This function is the reason that file
    has a direction column at all, and tests/test_ranking.py mutates the file to
    prove the read actually happens.
    """
    return -value if reg.metric(metric_id).direction == HIGHER else value


def _display_units(metric_id: str, value: float) -> float:
    """Storage units to display units, for ROUNDING only.

    Private, returns a float, and is called by _quantize and nothing else. It
    produces no string and reaches no template, so it is not a second display
    boundary: formatting for humans happens once, in Phase 5's cellpage.

    The scaling has to precede the rounding. Percent metrics are stored as
    fractions, so rounding 0.1243 and 0.1249 to the metric's 2 decimals makes
    both 0.12 and reports two different published numbers as equal.
    """
    return value * PERCENT_SCALE if reg.metric(metric_id).percent else value


def _quantize(task_id: str, metric_id: str, value: float) -> float:
    return round(_display_units(metric_id, value), reg.precision(task_id, metric_id))


def compare(
    task_id: str, metric_id: str, challenger: Bound, incumbent: Bound
) -> Comparison:
    """How `challenger` stands against `incumbent` on this cell.

    UNDECIDABLE is returned rather than a guess whenever the paper's own value
    does not exist:

      * either side ABSENT, which is the 24 degenerate cells
      * a sentinel incumbent that the challenger does not clear. A sentinel always
        points AWAY from the good direction, so a challenger on the defined side
        of the threshold is a decidable win and anything past it is unknowable.
      * a sentinel challenger, which only a submission could produce
    """
    if challenger.kind is BoundKind.ABSENT or incumbent.kind is BoundKind.ABSENT:
        return Comparison.UNDECIDABLE
    if challenger.value is None or incumbent.value is None:
        raise ValueError(f"a non-absent bound with no value: {challenger} {incumbent}")

    if incumbent.kind is not BoundKind.EXACT:
        if challenger.kind is not BoundKind.EXACT:
            return Comparison.UNDECIDABLE
        clears = (
            challenger.value <= incumbent.value
            if incumbent.kind is BoundKind.GREATER_THAN
            else challenger.value >= incumbent.value
        )
        return Comparison.BETTER if clears else Comparison.UNDECIDABLE

    if challenger.kind is not BoundKind.EXACT:
        return Comparison.UNDECIDABLE

    mine = _quantize(task_id, metric_id, challenger.value)
    theirs = _quantize(task_id, metric_id, incumbent.value)
    if mine == theirs:
        return Comparison.EQUAL
    return (
        Comparison.BETTER
        if rank_key(metric_id, mine) < rank_key(metric_id, theirs)
        else Comparison.WORSE
    )


def cell_state(
    task_id: str,
    metric_id: str,
    stage_id: str,
    baseline: Bound,
    entries: Sequence[Bound],
) -> CellState:
    """The state that colours one cell.

    Saturation is checked first and short-circuits everything, because a saturated
    cell is never ranked and never coloured win or loss. It is a stage-and-task
    lookup in the registry, never a predicate over values: a test like
    `mae == 0 and mape == 0 and r2 == 1` catches only 5 of the 10 saturated tasks,
    and 16 of the saturated cells are rates sitting at their ceiling.

    Every entry being UNDECIDABLE collapses to NO_ENTRY, which is exactly what
    happens against an ABSENT baseline. The state colours the row; the caller's
    own entry list decides what gets LISTED. Deciding what to list from the state
    hides real submissions on all 24 degenerate cells.
    """
    if reg.is_saturated(task_id, metric_id, stage_id):
        return CellState.SATURATED

    verdicts = [compare(task_id, metric_id, entry, baseline) for entry in entries]
    decided = [v for v in verdicts if v is not Comparison.UNDECIDABLE]
    if not decided:
        return CellState.NO_ENTRY
    if Comparison.BETTER in decided:
        return CellState.BEATS_BASELINE
    if Comparison.EQUAL in decided:
        return CellState.MATCHES_BASELINE
    return CellState.BASELINE_LEADS


@cache
def _bias_metrics() -> tuple[str, ...]:
    """The metric ids carrying a directional bias, most consequential first.

    Selected by the registry's `bias` attribute rather than by name, so the
    pairing lives in metrics.json where the contract put it.
    """
    by_bias = {m.bias: m.id for m in reg.metrics() if m.bias is not None}
    missing = [b for b in BIAS_ORDER if b not in by_bias]
    if missing:
        raise ValueError(f"no metric carries bias {missing}")
    return tuple(by_bias[bias] for bias in BIAS_ORDER)


def bias_sort_key(values: Mapping[str, float]) -> tuple[float, ...]:
    """Order slack entries: optimistic error first, conservative error second.

    Both are magnitudes to minimize, but they are not interchangeable. An earlier
    draft ranked on the conservative metric first, which makes the PREFERRED error
    the dominant key and lets a model with a huge optimistic error and a tiny
    conservative one take first place.

    A metric the entry does not report sorts last rather than as zero, because a
    missing measurement is not a perfect one.
    """
    return tuple(
        rank_key(metric_id, values[metric_id]) if metric_id in values else float("inf")
        for metric_id in _bias_metrics()
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_ranking.py -v`
Expected: 22 passed

- [ ] **Step 5: Verify lint and types**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy`
Expected: all clean

- [ ] **Step 6: Commit**

```bash
git add tools/ranking.py tests/test_ranking.py tests/conftest.py
git commit -m "feat(ranking): four-valued comparison, cell state and the slack bias"
```

---

### Task 6: The shard reader, and build.py calling ranking

**The reason this phase exists in this shape.** The pre-reset build shipped a 217-line ranking module with zero non-test consumers, so it was only ever tested against itself. Ranking gets its consumer in the same commit range that creates it.

**Files:**
- Create: `tools/shards.py`
- Modify: `tools/ranking.py`, `build.py`, `templates/pages/matrix.html`
- Test: `tests/test_shards.py`, `tests/test_matrix_states.py`

**Interfaces:**
- Consumes: `tools.ingest` (`shard_path`), `tools.registry`, `tools.baseline`, `tools.ranking`.
- Produces:
  - `shards.Record` (fields `task`, `metric`, `pdk`, `stage`, `model_id`, `model_label`, `source`, `value_macro`, `value_pooled`, `ranked_on`, `n_circuits`, `n_positive`)
  - `shards.load(task_id: str, pdk_id: str, stage_id: str) -> tuple[Record, ...]`
  - `shards.bound_of(record: Record) -> Bound`
  - `shards.populated_combos() -> tuple[tuple[str, str, str], ...]`
  - `ranking.rank_of(task_id: str, metric_id: str, pdk_id: str, stage_id: str, value: float) -> int | None`
  - `ranking.percentile_of(task_id: str, metric_id: str, pdk_id: str, stage_id: str, value: float) -> float | None`

`rank_of` and `percentile_of` exist because Phase 6's plausibility layer needs them, and the alternative is a second copy of the ordering rule in `tools/guard/`. Two copies of a rule that has to encode the `mpe` before `mne` bias will not stay identical.

**Record is flattened per metric.** `ingest.Entry` holds one model's whole metric set for a combo, which is the right shape to write; `shards.Record` is one `(metric, model)` pair, which is the right shape for a ranking table. `shards.load` is the only conversion between the two.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_shards.py`:

```python
"""Reading shards back, and the states the matrix will show.

Expected values live here, in tests. They must never appear in tools/.
"""

from __future__ import annotations

from tools import baseline, ranking
from tools import registry as reg
from tools import shards


def test_exactly_the_total_area_combos_carry_data() -> None:
    """One task has data, at 20 of the 232 live combos. The other 212 are empty
    and that is a first-class state, not a gap to fill."""
    populated = shards.populated_combos()
    assert len(populated) == 20
    assert {c[0] for c in populated} == {"total_area_prediction"}
    assert {c[1] for c in populated} == {p.id for p in reg.pdks()}
    assert {c[2] for c in populated} == {s.id for s in reg.stages()}


def test_a_combo_with_no_shard_loads_as_empty_rather_than_raising() -> None:
    assert shards.load("cell_arc_slew_prediction", "asap7", "cts") == ()


def test_records_are_flattened_one_per_metric_and_model() -> None:
    records = shards.load("total_area_prediction", "ng45", "floorplan")
    assert {r.metric for r in records} == set(reg.task("total_area_prediction").metrics)
    assert {r.model_id for r in records} == {"lab-fixed-mlp"}
    assert {r.source for r in records} == {"submission"}


def test_every_record_declares_the_basis_it_is_ranked_on() -> None:
    """Open decision 1, resolved as data. Ranking is on macro-mean; the pooled
    figure the paper published stays visible as the baseline's own number."""
    records = shards.load("total_area_prediction", "ng45", "floorplan")
    assert {r.ranked_on for r in records} == {"macro"}
    assert all(r.value_pooled is None for r in records)


def test_the_shard_values_are_the_ones_ingest_wrote() -> None:
    records = shards.load("total_area_prediction", "ng45", "floorplan")
    by_metric = {r.metric: r.value_macro for r in records}
    assert round(by_metric["mae"], 4) == 911.9777
    assert round(by_metric["mape"], 6) == 0.046544


def test_the_lab_model_beats_the_published_baseline_on_area_at_floorplan() -> None:
    """The end-to-end claim of this phase, in one assertion. 911.98 against a
    published 1,781.97."""
    records = shards.load("total_area_prediction", "ng45", "floorplan")
    mae = next(r for r in records if r.metric == "mae")
    bound = baseline.lookup("total_area_prediction", "mae", "ng45", "floorplan").bound
    assert (
        ranking.cell_state(
            "total_area_prediction",
            "mae",
            "floorplan",
            bound,
            (shards.bound_of(mae),),
        )
        is ranking.CellState.BEATS_BASELINE
    )


def test_forty_eight_rankable_cells_have_data() -> None:
    """20 combos x 3 metrics is 60, of which the 4 global_route combos x 3 are
    saturated and never ranked. Derived, not asserted from the shards' own view of
    themselves."""
    filled = {
        (r.task, r.metric, r.pdk, r.stage)
        for combo in shards.populated_combos()
        for r in shards.load(*combo)
    }
    rankable = {
        c
        for c in filled
        if not reg.is_saturated(c[0], c[1], c[3])
        and not reg.is_degenerate(c[0], c[1], c[3])
    }
    assert len(filled) == 60
    assert len(rankable) == 48


def test_rank_of_orders_by_the_registrys_direction() -> None:
    records = shards.load("total_area_prediction", "ng45", "floorplan")
    mae = next(r for r in records if r.metric == "mae")
    assert (
        ranking.rank_of("total_area_prediction", "mae", "ng45", "floorplan", 1.0) == 1
    )
    assert (
        ranking.rank_of(
            "total_area_prediction", "mae", "ng45", "floorplan", mae.value_macro + 1.0
        )
        == 2
    )


def test_percentile_of_is_none_on_an_empty_cell() -> None:
    assert (
        ranking.percentile_of("cell_arc_slew_prediction", "mae", "asap7", "cts", 1.0)
        is None
    )
```

Create `tests/test_matrix_states.py`:

```python
"""build.py must CALL ranking, and the matrix must show the result.

The pre-reset build shipped a ranking module with no non-test consumer. This file
is the assertion that it has one.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from tools import ranking
from tools import registry as reg

ROOT = Path(__file__).resolve().parent.parent


def test_build_py_imports_ranking() -> None:
    tree = ast.parse((ROOT / "build.py").read_text(encoding="utf-8"))
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
        if node.module == "tools"
    }
    assert "ranking" in imported


def test_every_cell_carries_exactly_one_known_state(site: Path) -> None:
    html = (site / "index.html").read_text(encoding="utf-8")
    found = re.findall(r'data-state="([a-z_]+)"', html)
    assert len(found) == 880
    assert set(found) <= {s.value for s in ranking.CellState}


def test_the_matrix_shows_real_comparison_states_now() -> None:
    """Before this phase every live cell was no_entry or saturated. The 20 real
    combos are what turn that into a leaderboard."""
    html = (ROOT / "dist" / "index.html").read_text(encoding="utf-8")
    comparison = {
        ranking.CellState.BEATS_BASELINE.value,
        ranking.CellState.MATCHES_BASELINE.value,
        ranking.CellState.BASELINE_LEADS.value,
    }
    found = set(re.findall(r'data-state="([a-z_]+)"', html))
    assert found & comparison, "no cell shows a comparison; ranking is not wired in"


def test_the_saturated_count_is_unchanged_by_real_data(site: Path) -> None:
    """Saturation is a stage rule. Adding real entries at global_route must not
    move a single cell out of it."""
    html = (site / "index.html").read_text(encoding="utf-8")
    found = re.findall(r'data-state="([a-z_]+)"', html)
    assert found.count(ranking.CellState.SATURATED.value) == 120


def test_no_cell_renders_undefined_nan_or_null(site: Path) -> None:
    html = (site / "index.html").read_text(encoding="utf-8")
    for bad in ("undefined", "NaN", "None", "null"):
        assert bad not in html, bad
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_shards.py tests/test_matrix_states.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'tools.shards'`

- [ ] **Step 3: Implement the reader**

Create `tools/shards.py`:

```python
"""Read data/cells/ back, flattened one row per (metric, model).

ingest.Entry is the right shape to WRITE: one model's whole metric set for a
combo. Record is the right shape to RANK: one metric, one model. This module is
the only conversion between the two, so the ranking table and the shard file
cannot grow separate ideas of what a row is.

A combo with no shard loads as an empty tuple rather than raising. 212 of the 232
live combos have no data at all, and that is what a new leaderboard looks like.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache

from tools import registry as reg
from tools.baseline import Bound, BoundKind
from tools.ingest import shard_path


@dataclass(frozen=True, slots=True)
class Record:
    """One model's result on one metric cell."""

    task: str
    metric: str
    pdk: str
    stage: str
    model_id: str
    model_label: str
    source: str
    value_macro: float
    value_pooled: float | None
    ranked_on: str
    n_circuits: int
    n_positive: int | None


@cache
def load(task_id: str, pdk_id: str, stage_id: str) -> tuple[Record, ...]:
    """Every record for one combo, in file order. Empty when no shard exists."""
    path = shard_path(task_id, pdk_id, stage_id)
    if not path.exists():
        return ()

    payload = json.loads(path.read_text(encoding="utf-8"))
    if (payload["task"], payload["pdk"], payload["stage"]) != (
        task_id,
        pdk_id,
        stage_id,
    ):
        raise ValueError(f"{path} declares a different combo than its own location")

    known = set(reg.task(task_id).metrics)
    records: list[Record] = []
    for entry in payload["entries"]:
        if not entry.get("source"):
            raise ValueError(f"{path}: an entry carries no source")
        for metric_id, value in entry["metrics"].items():
            if metric_id not in known:
                raise ValueError(f"{path}: metric {metric_id!r} is not on this task")
            records.append(
                Record(
                    task=task_id,
                    metric=metric_id,
                    pdk=pdk_id,
                    stage=stage_id,
                    model_id=entry["model_id"],
                    model_label=entry["model_label"],
                    source=entry["source"],
                    value_macro=value["macro"],
                    value_pooled=value["pooled"],
                    ranked_on=value["ranked_on"],
                    n_circuits=value["n_circuits"],
                    n_positive=value["n_positive"],
                )
            )
    return tuple(records)


def bound_of(record: Record) -> Bound:
    """A record as the Bound that ranking compares.

    A submission always carries an exact number. Only a published baseline can be
    a one-sided bound, because only the paper thresholded a value away.
    """
    return Bound(BoundKind.EXACT, record.value_macro)


@cache
def populated_combos() -> tuple[tuple[str, str, str], ...]:
    """Live combos that have a shard on disk, in registry order."""
    return tuple(combo for combo in reg.live_combos() if load(*combo))
```

- [ ] **Step 4: Add the two functions Phase 6 will need**

Append to `tools/ranking.py`, importing `shards` inside the functions to keep the module import-cycle free:

```python
def _ordered_values(
    task_id: str, metric_id: str, pdk_id: str, stage_id: str
) -> list[float]:
    """Every submitted value on this cell, best first."""
    from tools import shards  # noqa: PLC0415

    values = [
        r.value_macro
        for r in shards.load(task_id, pdk_id, stage_id)
        if r.metric == metric_id
    ]
    return sorted(values, key=lambda v: rank_key(metric_id, v))


def rank_of(
    task_id: str, metric_id: str, pdk_id: str, stage_id: str, value: float
) -> int | None:
    """Where `value` would place on this cell, 1-based. None on an empty cell.

    Shared with Phase 6's plausibility layer rather than reimplemented there. Two
    copies of an ordering rule that has to encode the mpe-before-mne bias will not
    stay identical.
    """
    ordered = _ordered_values(task_id, metric_id, pdk_id, stage_id)
    if not ordered:
        return None
    key = rank_key(metric_id, value)
    return sum(1 for other in ordered if rank_key(metric_id, other) < key) + 1


def percentile_of(
    task_id: str, metric_id: str, pdk_id: str, stage_id: str, value: float
) -> float | None:
    """Share of submitted values this one is at least as good as, in [0, 1].

    None on an empty cell, deliberately: 0.0 would read as "worst on the cell"
    when the truth is "there is no cell to be worst on".
    """
    ordered = _ordered_values(task_id, metric_id, pdk_id, stage_id)
    if not ordered:
        return None
    key = rank_key(metric_id, value)
    return sum(1 for other in ordered if rank_key(metric_id, other) >= key) / len(
        ordered
    )
```

- [ ] **Step 5: Wire ranking into build.py**

In `build.py`, add `from tools import ranking, shards` to the imports and replace whatever Phase 3 put in the cell's `state` field:

```python
def cell_context(
    task_id: str, metric_id: str, pdk_id: str, stage_id: str
) -> dict[str, Any]:
    """Everything the template needs for one cell. All computation lands here.

    Templates hold loops and conditionals only, so the state string is decided in
    Python and the template just prints it.
    """
    bound = baseline.lookup(task_id, metric_id, pdk_id, stage_id).bound
    entries = tuple(
        shards.bound_of(record)
        for record in shards.load(task_id, pdk_id, stage_id)
        if record.metric == metric_id
    )
    state = ranking.cell_state(task_id, metric_id, stage_id, bound, entries)
    return {
        "task": task_id,
        "metric": metric_id,
        "pdk": pdk_id,
        "stage": stage_id,
        "state": state.value,
        "entry_count": len(entries),
    }
```

The matrix template already renders `data-state="{{ cell.state }}"` from Phase 3; nothing there changes except that the value is now computed rather than constant.

- [ ] **Step 6: Build and look at it**

Run: `make build && uv run pytest tests/test_shards.py tests/test_matrix_states.py -v`
Expected: 14 passed

Then count what actually changed:

```bash
uv run python -c "
import re, pathlib, collections
html = pathlib.Path('dist/index.html').read_text()
print(collections.Counter(re.findall(r'data-state=\"([a-z_]+)\"', html)))
"
du -sh dist; ls -l dist/index.html
```

Expected: 880 cells, 120 `saturated`, a nonzero count of at least one comparison state, and the rest `no_entry`.

**Watch the page weight here.** Phase 3 measured the grid at 74.4 KiB with every cell `no_entry` and 88.0 KiB in the worst case where every cell reads `matches_baseline`, against an 88 KB per-page cap. This is the phase that lights those states up, so this is the phase where the cap can break. **Do not raise the cap.** Phase 3 documents the escalation lever: split the matrix into one page per stage at `/stage/<id>/`. Pull that lever if `dist/index.html` exceeds the budget.

- [ ] **Step 7: Run the full suite**

Run: `make check`
Expected: lint clean, mypy clean, validate clean, all tests pass, build succeeds.

- [ ] **Step 8: Commit**

```bash
git add tools/shards.py tools/ranking.py build.py tests/test_shards.py tests/test_matrix_states.py
git commit -m "feat(matrix): rank the 20 real combos against the published baseline"
```

---

### Task 7: The divergence check and the mutations

The gate on the phase.
Every mutation here ships a believable number, and a believable wrong number is worse than a crash.

**Files:**
- Create: `tools/checks/ingest.py`
- Modify: `tools/checks/__init__.py`
- Test: `tests/test_ingest_check.py`

**Interfaces:**
- Consumes: `tools.shards`, `tools.baseline`, `tools.registry`, `tools.checks.register`.
- Produces:
  - `checks.ingest.check() -> list[str]`, registered as `"ingest"` in `tools.checks.CHECKS`
  - `checks.ingest.DIVERGENCE_FACTOR: float`
  - `checks.ingest.divergence(observed: float, published: float) -> float`

**The cross-check is the only percent detector that works on MAPE.** `tpr` and `tnr` are true rates, so `0 <= v <= 1` catches a 100x error outright. MAPE is unbounded above; its ceiling is the `> 10000 %` sentinel, which is `100.0` stored, and 28 published cells legitimately exceed 150 %. A range guard there would reject real data. What does work is comparing our aggregate of the baseline side of `eval.log` against `data/baseline.json` for the same cell: a systematic 100x offset is invisible per cell and unmistakable as a ratio.

Measured on `total_area_prediction` at NG45 floorplan, correct code gives `1789.5997 / 1781.97 = 1.004` for MAE and `0.124217 / 0.1243 = 0.9993` for MAPE. A `x100` at ingest gives `100.05`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ingest_check.py`:

```python
"""The ingest check, and the mutations it must catch.

Written against the registry, the baseline and the raw shard JSON rather than
against tools/ingest.py, so a shared misreading cannot self-confirm.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from tools import baseline, ingest
from tools import registry as reg
from tools import shards
from tools.checks import CHECKS
from tools.checks import ingest as check_mod


@pytest.fixture
def mutable_cells(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    dest = tmp_path / "cells"
    shutil.copytree(ingest.CELLS_DIR, dest)
    monkeypatch.setattr(ingest, "CELLS_DIR", dest)
    shards.load.cache_clear()
    shards.populated_combos.cache_clear()
    yield dest
    shards.load.cache_clear()
    shards.populated_combos.cache_clear()


def _rewrite(path: Path, mutate: Callable[[dict[str, Any]], None]) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    mutate(payload)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    shards.load.cache_clear()
    shards.populated_combos.cache_clear()


def _ng45_floorplan(root: Path) -> Path:
    return root / "total_area_prediction" / "ng45" / "floorplan.json"


def test_the_check_is_registered() -> None:
    assert "ingest" in CHECKS


def test_the_check_passes_on_the_committed_shards() -> None:
    assert check_mod.check() == []


def test_the_divergence_ratio_is_symmetric() -> None:
    """A 100x error and a 0.01x error are the same magnitude of wrong."""
    assert check_mod.divergence(100.0, 1.0) == check_mod.divergence(1.0, 100.0)
    assert check_mod.divergence(1.0, 1.0) == 1.0


def test_the_real_data_sits_far_inside_the_threshold() -> None:
    """1789.5997 against a published 1,781.97 is 1.004. The pooled and macro-mean
    estimators differ by 0.4 percent on this design-level task; the detector fires
    at an order of magnitude and is not measuring that difference."""
    assert check_mod.divergence(1789.5997, 1781.97) < 1.01
    assert check_mod.divergence(0.124217, 0.1243) < 1.01
    assert check_mod.DIVERGENCE_FACTOR >= 10.0


def test_a_percent_error_on_mape_is_caught(mutable_cells: Path) -> None:
    """THE mutation this phase exists to prevent. It raises nothing, no range
    guard on MAPE is possible, and the result looks like a finding: every MAPE
    cell quietly reads baseline_leads."""

    def mutate(payload: dict[str, Any]) -> None:
        payload["cross_check"]["mape"] *= 100
        for entry in payload["entries"]:
            entry["metrics"]["mape"]["macro"] *= 100

    _rewrite(_ng45_floorplan(mutable_cells), mutate)
    messages = check_mod.check()
    assert any("diverges" in m and "mape" in m for m in messages)


def test_the_same_error_on_mae_is_caught_too(mutable_cells: Path) -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["cross_check"]["mae"] *= 100

    _rewrite(_ng45_floorplan(mutable_cells), mutate)
    assert any("diverges" in m for m in check_mod.check())


def test_an_entry_without_a_source_is_caught(mutable_cells: Path) -> None:
    """make validate fails on any record lacking one."""

    def mutate(payload: dict[str, Any]) -> None:
        for entry in payload["entries"]:
            entry["source"] = ""

    _rewrite(_ng45_floorplan(mutable_cells), mutate)
    assert any("source" in m for m in check_mod.check())


def test_an_unknown_source_value_is_caught(mutable_cells: Path) -> None:
    def mutate(payload: dict[str, Any]) -> None:
        for entry in payload["entries"]:
            entry["source"] = "paper"

    _rewrite(_ng45_floorplan(mutable_cells), mutate)
    assert any("source" in m for m in check_mod.check())


def test_a_shard_on_a_void_combo_is_caught(mutable_cells: Path) -> None:
    """The registry says those 40 cells do not exist."""
    void = mutable_cells / "total_wirelength_prediction" / "ng45"
    void.mkdir(parents=True)
    payload = json.loads(_ng45_floorplan(mutable_cells).read_text(encoding="utf-8"))
    payload["task"] = "total_wirelength_prediction"
    (void / "floorplan.json").write_text(json.dumps(payload, indent=2) + "\n")
    shards.load.cache_clear()
    shards.populated_combos.cache_clear()
    assert any("void" in m for m in check_mod.check())


def test_a_metric_that_is_not_on_the_task_is_caught(mutable_cells: Path) -> None:
    def mutate(payload: dict[str, Any]) -> None:
        for entry in payload["entries"]:
            entry["metrics"]["tpr"] = dict(entry["metrics"]["mape"])

    _rewrite(_ng45_floorplan(mutable_cells), mutate)
    assert any("tpr" in m for m in check_mod.check())


def test_a_rate_outside_the_unit_interval_is_caught(mutable_cells: Path) -> None:
    """tpr and tnr are true rates, so the assertion is free. It is NOT extended to
    the MAPE family, which is unbounded above."""
    messages = check_mod._rate_failures(  # the layer, exercised directly
        task_id="worst_slack_prediction",
        metric_id="tpr",
        value=58.9,
    )
    assert messages


def test_no_ceiling_guard_exists_on_the_mape_family() -> None:
    """48 published cells would be rejected by a [0, 1.5] ceiling. The check must
    not have grown one."""
    assert (
        check_mod._rate_failures(
            task_id="cell_arc_slew_prediction", metric_id="mape", value=11.3469
        )
        == []
    )


def test_the_shard_count_matches_the_combos_on_disk() -> None:
    on_disk = sorted(ingest.CELLS_DIR.rglob("*.json"))
    assert len(on_disk) == len(shards.populated_combos()) == 20


def test_a_shard_filed_under_the_wrong_combo_is_caught(mutable_cells: Path) -> None:
    """The file's own task/pdk/stage must agree with its path, or a shard silently
    serves the wrong cell."""

    def mutate(payload: dict[str, Any]) -> None:
        payload["stage"] = "cts"

    _rewrite(_ng45_floorplan(mutable_cells), mutate)
    with pytest.raises(ValueError):
        shards.load("total_area_prediction", "ng45", "floorplan")
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_ingest_check.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'tools.checks.ingest'`

- [ ] **Step 3: Implement the check**

Create `tools/checks/ingest.py`:

```python
"""data/cells/ must agree with the registry and with the published baseline.

Four layers, each catching something the others cannot:

  1. structure  - the shard sits on a live, non-void combo and names only metrics
                  that belong to its task
  2. provenance - every entry declares a source, from the contract's vocabulary
  3. rates      - tpr and tnr land in [0, 1], which catches a 100x error outright
  4. divergence - our aggregate of the BASELINE side of eval.log against the
                  published Table 8 value for the same cell

Layer 4 is the only detector that works on MAPE. MAPE is unbounded above, its
ceiling is the "> 10000 %" sentinel, and 28 published cells legitimately exceed
150 %, so no range guard is possible. A systematic 100x offset is invisible per
cell and unmistakable as a ratio, which is why the ingest run records the
cross_check figure and commits it.

No count is written as a literal. Every expected set comes from tools.registry.
"""

from __future__ import annotations

import json

from tools import baseline, ingest
from tools import registry as reg
from tools import shards
from tools.checks import register

DIVERGENCE_FACTOR = 10.0
"""Flag at an order of magnitude.

Deliberately loose. The pooled and macro-mean estimators genuinely differ, by
0.4 % on the one design-level task with data and by more on the finer-grained
ones. This tripwire is for a unit error, not for an estimator difference, and
tightening it would make it fire on the thing the contract says to expect.
"""

ALLOWED_SOURCES = ("paper", "synthetic", "submission")


def divergence(observed: float, published: float) -> float:
    """How many times apart two numbers are, symmetrically and always >= 1.

    Returns infinity when exactly one side is zero, because "zero against 1781"
    is the largest divergence there is and must not come back as a ratio of 1.
    """
    if observed == 0.0 and published == 0.0:
        return 1.0
    if observed == 0.0 or published == 0.0:
        return float("inf")
    ratio = abs(observed / published)
    return ratio if ratio >= 1.0 else 1.0 / ratio


def _rate_failures(*, task_id: str, metric_id: str, value: float) -> list[str]:
    """A true rate cannot exceed 1. Nothing else gets a ceiling.

    Selection is by registry attribute: percent AND higher-is-better is exactly
    tpr and tnr. The percent metrics that are lower-is-better are the MAPE family,
    which is unbounded above, and a ceiling there would reject published data.
    """
    spec = reg.metric(metric_id)
    if not (spec.percent and spec.direction == "higher"):
        return []
    if 0.0 <= value <= 1.0:
        return []
    return [
        f"{task_id}/{metric_id}: rate {value} is outside the unit interval, "
        "which is the signature of a value stored in display units"
    ]


@register("ingest")
def check() -> list[str]:
    failures: list[str] = []
    live = set(reg.live_combos())

    for path in sorted(ingest.CELLS_DIR.rglob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        combo = (payload["task"], payload["pdk"], payload["stage"])
        task_id, pdk_id, stage_id = combo

        if reg.is_void(task_id, stage_id):
            failures.append(f"{combo}: a shard on a void combo, which has no cells")
            continue
        if combo not in live:
            failures.append(f"{combo}: not a live combo")
            continue

        known = set(reg.task(task_id).metrics)
        for entry in payload["entries"]:
            if entry.get("source") not in ALLOWED_SOURCES:
                failures.append(f"{combo}: entry source {entry.get('source')!r}")
            for metric_id, value in entry["metrics"].items():
                if metric_id not in known:
                    failures.append(
                        f"{combo}: metric {metric_id!r} is not on this task"
                    )
                    continue
                failures += _rate_failures(
                    task_id=task_id, metric_id=metric_id, value=value["macro"]
                )

        for metric_id, observed in payload.get("cross_check", {}).items():
            if metric_id not in known:
                failures.append(f"{combo}: cross_check names {metric_id!r}")
                continue
            if reg.is_degenerate(task_id, metric_id, stage_id):
                continue
            bound = baseline.lookup(task_id, metric_id, pdk_id, stage_id).bound
            if bound.value is None:
                continue
            ratio = divergence(observed, bound.value)
            if ratio > DIVERGENCE_FACTOR:
                failures.append(
                    f"{combo} {metric_id}: our baseline aggregate {observed} "
                    f"diverges {ratio:.1f}x from the published {bound.value}. "
                    "A systematic factor of 100 is a percent-storage error."
                )

    for combo in shards.populated_combos():
        if combo not in live:
            failures.append(f"{combo}: loaded but not live")

    return failures
```

Register it by appending to `tools/checks/__init__.py`:

```python
from tools.checks import ingest as _ingest  # noqa: E402,F401
```

- [ ] **Step 4: Run the tests and the validator**

Run: `uv run pytest tests/test_ingest_check.py -v && uv run eda-validate`
Expected: 14 passed; `validate: 3 checks, 0 failures`, exit 0

- [ ] **Step 5: Prove the percent mutation by hand, outside the suite**

```bash
uv run python -c "
from tools.checks import ingest as c
print('correct  ', round(c.divergence(0.124217, 0.1243), 4))
print('x100     ', round(c.divergence(12.4217, 0.1243), 1))
print('threshold', c.DIVERGENCE_FACTOR)
"
```

Expected: `correct 0.9993`-ish as `1.0007`, `x100 99.9`, `threshold 10.0`. The detector has roughly two orders of magnitude of headroom over the estimator difference it must not fire on.

- [ ] **Step 6: Run the full gate**

Run: `make check`
Expected: lint clean, mypy clean, `validate: 3 checks, 0 failures`, all tests pass, build succeeds.

- [ ] **Step 7: Commit and open the PR**

```bash
git add tools/checks/ingest.py tools/checks/__init__.py tests/test_ingest_check.py
git commit -m "test(ingest): pin the mutations that would ship believable numbers"
git push -u origin phase-4/ingest-ranking
gh pr create --title "Phase 4: ingest and ranking" --body "Ingests the lab's 20 total_area combos into data/cells/ and ships tools/ranking.py with build.py as its consumer. eval.log MAPE is stored as the fraction it already is; aggregation is macro-mean with a median and positive count for R2; the pooled Overall block, the CSV R2 columns and all tfevents are never read. Checkpoints are walked as zips and never unpickled. Comparison is four-valued so a sentinel baseline stays undecidable rather than guessed."
```

---

## Phase gate

Every item must pass before Phase 5 starts.

```bash
make ingest && make check
EDA_EXPERIMENTS=~/Downloads/eda-ml-models uv run pytest tests/test_ckpt.py -v
```

**Paths**

- [ ] all five stage names parse, including the three containing an underscore
- [ ] `rsplit("_", 2)` is proved wrong by an executable assertion, not a comment
- [ ] uppercase PDK directories normalize to the lowercase registry id, all four
- [ ] an unknown stage or PDK raises rather than returning `None`
- [ ] the real tree yields **exactly 20 combos**, one task, one family

**eval.log**

- [ ] all 18 per-circuit lines parse; a truncated log raises rather than aggregating a subset
- [ ] **MAPE is not rescaled**; the stored value stays a fraction below 1.0
- [ ] the `Overall` block is never parsed as a circuit, and its numbers reach no shard
- [ ] macro-mean differs from pooled on the fixture where they differ: 1789.5997 against 1781.9696
- [ ] R2 uses the **median** with a positive count: -26.8635 and 0 of 18, against a pooled 0.9892
- [ ] the CSV `baseline_r2` / `model_r2` columns and all tfevents are read by nothing

**Checkpoints and hparams**

- [ ] `read_state_dict_shapes` recovers `41 -> 64 -> 32 -> 16 -> 1` and 5,313 parameters
- [ ] the same shapes come back from a **real lab checkpoint** with `EDA_EXPERIMENTS` set
- [ ] `hparams.yaml`'s `in_features: 7` is parsed and then **ignored**
- [ ] `yaml.safe_load` is proved to raise on the real tag; the stripping loader constructs no foreign object
- [ ] the AST scan finds no `torch.load`, `pickle.load`, `yaml.full_load`, `UnsafeLoader`, `add_safe_globals` or a `weights_only` keyword anywhere in `tools/` or `build.py`
- [ ] `torch` is imported nowhere; `Unpickler` appears in exactly one file

**Shards**

- [ ] 20 shards under `data/cells/`, one per combo, none hand-edited
- [ ] every entry carries an explicit `source` from the contract's vocabulary
- [ ] every metric is a subset of that task's registry row
- [ ] `value_pooled` is null and `ranked_on` is `"macro"` on every record, which is open decision 1 recorded as data
- [ ] no shard exists on a void combo; saturated cells still carry their measurement
- [ ] 60 cells have data, of which **48 are rankable** and 12 are saturated

**Ranking**

- [ ] `rank_key` follows a direction flipped in a temp registry copy, proving the read happens
- [ ] equality is decided at display precision, with the `x100` applied **before** the rounding
- [ ] `compare` is four-valued; an `ABSENT` baseline is `UNDECIDABLE` and never a win
- [ ] a submission on the defined side of a sentinel wins; one past it is `UNDECIDABLE`, not a loss
- [ ] saturation short-circuits `cell_state`; the two wirelength tasks stay rankable at `global_route`
- [ ] `matches_baseline` is returned, not folded into `baseline_leads`
- [ ] `bias_sort_key` orders `mpe` before `mne`, selected by registry bias and not by name
- [ ] `ranking` exports no formatter

**The consumer**

- [ ] `build.py` imports `tools.ranking`; no module in this phase ships uncalled
- [ ] `dist/index.html` has 880 cells, 120 `saturated`, and at least one real comparison state
- [ ] no cell renders `undefined`, `NaN`, `None` or `null`
- [ ] `dist/index.html` is within the 88 KB per-page budget. Phase 3 measured 74.4 KiB empty and 88.0 KiB worst-case, so this is the phase where it can break. **Do not raise the cap**; pull Phase 3's escalation lever and split the matrix into one page per stage at `/stage/<id>/`.

**The check**

- [ ] `eda-validate` reports `3 checks, 0 failures`
- [ ] the divergence tripwire reads ~1.0 on correct data and ~100 on a `x100` mutation
- [ ] `tpr` and `tnr` are guarded to `[0, 1]`; **no ceiling guard exists on the MAPE family**
- [ ] all eight mutations are caught

## Review prompt

```
Use a data-integrity reviewer on tools/ingest.py, tools/evallog.py,
tools/ranking.py, tools/shards.py and data/cells/ against docs/DATA_CONTRACT.md
and this plan.

Trace one metric end to end, by hand and not through the test suite. Pick
ac97_ctrl at NG45 floorplan, find its line in the lab's eval.log, and confirm the
number that reaches data/cells/total_area_prediction/ng45/floorplan.json is that
value carried through the documented transformations and nothing else. State
which transformations you saw applied and in what order.

Then verify, independently of the test suite:
- eval.log MAPE is NOT rescaled anywhere on the ingest path, and the stored value
  is a fraction. This is the single most dangerous bug in the project.
- no code path reads the eval.log "Overall" block, aggregated_eval_metrics.csv's
  baseline_r2 or model_r2 columns, or any tfevents file
- MAE and MAPE are macro-mean over 18 circuits and R2 is a median with a positive
  count, and confirm the pooled R2 of 0.9892 appears in no shard while the
  per-circuit median is -26.86 with zero circuits positive
- metric direction is read from data/registry/metrics.json at every ranking
  decision and is hardcoded nowhere
- the x100 for percent metrics happens before rounding in ranking's equality
  quantizer, and nowhere else in tools/
- no path unpickles: confirm find_class returns an inert placeholder for EVERY
  foreign global, that there is no safe_globals allowlist, and that hparams.yaml
  is parsed by a loader that constructs no objects
- comparison against a sentinel baseline returns UNDECIDABLE rather than a
  guessed verdict, on both the > 10000 % and < -1 forms
- ranking is imported and called by build.py, not merely present

Finally apply each of these mutations to a COPY of the repo and confirm make
check fails: multiply every ingested mape by 100; replace the macro-mean with the
Overall MAE; replace the R2 median with a mean; hardcode metric direction to
"lower" in tools/ranking.py; delete the source field from one entry; add a shard
under total_wirelength_prediction/ng45/floorplan.json; round the percent
comparison before scaling it; return a bool from compare instead of the
four-valued Comparison. Report any mutation that does NOT fail.

Report only correctness gaps and unguarded values. Do not report style
preferences.
```
