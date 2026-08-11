"""Standing guard against every path that executes untrusted code.

Written in Phase 0, before the code it guards exists, so it can never regress.
Community submissions run on our runner: checkpoints are pickles and the lab's own
`hparams.yaml` carries `!!python/object:` tags. Both are arbitrary-code-execution
vectors if loaded naively, and both have an inviting "just disable the check"
escape hatch that this test exists to keep shut.

See the data gotchas in CLAUDE.md.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIRS = ("tools", "tests")
SOURCE_FILES = ("build.py",)

# NOTE: the pickle and yaml names below appear only as regex *patterns* to search
# for. This module imports none of them and deserializes nothing. It is the guard
# against those calls, not an instance of them.
#
# Each pattern maps to why it is banned and what to use instead.
FORBIDDEN: dict[str, tuple[str, str]] = {
    r"\byaml\.load\s*\((?![^)]*SafeLoader)": (
        "yaml.load without SafeLoader constructs arbitrary Python objects",
        "use the tag-stripping loader in tools/yamlsafe.py",
    ),
    r"\byaml\.full_load\b": (
        "full_load constructs arbitrary Python objects",
        "use the tag-stripping loader in tools/yamlsafe.py",
    ),
    r"\bUnsafeLoader\b": (
        "UnsafeLoader is unpickling by another name",
        "use the tag-stripping loader in tools/yamlsafe.py",
    ),
    r"weights_only\s*=\s*False": (
        "weights_only=False executes whatever the checkpoint author pickled",
        "use the restricted reader in tools/ckpt.py",
    ),
    r"\badd_safe_globals\b|\bsafe_globals\b": (
        "allowlisting globals is a treadmill: every new submitter class needs a "
        "security judgement call",
        "use the restricted reader in tools/ckpt.py, which never executes foreign code",
    ),
    r"\bpickle\.loads?\b": (
        "pickle.load executes arbitrary code by design",
        "use the restricted reader in tools/ckpt.py",
    ),
}


def _python_files() -> list[Path]:
    found = [p for d in SOURCE_DIRS for p in (ROOT / d).rglob("*.py")]
    found += [ROOT / f for f in SOURCE_FILES if (ROOT / f).exists()]
    return found


def test_no_unpickling_paths() -> None:
    """No code path may execute data supplied by a submitter."""
    this_file = Path(__file__).resolve()
    violations: list[str] = []

    for path in _python_files():
        if path.resolve() == this_file:
            continue  # the patterns themselves live here
        text = path.read_text(encoding="utf-8")
        for pattern, (why, instead) in FORBIDDEN.items():
            for match in re.finditer(pattern, text):
                line = text.count("\n", 0, match.start()) + 1
                violations.append(
                    f"{path.relative_to(ROOT)}:{line}: {match.group()!r}\n"
                    f"    {why}\n"
                    f"    instead: {instead}"
                )

    assert not violations, "forbidden unpickling path:\n" + "\n".join(violations)


def test_torch_load_always_pins_weights_only() -> None:
    """If torch.load is ever called, it must pin weights_only=True.

    Necessary but not sufficient on its own, which is why tools/ckpt.py exists.
    Verified against the lab's data: weights_only=True refuses all 360 of their
    checkpoints, so any code reaching for torch.load directly is on the wrong path.
    """
    this_file = Path(__file__).resolve()
    violations: list[str] = []

    for path in _python_files():
        if path.resolve() == this_file:
            continue
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"torch\.load\s*\(", text):
            tail = text[match.start() : match.start() + 400]
            if "weights_only=True" not in tail.replace(" ", ""):
                line = text.count("\n", 0, match.start()) + 1
                violations.append(
                    f"{path.relative_to(ROOT)}:{line}: torch.load without "
                    "weights_only=True"
                )

    assert not violations, "unpinned torch.load:\n" + "\n".join(violations)
