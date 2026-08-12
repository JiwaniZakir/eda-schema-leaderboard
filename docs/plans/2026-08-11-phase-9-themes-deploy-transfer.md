# Phase 9 - Themes, Deploy and Transfer Implementation Plan

> **For agentic workers:** Implement this plan task-by-task - either dispatch a fresh subagent per task (recommended) or execute inline with review checkpoints. Steps use checkbox (`- [ ]`) syntax for tracking. Tasks 6 to 8 touch live GitHub state and are irreversible; run them inline, with a human watching, never in a background subagent.

**Goal:** ship two themes against one machine-checked CSS-variable contract, prove the deploy pipeline end to end including the cross-repo rebuild trigger, and hand both repositories to `drexel-ice` with their guardrails demonstrably intact.

**Architecture:** the contract is *derived, never listed*. `tools/cssvars.py` parses `var(--x)` references out of everything that consumes CSS and custom-property declarations out of each theme stylesheet, then diffs the sets. `tools/contrast.py` computes WCAG relative luminance from the same parsed values, so contrast is asserted against the colours that actually ship rather than against a table someone maintained by hand. Both land as checks in the existing `tools/checks/` registry, so `make validate` and the CI `validate` job pick them up with no workflow change. `build.py` selects one theme file by `THEME`, and a Makefile target builds both.

**Tech stack:** Python 3.11+, `uv`, `pytest`, `mypy --strict`, `ruff`, CSS custom properties, pa11y-ci, GitHub Actions, GitHub Pages, `gh`.

## Global constraints

Copied from `PLAN.md`; every task's requirements implicitly include these.

- Python **3.11+**, type hints on all public functions, `ruff` and `mypy` clean.
- **Registries are the only source of vocabulary.** CSS variable names are not registry vocabulary and may be named in `tools/checks/`; task, PDK, stage, metric and circuit names may not.
- **Counts are derived, never literal.** `tests/test_registry.py::test_no_count_literal_appears_in_tools` greps every `tools/**/*.py` for the strings `46 232 880 856 120 40 24 920`. The contrast constants below are safe (`0.2126`, `0.7152`, `0.0722`, `0.03928`, `12.92`, `1.055`, `2.4`, `4.5`, `3.0`, `255`, `16` all tokenize clear of that set), but a stray `0.24` or `0.40` in `tools/` will fail that test with a confusing message. Write ratios as `4.5`, not `0.24`-style fractions.
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
| Pages is live at `https://jiwanizakir.github.io/eda-schema-leaderboard/`, `build_type: workflow`, `cname: null`. | There is no custom domain yet. Task 8 decides one or accepts the `drexel-ice.github.io` URL. |
| `main` protection: 7 required contexts (`size`, `analyze (python)`, `lint`, `typecheck`, `validate`, `test`, `build`), `dismiss_stale_reviews: true`, **`required_approving_review_count: 0`**, **`enforce_admins: false`**, `require_code_owner_reviews: false`. | Task 8 raises all three. The context list is re-derived, not retyped, because CodeQL now also emits `analyze (javascript-typescript)` since `static/js/` exists. |
| **No secrets exist on either repository.** `gh secret list` is empty for both. | `claude-review.yml` has skipped on every PR to date, and `SITE_DISPATCH_TOKEN` is unset, so `repository_dispatch` has never once fired. Tasks 6 and 7. |
| `notify-site.yml` in the experiments repo POSTs to a **hardcoded** `repos/JiwaniZakir/eda-schema-leaderboard/dispatches`. | Task 8 must update it. A transferred repository's API redirects, but `curl -X POST` does not follow a redirect by default and the dispatch would silently 301 into nothing. |
| `gh repo transfer` **does not exist** in gh 2.83.2. `PLAN.md` Phase 9 quotes it anyway. | Task 8 uses `gh api -X POST repos/OWNER/REPO/transfer -f new_owner=drexel-ice`. |

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
    assert cssvars.referenced("a { color: var(--text, #000); }") == frozenset({"--text"})


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
        return ["no var() references found outside the themes; the contract cannot be empty"]

    per_theme = cssvars.theme_variables()
    internal = cssvars.theme_internal_references()

    for name in sorted(per_theme):
        declared = per_theme[name]
        for missing in sorted(required - declared):
            failures.append(f"{name}.css does not define {missing}, which the site reads")
        for dead in sorted(declared - required - internal):
            failures.append(f"{name}.css defines {dead}, which nothing reads")

    names = sorted(per_theme)
    first = names[0]
    for other in names[1:]:
        for var in sorted(per_theme[first] ^ per_theme[other]):
            owner = first if var in per_theme[first] else other
            failures.append(f"{var} is defined only by {owner}.css; every theme defines the same set")

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

TEXT_MINIMUM = 4.5      # WCAG 2.1 AA, 1.4.3, normal-size text
GRAPHIC_MINIMUM = 3.0   # WCAG 2.1 AA, 1.4.11, non-text contrast

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

### Task 8: Transfer, re-apply the guardrails, and prove they survived

Protection that silently did not survive a transfer is worse than none, because you will believe it is there.

**Do not start this until Tasks 1 to 7 are merged.** Every command below is irreversible or touches live state.

**Files:**
- Modify: `.github/CODEOWNERS`
- Modify: `README.md`, `docs/` (any absolute URL)
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
git add .github/CODEOWNERS README.md
git commit -m "chore(transfer): real CODEOWNERS handles and drexel-ice URLs"
git push -u origin phase-9/transfer-followups
gh pr create --title "Phase 9: transfer follow-ups" --body "CODEOWNERS handles verified against the API, absolute URLs updated for the new owner. Branch protection, Pages and the negative test are verified live; evidence in the phase gate checklist."
```

This PR is the first one that needs someone else's approval. That it cannot be self-merged is the proof that Step 6 worked.

---

## Phase gate

Every item must pass. Paste the output, do not summarise it.

```bash
make check
make themes
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

Report only exposures and unguarded values. Do not report style preferences.
```
