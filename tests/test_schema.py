"""The cell schema accepts what it should and rejects what it must.

Each bad fixture asserts the *keyword* that rejects it, not merely that something
did. A fixture that passes for the wrong reason is worse than no fixture: it
reports coverage the schema does not actually have.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from tools import registry as reg

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "schema"
FIXTURES = ROOT / "tests" / "fixtures" / "cells"


def _validator() -> Draft202012Validator:
    schema = json.loads((SCHEMA_DIR / "cell.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _load(name: str) -> dict[str, object]:
    data = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_good_fixture_validates() -> None:
    errors = sorted(_validator().iter_errors(_load("good")), key=str)
    assert not errors, "\n".join(e.message for e in errors)


@pytest.mark.parametrize(
    ("fixture", "keyword", "why"),
    [
        pytest.param(
            "bad_short_task_id",
            "enum",
            "task IDs keep the _prediction suffix; dropping it is the mistake a "
            "submitter reading only the paper will make",
            id="short-task-id",
        ),
        pytest.param(
            "bad_metric_not_in_task",
            "enum",
            "worst_slack publishes no MAPE row; task and metric are each valid "
            "alone, so only the pairing rule catches this",
            id="metric-not-in-task",
        ),
        pytest.param(
            "bad_void_cell",
            "not",
            "wirelength has no floorplan estimate, so a value there is fabricated",
            id="void-cell",
        ),
        pytest.param(
            "bad_missing_source",
            "required",
            "an unsourced record makes synthetic and real data indistinguishable",
            id="missing-source",
        ),
        pytest.param(
            "bad_unknown_source",
            "enum",
            "provenance must be one of the three declared kinds",
            id="unknown-source",
        ),
        pytest.param(
            "bad_value_as_string",
            "type",
            "a quoted number sorts lexically and would rank 9 above 100",
            id="value-as-string",
        ),
        pytest.param(
            "bad_extra_key",
            "additionalProperties",
            "an unknown key is a typo or a smuggling attempt",
            id="extra-key",
        ),
        pytest.param(
            "bad_ranked_on_without_value",
            "type",
            "a cell declaring it ranks on the macro aggregate, with that "
            "aggregate null, cannot produce a ranking at all",
            id="ranked-on-without-value",
        ),
    ],
)
def test_bad_fixtures_are_rejected(fixture: str, keyword: str, why: str) -> None:
    errors = list(_validator().iter_errors(_load(fixture)))
    assert errors, f"{fixture} should have been rejected: {why}"
    keywords = {e.validator for e in errors}
    assert keyword in keywords, (
        f"{fixture} was rejected, but by {sorted(keywords)} rather than {keyword!r}; "
        f"it may be passing for the wrong reason. Expected because: {why}"
    )


def test_schema_enums_match_the_registry() -> None:
    """The schema is generated from the registry, so drift must be impossible.

    External tooling consumes these schemas by URL and cannot run our Python, so
    they are committed as static files rather than built on demand. That makes
    this equality check the thing standing between a registry edit and a stale
    published schema.
    """
    schema = json.loads((SCHEMA_DIR / "cell.schema.json").read_text(encoding="utf-8"))
    props = schema["properties"]
    assert props["task"]["enum"] == [t.id for t in reg.tasks()]
    assert props["metric"]["enum"] == [m.id for m in reg.metrics()]
    assert props["pdk"]["enum"] == [p.id for p in reg.pdks()]
    assert props["stage"]["enum"] == [s.id for s in reg.stages()]


def test_every_task_has_a_metric_membership_rule() -> None:
    schema = json.loads((SCHEMA_DIR / "cell.schema.json").read_text(encoding="utf-8"))
    constrained = {
        rule["if"]["properties"]["task"]["const"]
        for rule in schema["allOf"]
        if "task" in rule.get("if", {}).get("properties", {})
    }
    assert constrained == {t.id for t in reg.tasks()}


def test_submission_schema_is_valid() -> None:
    schema = json.loads(
        (SCHEMA_DIR / "submission.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)
