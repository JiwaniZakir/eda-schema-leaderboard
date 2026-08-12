"""Cross-check the registry against docs/sources/, an independent source.

These 58 values had NO check before 2026-08-11. PLAN.md claimed circuits, metal
layers and utilization were "cross-checked against docs/sources/", but the only
file there was table8_baseline.csv, which contains none of them. The tests
asserted against literals copied into the test file instead, so a transposed
digit would propagate into the registry and its own test together and stay green
permanently. That is the exact gap the pre-reset audit named, and mutating
ethernet.registers from 10,544 to 87 left all 115 tests passing.

table2_circuits.csv and pdk_physical.csv were extracted from the paper to close
it. Unlike docs/sources/verbatim/, they are committed, so this check runs in CI
and on a fresh clone.

Deliberately reads the CSVs itself rather than going through any tools/ helper.
A test that reaches its expected values through the same code path as the thing
it checks verifies nothing.
"""

from __future__ import annotations

import csv
from pathlib import Path

from tools import registry as reg

SOURCES = Path(__file__).resolve().parent.parent / "docs" / "sources"


def _rows(name: str) -> list[dict[str, str]]:
    with (SOURCES / name).open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_every_circuit_attribute_matches_table_2() -> None:
    """All 54 values, not just ethernet's three."""
    paper = {r["circuit"]: r for r in _rows("table2_circuits.csv")}
    registry = {c.id: c for c in reg.circuits()}

    assert set(registry) == set(paper)

    mismatches = [
        f"{cid}.{field}: registry={getattr(registry[cid], field)} paper={want[field]}"
        for cid, want in sorted(paper.items())
        for field in ("inputs", "outputs", "registers")
        if getattr(registry[cid], field) != int(want[field])
    ]
    assert not mismatches, mismatches


def test_metal_layer_counts_match_the_paper() -> None:
    rows = _rows("pdk_physical.csv")
    paper = {r["pdk"].lower(): int(r["metal_layers"]) for r in rows}
    registry = {p.id: p.metal_layers for p in reg.pdks()}
    assert registry == paper


def test_the_source_csv_covers_every_circuit_the_registry_declares() -> None:
    """Guards the check itself. If the CSV silently lost rows, the comparison
    above would still pass on whatever remained, so the count is pinned here."""
    assert len(_rows("table2_circuits.csv")) == 18
    assert len(_rows("pdk_physical.csv")) == 4


def test_void_and_degenerate_cell_sets_match_the_published_table() -> None:
    """Sets, not counts.

    Counting alone passes when degeneracy and saturation are swapped: 40 void
    and 24 degenerate stay 40 and 24 while 24 cells are silently mistyped. This
    compares which cells, keyed on the table8 labels the paper itself prints.
    """
    published = _rows("table8_baseline.csv")
    csv_void = {
        (r["task"], r["metric"], r["pdk"], r["stage_transition"])
        for r in published
        if r["kind"] == "VOID"
    }
    csv_degenerate = {
        (r["task"], r["metric"], r["pdk"], r["stage_transition"])
        for r in published
        if r["kind"] == "DEGENERATE"
    }

    task_label = {t.id: t.table8_label for t in reg.tasks()}
    metric_label = {m.id: m.table8_label for m in reg.metrics()}
    stage_label = {s.id: s.table8_label for s in reg.stages()}
    pdk_label = {p.id: p.table8_label for p in reg.pdks()}

    reg_void: set[tuple[str, str, str, str]] = set()
    reg_degenerate: set[tuple[str, str, str, str]] = set()
    for task in reg.tasks():
        for metric_id in task.metrics:
            for pdk in reg.pdks():
                for stage in reg.stages():
                    key = (
                        task_label[task.id],
                        metric_label[metric_id],
                        pdk_label[pdk.id],
                        stage_label[stage.id],
                    )
                    if reg.is_void(task.id, stage.id):
                        reg_void.add(key)
                    elif reg.is_degenerate(task.id, metric_id, stage.id):
                        reg_degenerate.add(key)

    assert reg_void == csv_void
    assert reg_degenerate == csv_degenerate
