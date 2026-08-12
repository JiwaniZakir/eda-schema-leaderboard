"""Run every registered check. Exits non-zero on the first failure set."""

from __future__ import annotations

from tools.checks import CHECKS


def main() -> int:
    if not CHECKS:
        print("validate: no checks registered, refusing to report success")
        return 1

    failures = 0
    for name, fn in sorted(CHECKS.items()):
        messages = fn()
        for message in messages:
            print(f"{name}: {message}")
        failures += len(messages)

    print(f"validate: {len(CHECKS)} checks, {failures} failures")
    return 1 if failures else 0
