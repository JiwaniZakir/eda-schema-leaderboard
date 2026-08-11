"""Validation checks, registered into tools.validate.CHECKS.

Each check is a pure function returning the failures it found, so `make validate`
can report everything wrong in one run rather than forcing a fix-and-rerun cycle.
"""

from tools.validate import CHECKS

from .baseline_csv import check_baseline_csv

CHECKS["baseline-csv"] = check_baseline_csv

__all__ = ["check_baseline_csv"]
