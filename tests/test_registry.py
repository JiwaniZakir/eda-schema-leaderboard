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
