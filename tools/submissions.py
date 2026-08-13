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
import math
from pathlib import Path
from typing import Any

import jsonschema
import yaml
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


# The experiments repo documents its submission record as `submission.yaml`,
# while the schema and everything downstream are JSON. Scanning only one of the
# two would put us straight back in the vacuous case this module exists to fix:
# a guard that reports a clean pass because it was looking for the wrong
# extension.
SUFFIXES = (".json", ".yaml", ".yml")


def discover(root: Path) -> list[Path]:
    """Every submission record under `root`, sorted for deterministic output.

    Sorted because the failure list is compared in tests and read by humans, and
    filesystem order is neither stable across platforms nor meaningful.
    """
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix in SUFFIXES)


class NonFiniteNumberError(ValueError):
    """A record carried NaN or an infinity where a rankable number belongs."""


def _reject_non_finite(node: Any, path: str = "(root)") -> None:
    """Refuse NaN and infinities anywhere in a record.

    Both parsers accept them by default and both are wrong for us. `json.loads`
    reads the bare literals `NaN`, `Infinity` and `-Infinity` even though none is
    valid JSON, and YAML 1.1 reads `.nan` and `.inf`. Either produces a float
    that survives schema validation - JSON Schema's `number` accepts it - and
    then poisons everything downstream: NaN compares false against every bound,
    so a cell carrying one sorts unpredictably and can be ranked as a win.

    On a leaderboard other groups cite, a silently unrankable number is worse
    than a rejected submission.
    """
    if isinstance(node, float) and not math.isfinite(node):
        raise NonFiniteNumberError(f"{path} is {node}, which is not a rankable number")
    if isinstance(node, dict):
        for key, value in node.items():
            _reject_non_finite(value, f"{path}/{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            _reject_non_finite(value, f"{path}/{i}")


def _parse(path: Path) -> Any:
    """Read one record. YAML goes through safe_load, never full_load.

    A submission record is written by someone outside the lab. `yaml.safe_load`
    refuses `!!python/object:` tags with a ConstructorError, and that refusal is
    the correct outcome here rather than an inconvenience to work around: tags in
    a submission record are a code-execution attempt, not a formatting choice.

    Note this is the opposite call from `hparams.yaml`, which legitimately
    carries those tags and needs the tag-stripping loader. hparams.yaml is not a
    submission record and never reaches this path.
    """
    text = path.read_text(encoding="utf-8")
    record = json.loads(text) if path.suffix == ".json" else yaml.safe_load(text)
    _reject_non_finite(record)
    return record


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
            record = _parse(path)
        except json.JSONDecodeError as exc:
            failures.append(Failure("submissions", f"{rel}: not valid JSON: {exc}"))
            continue
        except yaml.YAMLError as exc:
            # Includes ConstructorError from a !!python/object: tag, which is the
            # case worth being loud about.
            failures.append(
                Failure("submissions", f"{rel}: not safe-loadable YAML: {exc}")
            )
            continue
        except NonFiniteNumberError as exc:
            failures.append(Failure("submissions", f"{rel}: {exc}"))
            continue
        except UnicodeDecodeError as exc:
            # Caught explicitly because it is neither an OSError nor a
            # JSONDecodeError - it subclasses ValueError - so it would otherwise
            # escape both handlers below and abort the whole run. One submission
            # with a stray byte would take every other submission's result with
            # it, on the code path that exists to handle files we did not write.
            failures.append(Failure("submissions", f"{rel}: not valid UTF-8: {exc}"))
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
