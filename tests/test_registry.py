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
