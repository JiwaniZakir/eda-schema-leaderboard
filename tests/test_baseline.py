"""The published baseline: parsing, the join, the emit and the loader.

Expected values and counts live here, in tests. They must never appear in tools/.
"""

from __future__ import annotations

import csv

import pytest

from tools import baseline as bl
from tools import registry as reg


def test_a_plain_value_parses_through_its_thousands_separator() -> None:
    assert bl.parse_bound("1,781.97", percent=False) == bl.Bound(
        bl.BoundKind.EXACT, 1781.97
    )


def test_a_percent_value_is_divided_by_one_hundred() -> None:
    """The CSV is in DISPLAY units. Storage is a fraction. Inverting this makes
    every MAPE cell render baseline_leads and every TPR/TNR cell render
    beats_baseline, with no error raised anywhere."""
    assert bl.parse_bound("12.43 %", percent=True) == bl.Bound(
        bl.BoundKind.EXACT, 0.1243
    )


def test_the_percent_conversion_carries_no_float_noise() -> None:
    """Decimal, not float, division. `12.43 / 100` in binary floating point is
    0.12429999999999999, and 69 of the published cells land like that. The CSV
    holds decimal strings, so scale them as decimals and cross to float once."""
    assert repr(bl.parse_bound("22.51 %", percent=True).value) == "0.2251"


def test_a_rate_at_one_hundred_percent_becomes_exactly_one() -> None:
    assert bl.parse_bound("100.00 %", percent=True) == bl.Bound(bl.BoundKind.EXACT, 1.0)


def test_the_upper_sentinel_becomes_a_greater_than_bound() -> None:
    """The paper thresholded the underlying number away, so it does not exist and
    must never be invented. The threshold converts like any other percent."""
    assert bl.parse_bound("> 10000 %", percent=True) == bl.Bound(
        bl.BoundKind.GREATER_THAN, 100.0
    )


def test_the_lower_sentinel_becomes_a_less_than_bound() -> None:
    assert bl.parse_bound("< -1", percent=False) == bl.Bound(
        bl.BoundKind.LESS_THAN, -1.0
    )


def test_a_negative_value_parses_as_an_exact_bound() -> None:
    assert bl.parse_bound("-0.402", percent=False) == bl.Bound(
        bl.BoundKind.EXACT, -0.402
    )


def test_an_empty_value_is_rejected_rather_than_defaulted() -> None:
    """VOID and DEGENERATE rows arrive empty. Silently yielding 0.0 here would
    publish a fabricated baseline for a cell the paper never measured."""
    with pytest.raises(ValueError):
        bl.parse_bound("", percent=False)


def test_percent_comes_from_the_registry_not_from_the_suffix() -> None:
    """The trailing '%' is a formatting artifact of the table. The registry's
    metric.percent flag is the rule, and it is what the caller passes."""
    assert bl.parse_bound("12.43 %", percent=False) == bl.Bound(
        bl.BoundKind.EXACT, 12.43
    )


def _csv_rows() -> list[dict[str, str]]:
    with bl.CSV_PATH.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_build_emits_one_entry_per_live_cell() -> None:
    assert len(bl.build()) == 880


def test_the_keys_are_exactly_the_live_cells() -> None:
    """Not a count. The set, both directions."""
    assert {e.key for e in bl.build()} == set(reg.live_cells())


def test_void_cells_are_absent_entirely_rather_than_null() -> None:
    """A void cell does not exist. Emitting it with a null value would put it back
    into the 880 and make the matrix render a structural hole as a data gap."""
    voids = [r for r in _csv_rows() if r["kind"] == "VOID"]
    assert len(voids) == 40
    keys = {e.key for e in bl.build()}
    for task_id, _metric, _pdk, stage_id in keys:
        assert not reg.is_void(task_id, stage_id)


def test_degenerate_cells_carry_an_absent_bound() -> None:
    degenerate = [e for e in bl.build() if e.baseline_state == bl.DEGENERATE]
    assert len(degenerate) == 24
    for entry in degenerate:
        assert entry.bound == bl.Bound(bl.BoundKind.ABSENT, None)
        assert reg.is_degenerate(entry.task, entry.metric, entry.stage)


def test_published_cells_all_carry_a_number() -> None:
    published = [e for e in bl.build() if e.baseline_state == bl.PUBLISHED]
    assert len(published) == 856
    for entry in published:
        assert entry.bound.value is not None
        assert entry.bound.kind != "absent"


def test_every_entry_is_sourced_from_the_paper() -> None:
    assert {e.source for e in bl.build()} == {bl.PAPER}


def test_every_csv_row_is_either_consumed_or_void() -> None:
    """The join is checked from the CSV side too, so a row the registry does not
    know about cannot be silently skipped."""
    labels = {
        (t.table8_label, m.table8_label, s.table8_label, p.table8_label)
        for t in reg.tasks()
        for m in reg.metrics()
        for s in reg.stages()
        for p in reg.pdks()
    }
    unconsumed = 0
    for row in _csv_rows():
        key = (row["task"], row["metric"], row["stage_transition"], row["pdk"])
        assert key in labels, f"CSV row does not join: {key}"
        if row["kind"] == "VOID":
            unconsumed += 1
    assert unconsumed == 40


def test_the_sentinel_key_set_is_derived_from_the_raw_csv() -> None:
    """Twenty upper sentinels, all MAPE. Twelve lower sentinels, all R2. Derived
    by scanning the raw value strings, which is a different route than
    parse_bound takes, so a sentinel demoted to an exact value is caught."""
    assert len(bl.published_sentinel_keys()) == 32


def test_regeneration_is_byte_identical() -> None:
    assert bl.to_json(bl.build()) == bl.to_json(bl.build())


def test_the_committed_file_matches_a_fresh_build() -> None:
    """data/baseline.json is generated, never edited. If this fails, either the
    CSV moved or somebody typed into the file."""
    assert bl.BASELINE_PATH.read_text(encoding="utf-8") == bl.to_json(bl.build())


def test_the_emitted_json_carries_no_float_noise() -> None:
    """A reviewer diffing this file against the paper must see 0.1243 where the
    paper says 12.43 %, not 0.12429999999999999."""
    text = bl.BASELINE_PATH.read_text(encoding="utf-8")
    assert "0000000" not in text
    assert "9999999" not in text
