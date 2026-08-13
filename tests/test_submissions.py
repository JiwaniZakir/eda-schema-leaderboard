"""Submission validation examines the submission, and says how much it examined.

The bug these tests exist to prevent: the experiments repo ran `eda-validate`
with no argument, which validated *this* repo's registries and reported success
on a submission pull request it had never opened. Every test here is aimed at
some version of "passed without looking".
"""

from __future__ import annotations

import json
import socket
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools.submissions import check_submissions, discover
from tools.validate import main

ROOT = Path(__file__).resolve().parent.parent


def _record(**overrides: Any) -> dict[str, Any]:
    """A schema-valid submission carrying one schema-valid cell."""
    cell = json.loads(
        (ROOT / "tests" / "fixtures" / "cells" / "good.json").read_text(
            encoding="utf-8"
        )
    )
    record: dict[str, Any] = {
        "schema_version": 1,
        "submission_id": "demo-model",
        "model_name": "Demo Model",
        "authors": [{"name": "A Researcher"}],
        "submitted_at": "2026-08-12T00:00:00Z",
        "division": "open",
        "source": "submission",
        "results": [cell],
    }
    record.update(overrides)
    return record


def _write(directory: Path, name: str, payload: Any) -> Path:
    path = directory / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        payload if isinstance(payload, str) else json.dumps(payload),
        encoding="utf-8",
    )
    return path


def test_valid_submission_passes(tmp_path: Path) -> None:
    _write(tmp_path, "sub.json", _record())
    assert check_submissions(tmp_path) == []


def test_invalid_submission_is_rejected(tmp_path: Path) -> None:
    _write(tmp_path, "sub.json", _record(division="sideways"))
    failures = check_submissions(tmp_path)
    assert failures, "an out-of-enum division must be rejected"
    assert any("division" in str(f) for f in failures)


def test_bad_nested_cell_is_rejected(tmp_path: Path) -> None:
    """The cross-schema $ref must actually be followed.

    `results` items are validated by cell.schema.json, reached through a $ref to
    an absolute https $id. If that ref silently resolved to nothing, a garbage
    cell would sail through and this is the only test that would notice.
    """
    _write(tmp_path, "sub.json", _record(results=[{"task": "not_a_real_task"}]))
    failures = check_submissions(tmp_path)
    assert failures, "a malformed cell inside results must be rejected"


def test_resolution_is_offline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Validation must not depend on the public site being reachable.

    A guard that fails open when the network hiccups is not a guard. Sockets are
    blocked outright; if anything tries to fetch the $id URL, this test fails.
    """

    class NoNetwork(socket.socket):
        def connect(self, *args: Any, **kwargs: Any) -> None:
            raise OSError("network access attempted during schema validation")

    monkeypatch.setattr(socket, "socket", NoNetwork)
    _write(tmp_path, "sub.json", _record())
    assert check_submissions(tmp_path) == []


def test_empty_directory_passes_by_default(tmp_path: Path) -> None:
    """A README-only pull request legitimately has nothing to validate."""
    assert check_submissions(tmp_path) == []


def test_empty_directory_fails_when_required(tmp_path: Path) -> None:
    """...but not when the pull request actually changed submissions/.

    This is the vacuity guard. Without it, a submission PR whose files landed
    somewhere the scan does not reach reports a clean pass.
    """
    failures = check_submissions(tmp_path, require_nonempty=True)
    assert len(failures) == 1
    assert "no submission files found" in str(failures[0])


def test_missing_directory_is_a_failure(tmp_path: Path) -> None:
    failures = check_submissions(tmp_path / "nope", require_nonempty=False)
    assert failures and "not a directory" in str(failures[0])


def test_malformed_json_is_a_failure(tmp_path: Path) -> None:
    _write(tmp_path, "sub.json", "{not json")
    failures = check_submissions(tmp_path)
    assert failures and "not valid JSON" in str(failures[0])


def test_discover_is_recursive_and_sorted(tmp_path: Path) -> None:
    _write(tmp_path, "b/second.json", _record())
    _write(tmp_path, "a/first.json", _record())
    _write(tmp_path, "notes.txt", "ignored")
    found = discover(tmp_path)
    assert [p.name for p in found] == ["first.json", "second.json"]


def test_yaml_submissions_are_validated(tmp_path: Path) -> None:
    """The experiments repo documents `submission.yaml`, not `.json`.

    Scanning only one extension is how this guard becomes vacuous a second time:
    a clean pass because it was looking for the wrong filename.
    """
    _write(tmp_path, "submission.yaml", yaml.safe_dump(_record()))
    assert check_submissions(tmp_path) == []

    _write(tmp_path, "bad.yml", yaml.safe_dump(_record(division="sideways")))
    assert any("bad.yml" in str(f) for f in check_submissions(tmp_path))


def test_yaml_python_tags_are_refused(tmp_path: Path) -> None:
    """A `!!python/object:` tag in a submission is a code-execution attempt.

    safe_load raising here is the correct outcome, not an inconvenience. This is
    the opposite call from hparams.yaml, which legitimately carries such tags and
    is never a submission record.
    """
    _write(
        tmp_path,
        "evil.yaml",
        "!!python/object/apply:os.system ['echo pwned']\n",
    )
    failures = check_submissions(tmp_path)
    assert failures, "a python-tagged YAML submission must be rejected"
    assert any("not safe-loadable YAML" in str(f) for f in failures)


def test_nan_is_rejected(tmp_path: Path) -> None:
    """`NaN` is not valid JSON, but json.loads reads it anyway.

    It then survives schema validation, because JSON Schema's `number` accepts
    it, and poisons ranking: NaN compares false against every bound, so the cell
    sorts unpredictably and can be recorded as a win. On a leaderboard other
    groups cite, that is worse than a rejected submission.
    """
    _write(tmp_path, "nan.json", '{"schema_version": 1, "value": NaN}')
    failures = check_submissions(tmp_path)
    assert failures, "a NaN literal must be rejected"
    assert any("not a rankable number" in str(f) for f in failures)


def test_yaml_infinity_is_rejected(tmp_path: Path) -> None:
    """YAML 1.1 reads `.inf`, so the same hole exists on the YAML path."""
    _write(tmp_path, "inf.yaml", "schema_version: 1\nvalue: .inf\n")
    failures = check_submissions(tmp_path)
    assert any("not a rankable number" in str(f) for f in failures)


def test_invalid_utf8_is_reported_not_raised(tmp_path: Path) -> None:
    """One bad byte must not abort every other submission's result.

    UnicodeDecodeError subclasses ValueError, not OSError and not
    JSONDecodeError, so without an explicit handler it escapes both and takes
    down the whole run - on the code path that exists to handle files we did not
    write.
    """
    (tmp_path / "bad.json").write_bytes(b'{"a": "\xff\xfe"}')
    _write(tmp_path, "good.json", _record())

    failures = check_submissions(tmp_path)  # must not raise
    assert any("not valid UTF-8" in str(f) for f in failures)
    # The valid record was still reached and still passed.
    assert not any("good.json" in str(f) for f in failures)


def test_one_bad_file_does_not_hide_the_others(tmp_path: Path) -> None:
    """Report everything wrong in one run, matching tools.validate's contract."""
    _write(tmp_path, "a.json", _record(division="sideways"))
    _write(tmp_path, "b.json", _record(submission_id="X"))
    failures = check_submissions(tmp_path)
    named = {str(f) for f in failures}
    assert any("a.json" in n for n in named)
    assert any("b.json" in n for n in named)


def test_cli_rejects_require_nonempty_without_submissions() -> None:
    """A flag that silently does nothing is how vacuous checks get written."""
    assert main(["--require-nonempty"]) == 2


def test_cli_reports_the_count(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The count is the evidence. 'validate: ok' cannot be told apart from
    'validate: examined nothing', which is the whole bug."""
    _write(tmp_path, "sub.json", _record())
    assert main(["--submissions", str(tmp_path)]) == 0
    assert f"1 submissions from {tmp_path}" in capsys.readouterr().out
