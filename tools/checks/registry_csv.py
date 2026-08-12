"""Cross-check of data/registry/ against the paper's own numbers.

`docs/sources/table8_baseline.csv` is Table 8 parsed to one tidy row per
(task, metric, stage, pdk), verified by two independent parsers reading the
LaTeX source. It is the only source in this repository that is independent of
the registry, so it is the only thing a registry and its own tests cannot both
misread in the same way.

Three properties make this file worth more than a schema check:

* Every comparison runs in BOTH directions. One-way containment passes on a
  registry that has invented an extra entry, which is how a phantom fifth PDK
  survives the misspelled column header in the published table.
* Join keys are checked for collisions BEFORE the sets are compared. Two entries
  claiming one `table8_label` compare equal as a set while one of them silently
  never resolves.
* Every join key is checked for IDENTITY, not only for membership. Exchanging
  two entries' labels inside one dimension leaves the label set, the per-task
  metric sets and the VOID/DEGENERATE classification all intact, so a purely
  set-based cross-check stays green while each affected cell is scored against
  another cell's published number.
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Protocol

from tools import registry as reg
from tools.checks import register

CSV_PATH = (
    Path(__file__).resolve().parents[2] / "docs" / "sources" / "table8_baseline.csv"
)

TASK_COLUMN = "task"
METRIC_COLUMN = "metric"
STAGE_COLUMN = "stage_transition"
PDK_COLUMN = "pdk"
KIND_COLUMN = "kind"

VOID_KIND = "VOID"
DEGENERATE_KIND = "DEGENERATE"

# Two pieces of the published table's typography, not vocabulary. Table 8 spells
# a stage as a transition into the common target stage, and the lab's task ids
# carry a suffix the paper's row labels do not print.
TRANSITION_SEPARATOR = " to "
TASK_ID_SUFFIX = "_prediction"

SAMPLE = 5

Triple = tuple[str, str, str]
Quad = tuple[str, str, str, str]


class Labelled(Protocol):
    """Any registry row that carries the Table 8 join key.

    Declared read-only so the frozen dataclasses in tools.registry satisfy it.
    """

    @property
    def id(self) -> str: ...

    @property
    def table8_label(self) -> str: ...


def rows() -> tuple[dict[str, str], ...]:
    """The CSV as dicts. Read on every call; this runs once per validation."""
    with CSV_PATH.open(encoding="utf-8") as handle:
        return tuple(csv.DictReader(handle))


def _sample(items: Iterable[object]) -> str:
    """Render a bounded example list, so one systematic error does not print a
    message per cell and bury the other failures."""
    listed = sorted(str(item) for item in items)
    head = ", ".join(listed[:SAMPLE])
    if len(listed) > SAMPLE:
        return f"{head}, ... ({len(listed)} total)"
    return head


def _dimension(
    name: str,
    column: str,
    entries: Sequence[Labelled],
    csv_rows: Sequence[dict[str, str]],
) -> list[str]:
    """Diff one dimension's join keys against the CSV column that carries them."""
    messages: list[str] = []

    counts = Counter(entry.table8_label for entry in entries)
    for label, seen in sorted(counts.items()):
        if seen > 1:
            messages.append(
                f"{name}: table8_label {label!r} is claimed by {seen} entries, "
                "so the join is ambiguous"
            )

    registry_labels = set(counts)
    csv_labels = {row[column] for row in csv_rows}

    missing = csv_labels - registry_labels
    if missing:
        messages.append(
            f"{name}: CSV labels join to no registry entry: {_sample(missing)}"
        )
    extra = registry_labels - csv_labels
    if extra:
        messages.append(
            f"{name}: registry labels appear in no CSV row: {_sample(extra)}"
        )

    return messages


def _fold(text: str) -> str:
    """Letters and digits only, upper case.

    The published table decorates a name with case, spacing and typography the
    lab's ids do not carry: `R^2` against `r2`, `MAPE TOP5` against
    `mape_top5`, `Cell Arc Slew` against `cell_arc_slew`. Folding both sides
    removes exactly that decoration and leaves the name itself, so the two can
    be compared without transcribing a single mapping by hand.
    """
    return "".join(ch for ch in text if ch.isalnum()).upper()


def _published_name(label: str) -> str:
    """A published label with nothing stripped. The default extractor."""
    return label


def _task_published_name(label: str) -> str:
    """Table 8 prints a task's unit inside its own row-group label. The name is
    what precedes it, so `Total Area (u m^2)` names `total_area`."""
    opened = label.rfind("(")
    return label[:opened] if opened != -1 else label


def _stage_published_name(label: str) -> str:
    """Every transition ends at detailed route, so the starting stage is what
    names the row group: `global place to detailed route` names `global_place`."""
    return label.split(TRANSITION_SEPARATOR, 1)[0]


def _task_registry_name(entry_id: str) -> str:
    """The lab's task ids all carry one shared suffix, which the paper's row
    labels do not print. This drops it and nothing else; an id without it is
    compared whole."""
    return entry_id.removesuffix(TASK_ID_SUFFIX)


def _registry_name(entry_id: str) -> str:
    """An id with nothing stripped. The default extractor."""
    return entry_id


def _identity(
    name: str,
    entries: Sequence[Labelled],
    *,
    published_name: Callable[[str], str] = _published_name,
    registry_name: Callable[[str], str] = _registry_name,
) -> list[str]:
    """Every entry's join key must spell the entry that claims it.

    Membership is not identity. `_dimension` proves each label appears in the
    published column and each column value has a home, which two entries trading
    labels satisfies perfectly. This restates the join as a per-entry fact: the
    row `mpe` reads is the row Table 8 prints as MPE, and no other.

    Where a label names a DIFFERENT entry, the message says which, because a
    permutation is otherwise indistinguishable from a typo in the diagnostics
    and the two are fixed differently.
    """
    messages: list[str] = []

    claimed: dict[str, str] = {}
    for entry in entries:
        key = _fold(registry_name(entry.id))
        if key in claimed:
            messages.append(
                f"{name}: {entry.id!r} and {claimed[key]!r} reduce to the same "
                "name, so no label can distinguish them"
            )
        claimed[key] = entry.id

    for entry in entries:
        mine = _fold(registry_name(entry.id))
        printed = _fold(published_name(entry.table8_label))
        if printed == mine:
            continue
        named = claimed.get(printed)
        if named is None:
            messages.append(
                f"{name}: {entry.id!r} declares the Table 8 label "
                f"{entry.table8_label!r}, which names no registry entry"
            )
        else:
            messages.append(
                f"{name}: {entry.id!r} declares the Table 8 label "
                f"{entry.table8_label!r}, which is the published row for "
                f"{named!r}"
            )

    return messages


def _label_index(entries: Sequence[Labelled]) -> dict[str, str]:
    return {entry.table8_label: entry.id for entry in entries}


def _resolved_quads(csv_rows: Sequence[dict[str, str]]) -> dict[Quad, str]:
    """CSV rows keyed by registry ids, dropping any row whose labels do not join.

    Unjoinable rows are already reported by the dimension diff; carrying them
    further would raise KeyError and hide every later message behind a traceback.
    """
    task_ids = _label_index(reg.tasks())
    metric_ids = _label_index(reg.metrics())
    stage_ids = _label_index(reg.stages())
    pdk_ids = _label_index(reg.pdks())

    resolved: dict[Quad, str] = {}
    for row in csv_rows:
        task_id = task_ids.get(row[TASK_COLUMN])
        metric_id = metric_ids.get(row[METRIC_COLUMN])
        stage_id = stage_ids.get(row[STAGE_COLUMN])
        pdk_id = pdk_ids.get(row[PDK_COLUMN])
        if task_id is None or metric_id is None or stage_id is None or pdk_id is None:
            continue
        resolved[(task_id, metric_id, pdk_id, stage_id)] = row[KIND_COLUMN]
    return resolved


def _metric_sets(csv_rows: Sequence[dict[str, str]]) -> list[str]:
    """Per-task metric sets. Table 8's rows are ragged, so this is the check that
    a task did not quietly inherit another task's row set."""
    messages: list[str] = []

    published: defaultdict[str, set[str]] = defaultdict(set)
    for row in csv_rows:
        published[row[TASK_COLUMN]].add(row[METRIC_COLUMN])

    for task in reg.tasks():
        declared = {reg.metric(metric_id).table8_label for metric_id in task.metrics}
        found = published.get(task.table8_label, set())
        for label in sorted(found - declared):
            messages.append(
                f"{task.id}: Table 8 publishes a {label!r} row, "
                "the registry does not declare it"
            )
        for label in sorted(declared - found):
            messages.append(
                f"{task.id}: the registry declares {label!r}, "
                "Table 8 publishes no such row"
            )

    return messages


def _coverage(
    resolved: dict[Quad, str], csv_rows: Sequence[dict[str, str]]
) -> list[str]:
    """Every cell the registry describes is published exactly once, and nothing
    is published that the registry does not describe.

    Void cells are included: Table 8 carries a row for them, stamped VOID.
    """
    messages: list[str] = []

    expected = {
        (task_id, metric_id, pdk.id, stage.id)
        for task_id, metric_id in reg.metric_rows()
        for pdk in reg.pdks()
        for stage in reg.stages()
    }

    if len(resolved) != len(csv_rows):
        seen: Counter[Quad] = Counter()
        for row in csv_rows:
            seen[
                (
                    row[TASK_COLUMN],
                    row[METRIC_COLUMN],
                    row[PDK_COLUMN],
                    row[STAGE_COLUMN],
                )
            ] += 1
        duplicated = {quad for quad, count in seen.items() if count > 1}
        if duplicated:
            messages.append(f"coverage: CSV rows are duplicated: {_sample(duplicated)}")

    missing = expected - set(resolved)
    if missing:
        messages.append(
            f"coverage: registry cells with no published row: {_sample(missing)}"
        )
    unknown = set(resolved) - expected
    if unknown:
        messages.append(
            "coverage: published rows the registry does not describe: "
            f"{_sample(unknown)}"
        )

    return messages


def _kinds(resolved: dict[Quad, str]) -> list[str]:
    """The CSV's kind column against the registry's structural classification.

    Restated in BOTH directions. `VOID` subtracts a cell from the grid and
    `DEGENERATE` does not, so swapping them leaves every headline count intact
    while mistyping a whole block of cells.
    """
    messages: list[str] = []

    by_triple: defaultdict[Triple, set[str]] = defaultdict(set)
    for (task_id, metric_id, _pdk_id, stage_id), kind in resolved.items():
        by_triple[(task_id, metric_id, stage_id)].add(kind)

    inconsistent = {triple for triple, kinds in by_triple.items() if len(kinds) > 1}
    if inconsistent:
        messages.append(
            "kind: a cell's kind varies by PDK, which the registry cannot "
            f"express: {_sample(inconsistent)}"
        )

    csv_void = {triple for triple, kinds in by_triple.items() if kinds == {VOID_KIND}}
    csv_degenerate = {
        triple for triple, kinds in by_triple.items() if kinds == {DEGENERATE_KIND}
    }

    registry_void = {
        (task_id, metric_id, stage.id)
        for task_id, metric_id in reg.metric_rows()
        for stage in reg.stages()
        if reg.is_void(task_id, stage.id)
    }
    registry_degenerate = {
        (task_id, metric_id, stage.id)
        for task_id, metric_id in reg.metric_rows()
        for stage in reg.stages()
        if reg.is_degenerate(task_id, metric_id, stage.id)
    }

    for label, from_csv, from_registry in (
        (VOID_KIND, csv_void, registry_void),
        (DEGENERATE_KIND, csv_degenerate, registry_degenerate),
    ):
        unclassified = from_csv - from_registry
        if unclassified:
            messages.append(
                f"kind: the CSV stamps {label} where the registry does not: "
                f"{_sample(unclassified)}"
            )
        overclassified = from_registry - from_csv
        if overclassified:
            messages.append(
                f"kind: the registry classifies {label} where the CSV does not: "
                f"{_sample(overclassified)}"
            )

    return messages


@register("registry_csv")
def check() -> list[str]:
    """Return one message per mismatch. Empty means the registry matches Table 8."""
    csv_rows = rows()

    messages: list[str] = []
    messages += _dimension("tasks", TASK_COLUMN, reg.tasks(), csv_rows)
    messages += _dimension("metrics", METRIC_COLUMN, reg.metrics(), csv_rows)
    messages += _dimension("stages", STAGE_COLUMN, reg.stages(), csv_rows)
    messages += _dimension("pdks", PDK_COLUMN, reg.pdks(), csv_rows)
    messages += _identity(
        "tasks",
        reg.tasks(),
        published_name=_task_published_name,
        registry_name=_task_registry_name,
    )
    messages += _identity("metrics", reg.metrics())
    messages += _identity("stages", reg.stages(), published_name=_stage_published_name)
    messages += _identity("pdks", reg.pdks())
    messages += _metric_sets(csv_rows)

    resolved = _resolved_quads(csv_rows)
    messages += _coverage(resolved, csv_rows)
    messages += _kinds(resolved)
    return messages
