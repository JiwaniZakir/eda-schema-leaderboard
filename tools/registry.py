"""Typed loaders for the five registries.

This is the only import path for grid vocabulary. Never hardcode a task, metric,
PDK, stage or circuit name anywhere else; read it from here.

The registries are generated to match `docs/DATA_CONTRACT.md`, which is the
document of record when the two disagree.

**No count in this module is a literal.** 46, 232, 880, 920 are all derived, and
`tests/test_no_hardcoded_counts.py` enforces that. A registry that hardcodes 880
cannot tell you when it has drifted from the data it claims to describe.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

REGISTRY_DIR = Path(__file__).resolve().parent.parent / "data" / "registry"


@dataclass(frozen=True, slots=True)
class Task:
    """One prediction target.

    `id` is the lab's own identifier, suffixed `_prediction`, matching upstream
    `drexel-ice/EDA-schema` and the results-tree layout. Do not shorten it;
    submissions are keyed on this string.

    `design_level` is behaviourally load-bearing, not descriptive: Phase 3 ingest
    reads one pooled `all_circuits.csv` for these six tasks and per-circuit CSVs
    for the rest. `granularity` is descriptive only.
    """

    id: str
    label: str
    table8_label: str
    unit: str
    granularity: str
    design_level: bool
    metrics: tuple[str, ...]
    precision_overrides: dict[str, int]


@dataclass(frozen=True, slots=True)
class Metric:
    """One metric row.

    `direction` is what ranking optimizes, declared once here and read everywhere.

    `bias` is set only on `mpe` and `mne`. The paper prefers a conservative miss
    over an optimistic one of equal magnitude, and ranking these as plain
    magnitude is a correctness bug rather than a style choice.

    `percent` values are stored as fractions in [0, 1] and multiplied by 100 only
    at display, exactly once.
    """

    id: str
    label: str
    long_label: str
    table8_label: str
    direction: str  # "higher" | "lower"
    bias: str | None  # "conservative" | "optimistic" | None
    percent: bool
    precision: int


@dataclass(frozen=True, slots=True)
class Stage:
    """One stage transition, always predicting the post-`detailed_route` value.

    Carries the grid's three exception rules as data rather than as code in some
    other module, so `is_void`, `is_saturated` and `is_degenerate` all derive from
    here and cannot drift from one another.
    """

    id: str
    label: str
    table8_label: str
    order: int
    void_tasks: tuple[str, ...]
    saturated_tasks: tuple[str, ...]
    degenerate_tasks: tuple[str, ...]
    degenerate_metrics: tuple[str, ...]


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
class Circuit:
    id: str
    inputs: int
    outputs: int
    registers: int


def _load(name: str) -> list[dict[str, Any]]:
    path = REGISTRY_DIR / f"{name}.json"
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise TypeError(f"{path} must hold a JSON array, got {type(data).__name__}")
    return data


@cache
def tasks() -> tuple[Task, ...]:
    return tuple(
        Task(
            id=r["id"],
            label=r["label"],
            table8_label=r["table8_label"],
            unit=r["unit"],
            granularity=r["granularity"],
            design_level=r["design_level"],
            metrics=tuple(r["metrics"]),
            precision_overrides=dict(r["precision_overrides"]),
        )
        for r in _load("tasks")
    )


@cache
def metrics() -> tuple[Metric, ...]:
    return tuple(
        Metric(
            id=r["id"],
            label=r["label"],
            long_label=r["long_label"],
            table8_label=r["table8_label"],
            direction=r["direction"],
            bias=r["bias"],
            percent=r["percent"],
            precision=r["precision"],
        )
        for r in _load("metrics")
    )


@cache
def stages() -> tuple[Stage, ...]:
    return tuple(
        Stage(
            id=r["id"],
            label=r["label"],
            table8_label=r["table8_label"],
            order=r["order"],
            void_tasks=tuple(r["void_tasks"]),
            saturated_tasks=tuple(r["saturated_tasks"]),
            degenerate_tasks=tuple(r["degenerate_tasks"]),
            degenerate_metrics=tuple(r["degenerate_metrics"]),
        )
        for r in _load("stages")
    )


@cache
def pdks() -> tuple[Pdk, ...]:
    return tuple(
        Pdk(
            id=r["id"],
            label=r["label"],
            long_label=r["long_label"],
            table8_label=r["table8_label"],
            metal_layers=r["metal_layers"],
            utilization=r["utilization"],
            utilization_sweep=tuple(r["utilization_sweep"]),
        )
        for r in _load("pdks")
    )


@cache
def circuits() -> tuple[Circuit, ...]:
    return tuple(
        Circuit(
            id=r["id"],
            inputs=r["inputs"],
            outputs=r["outputs"],
            registers=r["registers"],
        )
        for r in _load("circuits")
    )


# -- by-id lookups ---------------------------------------------------------


@cache
def task(task_id: str) -> Task:
    for entry in tasks():
        if entry.id == task_id:
            return entry
    raise KeyError(f"unknown task: {task_id!r}")


@cache
def metric(metric_id: str) -> Metric:
    for entry in metrics():
        if entry.id == metric_id:
            return entry
    raise KeyError(f"unknown metric: {metric_id!r}")


@cache
def stage(stage_id: str) -> Stage:
    for entry in stages():
        if entry.id == stage_id:
            return entry
    raise KeyError(f"unknown stage: {stage_id!r}")


@cache
def pdk(pdk_id: str) -> Pdk:
    for entry in pdks():
        if entry.id == pdk_id:
            return entry
    raise KeyError(f"unknown pdk: {pdk_id!r}")


# -- the three exception rules ---------------------------------------------


def is_void(task_id: str, stage_id: str) -> bool:
    """True when the cell does not exist: no baseline estimate is possible.

    Only `total_wirelength` and `interconnect_length` at `floorplan`. Half-
    perimeter wirelength is the baseline estimator for both, and the paper's
    footnote says it is unavailable before placement.

    Void is the only rule that subtracts from the live count.
    """
    return task_id in stage(stage_id).void_tasks


def is_degenerate(task_id: str, metric_id: str, stage_id: str) -> bool:
    """True when the cell exists but its baseline is a 0/0.

    `mpe`/`mne` for the three slack tasks at `global_route`, where the baseline is
    exact so there are no positive and no negative errors to average. The paper
    prints "No positive or negative error, n_p = n_n = 0".

    These stay live: a submission there has its own MPE and MNE even though the
    baseline has none. They carry `baseline_value: null`, so nothing can be
    recorded as beating a baseline that was never measured.
    """
    st = stage(stage_id)
    return task_id in st.degenerate_tasks and metric_id in st.degenerate_metrics


def is_saturated(task_id: str, metric_id: str, stage_id: str) -> bool:
    """True when the baseline is already at the optimum, so the cell is unwinnable.

    Expressed as a stage-and-task rule, never as a test on values. A predicate
    like `mae == 0 and mape == 0 and r2 == 1` identifies only five of the ten
    saturated tasks, because the other five publish no MAPE row, no R² row, or
    neither; and eight of these cells are `tpr`/`tnr` sitting at 100%, where
    "error is approximately zero" is simply false.

    Saturation is enumerated **positively** in `stages.json` rather than as
    "everything except the two wirelength tasks". The negative form is shorter and
    matches the paper's prose, which is exactly why it is dangerous: a thirteenth
    task added later would inherit saturation silently and be permanently
    unrankable, with nothing raising an error. Saturation is an empirical fact
    about the tool flow, not a default.

    **Degeneracy wins.** The precedence matters more than it looks: reversing it
    yields 144 saturated and 0 degenerate while still producing 880 live cells and
    232 live combos, so the phase gate passes green with 24 cells mis-typed. That
    is why `tests/test_registry.py` asserts 40/24/120 independently of 880.
    """
    if is_degenerate(task_id, metric_id, stage_id):
        return False
    return task_id in stage(stage_id).saturated_tasks


def precision(task_id: str, metric_id: str) -> int:
    """Decimal places for display, task-specific where the paper differs.

    `mae` is published at 4dp for the arc and path tasks and 2dp elsewhere, so
    precision cannot live on the metric alone.
    """
    override = task(task_id).precision_overrides.get(metric_id)
    return override if override is not None else metric(metric_id).precision


# -- derived grid ----------------------------------------------------------


def metric_rows() -> tuple[tuple[str, str], ...]:
    """Every `(task, metric)` pair. Derived; the contract says this is 46."""
    return tuple((t.id, metric_id) for t in tasks() for metric_id in t.metrics)


def live_combos() -> tuple[tuple[str, str, str], ...]:
    """Every live `(task, pdk, stage)`."""
    return tuple(
        (t.id, p.id, s.id)
        for t in tasks()
        for p in pdks()
        for s in stages()
        if not is_void(t.id, s.id)
    )


def live_cells() -> tuple[tuple[str, str, str, str], ...]:
    """Every live `(task, metric, pdk, stage)`.

    Excludes void only. Degenerate cells are live, because the cell exists even
    though its baseline does not.
    """
    return tuple(
        (t, m, p.id, s.id)
        for t, m in metric_rows()
        for p in pdks()
        for s in stages()
        if not is_void(t, s.id)
    )
