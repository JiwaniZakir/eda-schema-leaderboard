"""Ranking, comparison and cell state.

One place reads `direction`, `bias` and the published sentinels, so Phase 6's
matrix and Phase 7's cell pages cannot drift into two different answers.

Three things here are easy to get wrong and expensive to get wrong:

**Comparison returns four values, not a bool.** For the 32 sentinel cells the
underlying number does not exist - the paper thresholded it away. A submission at
R² = -0.5 genuinely beats `< -1`, but one at -3 is genuinely undecidable, and
rendering that as a loss would be a fabrication.

**Sentinels are published in display units.** `> 10000 %` against a MAPE stored
as a fraction parses to 100.0, not 10000.0. Get this wrong and every real
submission appears to beat the sentinel, because 1.2269 < 10000 is trivially true.

**Equality is decided at display precision.** Exact float equality makes
`matches_baseline` unreachable, and tying is the best achievable outcome on
roughly 132 cells. Table 8's values are themselves rounded, so a published number
is only meaningful to its published precision.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isnan

from tools import registry as reg


class Comparison(StrEnum):
    BETTER = "better"
    EQUAL = "equal"
    WORSE = "worse"
    UNDECIDABLE = "undecidable"


class CellState(StrEnum):
    BEATS_BASELINE = "beats_baseline"
    MATCHES_BASELINE = "matches_baseline"
    BASELINE_LEADS = "baseline_leads"
    NO_ENTRY = "no_entry"
    SATURATED = "saturated"


class BoundKind(StrEnum):
    EXACT = "exact"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    ABSENT = "absent"


@dataclass(frozen=True, slots=True)
class Bound:
    """A value that may be exact, one-sided, or absent.

    Always held in **registry units**: a fraction for percent-format metrics.
    """

    kind: BoundKind
    value: float | None = None

    @classmethod
    def exact(cls, value: float) -> Bound:
        if isnan(value):
            raise ValueError("NaN cannot be ranked; exclude the entry instead")
        return cls(BoundKind.EXACT, value)

    @classmethod
    def absent(cls) -> Bound:
        """A baseline that was never measured, as in the 24 degenerate cells."""
        return cls(BoundKind.ABSENT)

    @classmethod
    def parse(cls, metric_id: str, published: str) -> Bound:
        """Read a published Table 8 string, converting display units to storage.

        `> 10000 %` on a percent metric becomes `greater_than 100.0`.
        """
        text = published.strip()
        if not text:
            return cls.absent()

        m = reg.metric(metric_id)
        scale = 100.0 if m.percent else 1.0

        kind = BoundKind.EXACT
        if text.startswith(">"):
            kind, text = BoundKind.GREATER_THAN, text[1:]
        elif text.startswith("<"):
            kind, text = BoundKind.LESS_THAN, text[1:]

        number = float(text.replace("%", "").replace(",", "").strip()) / scale
        return cls(kind, number)


def rank_key(metric_id: str, value: float) -> float:
    """Sort key that is always ascending, best first.

    Direction is read here and nowhere else, so no caller ever has to remember
    that R² inverts.
    """
    if isnan(value):
        raise ValueError(f"NaN is not rankable for metric {metric_id!r}")
    return -value if reg.metric(metric_id).direction == "higher" else value


def slack_rank_key(mpe: float, mne: float) -> tuple[float, float]:
    """Order a slack task's results when one sequence is needed across metrics.

    Optimistic error leads, because an optimistic slack prediction hides a real
    timing violation and that is the failure with silicon consequences.

    **Known degenerate case, accepted deliberately.** A model that always predicts
    wildly pessimistic slack never overestimates, scores `mpe = 0`, and takes
    first place here while being useless. It is not patched, because `mae` is a
    separate cell in the same grid and such a model places last there. Phase 5's
    plausibility layer flags the combination. Do not "fix" this into a weighted
    blend; the paper specifies no exchange rate and inventing one would be us
    fabricating a number the science does not support.
    """
    return (mpe, mne)


def compare(
    task_id: str, metric_id: str, challenger: Bound, incumbent: Bound
) -> Comparison:
    """Is `challenger` better than `incumbent` on this metric?"""
    if BoundKind.ABSENT in (challenger.kind, incumbent.kind):
        # Nothing can be recorded as beating a baseline that was never measured.
        return Comparison.UNDECIDABLE

    assert challenger.value is not None and incumbent.value is not None

    if challenger.kind is BoundKind.EXACT and incumbent.kind is BoundKind.EXACT:
        dp = reg.precision(task_id, metric_id)
        if round(challenger.value, dp) == round(incumbent.value, dp):
            return Comparison.EQUAL
        a = rank_key(metric_id, challenger.value)
        b = rank_key(metric_id, incumbent.value)
        return Comparison.BETTER if a < b else Comparison.WORSE

    if challenger.kind is not BoundKind.EXACT:
        # Two one-sided bounds, or a one-sided challenger, decide nothing.
        return Comparison.UNDECIDABLE

    # Incumbent is one-sided: beatable only from the defined side of the
    # threshold. `x == t` counts as BETTER, because the incumbent is strictly
    # beyond t.
    threshold = incumbent.value
    if incumbent.kind is BoundKind.GREATER_THAN:
        # Only meaningful for a lower-is-better metric, e.g. MAPE > 10000 %.
        return (
            Comparison.BETTER
            if challenger.value <= threshold
            else Comparison.UNDECIDABLE
        )
    return (
        Comparison.BETTER if challenger.value >= threshold else Comparison.UNDECIDABLE
    )


def cell_state(
    task_id: str,
    metric_id: str,
    stage_id: str,
    baseline: Bound,
    entries: tuple[Bound, ...],
) -> CellState:
    """The state a cell renders in.

    Saturation is checked first and structurally: a saturated cell is never
    ranked and never coloured win or loss, whatever anyone submitted.
    """
    if reg.is_saturated(task_id, metric_id, stage_id):
        return CellState.SATURATED
    if not entries:
        return CellState.NO_ENTRY

    verdicts = [compare(task_id, metric_id, e, baseline) for e in entries]
    if Comparison.BETTER in verdicts:
        return CellState.BEATS_BASELINE
    if Comparison.EQUAL in verdicts:
        return CellState.MATCHES_BASELINE
    if all(v is Comparison.UNDECIDABLE for v in verdicts):
        # Every entry sits against a sentinel or an absent baseline. Claiming the
        # baseline leads would assert a comparison that was never made.
        return CellState.NO_ENTRY
    return CellState.BASELINE_LEADS
