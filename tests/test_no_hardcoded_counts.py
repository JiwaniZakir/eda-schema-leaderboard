"""Phase 1's exit criterion, enforced rather than asserted.

PLAN.md requires the counts 46 / 880 / 232 to be *derived*, with no literals in
the source. A registry that hardcodes 880 cannot tell you when it has drifted
from the data it claims to describe: it will keep reporting 880 long after the
grid stopped having 880 cells.

**`tools/checks/` is deliberately exempt.** Those modules exist precisely to
assert the contract's numbers against the data, which is the same job a test
does. Banning literals there would ban the check from checking anything. The rule
applies to the derivation layer, where a literal would be an answer substituted
for a computation.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# The derivation layer. Anything here must compute, never recall.
DERIVATION_MODULES = ("tools/registry.py", "tools/ranking.py")

# Grid counts. Every one of these is a fact about the data, not about the code.
FORBIDDEN_COUNTS = (920, 880, 856, 240, 232, 120, 46, 40, 24)


def _code_lines(path: Path) -> list[tuple[int, str]]:
    """Source lines with comments and docstrings stripped.

    The counts appear all over the prose in this repo, explaining *why* the
    derivations are shaped as they are. That documentation is the point; only
    executable literals are the problem.
    """
    import ast
    import io
    import tokenize

    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)

    doc_lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef):
            doc = ast.get_docstring(node, clean=False)
            if doc and node.body:
                first = node.body[0]
                if isinstance(first, ast.Expr) and first.end_lineno:
                    doc_lines.update(range(first.lineno, first.end_lineno + 1))

    comment_lines: set[int] = set()
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type == tokenize.COMMENT:
            comment_lines.add(tok.start[0])

    return [
        (i, line)
        for i, line in enumerate(text.splitlines(), start=1)
        if i not in doc_lines and i not in comment_lines
    ]


@pytest.mark.parametrize("rel", DERIVATION_MODULES)
def test_no_grid_count_literals(rel: str) -> None:
    path = ROOT / rel
    assert path.exists(), f"{rel} is missing; update DERIVATION_MODULES"

    offenders: list[str] = []
    for lineno, line in _code_lines(path):
        for count in FORBIDDEN_COUNTS:
            if re.search(rf"(?<![\w.]){count}(?![\w.])", line):
                offenders.append(f"{rel}:{lineno}: literal {count} in {line.strip()!r}")

    assert not offenders, (
        "grid counts must be derived, not written down:\n" + "\n".join(offenders)
    )


def test_the_counts_are_actually_derived() -> None:
    """Guard against the rule being satisfied by deleting the computation.

    A module with no counts and no derivations would pass the test above.
    """
    from tools import registry as reg

    assert len(reg.metric_rows()) == 46
    assert len(reg.live_cells()) == 880
    assert len(reg.live_combos()) == 232
