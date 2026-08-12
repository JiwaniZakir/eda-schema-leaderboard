# Phase 1 - Registries Implementation Plan

> **For agentic workers:** Implement this plan task-by-task - either dispatch a fresh subagent per task (recommended) or execute inline with review checkpoints. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** rebuild the five registry files and the typed loader that is the only import path for vocabulary in this project.

**Architecture:** five JSON files under `data/registry/`, generated to match `docs/DATA_CONTRACT.md` Appendix A, plus `tools/registry.py` which loads them into frozen dataclasses and derives every count. A separate checker, `tools/checks/registry_csv.py`, diffs the registries against `docs/sources/table8_baseline.csv` as **sets**, so a shared misreading between the registry and its own tests cannot self-confirm.

**Tech stack:** Python 3.11+, `uv`, `pytest`, `mypy --strict`, `ruff`.

## Global constraints

Copied from `PLAN.md`; every task's requirements implicitly include these.

- Python **3.11+**, type hints on all public functions, `ruff` and `mypy` clean.
- **Registries are the only source of vocabulary.** Never hardcode a task, PDK, stage, metric or circuit name outside `data/registry/`.
- **Counts are derived, never literal.** 46, 232, 880, 856, 120, 40, 24 are computed and asserted, never written into source. `tests/` may assert them as expected values; `tools/` may not contain them.
- **Percent metrics** (`mape`, `mape_p95`, `mape_top5`, `tpr`, `tnr`) are stored as fractions in `[0, 1]`.
- Conventional commits. Branch `phase-1/registries`. Never push to `main`.
- **Never use an em dash** in prose, code comments or generated copy.

## Source of truth

`docs/DATA_CONTRACT.md` **Appendix A** contains every value needed. It was verified against the pre-reset registries before they were deleted: metrics 11/11, tasks 12/12, pdks 4/4, stages 5/5 exact. Read Appendix A, not this plan, for the values themselves. This plan gives structure and tests.

`docs/sources/table8_baseline.csv` is the independent cross-check. Its columns are `task,metric,stage_transition,pdk,value,kind,src_line` and its vocabulary is the `table8_label` of each registry entry.

## File structure

| File | Responsibility |
|---|---|
| `data/registry/circuits.json` | 18 circuits, Table 2 attributes |
| `data/registry/metrics.json` | 11 metrics: direction, bias, percent, precision |
| `data/registry/pdks.json` | 4 PDKs: metal layers, utilization |
| `data/registry/stages.json` | 5 stages: order, and the void/saturated/degenerate sets |
| `data/registry/tasks.json` | 12 tasks: unit, granularity, metrics[], precision overrides |
| `tools/registry.py` | typed loaders, lookups, cell classification, derived counts |
| `tools/checks/__init__.py` | the `CHECKS` registry |
| `tools/checks/registry_csv.py` | set-based cross-check against the CSV |
| `tools/validate.py` | `eda-validate` entry point, runs every registered check |
| `tests/test_registry.py` | loaders, partition, derived counts |
| `tests/test_registry_csv.py` | the cross-check itself |
| `tests/test_mutations.py` | the three regressions that passed pre-reset |

---

### Task 1: Restore packaging and the circuits registry

The smallest complete vertical slice: one JSON file, one dataclass, one loader, one test that fails for the right reason. It establishes the pattern the next four tasks repeat.

**Files:**
- Modify: `pyproject.toml`
- Create: `tools/__init__.py`, `tools/registry.py`
- Create: `data/registry/circuits.json`
- Test: `tests/test_registry.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `reg.Circuit`, `reg.circuits() -> tuple[Circuit, ...]`, and the private `reg._load(name: str) -> list[dict[str, Any]]` that every later loader reuses.

- [ ] **Step 1: Restore packaging**

In `pyproject.toml`, delete the `[tool.uv] package = false` block and the "RESTORE IN PHASE 1" comment block, then add back:

```toml
[project.scripts]
eda-validate = "tools.validate:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["tools"]
```

Set mypy's targets:

```toml
[tool.mypy]
python_version = "3.11"
strict = true
warn_unreachable = true
files = ["tools", "tests"]
```

`eda-validate` must be a real entry point, never `python -m tools.validate`. Running the module as `__main__` creates a second copy of it, so checks registering into `tools.validate.CHECKS` land in a different dict than the one `main()` reads and validation silently passes having done nothing. That bug shipped once already.

- [ ] **Step 2: Write the failing test**

Create `tests/test_registry.py`:

```python
"""Registry loading and derived counts.

Expected values live here, in tests. They must never appear in tools/.
"""

from __future__ import annotations

from tools import registry as reg


def test_eighteen_circuits_load() -> None:
    assert len(reg.circuits()) == 18


def test_circuit_ids_are_unique() -> None:
    ids = [c.id for c in reg.circuits()]
    assert len(ids) == len(set(ids))


def test_ethernet_attributes_match_table_2() -> None:
    """The pre-reset suite let ethernet.registers change 10,544 -> 87 and stayed
    green. This is the value, asserted directly."""
    eth = next(c for c in reg.circuits() if c.id == "ethernet")
    assert (eth.inputs, eth.outputs, eth.registers) == (96, 115, 10544)
```

- [ ] **Step 3: Run it to make sure it fails**

Run: `uv run pytest tests/test_registry.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'tools'`

- [ ] **Step 4: Create the circuits registry**

Create `data/registry/circuits.json` as a JSON array of 18 objects with keys `id`, `inputs`, `outputs`, `registers`, transcribed from the Circuits table in `docs/DATA_CONTRACT.md`. First and last for shape:

```json
[
  { "id": "ac97_ctrl", "inputs": 84, "outputs": 48, "registers": 2211 },
  { "id": "wb_dma", "inputs": 217, "outputs": 215, "registers": 521 }
]
```

- [ ] **Step 5: Write the loader**

Create `tools/__init__.py`:

```python
"""Pure functions for the EDA-Schema leaderboard.

Side effects belong in build.py and CLI entry points, never here.
"""

__version__ = "0.1.0"
```

Create `tools/registry.py`:

```python
"""Typed access to data/registry/.

This module is the ONLY import path for vocabulary. Nothing else in the project
may hardcode a task, metric, stage, PDK or circuit name.

Counts are derived here and asserted in tests. No count literal belongs in this
file.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

REGISTRY_DIR = Path(__file__).resolve().parent.parent / "data" / "registry"


@dataclass(frozen=True, slots=True)
class Circuit:
    id: str
    inputs: int
    outputs: int
    registers: int


@cache
def _load(name: str) -> tuple[dict[str, Any], ...]:
    """Read one registry file. Cached, so the JSON is parsed once per process."""
    path = REGISTRY_DIR / f"{name}.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{path} must be a non-empty JSON array")
    return tuple(rows)


@cache
def circuits() -> tuple[Circuit, ...]:
    return tuple(Circuit(**row) for row in _load("circuits"))
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_registry.py -v`
Expected: 3 passed

- [ ] **Step 7: Verify lint and types**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy`
Expected: all clean

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml tools/__init__.py tools/registry.py data/registry/circuits.json tests/test_registry.py
git commit -m "feat(registry): restore packaging and the circuits registry"
```

---

### Task 2: Metrics registry

Carries `direction`, which every ranking decision reads, and `percent`, which is the percent-storage rule in machine-readable form.

**Files:**
- Create: `data/registry/metrics.json`
- Modify: `tools/registry.py`
- Test: `tests/test_registry.py`

**Interfaces:**
- Consumes: `reg._load`.
- Produces: `reg.Metric`, `reg.metrics() -> tuple[Metric, ...]`, `reg.metric(metric_id: str) -> Metric`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_registry.py`:

```python
PERCENT_METRICS = {"mape", "mape_p95", "mape_top5", "tpr", "tnr"}
HIGHER_IS_BETTER = {"r2", "tpr", "tnr"}


def test_eleven_metrics_load() -> None:
    assert len(reg.metrics()) == 11


def test_every_metric_has_a_direction() -> None:
    for m in reg.metrics():
        assert m.direction in {"lower", "higher"}


def test_directions_are_correct() -> None:
    for m in reg.metrics():
        expected = "higher" if m.id in HIGHER_IS_BETTER else "lower"
        assert m.direction == expected, f"{m.id} direction is {m.direction}"


def test_percent_flag_is_exactly_the_documented_set() -> None:
    """This flag IS the percent-storage rule. Getting it wrong makes every MAPE
    cell render baseline_leads and every TPR/TNR cell render beats_baseline."""
    assert {m.id for m in reg.metrics() if m.percent} == PERCENT_METRICS


def test_slack_bias_is_encoded() -> None:
    """The paper ranks a pessimistic prediction above an optimistic one of equal
    magnitude. Ranking these as plain magnitude is a correctness bug."""
    assert reg.metric("mpe").bias == "optimistic"
    assert reg.metric("mne").bias == "conservative"
    assert all(m.bias is None for m in reg.metrics() if m.id not in {"mpe", "mne"})


def test_metric_lookup_rejects_unknown_ids() -> None:
    import pytest

    with pytest.raises(KeyError):
        reg.metric("not_a_metric")
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_registry.py -v`
Expected: FAIL, `AttributeError: module 'tools.registry' has no attribute 'metrics'`

- [ ] **Step 3: Create the metrics registry**

Create `data/registry/metrics.json` as an array of 11 objects with keys `id`, `label`, `long_label`, `table8_label`, `direction`, `bias`, `percent`, `precision`, transcribed from Appendix A's `metrics.json` table. Two for shape:

```json
[
  {
    "id": "mae", "label": "MAE", "long_label": "Mean Absolute Error",
    "table8_label": "MAE", "direction": "lower", "bias": null,
    "percent": false, "precision": 2
  },
  {
    "id": "mpe", "label": "MPE", "long_label": "Mean Positive Error",
    "table8_label": "MPE", "direction": "lower", "bias": "optimistic",
    "percent": false, "precision": 2
  }
]
```

- [ ] **Step 4: Add the loader**

Append to `tools/registry.py`, after `Circuit`:

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
    precision: int
```

and after `circuits()`:

```python
@cache
def metrics() -> tuple[Metric, ...]:
    return tuple(Metric(**row) for row in _load("metrics"))


@cache
def _metric_index() -> dict[str, Metric]:
    return {m.id: m for m in metrics()}


def metric(metric_id: str) -> Metric:
    """Look up one metric. Raises KeyError on an unknown id, deliberately: a
    silent default here would let a typo rank in the wrong direction."""
    try:
        return _metric_index()[metric_id]
    except KeyError:
        raise KeyError(f"unknown metric {metric_id!r}") from None
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_registry.py -v`
Expected: 9 passed

- [ ] **Step 6: Commit**

```bash
git add data/registry/metrics.json tools/registry.py tests/test_registry.py
git commit -m "feat(registry): add the metrics registry with direction and bias"
```

---

### Task 3: PDK and stage registries

Grouped because both are small and neither has a consumer without the other. The stage file also carries the three cell-classification sets, which Task 6 reads.

**Files:**
- Create: `data/registry/pdks.json`, `data/registry/stages.json`
- Modify: `tools/registry.py`
- Test: `tests/test_registry.py`

**Interfaces:**
- Consumes: `reg._load`.
- Produces: `reg.Pdk`, `reg.Stage`, `reg.pdks()`, `reg.stages()`, `reg.pdk(pdk_id)`, `reg.stage(stage_id)`. `stages()` returns stages **sorted by `order`**.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_registry.py`:

```python
STAGE_IDS_IN_ORDER = (
    "floorplan",
    "global_place",
    "detailed_place",
    "cts",
    "global_route",
)


def test_four_pdks_load() -> None:
    assert len(reg.pdks()) == 4


def test_pdk_physical_attributes_match_the_paper() -> None:
    """Pre-reset, ng45.metal_layers could become 99 and sky130.utilization 0.9
    with the suite still green."""
    layers = {p.id: p.metal_layers for p in reg.pdks()}
    assert layers == {"ng45": 10, "sky130": 5, "ihp130": 7, "asap7": 9}
    util = {p.id: p.utilization for p in reg.pdks()}
    assert util == {"ng45": 0.40, "sky130": 0.30, "ihp130": 0.30, "asap7": 0.40}


def test_five_stages_load() -> None:
    assert len(reg.stages()) == 5


def test_stage_ids_are_in_order_not_merely_a_set() -> None:
    """A test asserting sorted(orders) == range(1, n+1) passes on a FULLY
    REVERSED sequence. The pre-reset suite had exactly that hole. Assert the
    ids in sequence."""
    assert tuple(s.id for s in reg.stages()) == STAGE_IDS_IN_ORDER
    assert [s.order for s in reg.stages()] == [1, 2, 3, 4, 5]


def test_the_third_pdk_is_ihp_not_iph() -> None:
    """Table 8 misspells it IPH130 five times, once per stage group. A naive
    parse invents a phantom fifth PDK."""
    assert {p.id for p in reg.pdks()} == {"ng45", "sky130", "ihp130", "asap7"}
    assert not any("iph" in p.id.lower() for p in reg.pdks())
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_registry.py -v`
Expected: FAIL, `AttributeError: module 'tools.registry' has no attribute 'pdks'`

- [ ] **Step 3: Create both registries**

`data/registry/pdks.json`, four objects with keys `id`, `label`, `long_label`, `table8_label`, `metal_layers`, `utilization`, `utilization_sweep`, from Appendix A:

```json
[
  {
    "id": "ng45", "label": "NG45", "long_label": "Nangate 45 nm",
    "table8_label": "NG45", "metal_layers": 10, "utilization": 0.40,
    "utilization_sweep": [0.3, 0.4, 0.5]
  }
]
```

`data/registry/stages.json`, five objects with keys `id`, `label`, `table8_label`, `order`, `void_tasks`, `saturated_tasks`, `degenerate_tasks`, `degenerate_metrics`. Only `floorplan` and `global_route` have non-empty sets:

```json
[
  {
    "id": "floorplan", "label": "Floorplan",
    "table8_label": "floorplan to detailed route", "order": 1,
    "void_tasks": [
      "total_wirelength_prediction",
      "interconnect_length_prediction"
    ],
    "saturated_tasks": [], "degenerate_tasks": [], "degenerate_metrics": []
  }
]
```

`global_route` carries `saturated_tasks` as the ten tasks that are **not** `total_wirelength_prediction` or `interconnect_length_prediction`, `degenerate_tasks` as the three slack tasks, and `degenerate_metrics` as `["mpe", "mne"]`. Every other stage has four empty lists.

- [ ] **Step 4: Add the loaders**

Append the dataclasses to `tools/registry.py`:

```python
@dataclass(frozen=True, slots=True)
class Pdk:
    id: str
    label: str
    long_label: str
    table8_label: str
    metal_layers: int
    utilization: float
    utilization_sweep: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class Stage:
    id: str
    label: str
    table8_label: str
    order: int
    void_tasks: tuple[str, ...]
    saturated_tasks: tuple[str, ...]
    degenerate_tasks: tuple[str, ...]
    degenerate_metrics: tuple[str, ...]
```

and the loaders:

```python
@cache
def pdks() -> tuple[Pdk, ...]:
    return tuple(
        Pdk(**{**row, "utilization_sweep": tuple(row["utilization_sweep"])})
        for row in _load("pdks")
    )


@cache
def stages() -> tuple[Stage, ...]:
    """Always returned in `order`. Callers render the stage strip straight from
    this, so the sequence is part of the contract."""
    rows = [
        Stage(
            **{
                **row,
                "void_tasks": tuple(row["void_tasks"]),
                "saturated_tasks": tuple(row["saturated_tasks"]),
                "degenerate_tasks": tuple(row["degenerate_tasks"]),
                "degenerate_metrics": tuple(row["degenerate_metrics"]),
            }
        )
        for row in _load("stages")
    ]
    return tuple(sorted(rows, key=lambda s: s.order))


@cache
def _pdk_index() -> dict[str, Pdk]:
    return {p.id: p for p in pdks()}


@cache
def _stage_index() -> dict[str, Stage]:
    return {s.id: s for s in stages()}


def pdk(pdk_id: str) -> Pdk:
    try:
        return _pdk_index()[pdk_id]
    except KeyError:
        raise KeyError(f"unknown pdk {pdk_id!r}") from None


def stage(stage_id: str) -> Stage:
    try:
        return _stage_index()[stage_id]
    except KeyError:
        raise KeyError(f"unknown stage {stage_id!r}") from None
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_registry.py -v`
Expected: 14 passed

- [ ] **Step 6: Commit**

```bash
git add data/registry/pdks.json data/registry/stages.json tools/registry.py tests/test_registry.py
git commit -m "feat(registry): add the pdk and stage registries"
```

---

### Task 4: Tasks registry

**Files:**
- Create: `data/registry/tasks.json`
- Modify: `tools/registry.py`
- Test: `tests/test_registry.py`

**Interfaces:**
- Consumes: `reg._load`, `reg.metric`.
- Produces: `reg.Task`, `reg.tasks()`, `reg.task(task_id)`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_registry.py`:

```python
METRICS_PER_TASK = {
    "total_area_prediction": 3,
    "total_power_prediction": 3,
    "total_wirelength_prediction": 3,
    "interconnect_length_prediction": 7,
    "worst_arrival_time_prediction": 2,
    "worst_slack_prediction": 5,
    "total_negative_slack_prediction": 3,
    "timing_path_arrival_time_prediction": 6,
    "timing_path_slack_prediction": 5,
    "net_arc_delay_prediction": 3,
    "cell_arc_delay_prediction": 3,
    "cell_arc_slew_prediction": 3,
}


def test_twelve_tasks_load() -> None:
    assert len(reg.tasks()) == 12


def test_task_ids_keep_the_prediction_suffix() -> None:
    """The lab's own tooling and the on-disk results tree use these strings.
    Shortening them buys tidier URLs and costs a translation layer at every
    submission boundary."""
    assert all(t.id.endswith("_prediction") for t in reg.tasks())


def test_per_task_metric_counts_match_table_8() -> None:
    assert {t.id: len(t.metrics) for t in reg.tasks()} == METRICS_PER_TASK


def test_every_task_metric_exists_in_the_metric_registry() -> None:
    known = {m.id for m in reg.metrics()}
    for t in reg.tasks():
        assert set(t.metrics) <= known, f"{t.id} references unknown metrics"


def test_six_tasks_are_design_level() -> None:
    """This selects how records are gathered before metrics are computed, so it
    is load-bearing rather than descriptive."""
    design = {t.id for t in reg.tasks() if t.design_level}
    assert design == {
        "total_area_prediction",
        "total_power_prediction",
        "total_wirelength_prediction",
        "worst_arrival_time_prediction",
        "worst_slack_prediction",
        "total_negative_slack_prediction",
    }


def test_the_three_arc_tasks_publish_r2() -> None:
    """The paper's prose says R2 is omitted for all timing metrics. Table 8
    contradicts it. Following the prose derives 43 metric rows, not 46."""
    for tid in (
        "net_arc_delay_prediction",
        "cell_arc_delay_prediction",
        "cell_arc_slew_prediction",
    ):
        assert "r2" in reg.task(tid).metrics
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_registry.py -v`
Expected: FAIL, `AttributeError: module 'tools.registry' has no attribute 'tasks'`

- [ ] **Step 3: Create the tasks registry**

`data/registry/tasks.json`, twelve objects with keys `id`, `label`, `table8_label`, `unit`, `granularity`, `design_level`, `metrics`, `precision_overrides`. Take `table8_label`, `unit`, `granularity`, `design_level` and `precision_overrides` from Appendix A's `tasks.json` table and `metrics` from the per-task metric sets table:

```json
[
  {
    "id": "total_area_prediction", "label": "Total Area",
    "table8_label": "Total Area (u m^2)", "unit": "µm²",
    "granularity": "design", "design_level": true,
    "metrics": ["mae", "mape", "r2"], "precision_overrides": {}
  },
  {
    "id": "timing_path_slack_prediction", "label": "Timing Path Slack",
    "table8_label": "Timing Path Slack (ns)", "unit": "ns",
    "granularity": "path", "design_level": false,
    "metrics": ["mae", "mpe", "mne", "tpr", "tnr"],
    "precision_overrides": { "mae": 4, "mpe": 4, "mne": 4 }
  }
]
```

- [ ] **Step 4: Add the loader**

```python
@dataclass(frozen=True, slots=True)
class Task:
    id: str
    label: str
    table8_label: str
    unit: str
    granularity: str
    design_level: bool
    metrics: tuple[str, ...]
    precision_overrides: dict[str, int]


@cache
def tasks() -> tuple[Task, ...]:
    return tuple(
        Task(**{**row, "metrics": tuple(row["metrics"])}) for row in _load("tasks")
    )


@cache
def _task_index() -> dict[str, Task]:
    return {t.id: t for t in tasks()}


def task(task_id: str) -> Task:
    try:
        return _task_index()[task_id]
    except KeyError:
        raise KeyError(f"unknown task {task_id!r}") from None
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_registry.py -v`
Expected: 20 passed

- [ ] **Step 6: Commit**

```bash
git add data/registry/tasks.json tools/registry.py tests/test_registry.py
git commit -m "feat(registry): add the tasks registry with per-task metric sets"
```

---

### Task 5: Cell classification

Void, degenerate and saturated. **Precedence is the whole point of this task.**

**Files:**
- Modify: `tools/registry.py`
- Test: `tests/test_registry.py`

**Interfaces:**
- Consumes: `reg.stage`, `reg.task`, `reg.metric`.
- Produces: `reg.is_void(task_id, stage_id) -> bool`, `reg.is_degenerate(task_id, metric_id, stage_id) -> bool`, `reg.is_saturated(task_id, metric_id, stage_id) -> bool`, `reg.precision(task_id, metric_id) -> int`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_registry.py`:

```python
def test_void_is_the_two_wirelength_tasks_at_floorplan_only() -> None:
    assert reg.is_void("total_wirelength_prediction", "floorplan")
    assert reg.is_void("interconnect_length_prediction", "floorplan")
    assert not reg.is_void("total_wirelength_prediction", "global_place")
    assert not reg.is_void("total_area_prediction", "floorplan")


def test_degenerate_is_mpe_mne_on_slack_tasks_at_global_route() -> None:
    assert reg.is_degenerate("worst_slack_prediction", "mpe", "global_route")
    assert reg.is_degenerate("worst_slack_prediction", "mne", "global_route")
    assert not reg.is_degenerate("worst_slack_prediction", "mae", "global_route")
    assert not reg.is_degenerate("worst_slack_prediction", "mpe", "cts")


def test_degeneracy_beats_saturation() -> None:
    """PRECEDENCE IS LOAD-BEARING. Reversing these two still yields 880 live
    cells and 232 live combos, so the headline counts stay green while 24 cells
    are silently mistyped. This is the assertion that catches it."""
    assert reg.is_degenerate("worst_slack_prediction", "mpe", "global_route")
    assert not reg.is_saturated("worst_slack_prediction", "mpe", "global_route")


def test_saturation_is_a_stage_rule_not_a_numeric_test() -> None:
    assert reg.is_saturated("total_area_prediction", "mae", "global_route")
    assert reg.is_saturated("worst_slack_prediction", "tpr", "global_route")
    assert not reg.is_saturated("total_wirelength_prediction", "mae", "global_route")
    assert not reg.is_saturated("total_area_prediction", "mae", "cts")


def test_precision_defaults_to_the_metric_and_is_overridden_per_task() -> None:
    assert reg.precision("total_area_prediction", "mae") == 2
    assert reg.precision("total_area_prediction", "r2") == 3
    assert reg.precision("cell_arc_delay_prediction", "mae") == 4
    assert reg.precision("timing_path_slack_prediction", "mpe") == 4
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_registry.py -v`
Expected: FAIL, `AttributeError: module 'tools.registry' has no attribute 'is_void'`

- [ ] **Step 3: Implement**

Append to `tools/registry.py`:

```python
def is_void(task_id: str, stage_id: str) -> bool:
    """The cell does not exist. Void cells are not part of the 880.

    Half-perimeter wirelength is the baseline estimator for both wirelength
    tasks, and at floorplan there are no placed coordinates to compute it from.
    """
    return task_id in stage(stage_id).void_tasks


def is_degenerate(task_id: str, metric_id: str, stage_id: str) -> bool:
    """The cell exists, but its baseline is 0/0 and was never measured.

    Table 8 prints "No positive or negative error, n_p = n_n = 0". These 24
    cells stay live and carry baseline_value: null, so nothing can be recorded
    as beating a baseline that does not exist.
    """
    s = stage(stage_id)
    return task_id in s.degenerate_tasks and metric_id in s.degenerate_metrics


def is_saturated(task_id: str, metric_id: str, stage_id: str) -> bool:
    """The baseline is already at the optimum, so the cell is never ranked.

    Checked AFTER degeneracy, deliberately. A degenerate cell is unmeasured, not
    perfect, and conflating them mistypes 24 cells while every headline count
    stays correct.

    This is a stage-and-task rule, never a predicate over values. A test like
    `mae == 0 and mape == 0 and r2 == 1` marks only 5 of the 10 saturated tasks,
    because the other five publish no MAPE row, no R2 row, or neither. And 16 of
    the saturated cells are tpr/tnr sitting at 100 %, where an "error is
    approximately zero" test returns false.
    """
    if is_degenerate(task_id, metric_id, stage_id):
        return False
    return task_id in stage(stage_id).saturated_tasks


def precision(task_id: str, metric_id: str) -> int:
    """Display decimal places, per (task, metric).

    Ground truth for the plausibility guard: a submission claiming MAE 0.00001
    on cell_arc_delay is claiming precision the dataset cannot express.
    """
    return task(task_id).precision_overrides.get(metric_id, metric(metric_id).precision)
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_registry.py -v`
Expected: 25 passed

- [ ] **Step 5: Commit**

```bash
git add tools/registry.py tests/test_registry.py
git commit -m "feat(registry): add cell classification with degeneracy before saturation"
```

---

### Task 6: Derived enumerations and the partition

**Files:**
- Modify: `tools/registry.py`
- Test: `tests/test_registry.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `reg.metric_rows() -> tuple[tuple[str, str], ...]`, `reg.live_combos() -> tuple[tuple[str, str, str], ...]` as `(task, pdk, stage)`, `reg.live_cells() -> tuple[tuple[str, str, str, str], ...]` as `(task, metric, pdk, stage)`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_registry.py`:

```python
def test_metric_rows_derive_to_46() -> None:
    assert len(reg.metric_rows()) == 46


def test_live_combos_derive_to_232() -> None:
    assert len(reg.live_combos()) == 232


def test_live_cells_derive_to_880() -> None:
    assert len(reg.live_cells()) == 880


def test_the_partition_not_just_the_total() -> None:
    """ASSERT THE PARTITION. 880 stays correct while degeneracy and saturation
    are swapped; 40/24/120 does not."""
    all_cells = [
        (t.id, m, p.id, s.id)
        for t, m in reg.metric_rows_expanded()
        for p in reg.pdks()
        for s in reg.stages()
    ]
    assert len(all_cells) == 920

    void = [c for c in all_cells if reg.is_void(c[0], c[3])]
    degen = [c for c in all_cells if reg.is_degenerate(c[0], c[1], c[3])]
    sat = [c for c in all_cells if reg.is_saturated(c[0], c[1], c[3])]

    assert len(void) == 40, "void cells"
    assert len(degen) == 24, "degenerate cells"
    assert len(sat) == 120, "saturated cells"
    assert len(all_cells) - len(void) == 880, "live cells"


def test_no_cell_is_both_degenerate_and_saturated() -> None:
    for t, m, _p, s in reg.live_cells():
        assert not (reg.is_degenerate(t, m, s) and reg.is_saturated(t, m, s))


def test_no_count_literal_appears_in_tools() -> None:
    """Counts are derived. A literal here means the derivation was replaced by a
    constant and the registry stopped being the source of truth.

    Parsed with `ast`, not grepped. A regex over raw text also matches prose, and
    this module's own docstrings legitimately discuss the 24 degenerate cells and
    the 46 metric rows. Grepping would force those explanations out of the code
    to satisfy a test about code, which is the tail wagging the dog. The AST
    contains no comments at all and represents a docstring as a str constant, so
    both are excluded for free.
    """
    import ast
    from pathlib import Path

    forbidden = {46, 232, 880, 856, 120, 24, 40, 920}
    root = Path(__file__).resolve().parent.parent / "tools"
    offenders: list[str] = []
    for py in sorted(root.rglob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            # `type(...) is int` rather than isinstance: True is an int subclass
            # and a bare `True` in source must not be read as the number 1.
            if isinstance(node, ast.Constant) and type(node.value) is int:
                if node.value in forbidden:
                    offenders.append(f"{py.name}:{node.lineno} hardcodes {node.value}")
    assert not offenders, offenders
```

`metric_rows_expanded()` is a small helper returning `(Task, metric_id)` pairs, added alongside `metric_rows()`.

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_registry.py -v`
Expected: FAIL, `AttributeError: module 'tools.registry' has no attribute 'metric_rows'`

- [ ] **Step 3: Implement**

```python
@cache
def metric_rows_expanded() -> tuple[tuple[Task, str], ...]:
    return tuple((t, metric_id) for t in tasks() for metric_id in t.metrics)


@cache
def metric_rows() -> tuple[tuple[str, str], ...]:
    """Every (task_id, metric_id) pair. The contract says this derives to 46."""
    return tuple((t.id, metric_id) for t, metric_id in metric_rows_expanded())


@cache
def live_combos() -> tuple[tuple[str, str, str], ...]:
    """(task, pdk, stage) triples that are not void. One shard file each."""
    return tuple(
        (t.id, p.id, s.id)
        for t in tasks()
        for p in pdks()
        for s in stages()
        if not is_void(t.id, s.id)
    )


@cache
def live_cells() -> tuple[tuple[str, str, str, str], ...]:
    """(task, metric, pdk, stage) quads that are not void."""
    return tuple(
        (task_id, metric_id, p.id, s.id)
        for task_id, metric_id in metric_rows()
        for p in pdks()
        for s in stages()
        if not is_void(task_id, s.id)
    )
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_registry.py -v`
Expected: 31 passed

- [ ] **Step 5: Commit**

```bash
git add tools/registry.py tests/test_registry.py
git commit -m "feat(registry): derive metric rows, live combos and live cells"
```

---

### Task 7: Cross-check against the CSV

**The most valuable file in this phase.** It diffs the registry against an independent source as **sets**, so a registry and its own tests cannot agree on a shared misreading.

**Files:**
- Create: `tools/checks/__init__.py`, `tools/checks/registry_csv.py`, `tools/validate.py`
- Test: `tests/test_registry_csv.py`

**Interfaces:**
- Consumes: `tools.registry`.
- Produces: `checks.CHECKS: dict[str, Callable[[], list[str]]]`, `registry_csv.check() -> list[str]` returning failure messages, empty on success. `tools.validate.main() -> int`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_registry_csv.py`:

```python
"""The registry must agree with docs/sources/table8_baseline.csv.

Written against the CSV deliberately, not against the registry, so a shared
misreading between the registry and its own tests cannot self-confirm.
"""

from __future__ import annotations

import csv
from pathlib import Path

from tools import registry as reg
from tools.checks import registry_csv

CSV_PATH = (
    Path(__file__).resolve().parent.parent / "docs" / "sources" / "table8_baseline.csv"
)


def _csv_rows() -> list[dict[str, str]]:
    with CSV_PATH.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_the_check_passes_on_current_data() -> None:
    assert registry_csv.check() == []


def test_every_task_label_joins() -> None:
    csv_labels = {r["task"] for r in _csv_rows()}
    reg_labels = {t.table8_label for t in reg.tasks()}
    assert csv_labels == reg_labels


def test_every_metric_label_joins() -> None:
    csv_labels = {r["metric"] for r in _csv_rows()}
    reg_labels = {m.table8_label for m in reg.metrics()}
    assert csv_labels == reg_labels


def test_every_stage_label_joins() -> None:
    csv_labels = {r["stage_transition"] for r in _csv_rows()}
    reg_labels = {s.table8_label for s in reg.stages()}
    assert csv_labels == reg_labels


def test_every_pdk_label_joins() -> None:
    csv_labels = {r["pdk"] for r in _csv_rows()}
    reg_labels = {p.table8_label for p in reg.pdks()}
    assert csv_labels == reg_labels


def test_table8_labels_are_unique_per_registry() -> None:
    """Duplicate detection BEFORE set comparison. Comparing sets alone hides a
    collision that silently drops a mapping."""
    for rows in (reg.tasks(), reg.metrics(), reg.stages(), reg.pdks()):
        labels = [r.table8_label for r in rows]
        assert len(labels) == len(set(labels))


def test_per_task_metric_sets_match_the_csv() -> None:
    from collections import defaultdict

    csv_sets: defaultdict[str, set[str]] = defaultdict(set)
    for r in _csv_rows():
        csv_sets[r["task"]].add(r["metric"])

    for t in reg.tasks():
        expected = {reg.metric(m).table8_label for m in t.metrics}
        assert csv_sets[t.table8_label] == expected, t.id


def test_kinds_match_the_registry_classification() -> None:
    """Restate the classification NEGATIVELY from the CSV, as a cross-check on
    the registry's positive enumeration."""
    by_kind = {"VOID": set(), "DEGENERATE": set()}
    tl = {t.table8_label: t.id for t in reg.tasks()}
    ml = {m.table8_label: m.id for m in reg.metrics()}
    sl = {s.table8_label: s.id for s in reg.stages()}

    for r in _csv_rows():
        if r["kind"] in by_kind:
            by_kind[r["kind"]].add(
                (tl[r["task"]], ml[r["metric"]], sl[r["stage_transition"]])
            )

    for t, m, s in by_kind["VOID"]:
        assert reg.is_void(t, s), f"CSV says VOID, registry disagrees: {t} {m} {s}"
    for t, m, s in by_kind["DEGENERATE"]:
        assert reg.is_degenerate(t, m, s), f"CSV says DEGENERATE: {t} {m} {s}"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_registry_csv.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'tools.checks'`

- [ ] **Step 3: Implement the check**

Create `tools/checks/__init__.py`:

```python
"""Validation checks, registered by name.

Checks import THIS module and register into CHECKS. tools/validate.py reads the
same dict. It must be imported as a package, never run as __main__, or the two
end up with different dicts and validation silently passes having run nothing.
"""

from __future__ import annotations

from collections.abc import Callable

CHECKS: dict[str, Callable[[], list[str]]] = {}


def register(name: str) -> Callable[[Callable[[], list[str]]], Callable[[], list[str]]]:
    def decorate(fn: Callable[[], list[str]]) -> Callable[[], list[str]]:
        CHECKS[name] = fn
        return fn

    return decorate


from tools.checks import registry_csv as _registry_csv  # noqa: E402,F401
```

Create `tools/checks/registry_csv.py` implementing `check() -> list[str]` that performs the same set diffs as the test, returning a message per mismatch, and decorate it with `@register("registry_csv")`. Compare `table8_label` sets in **both directions** and detect duplicate labels before comparing.

Create `tools/validate.py`:

```python
"""Run every registered check. Exits non-zero on the first failure set."""

from __future__ import annotations

from tools.checks import CHECKS


def main() -> int:
    if not CHECKS:
        print("validate: no checks registered, refusing to report success")
        return 1

    failures = 0
    for name, fn in sorted(CHECKS.items()):
        messages = fn()
        for message in messages:
            print(f"{name}: {message}")
        failures += len(messages)

    print(f"validate: {len(CHECKS)} checks, {failures} failures")
    return 1 if failures else 0
```

The empty-`CHECKS` guard is not defensive padding. Validation previously passed having run nothing, and this is the assertion that would have caught it.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest -v && uv run eda-validate`
Expected: all tests pass; `validate: 1 checks, 0 failures`, exit 0

- [ ] **Step 5: Commit**

```bash
git add tools/checks tools/validate.py tests/test_registry_csv.py
git commit -m "feat(validate): cross-check the registry against the paper CSV"
```

---

### Task 8: Regression mutations

The gate on this whole phase. Three mutations left the pre-reset suite fully green; the new suite must fail on each.

**Files:**
- Test: `tests/test_mutations.py`

**Interfaces:**
- Consumes: `tools.registry`, `tools.checks.registry_csv`.
- Produces: nothing.

- [ ] **Step 1: Write the tests**

Create `tests/test_mutations.py`:

```python
"""Mutations that the pre-reset suite survived.

Each one perturbs a registry file in a temp copy, points the loader at it, and
asserts something fails. If a test here passes with the mutation applied, that
value has no verification and the suite is decorative.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest

from tools import registry as reg


@pytest.fixture
def mutable_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    dest = tmp_path / "registry"
    shutil.copytree(reg.REGISTRY_DIR, dest)
    monkeypatch.setattr(reg, "REGISTRY_DIR", dest)
    for fn in (
        reg._load,
        reg.tasks,
        reg.metrics,
        reg.stages,
        reg.pdks,
        reg.circuits,
        reg._task_index,
        reg._metric_index,
        reg._stage_index,
        reg._pdk_index,
        reg.metric_rows,
        reg.metric_rows_expanded,
        reg.live_combos,
        reg.live_cells,
    ):
        fn.cache_clear()
    yield dest
    for fn in (
        reg._load,
        reg.tasks,
        reg.metrics,
        reg.stages,
        reg.pdks,
        reg.circuits,
        reg._task_index,
        reg._metric_index,
        reg._stage_index,
        reg._pdk_index,
        reg.metric_rows,
        reg.metric_rows_expanded,
        reg.live_combos,
        reg.live_cells,
    ):
        fn.cache_clear()


def _rewrite(path: Path, mutate) -> None:
    rows = json.loads(path.read_text())
    mutate(rows)
    path.write_text(json.dumps(rows, indent=2))


def test_reversed_stage_order_is_caught(mutable_registry: Path) -> None:
    """Pre-reset this passed. sorted(orders) == range(1, n+1) is true on a
    reversed sequence."""

    def mutate(rows: list[dict]) -> None:
        n = len(rows)
        for r in rows:
            r["order"] = n + 1 - r["order"]

    _rewrite(mutable_registry / "stages.json", mutate)
    with pytest.raises(AssertionError):
        assert tuple(s.id for s in reg.stages()) == (
            "floorplan",
            "global_place",
            "detailed_place",
            "cts",
            "global_route",
        )


def test_corrupted_circuit_attribute_is_caught(mutable_registry: Path) -> None:
    """Pre-reset, ethernet.registers 10,544 -> 87 left 115/115 green."""

    def mutate(rows: list[dict]) -> None:
        for r in rows:
            if r["id"] == "ethernet":
                r["registers"] = 87

    _rewrite(mutable_registry / "circuits.json", mutate)
    eth = next(c for c in reg.circuits() if c.id == "ethernet")
    with pytest.raises(AssertionError):
        assert eth.registers == 10544


def test_swapped_degeneracy_and_saturation_is_caught(mutable_registry: Path) -> None:
    """The dangerous one: 880 and 232 both stay correct while 24 cells are
    silently mistyped. Only the partition catches it."""

    def mutate(rows: list[dict]) -> None:
        for r in rows:
            if r["id"] == "global_route":
                r["degenerate_tasks"] = []
                r["degenerate_metrics"] = []

    _rewrite(mutable_registry / "stages.json", mutate)

    assert len(reg.live_cells()) == 880, "the total is still right, as expected"

    degen = [c for c in reg.live_cells() if reg.is_degenerate(c[0], c[1], c[3])]
    sat = [c for c in reg.live_cells() if reg.is_saturated(c[0], c[1], c[3])]
    with pytest.raises(AssertionError):
        assert len(degen) == 24 and len(sat) == 120


def test_a_phantom_pdk_is_caught(mutable_registry: Path) -> None:
    """Table 8 misspells IHP130 as IPH130 five times."""

    def mutate(rows: list[dict]) -> None:
        for r in rows:
            if r["id"] == "ihp130":
                r["table8_label"] = "IPH130"

    _rewrite(mutable_registry / "pdks.json", mutate)
    from tools.checks import registry_csv

    assert registry_csv.check() != [], "the CSV cross-check must reject this"
```

- [ ] **Step 2: Run and confirm every mutation is caught**

Run: `uv run pytest tests/test_mutations.py -v`
Expected: 4 passed. A failure here means that value has no verification.

- [ ] **Step 3: Run the full gate**

Run: `make check`
Expected: lint clean, mypy clean, `validate: 1 checks, 0 failures`, all tests pass, build skipped for Phase 3.

- [ ] **Step 4: Commit and open the PR**

```bash
git add tests/test_mutations.py
git commit -m "test(registry): pin the three mutations the old suite survived"
git push -u origin phase-1/registries
gh pr create --title "Phase 1: registries" --body "Rebuilds the five registry files and the typed loader. Cross-checked against docs/sources/table8_baseline.csv as sets. Includes regression tests for the three mutations the pre-reset suite survived."
```

---

## Phase gate

Every item must pass before Phase 2 starts.

```bash
make check
```

- [ ] 12 tasks, 11 metrics, 5 stages, 4 PDKs, 18 circuits load
- [ ] `metric_rows()` derives to 46, `live_combos()` to 232, `live_cells()` to 880
- [ ] the partition asserts: 40 void, 24 degenerate, 120 saturated
- [ ] stage ids assert **in order**, not as a set
- [ ] every task's `metrics[]` is a subset of `metrics.json` keys
- [ ] every metric has a direction; `mpe` is optimistic, `mne` conservative
- [ ] `percent` is exactly `{mape, mape_p95, mape_top5, tpr, tnr}`
- [ ] every `table8_label` joins to the CSV with **zero unmatched**, all four dimensions
- [ ] circuits, metal layers, utilization and units are asserted against `docs/sources/`
- [ ] no count literal appears anywhere in `tools/`
- [ ] all four regression mutations are caught

## Review prompt

```
Use a domain reviewer on data/registry/ and tools/registry.py against
docs/DATA_CONTRACT.md Appendix A. Verify the per-task metric sets match Table 8
exactly, the 8 void combos are the specified ones and no others, directions are
right (especially R2 higher versus MAE lower), and the mpe/mne bias is encoded.

Then independently apply each of these mutations to a COPY of the repo and
confirm the suite fails: reverse every stages.json order; set ethernet.registers
to 87; empty global_route.degenerate_tasks; rename ihp130's table8_label to
IPH130. Report any mutation that does NOT fail the suite.

Report only mismatches and unguarded values. Do not report style preferences.
```
