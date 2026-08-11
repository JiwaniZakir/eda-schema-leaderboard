"""Anchors for the unpickling guard.

The guard itself lives in `tools/checks/no_unpickling.py` and runs as part of
`make validate`, so it is enforced by the `validate` CI job as well as by these
tests. That redundancy is deliberate: an audit pointed out that when the guard
lived only in a test file, deleting that file was a fully green, self-mergeable
pull request. Removing a test cannot fail a test run.

Now the check must be removed from two places, one of which is a required CI job,
and this file asserts the registration still exists.
"""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path

import pytest

from tools import validate as validate_mod
from tools.checks import no_unpickling

ROOT = Path(__file__).resolve().parent.parent


def test_guard_is_registered() -> None:
    """The guard must run as part of validate, not only as a test."""
    import tools.checks  # noqa: F401

    assert "no-unpickling" in validate_mod.CHECKS


def test_first_party_code_is_clean() -> None:
    failures = no_unpickling.check_no_unpickling()
    assert failures == [], "\n".join(str(f) for f in failures)


def _scan_source(source: str, tmp_path: Path) -> list[tuple[int, str, str]]:
    path = tmp_path / "sample.py"
    path.write_text(textwrap.dedent(source), encoding="utf-8")
    return no_unpickling.scan(path)


# Every one of these defeated the previous regex implementation.
BYPASSES = [
    pytest.param("import yaml\nyaml.unsafe_load(f)", id="yaml-unsafe_load"),
    pytest.param("import yaml\nyaml.load_all(f)", id="yaml-load_all"),
    pytest.param("import yaml\nyaml.full_load_all(f)", id="yaml-full_load_all"),
    pytest.param("import yaml\nyaml.unsafe_load_all(f)", id="yaml-unsafe_load_all"),
    pytest.param("import pickle as p\np.loads(b)", id="pickle-aliased-module"),
    pytest.param("from pickle import loads\nloads(b)", id="pickle-from-import"),
    pytest.param("import pickle\npickle.Unpickler(f).load()", id="pickle-Unpickler"),
    pytest.param("import joblib\njoblib.load(f)", id="joblib"),
    pytest.param("import dill\ndill.loads(b)", id="dill"),
    pytest.param("import marshal\nmarshal.loads(b)", id="marshal"),
    pytest.param("import shelve\nshelve.open('db')", id="shelve"),
    pytest.param("import pandas\npandas.read_pickle(f)", id="pandas-read_pickle"),
    pytest.param("import numpy\nnumpy.load(f, allow_pickle=True)", id="numpy-pickle"),
    pytest.param("import torch\ntorch.jit.load(f)", id="torch-jit"),
    pytest.param("import torch\ntorch.hub.load('r', 'm')", id="torch-hub"),
    pytest.param("import torch\ntorch.serialization.load(f)", id="torch-serialization"),
    pytest.param("import importlib\nimportlib.import_module('pickle')", id="importlib"),
    pytest.param("import torch\ngetattr(torch, 'load')(f)", id="getattr-indirection"),
    pytest.param(
        "import torch\ntorch.serialization.add_safe_globals([X])", id="safe-globals"
    ),
    # Found by review after the AST rewrite: binding a banned callable to a local
    # name walked straight past import-only alias resolution.
    pytest.param("import pickle\nread = pickle.loads\nread(blob)", id="assign-alias"),
    pytest.param(
        "import pickle as p\nfn = p.load\nfn(f)", id="assign-alias-through-module-alias"
    ),
    # The old substring test for "Safe" allowed any name containing it.
    pytest.param(
        "import yaml\nyaml.load(f, Loader=NotReallySafeLoader)", id="fake-safe-loader"
    ),
    pytest.param(
        "import yaml\nyaml.load(f, Loader=yaml.UnsafeLoader)", id="yaml-Unsafe"
    ),
    pytest.param(
        "import yaml\nyaml.load(f, Loader=yaml.Loader)", id="yaml-plain-Loader"
    ),
    pytest.param("import yaml\nyaml.load(f)", id="yaml-no-loader"),
]


@pytest.mark.parametrize("source", BYPASSES)
def test_known_bypasses_are_caught(source: str, tmp_path: Path) -> None:
    assert _scan_source(source, tmp_path), f"bypass not caught:\n{source}"


def test_adjacent_safe_call_cannot_launder_an_unsafe_one(tmp_path: Path) -> None:
    """The regex scanned a 400-char window, so a nearby safe call rescued a bad one.

    Checking keywords on the specific call node makes that impossible.
    """
    findings = _scan_source(
        """
        import torch
        bad = torch.load(untrusted)
        good = torch.load(trusted, weights_only=True)
        """,
        tmp_path,
    )
    assert len(findings) == 1
    assert findings[0][0] == 3, "must flag the unpinned call on its own line"


def test_trailing_comment_cannot_launder_a_call(tmp_path: Path) -> None:
    findings = _scan_source(
        "import torch\ntorch.load(f)  # weights_only=True once ckpts are fixed\n",
        tmp_path,
    )
    assert findings


def test_non_literal_weights_only_is_rejected(tmp_path: Path) -> None:
    """`weights_only=flag` is not a guarantee; only the literal True is."""
    assert _scan_source("import torch\ntorch.load(f, weights_only=flag)", tmp_path)


@pytest.mark.parametrize(
    "source",
    [
        pytest.param("import yaml\nyaml.safe_load(f)", id="yaml-safe_load"),
        pytest.param(
            "import yaml\nyaml.load(f, Loader=yaml.SafeLoader)", id="yaml-SafeLoader"
        ),
        pytest.param(
            "import torch\ntorch.load(f, weights_only=True)", id="torch-pinned"
        ),
        pytest.param("import numpy\nnumpy.load(f)", id="numpy-default"),
        pytest.param("import json\njson.loads(s)", id="json"),
        # Loader may legitimately be positional; flagging it was a false positive.
        pytest.param(
            "import yaml\nyaml.load(f, yaml.SafeLoader)", id="positional-safe"
        ),
        pytest.param("import yaml\nyaml.load(f, Loader=yaml.CSafeLoader)", id="csafe"),
        # Rebinding must drop a tracked alias rather than poison the name forever.
        pytest.param(
            "import pickle, json\nread = pickle.loads\nread = json.loads\nread(s)",
            id="alias-rebound-to-safe",
        ),
    ],
)
def test_safe_forms_are_allowed(source: str, tmp_path: Path) -> None:
    assert _scan_source(source, tmp_path) == [], f"false positive:\n{source}"


def test_scope_is_documented_as_first_party_only() -> None:
    """Submitted code cannot be covered by static analysis, and must not appear to be.

    Phase 5 layer 4 executes a submitter's predict.py on our runner deliberately.
    The control there is process isolation. If this docstring stops saying so,
    a later phase will inherit a false sense of coverage.
    """
    doc = no_unpickling.__doc__ or ""
    assert "submissions/**" in doc
    assert "isolation" in doc.lower()


def test_guard_module_exists() -> None:
    """Deleting the guard must break something loudly."""
    assert (ROOT / "tools" / "checks" / "no_unpickling.py").exists()
    assert ast.parse(
        (ROOT / "tools" / "checks" / "no_unpickling.py").read_text(encoding="utf-8")
    )
