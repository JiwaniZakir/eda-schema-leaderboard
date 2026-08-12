"""Validation entry point: JSON Schema plus guard layers 1 to 5.

Exits non-zero on any failure. This is what `make validate` and CI both call.

Scaffold state: the check registry below is empty, and validate() reports that
honestly rather than printing a green tick it has not earned. Phases 1 through 5
register real checks here.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Failure:
    """One validation failure, addressed to whoever has to fix it."""

    check: str
    detail: str

    def __str__(self) -> str:
        return f"{self.check}: {self.detail}"


# Each check returns the failures it found. An empty list means it passed.
# Registered by phase: schema (1), baselines (2), ingest (3), synth (4), guard (5).
CHECKS: dict[str, Callable[[], list[Failure]]] = {}


def validate() -> list[Failure]:
    """Run every registered check and collect all failures.

    Deliberately does not stop at the first failure. One run should report
    everything that is wrong, not force a fix-and-rerun cycle.
    """
    failures: list[Failure] = []
    for name, check in CHECKS.items():
        try:
            failures.extend(check())
        except Exception as exc:  # a crashing check is itself a failure
            failures.append(Failure(name, f"check raised {type(exc).__name__}: {exc}"))
    return failures


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="eda-validate",
        description="JSON Schema plus guard layers 1 to 5. Exits non-zero on failure.",
    )
    parser.add_argument(
        "--submissions",
        type=Path,
        metavar="DIR",
        help=(
            "Also validate community submission records under DIR against "
            "schema/submission.schema.json. Used by the experiments repo, which "
            "checks this repo out and points at its own tree."
        ),
    )
    parser.add_argument(
        "--require-nonempty",
        action="store_true",
        help=(
            "Fail if --submissions finds no records. CI sets this when the pull "
            "request actually changed submissions/, so that an empty scan is a "
            "failure rather than a silent pass."
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    # Import for the registration side effect. Deferred to avoid a cycle: checks
    # import Failure from this module.
    import tools.checks  # noqa: F401

    if not CHECKS:
        # Never silently succeed. An empty registry means registration broke, and
        # a validator that passes without running anything is worse than none.
        print("validate: no checks registered", file=sys.stderr)
        return 1

    if args.require_nonempty and args.submissions is None:
        print(
            "validate: --require-nonempty is meaningless without --submissions",
            file=sys.stderr,
        )
        return 2

    failures = validate()

    submission_count = 0
    if args.submissions is not None:
        # Imported here rather than at module scope: tools.submissions imports
        # Failure from this module, same cycle as tools.checks above.
        from tools.submissions import check_submissions, discover

        submission_count = len(discover(args.submissions))
        failures.extend(
            check_submissions(args.submissions, require_nonempty=args.require_nonempty)
        )

    for failure in failures:
        print(f"FAIL {failure}", file=sys.stderr)

    summary = f"validate: {len(CHECKS)} checks"
    if args.submissions is not None:
        # Always state the count. "Passed" without it cannot be told apart from
        # "examined nothing", which is the failure this argument exists to fix.
        summary += f", {submission_count} submissions from {args.submissions}"
    summary += f", {len(failures)} failures"
    print(summary)

    return 1 if failures else 0
