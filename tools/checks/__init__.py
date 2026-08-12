"""Validation checks, registered by name.

Checks import THIS module and register into CHECKS. tools/validate.py reads the
same dict. It must be imported as a package, never run as __main__, or the two
end up with different dicts and validation silently passes having run nothing.
"""

from __future__ import annotations

from collections.abc import Callable

CHECKS: dict[str, Callable[[], list[str]]] = {}


def register(name: str) -> Callable[[Callable[[], list[str]]], Callable[[], list[str]]]:
    """Register a check under `name`. The decorated function returns one message
    per failure and an empty list on success."""

    def decorate(fn: Callable[[], list[str]]) -> Callable[[], list[str]]:
        if name in CHECKS:
            raise KeyError(f"a check named {name!r} is already registered")
        CHECKS[name] = fn
        return fn

    return decorate


from tools.checks import baseline as _baseline  # noqa: E402,F401
from tools.checks import registry_csv as _registry_csv  # noqa: E402,F401
