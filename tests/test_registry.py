"""The Phase 1 gate.

Literals are permitted in this file and nowhere else. `tools/` must *derive*
46 / 232 / 880; these tests assert what those derivations should come to.
`tests/test_no_hardcoded_counts.py` enforces the other half of that bargain.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from tools import registry as reg

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "docs" / "sources" / "table8_baseline.csv"


@pytest.mark.parametrize(
    ("loader", "expected", "what"),
    [
        pytest.param(reg.tasks, 12, "prediction tasks", id="tasks"),
        pytest.param(reg.metrics, 11, "distinct metrics", id="metrics"),
        pytest.param(reg.pdks, 4, "PDKs", id="pdks"),
        pytest.param(reg.stages, 5, "stage transitions", id="stages"),
        pytest.param(reg.circuits, 18, "IWLS'05 circuits", id="circuits"),
    ],
)
def test_vocabulary_sizes(loader, expected: int, what: str) -> None:  # type: ignore[no-untyped-def]
    assert len(loader()) == expected, f"expected {expected} {what}"


def test_ids_are_unique() -> None:
    for loader in (reg.tasks, reg.metrics, reg.stages, reg.pdks, reg.circuits):
        ids = [e.id for e in loader()]
        assert len(ids) == len(set(ids)), f"duplicate id in {loader.__name__}()"


def test_metric_rows_sum_to_46() -> None:
    """Derived two independent ways, so a bug in one is not self-confirming."""
    from_tasks = sum(len(t.metrics) for t in reg.tasks())
    assert from_tasks == 46
    assert len(reg.metric_rows()) == 46


def test_live_cells_is_880() -> None:
    assert len(reg.live_cells()) == 880


def test_live_combos_is_232() -> None:
    assert len(reg.live_combos()) == 232


def _all_cells() -> list[tuple[str, str, str, str]]:
    return [
        (t, m, p.id, s.id)
        for t, m in reg.metric_rows()
        for p in reg.pdks()
        for s in reg.stages()
    ]


def test_grid_partition_is_40_24_120() -> None:
    """The counts that 880 alone cannot protect.

    Reversing the saturated/degenerate precedence yields 144 saturated and 0
    degenerate while STILL producing 880 live cells and 232 live combos. The
    headline gate passes green with 24 cells silently mis-typed, and the damage
    only surfaces when Phase 6 colours a win against a baseline that was never
    measured. So assert the partition, not just the total.
    """
    cells = _all_cells()
    void = {c for c in cells if reg.is_void(c[0], c[3])}
    degen = {c for c in cells if reg.is_degenerate(c[0], c[1], c[3])}
    sat = {c for c in cells if reg.is_saturated(c[0], c[1], c[3])}

    assert len(cells) == 920
    assert len(void) == 40, "void: 2 wirelength tasks x their metrics x 4 pdks"
    assert len(degen) == 24, "degenerate: mpe/mne x 3 slack tasks x 4 pdks"
    assert len(sat) == 120, "saturated: global_route minus wirelength minus degenerate"
    assert not (degen & sat), "degeneracy must win over saturation"
    assert not (void & degen), "a void cell cannot also be degenerate"


def test_void_is_task_level_not_metric_level() -> None:
    """`is_void` takes no metric, and that signature is the documentation.

    If a combo could be partly void, the 232 combo count stops being well defined.
    """
    for task_id in ("total_wirelength_prediction", "interconnect_length_prediction"):
        assert reg.is_void(task_id, "floorplan")
        for stage_id in ("global_place", "detailed_place", "cts", "global_route"):
            assert not reg.is_void(task_id, stage_id)


def test_saturation_is_not_a_numeric_predicate() -> None:
    """Regression guard against someone re-deriving saturation from values.

    `mae == 0 and mape == 0 and r2 == 1` looks like a reasonable definition and
    identifies only a minority of the saturated tasks, because the others publish
    no MAPE row, no R² row, or neither.
    """
    with CSV_PATH.open(encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r["kind"] == "VAL"]

    gr = [r for r in rows if r["stage_transition"].startswith("global route")]
    by_task: dict[str, dict[str, str]] = {}
    for r in gr:
        by_task.setdefault(r["task"], {})[r["metric"]] = r["value"]

    def zeroish(v: str | None) -> bool:
        return v is not None and v.replace("%", "").replace(",", "").strip() in {
            "0.00",
            "0.0000",
        }

    naive = {
        t
        for t, vals in by_task.items()
        if zeroish(vals.get("MAE"))
        and zeroish(vals.get("MAPE"))
        and vals.get("R^2") == "1.000"
    }

    saturated_tasks = set(reg.stage("global_route").saturated_tasks)
    assert len(saturated_tasks) == 10
    assert len(naive) < len(saturated_tasks), (
        "the numeric predicate should identify FEWER tasks than the structural "
        f"rule; it found {len(naive)} of {len(saturated_tasks)}"
    )

    # And the rate metrics are why "error is approximately zero" fails outright.
    rates = [
        c
        for c in _all_cells()
        if reg.is_saturated(c[0], c[1], c[3]) and c[1] in {"tpr", "tnr"}
    ]
    assert rates, "tpr/tnr cells sit at their 100% ceiling, not at zero error"


def test_every_task_metric_is_declared() -> None:
    known = {m.id for m in reg.metrics()}
    for t in reg.tasks():
        unknown = set(t.metrics) - known
        assert not unknown, f"{t.id} references unknown metrics {sorted(unknown)}"


def test_every_metric_has_a_direction() -> None:
    for m in reg.metrics():
        assert m.direction in {"higher", "lower"}, (
            f"{m.id} has direction {m.direction!r}"
        )


def test_directions_are_correct() -> None:
    """R² higher-better versus MAE lower-better is the classic inversion."""
    higher = {m.id for m in reg.metrics() if m.direction == "higher"}
    assert higher == {"r2", "tpr", "tnr"}


def test_bias_only_on_mpe_and_mne() -> None:
    biased = {m.id: m.bias for m in reg.metrics() if m.bias is not None}
    assert biased == {"mpe": "optimistic", "mne": "conservative"}


def test_percent_metrics() -> None:
    """Stored as fractions; the x100 happens once, at display."""
    percent = {m.id for m in reg.metrics() if m.percent}
    assert percent == {"mape", "mape_p95", "mape_top5", "tpr", "tnr"}


def test_design_level_matches_granularity() -> None:
    """Redundant fields are acceptable only with a guard that they agree.

    `design_level` governs Phase 3's pooled-vs-per-circuit file choice, so it is
    behaviourally load-bearing; `granularity` is descriptive. They must not drift.
    """
    for t in reg.tasks():
        assert t.design_level == (t.granularity == "design"), t.id
    assert sum(1 for t in reg.tasks() if t.design_level) == 6


@pytest.mark.parametrize(
    ("task_id", "metric_id", "expected"),
    [
        pytest.param("cell_arc_delay_prediction", "mae", 4, id="arc-mae-4dp"),
        pytest.param(
            "cell_arc_delay_prediction", "mape", 2, id="override-does-not-leak"
        ),
        pytest.param("timing_path_slack_prediction", "mpe", 4, id="path-slack-mpe-4dp"),
        pytest.param("total_area_prediction", "mae", 2, id="area-mae-2dp"),
        pytest.param("total_area_prediction", "r2", 3, id="r2-is-3dp"),
    ],
)
def test_precision_for_pairs(task_id: str, metric_id: str, expected: int) -> None:
    assert reg.precision(task_id, metric_id) == expected


def test_precision_overrides_reference_declared_metrics() -> None:
    """A typo in an override key silently does nothing and renders 2dp forever."""
    for t in reg.tasks():
        stray = set(t.precision_overrides) - set(t.metrics)
        assert not stray, f"{t.id} overrides precision for non-member {sorted(stray)}"


def test_nine_pairs_are_four_dp() -> None:
    four = {
        (t.id, m) for t in reg.tasks() for m in t.metrics if reg.precision(t.id, m) == 4
    }
    assert len(four) == 9


def test_unknown_ids_raise() -> None:
    for fn, bad in (
        (reg.task, "total_area"),  # the suffix-dropped form
        (reg.metric, "rmse"),
        (reg.stage, "place_resize"),  # named in prose, absent from Table 8
        (reg.pdk, "iph130"),  # the paper's typo
    ):
        with pytest.raises(KeyError):
            fn(bad)


def test_stage_order_is_contiguous() -> None:
    orders = sorted(s.order for s in reg.stages())
    assert orders == list(range(1, len(orders) + 1))
