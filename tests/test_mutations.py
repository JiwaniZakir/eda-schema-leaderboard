"""Mutations that the pre-reset suite survived.

Each one perturbs a registry file in a temp copy, points the loader at it, and
asserts something fails. If a test here passes with the mutation applied, that
value has no verification and the suite is decorative.

Every test asserts twice. Once on the observation through the loader, which
proves the mutated value actually reaches a caller, and once by calling the
REAL guarding test from the sibling suite, which proves the guard exists rather
than being re-implemented here. Deleting a guard therefore breaks this file too.
"""

from __future__ import annotations

import itertools
import json
import shutil
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
import test_registry as suite
import test_registry_csv as csv_suite

from tools import baseline as bl
from tools import registry as reg
from tools.checks import registry_csv

Mutation = Callable[[list[dict[str, Any]]], None]


def _clear_caches() -> None:
    """Drop every functools cache in tools.registry and tools.baseline.

    Enumerated by introspection rather than by name: a cached function added
    later would otherwise keep serving values read from the real registry, and
    the mutation would look like it had no effect - a false green in the one
    file whose whole job is to prove mutations are caught.

    tools.baseline is included because its label index is derived from the
    registry, so a stale cache there would make a mutated join look harmless.
    """
    for module in (reg, bl):
        for name in dir(module):
            clear = getattr(getattr(module, name), "cache_clear", None)
            if callable(clear):
                clear()


@pytest.fixture
def mutable_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A writable copy of data/registry/, with the loader pointed at it.

    The committed files are never touched. A test that edited them in place and
    then failed would leave the repository holding a corrupt registry.
    """
    dest = tmp_path / "registry"
    shutil.copytree(reg.REGISTRY_DIR, dest)
    monkeypatch.setattr(reg, "REGISTRY_DIR", dest)
    _clear_caches()
    yield dest
    _clear_caches()


def _rewrite(path: Path, mutate: Mutation) -> None:
    rows: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
    mutate(rows)
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    _clear_caches()


def _guard_fails(guard: Callable[[], None]) -> bool:
    """True when the real test rejects the mutated registry."""
    try:
        guard()
    except AssertionError:
        return True
    return False


def test_reversed_stage_order_is_caught(mutable_registry: Path) -> None:
    """Pre-reset this passed. sorted(orders) == range(1, n+1) is true on a
    reversed sequence."""

    def mutate(rows: list[dict[str, Any]]) -> None:
        n = len(rows)
        for r in rows:
            r["order"] = n + 1 - r["order"]

    _rewrite(mutable_registry / "stages.json", mutate)

    with pytest.raises(AssertionError):
        assert tuple(s.id for s in reg.stages()) == suite.STAGE_IDS_IN_ORDER
    assert _guard_fails(suite.test_stage_ids_are_in_order_not_merely_a_set)


def test_corrupted_circuit_attribute_is_caught(mutable_registry: Path) -> None:
    """Pre-reset, ethernet.registers 10,544 -> 87 left 115/115 green."""

    def mutate(rows: list[dict[str, Any]]) -> None:
        for r in rows:
            if r["id"] == "ethernet":
                r["registers"] = 87

    _rewrite(mutable_registry / "circuits.json", mutate)

    eth = next(c for c in reg.circuits() if c.id == "ethernet")
    with pytest.raises(AssertionError):
        assert eth.registers == 10544
    assert _guard_fails(suite.test_ethernet_attributes_match_table_2)


def test_swapped_degeneracy_and_saturation_is_caught(mutable_registry: Path) -> None:
    """The dangerous one: 880 and 232 both stay correct while 24 cells are
    silently mistyped. Only the partition catches it."""

    def mutate(rows: list[dict[str, Any]]) -> None:
        for r in rows:
            if r["id"] == "global_route":
                r["degenerate_tasks"] = []
                r["degenerate_metrics"] = []

    _rewrite(mutable_registry / "stages.json", mutate)

    assert len(reg.live_cells()) == 880, "the total is still right, as expected"
    assert len(reg.live_combos()) == 232, "and so is the combo count"

    degen = [c for c in reg.live_cells() if reg.is_degenerate(c[0], c[1], c[3])]
    sat = [c for c in reg.live_cells() if reg.is_saturated(c[0], c[1], c[3])]
    with pytest.raises(AssertionError):
        assert len(degen) == 24 and len(sat) == 120
    assert _guard_fails(suite.test_the_partition_not_just_the_total)
    assert registry_csv.check() != [], "the CSV cross-check catches it independently"


def test_a_phantom_pdk_is_caught(mutable_registry: Path) -> None:
    """Table 8 misspells IHP130 as IPH130 five times."""

    def mutate(rows: list[dict[str, Any]]) -> None:
        for r in rows:
            if r["id"] == "ihp130":
                r["table8_label"] = "IPH130"

    _rewrite(mutable_registry / "pdks.json", mutate)

    assert registry_csv.check() != [], "the CSV cross-check must reject this"
    assert _guard_fails(csv_suite.test_every_pdk_label_joins)


def _swap_labels(path: Path, id_a: str, id_b: str) -> None:
    """Exchange two entries' table8_label values, leaving everything else alone."""

    def mutate(rows: list[dict[str, Any]]) -> None:
        by_id = {r["id"]: r for r in rows}
        by_id[id_a]["table8_label"], by_id[id_b]["table8_label"] = (
            by_id[id_b]["table8_label"],
            by_id[id_a]["table8_label"],
        )

    _rewrite(path, mutate)


def test_swapped_metric_labels_reassign_real_baselines(mutable_registry: Path) -> None:
    """mpe and mne trade join keys, so every slack cell is scored against the
    opposite error.

    Table 8 publishes Worst Slack at NG45 floorplan as MPE 0.06 and MNE 3.68.
    After the swap the optimistic-error cell carries the conservative number.
    docs/DATA_CONTRACT.md calls ranking those two as interchangeable magnitudes
    a correctness bug rather than a style choice, so this is the observation
    half of the mutation: the wrong value really does reach a caller.
    """
    _swap_labels(mutable_registry / "metrics.json", "mpe", "mne")

    built = {e.key: e for e in bl.build()}
    mpe = built[("worst_slack_prediction", "mpe", "ng45", "floorplan")]
    mne = built[("worst_slack_prediction", "mne", "ng45", "floorplan")]
    with pytest.raises(AssertionError):
        assert (mpe.bound.value, mne.bound.value) == (0.06, 3.68)
    assert (mpe.bound.value, mne.bound.value) == (3.68, 0.06), "the swap took effect"

    assert registry_csv.check() != [], "the CSV cross-check must reject this"
    assert _guard_fails(csv_suite.test_every_label_names_its_own_entry)


def test_swapped_pdk_labels_reassign_real_baselines(mutable_registry: Path) -> None:
    """sky130 and ihp130 trade join keys.

    Table 8 publishes Total Area MAE at floorplan as 18,567.03 for SKY130 and
    48,738.62 for IHP130. Both stay in the file, both stay published, and both
    land on the wrong PDK.
    """
    _swap_labels(mutable_registry / "pdks.json", "sky130", "ihp130")

    built = {e.key: e for e in bl.build()}
    sky = built[("total_area_prediction", "mae", "sky130", "floorplan")]
    ihp = built[("total_area_prediction", "mae", "ihp130", "floorplan")]
    with pytest.raises(AssertionError):
        assert (sky.bound.value, ihp.bound.value) == (18567.03, 48738.62)
    assert (sky.bound.value, ihp.bound.value) == (48738.62, 18567.03)

    assert registry_csv.check() != [], "the CSV cross-check must reject this"
    assert _guard_fails(csv_suite.test_every_label_names_its_own_entry)


REGISTRY_FILES_WITH_LABELS = ("tasks.json", "metrics.json", "stages.json", "pdks.json")


def test_no_pairwise_label_swap_survives_the_cross_check(
    mutable_registry: Path,
) -> None:
    """Every permutation of the join key, not the eight that happened to be
    noticed.

    A swap inside one dimension preserves the label SET, the per-task metric
    sets and the VOID/DEGENERATE classification, so a set-based join check sees
    nothing while data/baseline.json is rebuilt with between 62 and 354 cells
    carrying another cell's published number. All 137 pairs are swept here
    because the property under test is per-entry identity, and a sample of it
    is exactly what let this through the first time.
    """
    survivors: list[str] = []
    swept = 0
    for filename in REGISTRY_FILES_WITH_LABELS:
        path = mutable_registry / filename
        original = path.read_text(encoding="utf-8")
        ids = [row["id"] for row in json.loads(original)]
        for id_a, id_b in itertools.combinations(ids, 2):
            swept += 1
            _swap_labels(path, id_a, id_b)
            messages = registry_csv.check()
            if not messages:
                survivors.append(f"{filename}: {id_a} <-> {id_b}")
            elif not any(id_a in m and id_b in m for m in messages):
                survivors.append(
                    f"{filename}: {id_a} <-> {id_b} is rejected but no message "
                    f"names both entries: {messages}"
                )
            path.write_text(original, encoding="utf-8")
            _clear_caches()

    assert not survivors, survivors
    # Guards the guard. A dimension that lost its entries would sweep nothing
    # and report no survivors, which reads identically to a clean pass.
    assert swept == 66 + 55 + 10 + 6, f"swept {swept} pairs, expected 137"
