"""Static guard against every path that executes data as code.

Community submissions run on our runner. Checkpoints are pickles and the lab's
own `hparams.yaml` carries `!!python/object:` tags, so there is standing pressure
to reach for a loader that just works. This refuses all of them.

**Why AST and not a regex.** The first version matched spellings, and an audit
defeated it 26 ways out of 35 attempts. `yaml.unsafe_load` sailed through while
bare `yaml.load` was caught, even though PyYAML documents the former as the
replacement for the latter. So did `import pickle as p`, `from pickle import
loads`, `joblib.load`, `numpy.load(allow_pickle=True)` and `pandas.read_pickle`.
Matching names cannot see through an alias; resolving the AST can.

**Scope.** This covers first-party code only: `tools/`, `tests/`, `build.py`.
It does NOT cover `submissions/**`, and it cannot. Submitted code is arbitrary by
definition, and Phase 5 layer 4 executes a submitter's `predict.py` deliberately.
The control there is process isolation - network-denied, unprivileged, ephemeral -
not static analysis. Do not read a pass here as saying submissions are safe.
"""

from __future__ import annotations

import ast
from pathlib import Path

from tools.validate import Failure

ROOT = Path(__file__).resolve().parent.parent.parent
SCAN_DIRS = ("tools", "tests")
SCAN_FILES = ("build.py",)

# Fully qualified callables that deserialize by executing. Resolved through
# import aliases, so `import pickle as p; p.loads(x)` is caught as pickle.loads.
BANNED: dict[str, str] = {
    "pickle.load": "executes arbitrary code by design",
    "pickle.loads": "executes arbitrary code by design",
    "pickle.Unpickler": "executes arbitrary code by design",
    "dill.load": "a pickle superset; strictly worse",
    "dill.loads": "a pickle superset; strictly worse",
    "cloudpickle.load": "a pickle superset",
    "cloudpickle.loads": "a pickle superset",
    "marshal.load": "executes arbitrary code",
    "marshal.loads": "executes arbitrary code",
    "shelve.open": "unpickles values transparently",
    "joblib.load": "unpickles; common in ML code and easy to reach for",
    "pandas.read_pickle": "unpickles",
    "yaml.load_all": "constructs arbitrary Python objects",
    "yaml.full_load": "constructs arbitrary Python objects",
    "yaml.full_load_all": "constructs arbitrary Python objects",
    "yaml.unsafe_load": "constructs arbitrary Python objects; PyYAML's own "
    "suggested replacement for the bare load this guard bans",
    "yaml.unsafe_load_all": "constructs arbitrary Python objects",
    "torch.jit.load": "deserializes and can execute",
    "torch.hub.load": "downloads and executes remote code",
    "torch.serialization.load": "the unpinned spelling of torch.load",
    "torch.serialization.add_safe_globals": "allowlisting globals is a treadmill; "
    "each addition is a security judgement call",
    "torch.serialization.safe_globals": "allowlisting globals is a treadmill",
}

REMEDY = {
    "yaml": "use the tag-stripping loader in tools/yamlsafe.py",
    "pickle": "use the restricted reader in tools/ckpt.py",
    "torch": "use the restricted reader in tools/ckpt.py",
}


def _remedy(dotted: str) -> str:
    return REMEDY.get(dotted.split(".", 1)[0], "do not deserialize untrusted data")


class _Scanner(ast.NodeVisitor):
    """Resolves names to fully qualified dotted paths, then judges each call."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.aliases: dict[str, str] = {}
        self.findings: list[tuple[int, str, str]] = []

    # -- import resolution -------------------------------------------------

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.aliases[alias.asname or alias.name.split(".")[0]] = alias.name
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            for alias in node.names:
                local = alias.asname or alias.name
                self.aliases[local] = f"{node.module}.{alias.name}"
        self.generic_visit(node)

    def _dotted(self, node: ast.expr) -> str | None:
        """Fully qualified dotted name for a call target, following aliases."""
        parts: list[str] = []
        cur: ast.expr = node
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if not isinstance(cur, ast.Name):
            return None
        parts.append(cur.id)
        parts.reverse()
        head = self.aliases.get(parts[0], parts[0])
        return ".".join([head, *parts[1:]])

    # -- judgement ---------------------------------------------------------

    def _kwarg(self, call: ast.Call, name: str) -> ast.expr | None:
        for kw in call.keywords:
            if kw.arg == name:
                return kw.value
        return None

    def visit_Call(self, node: ast.Call) -> None:
        dotted = self._dotted(node.func)
        if dotted is not None:
            self._judge(node, dotted)
        self.generic_visit(node)

    def _judge(self, call: ast.Call, dotted: str) -> None:
        line = call.lineno

        if dotted in BANNED:
            self.findings.append((line, dotted, BANNED[dotted]))
            return

        # torch.load: safe only when weights_only is pinned literally True. A
        # keyword check on this exact call cannot be laundered by a neighbouring
        # safe call or a trailing comment, which is how the regex version failed.
        if dotted in {"torch.load"}:
            value = self._kwarg(call, "weights_only")
            if value is None:
                self.findings.append((line, dotted, "called without weights_only=True"))
            elif not (isinstance(value, ast.Constant) and value.value is True):
                self.findings.append(
                    (line, dotted, "weights_only is not the literal True")
                )
            return

        # numpy.load is safe unless pickling is switched on.
        if dotted in {"numpy.load", "np.load"}:
            value = self._kwarg(call, "allow_pickle")
            if isinstance(value, ast.Constant) and value.value is True:
                self.findings.append((line, dotted, "allow_pickle=True unpickles"))
            return

        # yaml.load is safe only with an explicit safe loader.
        if dotted == "yaml.load":
            loader = self._kwarg(call, "Loader")
            name = ast.unparse(loader) if loader is not None else ""
            if "Safe" not in name:
                self.findings.append(
                    (line, dotted, f"Loader={name or 'unset'} constructs objects")
                )
            return

        # Indirection: getattr(torch, "load") and importlib.import_module("pickle")
        # defeat name resolution, so treat a literal string argument naming a
        # banned module as the call itself.
        if dotted in {"getattr", "importlib.import_module", "__import__"}:
            for arg in call.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    target = arg.value
                    root = target.split(".")[0]
                    if root in REMEDY or target in {"load", "loads"}:
                        self.findings.append(
                            (
                                line,
                                dotted,
                                f"dynamic access to {target!r} evades static review",
                            )
                        )


def _files() -> list[Path]:
    found = [p for d in SCAN_DIRS for p in (ROOT / d).rglob("*.py")]
    found += [ROOT / f for f in SCAN_FILES if (ROOT / f).exists()]
    return sorted(found)


def scan(path: Path) -> list[tuple[int, str, str]]:
    """Findings for one file, as (line, dotted name, reason)."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    scanner = _Scanner(path)
    scanner.visit(tree)
    return scanner.findings


def check_no_unpickling() -> list[Failure]:
    name = "no-unpickling"
    this = Path(__file__).resolve()
    failures: list[Failure] = []

    for path in _files():
        if path.resolve() == this:
            continue  # the banned names are listed here as data
        try:
            findings = scan(path)
        except SyntaxError as exc:
            failures.append(Failure(name, f"{path.relative_to(ROOT)}: {exc}"))
            continue
        for line, dotted, why in findings:
            failures.append(
                Failure(
                    name,
                    f"{path.relative_to(ROOT)}:{line}: {dotted} - {why}. "
                    f"Instead: {_remedy(dotted)}",
                )
            )

    return failures
