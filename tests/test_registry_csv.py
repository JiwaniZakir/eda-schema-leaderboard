"""The registry must agree with docs/sources/table8_baseline.csv.

Written against the CSV deliberately, not against the registry, so a shared
misreading between the registry and its own tests cannot self-confirm.
"""

from __future__ import annotations

import csv
from pathlib import Path

from tools import registry as reg
from tools.checks import registry_csv

CSV_PATH = (
    Path(__file__).resolve().parent.parent / "docs" / "sources" / "table8_baseline.csv"
)


def _csv_rows() -> list[dict[str, str]]:
    with CSV_PATH.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_the_check_passes_on_current_data() -> None:
    assert registry_csv.check() == []


def test_every_task_label_joins() -> None:
    csv_labels = {r["task"] for r in _csv_rows()}
    reg_labels = {t.table8_label for t in reg.tasks()}
    assert csv_labels == reg_labels


def test_every_metric_label_joins() -> None:
    csv_labels = {r["metric"] for r in _csv_rows()}
    reg_labels = {m.table8_label for m in reg.metrics()}
    assert csv_labels == reg_labels


def test_every_stage_label_joins() -> None:
    csv_labels = {r["stage_transition"] for r in _csv_rows()}
    reg_labels = {s.table8_label for s in reg.stages()}
    assert csv_labels == reg_labels


def test_every_pdk_label_joins() -> None:
    csv_labels = {r["pdk"] for r in _csv_rows()}
    reg_labels = {p.table8_label for p in reg.pdks()}
    assert csv_labels == reg_labels


def _fold(text: str) -> str:
    """Letters and digits only, upper case.

    Table 8 decorates a name with spacing, case and typography that the lab's
    ids do not carry: `R^2` against `r2`, `MAPE TOP5` against `mape_top5`,
    `Cell Arc Slew` against `cell_arc_slew`. Folding both sides removes exactly
    that decoration and leaves the name itself.
    """
    return "".join(ch for ch in text if ch.isalnum()).upper()


def test_every_label_names_its_own_entry() -> None:
    """Each join key must spell the entry that claims it.

    Set equality is not identity. Exchanging two entries' table8_label values
    inside one dimension keeps the label set, the per-task metric sets and the
    VOID/DEGENERATE classification all intact, so every set-based check stays
    green while the join silently hands each cell the other one's published
    number. Restated here against the paper's own printed strings.
    """
    published = _csv_rows()
    mismatches: list[str] = []

    for task in reg.tasks():
        label = task.table8_label
        # Table 8 prints the unit inside the row-group label; the name is what
        # precedes it, and the lab's ids carry a shared `_prediction` suffix.
        stem = label[: label.rfind("(")] if "(" in label else label
        if _fold(stem) != _fold(task.id.removesuffix("_prediction")):
            mismatches.append(f"task {task.id} declares {label!r}")

    for metric in reg.metrics():
        if _fold(metric.table8_label) != _fold(metric.id):
            mismatches.append(f"metric {metric.id} declares {metric.table8_label!r}")

    for stage in reg.stages():
        # Every transition ends at detailed route; the starting stage names it.
        head = stage.table8_label.split(" to ")[0]
        if _fold(head) != _fold(stage.id):
            mismatches.append(f"stage {stage.id} declares {stage.table8_label!r}")

    for pdk in reg.pdks():
        if _fold(pdk.table8_label) != _fold(pdk.id):
            mismatches.append(f"pdk {pdk.id} declares {pdk.table8_label!r}")

    assert not mismatches, mismatches

    # Guards the guard: a label that names its entry but appears in no published
    # row would satisfy the loop above vacuously.
    for column, labels in (
        ("task", {t.table8_label for t in reg.tasks()}),
        ("metric", {m.table8_label for m in reg.metrics()}),
        ("stage_transition", {s.table8_label for s in reg.stages()}),
        ("pdk", {p.table8_label for p in reg.pdks()}),
    ):
        assert labels <= {row[column] for row in published}


def test_table8_labels_are_unique_per_registry() -> None:
    """Duplicate detection BEFORE set comparison. Comparing sets alone hides a
    collision that silently drops a mapping."""
    for rows in (reg.tasks(), reg.metrics(), reg.stages(), reg.pdks()):
        labels = [r.table8_label for r in rows]
        assert len(labels) == len(set(labels))


def test_per_task_metric_sets_match_the_csv() -> None:
    from collections import defaultdict

    csv_sets: defaultdict[str, set[str]] = defaultdict(set)
    for r in _csv_rows():
        csv_sets[r["task"]].add(r["metric"])

    for t in reg.tasks():
        expected = {reg.metric(m).table8_label for m in t.metrics}
        assert csv_sets[t.table8_label] == expected, t.id


def test_kinds_match_the_registry_classification() -> None:
    """Restate the classification NEGATIVELY from the CSV, as a cross-check on
    the registry's positive enumeration."""
    by_kind: dict[str, set[tuple[str, str, str]]] = {"VOID": set(), "DEGENERATE": set()}
    tl = {t.table8_label: t.id for t in reg.tasks()}
    ml = {m.table8_label: m.id for m in reg.metrics()}
    sl = {s.table8_label: s.id for s in reg.stages()}

    for r in _csv_rows():
        if r["kind"] in by_kind:
            by_kind[r["kind"]].add(
                (tl[r["task"]], ml[r["metric"]], sl[r["stage_transition"]])
            )

    for t, m, s in by_kind["VOID"]:
        assert reg.is_void(t, s), f"CSV says VOID, registry disagrees: {t} {m} {s}"
    for t, m, s in by_kind["DEGENERATE"]:
        assert reg.is_degenerate(t, m, s), f"CSV says DEGENERATE: {t} {m} {s}"
