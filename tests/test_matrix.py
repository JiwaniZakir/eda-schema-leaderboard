"""The matrix page: context, grid, states, palette, stage strip, budget.

Expected values and counts live here, in tests. They must never appear in
build.py or tools/.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import build
from tools import baseline as bl
from tools import matrix
from tools import registry as reg


def test_the_build_writes_an_index(site: Path) -> None:
    assert (site / "index.html").is_file()


def test_the_stylesheets_are_copied(site: Path) -> None:
    assert (site / "static" / "css" / "base.css").is_file()
    assert (site / "static" / "css" / "theme.css").is_file()


def test_the_theme_source_files_are_not_published(site: Path) -> None:
    """One theme ships, renamed to theme.css. Copying the whole themes directory
    would publish the theme nobody selected and let a page link the wrong one."""
    assert not (site / "static" / "css" / "themes").exists()


def test_an_unknown_theme_fails_the_build_loudly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A typo in THEME must not silently fall back to the default. A site that
    deployed with the wrong brand and exited 0 is worse than one that failed."""
    monkeypatch.setenv("THEME", "not_a_theme")
    with pytest.raises(SystemExit):
        build.selected_theme()


def test_a_plain_value_formats_at_the_registry_precision() -> None:
    """MAE on a design-level task is 2dp; on cell_arc_delay it is 4dp, which is
    the ground truth Phase 6's plausibility layer keys on."""
    assert (
        matrix.format_bound(
            "total_area_prediction", "mae", bl.Bound(bl.BoundKind.EXACT, 1781.97)
        )
        == "1,781.97"
    )
    assert (
        matrix.format_bound(
            "cell_arc_delay_prediction", "mae", bl.Bound(bl.BoundKind.EXACT, 0.0)
        )
        == "0.0000"
    )


def test_a_percent_metric_is_multiplied_by_one_hundred_here_and_only_here() -> None:
    """Storage is a fraction, display is a percent. Table 8 prints 12.43 %, and
    data/baseline.json holds 0.1243. This is the single conversion point in the
    project."""
    assert (
        matrix.format_bound(
            "total_area_prediction", "mape", bl.Bound(bl.BoundKind.EXACT, 0.1243)
        )
        == "12.43 %"
    )


def test_a_rate_at_its_ceiling_renders_as_one_hundred_percent() -> None:
    assert (
        matrix.format_bound(
            "worst_slack_prediction", "tpr", bl.Bound(bl.BoundKind.EXACT, 1.0)
        )
        == "100.00 %"
    )


def test_an_upper_sentinel_renders_its_comparator() -> None:
    """The paper thresholded the number away, so the cell shows a bound. A bare
    10,000.00 % would assert a measurement nobody made."""
    text = matrix.format_bound(
        "net_arc_delay_prediction", "mape", bl.Bound(bl.BoundKind.GREATER_THAN, 100.0)
    )
    assert text.startswith(">")
    assert text == "> 10,000.00 %"


def test_a_lower_sentinel_renders_its_comparator() -> None:
    text = matrix.format_bound(
        "net_arc_delay_prediction", "r2", bl.Bound(bl.BoundKind.LESS_THAN, -1.0)
    )
    assert text == "< -1.000"


def test_a_degenerate_bound_renders_the_marker_and_never_a_number() -> None:
    """0/0 is not 0. Formatting an absent bound as 0.00 would publish a baseline
    the paper explicitly says was never measured."""
    assert (
        matrix.format_bound(
            "worst_slack_prediction", "mpe", bl.Bound(bl.BoundKind.ABSENT, None)
        )
        == matrix.DEGENERATE_MARKER
    )


def test_saturation_comes_from_the_registry_not_from_the_value() -> None:
    """A cell at global route with a 0.00 baseline is saturated because of where
    it sits, not because of what it says. total_wirelength also sits at global
    route and is NOT saturated, and its baseline MAE there is 13,698.67."""
    assert (
        matrix.cell("total_area_prediction", "mae", "ng45", "global_route").state
        == matrix.SATURATED
    )
    live = matrix.cell("total_wirelength_prediction", "mae", "ng45", "global_route")
    assert live.state == matrix.NO_ENTRY
    assert live.display == "13,698.67"


def test_a_saturated_rate_is_still_saturated_at_one_hundred_percent() -> None:
    """16 of the 120 saturated cells are tpr/tnr at their ceiling. An
    is-the-error-near-zero test returns false on every one of them."""
    assert (
        matrix.cell("worst_slack_prediction", "tpr", "ng45", "global_route").state
        == matrix.SATURATED
    )


def test_degeneracy_is_reported_separately_from_state() -> None:
    """State is about submissions; baseline_kind is about the paper. Collapsing
    them loses the difference between 'nobody has entered' and 'there is nothing
    to enter against'."""
    entry = matrix.cell("worst_slack_prediction", "mpe", "ng45", "global_route")
    assert entry.state == matrix.NO_ENTRY
    assert entry.baseline_kind == "degenerate"
    assert entry.display == matrix.DEGENERATE_MARKER


def test_the_three_baseline_kinds_partition_the_live_cells() -> None:
    """856 published, of which 32 are sentinels, plus 24 degenerate."""
    kinds = [matrix.cell(*key).baseline_kind for key in reg.live_cells()]
    assert kinds.count("sentinel") == 32
    assert kinds.count("degenerate") == 24
    assert kinds.count("published") == 824
    assert len(kinds) == 880


def test_a_void_cell_has_no_context_at_all() -> None:
    with pytest.raises(KeyError):
        matrix.cell("total_wirelength_prediction", "mae", "ng45", "floorplan")
