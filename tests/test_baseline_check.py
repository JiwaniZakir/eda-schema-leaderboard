"""The baseline check, and the mutations it must catch.

Written against the registry and the raw CSV rather than against tools/baseline.py,
so a shared misreading cannot self-confirm.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

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
    upper = [
        e for e in bl.baselines().values() if e.bound.kind is bl.BoundKind.GREATER_THAN
    ]
    lower = [
        e for e in bl.baselines().values() if e.bound.kind is bl.BoundKind.LESS_THAN
    ]
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
        if e.bound.kind is bl.BoundKind.EXACT
        and e.bound.value is not None
        and e.bound.value > 1.0
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
