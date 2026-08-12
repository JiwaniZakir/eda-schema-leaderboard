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
