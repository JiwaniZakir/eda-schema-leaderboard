"""The published baseline: parsing, the join, the emit and the loader.

Expected values and counts live here, in tests. They must never appear in tools/.
"""

from __future__ import annotations

import pytest

from tools import baseline as bl


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
