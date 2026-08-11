"""Invariants over the recovered Table 8 baseline.

Everything downstream keys off this file, and a silent corruption here would
surface much later as a wrong cell colour rather than as an error. The counts are
derived from the data, then compared against the contract, so a drift in either
direction is caught.

See docs/DATA_CONTRACT.md.
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from tools.validate import Failure

CSV_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "docs"
    / "sources"
    / "table8_baseline.csv"
)

# From docs/DATA_CONTRACT.md. VOID subtracts from the live count; DEGENERATE
# does not, because the cell exists and a submission would have its own value.
EXPECTED_TOTAL = 920
EXPECTED_VAL = 856
EXPECTED_VOID = 40
EXPECTED_DEGENERATE = 24
EXPECTED_LIVE = 880

EXPECTED_TASKS = 12
EXPECTED_METRIC_ROWS = 46
EXPECTED_STAGES = 5
EXPECTED_PDKS = ("ASAP7", "IHP130", "NG45", "SKY130")

# Published sentinels: the paper thresholded the underlying value away, so these
# are the value, not a formatting of one. See docs/DATA_CONTRACT.md.
SENTINELS = frozenset({"> 10000 %", "< -1"})


def _is_numeric(value: str) -> bool:
    """True when a cell would be read as a baseline number.

    Tolerates the published formatting: thousands separators and a percent suffix.
    """
    cleaned = value.replace(",", "").replace("%", "").strip()
    try:
        float(cleaned)
    except ValueError:
        return False
    return True


def check_baseline_csv() -> list[Failure]:
    name = "baseline-csv"
    if not CSV_PATH.exists():
        return [Failure(name, f"missing {CSV_PATH}")]

    with CSV_PATH.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    failures: list[Failure] = []

    def expect(label: str, actual: object, wanted: object) -> None:
        if actual != wanted:
            failures.append(
                Failure(name, f"{label}: expected {wanted!r}, got {actual!r}")
            )

    kinds = Counter(r["kind"] for r in rows)
    expect("total cells", len(rows), EXPECTED_TOTAL)
    expect("published (VAL)", kinds["VAL"], EXPECTED_VAL)
    expect("void (VOID)", kinds["VOID"], EXPECTED_VOID)
    expect("degenerate (DEGENERATE)", kinds["DEGENERATE"], EXPECTED_DEGENERATE)

    live = sum(1 for r in rows if r["kind"] != "VOID")
    expect("live cells", live, EXPECTED_LIVE)

    expect("distinct tasks", len({r["task"] for r in rows}), EXPECTED_TASKS)
    expect(
        "distinct stages", len({r["stage_transition"] for r in rows}), EXPECTED_STAGES
    )
    expect(
        "metric rows",
        len({(r["task"], r["metric"]) for r in rows}),
        EXPECTED_METRIC_ROWS,
    )

    pdks = tuple(sorted({r["pdk"] for r in rows}))
    expect("pdks", pdks, EXPECTED_PDKS)

    # The paper's Table 8 header misspells IHP130 as IPH130, five times. If that
    # ever reaches this file, a phantom fifth PDK has entered the pipeline.
    if any(r["pdk"] == "IPH130" for r in rows):
        failures.append(
            Failure(
                name, "found 'IPH130': the Table 8 header typo was not canonicalized"
            )
        )

    # VOID and DEGENERATE cells legitimately carry the paper's footnote text
    # explaining why they are empty, which is worth keeping as provenance. What
    # they must never carry is a *number*, because anything numeric there could be
    # picked up and ranked as if it were a real baseline.
    for i, r in enumerate(rows, start=2):  # +2: header is line 1
        value = r["value"].strip()
        if r["kind"] == "VAL":
            if not value:
                failures.append(Failure(name, f"line {i}: kind=VAL with no value"))
            elif not _is_numeric(value) and value not in SENTINELS:
                failures.append(
                    Failure(
                        name,
                        f"line {i}: kind=VAL value {value!r} is neither a number "
                        f"nor a published sentinel",
                    )
                )
        elif _is_numeric(value):
            failures.append(
                Failure(
                    name,
                    f"line {i}: kind={r['kind']} carries the number {value!r}; "
                    f"an unpopulated cell must never look rankable",
                )
            )

    return failures
