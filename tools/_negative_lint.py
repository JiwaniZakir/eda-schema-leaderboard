"""Deliberately broken. Part of the Phase 0 negative test; never merged."""

import os  # F401: imported but unused


def broken() -> int:
    return undefined_name  # F821: undefined name
