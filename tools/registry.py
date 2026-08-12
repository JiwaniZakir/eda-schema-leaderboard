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
    """Look up one PDK. Raises KeyError on an unknown id: results-tree directory
    names are uppercase and must be normalized before they reach here."""
    try:
        return _pdk_index()[pdk_id]
    except KeyError:
        raise KeyError(f"unknown pdk {pdk_id!r}") from None


def stage(stage_id: str) -> Stage:
    """Look up one stage. Raises KeyError on an unknown id: three stage ids
    contain underscores, so a split-based path parse lands here with junk."""
    try:
        return _stage_index()[stage_id]
    except KeyError:
        raise KeyError(f"unknown stage {stage_id!r}") from None


@cache
def tasks() -> tuple[Task, ...]:
    """Returned in Table 8 row order. `metrics` is ordered the same way, so a
    renderer can walk a task's rows straight down the published table."""
    return tuple(
        Task(
            **{
                **row,
                "metrics": tuple(row["metrics"]),
                "precision_overrides": dict(row["precision_overrides"]),
            }
        )
        for row in _load("tasks")
    )


@cache
def _task_index() -> dict[str, Task]:
    return {t.id: t for t in tasks()}


def task(task_id: str) -> Task:
    """Look up one task. Raises KeyError on an unknown id: task ids keep the
    lab's `_prediction` suffix, and a stripped one must not silently resolve."""
    try:
        return _task_index()[task_id]
    except KeyError:
        raise KeyError(f"unknown task {task_id!r}") from None
