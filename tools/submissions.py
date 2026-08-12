"""Schema validation for community submissions living in another repository.

The experiments repo checks this repo out to `.site` and runs `eda-validate`
against its own tree. Before this module existed it ran `eda-validate` with no
argument, which validated *this* repo's registries and baseline and then reported
success - a green check on a submission pull request that had never been looked
at. The submission could have contained anything.

So the entry point takes an explicit directory, reports how many files it
actually validated, and can be told to insist that number is non-zero. A guard
that cannot state what it examined is not evidence.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
from referencing import Registry, Resource

from tools.validate import Failure

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schema"
SCHEMA_PATH = SCHEMA_DIR / "submission.schema.json"
CELL_SCHEMA_PATH = SCHEMA_DIR / "cell.schema.json"


def _load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        schema: dict[str, Any] = json.load(handle)
    return schema


def _validator() -> jsonschema.Draft202012Validator:
    """A validator that resolves the cell `$ref` from disk, never over the network.

    `submission.schema.json` references `cell.schema.json` by its public
    `https://jiwanizakir.github.io/...` `$id`, because external tooling consumes
    these schemas by URL. Left to itself, jsonschema would try to *fetch* that
    URL the first time it validates a record whose `results` array is non-empty.

    That failure mode is nasty in exactly the place this code runs. On a
    submission pull request it means the guard depends on the public site being
    up, and a validator that fails open when the network hiccups is not a guard.
    Registering both schemas by `$id` makes resolution local and total.

    Verified: with sockets blocked, an unregistered validator raises
    `Unresolvable` on the first record carrying results. See
    tests/test_submissions.py::test_resolution_is_offline.
    """
    submission = _load(SCHEMA_PATH)
    cell = _load(CELL_SCHEMA_PATH)
    registry = Registry().with_resources(
        [
            (cell["$id"], Resource.from_contents(cell)),
            (submission["$id"], Resource.from_contents(submission)),
        ]
    )
    return jsonschema.Draft202012Validator(submission, registry=registry)


def discover(root: Path) -> list[Path]:
    """Every submission record under `root`, sorted for deterministic output.

    Sorted because the failure list is compared in tests and read by humans, and
    filesystem order is neither stable across platforms nor meaningful.
    """
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*.json") if p.is_file())


def check_submissions(root: Path, *, require_nonempty: bool = False) -> list[Failure]:
    """Validate every submission under `root` against the submission schema.

    `require_nonempty` is set by CI when the pull request actually touched
    `submissions/`. Finding nothing is legitimate on a README-only change and a
    hard error on a submission change, and only the caller knows which it is.
    """
    failures: list[Failure] = []

    if not root.is_dir():
        return [Failure("submissions", f"{root} is not a directory")]

    try:
        validator = _validator()
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        # The schema itself being unreadable must never read as "nothing wrong
        # with the submissions".
        return [Failure("submissions", f"could not load {SCHEMA_PATH.name}: {exc}")]

    found = discover(root)

    if not found and require_nonempty:
        failures.append(
            Failure(
                "submissions",
                f"no submission files found under {root}, but the pull request "
                "changed submissions/ - the guard would have passed without "
                "examining anything",
            )
        )

    for path in found:
        rel = path.relative_to(root)
        try:
            with path.open(encoding="utf-8") as handle:
                record = json.load(handle)
        except json.JSONDecodeError as exc:
            failures.append(Failure("submissions", f"{rel}: not valid JSON: {exc}"))
            continue
        except OSError as exc:
            failures.append(Failure("submissions", f"{rel}: unreadable: {exc}"))
            continue

        # iter_errors, not validate: one run should report every problem in the
        # file rather than the first, matching how tools.validate treats checks.
        for error in sorted(validator.iter_errors(record), key=str):
            location = "/".join(str(part) for part in error.absolute_path) or "(root)"
            failures.append(
                Failure("submissions", f"{rel}: {location}: {error.message}")
            )

    return failures
