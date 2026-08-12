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
