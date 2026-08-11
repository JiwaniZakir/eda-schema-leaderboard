"""Cross-checks the registries against the recovered Table 8.

The registries say what the grid is; `docs/sources/table8_baseline.csv` says what
the paper published. Drift between them would surface much later as a wrong cell
colour rather than as an error, so this compares them directly.

**Written against the CSV, deliberately not against `tools/registry.py`.** If the
derivation functions and this check were written from the same misreading they
would agree with each other and both be wrong. The CSV is parsed here
independently, and every comparison is on sets rather than totals, because two
errors that cancel would pass a count check.

See docs/DATA_CONTRACT.md.
"""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path

from tools import registry as reg
from tools.validate import Failure

ROOT = Path(__file__).resolve().parent.parent.parent
CSV_PATH = ROOT / "docs" / "sources" / "table8_baseline.csv"

NAME = "registry-consistency"


def _rows() -> list[dict[str, str]]:
    with CSV_PATH.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _decimals(value: str) -> int | None:
    """Decimal places actually published, or None if not a plain number."""
    if "%" in value or value.startswith(("<", ">")) or not value.strip():
        return None
    match = re.search(r"\.(\d+)$", value.replace(",", ""))
    return len(match.group(1)) if match else 0


def _vocab_failures(rows: list[dict[str, str]]) -> list[Failure]:
    """Every table8_label must resolve, in both directions, with no orphans."""
    out: list[Failure] = []
    pairs = [
        ("task", {t.table8_label for t in reg.tasks()}),
        ("metric", {m.table8_label for m in reg.metrics()}),
        ("pdk", {p.table8_label for p in reg.pdks()}),
        ("stage_transition", {s.table8_label for s in reg.stages()}),
    ]
    for column, declared in pairs:
        published = {r[column] for r in rows}
        for missing in sorted(published - declared):
            out.append(
                Failure(
                    NAME,
                    f"{column} {missing!r} appears in Table 8 but no registry entry "
                    f"declares that table8_label",
                )
            )
        for orphan in sorted(declared - published):
            out.append(
                Failure(
                    NAME,
                    f"{column} table8_label {orphan!r} is declared in the registry "
                    f"but never appears in Table 8",
                )
            )
    return out


def check_registry_consistency() -> list[Failure]:
    if not CSV_PATH.exists():
        return [Failure(NAME, f"missing {CSV_PATH}")]

    rows = _rows()
    failures = _vocab_failures(rows)
    if failures:
        # Without a resolvable vocabulary every later comparison is noise.
        return failures

    task_by_label = {t.table8_label: t.id for t in reg.tasks()}
    metric_by_label = {m.table8_label: m.id for m in reg.metrics()}
    pdk_by_label = {p.table8_label: p.id for p in reg.pdks()}
    stage_by_label = {s.table8_label: s.id for s in reg.stages()}

    def key(r: dict[str, str]) -> tuple[str, str, str, str]:
        return (
            task_by_label[r["task"]],
            metric_by_label[r["metric"]],
            pdk_by_label[r["pdk"]],
            stage_by_label[r["stage_transition"]],
        )

    # -- metric rows ------------------------------------------------------
    published_rows = {
        (task_by_label[r["task"]], metric_by_label[r["metric"]]) for r in rows
    }
    declared_rows = set(reg.metric_rows())
    for extra in sorted(declared_rows - published_rows):
        failures.append(
            Failure(NAME, f"registry declares metric row {extra} that Table 8 does not")
        )
    for missing in sorted(published_rows - declared_rows):
        failures.append(
            Failure(
                NAME, f"Table 8 publishes metric row {missing} that no task declares"
            )
        )

    # -- the three exception rules, compared as sets ----------------------
    published: dict[str, set[tuple[str, str, str, str]]] = defaultdict(set)
    for r in rows:
        published[r["kind"]].add(key(r))

    derived_void = {k for k in (key(r) for r in rows) if reg.is_void(k[0], k[3])}
    derived_degen = {
        k for k in (key(r) for r in rows) if reg.is_degenerate(k[0], k[1], k[3])
    }

    for label, derived, expected in (
        ("void", derived_void, published["VOID"]),
        ("degenerate", derived_degen, published["DEGENERATE"]),
    ):
        for extra_cell in sorted(derived - expected):
            failures.append(
                Failure(NAME, f"registry marks {extra_cell} {label}, Table 8 does not")
            )
        for missing_cell in sorted(expected - derived):
            failures.append(
                Failure(
                    NAME, f"Table 8 marks {missing_cell} {label}, registry does not"
                )
            )

    # -- live cells, cell for cell ----------------------------------------
    derived_live = set(reg.live_cells())
    published_live = {k for r in rows if (k := key(r)) not in published["VOID"]}
    for extra_live in sorted(derived_live - published_live):
        failures.append(
            Failure(NAME, f"registry considers {extra_live} live, Table 8 does not")
        )
    for missing_live in sorted(published_live - derived_live):
        failures.append(
            Failure(NAME, f"Table 8 considers {missing_live} live, registry does not")
        )

    # -- saturation must select only global-route, non-wirelength cells ---
    derived_sat = {
        k for k in (key(r) for r in rows) if reg.is_saturated(k[0], k[1], k[3])
    }
    for t, m, p, s in sorted(derived_sat):
        if s != "global_route":
            failures.append(
                Failure(
                    NAME, f"({t}, {m}, {p}, {s}) marked saturated outside global_route"
                )
            )

    # -- display precision against what was actually published ------------
    for r in rows:
        if r["kind"] != "VAL":
            continue
        seen = _decimals(r["value"])
        if seen is None:
            continue
        t, m, _, _ = key(r)
        want = reg.precision(t, m)
        if seen > want:
            failures.append(
                Failure(
                    NAME,
                    f"({t}, {m}) is published to {seen}dp but the registry declares "
                    f"{want}dp, so rendering would silently drop a digit",
                )
            )

    return failures
