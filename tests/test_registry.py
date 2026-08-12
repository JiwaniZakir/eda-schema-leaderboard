"""Registry loading and derived counts.

Expected values live here, in tests. They must never appear in tools/.
"""

from __future__ import annotations

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
