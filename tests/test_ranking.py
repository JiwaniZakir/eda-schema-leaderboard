"""Ranking, comparison and cell state.

The sentinel cases carry most of the weight here: they are the ones where a
plausible implementation silently produces a wrong leaderboard rather than an
error.
"""

from __future__ import annotations

import pytest

from tools import registry as reg
from tools.ranking import (
    Bound,
    BoundKind,
    CellState,
    Comparison,
    cell_state,
    compare,
    rank_key,
    slack_rank_key,
)


def test_rank_key_respects_direction() -> None:
    """R² inverts; MAE does not. No caller should have to remember which."""
    assert rank_key("r2", 0.99) < rank_key("r2", 0.50)
    assert rank_key("mae", 1.0) < rank_key("mae", 2.0)


def test_rank_key_rejects_nan() -> None:
    """A missing value must never sort as best."""
    with pytest.raises(ValueError, match="NaN"):
        rank_key("mae", float("nan"))


# -- the sentinel scale trap ----------------------------------------------


def test_percent_sentinel_is_parsed_into_storage_units() -> None:
    """`> 10000 %` is 100.0 as a fraction, not 10000.0.

    Parsed naively, every real submission beats it: a stored MAPE of 1.2269
    (122.69%) is trivially less than 10000. This single conversion is the
    difference between a meaningful sentinel and a free win on 20 cells.
    """
    b = Bound.parse("mape", "> 10000 %")
    assert b.kind is BoundKind.GREATER_THAN
    assert b.value == pytest.approx(100.0)


def test_non_percent_sentinel_is_not_rescaled() -> None:
    b = Bound.parse("r2", "< -1")
    assert b.kind is BoundKind.LESS_THAN
    assert b.value == pytest.approx(-1.0)


def test_published_value_round_trips_through_scale() -> None:
    assert Bound.parse("mape", "12.43 %").value == pytest.approx(0.1243)
    assert Bound.parse("mae", "1,781.97").value == pytest.approx(1781.97)


# -- comparison ------------------------------------------------------------


@pytest.mark.parametrize(
    ("challenger", "expected"),
    [
        pytest.param(50.0, Comparison.BETTER, id="clearly-inside"),
        pytest.param(100.0, Comparison.BETTER, id="exactly-at-threshold"),
        pytest.param(150.0, Comparison.UNDECIDABLE, id="beyond-threshold"),
    ],
)
def test_lower_better_sentinel(challenger: float, expected: Comparison) -> None:
    """MAPE `> 10000 %`: beatable only from the defined side."""
    incumbent = Bound.parse("mape", "> 10000 %")
    got = compare(
        "net_arc_delay_prediction", "mape", Bound.exact(challenger), incumbent
    )
    assert got is expected


@pytest.mark.parametrize(
    ("challenger", "expected"),
    [
        pytest.param(-0.5, Comparison.BETTER, id="above-threshold"),
        pytest.param(-3.0, Comparison.UNDECIDABLE, id="below-threshold"),
    ],
)
def test_higher_better_sentinel(challenger: float, expected: Comparison) -> None:
    """R² `< -1`: -0.5 clearly wins; -3 is genuinely undecidable, not a loss."""
    incumbent = Bound.parse("r2", "< -1")
    got = compare("net_arc_delay_prediction", "r2", Bound.exact(challenger), incumbent)
    assert got is expected


def test_sentinel_versus_sentinel_is_undecidable() -> None:
    a = Bound.parse("r2", "< -1")
    assert compare("net_arc_delay_prediction", "r2", a, a) is Comparison.UNDECIDABLE


@pytest.mark.parametrize(
    "other",
    [
        pytest.param(Bound.exact(1.0), id="vs-exact"),
        pytest.param(Bound.parse("mape", "> 10000 %"), id="vs-sentinel"),
        pytest.param(Bound.absent(), id="vs-absent"),
    ],
)
def test_absent_baseline_is_always_undecidable(other: Bound) -> None:
    """The guard for the 24 degenerate cells.

    Nothing may be recorded as beating a baseline that was never measured.
    """
    absent = Bound.absent()
    assert (
        compare("worst_slack_prediction", "mpe", absent, other)
        is Comparison.UNDECIDABLE
    )
    assert (
        compare("worst_slack_prediction", "mpe", other, absent)
        is Comparison.UNDECIDABLE
    )


def test_equality_is_decided_at_display_precision() -> None:
    """Exact float equality would make `matches_baseline` unreachable.

    Tying is the best achievable outcome on ~132 cells, and Table 8's own values
    are rounded, so a published number is only meaningful to its precision.
    """
    # total_area mae renders at 2dp, so a sub-milli difference is a tie.
    assert reg.precision("total_area_prediction", "mae") == 2
    got = compare(
        "total_area_prediction", "mae", Bound.exact(1781.9701), Bound.exact(1781.97)
    )
    assert got is Comparison.EQUAL

    # cell_arc_delay mae renders at 4dp, where the same gap is decisive.
    assert reg.precision("cell_arc_delay_prediction", "mae") == 4
    got = compare(
        "cell_arc_delay_prediction", "mae", Bound.exact(0.0011), Bound.exact(0.0019)
    )
    assert got is Comparison.BETTER


def test_direction_is_honoured_in_comparison() -> None:
    higher = compare(
        "total_area_prediction", "r2", Bound.exact(0.99), Bound.exact(0.95)
    )
    lower = compare("total_area_prediction", "mae", Bound.exact(1.0), Bound.exact(2.0))
    assert higher is Comparison.BETTER
    assert lower is Comparison.BETTER


# -- slack ordering --------------------------------------------------------


def test_slack_rank_key_puts_optimistic_error_first() -> None:
    conservative = slack_rank_key(mpe=0.1, mne=5.0)
    optimistic = slack_rank_key(mpe=1.0, mne=0.1)
    assert conservative < optimistic, "a lower MPE must outrank a lower MNE"


def test_slack_degenerate_case_is_intended_behaviour() -> None:
    """Documented, not a bug.

    A uniformly pessimistic model never overestimates, scores mpe=0, and leads
    this ordering while being useless. It is accepted because `mae` is a separate
    cell in the same grid where it places last, and Phase 5 flags the combination.
    This test exists so nobody reads that as a defect and "fixes" it into a
    weighted blend the paper never specified.
    """
    useless_but_safe = slack_rank_key(mpe=0.0, mne=999.0)
    accurate = slack_rank_key(mpe=0.05, mne=0.05)
    assert useless_but_safe < accurate


# -- cell state ------------------------------------------------------------


def test_saturated_cell_is_never_ranked() -> None:
    """Structural: whatever was submitted, a saturated cell shows as saturated."""
    got = cell_state(
        "total_area_prediction",
        "mae",
        "global_route",
        Bound.exact(0.0),
        (Bound.exact(0.0),),
    )
    assert got is CellState.SATURATED


@pytest.mark.parametrize(
    ("entries", "expected"),
    [
        pytest.param((), CellState.NO_ENTRY, id="no-entry"),
        pytest.param((Bound.exact(0.5),), CellState.BEATS_BASELINE, id="beats"),
        pytest.param((Bound.exact(1.0),), CellState.MATCHES_BASELINE, id="matches"),
        pytest.param((Bound.exact(2.0),), CellState.BASELINE_LEADS, id="loses"),
    ],
)
def test_cell_states_are_all_reachable(
    entries: tuple[Bound, ...], expected: CellState
) -> None:
    got = cell_state(
        "total_area_prediction", "mae", "floorplan", Bound.exact(1.0), entries
    )
    assert got is expected


def test_undecidable_entries_do_not_become_a_loss() -> None:
    """Claiming the baseline leads would assert a comparison never made."""
    got = cell_state(
        "worst_slack_prediction",
        "mpe",
        "cts",
        Bound.absent(),
        (Bound.exact(1.0),),
    )
    assert got is CellState.NO_ENTRY
