"""data/baseline.json must agree with the paper and with the registry.

Two layers, deliberately independent:

  1. the committed file against a fresh build from the CSV, which catches drift
     in the file
  2. the registry's own rules restated over the loaded entries, which catches a
     wrong builder that layer 1 would confirm rather than detect

No count is written as a literal. Every expected set comes from tools.registry.
"""

from __future__ import annotations

from tools import baseline as bl
from tools import registry as reg
from tools.checks import register


@register("baseline")
def check() -> list[str]:
    failures: list[str] = []
    entries = bl.baselines()

    fresh = {entry.key: entry for entry in bl.build()}
    for key in sorted(fresh.keys() - entries.keys()):
        failures.append(f"{key}: built from the CSV but missing from baseline.json")
    for key in sorted(entries.keys() - fresh.keys()):
        failures.append(f"{key}: in baseline.json but not built from the CSV")
    for key in sorted(entries.keys() & fresh.keys()):
        if entries[key] != fresh[key]:
            failures.append(
                f"{key}: committed {entries[key]} does not match the CSV {fresh[key]}"
            )

    expected = set(reg.live_cells())
    for key in sorted(expected - entries.keys()):
        failures.append(f"{key}: live cell missing from baseline.json")
    for key in sorted(entries.keys() - expected):
        failures.append(f"{key}: baseline.json carries a cell that is not live")

    sentinels = bl.published_sentinel_keys()
    for key in sorted(entries):
        entry = entries[key]
        task_id, metric_id, _pdk_id, stage_id = key
        spec = reg.metric(metric_id)

        if entry.source != bl.PAPER:
            failures.append(f"{key}: source is {entry.source!r}, expected {bl.PAPER!r}")

        degenerate = reg.is_degenerate(task_id, metric_id, stage_id)
        if degenerate != (entry.baseline_state == bl.DEGENERATE):
            failures.append(f"{key}: baseline_state disagrees with the registry")

        if degenerate:
            if entry.bound != bl.Bound(bl.BoundKind.ABSENT, None):
                failures.append(f"{key}: a degenerate cell must carry an absent bound")
            continue

        value = entry.bound.value
        if entry.bound.kind is bl.BoundKind.ABSENT or value is None:
            failures.append(f"{key}: a published cell must carry a value")
            continue

        # A sentinel always points AWAY from the good direction, so a submission
        # on the defined side of the threshold is a decidable win. Reading the
        # sentinel set straight off the raw CSV text is a different route than
        # parse_bound takes, so a demotion to an exact value is caught here.
        is_sentinel = entry.bound.kind in (
            bl.BoundKind.GREATER_THAN,
            bl.BoundKind.LESS_THAN,
        )
        if key in sentinels and not is_sentinel:
            failures.append(f"{key}: published as a sentinel, stored as an exact value")
        if is_sentinel and key not in sentinels:
            failures.append(f"{key}: stored as a bound, published as a plain value")
        if entry.bound.kind is bl.BoundKind.GREATER_THAN and spec.direction != "lower":
            failures.append(f"{key}: greater_than bound on a higher-is-better metric")
        if entry.bound.kind is bl.BoundKind.LESS_THAN and spec.direction != "higher":
            failures.append(f"{key}: less_than bound on a lower-is-better metric")

        # A rate genuinely cannot exceed 1, so this assertion is free and catches
        # a percent-stored value outright. Do NOT extend it to the lower-is-better
        # percent metrics: MAPE is unbounded above and a ceiling would reject
        # published cells. See docs/DATA_CONTRACT.md, "How to guard it".
        if spec.percent and spec.direction == "higher" and not 0.0 <= value <= 1.0:
            failures.append(f"{key}: rate {value} is outside the unit interval")

        if reg.is_saturated(task_id, metric_id, stage_id):
            optimum = 1.0 if spec.direction == "higher" else 0.0
            if entry.bound != bl.Bound(bl.BoundKind.EXACT, optimum):
                failures.append(
                    f"{key}: the registry says saturated, the paper published {value}"
                )

    return failures
