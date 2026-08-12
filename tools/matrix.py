"""Everything the matrix template is not allowed to do.

Pure functions. build.py calls panels() once and renders the result; the
template loops over it and reads attributes. No formatting, no arithmetic and no
registry lookup happens inside a template.

THE PERCENT BOUNDARY LIVES HERE. Everything under data/ stores a percent-format
metric as a fraction, and format_bound multiplies by 100 exactly once on its way
to the screen. There is no second multiplication anywhere in the project, and
adding one makes every MAPE cell read as a loss and every TPR cell as a win, in
silence. See docs/DATA_CONTRACT.md, "Percent storage - the single authoritative
rule".
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache

from tools import baseline as bl
from tools import registry as reg

# The two cell states this phase can produce. Phase 4 introduces the full
# CellState enum with the three comparison states and replaces the one call in
# _state() below; nothing else changes.
NO_ENTRY = "no_entry"
SATURATED = "saturated"

STATE_LABELS = {
    NO_ENTRY: "No entry",
    SATURATED: "Saturated",
}

PUBLISHED = "published"
SENTINEL = "sentinel"
DEGENERATE = "degenerate"

# What a cell prints when the paper measured nothing. Table 8's own words are
# "No positive or negative error, n_p = n_n = 0", which the legend carries in
# full; the cell carries the short form. It is deliberately not "0.00" and
# deliberately not blank: one asserts a measurement, the other asserts a gap.
DEGENERATE_MARKER = "0/0"

# Keyed on the enum, not on its string values. BoundKind exists so a drifted
# kind raises at the parse boundary instead of degrading into a silently-False
# comparison, and keying this map on bare strings would hand that back: a typo
# would leave every sentinel rendering as a bare number, with nothing to catch
# it. See tools/baseline.py, BoundKind.
COMPARATOR = {bl.BoundKind.GREATER_THAN: ">", bl.BoundKind.LESS_THAN: "<"}

PERCENT_SCALE = 100


@dataclass(frozen=True, slots=True)
class Cell:
    """One rendered cell.

    `state` is about submissions and drives the colour and the glyph.
    `baseline_kind` is about the paper and drives the three distinct baseline
    treatments. They are separate because a cell can be both `no_entry` and
    `degenerate`, and rendering those two facts through one channel loses the
    difference between "nobody has entered" and "there is nothing to enter
    against".
    """

    task: str
    metric: str
    pdk: str
    stage: str
    state: str
    state_label: str
    baseline_kind: str
    display: str


def format_bound(task_id: str, metric_id: str, bound: bl.Bound) -> str:
    """One bound as the string a reader sees.

    The ONLY place a percent-format metric is multiplied by 100, and the only
    place a sentinel's comparator is attached. A sentinel renders as its
    comparator plus its threshold, never as a bare number: the paper thresholded
    the underlying value away, so printing it without the comparator would claim
    a measurement that does not exist.
    """
    if bound.kind is bl.BoundKind.ABSENT:
        return DEGENERATE_MARKER

    value = bound.value
    if value is None:
        raise ValueError(f"{task_id}/{metric_id}: a non-absent bound has no value")

    spec = reg.metric(metric_id)
    if spec.percent:
        value *= PERCENT_SCALE

    text = f"{value:,.{reg.precision(task_id, metric_id)}f}"
    if spec.percent:
        text = f"{text} %"

    comparator = COMPARATOR.get(bound.kind)
    return text if comparator is None else f"{comparator} {text}"


def _baseline_kind(bound: bl.Bound) -> str:
    if bound.kind is bl.BoundKind.ABSENT:
        return DEGENERATE
    return SENTINEL if bound.kind in COMPARATOR else PUBLISHED


def _state(task_id: str, metric_id: str, stage_id: str) -> str:
    """Saturation is a stage-and-task rule, never a predicate over values.

    Phase 4 replaces this with ranking.cell_state once entries exist. Until then
    a cell is saturated or it is empty, because there is nothing to rank.
    """
    if reg.is_saturated(task_id, metric_id, stage_id):
        return SATURATED
    return NO_ENTRY


def cell(task_id: str, metric_id: str, pdk_id: str, stage_id: str) -> Cell:
    """One live cell. Raises KeyError on a void cell, via the baseline loader."""
    bound = bl.lookup(task_id, metric_id, pdk_id, stage_id).bound
    state = _state(task_id, metric_id, stage_id)
    return Cell(
        task=task_id,
        metric=metric_id,
        pdk=pdk_id,
        stage=stage_id,
        state=state,
        state_label=STATE_LABELS[state],
        baseline_kind=_baseline_kind(bound),
        display=format_bound(task_id, metric_id, bound),
    )


@dataclass(frozen=True, slots=True)
class Row:
    """One metric row within one stage panel.

    `task_rowspan` is the number of rows the task label spans, and it is 0 on
    every row after the first of its task. The template renders the label header
    only when it is non-zero, which is a conditional rather than a computation.
    """

    task_id: str
    task_label: str
    task_rowspan: int
    metric_id: str
    metric_label: str
    cells: tuple[Cell, ...]


@dataclass(frozen=True, slots=True)
class Panel:
    """One stage. Rendered as one table, captioned with the stage transition."""

    stage_id: str
    stage_label: str
    caption: str
    void_tasks: tuple[str, ...]
    rows: tuple[Row, ...]


# The task and metric columns sit left of the PDK columns. Declared here rather
# than as a colspan literal in the template, so a note still spans the whole
# table if the registry ever carries a different number of PDKs.
ROW_HEADER_COLUMNS = 2


@cache
def column_count() -> int:
    """Columns in one panel table: the two row headers plus one per PDK."""
    return ROW_HEADER_COLUMNS + len(reg.pdks())


@cache
def panels() -> tuple[Panel, ...]:
    """The whole grid, in registry order.

    Driven from reg.stages(), reg.tasks() and each task's own metric list, so a
    row exists because the registry says the cell is live and never because a
    template iterated something convenient.
    """
    built: list[Panel] = []
    for stage in reg.stages():
        rows: list[Row] = []
        for task in reg.tasks():
            if reg.is_void(task.id, stage.id):
                continue
            for index, metric_id in enumerate(task.metrics):
                rows.append(
                    Row(
                        task_id=task.id,
                        task_label=task.label,
                        task_rowspan=len(task.metrics) if index == 0 else 0,
                        metric_id=metric_id,
                        metric_label=reg.metric(metric_id).label,
                        cells=tuple(
                            cell(task.id, metric_id, p.id, stage.id) for p in reg.pdks()
                        ),
                    )
                )
        built.append(
            Panel(
                stage_id=stage.id,
                stage_label=stage.label,
                caption=stage.table8_label,
                void_tasks=tuple(reg.task(t).label for t in stage.void_tasks),
                rows=tuple(rows),
            )
        )
    return tuple(built)


@dataclass(frozen=True, slots=True)
class LegendItem:
    """One legend row. `id` doubles as the class the swatch carries, so the
    swatch is painted by the same rule as the cells it explains and the two
    cannot drift."""

    id: str
    label: str
    explanation: str


@cache
def legend() -> tuple[LegendItem, ...]:
    return (
        LegendItem(
            NO_ENTRY, STATE_LABELS[NO_ENTRY], "No submission for this cell yet."
        ),
        LegendItem(
            SATURATED,
            STATE_LABELS[SATURATED],
            "The tool estimate already matches the detailed route value, so this"
            " cell can be tied but not beaten and is never ranked.",
        ),
        LegendItem(
            DEGENERATE,
            DEGENERATE_MARKER,
            "The paper reports no positive or negative error, n_p = n_n = 0."
            " That is a 0/0 rather than a value of zero, so there is no baseline"
            " to compare against.",
        ),
        LegendItem(
            SENTINEL,
            "> or <",
            "The paper published a threshold rather than a value, so the true"
            " number is not recoverable from any source we have.",
        ),
    )
