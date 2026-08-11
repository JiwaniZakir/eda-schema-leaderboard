"""Validation checks, registered into tools.validate.CHECKS.

Each check is a pure function returning the failures it found, so `make validate`
can report everything wrong in one run rather than forcing a fix-and-rerun cycle.
"""

from tools.validate import CHECKS

from .baseline_csv import check_baseline_csv
from .no_unpickling import check_no_unpickling

CHECKS["baseline-csv"] = check_baseline_csv
CHECKS["no-unpickling"] = check_no_unpickling

__all__ = ["check_baseline_csv", "check_no_unpickling"]
