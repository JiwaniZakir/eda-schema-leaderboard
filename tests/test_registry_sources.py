"""Cross-check the registry against docs/sources/, an independent source.

PLAN.md's Phase 1 gate requires that "circuits, metal layers, utilization and
units are asserted against docs/sources/". Before this module all four were
asserted against literals re-typed inside tests/test_registry.py, which is not
an independent source: a transposed digit propagates into the registry and its
own test together and stays green permanently. That is the exact failure the
pre-reset audit named, where mutating ethernet.registers from 10,544 to 87 left
all 115 tests passing.

Eighty-six transcribed values are covered here, and every one has been shown to
fail the suite when mutated:

    54  circuit attributes      18 circuits x inputs, outputs, registers
     4  metal_layers            one per PDK
     4  utilization             one per PDK
    12  utilization_sweep       3 sweep points per PDK
    12  task units              one per task

The first four groups come from table2_circuits.csv and pdk_physical.csv, which
were extracted from the paper for this purpose. Unlike docs/sources/verbatim/
they are committed, so the check runs in CI and on a fresh clone.

Units need no extra file. Table 8 prints each task's unit inside its own
row-group label, so table8_baseline.csv - the artifact two independent parsers
agreed on cell for cell - is the source, and the label is parsed back apart
here.

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


def test_pdk_utilization_matches_the_paper() -> None:
    """Core utilization and its sweep range, against the source rather than a
    literal re-typed here.

    The paper sets 40 % for ASAP7 and NG45 and 30 % for SKY130 and IHP130, to
    account for their smaller metal stacks. Nothing downstream can rediscover a
    wrong value: utilization is an input to the flow, not a published result, so
    a transposed digit propagates silently forever.
    """
    rows = _rows("pdk_physical.csv")
    paper_base = {r["pdk"].lower(): round(float(r["utilization"]), 6) for r in rows}
    paper_sweep = {
        r["pdk"].lower(): tuple(
            round(float(v), 6) for v in r["utilization_sweep"].split("|")
        )
        for r in rows
    }

    registry_base = {p.id: round(p.utilization, 6) for p in reg.pdks()}
    registry_sweep = {
        p.id: tuple(round(v, 6) for v in p.utilization_sweep) for p in reg.pdks()
    }

    assert registry_base == paper_base
    assert registry_sweep == paper_sweep


def test_every_pdk_base_utilization_appears_in_its_own_sweep() -> None:
    """A sweep that does not contain the base is a transcription error in one of
    the two columns, and comparing each column separately cannot see it."""
    for pdk in reg.pdks():
        assert round(pdk.utilization, 6) in {
            round(v, 6) for v in pdk.utilization_sweep
        }, f"{pdk.id}: base utilization {pdk.utilization} is not in its sweep"


# Typography only. Table 8 flattens LaTeX \mu to an ASCII "u" and a superscript
# to a caret, so the two spellings of one unit have to be brought together
# before they can be compared. This map holds NO task-to-unit assignment: every
# such fact comes from the CSV, which is why substituting a wrong unit into the
# registry fails this test.
_UNIT_ASCII = {"µ": "u", "μ": "u", "²": "^2", "³": "^3"}


def _canonical_unit(text: str) -> str:
    return "".join(_UNIT_ASCII.get(ch, ch) for ch in text if not ch.isspace())


def test_task_units_match_the_unit_the_paper_prints() -> None:
    """Table 8 prints each task's unit inside its own row-group label, so the
    published table is the source for `unit` and no re-typed literal is needed.

    `unit` had zero coverage anywhere before this: changing total_area's unit to
    "furlongs" left the whole suite green. It is read at the display boundary of
    every cell page, so a wrong one is wrong on every page at once.
    """
    published = {r["task"] for r in _rows("table8_baseline.csv")}

    checked = 0
    mismatches: list[str] = []
    for task in reg.tasks():
        assert task.table8_label in published, f"{task.id} joins to no published row"
        # Read the unit out of the paper's own string, not the registry's.
        label = next(text for text in published if text == task.table8_label)
        opened, closed = label.rfind("("), label.rfind(")")
        assert opened != -1 and closed > opened, (
            f"{task.id}: Table 8 label {label!r} prints no unit, so this check "
            "would pass vacuously"
        )
        paper_unit = _canonical_unit(label[opened + 1 : closed])
        assert paper_unit, f"{task.id}: empty unit parsed from {label!r}"
        checked += 1
        if _canonical_unit(task.unit) != paper_unit:
            mismatches.append(
                f"{task.id}: registry unit {task.unit!r} "
                f"canonicalizes to {_canonical_unit(task.unit)!r}, "
                f"Table 8 prints {paper_unit!r}"
            )

    assert not mismatches, mismatches
    assert checked == len(reg.tasks())


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
