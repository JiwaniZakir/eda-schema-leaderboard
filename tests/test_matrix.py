"""The matrix page: context, grid, states, palette, stage strip, budget.

Expected values and counts live here, in tests. They must never appear in
build.py or tools/.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import build
from tools import baseline as bl
from tools import matrix
from tools import registry as reg


def test_the_build_writes_an_index(site: Path) -> None:
    assert (site / "index.html").is_file()


def test_the_stylesheets_are_copied(site: Path) -> None:
    assert (site / "static" / "css" / "base.css").is_file()
    assert (site / "static" / "css" / "theme.css").is_file()


def test_the_theme_source_files_are_not_published(site: Path) -> None:
    """One theme ships, renamed to theme.css. Copying the whole themes directory
    would publish the theme nobody selected and let a page link the wrong one."""
    assert not (site / "static" / "css" / "themes").exists()


def test_an_unknown_theme_fails_the_build_loudly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A typo in THEME must not silently fall back to the default. A site that
    deployed with the wrong brand and exited 0 is worse than one that failed."""
    monkeypatch.setenv("THEME", "not_a_theme")
    with pytest.raises(SystemExit):
        build.selected_theme()


def test_a_plain_value_formats_at_the_registry_precision() -> None:
    """MAE on a design-level task is 2dp; on cell_arc_delay it is 4dp, which is
    the ground truth Phase 6's plausibility layer keys on."""
    assert (
        matrix.format_bound(
            "total_area_prediction", "mae", bl.Bound(bl.BoundKind.EXACT, 1781.97)
        )
        == "1,781.97"
    )
    assert (
        matrix.format_bound(
            "cell_arc_delay_prediction", "mae", bl.Bound(bl.BoundKind.EXACT, 0.0)
        )
        == "0.0000"
    )


def test_a_percent_metric_is_multiplied_by_one_hundred_here_and_only_here() -> None:
    """Storage is a fraction, display is a percent. Table 8 prints 12.43 %, and
    data/baseline.json holds 0.1243. This is the single conversion point in the
    project."""
    assert (
        matrix.format_bound(
            "total_area_prediction", "mape", bl.Bound(bl.BoundKind.EXACT, 0.1243)
        )
        == "12.43 %"
    )


def test_a_rate_at_its_ceiling_renders_as_one_hundred_percent() -> None:
    assert (
        matrix.format_bound(
            "worst_slack_prediction", "tpr", bl.Bound(bl.BoundKind.EXACT, 1.0)
        )
        == "100.00 %"
    )


def test_an_upper_sentinel_renders_its_comparator() -> None:
    """The paper thresholded the number away, so the cell shows a bound. A bare
    10,000.00 % would assert a measurement nobody made."""
    text = matrix.format_bound(
        "net_arc_delay_prediction", "mape", bl.Bound(bl.BoundKind.GREATER_THAN, 100.0)
    )
    assert text.startswith(">")
    assert text == "> 10,000.00 %"


def test_a_lower_sentinel_renders_its_comparator() -> None:
    text = matrix.format_bound(
        "net_arc_delay_prediction", "r2", bl.Bound(bl.BoundKind.LESS_THAN, -1.0)
    )
    assert text == "< -1.000"


def test_a_degenerate_bound_renders_the_marker_and_never_a_number() -> None:
    """0/0 is not 0. Formatting an absent bound as 0.00 would publish a baseline
    the paper explicitly says was never measured."""
    assert (
        matrix.format_bound(
            "worst_slack_prediction", "mpe", bl.Bound(bl.BoundKind.ABSENT, None)
        )
        == matrix.DEGENERATE_MARKER
    )


def test_saturation_comes_from_the_registry_not_from_the_value() -> None:
    """A cell at global route with a 0.00 baseline is saturated because of where
    it sits, not because of what it says. total_wirelength also sits at global
    route and is NOT saturated, and its baseline MAE there is 13,698.67."""
    assert (
        matrix.cell("total_area_prediction", "mae", "ng45", "global_route").state
        == matrix.SATURATED
    )
    live = matrix.cell("total_wirelength_prediction", "mae", "ng45", "global_route")
    assert live.state == matrix.NO_ENTRY
    assert live.display == "13,698.67"


def test_a_saturated_rate_is_still_saturated_at_one_hundred_percent() -> None:
    """16 of the 120 saturated cells are tpr/tnr at their ceiling. An
    is-the-error-near-zero test returns false on every one of them."""
    assert (
        matrix.cell("worst_slack_prediction", "tpr", "ng45", "global_route").state
        == matrix.SATURATED
    )


def test_degeneracy_is_reported_separately_from_state() -> None:
    """State is about submissions; baseline_kind is about the paper. Collapsing
    them loses the difference between 'nobody has entered' and 'there is nothing
    to enter against'."""
    entry = matrix.cell("worst_slack_prediction", "mpe", "ng45", "global_route")
    assert entry.state == matrix.NO_ENTRY
    assert entry.baseline_kind == "degenerate"
    assert entry.display == matrix.DEGENERATE_MARKER


def test_the_three_baseline_kinds_partition_the_live_cells() -> None:
    """856 published, of which 32 are sentinels, plus 24 degenerate."""
    kinds = [matrix.cell(*key).baseline_kind for key in reg.live_cells()]
    assert kinds.count("sentinel") == 32
    assert kinds.count("degenerate") == 24
    assert kinds.count("published") == 824
    assert len(kinds) == 880


def test_a_void_cell_has_no_context_at_all() -> None:
    with pytest.raises(KeyError):
        matrix.cell("total_wirelength_prediction", "mae", "ng45", "floorplan")


CELL_RE = re.compile(r'<td class="state-([a-z_]+)"')


def test_the_grid_holds_one_cell_element_per_live_cell(index_html: str) -> None:
    """Derived from the registry, not from a literal in the template."""
    assert len(CELL_RE.findall(index_html)) == len(reg.live_cells())
    assert len(reg.live_cells()) == 880


def test_every_cell_carries_exactly_one_state_class(index_html: str) -> None:
    """A cell with two state classes renders in whichever colour lost the
    cascade, which is a coin toss that looks deliberate."""
    for found in CELL_RE.findall(index_html):
        assert found in {matrix.NO_ENTRY, matrix.SATURATED}
    assert '<td class="state-' in index_html
    assert re.search(r'<td class="state-\w+ state-', index_html) is None


def test_the_panels_are_the_registry_stages_in_order() -> None:
    assert tuple(p.stage_id for p in matrix.panels()) == tuple(
        s.id for s in reg.stages()
    )
    assert [s.order for s in reg.stages()] == [1, 2, 3, 4, 5]


def test_the_void_rows_are_structurally_absent_not_empty() -> None:
    """Void is a (task, stage) fact, so the two wirelength tasks contribute no
    rows at all at floorplan. An empty <td> would say the measurement is missing;
    an absent row says it does not exist."""
    floorplan = matrix.panels()[0]
    assert floorplan.stage_id == "floorplan"
    tasks_present = {row.task_id for row in floorplan.rows}
    assert "total_wirelength_prediction" not in tasks_present
    assert "interconnect_length_prediction" not in tasks_present
    assert len(tasks_present) == 10


def test_the_per_panel_cell_counts_match_the_partition() -> None:
    """144 + 184 * 4 = 880. Asserting only the total would pass while a void row
    moved from floorplan to another stage."""
    counts = [sum(len(row.cells) for row in p.rows) for p in matrix.panels()]
    assert counts == [144, 184, 184, 184, 184]
    assert sum(counts) == 880


def test_the_saturated_cells_are_all_in_the_last_panel() -> None:
    per_panel = [
        sum(1 for row in p.rows for c in row.cells if c.state == matrix.SATURATED)
        for p in matrix.panels()
    ]
    assert per_panel == [0, 0, 0, 0, 120]


def test_the_task_label_is_carried_once_per_task(index_html: str) -> None:
    """46 rows per panel, 12 task labels. Repeating the label on every row costs
    6 KiB against an 88 KB cap, which this page cannot spare."""
    spans = [row.task_rowspan for row in matrix.panels()[1].rows]
    assert sum(1 for n in spans if n) == 12
    assert sum(spans) == 46
    assert index_html.count('scope="rowgroup"') == 58


def test_no_cell_renders_a_python_repr_or_a_non_number(index_html: str) -> None:
    """The failure this catches is a None that reached a format string and a
    context key the template read but build.py never set."""
    for token in ("None", "nan", "NaN", "undefined", "null", "Undefined"):
        assert token not in index_html
    assert '<td class="state-no_entry"></td>' not in index_html


CSS = Path(__file__).resolve().parent.parent / "static" / "css" / "base.css"
GLYPH_RE = re.compile(r"\.state-([a-z_]+)::before\s*\{[^}]*content:\s*\"([^\"]*)\"")


def test_every_state_has_a_glyph_and_no_two_states_share_one() -> None:
    """Four states distinguishable WITHOUT colour. If two states share a glyph,
    the second channel is decorative and a colourblind reader is back to one."""
    glyphs = dict(GLYPH_RE.findall(CSS.read_text(encoding="utf-8")))
    assert len(glyphs) == 5, glyphs
    assert len(set(glyphs.values())) == 5, glyphs
    assert set(glyphs) == {
        "beats_baseline",
        "matches_baseline",
        "baseline_leads",
        matrix.NO_ENTRY,
        matrix.SATURATED,
    }


def test_the_glyph_colour_comes_from_the_state_key_variable() -> None:
    """The --state-*-key values are the shared palette. A glyph painted with the
    ink colour instead would drift from the legend."""
    css = CSS.read_text(encoding="utf-8")
    for key in ("beats", "matches", "leads", "none", "saturated"):
        assert f"var(--state-{key}-key)" in css


def test_saturated_degenerate_and_sentinel_are_three_distinct_treatments(
    index_html: str,
) -> None:
    """The three cases are easy to conflate into one grey cell, and conflating
    them tells a reader that an unmeasurable baseline and a perfect one are the
    same thing."""
    assert 'data-baseline="degenerate"' in index_html
    assert 'data-baseline="sentinel"' in index_html
    assert index_html.count('data-baseline="degenerate"') == 24
    assert index_html.count('data-baseline="sentinel"') == 32
    css = CSS.read_text(encoding="utf-8")
    assert '[data-baseline="degenerate"]' in css
    assert '[data-baseline="sentinel"]' in css


def test_the_baseline_case_rules_outrank_the_base_cell_border() -> None:
    """A selector that is present but loses the cascade renders nothing.

    `.panel tbody td` sets `border: 1px solid var(--border)` at specificity
    0-1-2, so a bare `td[data-baseline="sentinel"]` rule at 0-1-1 is overridden
    and the sentinel's left marker never appears. Verified in Chrome against the
    built page: computed border-left was `1px rgb(200, 210, 222)`, byte for byte
    what a plain cell gets. Asserting the selector string alone cannot see that,
    so this pins the qualified form.
    """
    css = CSS.read_text(encoding="utf-8")
    for case in (matrix.DEGENERATE, matrix.SENTINEL):
        assert f'.panel tbody td[data-baseline="{case}"]' in css


def test_no_sentinel_cell_prints_a_bare_number(index_html: str) -> None:
    """Every sentinel keeps its comparator all the way to the page."""
    sentinels = re.findall(
        r'<td class="state-\w+" data-baseline="sentinel">([^<]*)<', index_html
    )
    assert len(sentinels) == 32
    assert all(text.startswith((">", "&gt;", "<", "&lt;")) for text in sentinels)


def test_every_degenerate_cell_prints_the_marker(index_html: str) -> None:
    degenerate = re.findall(
        r'<td class="state-\w+" data-baseline="degenerate">([^<]*)<', index_html
    )
    assert len(degenerate) == 24
    assert set(degenerate) == {matrix.DEGENERATE_MARKER}


def test_the_legend_names_every_state_and_both_baseline_cases() -> None:
    ids = [item.id for item in matrix.legend()]
    assert len(ids) == len(set(ids))
    assert matrix.SATURATED in ids
    assert matrix.DEGENERATE in ids
    assert matrix.SENTINEL in ids


PILL_RE = re.compile(
    r'<button class="stage-pill" type="button" data-stage="([a-z_]+)"'
    r' aria-pressed="(true|false)"'
)


def test_the_stage_pills_are_real_buttons_in_registry_order(index_html: str) -> None:
    """A div with a click handler is not a button: it is not focusable, it does
    not fire on Enter or Space, and it announces as nothing."""
    found = PILL_RE.findall(index_html)
    assert [stage for stage, _ in found] == [s.id for s in reg.stages()]


def test_exactly_one_pill_is_pressed(index_html: str) -> None:
    pressed = [stage for stage, state in PILL_RE.findall(index_html) if state == "true"]
    assert pressed == [reg.stages()[0].id]


def test_every_pill_targets_a_panel_that_exists(index_html: str) -> None:
    panels = set(re.findall(r'data-stage-panel="([a-z_]+)"', index_html))
    assert panels == {stage for stage, _ in PILL_RE.findall(index_html)}
    assert len(panels) == 5


def test_no_panel_is_hidden_in_the_markup(index_html: str) -> None:
    """Without JavaScript the page must be complete. Shipping four panels with a
    hidden attribute and unhiding them in a script means a reader with a blocked
    script sees one fifth of the grid and no way to reach the rest."""
    assert "data-stage-panel" in index_html
    assert not re.search(r"<section[^>]*data-stage-panel[^>]*\shidden", index_html)


def test_the_strip_itself_is_hidden_until_the_script_runs(index_html: str) -> None:
    """The inverse rule for a control: a button that does nothing without
    JavaScript should not be offered."""
    assert re.search(r"<div[^>]*data-stage-strip[^>]*\shidden", index_html)


def test_the_script_names_no_registry_vocabulary() -> None:
    """Stage ids reach JavaScript through data attributes only. A stage id
    written into a script is a second copy of the registry that nothing checks."""
    js = Path(__file__).resolve().parent.parent / "static" / "js" / "matrix.js"
    text = js.read_text(encoding="utf-8")
    for stage in reg.stages():
        assert stage.id not in text
    for pdk in reg.pdks():
        assert pdk.id not in text
