# Phase 9 - Themes, Deploy and Transfer Implementation Plan

> **For agentic workers:** Implement this plan task-by-task - either dispatch a fresh subagent per task (recommended) or execute inline with review checkpoints. Steps use checkbox (`- [ ]`) syntax for tracking. Tasks 6, 7, 12 and 13 touch live GitHub state, live Zenodo state, or both, and are irreversible; run them inline, with a human watching, never in a background subagent.

**Goal:** ship two themes against one machine-checked CSS-variable contract, prove the deploy pipeline end to end including the cross-repo rebuild trigger, make the leaderboard **citable** with a persistent identifier and a generated citation surface, and hand both repositories to `drexel-ice` with their guardrails demonstrably intact.

**Architecture:** the contract is *derived, never listed*. `tools/cssvars.py` parses `var(--x)` references out of everything that consumes CSS and custom-property declarations out of each theme stylesheet, then diffs the sets. `tools/contrast.py` computes WCAG relative luminance from the same parsed values, so contrast is asserted against the colours that actually ship rather than against a table someone maintained by hand. Both land as checks in the existing `tools/checks/` registry, so `make validate` and the CI `validate` job pick them up with no workflow change. `build.py` selects one theme file by `THEME`, and a Makefile target builds both.

The citation half has the same shape. `CITATION.cff` at the repository root is the **only** place this leaderboard's own citation is written down; `tools/citation.py` validates it against the vendored Citation File Format 1.2.0 schema and formats BibTeX and APA from it, so the `/cite/` page, the card and GitHub's own "Cite this repository" button all render one fact. `tools/fingerprint.py` hashes the published data, records the digest beside the version, and `tools/checks/citation.py` fails the build the moment the data changes without the version changing.

**Tech stack:** Python 3.11+, `uv`, `pytest`, `mypy --strict`, `ruff`, CSS custom properties, pa11y-ci, GitHub Actions, GitHub Pages, `gh`.

## Global constraints

Copied from `PLAN.md`; every task's requirements implicitly include these.

- Python **3.11+**, type hints on all public functions, `ruff` and `mypy` clean.
- **Registries are the only source of vocabulary.** CSS variable names are not registry vocabulary and may be named in `tools/checks/`; task, PDK, stage, metric and circuit names may not.
- **Counts are derived, never literal.** `tests/test_registry.py::test_no_count_literal_appears_in_tools` parses every `tools/**/*.py` with `ast` and rejects any **int** constant in `{46, 232, 880, 856, 120, 24, 40, 920}`. It is an AST walk, not a grep, so comments, docstrings and float literals such as `0.24` are clear of it, and so are digits inside identifiers like `sha256`. What it does catch is a bare `40` or `24` written as a number in `tools/`, which is why nothing below indexes or slices with one.
- Both themes implement **the same variable contract**. A variable added to one and forgotten in the other is a silent failure in the browser: an undefined custom property resolves to nothing, with no console error and no fallback.
- Conventional commits. Branch `phase-9/themes-deploy-transfer`. Never push to `main`.
- **Never use an em dash** in prose, code comments or generated copy.

## Prior state this phase builds on

Verified against the repository and against live GitHub on 2026-08-11.

| Fact | Consequence for this phase |
|---|---|
| Phase 3 created `build.py`, `templates/base.html`, `static/css/base.css` and `static/css/themes/`, switching theme by one line driven by `THEME`. | Task 5 hardens that line rather than inventing it. |
| `tools/checks/__init__.py` holds the `CHECKS` registry and `eda-validate` runs every entry. | New checks register there and are gated by `make check` with no CI edit. |
| `.github/workflows/a11y.yml` already matrixes `theme: [drexel, neutral]` and sets `THEME` for the build. | Task 4 only has to widen the URL list and make a missing page fail loudly. |
| Pages is live at `https://jiwanizakir.github.io/eda-schema-leaderboard/`, `build_type: workflow`, `cname: null`. | There is no custom domain yet. Task 12 decides one or accepts the `drexel-ice.github.io` URL. |
| `main` protection: 7 required contexts (`size`, `analyze (python)`, `lint`, `typecheck`, `validate`, `test`, `build`), `dismiss_stale_reviews: true`, **`required_approving_review_count: 0`**, **`enforce_admins: false`**, `require_code_owner_reviews: false`. | Task 12 raises all three. The context list is re-derived, not retyped, because CodeQL now also emits `analyze (javascript-typescript)` since `static/js/` exists. |
| **No secrets exist on either repository.** `gh secret list` is empty for both. | `claude-review.yml` has skipped on every PR to date, and `SITE_DISPATCH_TOKEN` is unset, so `repository_dispatch` has never once fired. Tasks 6 and 7. |
| `notify-site.yml` in the experiments repo POSTs to a **hardcoded** `repos/JiwaniZakir/eda-schema-leaderboard/dispatches`. | Task 12 must update it. A transferred repository's API redirects, but `curl -X POST` does not follow a redirect by default and the dispatch would silently 301 into nothing. |
| `gh repo transfer` **does not exist** in gh 2.83.2. `PLAN.md` Phase 9 quotes it anyway. | Task 12 uses `gh api -X POST repos/OWNER/REPO/transfer -f new_owner=drexel-ice`. |
| **Nothing in the repository mints, records or renders a citation for the leaderboard itself.** Verified 2026-08-11: `DOI`, `Zenodo`, `CITATION.cff`, `BibTeX` and `ORCID` appear zero times across the repository, the CI workflows and all nine phase plans. `docs/CARD.yaml` has a `citation:` field, but its value cites the **source paper**, not this leaderboard. | `PLAN.md`'s goal is "a static, **citable** benchmark leaderboard". One of that sentence's three clauses had no owner. Tasks 8 to 11 and 13 close it. |
| `docs/CARD.yaml` carries `version: "0.1"`, `pyproject.toml` carries `version = "0.1.0"`, and nothing binds either to content. | Two spellings of one number, both hand-maintained, neither checked. Task 9 makes the version a checkable claim about the data. |

## The palette

Every value below was computed with the WCAG 2.1 relative-luminance formula before it was written down, and each passes the threshold Task 4 asserts. Task 4 recomputes them from the shipped CSS; if a value here is edited, the check is the authority, not this table.

**Shared four-state palette, byte-identical in both themes.** Okabe-Ito hues darkened until each clears 3:1 on its own theme surface.

| State | Key | On drexel bg | On neutral bg |
|---|---|---|---|
| `beats_baseline` | `#007a5e` | 4.64:1 | 4.80:1 |
| `matches_baseline` | `#0072b2` | 4.41:1 | 4.54:1 |
| `baseline_leads` | `#c04a00` | 4.22:1 | 4.35:1 |
| `no_entry` | `#6b6b6b` | 4.83:1 | 4.85:1 |
| `saturated` | `#5b6770` | 4.81:1 | 4.82:1 |

Colour is never the only channel. The glyph channel Phase 3 built carries the same distinction, and Task 4 does not weaken that requirement.

## The citation ordering rule

**Ruled here, and enforced by the phase gate: the transfer comes first, the DOI comes last.**

This phase does two things that collide. It changes the project's address - new owner, new Pages URL, possibly a new custom domain - and it mints a persistent identifier whose entire value is that it never changes. Doing them in the wrong order produces a permanent record of a dead address.

Three facts force the order.

1. **A DOI is minted against a snapshot, and the snapshot is immutable.** Zenodo archives the repository source at the tag and publishes it. Whatever `CITATION.cff`, `README.md` and the rendered `/cite/` page said about where the leaderboard lives is frozen into that record. Correcting it afterwards means either editing a published record's metadata, which does not touch the archived files, or cutting another release to supersede it. A DOI you have to apologise for is a DOI that failed at its one job.
2. **The old Pages URL does not survive the transfer.** `https://jiwanizakir.github.io/eda-schema-leaderboard/` is served because that user owns that repository. After the transfer they do not, and the site answers from `https://drexel-ice.github.io/eda-schema-leaderboard/` or from the custom domain instead. Task 12 Step 8 already says not to assume a redirect. A citation minted before that step names a URL that stops resolving on the day of the transfer.
3. **Zenodo's link is per repository and belongs to whoever authorized it.** The integration is enabled by flipping a switch against `owner/repo` on a Zenodo account that has authorized Zenodo's GitHub app. A transfer moves the repository under an owner whose account has granted no such authorization, and `zenodo/zenodo#1653` is the still-open question of whether an existing record can follow a repository to a new owner. Enabling it before the transfer is work that has to be redone after it, with a live DOI hanging on the outcome.

**So: Tasks 8 to 11 land the citation machinery, which is repository content and publishes nothing. Task 12 transfers and repoints the addresses. Task 13 is the only task that touches Zenodo, and it runs after the site answers 200 at its final URL.**

The machinery is not a promise, it is a trip-wire. `tools/checks/citation.py` derives the expected site URL from `repository-code` plus `static/CNAME` and fails when `url` disagrees, so from the moment the repository moves, `make check` is red until `CITATION.cff` is repointed. The ordering cannot be forgotten, because the build refuses to be green while it is wrong.

**The counter-argument, and the escape hatch.** If the transfer stalls on an org owner who is unavailable, the project sits with no identifier. That is the right trade: no identifier is a gap, and a wrong permanent identifier is damage. If the transfer is *abandoned* rather than delayed, record that verdict in `PLAN.md`'s open decisions table and mint under the current owner - the rule is not "transfer first", it is "settle the address first".

## File structure

| File | Responsibility |
|---|---|
| `tools/cssvars.py` | parse declarations and `var()` references; derive the contract |
| `tools/contrast.py` | sRGB relative luminance and contrast ratio, pure |
| `tools/checks/theme_contract.py` | every theme defines every consumed variable, and the same set as every other theme |
| `tools/checks/theme_contrast.py` | every asserted pair clears its WCAG threshold, in every theme |
| `tools/checks/__init__.py` | register the two new checks |
| `static/css/themes/drexel.css` | navy, gold, serif headings |
| `static/css/themes/neutral.css` | near-white ground, near-black text, one accent, dense table headers |
| `static/css/base.css` | consumes the contract; the only place a variable is *used* |
| `build.py` | `selected_theme()` validates `THEME` and fails loudly on an unknown value |
| `Makefile` | `themes` target: build both, prove they differ |
| `.pa11yci.json` | the a11y URL set |
| `.github/workflows/a11y.yml` | discover a cell page, fail if none |
| `.github/CODEOWNERS` | real handles at transfer |
| `.github/workflows/claude-review.yml` | configured or deleted, per Task 7 |
| `static/CNAME` | only if a custom domain is agreed |
| `tests/test_themes.py` | contract, shared palette, mutation |
| `tests/test_contrast.py` | the maths, then every shipped pair |
| `tests/test_build_theme.py` | `THEME` selection and its failure mode |
| `CITATION.cff` | **the** citation: version, authors, licence, DOI, fingerprint, and the paper as a reference |
| `schema/citation-cff-1.2.0.json` | the vendored CFF 1.2.0 schema, so validation needs no network |
| `tools/citation.py` | load, validate, and format BibTeX and APA for every reference in it |
| `tools/fingerprint.py` | SHA-256 over the published data; `eda-fingerprint --write` records it |
| `tools/releases.py` | parse the version-to-DOI ledger in `docs/RELEASES.md` |
| `tools/release_check.py` | the tag gate: tag, version, fingerprint and ledger must agree |
| `tools/checks/citation.py` | one check: schema, fingerprint, the two versions, the home URL, the ledger |
| `templates/partials/citation-block.html` | the one citation block, rendered on `/cite/` and on the card |
| `templates/pages/cite.html` | `/cite/` |
| `templates/base.html` | the version and fingerprint stamp in the footer, and the `/cite/` nav entry |
| `docs/RELEASES.md` | what a tagged release contains, why it is immutable, and the ledger |
| `docs/CARD.yaml` | modified: stops declaring its own `version` and `citation` |
| `tools/card.py` | modified: those two keys leave `REQUIRED_TOP_LEVEL` |
| `.github/workflows/release.yml` | on a tag: verify, build, attach the site archive. No secret is added |
| `tests/test_citation.py` | CFF validity, the formatters, and the single-source rule |
| `tests/test_fingerprint.py` | determinism, and the data-changed-without-a-version-bump mutation |
| `tests/test_cite_page.py` | the page, the card block, and that the two agree byte for byte |
| `tests/test_release.py` | ledger parsing, the tag gate, and the bootstrap-once rule |

---

### Task 1: Derive the theme contract and fail on a gap

The whole value of this phase's test suite is here. A theme contract written as a list in a test is a second thing to maintain and it drifts; a contract derived from what the site actually reads cannot.

**Files:**
- Create: `tools/cssvars.py`
- Create: `tools/checks/theme_contract.py`
- Modify: `tools/checks/__init__.py`
- Test: `tests/test_themes.py`

**Interfaces:**
- Consumes: the filesystem only. No registry, no build.
- Produces:
  - `cssvars.strip_comments(css: str) -> str`
  - `cssvars.declared(css: str) -> frozenset[str]`
  - `cssvars.referenced(text: str) -> frozenset[str]`
  - `cssvars.values(css: str) -> dict[str, str]`
  - `cssvars.resolve(name: str, table: dict[str, str]) -> str`
  - `cssvars.theme_files() -> tuple[Path, ...]`
  - `cssvars.theme_variables() -> dict[str, frozenset[str]]` keyed by theme stem
  - `cssvars.contract() -> frozenset[str]`
  - `theme_contract.check() -> list[str]`, empty on success

- [ ] **Step 1: Write the failing test**

Create `tests/test_themes.py`:

```python
"""The theme contract.

The contract is DERIVED from what the site reads, never listed here. A list in a
test is a second source of truth and it drifts. What is asserted here is the
relationship: every variable the site reads is defined by every theme, and the
themes define the same set as each other.
"""

from __future__ import annotations

import re
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest

from tools import cssvars
from tools.checks import theme_contract


def test_at_least_two_themes_exist() -> None:
    assert len(cssvars.theme_files()) >= 2


def test_the_contract_is_not_empty() -> None:
    """An empty contract would make every other assertion here vacuously true.
    This is the same guard as the empty-CHECKS guard in tools/validate.py, and
    for the same reason: a check that silently checks nothing is worse than no
    check."""
    assert cssvars.contract(), "no var() references found outside the themes"


def test_every_theme_defines_every_contract_variable() -> None:
    required = cssvars.contract()
    for name, declared in cssvars.theme_variables().items():
        assert required <= declared, f"{name} is missing {sorted(required - declared)}"


def test_the_themes_define_identical_variable_sets() -> None:
    """A variable added to one theme and forgotten in the other renders as
    nothing at all: an undefined custom property produces no error, no fallback
    and no console warning."""
    sets = cssvars.theme_variables()
    names = sorted(sets)
    first = names[0]
    for other in names[1:]:
        assert sets[first] == sets[other], (
            f"{first} and {other} differ on {sorted(sets[first] ^ sets[other])}"
        )


def test_no_theme_defines_a_variable_nobody_reads() -> None:
    """Dead variables rot. A private brand primitive is exempt because it is
    referenced by the theme's own declarations."""
    required = cssvars.contract()
    internal = cssvars.theme_internal_references()
    for name, declared in cssvars.theme_variables().items():
        dead = declared - required - internal
        assert not dead, f"{name} defines unused {sorted(dead)}"


def test_the_check_passes_on_current_data() -> None:
    assert theme_contract.check() == []


def test_comments_do_not_count_as_declarations() -> None:
    css = ":root { /* --commented-out: red; */ --live: blue; }"
    assert cssvars.declared(css) == frozenset({"--live"})


def test_a_declaration_after_a_brace_is_found() -> None:
    """Formatted CSS puts one declaration per line, but a single-line rule is
    legal and a ^-anchored regex misses it, which reports a false gap."""
    assert cssvars.declared(":root { --a: 1; --b: 2; }") == frozenset({"--a", "--b"})


def test_a_var_reference_is_not_a_declaration() -> None:
    assert cssvars.declared("a { color: var(--text); }") == frozenset()
    assert cssvars.referenced("a { color: var(--text, #000); }") == frozenset(
        {"--text"}
    )


def test_resolve_follows_indirection() -> None:
    table = cssvars.values(":root { --brand: #07294d; --accent: var(--brand); }")
    assert cssvars.resolve("--accent", table) == "#07294d"


@pytest.fixture
def mutable_themes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    dest = tmp_path / "themes"
    shutil.copytree(cssvars.THEME_DIR, dest)
    monkeypatch.setattr(cssvars, "THEME_DIR", dest)
    cssvars.theme_files.cache_clear()
    cssvars.contract.cache_clear()
    yield dest
    cssvars.theme_files.cache_clear()
    cssvars.contract.cache_clear()


def test_dropping_a_variable_from_one_theme_is_caught(mutable_themes: Path) -> None:
    """The mutation this phase exists to catch. Pick the variable
    deterministically rather than naming one, so the test keeps working when the
    contract changes."""
    victim = sorted(cssvars.contract())[0]
    target = sorted(mutable_themes.glob("*.css"))[0]
    text = target.read_text(encoding="utf-8")
    stripped = re.sub(rf"(?m)^\s*{re.escape(victim)}\s*:[^;]*;\s*$\n?", "", text)
    assert stripped != text, f"{victim} was not declared on its own line in {target}"
    target.write_text(stripped, encoding="utf-8")

    failures = theme_contract.check()
    assert any(victim in f for f in failures), failures
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `uv run pytest tests/test_themes.py -v`
Expected: FAIL at collection, `ModuleNotFoundError: No module named 'tools.cssvars'`

- [ ] **Step 3: Write the parser**

Create `tools/cssvars.py`:

```python
"""Parse CSS custom properties out of stylesheets.

The theme contract is DERIVED, never listed. Every var(--x) referenced outside
static/css/themes/ must be declared by every theme file, and the themes must
declare the same set as one another.

The failure this prevents is silent: an undefined custom property resolves to
nothing. No error, no fallback, no console warning. A cell simply loses its
colour on one theme and nobody notices until a reader does.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
THEME_DIR = ROOT / "static" / "css" / "themes"

# Sources that CONSUME variables. The themes are deliberately excluded: they are
# the definition side, and including them would let a theme satisfy the contract
# by referencing its own variables.
CONSUMER_GLOBS = ("static/css/*.css", "static/js/*.js", "templates/**/*.html")

_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_DECL = re.compile(r"(?:^|[;{])\s*(--[A-Za-z0-9_-]+)\s*:", re.MULTILINE)
_VALUE = re.compile(r"(?:^|[;{])\s*(--[A-Za-z0-9_-]+)\s*:\s*([^;{}]+)", re.MULTILINE)
_REF = re.compile(r"var\(\s*(--[A-Za-z0-9_-]+)")

_MAX_INDIRECTION = 8


def strip_comments(css: str) -> str:
    """Drop /* ... */ so a commented-out declaration does not count as one."""
    return _COMMENT.sub(" ", css)


def declared(css: str) -> frozenset[str]:
    """Custom properties this stylesheet DEFINES."""
    return frozenset(_DECL.findall(strip_comments(css)))


def referenced(text: str) -> frozenset[str]:
    """Custom properties this file READS through var()."""
    return frozenset(_REF.findall(strip_comments(text)))


def values(css: str) -> dict[str, str]:
    """Declared name to raw value, lowercased and trimmed.

    Lowercasing is what makes cross-theme equality of the shared palette a
    string comparison rather than a colour comparison. #007A5E and #007a5e are
    the same colour and must not read as a palette divergence.
    """
    return {
        name: value.strip().lower()
        for name, value in _VALUE.findall(strip_comments(css))
    }


def resolve(name: str, table: dict[str, str]) -> str:
    """Follow `var(--other)` indirection to a literal value.

    A theme is expected to define brand primitives and point the contract at
    them. Without this, every check below would see the string "var(--navy)" and
    have nothing to measure.
    """
    seen = 0
    value = table[name]
    while value.startswith("var("):
        if seen >= _MAX_INDIRECTION:
            raise ValueError(f"{name} indirects more than {_MAX_INDIRECTION} times")
        match = _REF.match(value)
        if match is None:
            raise ValueError(f"{name} has a malformed var() value: {value!r}")
        value = table[match.group(1)]
        seen += 1
    return value


@cache
def theme_files() -> tuple[Path, ...]:
    files = tuple(sorted(THEME_DIR.glob("*.css")))
    if len(files) < 2:
        raise FileNotFoundError(f"{THEME_DIR} must hold at least two stylesheets")
    return files


@cache
def theme_variables() -> dict[str, frozenset[str]]:
    return {p.stem: declared(p.read_text(encoding="utf-8")) for p in theme_files()}


@cache
def theme_internal_references() -> frozenset[str]:
    """Variables a theme reads from within its own file, which is how a brand
    primitive stays legitimate without being part of the contract."""
    used: set[str] = set()
    for path in theme_files():
        used |= referenced(path.read_text(encoding="utf-8"))
    return frozenset(used)


@cache
def contract() -> frozenset[str]:
    """Every variable the site reads. This IS the contract."""
    used: set[str] = set()
    for pattern in CONSUMER_GLOBS:
        for path in ROOT.glob(pattern):
            if THEME_DIR in path.parents:
                continue
            used |= referenced(path.read_text(encoding="utf-8"))
    return frozenset(used)
```

`_DECL` and `_VALUE` both anchor on `^` or `;` or `{`, which is what makes a single-line rule parse and what stops `var(--x)` being mistaken for a declaration: a reference is always preceded by `(`.

- [ ] **Step 4: Write the check**

Create `tools/checks/theme_contract.py`:

```python
"""Every theme defines every variable the site reads, and the same set as every
other theme."""

from __future__ import annotations

from tools import cssvars
from tools.checks import register


@register("theme_contract")
def check() -> list[str]:
    failures: list[str] = []

    required = cssvars.contract()
    if not required:
        return [
            "no var() references found outside the themes; the contract cannot be empty"
        ]

    per_theme = cssvars.theme_variables()
    internal = cssvars.theme_internal_references()

    for name in sorted(per_theme):
        declared = per_theme[name]
        for missing in sorted(required - declared):
            failures.append(
                f"{name}.css does not define {missing}, which the site reads"
            )
        for dead in sorted(declared - required - internal):
            failures.append(f"{name}.css defines {dead}, which nothing reads")

    names = sorted(per_theme)
    first = names[0]
    for other in names[1:]:
        for var in sorted(per_theme[first] ^ per_theme[other]):
            owner = first if var in per_theme[first] else other
            failures.append(
                f"{var} is defined only by {owner}.css; every theme defines the same set"
            )

    return failures
```

Append the import to `tools/checks/__init__.py`, beside the existing one:

```python
from tools.checks import theme_contract as _theme_contract  # noqa: E402,F401
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_themes.py -v`
Expected: every test passes **except** those that depend on the two themes being complete, which Tasks 2 and 3 finish. If `test_every_theme_defines_every_contract_variable` fails here, read its message: it is the to-do list for the next two tasks. Record that list before moving on.

- [ ] **Step 6: Commit**

```bash
git add tools/cssvars.py tools/checks/theme_contract.py tools/checks/__init__.py tests/test_themes.py
git commit -m "test(themes): derive the CSS variable contract and diff it per theme"
```

---

### Task 2: The drexel theme

Navy `#07294D`, gold `#FFC600`, serif headings. Light ground, because 880 cells of dense numeric table on a navy field is a readability problem the brand colour does not justify. The navy carries the chrome: header band, table header, pill ink, focus ring. The gold carries exactly one job, the active stage pill, where navy-on-gold measures 9.30:1.

**Files:**
- Modify: `static/css/themes/drexel.css`
- Modify: `static/css/base.css` (only if a contract variable has no consumer yet)

**Interfaces:**
- Consumes: nothing at runtime. Checked by `tools/checks/theme_contract.py`.
- Produces: a `:root` block defining every variable in `cssvars.contract()`.

- [ ] **Step 1: Run the contract check to get the gap list**

Run: `uv run eda-validate`
Expected: `theme_contract:` lines naming every variable drexel is missing. That list is this step's specification.

- [ ] **Step 2: Write the theme**

Write `static/css/themes/drexel.css`. Every value below is measured; the ratio in each comment is what Task 4 recomputes.

```css
/*
 * Drexel. Navy #07294D, gold #FFC600, serif headings.
 *
 * Light ground on purpose. The matrix is 880 numeric cells and the brand navy
 * is chrome, not canvas: header band, table header, pill ink, focus ring. The
 * gold has exactly one job, the active stage pill, where navy on gold is
 * 9.30:1.
 *
 * The --state-*-key values are the shared four-state palette and are byte
 * identical to every other theme. Change one here and tests/test_themes.py
 * fails on the next theme, which is the point.
 */

:root {
  /* Brand primitives. Private to this file: referenced only by the contract
     variables below, never by base.css. */
  --drexel-navy: #07294d;
  --drexel-gold: #ffc600;

  --font-body: ui-sans-serif, system-ui, "Helvetica Neue", Arial, sans-serif;
  --font-heading: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
  --font-mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, monospace;

  --ground: #ffffff;
  --surface: #f5f7fa;
  --surface-raised: #ffffff;
  --border: #c8d2de;          /* hairline, decorative */
  --border-strong: #78859a;   /* 3.48:1 on --surface, carries meaning */

  --text: #0b1f33;            /* 16.69:1 on --ground */
  --text-muted: #4a5a6b;      /* 6.60:1 on --surface */
  --link: #0a4c8c;            /* 8.66:1 on --ground */
  --link-visited: #5b3a8c;    /* 8.65:1 on --ground */

  --accent: var(--drexel-navy);
  --accent-ink: #ffffff;      /* 14.65:1 on --accent */
  --focus: var(--drexel-navy);/* 14.65:1 on --ground */

  --pill-bg: #e7ebf0;
  --pill-ink: var(--drexel-navy);         /* 12.24:1 on --pill-bg */
  --pill-active-bg: var(--drexel-gold);
  --pill-active-ink: var(--drexel-navy);  /* 9.30:1 on --pill-active-bg */

  --table-header-bg: var(--drexel-navy);
  --table-header-ink: #ffffff;            /* 14.65:1 */
  --table-header-pad: 0.55rem 0.7rem;
  --table-row-alt: #f0f3f7;
  --table-cell-pad: 0.45rem 0.6rem;

  --void-ink: #7f8d9e;        /* 3.38:1 on --ground, hatch for absent cells */

  /* Shared four-state data palette. Okabe-Ito hues darkened until each clears
     3:1 on its own surface. IDENTICAL in every theme. */
  --state-beats-key: #007a5e;
  --state-matches-key: #0072b2;
  --state-leads-key: #c04a00;
  --state-none-key: #6b6b6b;
  --state-saturated-key: #5b6770;

  --state-beats-bg: #e3f3ec;
  --state-beats-ink: #10513c;      /* 8.08:1 ink, 4.64:1 key */
  --state-matches-bg: #e4eef7;
  --state-matches-ink: #0b4a75;    /* 7.94:1 ink, 4.41:1 key */
  --state-leads-bg: #fbe9de;
  --state-leads-ink: #8a3b00;      /* 6.58:1 ink, 4.22:1 key */
  --state-none-bg: #f2f4f6;
  --state-none-ink: #40505f;       /* 7.53:1 ink, 4.83:1 key */
  --state-saturated-bg: #e8eaed;
  --state-saturated-ink: #3f4a55;  /* 7.50:1 ink, 4.81:1 key */
}
```

- [ ] **Step 3: Wire any orphan into base.css**

If Step 4 reports `defines --x, which nothing reads`, either delete the variable or give it a consumer in `static/css/base.css`. Do not add it to a theme "for later": an unread variable is how the two themes drift apart in the first place. Serif headings need one rule, in `base.css`, not in the theme:

```css
h1, h2, h3 {
  font-family: var(--font-heading);
}
```

- [ ] **Step 4: Run the checks**

Run: `uv run eda-validate && uv run pytest tests/test_themes.py -v`
Expected: `theme_contract` reports only `neutral.css` gaps, which Task 3 closes. No drexel line remains.

- [ ] **Step 5: Commit**

```bash
git add static/css/themes/drexel.css static/css/base.css
git commit -m "feat(themes): complete the drexel theme against the variable contract"
```

---

### Task 3: The neutral theme

Near-white ground, near-black text, one accent, dense table headers. The same shared data palette, and no second accent: where drexel spends gold on the active stage pill, neutral reuses its single accent.

**Files:**
- Modify: `static/css/themes/neutral.css`
- Test: `tests/test_themes.py`

**Interfaces:**
- Consumes: nothing at runtime.
- Produces: the same variable set as `drexel.css`, with the five `--state-*-key` values byte-identical.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_themes.py`:

```python
def test_every_theme_ships_the_same_data_palette() -> None:
    """`Both share the colourblind-safe four-state data palette` is a
    requirement, so it is asserted rather than described. The keys are compared
    after resolution, so a theme may point at a brand primitive, and lowercased,
    so #007A5E and #007a5e do not read as a divergence."""
    resolved: dict[str, dict[str, str]] = {}
    for path in cssvars.theme_files():
        table = cssvars.values(path.read_text(encoding="utf-8"))
        resolved[path.stem] = {
            name: cssvars.resolve(name, table)
            for name in sorted(table)
            if name.endswith("-key")
        }

    names = sorted(resolved)
    assert resolved[names[0]], "no --state-*-key variables found"
    for other in names[1:]:
        assert resolved[names[0]] == resolved[other], (
            f"{names[0]} and {other} disagree on the shared palette"
        )
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_themes.py::test_every_theme_ships_the_same_data_palette -v`
Expected: FAIL, either `no --state-*-key variables found` or a dict inequality naming the diverging key, depending on what Phase 3 left in `neutral.css`.

- [ ] **Step 3: Write the theme**

Write `static/css/themes/neutral.css`:

```css
/*
 * Neutral. Near-white ground, near-black text, one accent, dense table headers.
 *
 * The restraint is the design: this is the theme for a reader who came to look
 * at 880 numbers, so nothing competes with them. One accent (#005ea2) does
 * links, focus, and the active stage pill. Table headers are tighter than
 * drexel's, because a dense header keeps more of the grid above the fold.
 *
 * The --state-*-key values are byte identical to drexel.css. That equality is
 * asserted, not trusted.
 */

:root {
  --font-body: ui-sans-serif, system-ui, "Helvetica Neue", Arial, sans-serif;
  --font-heading: ui-sans-serif, system-ui, "Helvetica Neue", Arial, sans-serif;
  --font-mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, monospace;

  --ground: #ffffff;
  --surface: #fafafa;
  --surface-raised: #ffffff;
  --border: #d4d4d4;
  --border-strong: #8a8a8a;   /* 3.31:1 on --surface */

  --text: #171717;            /* 17.93:1 on --ground */
  --text-muted: #525252;      /* 7.49:1 on --surface */
  --link: #005ea2;            /* 6.72:1 on --ground */
  --link-visited: #6b2fa0;    /* 8.27:1 on --ground */

  --accent: #005ea2;
  --accent-ink: #ffffff;      /* 6.72:1 on --accent */
  --focus: #005ea2;           /* 6.72:1 on --ground */

  --pill-bg: #efefef;
  --pill-ink: #171717;               /* 15.59:1 on --pill-bg */
  --pill-active-bg: #005ea2;         /* the one accent, reused */
  --pill-active-ink: #ffffff;        /* 6.72:1 */

  --table-header-bg: #efefef;
  --table-header-ink: #171717;       /* 15.59:1 */
  --table-header-pad: 0.25rem 0.5rem;/* dense, deliberately tighter than drexel */
  --table-row-alt: #f5f5f5;
  --table-cell-pad: 0.3rem 0.5rem;

  --void-ink: #8e8e8e;        /* 3.28:1 on --ground */

  /* Shared four-state data palette. IDENTICAL to drexel.css. */
  --state-beats-key: #007a5e;
  --state-matches-key: #0072b2;
  --state-leads-key: #c04a00;
  --state-none-key: #6b6b6b;
  --state-saturated-key: #5b6770;

  --state-beats-bg: #eaf6f1;
  --state-beats-ink: #0f5140;      /* 8.34:1 ink, 4.80:1 key */
  --state-matches-bg: #e8f1f8;
  --state-matches-ink: #0b4a75;    /* 8.16:1 ink, 4.54:1 key */
  --state-leads-bg: #fcede3;
  --state-leads-ink: #8a3b00;      /* 6.79:1 ink, 4.35:1 key */
  --state-none-bg: #f4f4f4;
  --state-none-ink: #4a4a4a;       /* 8.06:1 ink, 4.85:1 key */
  --state-saturated-bg: #eaeaea;
  --state-saturated-ink: #454545;  /* 7.97:1 ink, 4.82:1 key */
}
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_themes.py -v && uv run eda-validate`
Expected: all theme tests pass; `theme_contract` contributes 0 failures.

- [ ] **Step 5: Commit**

```bash
git add static/css/themes/neutral.css tests/test_themes.py
git commit -m "feat(themes): complete the neutral theme and pin the shared palette"
```

---

### Task 4: Contrast, computed from the shipped CSS

The gate says contrast at least 4.5:1 for every cell state in both themes. A reviewer eyeballing a screenshot cannot assert that, and a hand-maintained table of ratios goes stale the first time a hex changes. This computes it from the files that ship.

pa11y checks rendered pages and will catch a contrast failure on text it can see, but it cannot see a state that no cell currently renders. With no submissions yet, `beats_baseline` and `baseline_leads` appear nowhere on the live matrix, so pa11y alone would pass while two of the four states were unreadable.

**Files:**
- Create: `tools/contrast.py`
- Create: `tools/checks/theme_contrast.py`
- Modify: `tools/checks/__init__.py`
- Modify: `.pa11yci.json`, `.github/workflows/a11y.yml`
- Test: `tests/test_contrast.py`

**Interfaces:**
- Consumes: `cssvars.theme_files`, `cssvars.values`, `cssvars.resolve`.
- Produces:
  - `contrast.relative_luminance(colour: str) -> float`
  - `contrast.ratio(a: str, b: str) -> float`
  - `theme_contrast.check() -> list[str]`

- [ ] **Step 1: Write the failing test**

Create `tests/test_contrast.py`:

```python
"""WCAG contrast, computed from the CSS that actually ships.

pa11y checks rendered pages, which is necessary and not sufficient: with no
submissions yet, no cell on the live matrix renders beats_baseline or
baseline_leads, so pa11y cannot see two of the four states at all.
"""

from __future__ import annotations

import pytest

from tools import contrast, cssvars
from tools.checks import theme_contrast


def test_known_ratios_from_the_wcag_definition() -> None:
    assert contrast.ratio("#000000", "#ffffff") == pytest.approx(21.0, abs=0.01)
    assert contrast.ratio("#ffffff", "#ffffff") == pytest.approx(1.0, abs=0.01)
    assert contrast.ratio("#767676", "#ffffff") == pytest.approx(4.54, abs=0.01)


def test_ratio_is_symmetric() -> None:
    assert contrast.ratio("#07294d", "#ffc600") == contrast.ratio("#ffc600", "#07294d")


def test_short_hex_expands() -> None:
    assert contrast.ratio("#fff", "#000") == pytest.approx(21.0, abs=0.01)


def test_a_non_colour_value_raises() -> None:
    with pytest.raises(ValueError):
        contrast.relative_luminance("ui-sans-serif, system-ui")


def test_every_state_clears_wcag_aa_in_every_theme() -> None:
    """The gate: 4.5:1 for state text, 3:1 for the state key, in both themes."""
    assert theme_contrast.check() == []


def test_the_check_actually_inspects_every_theme() -> None:
    """A check that silently found no pairs would return [] and read as a pass.
    Assert the work happened."""
    pairs = theme_contrast.audit()
    themes = {theme for theme, _, _, _, _ in pairs}
    assert themes == {p.stem for p in cssvars.theme_files()}
    assert len(pairs) >= len(themes) * 5


def test_a_washed_out_ink_is_caught() -> None:
    """Prove the threshold bites rather than decorating."""
    assert contrast.ratio("#b8ccc4", "#e3f3ec") < 4.5
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_contrast.py -v`
Expected: FAIL at collection, `ModuleNotFoundError: No module named 'tools.contrast'`

- [ ] **Step 3: Implement the maths**

Create `tools/contrast.py`:

```python
"""WCAG 2.1 relative luminance and contrast ratio.

Pure. Takes CSS hex colours as they appear in the stylesheets and returns the
ratio the success criteria are written against.

Keep decimal literals away from the forbidden-count strings that
tests/test_registry.py greps for in tools/. The constants below are the ones the
specification defines; do not restyle them into fractions.
"""

from __future__ import annotations

import re

_HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def _channels(colour: str) -> tuple[int, int, int]:
    value = colour.strip().lower()
    if _HEX.match(value) is None:
        raise ValueError(f"not a hex colour: {colour!r}")
    body = value[1:]
    if len(body) == 3:
        body = "".join(ch * 2 for ch in body)
    return (int(body[0:2], 16), int(body[2:4], 16), int(body[4:6], 16))


def relative_luminance(colour: str) -> float:
    """WCAG 2.1 relative luminance of an sRGB hex colour."""

    def linearize(channel: int) -> float:
        srgb = channel / 255
        if srgb <= 0.03928:
            return srgb / 12.92
        return ((srgb + 0.055) / 1.055) ** 2.4

    red, green, blue = (linearize(c) for c in _channels(colour))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def ratio(a: str, b: str) -> float:
    """Contrast ratio between two hex colours, from 1.0 to 21.0."""
    first, second = relative_luminance(a), relative_luminance(b)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)
```

- [ ] **Step 4: Implement the check**

Create `tools/checks/theme_contrast.py`. The state pairs are **derived** from the variable names, so a sixth state added later is audited without editing this file. The chrome pairs are named, because their relationship is not encoded in their names.

```python
"""Contrast, per theme, computed from the shipped stylesheets."""

from __future__ import annotations

import re

from tools import contrast, cssvars
from tools.checks import register

TEXT_MINIMUM = 4.5  # WCAG 2.1 AA, 1.4.3, normal-size text
GRAPHIC_MINIMUM = 3.0  # WCAG 2.1 AA, 1.4.11, non-text contrast

# Foreground, background, threshold. Named because the relationship between
# these two variables is not recoverable from their names.
CHROME_PAIRS: tuple[tuple[str, str, float], ...] = (
    ("--text", "--ground", TEXT_MINIMUM),
    ("--text", "--surface", TEXT_MINIMUM),
    ("--text", "--table-row-alt", TEXT_MINIMUM),
    ("--text-muted", "--surface", TEXT_MINIMUM),
    ("--link", "--ground", TEXT_MINIMUM),
    ("--link-visited", "--ground", TEXT_MINIMUM),
    ("--accent-ink", "--accent", TEXT_MINIMUM),
    ("--pill-ink", "--pill-bg", TEXT_MINIMUM),
    ("--pill-active-ink", "--pill-active-bg", TEXT_MINIMUM),
    ("--table-header-ink", "--table-header-bg", TEXT_MINIMUM),
    ("--focus", "--ground", GRAPHIC_MINIMUM),
    ("--border-strong", "--surface", GRAPHIC_MINIMUM),
    ("--void-ink", "--ground", GRAPHIC_MINIMUM),
)

_STATE = re.compile(r"^--state-(?P<state>[a-z0-9-]+)-(?P<role>bg|ink|key)$")


def _state_pairs(names: frozenset[str]) -> tuple[tuple[str, str, float], ...]:
    """Derive (ink on bg) and (key on bg) for every state present."""
    states = sorted({m.group("state") for n in names if (m := _STATE.match(n))})
    pairs: list[tuple[str, str, float]] = []
    for state in states:
        background = f"--state-{state}-bg"
        pairs.append((f"--state-{state}-ink", background, TEXT_MINIMUM))
        pairs.append((f"--state-{state}-key", background, GRAPHIC_MINIMUM))
    return tuple(pairs)


def audit() -> tuple[tuple[str, str, str, float, float], ...]:
    """Every measured pair: (theme, foreground, background, ratio, threshold)."""
    rows: list[tuple[str, str, str, float, float]] = []
    for path in cssvars.theme_files():
        table = cssvars.values(path.read_text(encoding="utf-8"))
        pairs = CHROME_PAIRS + _state_pairs(frozenset(table))
        for foreground, background, threshold in pairs:
            if foreground not in table or background not in table:
                continue  # theme_contract reports the missing variable
            measured = contrast.ratio(
                cssvars.resolve(foreground, table),
                cssvars.resolve(background, table),
            )
            rows.append((path.stem, foreground, background, measured, threshold))
    return tuple(rows)


@register("theme_contrast")
def check() -> list[str]:
    rows = audit()
    if not rows:
        return ["no contrast pairs were measured; the check cannot report a pass"]
    return [
        f"{theme}.css: {fg} on {bg} is {measured:.2f}:1, below {threshold}:1"
        for theme, fg, bg, measured, threshold in rows
        if measured < threshold
    ]
```

Register it in `tools/checks/__init__.py`:

```python
from tools.checks import theme_contrast as _theme_contrast  # noqa: E402,F401
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_contrast.py -v && uv run eda-validate`
Expected: all pass; `validate: 3 checks, 0 failures`.

If a pair fails, darken the ink or lighten the background until it passes. **Do not lower a threshold.** The thresholds are the success criteria, not a preference.

- [ ] **Step 6: Widen the a11y sweep to real pages**

`.pa11yci.json` currently tests one URL. Replace `urls` with:

```json
  "urls": [
    "http://localhost:8080/",
    "http://localhost:8080/explore/",
    "http://localhost:8080/about/card/",
    "http://localhost:8080/submit/"
  ]
```

Then, in `.github/workflows/a11y.yml`, replace the `pa11y-ci` step so a cell page is discovered rather than hardcoded, and a missing one fails:

```yaml
      - name: pa11y-ci
        run: |
          # Route-agnostic: any nested index.html is a cell or model page. If
          # none exists the build is broken, and a silently narrowed a11y sweep
          # is exactly the decorative guard this project keeps deleting.
          cell=$(find dist -mindepth 3 -name index.html | sort | head -1)
          if [ -z "$cell" ]; then
            echo "::error::no nested page found under dist/; a11y sweep would be trivial"
            exit 1
          fi
          url="http://localhost:8080/${cell#dist/}"
          url="${url%index.html}"
          echo "also testing $url"
          npx --yes pa11y-ci --config .pa11yci.json "$url"
```

Add `.pa11yci.json` to that workflow's `on.pull_request.paths` so a config change retests.

- [ ] **Step 7: Run pa11y locally against both themes**

```bash
THEME=drexel uv run python build.py
uv run python -m http.server -d dist 8080 &
npx --yes pa11y-ci --config .pa11yci.json
kill %1
THEME=neutral uv run python build.py
uv run python -m http.server -d dist 8080 &
npx --yes pa11y-ci --config .pa11yci.json
kill %1
```

Expected: zero errors on both. pa11y reports warnings and notices too; only errors fail.

- [ ] **Step 8: Commit**

```bash
git add tools/contrast.py tools/checks/theme_contrast.py tools/checks/__init__.py tests/test_contrast.py .pa11yci.json .github/workflows/a11y.yml
git commit -m "feat(themes): compute WCAG contrast from the shipped stylesheets"
```

---

### Task 5: One line switches the theme, and an unknown value fails loudly

**Files:**
- Modify: `build.py`
- Modify: `Makefile`
- Test: `tests/test_build_theme.py`

**Interfaces:**
- Consumes: `cssvars.theme_files`.
- Produces: `build.selected_theme(env: Mapping[str, str] | None = None) -> str`, `build.theme_stylesheet() -> Path`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_build_theme.py`:

```python
"""THEME selection.

The value comes from the environment, so it is wrong sooner or later: a typo in
a workflow, a stale shell. The failure mode that matters is the quiet one, where
an unknown THEME falls back to the default and CI publishes drexel while its log
says neutral.
"""

from __future__ import annotations

import pytest

import build
from tools import cssvars


def test_the_default_theme_is_a_real_file() -> None:
    assert build.selected_theme({}) in {p.stem for p in cssvars.theme_files()}


def test_the_environment_selects_the_theme() -> None:
    for name in (p.stem for p in cssvars.theme_files()):
        assert build.selected_theme({"THEME": name}) == name


def test_an_unknown_theme_stops_the_build() -> None:
    """A typo must not publish the default under another name's log line."""
    with pytest.raises(SystemExit) as excinfo:
        build.selected_theme({"THEME": "drexl"})
    assert "drexl" in str(excinfo.value)


def test_the_stylesheet_path_matches_the_selection() -> None:
    path = build.theme_stylesheet({"THEME": "neutral"})
    assert path.name == "neutral.css"
    assert path.is_file()
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_build_theme.py -v`
Expected: FAIL, `AttributeError: module 'build' has no attribute 'selected_theme'`

- [ ] **Step 3: Implement**

In `build.py`, replace the existing one-line theme selection with:

```python
DEFAULT_THEME = "drexel"


def selected_theme(env: Mapping[str, str] | None = None) -> str:
    """Which theme this build renders. One environment variable switches it.

    An unknown value stops the build. The alternative, falling back to the
    default, publishes one theme while the log claims another, and nobody reads
    a green log.
    """
    environ = os.environ if env is None else env
    name = environ.get("THEME", DEFAULT_THEME)
    available = sorted(p.stem for p in cssvars.theme_files())
    if name not in available:
        raise SystemExit(f"THEME={name!r} is not one of {available}")
    return name


def theme_stylesheet(env: Mapping[str, str] | None = None) -> Path:
    return cssvars.THEME_DIR / f"{selected_theme(env)}.css"
```

Add `from collections.abc import Mapping` and `from tools import cssvars` to the imports. At the copy-assets step, copy `theme_stylesheet()` to the site's theme asset path and print the selection:

```python
    stylesheet = theme_stylesheet()
    shutil.copyfile(stylesheet, DIST / THEME_ASSET)
    print(f"theme: {stylesheet.name}")
```

- [ ] **Step 4: Add the two-theme build target**

Append to the `Makefile`, and add `themes` to `.PHONY`. `THEME_ASSET` matches whatever path `build.py` writes; change it in one place if Phase 3 chose differently.

```make
# Where build.py drops the selected stylesheet inside dist/.
THEME_ASSET ?= assets/theme.css

# Each guard is a SINGLE recipe line, for the reason documented at the top of
# this file: make runs every line in its own shell.
themes:
	THEME=drexel uv run python build.py
	rm -rf dist-drexel && cp -r dist dist-drexel
	THEME=neutral uv run python build.py
	rm -rf dist-neutral && cp -r dist dist-neutral
	@if cmp -s dist-drexel/$(THEME_ASSET) dist-neutral/$(THEME_ASSET); then echo "themes: both builds shipped the SAME stylesheet"; exit 1; fi
	@if ! cmp -s static/css/themes/drexel.css dist-drexel/$(THEME_ASSET); then echo "themes: dist-drexel does not carry drexel.css"; exit 1; fi
	@if ! cmp -s static/css/themes/neutral.css dist-neutral/$(THEME_ASSET); then echo "themes: dist-neutral does not carry neutral.css"; exit 1; fi
	@echo "themes: dist-drexel and dist-neutral built, distinct, and each carries its own stylesheet"
```

`make clean` already removes `dist-drexel` and `dist-neutral`.

- [ ] **Step 5: Run everything**

```bash
uv run pytest tests/test_build_theme.py -v
make themes
```

Expected: 4 passed, then `themes: dist-drexel and dist-neutral built, distinct, and each carries its own stylesheet`.

- [ ] **Step 6: Look at both, side by side**

```bash
uv run python -m http.server -d dist-drexel 8081 &
uv run python -m http.server -d dist-neutral 8082 &
open http://localhost:8081/ http://localhost:8082/
```

This is a human step and it is the point of the phase. Click all five stages in both. **Pick one to ship** and set `DEFAULT_THEME` to it.

- [ ] **Step 7: Commit**

```bash
git add build.py Makefile tests/test_build_theme.py
git commit -m "feat(build): validate THEME and build both themes from one target"
```

---

### Task 6: Prove the deploy pipeline, including the trigger that has never fired

The site deploys and Pages is live. What has never been exercised is the cross-repo path: `SITE_DISPATCH_TOKEN` is unset on the experiments repo, so `notify-site.yml` has taken its `::notice::` branch and exited 0 on every push. A green workflow that did nothing is the exact failure this project keeps finding.

**Files:**
- No repository files change unless a defect is found.
- Live state: one secret on `JiwaniZakir/eda-schema-experiments`.

**Interfaces:**
- Consumes: `.github/workflows/deploy.yml`, the experiments repo's `notify-site.yml`.
- Produces: evidence, pasted into the PR body.

- [ ] **Step 1: Deploy from main and confirm it lands**

```bash
gh workflow run deploy.yml -R JiwaniZakir/eda-schema-leaderboard
gh run watch -R JiwaniZakir/eda-schema-leaderboard
curl -sI https://jiwanizakir.github.io/eda-schema-leaderboard/ | head -1
```

Expected: the run concludes `success`, and `HTTP/2 200`.

- [ ] **Step 2: Confirm the published bytes are this build**

```bash
curl -s https://jiwanizakir.github.io/eda-schema-leaderboard/assets/theme.css | head -20
```

Expected: the header comment of the theme chosen in Task 5. A 404 here means `build.py` writes the stylesheet somewhere other than `THEME_ASSET`, and the Makefile guard in Task 5 is checking a path nothing produces.

- [ ] **Step 3: Prove the site side of `repository_dispatch` independently**

```bash
gh api -X POST repos/JiwaniZakir/eda-schema-leaderboard/dispatches -f event_type=results-updated
sleep 10
gh run list -R JiwaniZakir/eda-schema-leaderboard --workflow=deploy.yml --event=repository_dispatch --limit 3
```

Expected: a new `deploy` run with event `repository_dispatch`. This isolates the site's listener from the experiments repo's sender, so a failure in Step 4 has exactly one possible cause.

- [ ] **Step 4: Give the experiments repo a token and prove the sender**

Create a fine-grained PAT scoped to **`eda-schema-leaderboard` only**, with `Contents: Read and write` (the `dispatches` endpoint is gated on Contents write) and nothing else. Then:

```bash
gh secret set SITE_DISPATCH_TOKEN -R JiwaniZakir/eda-schema-experiments
gh secret list -R JiwaniZakir/eda-schema-experiments
```

Expected: `SITE_DISPATCH_TOKEN` listed. Never paste the token into a file, a commit or a workflow.

Then trigger a real push on the experiments repo through a PR, and watch both sides:

```bash
gh run list -R JiwaniZakir/eda-schema-experiments --workflow=notify-site.yml --limit 1
gh run list -R JiwaniZakir/eda-schema-leaderboard --workflow=deploy.yml --event=repository_dispatch --limit 1
```

Expected: `notify-site` prints `dispatched results-updated`, not the skip notice, and a matching `deploy` run appears within a minute.

- [ ] **Step 5: Measure the payload against the budget**

```bash
make themes
du -sh dist-drexel dist-neutral
find dist-drexel -name '*.html' -print0 | xargs -0 wc -c | sort -rn | head -6
find dist-drexel -type f -print0 | xargs -0 wc -c | sort -rn | head -6
```

Budgets, from `PLAN.md`: `dist/` targets **20 MB** against a Pages cap of **1 GB**; no page exceeds **88 KB**; `size-guard.yml` hard-fails at 200 MB and at 1 MB for any tracked file. Record the three numbers in the PR body. If a page is over 88 KB, that is a Phase 5 regression and it is fixed here rather than noted.

- [ ] **Step 6: Record the evidence**

No commit unless a defect was found. Paste into the PR body: the deploy run URL, the `curl -sI` status line, the `repository_dispatch` run URL, and the `du -sh` output for both themes.

---

### Task 7: Decide the review stack, out loud

**This is a decision task. Do not pick silently and do not implement both.**

The facts, verified:

- `claude-review.yml` has **never run**. `gh secret list` is empty on both repositories, so `preflight` resolves `configured=false` and `review` skips on every pull request to date. The workflow reports green while doing nothing.
- The review value on this repository actually came from **`coderabbitai`**, which appears nowhere in `PLAN.md`.
- Every phase also ends with an adversarial subagent review, which is a third layer.
- Three overlapping automated reviewers violates the project's one-tool-per-job rule. `PLAN.md` Phase 0 listed "resolve the review stack to one tool" in scope and it did not happen, so it lands here.

Neither option is free, and the plan does not choose for you.

**Option A: configure it, and keep it credential-free.**

`PLAN.md` Phase 0 specified workload identity federation rather than a long-lived secret. That is achievable only through a cloud provider: the direct Anthropic API has no OIDC federation path, so "configure the key" there means a long-lived Console key in a repo secret, which is the thing federation was chosen to avoid. Federated, via Bedrock:

```yaml
  review:
    needs: preflight
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
      id-token: write        # the OIDC token, exchanged for a short-lived role
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
          persist-credentials: false

      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ vars.CLAUDE_REVIEW_ROLE_ARN }}
          aws-region: us-east-1

      - uses: anthropics/claude-code-action@v1
        with:
          use_bedrock: true
          prompt: |
            ...unchanged...
```

Cost: an AWS account with Bedrock model access, an IAM role trusting this repository's OIDC subject, and after transfer that trust policy names `drexel-ice`, so it is re-issued by whoever owns the AWS account. `preflight` then keys on `vars.CLAUDE_REVIEW_ROLE_ARN` instead of a secret. The `pull_request` trigger and the fork skip stay exactly as they are.

**Option B: delete it, and name CodeRabbit the one automated reviewer.**

```bash
git rm .github/workflows/claude-review.yml
```

Then make the incumbent explicit rather than accidental, in `.coderabbit.yaml`:

```yaml
# The single automated PR reviewer. See PLAN.md, review stack decision.
reviews:
  profile: assertive
  request_changes_workflow: false
  path_filters:
    - "!dist/**"
    - "!docs/sources/**"
  path_instructions:
    - path: "tools/**"
      instructions: >-
        Flag any path that unpickles data or loads YAML with a tag-executing
        loader. Flag any hardcoded task, PDK, stage, metric or circuit name
        outside data/registry/. Flag any count literal from the set
        46, 232, 880, 856, 120, 40, 24, 920.
    - path: "data/registry/**"
      instructions: >-
        These are the single source of truth for every vocabulary. Any change
        needs a matching change in docs/DATA_CONTRACT.md.
```

Cost: no Claude review in CI. Claude still reviews every phase as an adversarial subagent at authoring time, which is where its findings have actually been used.

**Safe either way:** branch protection requires `size`, `analyze (python)`, `lint`, `typecheck`, `validate`, `test`, `build`. `claude-review` is not a required context, so deleting it cannot wedge merges. Confirm before deleting:

```bash
gh api repos/JiwaniZakir/eda-schema-leaderboard/branches/main/protection \
  --jq '.required_status_checks.contexts'
```

- [ ] **Step 1: Put the decision to the maintainer**

Present both options with their costs. Do not proceed on a guess.

- [ ] **Step 2: Implement exactly one**

- [ ] **Step 3: Record the verdict in PLAN.md**

Add a row to the `## Open decisions` table with the verdict, the date, and the role split if two reviewers coexist. An undocumented coexistence is what the one-tool-per-job rule forbids; a documented one is allowed.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/claude-review.yml PLAN.md   # or: git add -u for the deletion
git commit -m "chore(ci): resolve the review stack to one automated reviewer"
```

---

### Task 8: One citation, in one file

`PLAN.md`'s goal is "a static, **citable** benchmark leaderboard". Until this task, nothing in the repository cited the leaderboard. `docs/CARD.yaml` has a `citation:` field and its value names the source paper, so a reader who followed it credited the dataset authors for this work and still had no way to cite the leaderboard itself.

`CITATION.cff` at the repository root fixes that once. GitHub renders it as the "Cite this repository" button, Zenodo reads it when archiving a release, Zotero reads it on import, and `tools/citation.py` renders every copy the site displays. One file, four consumers, no second copy to forget.

**There is deliberately no `.zenodo.json`.** Zenodo populates a deposition from `CITATION.cff` when the repository has one, so a second metadata file would only be a second place for the authors, the version and the DOI to disagree. That is the one-tool-per-job rule applied to metadata.

The schema is **vendored**, not fetched. A validator that needs the network is a validator that gets skipped on the day it matters.

**Files:**
- Create: `CITATION.cff`, `schema/citation-cff-1.2.0.json`, `tools/citation.py`, `tools/checks/citation.py`
- Modify: `tools/checks/__init__.py`, `tools/card.py`, `docs/CARD.yaml`, `templates/pages/card.html`, `docs/sources/PROVENANCE.md`
- Test: `tests/test_citation.py`

**Interfaces:**
- Consumes: `CITATION.cff`, `schema/citation-cff-1.2.0.json`, `jsonschema` (already a dependency), `static/CNAME` when it exists.
- Produces:
  - `citation.CITATION_PATH: Path`, `citation.SCHEMA_PATH: Path`, `citation.ROOT: Path`
  - `citation.CitationError`
  - `citation.Author`, `citation.Reference`, `citation.Citation`, `citation.Block`
  - `citation.schema_problems(raw: Any) -> list[str]`
  - `citation.load(path: Path = CITATION_PATH) -> Citation`
  - `citation.apa(ref: Reference) -> str`, `citation.apa_authors(authors: tuple[Author, ...]) -> str`
  - `citation.bibtex(ref: Reference) -> str`, `citation.bibtex_author(author: Author) -> str`
  - `citation.doi_url(ref: Reference) -> str`
  - `citation.blocks(loaded: Citation | None = None) -> tuple[Block, ...]`
  - `checks.citation.expected_site_url(repository_code: str, cname_path: Path) -> str`
  - `checks.citation.problems(path: Path, cname_path: Path) -> list[str]`, `checks.citation.check() -> list[str]`

- [ ] **Step 1: Vendor the schema**

```bash
mkdir -p schema
curl -sSfL -o schema/citation-cff-1.2.0.json \
  https://raw.githubusercontent.com/citation-file-format/citation-file-format/1.2.0/schema.json
python3 -c "import json;d=json.load(open('schema/citation-cff-1.2.0.json'));print(d['\$id'], d['required'])"
```

Expected: `https://citation-file-format.github.io/1.2.0/schema.json ['authors', 'cff-version', 'message', 'title']`, and a file of roughly 64 KB, well inside the 1 MB per-file cap.

Record the provenance in `docs/sources/PROVENANCE.md`: the Citation File Format schema is CC-BY-4.0, from `citation-file-format/citation-file-format` at tag `1.2.0`.

**Do not add a fourth entry to `docs/CARD.yaml`'s `licences:` list.** `tests/test_card.py::test_licensing_declares_all_three_licences` asserts that set is exactly `{MIT, CC-BY-4.0, CC-BY-NC-SA-4.0}`, and the schema is a build-time validator, not something the leaderboard distributes as data. Attribution goes in `PROVENANCE.md`.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_citation.py`:

```python
"""CITATION.cff: valid, complete, and the only place any of this is written.

The gap this closes was measured, not guessed. Before this task, `DOI`,
`Zenodo`, `CITATION.cff`, `BibTeX` and `ORCID` appeared zero times across the
repository, the CI workflows and all nine phase plans, while PLAN.md's goal
sentence promised a CITABLE leaderboard.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

from tools import card, citation

ROOT = Path(__file__).resolve().parent.parent
PLACEHOLDER_ORCID = "https://orcid.org/0000-0000-0000-0000"


def _raw() -> dict[str, object]:
    loaded = yaml.safe_load(citation.CITATION_PATH.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def test_the_file_lives_where_github_looks_for_it() -> None:
    """GitHub renders "Cite this repository" from CITATION.cff on the default
    branch, reading the repository root, docs/ or .github/. Anywhere else and
    the button never appears, which is a silent failure: the file is present,
    correct, and doing nothing."""
    assert citation.CITATION_PATH == ROOT / "CITATION.cff"
    assert citation.CITATION_PATH.is_file()


def test_the_vendored_schema_is_the_one_we_claim() -> None:
    schema = json.loads(citation.SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["$id"] == "https://citation-file-format.github.io/1.2.0/schema.json"


def test_it_validates_against_the_citation_file_format_schema() -> None:
    assert citation.schema_problems(_raw()) == []


def test_a_missing_required_field_is_caught() -> None:
    """Prove the validator bites rather than decorating."""
    raw = _raw()
    del raw["authors"]
    assert any("authors" in problem for problem in citation.schema_problems(raw))


def test_a_misspelled_key_is_caught() -> None:
    """The schema sets additionalProperties: false, so the British spelling is
    an error rather than a line that is silently ignored forever."""
    raw = _raw()
    raw["licence"] = "MIT"
    assert any("licence" in problem for problem in citation.schema_problems(raw))


def test_the_release_date_survives_yaml_as_a_string() -> None:
    """CFF dates are STRINGS matching YYYY-MM-DD. PyYAML turns an unquoted
    2026-08-11 into a datetime.date, which then fails validation as "not of type
    string"; the schema carries a $comment telling tool implementers to cast.
    load() casts, so an unquoted date is accepted rather than being a trap that
    only fires when someone removes the quotes."""
    loaded = citation.load()
    assert isinstance(loaded.released, str)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", loaded.released)


def test_it_cites_the_leaderboard_and_not_the_paper() -> None:
    """THE GAP, asserted. docs/CARD.yaml's citation field named the paper."""
    leaderboard = citation.load().leaderboard
    assert "leaderboard" in leaderboard.title.lower()
    assert leaderboard.kind == "software"
    assert leaderboard.url.startswith("https://")


def test_the_paper_is_carried_as_a_reference() -> None:
    paper = citation.load().paper
    assert paper.kind == "article"
    assert paper.eprint == "2605.06952"
    assert paper.authors


def test_one_formatter_serves_both_references() -> None:
    """A second implementation is how two citations on one page drift into two
    styles, and the reader cannot tell which one is wrong."""
    loaded = citation.load()
    for ref in (loaded.leaderboard, loaded.paper):
        assert citation.bibtex(ref).startswith("@")
        assert ref.title in citation.apa(ref)


def test_the_bibtex_is_balanced_and_paste_ready() -> None:
    entry = citation.bibtex(citation.load().leaderboard)
    assert entry.count("{") == entry.count("}")
    assert entry.startswith("@software{")
    assert entry.rstrip().endswith("}")
    for field in ("author", "title", "year", "url"):
        assert re.search(rf"^\s*{field}\s+=", entry, re.MULTILINE), field


def test_apa_orders_and_punctuates_authors() -> None:
    people = (
        citation.Author(given="Ada", family="Lovelace"),
        citation.Author(given="Alan Mathison", family="Turing"),
    )
    assert citation.apa_authors(people) == "Lovelace, A., & Turing, A. M."


def test_apa_handles_a_lone_author_and_an_entity() -> None:
    solo = (citation.Author(given="Ada", family="Lovelace"),)
    assert citation.apa_authors(solo) == "Lovelace, A."
    lab = (citation.Author(name="Drexel ICE Laboratory"),)
    assert citation.apa_authors(lab) == "Drexel ICE Laboratory"


def test_an_entity_author_is_braced_in_bibtex() -> None:
    """Without braces, BibTeX reads "Drexel ICE Laboratory" as a person and
    prints "D. I. Laboratory"."""
    entity = citation.Author(name="Drexel ICE Laboratory")
    assert citation.bibtex_author(entity) == "{Drexel ICE Laboratory}"


def test_no_placeholder_orcid_ships() -> None:
    """A placeholder ORCID credits nobody while looking filled in, which is
    worse than an absent field. CFF makes orcid optional; leave it out until
    there is a real one."""
    assert PLACEHOLDER_ORCID not in citation.CITATION_PATH.read_text(encoding="utf-8")


def test_every_orcid_is_the_full_https_uri() -> None:
    """The schema's pattern demands the URI form. A bare 0000-0002-1825-0097 is
    the natural thing to paste and it fails validation."""
    for author in citation.load().leaderboard.authors:
        if author.orcid is not None:
            assert author.orcid.startswith("https://orcid.org/")


def test_no_em_dash_in_the_citation() -> None:
    assert "—" not in citation.CITATION_PATH.read_text(encoding="utf-8")


def test_there_is_no_second_metadata_file() -> None:
    """Zenodo reads CITATION.cff. A .zenodo.json would be a second place for the
    authors, the version and the DOI to disagree."""
    assert not (ROOT / ".zenodo.json").exists()


def test_the_card_no_longer_declares_its_own_version_or_citation() -> None:
    """docs/CARD.yaml carried version: "0.1" and a citation naming the paper.
    Both are derived now, and this is what stops them growing back."""
    raw = yaml.safe_load((ROOT / "docs" / "CARD.yaml").read_text(encoding="utf-8"))
    assert "version" not in raw
    assert "citation" not in raw
    assert "version" not in card.REQUIRED_TOP_LEVEL
    assert "citation" not in card.REQUIRED_TOP_LEVEL


def test_a_citation_with_no_authors_cannot_be_rendered() -> None:
    with pytest.raises(citation.CitationError):
        citation.apa_authors(())
```

- [ ] **Step 3: Run to verify they fail**

Run: `uv run pytest tests/test_citation.py -v`
Expected: FAIL at collection, `ImportError: cannot import name 'citation' from 'tools'`

- [ ] **Step 4: Write CITATION.cff**

Before writing the author list, check it. The paper's authors are transcribed from the arXiv listing, not from memory:

```bash
curl -sSfL https://arxiv.org/abs/2605.06952 | grep -io '<meta name="citation_author" content="[^"]*"'
```

Use exactly what that prints, in that order. If the listing disagrees with what is written below, the listing wins.

Create `CITATION.cff` at the repository root:

```yaml
# How to cite THIS leaderboard. Not the paper it benchmarks against: that is the
# entry under references:, and citing it instead of this was the gap this file
# closes.
#
# This is the only place the version, the release date, the authors, the licence
# and the DOI are written down. tools/citation.py renders every other copy: the
# /cite/ page, the block on /about/card/, the footer stamp on every page,
# GitHub's "Cite this repository" button, and Zenodo's deposition metadata.
#
# Do NOT add a .zenodo.json. Zenodo reads this file.
cff-version: 1.2.0
message: >-
  If you use this leaderboard or the comparisons published on it, please cite
  both this record and the EDA-Schema-V2 paper whose baseline it publishes.
title: EDA-Schema Leaderboard
type: software
authors:
  - given-names: Zakir
    family-names: Jiwani
  - name: Drexel ICE Laboratory
version: "0.1.0"
date-released: "2026-08-11"
license: MIT
url: https://jiwanizakir.github.io/eda-schema-leaderboard/
repository-code: https://github.com/JiwaniZakir/eda-schema-leaderboard
abstract: >-
  A static benchmark leaderboard for the EDA-Schema-V2 dataset. It publishes the
  paper's Table 8 baseline across twelve prediction tasks, four PDKs and five
  stage transitions, and ranks community submissions against it.
keywords:
  - electronic design automation
  - benchmark
  - leaderboard
  - machine learning
  - EDA-Schema
identifiers:
  # CFF has no field for a content digest, and `other` is the schema's escape
  # hatch. Task 9 fills this in with `make version` and then fails the build
  # whenever data/ moves and this does not. The zeros below live for exactly one
  # commit.
  - type: other
    value: "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    description: Data fingerprint of the published leaderboard
references:
  - type: article
    scope: Cite the dataset and the published baseline this leaderboard ranks against
    title: "EDA-Schema-V2: a graph-based schema for chip design data"
    authors:
      - given-names: Pratik
        family-names: Kolluru
      - given-names: Ioannis
        family-names: Savidis
    year: 2026
    status: preprint
    url: https://arxiv.org/abs/2605.06952
    identifiers:
      - type: other
        value: arXiv:2605.06952
```

`url`, `version` and `date-released` are quoted deliberately. YAML would otherwise hand `date-released` back as a `datetime.date` and `version: 0.1` back as a float, and both are string-typed in CFF.

- [ ] **Step 5: Write the loader and the formatters**

Create `tools/citation.py`:

```python
"""CITATION.cff, loaded once and rendered everywhere.

CITATION.cff in the repository root is the only place this leaderboard's own
citation is written down. This module validates it against the vendored
Citation File Format 1.2.0 schema and formats BibTeX and APA from it, so the
/cite/ page, the card block, the footer stamp and GitHub's own citation button
are four renderings of one fact rather than four facts.

The same two formatters serve the leaderboard and the paper. A second
implementation is how two citations on one page end up in two styles.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass, replace
from functools import cache
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft7Validator

ROOT = Path(__file__).resolve().parent.parent
CITATION_PATH = ROOT / "CITATION.cff"
SCHEMA_PATH = ROOT / "schema" / "citation-cff-1.2.0.json"

# The identifiers[] entry carrying the data fingerprint is found by its
# description, not by its value, so tools/fingerprint.py and this module share
# no constant and neither imports the other's spelling of "sha256".
FINGERPRINT_DESCRIPTION = "Data fingerprint of the published leaderboard"

ZENODO_PREFIX = "10.5281/zenodo."

# The schema requires only cff-version, message, title and authors. These are
# the fields the SITE needs; a file without them validates cleanly and then
# renders a citation with holes in it.
REQUIRED_KEYS: tuple[str, ...] = (
    "type",
    "version",
    "date-released",
    "url",
    "repository-code",
    "license",
    "references",
)

BIBTEX_ENTRY: dict[str, str] = {
    "software": "software",
    "dataset": "misc",
    "database": "misc",
    "article": "article",
    "generic": "misc",
}

APA_MEDIUM: dict[str, str] = {
    "software": "Computer software",
    "dataset": "Data set",
    "database": "Data set",
}

_ARXIV = re.compile(r"arXiv:(?P<id>\d{4}\.\d{4,5}(?:v\d+)?)", re.IGNORECASE)
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


class CitationError(Exception):
    """CITATION.cff is invalid, or is missing something the site needs."""


@dataclass(frozen=True, slots=True)
class Author:
    given: str = ""
    family: str = ""
    name: str = ""  # an entity: a lab, a group, an institution
    orcid: str | None = None


@dataclass(frozen=True, slots=True)
class Reference:
    key: str
    kind: str
    title: str
    authors: tuple[Author, ...]
    year: str
    url: str
    scope: str
    doi: str | None = None
    version: str | None = None
    publisher: str | None = None
    eprint: str | None = None


@dataclass(frozen=True, slots=True)
class Citation:
    leaderboard: Reference
    references: tuple[Reference, ...]
    released: str
    repository_code: str
    licence: str
    fingerprint: str | None

    @property
    def paper(self) -> Reference:
        """The work this leaderboard benchmarks against. It is the first
        reference by construction: load() refuses a file without one."""
        return self.references[0]


@dataclass(frozen=True, slots=True)
class Block:
    """One rendered citation. The template loops these and does nothing else."""

    scope: str
    key: str
    apa: str
    bibtex: str
    doi_url: str


def _stringify_dates(value: Any) -> Any:
    """Cast YAML date objects to strings before validating.

    CFF dates are strings matching YYYY-MM-DD, and the schema carries a
    $comment saying so to tool implementers. PyYAML turns an unquoted
    2026-08-11 into a datetime.date, which then fails validation as "not of
    type string" while being a perfectly correct file.
    """
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _stringify_dates(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_stringify_dates(item) for item in value]
    return value


@cache
def _validator() -> Draft7Validator:
    return Draft7Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))


def schema_problems(raw: Any) -> list[str]:
    """Every CFF 1.2.0 schema violation, as readable lines. Empty on success."""
    errors = sorted(_validator().iter_errors(_stringify_dates(raw)), key=str)
    return [
        f"{'/'.join(str(part) for part in error.absolute_path) or 'CITATION.cff'}: "
        f"{error.message}"
        for error in errors
    ]


def _author(raw: dict[str, Any]) -> Author:
    return Author(
        given=str(raw.get("given-names", "")),
        family=str(raw.get("family-names", "")),
        name=str(raw.get("name", "")),
        orcid=None if raw.get("orcid") is None else str(raw["orcid"]),
    )


def _bibtex_key(title: str, authors: tuple[Author, ...], year: str) -> str:
    lead = _NON_ALNUM.sub("", (authors[0].family or authors[0].name).lower())
    words = title.lower().split()
    word = _NON_ALNUM.sub("", words[0]) if words else "work"
    return f"{lead}{year}{word}"


def _publisher(raw: dict[str, Any]) -> str | None:
    entity = raw.get("publisher")
    if isinstance(entity, dict):
        return str(entity.get("name", "")) or None
    return None


def _eprint(raw: dict[str, Any]) -> str | None:
    identifiers = raw.get("identifiers", [])
    haystack = " ".join(str(entry.get("value", "")) for entry in identifiers)
    match = _ARXIV.search(f"{haystack} {raw.get('url', '')}")
    return None if match is None else match.group("id")


def _reference(raw: dict[str, Any], default_scope: str) -> Reference:
    authors = tuple(_author(person) for person in raw.get("authors", []))
    released = str(raw.get("date-released") or raw.get("date-published") or "")
    year = str(raw.get("year") or released.split("-")[0])
    title = str(raw["title"])
    return Reference(
        key=_bibtex_key(title, authors, year),
        kind=str(raw.get("type", "generic")),
        title=title,
        authors=authors,
        year=year,
        url=str(raw.get("url", "")),
        scope=str(raw.get("scope", default_scope)),
        doi=None if raw.get("doi") is None else str(raw["doi"]),
        version=None if raw.get("version") is None else str(raw["version"]),
        publisher=_publisher(raw),
        eprint=_eprint(raw),
    )


def _fingerprint_identifier(raw: dict[str, Any]) -> str | None:
    for entry in raw.get("identifiers", []):
        if entry.get("description") == FINGERPRINT_DESCRIPTION:
            return str(entry.get("value", "")) or None
    return None


def _required_problems(raw: dict[str, Any]) -> list[str]:
    problems = [f"missing or empty: {key}" for key in REQUIRED_KEYS if not raw.get(key)]
    references = raw.get("references")
    if isinstance(references, list) and references:
        first = references[0]
        if not isinstance(first, dict) or not first.get("authors"):
            problems.append("references[0] must carry the source paper and its authors")
    return problems


def load(path: Path = CITATION_PATH) -> Citation:
    """Parse, validate and structure CITATION.cff.

    Raises rather than returning a partial object. Every consumer of this
    renders a citation, and half a citation is worse than none: it looks
    complete to a reader who does not know what is missing.
    """
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise CitationError(f"{path} is not a mapping")

    problems = schema_problems(raw)
    problems.extend(_required_problems(raw))
    if problems:
        raise CitationError(f"{path}:\n  " + "\n  ".join(problems))

    root: dict[str, Any] = _stringify_dates(raw)
    leaderboard = _reference(root, default_scope="Cite the leaderboard")
    if leaderboard.doi is not None and leaderboard.doi.startswith(ZENODO_PREFIX):
        leaderboard = replace(leaderboard, publisher="Zenodo")

    return Citation(
        leaderboard=leaderboard,
        references=tuple(
            _reference(entry, default_scope="Cite the source paper")
            for entry in root["references"]
        ),
        released=str(root["date-released"]),
        repository_code=str(root["repository-code"]),
        licence=str(root["license"]),
        fingerprint=_fingerprint_identifier(root),
    )


def _initials(given: str) -> str:
    parts = [part for part in re.split(r"[\s\-]+", given) if part]
    return " ".join(f"{part[0].upper()}." for part in parts)


def apa_author(author: Author) -> str:
    if author.name:
        return author.name
    initials = _initials(author.given)
    return f"{author.family}, {initials}" if initials else author.family


def apa_authors(authors: tuple[Author, ...]) -> str:
    """An APA 7 author list: comma separated, ampersand before the last."""
    rendered = [apa_author(author) for author in authors]
    if not rendered:
        raise CitationError("a reference with no authors cannot be cited")
    if len(rendered) == 1:
        return rendered[0]
    return f"{', '.join(rendered[:-1])}, & {rendered[-1]}"


def bibtex_author(author: Author) -> str:
    """Braces around an entity name, or BibTeX reads "Drexel ICE Laboratory" as
    a person and prints "D. I. Laboratory"."""
    if author.name:
        return f"{{{author.name}}}"
    return f"{author.family}, {author.given}"


def doi_url(ref: Reference) -> str:
    return f"https://doi.org/{ref.doi}" if ref.doi else ""


def bibtex(ref: Reference) -> str:
    """One BibTeX entry, for either the leaderboard or the paper."""
    fields: list[tuple[str, str]] = [
        ("author", " and ".join(bibtex_author(author) for author in ref.authors)),
        # The inner braces preserve the capitalisation of EDA-Schema.
        ("title", "{" + ref.title + "}"),
        ("year", ref.year),
    ]
    if ref.version:
        fields.append(("version", ref.version))
    if ref.publisher:
        fields.append(("publisher", ref.publisher))
    if ref.eprint:
        fields.append(("eprint", ref.eprint))
        fields.append(("archivePrefix", "arXiv"))
    if ref.doi:
        fields.append(("doi", ref.doi))
    fields.append(("url", ref.url))

    width = max(len(name) for name, _ in fields)
    body = "\n".join(f"  {name:<{width}} = {{{value}}}," for name, value in fields)
    return f"@{BIBTEX_ENTRY[ref.kind]}{{{ref.key},\n{body}\n}}"


def apa(ref: Reference) -> str:
    """One APA 7 reference, for either the leaderboard or the paper."""
    # A personal author list already ends in an initial's full stop; an entity
    # such as "Drexel ICE Laboratory" does not, and APA wants one before the
    # year regardless.
    people = apa_authors(ref.authors)
    if not people.endswith("."):
        people = f"{people}."
    parts = [f"{people} ({ref.year}). {ref.title}"]
    if ref.version:
        parts.append(f" (Version {ref.version})")
    if ref.eprint:
        parts.append(f" (arXiv:{ref.eprint})")
    elif ref.kind in APA_MEDIUM:
        parts.append(f" [{APA_MEDIUM[ref.kind]}]")
    publisher = ref.publisher or ("arXiv" if ref.eprint else None)
    if publisher:
        parts.append(f". {publisher}")
    parts.append(f". {doi_url(ref) or ref.url}")
    return "".join(parts)


def blocks(loaded: Citation | None = None) -> tuple[Block, ...]:
    """Every citation the site displays, the leaderboard first.

    /cite/ and /about/card/ both render THIS, through one partial. Two lists
    would be two places to forget the paper.
    """
    current = load() if loaded is None else loaded
    return tuple(
        Block(
            scope=ref.scope,
            key=ref.key,
            apa=apa(ref),
            bibtex=bibtex(ref),
            doi_url=doi_url(ref),
        )
        for ref in (current.leaderboard, *current.references)
    )
```

- [ ] **Step 6: Write the check, including the transfer trip-wire**

Create `tools/checks/citation.py`. It grows across this phase and stays **one** check: Task 8 lands the schema, the required fields and the home URL; Task 9 adds the fingerprint and the two versions; Task 11 adds the release ledger. A reader of `eda-validate` output should see one line about the citation, not four.

```python
"""CITATION.cff is valid, complete, and points at the site's real home."""

from __future__ import annotations

import re
from pathlib import Path

from tools import citation
from tools.checks import register

CNAME_PATH = citation.ROOT / "static" / "CNAME"
PLACEHOLDER_ORCID = "https://orcid.org/0000-0000-0000-0000"

_REPO = re.compile(
    r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$"
)


def expected_site_url(repository_code: str, cname_path: Path = CNAME_PATH) -> str:
    """Where a repository at this URL publishes its Pages site.

    This is the transfer trip-wire, and it is the mechanism behind this phase's
    ordering rule. The moment the repository moves to drexel-ice, the expected
    URL changes while CITATION.cff still says jiwanizakir, so `make check` goes
    red until the citation is repointed. Nobody has to remember.
    """
    match = _REPO.match(repository_code.strip())
    if match is None:
        raise ValueError(f"not a GitHub repository URL: {repository_code!r}")
    if cname_path.is_file():
        return f"https://{cname_path.read_text(encoding='utf-8').strip()}/"
    return f"https://{match.group('owner').lower()}.github.io/{match.group('repo')}/"


def problems(
    path: Path = citation.CITATION_PATH, cname_path: Path = CNAME_PATH
) -> list[str]:
    try:
        loaded = citation.load(path)
    except citation.CitationError as error:
        return str(error).splitlines()

    failures: list[str] = []
    text = path.read_text(encoding="utf-8")
    if "—" in text:
        failures.append(f"{path.name} contains an em dash")
    if PLACEHOLDER_ORCID in text:
        failures.append(f"{path.name} still carries the placeholder ORCID")

    try:
        expected = expected_site_url(loaded.repository_code, cname_path)
    except ValueError as error:
        failures.append(str(error))
        return failures

    if loaded.leaderboard.url != expected:
        failures.append(
            f"url is {loaded.leaderboard.url}, but repository-code and "
            f"static/CNAME say the site is served from {expected}. A citation "
            "naming the wrong home is exactly what a repository transfer causes"
        )
    return failures


@register("citation")
def check() -> list[str]:
    return problems()
```

Register it beside the others in `tools/checks/__init__.py`:

```python
from tools.checks import citation as _citation  # noqa: E402,F401
```

- [ ] **Step 7: Stop the card declaring its own version and citation**

In `tools/card.py`, drop `"version"` and `"citation"` from `REQUIRED_TOP_LEVEL` and from the `Card` dataclass, and delete them from `docs/CARD.yaml`. If `templates/pages/card.html` prints either, delete those lines; Task 10 puts the real citation block on that page.

`updated:` stays. It is the date the card's prose was last reviewed, which is genuinely not the date the data was released, and binding the two would force an editorial edit on every data change. That is a deliberate non-binding, not an oversight.

- [ ] **Step 8: Run everything**

```bash
uv run pytest tests/test_citation.py tests/test_card.py -v
uv run eda-validate
uv run ruff check . && uv run ruff format --check . && uv run mypy
```

Expected: all tests pass, `citation` contributes 0 failures, and the check count printed by `eda-validate` has gone up by one.

- [ ] **Step 9: Confirm GitHub actually renders it**

Push the branch and open it on GitHub. The "Cite this repository" button appears in the sidebar of the repository landing page once the file is on the **default** branch, so this is confirmed after merge, not before. If GitHub shows a parse error instead, it names the line; the vendored schema should already have caught it.

- [ ] **Step 10: Commit**

```bash
git add CITATION.cff schema/citation-cff-1.2.0.json tools/citation.py tools/checks/citation.py tools/checks/__init__.py tools/card.py docs/CARD.yaml docs/sources/PROVENANCE.md templates/pages/card.html tests/test_citation.py
git commit -m "feat(citation): cite the leaderboard itself from one validated CITATION.cff"
```

---

### Task 9: Bind the version to the data, so nobody can forget to bump it

`version: "0.1"` in the card and `version = "0.1.0"` in `pyproject.toml` were two hand-maintained strings with nothing behind them. A citation whose version does not track its content is a citation that points at the wrong numbers, silently, and the reader has no way to notice.

**The choice, and why.** `PLAN.md`'s options were a test that fails when `data/` changes without a version change, or a build that stamps the version and a content hash into the page. This task does the first and gets the second nearly free, because both need the same digest. What it does **not** do is derive the version from git tags: a tag-derived version reads as `0.1.0-3-gabc1234` on every working tree, cannot be checked offline, and says nothing about whether the *data* moved. The fingerprint is a claim about content, checked against content.

**The set that is hashed is the DATA, not the code.** A CSS colour or a template tweak does not change what the leaderboard reports. Bumping the version on every whitespace fix trains people to bump without thinking, which is the failure this exists to prevent.

**Files:**
- Create: `tools/fingerprint.py`
- Modify: `tools/checks/citation.py`, `pyproject.toml`, `Makefile`, `build.py`, `templates/base.html`, `CITATION.cff`
- Test: `tests/test_fingerprint.py`

**Interfaces:**
- Consumes: `data/registry/*.json`, `data/baseline.json`, `data/cells/**/*.json`, `docs/sources/table8_baseline.csv`, `tools.citation`.
- Produces:
  - `fingerprint.CONTENT_GLOBS: tuple[str, ...]`, `fingerprint.PREFIX: str`
  - `fingerprint.content_files(root: Path = ROOT) -> tuple[Path, ...]`
  - `fingerprint.fingerprint(root: Path = ROOT) -> str`
  - `fingerprint.record(digest: str, path: Path) -> bool`
  - `fingerprint.main(argv: Sequence[str] | None = None) -> int`, the `eda-fingerprint` console script
  - `build.site_context() -> dict[str, str]`, exposed to every template as `site`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_fingerprint.py`:

```python
"""The version is a claim about the data, and this is what checks it."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tools import citation, fingerprint
from tools.checks import citation as citation_check

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """A whole copy of the citable content, editable without touching the repo."""
    dest = tmp_path / "repo"
    dest.mkdir()
    shutil.copy(ROOT / "CITATION.cff", dest / "CITATION.cff")
    shutil.copy(ROOT / "pyproject.toml", dest / "pyproject.toml")
    cname = ROOT / "static" / "CNAME"
    if cname.is_file():
        # After Task 12 the expected site URL comes from here, and a tree
        # without it would compute the github.io form and report a false gap.
        (dest / "static").mkdir()
        shutil.copy(cname, dest / "static" / "CNAME")
    for path in fingerprint.content_files():
        target = dest / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(path, target)
    return dest


def test_the_hashed_set_is_not_empty() -> None:
    """A digest over nothing is a stable digest that proves nothing, and it
    would pass every assertion below."""
    assert fingerprint.content_files()


def test_an_empty_content_set_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        fingerprint.fingerprint(tmp_path)


def test_it_is_deterministic(tree: Path) -> None:
    assert fingerprint.fingerprint(tree) == fingerprint.fingerprint(tree)


def test_it_is_prefixed_and_hex(tree: Path) -> None:
    digest = fingerprint.fingerprint(tree)
    assert digest.startswith(fingerprint.PREFIX)
    assert set(digest.removeprefix(fingerprint.PREFIX)) <= set("0123456789abcdef")


def test_one_changed_byte_changes_it(tree: Path) -> None:
    before = fingerprint.fingerprint(tree)
    target = sorted(tree.glob("data/registry/*.json"))[0]
    target.write_text(target.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert fingerprint.fingerprint(tree) != before


def test_a_rename_changes_it(tree: Path) -> None:
    """The path is hashed with its length, so shuffling bytes between a name and
    its neighbour's content cannot produce the same stream."""
    before = fingerprint.fingerprint(tree)
    target = sorted(tree.glob("data/registry/*.json"))[0]
    target.rename(target.with_name("zz_" + target.name))
    assert fingerprint.fingerprint(tree) != before


def test_code_is_not_hashed(tree: Path) -> None:
    """A CSS colour does not change what the leaderboard reports, and a version
    bump on every whitespace fix trains people to bump without reading."""
    assert not any(
        path.suffix in {".py", ".css", ".js", ".html"}
        for path in fingerprint.content_files()
    )


def test_the_recorded_fingerprint_matches_the_tree() -> None:
    """The live claim. This is the assertion that fails when data/ moves."""
    assert citation.load().fingerprint == fingerprint.fingerprint()


def test_changing_data_without_bumping_the_version_fails_the_check(
    tree: Path,
) -> None:
    """THE POINT OF THIS TASK. Edit one data file, leave the version alone, and
    the gate must go red naming the fingerprint."""
    assert citation_check.problems(tree / "CITATION.cff", tree / "static" / "CNAME") == []

    target = sorted(tree.glob("data/registry/*.json"))[0]
    target.write_text(target.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    failures = citation_check.problems(tree / "CITATION.cff", tree / "static" / "CNAME")
    assert any("fingerprint" in failure for failure in failures), failures


def test_the_two_declared_versions_must_agree(tree: Path) -> None:
    """pyproject.toml and CITATION.cff both name a version. They are two files
    and one fact, so they are bound rather than trusted."""
    pyproject = tree / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8").replace(
            'version = "0.1.0"', 'version = "9.9.9"', 1
        ),
        encoding="utf-8",
    )
    failures = citation_check.problems(tree / "CITATION.cff", tree / "static" / "CNAME")
    assert any("9.9.9" in failure for failure in failures), failures


def test_record_rewrites_exactly_one_line(tree: Path) -> None:
    path = tree / "CITATION.cff"
    before = path.read_text(encoding="utf-8")
    assert fingerprint.record("sha256:" + "a" * 64, path) is True
    after = path.read_text(encoding="utf-8")
    changed = [
        (one, two)
        for one, two in zip(before.splitlines(), after.splitlines(), strict=True)
        if one != two
    ]
    assert len(changed) == 1
    assert "# Do NOT add a .zenodo.json" in after or "zenodo" in after.lower()


def test_record_is_idempotent(tree: Path) -> None:
    path = tree / "CITATION.cff"
    digest = fingerprint.fingerprint(tree)
    assert fingerprint.record(digest, path) is True
    assert fingerprint.record(digest, path) is False
```

The count-literal guard only walks `tools/`, so digit literals in a test file are free. Nothing below writes one into `tools/`.

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_fingerprint.py -v`
Expected: FAIL at collection, `ImportError: cannot import name 'fingerprint' from 'tools'`

- [ ] **Step 3: Write the fingerprint**

Create `tools/fingerprint.py`:

```python
"""A content fingerprint over everything a citation is a claim about.

`version` is a string a human types, and a string a human types is a string a
human forgets. This turns it into a checkable claim: the digest of the published
data is recorded beside the version in CITATION.cff, and tools/checks/citation.py
fails the moment the data changes and the version does not.

Deliberately the DATA, not the code. A template tweak or a CSS colour does not
change what the leaderboard reports, and a version bump on every whitespace fix
trains people to bump without reading, which is the failure this prevents.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import re
from collections.abc import Sequence
from pathlib import Path

from tools import citation

ROOT = Path(__file__).resolve().parent.parent

# Everything the leaderboard REPORTS. Expanded and sorted, so the digest depends
# on content and never on filesystem order.
CONTENT_GLOBS: tuple[str, ...] = (
    "data/registry/*.json",
    "data/baseline.json",
    "data/cells/**/*.json",
    "docs/sources/table8_baseline.csv",
)

PREFIX = "sha256:"

_RECORDED = re.compile(r"(?P<lead>value:\s*[\"']?)sha256:[0-9a-f]+")


def content_files(root: Path = ROOT) -> tuple[Path, ...]:
    """Every file the fingerprint covers, sorted and deduplicated."""
    found: set[Path] = set()
    for pattern in CONTENT_GLOBS:
        found.update(path for path in root.glob(pattern) if path.is_file())
    if not found:
        raise FileNotFoundError(f"no content matched {CONTENT_GLOBS} under {root}")
    return tuple(sorted(found))


def fingerprint(root: Path = ROOT) -> str:
    """SHA-256 over the published data.

    Both the relative path and the payload are length-prefixed. Without that, a
    rename that shifts a byte boundary can produce the same concatenated stream
    from a different set of files, and the digest would silently agree.
    """
    digest = hashlib.sha256()
    for path in content_files(root):
        name = path.relative_to(root).as_posix().encode("utf-8")
        payload = path.read_bytes()
        for chunk in (name, payload):
            digest.update(str(len(chunk)).encode("ascii"))
            digest.update(b"\0")
            digest.update(chunk)
    return PREFIX + digest.hexdigest()


def record(digest: str, path: Path) -> bool:
    """Write the digest into CITATION.cff. Returns True when it changed.

    A single-line substitution rather than a YAML round trip: dumping the file
    back through PyYAML would strip every comment in it, and the comments are
    what tell the next person not to add a .zenodo.json.
    """
    text = path.read_text(encoding="utf-8")
    if len(_RECORDED.findall(text)) != 1:
        raise ValueError(f"{path} must carry exactly one sha256 identifier")
    updated = _RECORDED.sub(lambda match: match.group("lead") + digest, text, count=1)
    if updated == text:
        return False
    path.write_text(updated, encoding="utf-8")
    return True


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Print the data fingerprint, or record it in CITATION.cff"
    )
    parser.add_argument("--write", action="store_true", help="record it")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)

    digest = fingerprint(args.root)
    if not args.write:
        print(digest)
        return 0

    path = args.root / "CITATION.cff"
    changed = record(digest, path)
    version = citation.load(path).leaderboard.version
    print(f"fingerprint: {digest} ({'updated' if changed else 'unchanged'})")
    print(f"ledger row:  | {version} | {dt.date.today().isoformat()} | minting | {digest} |")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
```

The ledger row printed by `--write` is what Task 11 pastes into `docs/RELEASES.md`, so the digest is never retyped by hand.

- [ ] **Step 4: Extend the check**

Add to `tools/checks/citation.py`: `import tomllib`, `from tools import fingerprint`, and this, appended to `problems()` before the return:

```python
    recorded = loaded.fingerprint
    computed = fingerprint.fingerprint(path.parent)
    if recorded is None:
        failures.append(
            f"{path.name} records no data fingerprint; run `make version`"
        )
    elif recorded != computed:
        failures.append(
            f"the recorded data fingerprint is {recorded} but the tree hashes to "
            f"{computed}. data/ changed and version "
            f"{loaded.leaderboard.version} did not. Bump `version` and "
            "`date-released` in CITATION.cff and pyproject.toml, then run "
            "`make version`"
        )

    packaged = _pyproject_version(path.parent)
    if packaged != loaded.leaderboard.version:
        failures.append(
            f"pyproject.toml declares version {packaged} and CITATION.cff "
            f"declares {loaded.leaderboard.version}; they are one fact"
        )
```

with:

```python
def _pyproject_version(root: Path) -> str:
    raw = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    return str(raw["project"]["version"])
```

`path.parent` is the repository root, which is what lets the whole check run against the temporary tree the tests build.

- [ ] **Step 5: Stamp it into every page**

In `build.py`, add:

```python
def site_context() -> dict[str, str]:
    """What every page says about which version of the data it is showing."""
    loaded = citation.load()
    digest = fingerprint.fingerprint()
    return {
        "name": loaded.leaderboard.title,
        "version": loaded.leaderboard.version or "",
        "released": loaded.released,
        "fingerprint": digest,
        "fingerprint_short": digest.removeprefix(fingerprint.PREFIX)[:12],
    }
```

and register it once, in `environment()`, rather than threading it through every `render()` call:

```python
    env.globals["site"] = site_context()
```

Then extend the existing footer in `templates/base.html`:

```jinja
<footer class="site-footer">
<p>Baseline values are the paper's Table 8. Source: <a href="https://arxiv.org/abs/2605.06952">arXiv:2605.06952</a>.</p>
<p class="site-version">
Version {{ site.version }}, released {{ site.released }}. Data fingerprint
<code>{{ site.fingerprint_short }}</code>.
<a href="{{ base_path }}cite/">How to cite this leaderboard</a>.
</p>
</footer>
```

The `/cite/` link is a dead link until Task 10 renders the page, and `tests/test_pages.py::test_every_internal_link_resolves` will say so. Run Tasks 9 and 10 back to back, or add the link in Task 10.

- [ ] **Step 6: Wire the entry point and the target**

In `pyproject.toml`, under `[project.scripts]`:

```toml
eda-fingerprint = "tools.fingerprint:main"
```

In the `Makefile`, add `version` to `.PHONY` and:

```make
# Recompute the data fingerprint and record it in CITATION.cff. Run this after
# any change under data/, then bump `version` and `date-released` yourself.
# `make check` fails until you do.
version:
	uv run eda-fingerprint --write
```

- [ ] **Step 7: Record the real fingerprint and run the gate**

```bash
uv sync --all-extras
make version
uv run pytest tests/test_fingerprint.py -v
make check
```

Expected: the all-zero placeholder is replaced, the tests pass, and `make check` is green.

- [ ] **Step 8: Prove it fails, by hand**

```bash
printf '\n' >> data/baseline.json
uv run eda-validate; echo "exit=$?"
git checkout data/baseline.json
```

Expected: `citation:` reports the fingerprint mismatch and names both digests, `exit=1`. A test asserting this is not enough on its own; this confirms nothing between the check and the exit code swallows it.

- [ ] **Step 9: Commit**

```bash
git add tools/fingerprint.py tools/checks/citation.py pyproject.toml Makefile build.py templates/base.html CITATION.cff tests/test_fingerprint.py
git commit -m "feat(citation): bind the version to a fingerprint of the published data"
```

---

### Task 10: The citation surface, rendered once and shown twice

A citation nobody can find is a citation nobody uses. `/cite/` is the page a reader lands on from the footer of every page and from the nav, and it shows BibTeX and APA for **both** works: this leaderboard, and the paper whose baseline it publishes.

Both blocks come from `citation.blocks()` through **one** partial, included by both `/cite/` and `/about/card/`. That is the structural version of "one source of truth": there is no second template to update, so the two pages cannot disagree.

No JavaScript. The blocks are selectable text in a `<pre>`, a copy button is a convenience rather than a requirement, and `/cite/` stays trivially inside the 88 KB budget and out of the a11y risk surface. JSON-LD and Highwire `citation_*` meta tags were considered and deliberately left out: they are a third rendering of the same fact, and nothing in the goal asks for machine harvesting yet.

**Files:**
- Create: `templates/partials/citation-block.html`, `templates/pages/cite.html`
- Modify: `build.py`, `templates/base.html`, `templates/pages/card.html`, `static/css/base.css`, `.pa11yci.json`
- Test: `tests/test_cite_page.py`

**Interfaces:**
- Consumes: `citation.blocks()`, `build.site_context()`.
- Produces: `dist/cite/index.html`, and the citation block inside `dist/about/card/index.html`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cite_page.py`:

```python
"""The citation surface: one page, one partial, two pages rendering it."""

from __future__ import annotations

import html
import re
from pathlib import Path

from tools import citation

BUDGET_BYTES = 88 * 1024


def _bibtex_blocks(markup: str) -> list[str]:
    return [
        html.unescape(match)
        for match in re.findall(
            r'<pre class="citation-bibtex"><code>(.*?)</code></pre>', markup, re.DOTALL
        )
    ]


def test_the_page_is_built(built_dist: Path) -> None:
    assert (built_dist / "cite" / "index.html").is_file()


def test_it_shows_both_works(built_dist: Path) -> None:
    """The leaderboard AND the paper. Showing only the paper is the gap this
    phase closed; showing only the leaderboard would drop the attribution the
    data is published under."""
    blocks = _bibtex_blocks((built_dist / "cite" / "index.html").read_text("utf-8"))
    assert len(blocks) == len(citation.blocks())
    joined = "\n".join(blocks)
    assert "@software{" in joined
    assert "@article{" in joined


def test_apa_appears_for_every_work(built_dist: Path) -> None:
    markup = (built_dist / "cite" / "index.html").read_text("utf-8")
    for block in citation.blocks():
        assert html.escape(block.apa) in markup or block.apa in markup


def test_the_version_and_the_date_are_on_the_page(built_dist: Path) -> None:
    loaded = citation.load()
    markup = (built_dist / "cite" / "index.html").read_text("utf-8")
    assert loaded.leaderboard.version is not None
    assert loaded.leaderboard.version in markup
    assert loaded.released in markup
    assert loaded.fingerprint is not None
    assert loaded.fingerprint.split(":")[-1][:12] in markup


def test_the_card_shows_the_same_bytes(built_dist: Path) -> None:
    """One partial, two pages. If these ever differ, someone has written a
    second citation block and the reader now has two answers."""
    page = _bibtex_blocks((built_dist / "cite" / "index.html").read_text("utf-8"))
    card = _bibtex_blocks(
        (built_dist / "about" / "card" / "index.html").read_text("utf-8")
    )
    assert page == card
    assert page


def test_every_page_links_to_it(built_dist: Path) -> None:
    """The footer stamp is on every page, so the citation is never more than one
    click away from whatever the reader is looking at."""
    for page in sorted(built_dist.rglob("index.html")):
        assert "/cite/" in page.read_text(encoding="utf-8"), page


def test_the_doi_is_rendered_as_a_resolvable_link(built_dist: Path) -> None:
    """Before Task 13 there is no DOI and the block simply omits it. After it,
    the link must be the doi.org form, which is the one that keeps resolving
    when the record moves."""
    markup = (built_dist / "cite" / "index.html").read_text("utf-8")
    for block in citation.blocks():
        if block.doi_url:
            assert f'href="{block.doi_url}"' in markup
            assert block.doi_url.startswith("https://doi.org/")


def test_it_is_within_budget(built_dist: Path) -> None:
    size = (built_dist / "cite" / "index.html").stat().st_size
    print(f"cite/index.html: {size / 1024:.1f} KiB")
    assert size <= BUDGET_BYTES


def test_no_em_dash_reaches_the_page(built_dist: Path) -> None:
    assert "—" not in (built_dist / "cite" / "index.html").read_text("utf-8")
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_cite_page.py -v`
Expected: FAIL, `FileNotFoundError` on `cite/index.html`

- [ ] **Step 3: Write the partial**

Create `templates/partials/citation-block.html`. Loops and one conditional, nothing else:

```jinja
{# The one citation block. /cite/ and /about/card/ both include THIS, so the
   two pages cannot disagree. Everything here is computed in
   tools/citation.py. #}
{% for block in citation_blocks %}
<section class="citation" id="cite-{{ block.key }}">
<h3>{{ block.scope }}</h3>
<p class="citation-apa">{{ block.apa }}</p>
{% if block.doi_url %}
<p class="citation-doi"><a href="{{ block.doi_url }}">{{ block.doi_url }}</a></p>
{% endif %}
<pre class="citation-bibtex"><code>{{ block.bibtex }}</code></pre>
</section>
{% endfor %}
```

- [ ] **Step 4: Write the page**

Create `templates/pages/cite.html`:

```jinja
{% extends "base.html" %}
{% block title %}How to cite the EDA-Schema leaderboard{% endblock %}
{% block content %}
<h2>How to cite</h2>
<p>
This page describes version {{ site.version }}, released {{ site.released }}.
The data it publishes has fingerprint <code>{{ site.fingerprint }}</code>.
</p>
<p>
The site changes as submissions arrive; a citation must not. Cite a released
version: each one is archived under its own DOI, and the DOI below always
resolves to the most recent. The version to DOI ledger is in
<a href="{{ releases_url }}">RELEASES.md</a>.
</p>
{% include "partials/citation-block.html" %}
{% endblock %}
```

In `build.py`, render it beside the other pages, and pass the same context into the card:

```python
def _citation_context() -> dict[str, object]:
    loaded = citation.load()
    return {
        "citation_blocks": citation.blocks(loaded),
        "releases_url": f"{loaded.repository_code}/blob/main/docs/RELEASES.md",
    }
```

`templates/pages/card.html` gains `{% include "partials/citation-block.html" %}` inside a `<section id="card-citation">`, and the card's render call is given `**_citation_context()`.

- [ ] **Step 5: Nav, styles, a11y**

Add `/cite/` to the nav in `templates/base.html`, beside the Phase 8 entries. Add `/cite/` to `.pa11yci.json`. In `static/css/base.css`, style `.citation-bibtex` with `overflow-x: auto` so a long DOI line scrolls rather than widening the page, and use only variables already in the contract, or Task 1's check reports a new one.

- [ ] **Step 6: Run everything**

```bash
uv run pytest tests/test_cite_page.py tests/test_pages.py -v -s
make check
lychee --no-progress --accept 200,206,429 dist/
```

Expected: all pass, and `lychee` reports 0 errors. Before Task 13 there is no DOI, so there is no `doi.org` link for `lychee` to resolve; after Task 13 there is, and it must resolve.

- [ ] **Step 7: Read it as a stranger would**

```bash
make build && uv run python -m http.server -d dist 8080
```

Open `http://localhost:8080/cite/`. A human step. The question is not "does it render", it is: **if you had used this leaderboard in a paper, could you cite it correctly from this page without asking anyone?** If the answer needs a follow-up question, the page is not finished.

- [ ] **Step 8: Commit**

```bash
git add templates/partials/citation-block.html templates/pages/cite.html templates/pages/card.html templates/base.html build.py static/css/base.css .pa11yci.json tests/test_cite_page.py
git commit -m "feat(cite): render one citation block on /cite/ and on the card"
```

---

### Task 11: What a release is, and the gate in front of it

A citable snapshot must be **immutable** while the site keeps changing. Those two requirements are in direct tension and the resolution is the release: `main` and the deployed site move continuously, a tag does not, and it is the tag that carries a DOI.

Everything this task builds exists because a mistake in a release cannot be corrected, only superseded.

**Files:**
- Create: `docs/RELEASES.md`, `tools/releases.py`, `tools/release_check.py`, `.github/workflows/release.yml`
- Modify: `tools/checks/citation.py`, `pyproject.toml`
- Test: `tests/test_release.py`

**Interfaces:**
- Consumes: `docs/RELEASES.md`, `tools.citation`, `tools.fingerprint`.
- Produces:
  - `releases.LEDGER_PATH: Path`, `releases.MINTING: str`, `releases.Release`
  - `releases.load_ledger(path: Path = LEDGER_PATH) -> tuple[Release, ...]`
  - `releases.ledger_problems(rows: tuple[Release, ...]) -> list[str]`
  - `release_check.problems(tag: str, root: Path = citation.ROOT) -> list[str]`
  - `release_check.main(argv: Sequence[str] | None = None) -> int`, the `eda-release-check` console script

- [ ] **Step 1: Write the failing tests**

Create `tests/test_release.py`:

```python
"""The release ledger, and the gate between a tag and a DOI."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools import citation, fingerprint, release_check, releases

LEDGER_HEADER = """# Releases

| Version | Date | Version DOI | Data fingerprint |
|---|---|---|---|
"""


def _ledger(tmp_path: Path, *rows: str) -> Path:
    path = tmp_path / "RELEASES.md"
    path.write_text(LEDGER_HEADER + "".join(rows), encoding="utf-8")
    return path


def test_the_repository_ledger_parses() -> None:
    """Not "does not crash": the file must produce rows."""
    assert releases.load_ledger() or not releases.LEDGER_PATH.is_file()


def test_a_row_parses_into_its_four_fields(tmp_path: Path) -> None:
    digest = "sha256:" + "ab" * 32
    path = _ledger(tmp_path, f"| 0.1.0 | 2026-08-20 | 10.5281/zenodo.1234567 | {digest} |\n")
    row = releases.load_ledger(path)[0]
    assert row.version == "0.1.0"
    assert row.date == "2026-08-20"
    assert row.doi == "10.5281/zenodo.1234567"
    assert row.fingerprint == digest


def test_the_separator_row_is_not_a_release(tmp_path: Path) -> None:
    assert releases.load_ledger(_ledger(tmp_path)) == ()


def test_the_bootstrap_row_reads_as_no_doi(tmp_path: Path) -> None:
    """Zenodo issues the DOI FROM the release, so the first archived snapshot is
    always DOI-less. That is a bootstrap, not a habit."""
    digest = "sha256:" + "cd" * 32
    path = _ledger(tmp_path, f"| 0.1.0 | 2026-08-20 | minting | {digest} |\n")
    assert releases.load_ledger(path)[0].doi is None


def test_only_one_release_may_ever_be_minting(tmp_path: Path) -> None:
    """The rule that keeps the exception from becoming the practice."""
    digest = "sha256:" + "ef" * 32
    path = _ledger(
        tmp_path,
        f"| 0.1.0 | 2026-08-20 | minting | {digest} |\n",
        f"| 0.1.1 | 2026-08-21 | minting | {digest} |\n",
    )
    problems = releases.ledger_problems(releases.load_ledger(path))
    assert any("minting" in problem for problem in problems), problems


def test_dates_must_ascend(tmp_path: Path) -> None:
    digest = "sha256:" + "01" * 32
    path = _ledger(
        tmp_path,
        f"| 0.1.0 | 2026-08-20 | 10.5281/zenodo.1 | {digest} |\n",
        f"| 0.1.1 | 2026-08-19 | 10.5281/zenodo.2 | {digest} |\n",
    )
    assert releases.ledger_problems(releases.load_ledger(path))


def test_a_version_appears_once(tmp_path: Path) -> None:
    digest = "sha256:" + "02" * 32
    path = _ledger(
        tmp_path,
        f"| 0.1.0 | 2026-08-20 | 10.5281/zenodo.1 | {digest} |\n",
        f"| 0.1.0 | 2026-08-21 | 10.5281/zenodo.2 | {digest} |\n",
    )
    assert releases.ledger_problems(releases.load_ledger(path))


def test_a_mismatched_tag_is_refused() -> None:
    """The failure this gate exists for: v0.2.0 pushed against a CITATION.cff
    that still says 0.1.0 would archive a snapshot whose own metadata contradicts
    its DOI, permanently."""
    version = citation.load().leaderboard.version
    problems = release_check.problems("v9.9.9")
    assert any("9.9.9" in problem and version in problem for problem in problems)


def test_the_current_tag_would_pass_or_says_exactly_why() -> None:
    """Run against the real tree. Before the ledger has a row this reports the
    missing row and nothing else, which is the correct state mid-phase."""
    version = citation.load().leaderboard.version
    problems = release_check.problems(f"v{version}")
    assert all("RELEASES.md" in problem for problem in problems), problems


def test_the_workflow_adds_no_secret() -> None:
    """Zenodo's integration is a webhook it installs itself, and this job uses
    the token GitHub mints per run. Nothing here needs a stored credential, and
    a plan that quietly introduced one would be worth catching."""
    workflow = Path(".github/workflows/release.yml").read_text(encoding="utf-8")
    assert "secrets." not in workflow
    assert "github.token" in workflow


def test_the_fingerprint_in_the_ledger_is_the_one_that_shipped() -> None:
    rows = releases.load_ledger()
    for row in rows:
        if row.version == citation.load().leaderboard.version:
            assert row.fingerprint == fingerprint.fingerprint()
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_release.py -v`
Expected: FAIL at collection, `ImportError: cannot import name 'releases' from 'tools'`

- [ ] **Step 3: Write the ledger parser**

Create `tools/releases.py`:

```python
"""The version to DOI ledger in docs/RELEASES.md.

Markdown, because the first thing a reader wants when they see a DOI is which
numbers it describes, and they will be looking at GitHub when they want it.
Parsed rather than trusted: the release gate refuses a tag with no row here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER_PATH = ROOT / "docs" / "RELEASES.md"

# The one release that mints the DOI cannot contain it: Zenodo issues the DOI
# from the release, so the first archived snapshot is always DOI-less. Exactly
# one row may ever claim this, which is what stops a bootstrap becoming a habit.
MINTING = "minting"

_ROW = re.compile(
    r"^\|\s*(?P<version>[0-9][^|]*?)\s*"
    r"\|\s*(?P<date>\d{4}-\d{2}-\d{2})\s*"
    r"\|\s*(?P<doi>[^|]+?)\s*"
    r"\|\s*(?P<fingerprint>sha256:[0-9a-f]+)\s*\|\s*$",
    re.MULTILINE,
)

_DOI = re.compile(r"^10\.\d{4,9}/\S+$")


@dataclass(frozen=True, slots=True)
class Release:
    version: str
    date: str
    doi: str | None  # None while this release is the one minting it
    fingerprint: str


def load_ledger(path: Path = LEDGER_PATH) -> tuple[Release, ...]:
    if not path.is_file():
        return ()
    return tuple(
        Release(
            version=match.group("version"),
            date=match.group("date"),
            doi=None if match.group("doi") == MINTING else match.group("doi"),
            fingerprint=match.group("fingerprint"),
        )
        for match in _ROW.finditer(path.read_text(encoding="utf-8"))
    )


def ledger_problems(rows: tuple[Release, ...]) -> list[str]:
    problems: list[str] = []

    bootstraps = [row for row in rows if row.doi is None]
    if len(bootstraps) > 1:
        named = ", ".join(row.version for row in bootstraps)
        problems.append(
            f"{named} all claim to be minting the DOI; only the first release can be"
        )

    versions = [row.version for row in rows]
    for version in sorted(set(versions)):
        if versions.count(version) > 1:
            problems.append(f"version {version} appears more than once")

    dates = [row.date for row in rows]
    if dates != sorted(dates):
        problems.append("release dates are not in ascending order")

    for row in rows:
        if row.doi is not None and _DOI.match(row.doi) is None:
            problems.append(f"{row.version}: {row.doi} is not a DOI")

    return problems
```

- [ ] **Step 4: Write the gate**

Create `tools/release_check.py`:

```python
"""The gate between a tag and a DOI.

Runs on a tag push, before anything is published. Everything it checks is
something that, once Zenodo has archived it, cannot be corrected without
superseding the record.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from tools import citation, fingerprint, releases
from tools.checks import citation as citation_check


def problems(tag: str, root: Path = citation.ROOT) -> list[str]:
    path = root / "CITATION.cff"
    found = citation_check.problems(path, root / "static" / "CNAME")

    try:
        loaded = citation.load(path)
    except citation.CitationError:
        return found or [f"{path} could not be loaded"]

    version = loaded.leaderboard.version or ""
    if tag != f"v{version}":
        found.append(
            f"tag {tag} does not match CITATION.cff version {version}; expected v{version}"
        )

    rows = releases.load_ledger(root / "docs" / "RELEASES.md")
    found.extend(releases.ledger_problems(rows))

    row = next((entry for entry in rows if entry.version == version), None)
    if row is None:
        found.append(f"docs/RELEASES.md has no row for version {version}")
        return found

    if row.fingerprint != fingerprint.fingerprint(root):
        found.append(
            f"the ledger row for {version} records {row.fingerprint}, "
            "which is not what this tree hashes to"
        )
    if row.doi is None and any(entry.doi for entry in rows):
        found.append(
            f"{version} claims to be minting the DOI, but an earlier release has one"
        )
    if row.doi is not None and loaded.leaderboard.doi is None:
        found.append(
            f"the ledger gives {version} a DOI but CITATION.cff declares none"
        )
    return found


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify a tag against CITATION.cff and the release ledger"
    )
    parser.add_argument("--tag", required=True)
    args = parser.parse_args(argv)

    found = problems(args.tag)
    for line in found:
        print(f"release: {line}")
    print(f"release: {args.tag}, {len(found)} problems")
    return 1 if found else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
```

Add to `[project.scripts]`:

```toml
eda-release-check = "tools.release_check:main"
```

`eda-release-check` is a real entry point for the same reason `eda-validate` is: `python -m tools.release_check` imports `tools.checks` a second time under a different module identity, and the `CHECKS` registry it reads would not be the one the checks registered into.

- [ ] **Step 5: Write the release contract**

Create `docs/RELEASES.md`:

```markdown
# Releases

The site changes as submissions arrive. A citation must not. This file is where
those two facts are reconciled.

## What a tagged release is

A tag `vX.Y.Z` is an immutable snapshot of the repository. Zenodo archives the
**source tree at that tag**, publishes it as a record, and issues a DOI for it.
The record contains `CITATION.cff`, `data/`, `docs/sources/`, the tooling and
the templates: everything needed to rebuild the site the DOI describes with
`make build`. Rendered HTML is attached to the GitHub release as
`site-vX.Y.Z.tar.gz` for convenience, and is not what Zenodo archives.

Nothing about a published record can be edited into correctness afterwards. A
mistake is fixed by releasing again, never by amending. That is why
`.github/workflows/release.yml` refuses a tag whose version, fingerprint or
ledger row disagrees with the rest of the repository.

## What changes and what does not

| | Changes | Frozen |
|---|---|---|
| The deployed site | on every merge to `main` | never |
| A tagged release | never | at the tag |
| The concept DOI | resolves to the newest version | the identifier itself |
| A version DOI | never | at publication |

Cite the **concept DOI** to mean the leaderboard, and a **version DOI** to mean
the numbers you actually read.

## When to release

Any change to the fingerprinted content is a release: a new ingest, a corrected
baseline, a registry change. `make check` will not go green after such a change
until `version` and `date-released` are bumped in `CITATION.cff` and
`pyproject.toml` and `make version` has recorded the new fingerprint, so this
is enforced rather than remembered.

## The ledger

`CITATION.cff` carries the concept DOI, which is the one that always resolves to
the newest version. It has nowhere to record per-version DOIs, so they live here.

| Version | Date | Version DOI | Data fingerprint |
|---|---|---|---|
```

Leave the table empty. Task 13 adds the first row, using the line `make version` prints.

- [ ] **Step 6: Write the workflow**

Create `.github/workflows/release.yml`:

```yaml
name: release

# A tag is the only thing that produces a citable artifact, and every mistake it
# carries becomes permanent the moment Zenodo archives it. This job is the last
# place any of them can still be caught.
on:
  push:
    tags:
      - "v*"

permissions:
  contents: write # only to attach the built site to the release

jobs:
  citable:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          persist-credentials: false

      - uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true

      - run: uv sync --all-extras

      - name: the tag, the version, the fingerprint and the ledger must agree
        run: uv run eda-release-check --tag "${GITHUB_REF_NAME}"

      - name: build the site this DOI will describe
        env:
          # Copy this expression from deploy.yml rather than inventing a second
          # one. Two spellings of the base path is how an archived site ends up
          # with links that resolve nowhere.
          SITE_BASE: /${{ github.event.repository.name }}/
        run: uv run python build.py

      - name: archive it
        run: tar -czf "site-${GITHUB_REF_NAME}.tar.gz" -C dist .

      - name: attach it to the release
        env:
          # The token GitHub mints for this run. NOT a stored secret: this
          # workflow adds none, and Zenodo needs none either, because its
          # integration is a webhook Zenodo installs itself.
          GH_TOKEN: ${{ github.token }}
        run: gh release upload "${GITHUB_REF_NAME}" "site-${GITHUB_REF_NAME}.tar.gz" --clobber
```

If a custom domain lands in Task 12, `SITE_BASE` becomes `/` in both this workflow and `deploy.yml`, together.

- [ ] **Step 7: Run everything**

```bash
uv run pytest tests/test_release.py -v
uv run eda-release-check --tag "v$(uv run python -c 'from tools import citation; print(citation.load().leaderboard.version)')"; echo "exit=$?"
make check
```

Expected: the tests pass; `eda-release-check` exits 1 naming only the missing `docs/RELEASES.md` row, which Task 13 adds; `make check` is green.

- [ ] **Step 8: Commit**

```bash
git add docs/RELEASES.md tools/releases.py tools/release_check.py .github/workflows/release.yml pyproject.toml tests/test_release.py
git commit -m "feat(release): gate a tag on its version, fingerprint and ledger row"
```

---

### Task 12: Transfer, re-apply the guardrails, and prove they survived

Protection that silently did not survive a transfer is worse than none, because you will believe it is there.

**Do not start this until Tasks 1 to 11 are merged.** Every command below is irreversible or touches live state.

**This task comes before any DOI exists, deliberately.** See the citation ordering rule above. Step 8 repoints `CITATION.cff` at the new home, and `tools/checks/citation.py` keeps `make check` red until it does.

**Files:**
- Modify: `.github/CODEOWNERS`
- Modify: `README.md`, `docs/` (any absolute URL), `CITATION.cff`
- Create: `static/CNAME` (only if a custom domain is agreed)
- Modify (experiments repo): `.github/workflows/notify-site.yml`

**Interfaces:**
- Consumes: the current protection JSON, the current check-run names.
- Produces: two repositories under `drexel-ice` with protection, CODEOWNERS and Pages verified by a negative test.

- [ ] **Step 1: Snapshot everything first**

```bash
gh api repos/JiwaniZakir/eda-schema-leaderboard/branches/main/protection > /tmp/protection-site-before.json
gh api repos/JiwaniZakir/eda-schema-experiments/branches/main/protection > /tmp/protection-experiments-before.json
gh api repos/JiwaniZakir/eda-schema-leaderboard/pages > /tmp/pages-before.json
gh secret list -R JiwaniZakir/eda-schema-leaderboard
gh secret list -R JiwaniZakir/eda-schema-experiments
gh variable list -R JiwaniZakir/eda-schema-leaderboard
```

Keep these. They are the diff target for Step 6.

- [ ] **Step 2: Check the destination org will run these workflows**

An organisation can restrict which actions may run. Every workflow here uses third-party actions (`astral-sh/setup-uv`, `lycheeverse/lychee-action`, `github/codeql-action`, and possibly `anthropics/claude-code-action`). If `drexel-ice` allows only GitHub-authored actions, CI goes red on arrival and the negative test in Step 9 becomes unreadable.

```bash
gh api orgs/drexel-ice/actions/permissions
gh api orgs/drexel-ice/actions/permissions/selected-actions 2>/dev/null || echo "no selected-actions policy"
```

Expected: `allowed_actions: all`, or a `patterns_allowed` list that already covers the above. Resolve with an org owner **before** transferring.

- [ ] **Step 3: Confirm there is a second human**

Step 6 sets `required_approving_review_count: 1` and `enforce_admins: true`. GitHub does not let an author approve their own pull request, so from that moment `main` is unmergeable by one person, admin or not. That is the intent, and it is only safe once someone else has write access.

```bash
gh api orgs/drexel-ice/members --jq '.[].login'
```

Expected: at least one login besides the maintainer, who will be granted write on both repositories.

- [ ] **Step 4: Transfer both repositories**

`gh repo transfer` does not exist in gh 2.83.2 despite `PLAN.md` quoting it. Use the API:

```bash
gh api -X POST repos/JiwaniZakir/eda-schema-leaderboard/transfer -f new_owner=drexel-ice
gh api -X POST repos/JiwaniZakir/eda-schema-experiments/transfer -f new_owner=drexel-ice
gh repo view drexel-ice/eda-schema-leaderboard --json name,owner,visibility
```

Then repoint the local clone:

```bash
git remote set-url origin https://github.com/drexel-ice/eda-schema-leaderboard.git
git remote -v
```

- [ ] **Step 5: Re-derive the required checks rather than retyping them**

The pre-transfer list is stale: it names `analyze (python)` only, and CodeQL now also emits `analyze (javascript-typescript)` because `static/js/` exists. Read the names off a real run on `main`:

```bash
gh api repos/drexel-ice/eda-schema-leaderboard/commits/main/check-runs \
  --jq '[.check_runs[].name] | unique | sort'
```

Expected something like:

```json
["analyze (javascript-typescript)","analyze (python)","build","lint","pa11y (drexel)","pa11y (neutral)","size","test","typecheck","validate"]
```

Requiring a context that never reports blocks every merge forever, and *not* requiring one that matters is a guard that only looks present. Pick the list deliberately: every `ci` job, `size`, both `analyze` legs. `pa11y` is path-filtered and will not report on most pull requests, so it must **not** be required.

- [ ] **Step 6: Re-apply protection, with the review requirement Phase 0 deferred**

```bash
gh api -X PUT repos/drexel-ice/eda-schema-leaderboard/branches/main/protection \
  -H "Accept: application/vnd.github+json" --input - <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "lint",
      "typecheck",
      "validate",
      "test",
      "build",
      "size",
      "analyze (python)",
      "analyze (javascript-typescript)"
    ]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": true,
    "required_approving_review_count": 1,
    "require_last_push_approval": true
  },
  "restrictions": null,
  "required_conversation_resolution": true,
  "allow_force_pushes": false,
  "allow_deletions": false
}
JSON
```

`restrictions` must be present and may be `null`; omitting it is a 422. Repeat for the experiments repo with its own context list (`size`, plus `validate-submission` once it reports).

Verify against the snapshot:

```bash
gh api repos/drexel-ice/eda-schema-leaderboard/branches/main/protection \
  --jq '{contexts:.required_status_checks.contexts,
         reviews:.required_pull_request_reviews.required_approving_review_count,
         codeowners:.required_pull_request_reviews.require_code_owner_reviews,
         admins:.enforce_admins.enabled,
         force:.allow_force_pushes.enabled}'
```

Expected: the full context list, `1`, `true`, `true`, `false`.

Do **not** verify by pushing to `main` to see it bounce. `enforce_admins` is on, the push would be rejected, and the project's rule is that nothing pushes to a default branch. The API assertion above plus the negative test in Step 9 is the verification.

- [ ] **Step 7: Real handles in CODEOWNERS, verified to resolve**

A handle GitHub cannot resolve makes the entire rule inert: no warning, no requested review. Verify each before committing it.

```bash
gh api users/PRATIK_HANDLE --jq .login
gh api users/SAVIDIS_HANDLE --jq .login
```

Then replace the placeholder block in `.github/CODEOWNERS`:

```
* @JiwaniZakir

/submissions/                   @PRATIK_HANDLE
/docs/CARD.yaml                 @SAVIDIS_HANDLE
/docs/SUBMISSION.md             @SAVIDIS_HANDLE

# These need a second human on every change, because they are what stops
# arbitrary code execution reaching the runner.
/.github/                       @JiwaniZakir @SECOND_REVIEWER
/tools/checks/                  @JiwaniZakir @SECOND_REVIEWER
/tests/test_security.py         @JiwaniZakir @SECOND_REVIEWER
```

`PLAN.md` says `docs/CARD.md`; Phase 8 ships `docs/CARD.yaml`. Own the file that exists.

Ask GitHub whether it parsed:

```bash
gh api repos/drexel-ice/eda-schema-leaderboard/codeowners/errors --jq '.errors'
```

Expected: `[]`. Any entry here means that line is doing nothing.

- [ ] **Step 8: Pages, the URL, and the CNAME**

The published URL becomes `https://drexel-ice.github.io/eda-schema-leaderboard/`. Relative links survive because the path prefix is unchanged; absolute URLs in `README.md`, the card and any citation do not.

```bash
gh api repos/drexel-ice/eda-schema-leaderboard/pages
grep -rn "jiwanizakir.github.io" --include='*.md' --include='*.py' --include='*.html' --include='*.yml' .
curl -sI https://jiwanizakir.github.io/eda-schema-leaderboard/ | head -1
```

Do not assume the old Pages URL redirects. Check it and, if it does not, say so wherever the old link was published.

If a custom domain is agreed (for example `eda-schema.ice.drexel.edu`), do all three, because each covers a different failure:

```bash
# 1. DNS, by whoever runs the zone
dig +short eda-schema.ice.drexel.edu CNAME     # expect drexel-ice.github.io.

# 2. the repository setting
gh api -X PUT repos/drexel-ice/eda-schema-leaderboard/pages \
  -f cname=eda-schema.ice.drexel.edu -F https_enforced=true

# 3. a file in the artifact, so a rebuild cannot drop it
printf 'eda-schema.ice.drexel.edu\n' > static/CNAME
```

and have `build.py` copy `static/CNAME` to `dist/CNAME`. Then:

```bash
curl -sI https://eda-schema.ice.drexel.edu/ | head -1     # expect 200, over HTTPS
```

If no domain is agreed, record that in `PLAN.md` and keep the `github.io` URL. An unresolvable CNAME takes the site down entirely, so a half-configured custom domain is worse than none.

Then repoint the citation, which by now is failing the gate on purpose:

```bash
uv run eda-validate; echo "exit=$?"
```

Expected: `citation: url is https://jiwanizakir.github.io/... but repository-code and static/CNAME say the site is served from ...`, `exit=1`. That is the trip-wire from Task 8 doing its job. Fix both lines in `CITATION.cff`:

```yaml
url: https://drexel-ice.github.io/eda-schema-leaderboard/
repository-code: https://github.com/drexel-ice/eda-schema-leaderboard
```

or, if a custom domain was agreed, `url: https://eda-schema.ice.drexel.edu/` with `static/CNAME` carrying the same host. Then:

```bash
uv run eda-validate && uv run pytest tests/test_citation.py tests/test_cite_page.py -v
curl -sI "$(uv run python -c 'from tools import citation; print(citation.load().leaderboard.url)')" | head -1
```

Expected: 0 failures, tests green, and `HTTP/2 200` from the URL the citation now names. **The site must answer 200 at this URL before Task 13 mints anything.** A DOI is permanent and its archived snapshot carries whatever this file said at the time.

- [ ] **Step 9: Re-run the Phase 0 negative test against the transferred repo**

Three deliberate defects, which must fail **three independent jobs**. They are separate jobs in `ci.yml` precisely so that one cannot mask another.

```bash
git checkout -b test/ci-negative

# 1. a lint error: an unused import is F401 under the configured rule set,
#    and the missing spaces also fail `ruff format --check`.
printf 'import os\nx=1\n' > tools/_negative.py

# 2. a validate failure: the IHP130 to IPH130 typo, which the registry CSV
#    cross-check is built to reject. Proven by tests/test_mutations.py.
uv run python - <<'PY'
import json, pathlib
p = pathlib.Path("data/registry/pdks.json")
rows = json.loads(p.read_text())
for r in rows:
    if r["id"] == "ihp130":
        r["table8_label"] = "IPH130"
p.write_text(json.dumps(rows, indent=2) + "\n")
PY

# 3. an over-cap binary. Random bytes, so it cannot compress under the limit.
mkdir -p tests/fixtures
dd if=/dev/urandom of=tests/fixtures/negative-2mb.bin bs=1024 count=2048

git add tools/_negative.py data/registry/pdks.json tests/fixtures/negative-2mb.bin
git commit -m "test: ci negative test, must fail lint, validate and size"
git push -u origin test/ci-negative
gh pr create --title "ci: negative test, must fail" \
  --body "Deliberate lint error, schema violation and 2 MB binary. lint, validate and size must each report failure independently. Close without merging."
gh pr checks --watch
```

Then assert, rather than reading the web page:

```bash
gh pr checks --json name,state --jq '.[] | select(.name | IN("lint","validate","size")) | [.name, .state] | @tsv'
```

Expected: three rows, every state `FAILURE`. `test` will also fail, which is fine and not what is being proven. **If any of the three passes, that guard is decorative and this phase is not done.**

Clean up:

```bash
gh pr close --delete-branch
git checkout main && git pull
git branch -D test/ci-negative
```

Confirm the working tree is clean and `data/registry/pdks.json` is back to `IHP130`.

- [ ] **Step 10: Repoint the experiments repo's dispatch**

`notify-site.yml` POSTs to a hardcoded `repos/JiwaniZakir/eda-schema-leaderboard/dispatches`. GitHub redirects a transferred repository's API, but `curl -X POST` does not follow redirects by default, so the dispatch would 301 into silence and `curl -sSf` may well still exit 0. Change the URL, do not rely on the redirect.

Also, `SITE_DISPATCH_TOKEN` is a fine-grained PAT bound to a repository under a specific resource owner. After transfer, the owner is `drexel-ice` and the old token no longer grants anything. It must be re-issued by an org member and set again:

```bash
gh secret set SITE_DISPATCH_TOKEN -R drexel-ice/eda-schema-experiments
```

Then re-run Task 6 Step 4 end to end against the new owner and confirm a `repository_dispatch` deploy run appears.

- [ ] **Step 11: Re-verify protection on the experiments repo too**

It transferred with `required_status_checks.contexts: ["size"]` and no review requirement. Apply the same treatment as Step 6, sized to its own check names.

- [ ] **Step 12: Commit and open the final PR**

```bash
git checkout -b phase-9/transfer-followups
git add .github/CODEOWNERS README.md CITATION.cff
git commit -m "chore(transfer): real CODEOWNERS handles and drexel-ice URLs"
git push -u origin phase-9/transfer-followups
gh pr create --title "Phase 9: transfer follow-ups" --body "CODEOWNERS handles verified against the API, absolute URLs updated for the new owner. Branch protection, Pages and the negative test are verified live; evidence in the phase gate checklist."
```

This PR is the first one that needs someone else's approval. That it cannot be self-merged is the proof that Step 6 worked.

---

### Task 13: Mint the DOI and cut the first citable release

**Last task in the phase, and the only one that touches Zenodo.** Do not start it until Task 12 is complete and the site answers 200 at its final URL. The reasoning is in the citation ordering rule above; the short version is that a DOI is permanent and its archived snapshot carries whatever `CITATION.cff` said at the time.

**Most of this cannot be automated, and that is not a limitation to work around.** Zenodo's GitHub integration is enabled by a human logging into Zenodo with GitHub OAuth and flipping a switch. The alternative is Zenodo's REST API with a long-lived personal token, which would mean storing a credential this project has a standing rule against. The webhook path needs no repository secret at all, so the manual step is also the safer one. Steps 1 to 4 and 7 are human. Steps 5, 6, 8 and 9 are commands.

**Files:**
- Modify: `CITATION.cff`, `docs/RELEASES.md`
- Live state: one Zenodo account authorization, one GitHub release, one Zenodo record.

**Interfaces:**
- Consumes: `tools/release_check.py`, `.github/workflows/release.yml`, a Zenodo login.
- Produces: a concept DOI recorded in `CITATION.cff`, a version DOI recorded in `docs/RELEASES.md`, and a `/cite/` page that shows both.

- [ ] **Step 1: Decide whose Zenodo account owns the record, before touching anything**

**This decision is permanent in practice.** The Zenodo record belongs to the account that authorized the integration. If that is a personal account, the lab's citable artifact is owned by an individual, and moving it later needs Zenodo support rather than a setting. Choose deliberately:

- an account the lab controls, or
- a personal account **plus** the record added to a Zenodo Community owned by the lab, so the affiliation is visible and the community can curate it.

Record the verdict, with the date, in `PLAN.md`'s open decisions table before continuing. This is a decision the maintainer cannot make alone.

- [ ] **Step 2: Authorize Zenodo against the transferred repository**

Human, in a browser:

1. Sign in at `https://zenodo.org` with **Log in with GitHub**, using the account decided in Step 1.
2. Open `https://zenodo.org/account/settings/github/`.
3. Find `drexel-ice/eda-schema-leaderboard` in the repository list and switch it **on**. Zenodo installs the webhook itself; no secret is added to the repository.
4. If the repository is not listed, press **Sync now**. If it still is not, an owner of the `drexel-ice` organisation has to grant the Zenodo OAuth application access under the organisation's third-party application settings. An organisation-owned repository is invisible to Zenodo until then, and there is no error message that says so.

Do **not** rely on any earlier authorization surviving the transfer. `zenodo/zenodo#1653` is the open question of whether a record can follow a repository to a new owner, and this is not the place to find out.

- [ ] **Step 3: Confirm what Zenodo will read**

Zenodo populates the deposition from `CITATION.cff`. Read it once more as the metadata it is about to become: title, authors, licence, version, `date-released`, abstract, keywords, and the `references` entry for the paper. This is the last moment any of it is cheap to change.

- [ ] **Step 4: Add the ledger row and tag**

```bash
git checkout -b phase-9/first-citable-release
make version                       # prints the ledger row, with today's date
```

Paste the printed row into `docs/RELEASES.md` under the header. The DOI column reads `minting` for this release and only this release: Zenodo issues the DOI **from** the release, so the first archived snapshot cannot contain it. `releases.ledger_problems` refuses a second row that claims the same.

```bash
uv run eda-release-check --tag "v0.1.0"; echo "exit=$?"
```

Expected: `release: v0.1.0, 0 problems`, `exit=0`. If it names a problem, fix it now: after the tag, fixing it costs another version.

Open the PR, get it approved and merged. `main` is protected now, so this is a real review.

- [ ] **Step 5: Cut the release**

```bash
git checkout main && git pull
gh release create v0.1.0 \
  --title "v0.1.0" \
  --notes "First citable release. Publishes the EDA-Schema-V2 Table 8 baseline across the full grid. See docs/RELEASES.md for what a release contains and CITATION.cff for how to cite it."
gh run watch
```

Expected: the `release` workflow concludes `success`, having run `eda-release-check`, built the site and attached `site-v0.1.0.tar.gz`.

- [ ] **Step 6: Confirm Zenodo received it**

```bash
gh api repos/drexel-ice/eda-schema-leaderboard/hooks --jq '.[] | {name, config: .config.url, active}'
```

Expected: a webhook whose URL is a `zenodo.org` endpoint, `active: true`. Then open `https://zenodo.org/account/settings/github/` and check the repository now lists a published record. It usually appears within a minute or two of the release.

- [ ] **Step 7: Read the record, then take both DOIs**

Human. On the record page, check that the title, the authors, the version, the licence and the abstract are what `CITATION.cff` said. Fix anything Zenodo guessed rather than read. Then, from the "Cite all versions" box, take:

- the **concept DOI**, which always resolves to the newest version, and
- the **version DOI** for `v0.1.0` specifically.

They are different numbers and the difference is the whole point. The concept DOI goes in `CITATION.cff` because that file describes the leaderboard; the version DOI goes in the ledger because that row describes one snapshot.

- [ ] **Step 8: Write the DOIs back, and release again**

The `v0.1.0` snapshot on Zenodo does not contain its own DOI, because it could not. `v0.1.1` is the first release whose archived `CITATION.cff` is self-describing, and it is what the site should advertise from here on.

```bash
git checkout -b phase-9/record-the-doi
```

In `CITATION.cff`, add the concept DOI and bump the version:

```yaml
doi: 10.5281/zenodo.CONCEPT
version: "0.1.1"
date-released: "YYYY-MM-DD"
```

In `docs/RELEASES.md`, replace `minting` in the `0.1.0` row with the **version** DOI, and add a `0.1.1` row.

```bash
uv run eda-fingerprint            # unchanged: no data moved, only metadata
make check
uv run eda-release-check --tag "v0.1.1"; echo "exit=$?"
```

Expected: 0 problems. The fingerprint is unchanged because nothing under `data/` moved, and that is correct: the fingerprint tracks the data, not the metadata about it.

Merge, then:

```bash
gh release create v0.1.1 --title "v0.1.1" --notes "Records the Zenodo concept DOI in CITATION.cff. No data change; the fingerprint is unchanged from v0.1.0."
gh run watch
```

- [ ] **Step 9: Verify the whole chain, from a cold start**

```bash
# the concept DOI resolves, and lands on the NEWEST version
curl -sI "https://doi.org/$(uv run python -c 'from tools import citation; print(citation.load().leaderboard.doi)')" | head -1

# the site shows it
curl -s "$(uv run python -c 'from tools import citation; print(citation.load().leaderboard.url)')cite/" | grep -o 'doi\.org/[^"<]*'

# GitHub renders the citation
gh api repos/drexel-ice/eda-schema-leaderboard/contents/CITATION.cff --jq '.name'

# and every link on the site still resolves, DOI included
lychee --no-progress --accept 200,206,429 dist/
```

Expected: a `302` to the Zenodo record, the DOI printed from the live `/cite/` page, `CITATION.cff` present on the default branch, and 0 link errors.

Last, the human check that matters: open the record's "Cite all versions" DOI in a private window, and confirm a stranger arriving there can tell **what this is, which version they are looking at, and where the live site is**. If any of the three needs a follow-up question, fix it now while there is only one version to fix.

---

## Phase gate

Every item must pass. Paste the output, do not summarise it.

```bash
make check
make themes
uv run eda-release-check --tag "v$(uv run python -c 'from tools import citation; print(citation.load().leaderboard.version)')"
```

**Themes**

- [ ] `cssvars.contract()` is non-empty and derived from `var()` usage, not listed
- [ ] both themes define every contract variable, and the same set as each other
- [ ] no theme defines a variable nothing reads
- [ ] the five `--state-*-key` values are byte-identical across both themes
- [ ] dropping one variable from one theme fails the check, proven by the mutation test
- [ ] every state's ink clears 4.5:1 and every state's key clears 3:1, **in both themes**, computed from the shipped CSS
- [ ] `pa11y-ci` reports zero errors on both themes across matrix, explore, card, submit and a discovered cell page
- [ ] `THEME=drexl` stops the build instead of silently publishing the default
- [ ] `make themes` proves the two builds carry different stylesheets
- [ ] a human has viewed both side by side and picked one

**Deploy**

- [ ] `gh run watch` on `deploy.yml` concludes `success`
- [ ] `curl -sI https://<domain>/` returns 200
- [ ] the published `theme.css` is the chosen theme, fetched over HTTP and read
- [ ] a manual `repository_dispatch` triggers a deploy run
- [ ] a push to the experiments repo's `main` triggers a deploy run, with `notify-site` printing `dispatched results-updated` rather than its skip notice
- [ ] `du -sh dist-drexel dist-neutral` is well under 1 GB and near the 20 MB intent
- [ ] no page exceeds 88 KB

**Review stack**

- [ ] one automated reviewer, chosen explicitly, with the verdict recorded in `PLAN.md`
- [ ] if `claude-review.yml` stays, it has actually run once and posted a review
- [ ] if it was deleted, no required status check referenced it

**Transfer**

- [ ] both repositories are under `drexel-ice`
- [ ] `required_approving_review_count` is 1, `require_code_owner_reviews` and `enforce_admins` are true, force pushes and deletions are off
- [ ] the required-context list includes both `analyze` legs and excludes path-filtered `pa11y`
- [ ] `codeowners/errors` returns `[]` and every handle resolves
- [ ] Pages serves 200 at the new URL; every absolute URL in the repo points at it
- [ ] the negative-test PR failed `lint`, `validate` and `size` **independently**, and was closed
- [ ] `notify-site.yml` points at the new owner and its token has been re-issued
- [ ] the experiments repo's protection was re-applied too

**Citation**

- [ ] `CITATION.cff` is in the repository root and validates against the vendored CFF 1.2.0 schema with zero errors
- [ ] it describes **this leaderboard**, with the paper carried as a `references:` entry, and both render from one formatter
- [ ] deleting a required field fails the validator, proven by the mutation test rather than assumed
- [ ] GitHub shows "Cite this repository" on the default branch and its rendered BibTeX matches the site's
- [ ] there is no `.zenodo.json`, and no stored secret was added for any of this
- [ ] `docs/CARD.yaml` declares neither `version` nor `citation`; both are derived
- [ ] `pyproject.toml` and `CITATION.cff` name the same version, and disagreeing fails the check

**Version binding**

- [ ] `make version` records the fingerprint, and it matches the tree
- [ ] appending one byte to a file under `data/` makes `eda-validate` exit non-zero naming both digests, run by hand and pasted
- [ ] the fingerprint covers data only: no `.py`, `.css`, `.js` or `.html` file is in the hashed set
- [ ] every page's footer carries the version, the release date and the fingerprint

**The citation surface**

- [ ] `/cite/` renders BibTeX and APA for the leaderboard **and** the paper
- [ ] the BibTeX blocks on `/cite/` and on `/about/card/` are byte-identical, because one partial renders both
- [ ] every built page links to `/cite/`
- [ ] `/cite/` is in `.pa11yci.json` and passes in both themes
- [ ] `/cite/` is under 88 KB and `lychee` resolves every link on it, DOI included
- [ ] a human who had used the leaderboard could cite it from that page without asking anyone

**Release and DOI**

- [ ] **the transfer completed and the site answered 200 at its final URL BEFORE the first tag was pushed.** This is the ordering rule and it is not negotiable: see the citation ordering rule above
- [ ] `CITATION.cff` `url` and `repository-code` name `drexel-ice`, and the citation check passes against the final URL
- [ ] pushing a tag whose name disagrees with `CITATION.cff` fails the `release` workflow, proven rather than assumed
- [ ] `docs/RELEASES.md` explains what a tag contains and why a citable snapshot is immutable while the site is not
- [ ] the ledger has exactly one `minting` row, and a second one fails the check
- [ ] the concept DOI resolves, and the record's title, authors, licence and version match `CITATION.cff`
- [ ] the version DOI for the released tag is recorded in the ledger, and it is a different number from the concept DOI
- [ ] `v0.1.1` or later is the advertised version, so the archived snapshot contains its own DOI
- [ ] the Zenodo record's ownership was decided deliberately and the verdict is in `PLAN.md`

## Review prompt

```
Use a security reviewer on the Phase 9 diff and on live GitHub state, against
docs/plans/2026-08-11-phase-9-themes-deploy-transfer.md.

Verify by running the commands, not by reading the plan:

1. Fetch branch protection for both repos under drexel-ice. Confirm
   required_approving_review_count >= 1, require_code_owner_reviews true,
   enforce_admins true, allow_force_pushes false, allow_deletions false, and
   that every required context corresponds to a job that actually reports on a
   normal pull request. Name any required context that can never report, and any
   guard job that is NOT required.
2. Confirm no workflow can be triggered by a fork with write permissions or
   secret access. Check every trigger, not just the review workflow.
3. Confirm no credential is static where the plan claimed federation, and that
   no token value appears in any file, commit or workflow log.
4. Independently apply each mutation and confirm the suite fails: delete one
   --state-*-key from neutral.css; change one --state-*-key so the two themes
   disagree; set a state ink to a colour under 4.5:1 on its background; set
   THEME to a name with no file. Report any mutation that does NOT fail.
5. Confirm the negative-test PR failed lint, validate and size as three separate
   check runs, and that none of the three passed.
6. Confirm no credential was introduced for the citation work. grep every
   workflow for `secrets.`, and confirm the Zenodo integration is a webhook
   Zenodo installed rather than a token stored in the repository.
7. Apply each mutation and confirm the suite fails: delete `authors` from
   CITATION.cff; append a byte to a file under data/ without bumping the
   version; set `pyproject.toml`'s version to something CITATION.cff does not
   say; point `repository-code` at an owner that is not the one serving Pages;
   add a second `minting` row to docs/RELEASES.md. Report any mutation that does
   NOT fail.
8. Confirm the DOI was minted AFTER the transfer. Fetch the Zenodo record and
   the tag it was cut from, and confirm the archived CITATION.cff names the
   post-transfer URL. A record naming the old owner is a permanent defect, not
   a to-do.

Report only exposures and unguarded values. Do not report style preferences.
```
