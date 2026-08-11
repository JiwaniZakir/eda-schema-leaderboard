"""Validation entry point: JSON Schema plus guard layers 1 to 5.

Exits non-zero on any failure. This is what `make validate` and CI both call.

Scaffold state: the check registry below is empty, and validate() reports that
honestly rather than printing a green tick it has not earned. Phases 1 through 5
register real checks here.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass


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


def main() -> int:
    # Import for the registration side effect. Deferred to avoid a cycle: checks
    # import Failure from this module.
    import tools.checks  # noqa: F401

    if not CHECKS:
        # Never silently succeed. An empty registry means registration broke, and
        # a validator that passes without running anything is worse than none.
        print("validate: no checks registered", file=sys.stderr)
        return 1

    failures = validate()
    for failure in failures:
        print(f"FAIL {failure}", file=sys.stderr)

    print(f"validate: {len(CHECKS)} checks, {len(failures)} failures")
    return 1 if failures else 0
