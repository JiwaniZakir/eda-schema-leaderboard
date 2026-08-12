"""Registry loading and derived counts.

Expected values live here, in tests. They must never appear in tools/.
"""

from __future__ import annotations

import pytest

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
    with pytest.raises(KeyError):
        reg.metric("not_a_metric")


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
