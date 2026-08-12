# Phase 10 - The Publish Path Implementation Plan

> **For agentic workers:** Implement this plan task-by-task - either dispatch a fresh subagent per task (recommended) or execute inline with review checkpoints. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** turn a merged, guard-passing `submission.yaml` into ranked, rendered shard entries, so a third party who submits actually appears on the site.

**Architecture:** `tools/submissions.py` discovers the one submission format and expands each bundle into the flat documents Phase 6's guard already validates.
`tools/reproduce.py` re-runs a submission against ground truth on a maintainer's machine and writes a committed reproduction record.
`tools/verification.py` owns the four-state trust vocabulary that record resolves to.
`tools/publish.py` recomputes each entry's aggregate from the submitter's per-circuit numbers and writes `data/published/**`, a tree the lab's `eda-ingest` never touches.
`tools/shards.py` becomes the single union point over `data/cells/**` and `data/published/**`, so neither generator can overwrite the other.
`tools/tally.py` counts cells won and tied, and `build.py` calls it in this phase.

**Tech stack:** Python 3.11+, `uv`, Jinja2, `jsonschema`, `pytest`, `mypy --strict`, `ruff`, vanilla JS, `lychee`, `pa11y-ci`. No new runtime dependency.

---

## The gap this phase closes

The project goal is "a static, citable benchmark leaderboard ... showing how **submitted models** compare against the paper's published baseline".
Across Phases 1 to 9, `data/cells/**` is written by exactly two things: `tools/ingest.py`, reading the lab's own results tree, and `tools/synth.py`, which Phase 7 recommends never shipping.

Phase 6 builds five guard layers that read `submissions/` and emit advisory `REJECT` and `FLAG` strings into `make validate`.
Phase 8 publishes a `/submit/` guide telling third parties how to write a submission.
**Nothing converts a merged, guard-passing submission into a shard.**
A third party can submit, clear every layer, get merged, and appear nowhere on the site.

There is a second, sharper bug underneath it.
`tools/checks/guard.py` globs `submissions/**/submission.json` and returns `[]` when the directory is missing.
The published guide tells submitters to write `submission.yaml`.
So a submitter who follows the documentation writes YAML, the glob matches nothing, `make validate` reports zero findings, and CI goes green on an **unvalidated** submission.
That is a guard that fails open, which is worse than no guard, because the green check is read as evidence.

This phase closes both.

## Two rulings already made by the maintainer

Do not re-litigate these.

### Ruling 1: the trust model is hybrid

A submission's declared metrics are published **immediately**, with a visible self-reported marker.
They are promoted only when our own runner reproduces them within a stated tolerance.

Four consequences, each of which is a design constraint below and a line in the phase gate:

- every entry carries a verification state, and the renderer makes self-reported visually distinct from reproduced **without relying on colour**
- a self-reported entry can never be silently presentable as verified.
  This is enforced structurally, not by care: the verification state is computed **only** from `data/reproductions/<model_id>.json`, a file written by a maintainer command on a trusted machine and committed, and the submission schema forbids the key outright.
  There is no code path from untrusted input to a promoted state.
- the reproduction tolerance is stated and justified against the display precision table in `docs/DATA_CONTRACT.md`, which publishes five tasks at 4 decimal places
- when reproduction **disagrees** with the declared number, the entry is not silently corrected.
  The disagreement is its own publishable state, `disputed`, which renders both numbers and is excluded from ranking and from cells-won.

### Ruling 2: this is Phase 10

It runs after the site is live and may depend on everything in Phases 1 to 9.

## A third ruling, which fixes the fail-open guard

### Ruling 3: one submission format

`submission.yaml`, matching what the Phase 8 `/submit/` guide publishes.
There is no second filename and no second parser.

YAML is loaded through `tools/yamlsafe.py`'s tag-stripping `SafeLoader`.
`yaml.full_load` and `yaml.UnsafeLoader` construct arbitrary objects and are the same hazard as unpickling; Phase 4's grep assertion already forbids them across `tools/` and this phase extends its reach rather than duplicating it.

**The check fails closed.**
If `submissions/` contains any file at all that is not part of a parseable, schema-valid submission, that is an error, not a silence.
The directory is committed with a `README.md`, so a missing `submissions/` is itself an error rather than an empty result.

## What this phase does not do

Named so the reviewer does not go looking for them.

- **It does not run reproduction in CI.** Scoring a prediction requires ground truth, and the only committed artifact with feature rows is Phase 6's smoke slice, which deliberately carries **no target column**. Reproduction is a maintainer command against a checkout of the lab's data, exactly like `make ingest`.
- **It does not add a second unpickling guard, a second sandbox or a second ordering rule.** It reuses `guard.runnability.run_predict`, `ranking.rank_key`, `ranking.compare` and `evallog.macro_mean` / `evallog.median_positive`. Where reuse required promoting a private name to public, that is a step in the task, not a copy.
- **It does not reproduce the four tail metrics.** `mae_p95`, `mape_p95`, `mae_top5` and `mape_top5` have no published formula, only prose on p.25, which is PLAN.md open decision 4 and needs Pratik. Cells carrying only those metrics stay `self_reported` until the decision lands. This gates two tasks' worth of metric rows, not the phase.

## Global constraints

Copied from `PLAN.md` and `CLAUDE.md`; every task's requirements implicitly include these.

- Python **3.11+**, type hints on all public functions, `ruff` and `mypy --strict` clean.
- **Registries are the only source of vocabulary.** Never hardcode a task, PDK, stage, metric or circuit name outside `data/registry/`. Where a formula must name the metric it computes, the binding is asserted against `reg.metrics()` in **both directions**, following the precedent `evallog._MEDIAN_METRICS` set in Phase 4.
- **Counts are derived, never literal.** No module under `tools/` writes 46, 232, 880, 856, 120, 40, 24 or 920, in code or in a docstring. Phase 1's AST scan catches the code; this plan's prose in `tools/` avoids the rest.
- **Percent metrics** (`mape`, `mape_p95`, `mape_top5`, `tpr`, `tnr`) are fractions in `[0, 1]` everywhere under `data/`, including in a submission's declared numbers. The `x100` happens exactly once, at display.
- **Every record carries an explicit `source`.** A published submission is `"source": "submission"` and `make validate` fails without one.
- **Never unpickle a checkpoint.** `weights_only=True` is not sufficient; it refuses all 360 of the lab's own checkpoints. Shapes come from `tools/ckpt.py`'s restricted zip reader. Community submissions run on our runner, so this is the security boundary and not a style preference.
- **Model labels are untrusted input rendered into HTML.** Every submission-derived string reaches the DOM through Jinja2 autoescaping or JavaScript `textContent`, never `innerHTML` and never `| safe`.
- **Never commit files over 1 MB**, and never commit anything under `data/` by hand.
- `dist/` targets ~20 MB and no page exceeds 88 KB.
- Conventional commits. Branch `phase-10/publish-path`. Never push to `main`.
- **Never use an em dash** in prose, code comments or generated copy.

## Inherited interfaces

Locked by the phases before this one.
If a name differs, adapt at the import line rather than reaching around it.

**Phase 1, `tools/registry.py`**

```python
reg.tasks() / metrics() / stages() / pdks() / circuits()   # tuples, stages in order
reg.task(id) / metric(id) / stage(id) / pdk(id)            # KeyError on unknown
reg.is_void(task_id, stage_id) -> bool
reg.is_degenerate(task_id, metric_id, stage_id) -> bool
reg.is_saturated(task_id, metric_id, stage_id) -> bool
reg.precision(task_id, metric_id) -> int                   # DISPLAY decimal places
reg.live_combos() / reg.live_cells()
reg.REGISTRY_DIR: Path
```

**Phase 1, `tools/checks/__init__.py`**

```python
CHECKS: dict[str, Callable[[], list[str]]]
register(name) -> decorator
```

**Phase 2, `tools/baseline.py`**

```python
class BoundKind(StrEnum): EXACT | GREATER_THAN | LESS_THAN | ABSENT
@dataclass(frozen=True) class Bound: kind: BoundKind; value: float | None
baseline.lookup(task_id, metric_id, pdk_id, stage_id) -> Baseline   # .bound
```

**Phase 4, `tools/evallog.py`, `tools/ingest.py`, `tools/shards.py`, `tools/ranking.py`, `tools/yamlsafe.py`**

```python
evallog.macro_mean(values) -> float
evallog.median_positive(values) -> tuple[float, int]

ingest.MetricValue(macro, pooled, ranked_on, n_circuits, n_positive)
ingest.Entry(model_id, model_label, family, source, architecture, metrics)
ingest.Shard(task, pdk, stage, generated_from, cross_check, entries)
ingest.shard_path(task_id, pdk_id, stage_id) -> Path      # data/cells/...
ingest.LAB_MODEL_ID = "lab-fixed-mlp"
ingest.SUBMISSION = "submission"; ingest.MACRO = "macro"

shards.Record(task, metric, pdk, stage, model_id, model_label, source,
              value_macro, value_pooled, ranked_on, n_circuits, n_positive)
shards.load(task_id, pdk_id, stage_id) -> tuple[Record, ...]
shards.bound_of(record) -> Bound
shards.populated_combos() -> tuple[tuple[str, str, str], ...]

ranking.Comparison(StrEnum): BETTER | EQUAL | WORSE | UNDECIDABLE
ranking.CellState(StrEnum): BEATS_BASELINE | MATCHES_BASELINE | BASELINE_LEADS
                            | NO_ENTRY | SATURATED
ranking.rank_key(metric_id, value) -> float
ranking.compare(task_id, metric_id, challenger: Bound, incumbent: Bound)
ranking.cell_state(task_id, metric_id, stage_id, baseline: Bound, entries)
ranking.rank_of(...) / ranking.percentile_of(...)

yamlsafe.TagStrippingLoader; yamlsafe.load(text); yamlsafe.load_path(path)
```

**Phase 5, `tools/cellpage.py`, `tools/urls.py`**

```python
cellpage.Entry(model_id, model_label, source, value, display, pooled_display,
               verdict, rank)
cellpage.MetricRow(..., mode, baseline_kind, baseline_value, entries, undecidable)
cellpage.CellPage(...)
cellpage.format_value(task_id, metric_id, value) -> str    # the display boundary
cellpage.CSV_COLUMNS: tuple[str, ...]
```

DOM contract: `section.metric-row[data-metric][data-state][data-mode]`, `.baseline[data-baseline]` above `table.ranking`, `tr[data-model][data-source][data-verdict]`.

**Phase 6, `tools/guard/`**

```python
guard.Severity(REJECT | FLAG); guard.Finding(layer, severity, message)
guard.LAYERS: dict[str, LayerFn]     # schema, features, splits, divisions,
                                     # runnability, plausibility
guard.run_all(sub) -> list[Finding]; guard.rejected(findings) -> bool
guard.schema.check(sub) -> list[Finding]
guard.runnability.run_predict(entry: Path, workdir: Path) -> RunResult
schema/submission.schema.json        # the flat, single-combo validated unit
data/registry/splits.json            # the canonical split
```

**Phase 8, `tools/submission.py`, `tools/modelpage.py`**

```python
submission.TIERS / DIVISIONS / BADGES; submission.PREDICT_SIGNATURE
modelpage.MODEL_ID_RE; modelpage.validate_id(model_id) -> str
```

### Three inherited defects this phase must correct

These are not style findings.
Each one is a place where two shipped plans disagree, and where following either one alone produces a wrong result.

| Defect | Where | Correction, and which task makes it |
|---|---|---|
| The guard globs `submission.json`; the guide publishes `submission.yaml`. The glob fails open on a missing directory. | Phase 6 Task 8 Step 3 against Phase 8 Task 4 Step 4 | YAML wins, and discovery fails closed. **Task 1.** |
| Phase 8's `TIERS` and `DIVISIONS` name guard layers `feature_stage`, `split_overlap` and `division`. Phase 6 registers them as `features`, `splits` and `divisions`, and Phase 8's own `test_every_tier_requires_only_guard_layers_that_exist` fails against them. | Phase 8 Task 4 Step 3 against Phase 6 Task 2 Step 5 | Phase 6's ids are canonical, because they are the dict keys the dispatcher actually uses. Phase 8's tuples are corrected. **Task 2.** |
| Phase 8's `reproduced` tier says `predict.py` "ran on our runner against the smoke slice and returned the reported metrics within tolerance". Phase 6 Task 6 Step 5 ships the smoke slice **with no target column**, on purpose. Metrics cannot be computed from it, so that tier as described is unreachable. | Phase 8 Task 4 Step 3 against Phase 6 Task 6 | The smoke slice proves runnability and nothing else. Reproduction scores against ground truth on a maintainer's machine. The tier description is rewritten. **Task 3.** |

A fourth, smaller one: `ranking._display_units` multiplies by `_PERCENT_SCALE` and `cellpage.format_value` multiplies by a separate literal `100.0`.
Two copies of the percent scale in a project whose single most dangerous bug is a factor of a hundred.
Task 3 promotes one constant and deletes the other.

## The design, in one page

Read this before Task 1.
Every question the reviewer will ask is answered here, and each answer names the task that implements it.

**What turns a validated submission into shard entries.**
`publish.entry_for(unit: submissions.Unit, record: reproduce.Record | None) -> ingest.Entry`.
One `Unit` is one `(task, pdk, stage)` combo of one submission; one `Entry` is that model's whole metric set for that combo.
It is the only function that constructs an `Entry` from untrusted input. **Task 4.**

**How it merges with the lab's entries without either overwriting the other.**
Structurally, by never writing to the same file.
`eda-ingest` owns `data/cells/**` and `eda-publish` owns `data/published/**`; both are full regenerations of their own tree from their own source, so a full re-ingest cannot delete a community entry and a full re-publish cannot delete the lab's.
`shards.load` is the single union point, lab first, keyed on `model_id`, and a collision is a raised error rather than a silent last-write-wins.
`ingest.LAB_MODEL_ID` is a reserved id that no submission directory may take. **Task 4.**

**A submission that covers only some combos.**
That is the normal case, not an exception.
`submission.yaml` is a bundle: shared identity plus a `results` list, one item per `(task, pdk, stage)` it claims.
Combos not listed get nothing, and no placeholder entry is written.
`submissions.expand` turns one bundle into N flat documents, each of which is exactly the shape Phase 6's `schema/submission.schema.json` already validates, so the guard runs unchanged on each. **Task 1.**

**Re-submission and versioning.**
`model_id` is the submission **directory name**, validated against `modelpage.MODEL_ID_RE`, and it is the identity.
A submission is a working-tree state, not an append-only log: editing `submissions/acme-mlp/submission.yaml` and re-running publish replaces that model's entries in place, at its existing index, in every combo it claims.
A submitter who wants their old entry to remain alongside the new one ships a new directory (`acme-mlp-v2`), which is a new identity and a new row.
Deleting the directory removes the entries, and `tools/checks/publish.py` fails if the working tree and `data/published/**` disagree, so neither a stale nor a missing entry can survive a merge. **Task 4.**

**How the aggregation rule is enforced.**
It is not enforced on a declared aggregate, because it cannot be: one number carries no evidence of how it was reduced.
So the submitter declares **per-circuit** numbers, and we compute the aggregate ourselves with the same two functions the lab's ingest uses, `evallog.macro_mean` and `evallog.median_positive`.
The declared aggregate is stored nowhere; it is only ever a claim, cross-checked against ours at the same tolerance reproduction uses.
A submitter who pooled instead of macro-meaning is caught here, before their model is ever run. **Task 4.**

**Saturated cells.**
The entry is stored and listed, and the cell is never ranked.
`ranking.cell_state` already short-circuits on `reg.is_saturated`, and Phase 4 already ruled that a saturated cell keeps its measurement.
Publishing into `global_route` must leave the saturated count exactly where it was. **Task 4 and Task 5.**

**Degenerate cells.**
The baseline is `ABSENT`, so `ranking.compare` returns `UNDECIDABLE` and the row renders in `no_comparison` mode with the entry listed and no verdict.
Nothing can beat a baseline that was never measured, so a degenerate cell contributes zero to cells-won for every model, forever. **Task 4 and Task 6.**

**Cells-won.**
`tally.cells_won_by_model()`, counting cells where the model's record compares `BETTER` against the published bound.
It excludes: void cells (not in `reg.live_cells()`), saturated cells, degenerate cells (`UNDECIDABLE`), sentinel comparisons that do not clear the threshold (`UNDECIDABLE`), ties (`EQUAL`, counted separately as cells-tied because tying is the best achievable outcome on roughly 132 cells), synthetic records, and disputed records.
`build.py` calls it in this phase. **Task 6.**

## File structure

| File | Responsibility |
|---|---|
| `submissions/README.md` | the committed root of the submissions tree; its existence is what makes a missing directory an error |
| `schema/submission_bundle.schema.json` | the bundle a submitter writes: identity plus `results[]` |
| `tools/submissions.py` | `Bundle`, `Unit`, `Discovery`, `discover`, `read_bundle`, `expand`; the one format, fail closed |
| `tools/verification.py` | `VerificationState`, `LABELS`, `NOTES`, `RANKABLE`, `parse`, `state_for` |
| `tools/reproduce.py` | `REL_TOL`, `display_floor`, `tolerance`, `agrees`, scorers, `Record`, `reproduce`, `main` |
| `tools/publish.py` | `entry_for`, `shard_for`, `publish`, `main`; the only constructor of an `Entry` from untrusted input |
| `tools/shards.py` | modified: `PUBLISHED_DIR`, `published_shard_path`, the lab-plus-published union, `Record.verification` |
| `tools/ingest.py` | modified: `Entry.verification`, `Entry.reproduction`, `LAB_VERIFICATION` |
| `tools/ranking.py` | modified: `quantize` and `PERCENT_SCALE` promoted to public, one copy each |
| `tools/tally.py` | `is_countable`, `cells_won_by_model`, `cells_tied_by_model`, `cells_won`, `cells_tied` |
| `tools/cellpage.py` | modified: verification on `Entry`, disputed excluded from the state, two new columns |
| `tools/checks/publish.py` | the drift detector, the fail-closed discovery errors, the disputed flags |
| `tools/checks/guard.py` | modified: reads `submissions.discover()` instead of globbing JSON |
| `data/published/**` | generated by `eda-publish`, committed by the generator, never hand-edited |
| `data/reproductions/*.json` | maintainer-written, committed; the only input that can promote an entry |
| `templates/pages/cell.html` | modified: the verification column and the disputed panel |
| `templates/pages/matrix.html` | modified: the self-reported and disputed markers, and the legend |
| `static/css/cell.css` | modified: verification styling, no new colour-only channel |
| `tests/fixtures/submissions_tree/**` | a well-formed tree, and eight malformed ones |
| `tests/fixtures/targets/**` | three tiny per-circuit ground-truth files, ours, not the lab's |
| `tests/test_submissions.py`, `test_verification.py`, `test_reproduce.py`, `test_publish.py`, `test_publish_render.py`, `test_tally.py`, `test_publish_e2e.py` | one per module, plus the end-to-end |

---

### Task 1: One format, and a discovery that fails closed

The fail-open guard is fixed before anything is built on top of it.
Until this task lands, every later task would be reading a tree nothing validates.

**Files:**
- Create: `tools/submissions.py`, `schema/submission_bundle.schema.json`, `submissions/README.md`
- Create: `tests/fixtures/submissions_tree/**`
- Modify: `tools/checks/guard.py`, `tests/test_guard.py`, `tests/fixtures/submissions/*.json` to `*.yaml`
- Test: `tests/test_submissions.py`

**Interfaces:**
- Consumes: `tools.registry`, `tools.yamlsafe` (`load_path`), `tools.guard` (`schema.check`, `run_all`, `rejected`, `Severity`), `tools.modelpage` (`MODEL_ID_RE`), `jsonschema`.
- Produces: `submissions.SUBMISSIONS_DIR: Path`, `submissions.BUNDLE_NAME: str`, `submissions.ALLOWED_FILES: frozenset[str]`, `submissions.Bundle`, `submissions.Unit`, `submissions.Discovery`, `submissions.model_id_of(directory: Path) -> str`, `submissions.read_bundle(directory: Path) -> Bundle`, `submissions.expand(bundle: Bundle) -> tuple[Unit, ...]`, `submissions.discover(root: Path = SUBMISSIONS_DIR) -> Discovery`.

#### The bundle, and why it is not a second schema

Phase 6's `schema/submission.schema.json` validates one flat document describing one `(task, pdk, stage)`.
That stays **exactly as it is** and remains the unit every guard layer sees.
Asking a submitter who covers twenty combos to write twenty directories with twenty copies of `predict.py` is not a format, it is a punishment, so the file they write is a bundle:

```yaml
# submissions/acme-mlp/submission.yaml
schema_version: 1
source: submission
submitted_at: "2026-08-11T00:00:00Z"
authors: ["A. Submitter"]
model_label: "Acme MLP"
division: open
features:
  - {namespace: netlist, name: no_of_cells}
  - {namespace: cell_metrics, name: no_of_total_cells}
split:
  train: [ac97_ctrl, aes_core, des3_area, ethernet, i2c, jpeg]
  test: [systemcaes, systemcdes, tv80]
predict_entrypoint: predict.py
model: {family: mlp, params: 5313}
results:
  - task: total_area_prediction
    pdk: ng45
    stage: floorplan
    target: total_area
    metrics: {mae: 850.0, mape: 0.0421, r2: -1.8}
    per_circuit:
      systemcaes: {mae: 700.0, mape: 0.0380, r2: -1.2}
      systemcdes: {mae: 900.0, mape: 0.0450, r2: -2.4}
      tv80:       {mae: 950.0, mape: 0.0433, r2: -1.8}
```

`expand` produces one flat document per `results` item by merging the identity keys with that item's keys, plus `submission_id` taken from the directory name.
A one-result bundle expands to a document byte-identical to Phase 6's `valid_open` fixture, and Step 1 asserts exactly that.
So the bundle is a container, not a competing schema, and the guard's contract is untouched.

`metrics` is the submitter's **claim**.
`per_circuit` is the evidence.
Task 4 recomputes the aggregate from the evidence and never stores the claim.

#### Fail closed means naming what is wrong

`discover` returns errors as strings rather than raising, because `tools/checks/*` prints message lists and one bad directory must not hide the other nineteen.
Every one of these is an error:

| Condition | Why silence is worse |
|---|---|
| `submissions/` does not exist | the tree is committed; missing means deleted, not empty |
| a file directly under `submissions/` other than `README.md` | someone wrote a submission at the wrong depth |
| a directory name that fails `MODEL_ID_RE` | `model_id` reaches a URL and a filename |
| a symlink anywhere in the tree | the read path would leave the repository |
| no `submission.yaml` in a submission directory | the exact fail-open case |
| a `submission.json` or `submission.yml` present | the near-miss filename, named explicitly so the fix is obvious |
| a file in a submission directory outside `ALLOWED_FILES` | staged data for a parser change we have not made |
| YAML that does not parse, or does not parse to a mapping | |
| a document that fails the bundle schema | |
| two directories whose ids differ only by case | one shard key, two submitters |
| `results` containing a duplicate `(task, pdk, stage)` | two claims on one cell from one model |
| any `results` item on a void combo | the paper says that cell does not exist |

- [ ] **Step 1: Write the failing tests**

Create `tests/test_submissions.py`:

```python
"""One submission format, and a discovery that reports rather than shrugs.

The bug this file exists for: the guard globbed submissions/**/submission.json
while the published guide told submitters to write submission.yaml, and returned
an empty list when the directory was missing. A submitter who followed the
documentation produced zero findings and a green CI run on an unvalidated entry.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import guard, submissions
from tools import registry as reg

TREES = Path(__file__).resolve().parent / "fixtures" / "submissions_tree"
GUARD_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "submissions"


def discover(name: str) -> submissions.Discovery:
    return submissions.discover(TREES / name)


def test_a_well_formed_tree_yields_its_bundles_and_no_errors() -> None:
    found = discover("valid")
    assert found.errors == ()
    assert [b.model_id for b in found.bundles] == ["acme-mlp", "beta-gnn"]


def test_the_model_id_is_the_directory_name_and_not_a_declared_field() -> None:
    """Identity comes from the filesystem, which the submitter cannot make
    disagree with itself. A declared id and a directory name are two identities
    and one of them is always the wrong one."""
    bundle = discover("valid").bundles[0]
    assert bundle.model_id == bundle.directory.name
    assert "submission_id" not in bundle.document


@pytest.mark.parametrize(
    "tree",
    [
        "missing_root",
        "json_instead_of_yaml",
        "yml_instead_of_yaml",
        "no_bundle",
        "stray_file_at_root",
        "stray_file_in_submission",
        "bad_model_id",
        "unparseable_yaml",
        "schema_invalid",
        "duplicate_id_by_case",
        "duplicate_result_combo",
        "void_combo",
        "symlinked_bundle",
        "declares_verification",
    ],
)
def test_every_malformed_tree_is_an_error_and_not_a_silence(tree: str) -> None:
    """THE test for this task. Each of these once produced, or would produce,
    zero findings and a green check."""
    found = discover(tree)
    assert found.errors, f"{tree} produced no error"
    assert all(isinstance(e, str) and e.strip() for e in found.errors)


def test_the_error_names_the_one_true_filename() -> None:
    """A message that says "invalid" teaches nothing. A submitter who wrote JSON
    must be told the filename to write instead."""
    messages = " ".join(discover("json_instead_of_yaml").errors)
    assert submissions.BUNDLE_NAME in messages


def test_a_submitter_cannot_declare_their_own_verification_state() -> None:
    """Ruling 1, enforced at the parse boundary. There is no path from untrusted
    input to a promoted state, so this is not a check that can be forgotten
    later."""
    assert discover("declares_verification").errors


def test_expansion_produces_exactly_the_document_the_guard_already_validates() -> None:
    """The bundle is a container, not a competing schema. A one-result bundle
    expands to the Phase 6 fixture verbatim, so the guard's contract is
    untouched."""
    bundle = submissions.read_bundle(TREES / "single_result" / "acme-mlp")
    units = submissions.expand(bundle)
    assert len(units) == 1
    expected = json.loads((GUARD_FIXTURES / "valid_open.json").read_text("utf-8"))
    assert units[0].document == expected


def test_expansion_covers_only_the_combos_the_bundle_claims() -> None:
    """Partial coverage is the normal case. Nothing is written for a combo the
    submitter did not claim."""
    bundle = discover("valid").bundles[0]
    units = submissions.expand(bundle)
    claimed = {(u.task, u.pdk, u.stage) for u in units}
    assert claimed == {
        ("total_area_prediction", "ng45", "floorplan"),
        ("total_area_prediction", "asap7", "cts"),
    }
    assert claimed < set(reg.live_combos())


def test_every_expanded_unit_passes_the_guard_schema_layer() -> None:
    for bundle in discover("valid").bundles:
        for unit in submissions.expand(bundle):
            assert guard.schema.check(unit.document) == []


def test_the_whole_guard_stack_runs_on_every_unit() -> None:
    """The consumer, in this task. A discovery nothing validates is the bug
    again with a different filename."""
    for bundle in discover("valid").bundles:
        for unit in submissions.expand(bundle):
            assert not guard.rejected(guard.run_all(unit.document))


def test_yaml_is_read_without_constructing_a_foreign_object() -> None:
    """hparams.yaml in the lab's tree carries !!python/object: tags and breaks
    safe_load. full_load and UnsafeLoader construct arbitrary objects and are the
    same hazard as unpickling. A submitter gets the same reader, for the same
    reason."""
    source = Path(__file__).resolve().parent.parent / "tools" / "submissions.py"
    text = source.read_text(encoding="utf-8")
    assert "yamlsafe" in text
    for forbidden in ("full_load", "UnsafeLoader", "yaml.load("):
        assert forbidden not in text
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_submissions.py -v`
Expected: FAIL, `ImportError: cannot import name 'submissions' from 'tools'`

- [ ] **Step 3: Build the fixture trees**

`tests/fixtures/submissions_tree/valid/` holds `acme-mlp/` and `beta-gnn/`, each with `submission.yaml` and `predict.py`, plus a root `README.md`.
`acme-mlp` claims two combos, `beta-gnn` one.
`tests/fixtures/submissions_tree/single_result/acme-mlp/submission.yaml` is the bundle whose expansion equals `valid_open.json`.

Then fourteen malformed trees, each a minimal copy of `valid` with exactly one thing wrong.
Write them out rather than generating them: a fixture that a helper builds is a fixture nobody reads when it fails.
`missing_root/` is the one exception; it is a path that does not exist and needs no files.

`symlinked_bundle/acme-mlp/submission.yaml` is created by the test session, not committed, because git's handling of a symlink across platforms is not what this fixture is testing:

```python
@pytest.fixture(scope="session", autouse=True)
def _symlink_fixture() -> Iterator[None]:
    target = TREES / "symlinked_bundle" / "acme-mlp" / submissions.BUNDLE_NAME
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.is_symlink():
        target.symlink_to(TREES / "valid" / "acme-mlp" / submissions.BUNDLE_NAME)
    yield
    target.unlink(missing_ok=True)
```

- [ ] **Step 4: Write the bundle schema**

`schema/submission_bundle.schema.json`, draft 2020-12, `"additionalProperties": false` at every object level.
`results` is an array with `"minItems": 1`.
`submission_id` and `verification` are **not** properties, so `additionalProperties: false` rejects both: the first because identity is the directory name, the second because Ruling 1 says a submitter cannot promote themselves.

Vocabulary enums are injected from the registry at load time exactly as Phase 6 does, never written into the file.
`results[].metrics` and `results[].per_circuit.<circuit>` are objects whose values are numbers, with `propertyNames.enum` filled from `reg.metrics()` and `reg.circuits()`.

- [ ] **Step 5: Implement `tools/submissions.py`**

```python
"""Find, read and expand the submissions tree.

ONE format: submissions/<model_id>/submission.yaml. There is no second filename
and no second parser.

The bug this module replaces globbed submission.json while the published guide
said submission.yaml, and returned an empty list when the directory was missing.
Both halves are fixed: one name, and anything under submissions/ that is not part
of a well formed submission is an error rather than a silence. A guard that fails
open is worse than no guard, because the green check is read as evidence.

The bundle a submitter writes is identity plus a results list. expand() turns it
into one flat document per claimed combo, each of which is exactly the shape
schema/submission.schema.json already validates, so every guard layer runs
unchanged. The bundle is a container, not a competing schema.

YAML is read through tools.yamlsafe, which strips tags and constructs no foreign
object. yaml.full_load and yaml.UnsafeLoader are the same hazard as unpickling.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import jsonschema

from tools import registry as reg
from tools import yamlsafe
from tools.modelpage import MODEL_ID_RE

ROOT = Path(__file__).resolve().parent.parent
SUBMISSIONS_DIR = ROOT / "submissions"
SCHEMA_PATH = ROOT / "schema" / "submission_bundle.schema.json"

BUNDLE_NAME = "submission.yaml"
NEAR_MISS_NAMES = ("submission.json", "submission.yml", "submission.YAML")
ROOT_FILES = frozenset({"README.md"})
ALLOWED_FILES = frozenset({BUNDLE_NAME, "predict.py", "README.md", "requirements.txt"})

RESULT_KEYS = ("task", "pdk", "stage", "target", "metrics", "per_circuit")
IDENTITY_DROP = ("results",)


@dataclass(frozen=True, slots=True)
class Bundle:
    """One submission directory, parsed and schema-valid."""

    model_id: str
    directory: Path
    document: dict[str, Any]


@dataclass(frozen=True, slots=True)
class Unit:
    """One (task, pdk, stage) claim, in the flat shape the guard validates."""

    model_id: str
    directory: Path
    task: str
    pdk: str
    stage: str
    document: dict[str, Any]


@dataclass(frozen=True, slots=True)
class Discovery:
    bundles: tuple[Bundle, ...]
    errors: tuple[str, ...]


@cache
def _schema() -> dict[str, Any]:
    """The bundle schema with registry vocabularies injected.

    The file on disk carries empty enums as markers. A hand written enum is a
    second copy of the vocabulary and drifts the first time a registry changes.
    """
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    result = schema["properties"]["results"]["items"]["properties"]
    result["task"]["enum"] = [t.id for t in reg.tasks()]
    result["pdk"]["enum"] = [p.id for p in reg.pdks()]
    result["stage"]["enum"] = [s.id for s in reg.stages()]
    result["metrics"]["propertyNames"]["enum"] = [m.id for m in reg.metrics()]
    result["per_circuit"]["propertyNames"]["enum"] = [c.id for c in reg.circuits()]
    circuits = schema["properties"]["split"]["properties"]
    circuits["train"]["items"]["enum"] = [c.id for c in reg.circuits()]
    circuits["test"]["items"]["enum"] = [c.id for c in reg.circuits()]
    return schema


def model_id_of(directory: Path) -> str:
    """The directory name, validated. Identity comes from the filesystem.

    A declared id plus a directory name is two identities, and one of them is
    always the wrong one. model_id reaches a URL and a filename, so the pattern
    is the one Phase 8 already uses for a model page route.
    """
    name = directory.name
    if not MODEL_ID_RE.fullmatch(name):
        raise ValueError(f"{name!r} is not a usable model id")
    return name


def read_bundle(directory: Path) -> Bundle:
    """Parse and validate one submission directory. Raises on anything wrong."""
    model_id = model_id_of(directory)
    path = directory / BUNDLE_NAME

    for entry in sorted(directory.iterdir()):
        if entry.is_symlink():
            raise ValueError(f"{entry} is a symlink; the read path must stay in-tree")
        if entry.is_file() and entry.name not in ALLOWED_FILES:
            near = " (did you mean %s?)" % BUNDLE_NAME
            hint = near if entry.name in NEAR_MISS_NAMES else ""
            raise ValueError(f"{entry} is not an expected submission file{hint}")

    if not path.is_file():
        raise ValueError(f"{directory} has no {BUNDLE_NAME}")

    document = yamlsafe.load_path(path)
    if not isinstance(document, dict):
        raise ValueError(f"{path} does not parse to a mapping")

    jsonschema.validate(document, _schema())

    seen: set[tuple[str, str, str]] = set()
    for result in document["results"]:
        combo = (result["task"], result["pdk"], result["stage"])
        if combo in seen:
            raise ValueError(f"{path} claims {combo} twice")
        seen.add(combo)
        if reg.is_void(result["task"], result["stage"]):
            raise ValueError(f"{path} claims {combo}, which the paper voids")

    return Bundle(model_id=model_id, directory=directory, document=document)


def expand(bundle: Bundle) -> tuple[Unit, ...]:
    """One flat guard-shaped document per claimed combo, in declaration order."""
    identity = {
        key: value for key, value in bundle.document.items() if key not in IDENTITY_DROP
    }
    units: list[Unit] = []
    for result in bundle.document["results"]:
        document = {**identity, "submission_id": bundle.model_id, **result}
        units.append(
            Unit(
                model_id=bundle.model_id,
                directory=bundle.directory,
                task=result["task"],
                pdk=result["pdk"],
                stage=result["stage"],
                document=document,
            )
        )
    return tuple(units)


def discover(root: Path = SUBMISSIONS_DIR) -> Discovery:
    """Every submission under `root`, and a message for everything that is not.

    Errors are returned rather than raised so one bad directory cannot hide the
    other nineteen, and an empty error tuple is the only thing a caller may read
    as success.
    """
    if not root.is_dir():
        return Discovery(
            (), (f"{root} does not exist; the submissions tree is not optional",)
        )

    bundles: list[Bundle] = []
    errors: list[str] = []
    by_lowered: dict[str, str] = {}

    for entry in sorted(root.iterdir()):
        if entry.is_symlink():
            errors.append(f"{entry} is a symlink; the read path must stay in-tree")
            continue
        if entry.is_file():
            if entry.name not in ROOT_FILES:
                errors.append(
                    f"{entry} sits at the root of the tree; a submission is a directory"
                )
            continue
        try:
            bundle = read_bundle(entry)
        except (ValueError, jsonschema.ValidationError) as exc:
            errors.append(f"{entry}: {exc}")
            continue
        clash = by_lowered.get(bundle.model_id.lower())
        if clash is not None:
            errors.append(f"{entry}: id collides with {clash} once cased")
            continue
        by_lowered[bundle.model_id.lower()] = bundle.model_id
        bundles.append(bundle)

    return Discovery(tuple(bundles), tuple(errors))
```

- [ ] **Step 6: Convert the Phase 6 fixtures and rewire the guard check**

Convert `tests/fixtures/submissions/*.json` to `*.yaml` and change `tests/test_guard.py`'s helper:

```python
def load(name: str) -> dict[str, Any]:
    from tools import yamlsafe

    return yamlsafe.load_path(FIXTURES / f"{name}.yaml")
```

`valid_open.json` **stays** as JSON, because `test_expansion_produces_exactly_the_document_the_guard_already_validates` compares against it and a fixture that is both the input and the expected output verifies nothing.
Keep it as the expected-output fixture only.

Replace the body of `tools/checks/guard.py`:

```python
"""Run the guard stack over every submission under submissions/.

Fails closed. A tree that yields no bundles and no errors is only possible when
the tree is genuinely empty, and a tree that is missing is itself an error.
"""

from __future__ import annotations

from tools import submissions
from tools.checks import register
from tools.guard import Severity, run_all


@register("guard")
def check() -> list[str]:
    found = submissions.discover()
    messages = [f"REJECT {error}" for error in found.errors]
    for bundle in found.bundles:
        for unit in submissions.expand(bundle):
            for finding in run_all(unit.document):
                prefix = "REJECT" if finding.severity is Severity.REJECT else "FLAG"
                messages.append(
                    f"{prefix} {bundle.model_id} "
                    f"{unit.task}/{unit.pdk}/{unit.stage}: "
                    f"[{finding.layer}] {finding.message}"
                )
    return messages
```

- [ ] **Step 7: Create the committed tree**

```bash
mkdir -p submissions
```

Write `submissions/README.md`: what a submission directory is, the one filename, a pointer to `/submit/` and to `docs/SUBMISSION.md`, and the sentence that this file's existence is load-bearing because a missing tree is an error.

- [ ] **Step 8: Run the tests**

Run: `uv run pytest tests/test_submissions.py tests/test_guard.py -v`
Expected: all pass.

Then prove the fail-open bug is actually gone, by hand:

```bash
mkdir -p /tmp/failopen/acme-mlp
cp tests/fixtures/submissions_tree/valid/acme-mlp/submission.yaml \
   /tmp/failopen/acme-mlp/submission.json
uv run python -c "
from pathlib import Path
from tools import submissions
found = submissions.discover(Path('/tmp/failopen'))
print('bundles', len(found.bundles))
for e in found.errors: print('ERROR', e)
"
```

Expected: `bundles 0` and at least one `ERROR` naming `submission.yaml`.
Before this task the same tree produced zero findings and exit 0.

- [ ] **Step 9: Commit**

```bash
git add tools/submissions.py tools/checks/guard.py schema/submission_bundle.schema.json \
        submissions/README.md tests/fixtures/submissions tests/fixtures/submissions_tree \
        tests/test_submissions.py tests/test_guard.py
git commit -m "fix(guard): one submission format, and a discovery that fails closed"
```

---

### Task 2: The verification vocabulary, and the record that is the only way to move

Four states, one file that can promote an entry, and a reconciliation with the tier ladder Phase 8 already published.

**Files:**
- Create: `tools/verification.py`, `data/reproductions/README.md`
- Modify: `tools/submission.py` (the Phase 8 tier and division data)
- Test: `tests/test_verification.py`, `tests/test_submit.py`

**Interfaces:**
- Consumes: `tools.registry`, `tools.guard` (`LAYERS`), `tools.submission` (`TIERS`).
- Produces: `verification.VerificationState`, `verification.LABELS: dict[str, str]`, `verification.NOTES: dict[str, str]`, `verification.RANKABLE: frozenset[VerificationState]`, `verification.parse(raw: str) -> VerificationState`, `verification.RECORDS_DIR: Path`, `verification.record_path(model_id: str) -> Path`.

#### The four states

| State | Meaning | Ranked | Counted in cells-won |
|---|---|---|---|
| `self_reported` | the numbers are the submitter's, recomputed by us from their per-circuit evidence. Nothing has been re-run. | yes | yes |
| `reproduced` | our runner re-ran `predict.py` against ground truth on the submitter's declared test split and agreed within tolerance | yes | yes |
| `verified` | the same, on the canonical split from `data/registry/splits.json` | yes | yes |
| `disputed` | our runner ran and **disagreed** beyond tolerance | **no** | **no** |

Self-reported entries rank, and that is the hybrid trust model rather than an oversight.
A leaderboard that publishes nothing until a maintainer has re-run it is a leaderboard with one entry on it, and the honest alternative to withholding is labelling.

`disputed` does not rank because a cell state is a claim about a comparison, and we have measured that the number driving the comparison is wrong.
It is still **listed**, on the cell page and the model page, with both numbers side by side.
Phase 5 already separated those two questions: "the state colours the row; `entries` decides what is listed".
This is the second consumer of that separation, and the first was the degenerate cells.

#### Promotion is structural, not procedural

```
submissions/<model_id>/submission.yaml     untrusted, cannot carry a verification key
data/reproductions/<model_id>.json         maintainer-written, committed, the ONLY promoter
```

`publish` reads the state from the record and from nowhere else.
There is no argument, no flag and no environment variable that promotes an entry, and the bundle schema rejects the key outright, so the property holds without anyone having to remember it.

The lab's own ingested entries get `self_reported` too.
Their numbers arrive from the lab's `eval.log` and nothing in this repository reproduced them.
Calling them verified because of who produced them would be exactly the trust this phase refuses to extend to anyone else, and the lab is a submitter here like any other.

#### Reconciling with Phase 8's tiers

Phase 8 published a three-rung ladder whose ids are `self-reported`, `reproduced` and `verified`.
Two corrections, both listed in Inherited interfaces:

1. **Ids are underscored.** Every other machine-readable value in this project is (`beats_baseline`, `no_comparison`, `not_ranked`), and a `data-verification="self-reported"` beside a `data-state="beats_baseline"` is a trap for the next selector anyone writes. `Tier.id` becomes `self_reported`.
2. **A fourth tier, `disputed`, is added**, because a state the renderer can show and the ladder cannot name is a ladder that lies. It is the only rung that is not above the one before it, and `test_tiers_are_ordered_by_strictness` is restated to run over the three ascending rungs with `disputed` excluded by an explicit filter rather than by luck.

And the layer ids in `Tier.requires` and `Division.requires` are corrected to Phase 6's actual dict keys: `feature_stage` becomes `features`, `split_overlap` becomes `splits`, `division` becomes `divisions`.
Phase 8's own `test_every_tier_requires_only_guard_layers_that_exist` fails today against `tools/guard.LAYERS`; this is what makes it pass for the right reason instead of by weakening the assertion.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_verification.py`:

```python
"""The trust vocabulary, and the rule that only a committed record moves it."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import submission, verification
from tools.verification import VerificationState as V

TOOLS = Path(__file__).resolve().parent.parent / "tools"


def test_every_state_has_a_distinct_human_label() -> None:
    """The label is the without-colour channel. Two states sharing a label makes
    the channel decorative."""
    labels = [verification.LABELS[s.value] for s in V]
    assert len(set(labels)) == len(labels)
    assert all(label.strip() for label in labels)


def test_every_state_has_a_note_a_reader_can_act_on() -> None:
    for state in V:
        assert len(verification.NOTES[state.value]) > 40


def test_disputed_is_the_only_unrankable_state() -> None:
    """A cell state is a claim about a comparison. We have measured that the
    number driving this one is wrong, so it does not colour a cell. It is still
    listed."""
    assert verification.RANKABLE == frozenset(V) - {V.DISPUTED}


def test_an_unknown_state_raises_at_the_boundary() -> None:
    """Parsing through the enum is what makes a hand edited shard fail loudly
    rather than render an empty badge."""
    assert verification.parse("self_reported") is V.SELF_REPORTED
    with pytest.raises(ValueError):
        verification.parse("verified_by_me")


def test_the_default_is_the_weakest_state() -> None:
    """If a code path ever forgets to set one, it must forget DOWNWARDS."""
    assert verification.DEFAULT is V.SELF_REPORTED
    assert verification.DEFAULT not in {V.REPRODUCED, V.VERIFIED}


def test_the_tier_ladder_and_the_state_machine_are_the_same_vocabulary() -> None:
    """Phase 8 publishes the ladder at /submit/ and this module drives the
    renderer. Two vocabularies for one concept drift on the first rename."""
    assert {t.id for t in submission.TIERS} == {s.value for s in V}


def test_every_tier_id_is_underscored_like_every_other_machine_value() -> None:
    for tier in submission.TIERS:
        assert "-" not in tier.id, tier.id


def test_the_ascending_rungs_are_ordered_by_strictness() -> None:
    """disputed is not a rung above reproduced. It is excluded explicitly rather
    than by an ordering that happens to work."""
    ladder = [t for t in submission.TIERS if t.id != V.DISPUTED.value]
    required = [set(t.requires) for t in ladder]
    for lower, higher in zip(required, required[1:], strict=False):
        assert lower <= higher


def test_no_module_can_promote_an_entry_from_its_own_input() -> None:
    """THE test for ruling 1. The only assignment of REPRODUCED or VERIFIED in
    tools/ reads data/reproductions/. Grepped rather than mocked, because the
    property is "no such path exists" and a mock only proves one path."""
    offenders: list[str] = []
    for py in sorted(TOOLS.rglob("*.py")):
        text = py.read_text(encoding="utf-8")
        if (
            "VerificationState.REPRODUCED" in text
            or "VerificationState.VERIFIED" in text
        ):
            if py.name not in {"verification.py", "reproduce.py"}:
                offenders.append(py.name)
    assert not offenders, offenders


def test_a_missing_record_means_self_reported_and_never_raises() -> None:
    """No record is the normal case for every submission on day one."""
    assert verification.state_for("no-such-model", "t", "p", "s") is V.SELF_REPORTED


def test_the_record_directory_is_committed_and_documented() -> None:
    assert (verification.RECORDS_DIR / "README.md").is_file()
```

Append to `tests/test_submit.py`:

```python
def test_every_tier_requires_only_guard_layers_that_exist() -> None:
    """Restated. This assertion was already in the file and was false, because
    the tiers named feature_stage, split_overlap and division while the guard
    registers features, splits and divisions."""
    known = set(guard.LAYERS)
    for tier in submission.TIERS:
        assert set(tier.requires) <= known, (
            f"{tier.id} names {set(tier.requires) - known}"
        )


def test_the_reproduced_tier_does_not_claim_the_smoke_slice_scores_anything() -> None:
    """The smoke slice ships with NO target column, on purpose, so a metric
    cannot be computed from it. A tier description that says otherwise describes
    a promotion nobody can earn."""
    tier = next(t for t in submission.TIERS if t.id == "reproduced")
    assert "smoke" not in tier.description.lower()
    assert "ground truth" in tier.description.lower()
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_verification.py tests/test_submit.py -v`
Expected: FAIL, `ImportError: cannot import name 'verification' from 'tools'`, and the two `test_submit.py` assertions fail against the current tier data.

- [ ] **Step 3: Implement `tools/verification.py`**

```python
"""How much of an entry we have checked ourselves.

Four states. Three of them rank; disputed does not, because a cell state is a
claim about a comparison and we have measured that the number driving it is
wrong. A disputed entry is still LISTED, with both numbers, because hiding a
disagreement is a worse failure than publishing one.

Promotion is structural. The state is read from data/reproductions/<id>.json,
written by a maintainer command on a machine that has the ground truth, and
committed. The submission schema has no verification property and
additionalProperties is false, so a submitter cannot declare one. There is no
argument, flag or environment variable that promotes an entry, which is why the
property holds without anyone having to remember it.

The lab's own ingested entries are self_reported too. Their numbers come from the
lab's eval.log and nothing here reproduced them, and promoting them for who
produced them is exactly the trust this module refuses to extend to anyone else.
"""

from __future__ import annotations

import json
from enum import StrEnum
from functools import cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
RECORDS_DIR = ROOT / "data" / "reproductions"


class VerificationState(StrEnum):
    SELF_REPORTED = "self_reported"
    REPRODUCED = "reproduced"
    VERIFIED = "verified"
    DISPUTED = "disputed"


DEFAULT = VerificationState.SELF_REPORTED
"""What a code path that forgets to set one lands on. It forgets downwards."""

RANKABLE = frozenset(VerificationState) - {VerificationState.DISPUTED}

LABELS: dict[str, str] = {
    VerificationState.SELF_REPORTED.value: "Self-reported",
    VerificationState.REPRODUCED.value: "Reproduced",
    VerificationState.VERIFIED.value: "Verified",
    VerificationState.DISPUTED.value: "Disputed",
}
"""The text channel. State is distinguishable without colour because this string
is rendered, not because a class name differs."""

NOTES: dict[str, str] = {
    VerificationState.SELF_REPORTED.value: (
        "These numbers are the submitter's own, recomputed by us from the "
        "per-circuit values they published. Nothing has been re-run here."
    ),
    VerificationState.REPRODUCED.value: (
        "We re-ran this model against ground truth on the test split it declared "
        "and got the same numbers within the published tolerance."
    ),
    VerificationState.VERIFIED.value: (
        "We re-ran this model against ground truth on the canonical split and got "
        "the same numbers within the published tolerance."
    ),
    VerificationState.DISPUTED.value: (
        "We re-ran this model and did not get the numbers it declared. Both are "
        "shown. The entry is listed but is not ranked and wins no cell."
    ),
}


def parse(raw: str) -> VerificationState:
    """Through the enum, so an unknown value raises at the boundary.

    A shard that was hand edited into a state nothing recognises must fail rather
    than render an empty badge beside a real number.
    """
    return VerificationState(raw)


def record_path(model_id: str) -> Path:
    return RECORDS_DIR / f"{model_id}.json"


@cache
def _record(model_id: str) -> dict[str, Any] | None:
    path = record_path(model_id)
    if not path.is_file():
        return None
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("model_id") != model_id:
        raise ValueError(f"{path} declares a different model than its own filename")
    return payload


def state_for(
    model_id: str, task_id: str, pdk_id: str, stage_id: str
) -> VerificationState:
    """The state for one model on one combo. No record means self_reported.

    Absence is the normal case for every submission on day one, so it returns the
    default rather than raising.
    """
    payload = _record(model_id)
    if payload is None:
        return DEFAULT
    for result in payload["results"]:
        if (result["task"], result["pdk"], result["stage"]) == (
            task_id,
            pdk_id,
            stage_id,
        ):
            return parse(result["state"])
    return DEFAULT
```

Write `data/reproductions/README.md`: the record format, who may write one, and the one sentence that a record committed by anyone other than a maintainer running `eda-reproduce` on a machine holding the ground truth is a security incident and not a data entry error.

- [ ] **Step 4: Correct the Phase 8 tier data**

In `tools/submission.py`: underscore the three ids, correct the layer names in every `requires` tuple, rewrite the `reproduced` description so it does not claim the smoke slice scores anything, and add the fourth tier:

```python
(
    Tier(
        id="disputed",
        label="Disputed",
        requires=("features", "splits", "divisions", "plausibility"),
        reproduced=True,
        description=(
            "We re-ran this model against ground truth and did not get the "
            "numbers it declared. Both are published. The entry is listed and is "
            "not ranked."
        ),
    ),
)
```

and

```python
(
    Tier(
        id="reproduced",
        label="Reproduced",
        requires=("features", "splits", "divisions", "plausibility", "runnability"),
        reproduced=True,
        description=(
            "Your predict.py ran on our runner against ground truth for the test "
            "split you declared, and returned the reported metrics within "
            "tolerance."
        ),
    ),
)
```

`DIVISIONS` gets the same layer-id correction: `open` requires `("splits",)` and `closed` requires `("features", "splits", "divisions", "plausibility")`.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_verification.py tests/test_submit.py -v`
Expected: all pass.

- [ ] **Step 6: Verify lint and types**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy`
Expected: all clean.

- [ ] **Step 7: Commit**

```bash
git add tools/verification.py tools/submission.py data/reproductions/README.md \
        tests/test_verification.py tests/test_submit.py
git commit -m "feat(verification): four trust states, promotable only by a committed record"
```

---

### Task 3: The tolerance, and the runner that earns a promotion

**Files:**
- Create: `tools/reproduce.py`, `tests/fixtures/targets/**`
- Modify: `tools/ranking.py`, `tools/cellpage.py`, `tools/guard/runnability.py`, `data/registry/metrics.json`, `tools/registry.py`, `docs/DATA_CONTRACT.md`, `pyproject.toml`, `Makefile`
- Test: `tests/test_reproduce.py`, `tests/test_registry.py`

**Interfaces:**
- Consumes: `tools.registry`, `tools.evallog` (`macro_mean`, `median_positive`), `tools.ranking` (`PERCENT_SCALE`, `quantize`), `tools.guard.runnability` (`run_predict`), `tools.submissions`, `tools.verification`.
- Produces: `ranking.PERCENT_SCALE: float`, `ranking.quantize(task_id, metric_id, value) -> float`, `runnability.RunResult.predictions`, `reg.Metric.formula`, `reproduce.REL_TOL: float`, `reproduce.display_floor(task_id, metric_id) -> float`, `reproduce.tolerance(task_id, metric_id, declared) -> float`, `reproduce.agrees(task_id, metric_id, declared, reproduced) -> bool`, `reproduce.SCORERS: dict[str, Scorer]`, `reproduce.score(task_id, metric_id, predicted, actual) -> float`, `reproduce.Reproduction`, `reproduce.Record`, `reproduce.reproduce_unit(unit, targets) -> Reproduction`, `reproduce.main() -> int`, the `eda-reproduce` console script.

#### The tolerance, and why it is two numbers

```python
tolerance = max(REL_TOL * abs(declared), display_floor(task, metric))
REL_TOL = 1e-3
display_floor = 0.5 * 10 ** -precision(task, metric),  in STORAGE units
```

**The floor exists because of the display precision table in `docs/DATA_CONTRACT.md`.**
The reference implementation rounds five tasks' `mae`, `mpe`, `mne`, `mae_p95` and `mae_top5` to 4 decimal places and formats everything else to 2 or 3.
Publishing at `p` decimals means a difference smaller than half a unit in the last place is a difference **the site cannot show**.
Flagging a disagreement no reader could see would put a scarlet `disputed` badge on an entry that renders identically to the number it supposedly contradicts, which teaches a reader that the badge means nothing.
So the floor is exactly half an ulp of the published precision, and no tighter.

**The relative term exists because reproduction runs somebody else's code on a different machine.**
Summing 18 circuits in a different order, on a different BLAS, at float32, moves the last few significant figures.
`1e-3` is far coarser than that (float32 accumulation over 18 terms is around `1e-6` relative) and far finer than any real modelling difference: Table 8 itself publishes MAE as `1,781.97`, which is six significant figures, so a 0.1 % disagreement is already visible in the published digits.
A model whose reproduction differs by more than one part in a thousand did not differ because of arithmetic.

**Both terms are computed in storage units, and that conversion is the trap.**
`precision` is decimals of the **display** number, and percent metrics are displayed after a `x100`.
So a `mape` at 2 decimals has a display floor of `0.005` percentage points, which is `5e-5` as a fraction.
Getting that division backwards makes the tolerance a hundred times too wide on every percent metric, which does not raise and simply stops the disputed state from ever firing.

Worked, from real numbers, and both branches are live:

| Cell | precision | display floor (storage) | `REL_TOL * declared` | tolerance |
|---|---|---|---|---|
| `cell_arc_delay` `mae`, declared 0.0031 | 4 | 5.0e-5 | 3.1e-6 | **5.0e-5**, floor wins |
| `total_area` `mape`, declared 0.0742 | 2 | 5.0e-5 | 7.42e-5 | **7.42e-5**, relative wins |
| `total_area` `mae`, declared 911.98 | 2 | 5.0e-3 | 9.1e-1 | **9.1e-1**, relative wins |

`r2` carries one extra condition: `n_positive` must match **exactly**.
It is a count, not a measurement, and a reproduction that puts a different number of circuits above zero found a different model, whatever the median did.

#### What disagreement does

Nothing is corrected.
The published value stays the one computed from the submitter's own per-circuit evidence, the reproduced value is stored beside it, the state becomes `disputed`, and both render.
`make validate` prints a `FLAG` line naming the model and the cell so the disagreement is visible in CI output rather than only on the page.
A disputed entry is promoted only by a **new** reproduction record that agrees, which means a new maintainer run.

The alternative, overwriting the declared number with ours, would publish a number the submitter never claimed under their name, and would erase the only evidence that the two disagree.

#### Which metrics can be reproduced at all

Seven metrics have equations in the paper, at 9 to 15 on p.25 to 26: `mae`, `mape`, `r2`, `mpe`, `mne`, `tpr`, `tnr`.
The four tail metrics have **no equation**, only prose, which is PLAN.md open decision 4 and needs Pratik.
A reproduction of a formula we guessed is not a reproduction.

So `metrics.json` gains a `formula` field, `"published"` or `"unpinned"`, generated from the contract and cross-checked against it.
`reproduce` refuses an unpinned metric with a message naming the open decision, and those cells stay `self_reported` until it is ruled.
This puts the open decision in the registry where a test can see it, rather than in a comment.

`docs/DATA_CONTRACT.md` Appendix A's `metrics.json` table gains the column in Step 1, before any code reads it.
The contract is edited first because when the two disagree, the contract is wrong and gets fixed first.

- [ ] **Step 1: Add `formula` to the contract and the registry**

In `docs/DATA_CONTRACT.md`, Appendix A, add a `formula` column to the `metrics.json` table: `published` for `mae`, `mape`, `r2`, `mpe`, `mne`, `tpr`, `tnr`; `unpinned` for `mae_p95`, `mape_p95`, `mae_top5`, `mape_top5`.
Add one sentence under the existing "OPEN (no published formula)" block pointing at the field.

Append to `tests/test_registry.py`:

```python
def test_the_pinned_formula_set_is_exactly_the_paper_s_equations() -> None:
    """Equations 9 to 15 define seven metrics. The four tail metrics have prose
    and no equation, which is open decision 4. The registry says so in a field a
    test can read instead of in a comment nobody parses."""
    pinned = {m.id for m in reg.metrics() if m.formula == "published"}
    unpinned = {m.id for m in reg.metrics() if m.formula == "unpinned"}
    assert pinned | unpinned == {m.id for m in reg.metrics()}
    assert len(pinned) == 7
    assert unpinned == {"mae_p95", "mape_p95", "mae_top5", "mape_top5"}


def test_every_unpinned_metric_is_a_tail_metric() -> None:
    """The tail metrics are the only ones the paper describes without an
    equation. If a fifth appears here, someone widened the exemption."""
    for metric in reg.metrics():
        if metric.formula == "unpinned":
            assert metric.id.endswith(("_p95", "_top5"))
```

Add `formula: str` to `reg.Metric` and to `data/registry/metrics.json`.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_reproduce.py`:

```python
"""Tolerance, scoring, and the promotion that only a maintainer run can grant.

Expected values live here, in tests. They must never appear in tools/.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import reproduce, submissions
from tools import registry as reg
from tools.verification import VerificationState as V

TARGETS = Path(__file__).resolve().parent / "fixtures" / "targets"
TREES = Path(__file__).resolve().parent / "fixtures" / "submissions_tree"


def test_the_display_floor_is_half_an_ulp_of_the_published_precision() -> None:
    """Anything finer than this is a difference the site cannot render, so
    flagging it would put a disputed badge on two identical printed numbers."""
    assert reproduce.display_floor("cell_arc_delay_prediction", "mae") == 5e-5
    assert reproduce.display_floor("total_area_prediction", "mae") == 5e-3


def test_the_display_floor_of_a_percent_metric_is_in_storage_units() -> None:
    """THE conversion test. precision counts decimals of the DISPLAY number and
    percent metrics are displayed after a x100, so a 2dp mape floor is 0.005
    percentage points, which is 5e-5 as a fraction. Getting this backwards makes
    the tolerance a hundred times too wide and the disputed state never fires."""
    assert reg.metric("mape").percent
    assert reproduce.display_floor("total_area_prediction", "mape") == pytest.approx(
        5e-5
    )


def test_the_floor_wins_on_a_small_four_decimal_value() -> None:
    assert reproduce.tolerance("cell_arc_delay_prediction", "mae", 0.0031) == 5e-5


def test_the_relative_term_wins_on_a_large_value() -> None:
    assert reproduce.tolerance(
        "total_area_prediction", "mae", 911.9777
    ) == pytest.approx(0.9119777)


def test_agreement_is_symmetric_about_the_declared_value() -> None:
    declared = 0.0742
    tol = reproduce.tolerance("total_area_prediction", "mape", declared)
    assert reproduce.agrees("total_area_prediction", "mape", declared, declared + tol)
    assert reproduce.agrees("total_area_prediction", "mape", declared, declared - tol)
    assert not reproduce.agrees(
        "total_area_prediction", "mape", declared, declared + 10 * tol
    )


def test_a_percent_metric_disagreeing_by_one_hundredth_of_a_point_agrees() -> None:
    """7.42 % against 7.424 % prints identically at 2dp. It is not a dispute."""
    assert reproduce.agrees("total_area_prediction", "mape", 0.0742, 0.07424)


def test_a_percent_metric_disagreeing_by_half_a_point_disputes() -> None:
    assert not reproduce.agrees("total_area_prediction", "mape", 0.0742, 0.0790)


def test_an_unpinned_metric_refuses_to_score_rather_than_guessing() -> None:
    """The four tail metrics have prose and no equation. A reproduction of a
    formula we invented is not a reproduction."""
    with pytest.raises(reproduce.UnpinnedFormula) as excinfo:
        reproduce.score("interconnect_length_prediction", "mae_p95", [1.0], [1.0])
    assert "decision 4" in str(excinfo.value)


def test_the_scorer_set_is_exactly_the_registry_s_pinned_set() -> None:
    """Both directions. A formula in code that the registry does not know is a
    second vocabulary; a pinned metric with no scorer is a silent gap."""
    assert set(reproduce.SCORERS) == {
        m.id for m in reg.metrics() if m.formula == "published"
    }


def test_mape_is_scored_as_a_fraction_and_never_rescaled() -> None:
    """The single most dangerous bug in the project. Predicted 110 against an
    actual 100 is a MAPE of 0.1, not 10."""
    assert reproduce.score("total_area_prediction", "mape", [110.0], [100.0]) == (
        pytest.approx(0.1)
    )


def test_tpr_and_tnr_land_in_the_unit_interval() -> None:
    """They are rates and genuinely cannot exceed 1, so the assertion is free and
    catches a 100x error outright."""
    predicted = [-1.0, -2.0, 3.0, 4.0]
    actual = [-1.0, 5.0, 3.0, 4.0]
    for metric_id in ("tpr", "tnr"):
        value = reproduce.score("worst_slack_prediction", metric_id, predicted, actual)
        assert 0.0 <= value <= 1.0


def test_mpe_and_mne_are_positive_magnitudes_with_the_reference_sign() -> None:
    """err = predicted - actual, MPE = mean(err[err > 0]),
    MNE = mean(abs(err[err < 0])). That is what produced Table 8."""
    predicted = [3.0, -2.0]
    actual = [1.0, 1.0]
    assert reproduce.score("worst_slack_prediction", "mpe", predicted, actual) == 2.0
    assert reproduce.score("worst_slack_prediction", "mne", predicted, actual) == 3.0


def test_r2_disagrees_when_the_positive_count_moves_even_if_the_median_holds() -> None:
    """n_positive is a count, not a measurement. A reproduction that puts a
    different number of circuits above zero found a different model."""
    assert not reproduce.counts_agree(n_positive=0, reproduced_n_positive=3)
    assert reproduce.counts_agree(n_positive=0, reproduced_n_positive=0)


def test_aggregation_uses_the_same_two_functions_the_lab_ingest_uses() -> None:
    """Not a second macro-mean. Two copies of an aggregation rule in a project
    whose baseline and model sides already use different estimators is how the
    third estimator appears."""
    source = Path(__file__).resolve().parent.parent / "tools" / "reproduce.py"
    text = source.read_text(encoding="utf-8")
    assert "evallog.macro_mean" in text
    assert "evallog.median_positive" in text
    assert "statistics.median" not in text
    assert "sum(" not in text.split("def score")[0]


def test_a_reproduction_that_agrees_promotes_and_one_that_does_not_disputes(
    tmp_path: Path,
) -> None:
    bundle = submissions.read_bundle(TREES / "valid" / "acme-mlp")
    unit = submissions.expand(bundle)[0]

    agreeing = reproduce.reproduce_unit(unit, TARGETS, _stub_predictions=None)
    assert agreeing.state in {V.REPRODUCED, V.VERIFIED}

    disputing = reproduce.reproduce_unit(
        unit, TARGETS, _stub_predictions=lambda values: [v * 2.0 for v in values]
    )
    assert disputing.state is V.DISPUTED
    assert disputing.disagreements


def test_the_written_record_names_its_own_model_and_scope(tmp_path: Path) -> None:
    """A record whose filename and content disagree is a record that promotes the
    wrong model."""
    record = reproduce.Record(
        model_id="acme-mlp",
        scope="declared_split",
        ran_at="2026-08-11T00:00:00Z",
        tool_version="1",
        results=(),
    )
    path = reproduce.write_record(record, root=tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert path.name == "acme-mlp.json"
    assert payload["model_id"] == "acme-mlp"
    assert payload["scope"] in reproduce.SCOPES


def test_the_canonical_scope_is_the_only_route_to_verified() -> None:
    """reproduced is the submitter's declared split. verified is the canonical
    one from data/registry/splits.json. Conflating them would let a submitter
    pick an easy split and be labelled verified for it."""
    assert reproduce.SCOPES["declared_split"] is V.REPRODUCED
    assert reproduce.SCOPES["canonical_split"] is V.VERIFIED


def test_percent_scale_is_defined_exactly_once_in_tools() -> None:
    """Two copies of the percent scale in a project whose single most dangerous
    bug is a factor of a hundred. ranking._display_units had one and
    cellpage.format_value had the other."""
    root = Path(__file__).resolve().parent.parent / "tools"
    definitions = [
        py.name
        for py in sorted(root.rglob("*.py"))
        if "PERCENT_SCALE = " in py.read_text(encoding="utf-8")
    ]
    assert definitions == ["ranking.py"]
```

- [ ] **Step 3: Run to verify they fail**

Run: `uv run pytest tests/test_reproduce.py -v`
Expected: FAIL, `ImportError: cannot import name 'reproduce' from 'tools'`

- [ ] **Step 4: Promote the two shared names**

In `tools/ranking.py`, rename `_PERCENT_SCALE` to `PERCENT_SCALE` and `_quantize` to `quantize`, updating the two internal call sites.
Both are public now because two other modules need them and a copy is worse than an export.
`_display_units` stays private and stays the only thing that reads `PERCENT_SCALE` inside `ranking`; the module still exports no formatter, and `test_ranking_exports_no_formatter` still passes because neither new name contains "format" or "display".

In `tools/cellpage.py`, `format_value` uses `ranking.PERCENT_SCALE` instead of its own `100.0`.

In `tools/guard/runnability.py`, add `predictions: tuple[float, ...] = ()` to `RunResult` and populate it on the success path.
The layer already parses `payload["predictions"]` and throws it away; reproduction needs the numbers, and a second subprocess runner to get them would be a second sandbox.

- [ ] **Step 5: Implement `tools/reproduce.py`**

```python
"""Re-run a submission against ground truth, and record whether it agrees.

This is a MAINTAINER command. Scoring a prediction needs the target, and the only
committed artifact with feature rows is the guard's smoke slice, which carries no
target column on purpose. So this runs where the lab's data is checked out,
exactly like eda-ingest, and never on a fork PR runner.

That is also the security boundary. The record this writes is the only thing that
can promote an entry above self_reported, and it is written by a trusted machine
and committed by a human. Nothing a submitter controls reaches it.

Agreement is a tolerance, not equality:

    tolerance = max(REL_TOL * |declared|, half an ulp of the published precision)

The floor is there because a difference the site cannot print is not a difference
a reader can see. The relative term is there because reproduction runs somebody
else's code on another machine, and float accumulation over 18 circuits moves the
last few significant figures. Both are computed in STORAGE units, so the floor of
a percent metric is divided by the percent scale; getting that backwards widens
the tolerance a hundredfold and the disputed state never fires again.

Nothing is corrected. A disagreement is published as a disagreement.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools import evallog, ranking, submissions
from tools import registry as reg
from tools import verification
from tools.guard.runnability import run_predict
from tools.verification import VerificationState as V

REL_TOL = 1e-3
"""One part in a thousand.

Coarser than float32 accumulation over eighteen circuits by three orders of
magnitude, and finer than the six significant figures Table 8 itself publishes.
A reproduction outside it did not differ because of arithmetic.
"""

SCOPES: dict[str, V] = {
    "declared_split": V.REPRODUCED,
    "canonical_split": V.VERIFIED,
}
"""Which split was scored, and what that earns.

Conflating them would let a submitter choose an easy split and be labelled
verified for it.
"""

PUBLISHED = "published"
Scorer = Callable[[Sequence[float], Sequence[float]], float]
SCORERS: dict[str, Scorer] = {}


class UnpinnedFormula(RuntimeError):
    """Raised for a metric the paper describes in prose and never defines."""


def scorer(metric_id: str) -> Callable[[Scorer], Scorer]:
    """Bind one formula to one metric id.

    The id is a literal here because a formula has to name what it computes and
    the registry cannot hold an equation. The binding is asserted against
    reg.metrics() in both directions by tests/test_reproduce.py, so the registry
    stays the vocabulary and this file holds only the arithmetic. Same precedent
    as evallog._MEDIAN_METRICS.
    """

    def decorate(fn: Scorer) -> Scorer:
        SCORERS[metric_id] = fn
        return fn

    return decorate


@scorer("mae")
def _mae(predicted: Sequence[float], actual: Sequence[float]) -> float:
    return evallog.macro_mean(
        [abs(p - a) for p, a in zip(predicted, actual, strict=True)]
    )


@scorer("mape")
def _mape(predicted: Sequence[float], actual: Sequence[float]) -> float:
    """A FRACTION. Predicted 110 against an actual 100 is 0.1, never 10."""
    pairs = [(p, a) for p, a in zip(predicted, actual, strict=True) if a != 0.0]
    if not pairs:
        raise ValueError("MAPE over rows whose target is zero everywhere")
    return evallog.macro_mean([abs((p - a) / a) for p, a in pairs])


@scorer("r2")
def _r2(predicted: Sequence[float], actual: Sequence[float]) -> float:
    mean = evallog.macro_mean(list(actual))
    total = sum((a - mean) ** 2 for a in actual)
    residual = sum((a - p) ** 2 for p, a in zip(predicted, actual, strict=True))
    if total == 0.0:
        raise ValueError("R2 against a target with no variance")
    return 1.0 - residual / total


@scorer("mpe")
def _mpe(predicted: Sequence[float], actual: Sequence[float]) -> float:
    """Optimistic error. err = predicted - actual, mean over err > 0.

    Confirmed against the reference implementation that produced Table 8, and
    published as a positive magnitude where lower is better.
    """
    errors = [p - a for p, a in zip(predicted, actual, strict=True) if p - a > 0.0]
    return evallog.macro_mean(errors) if errors else 0.0


@scorer("mne")
def _mne(predicted: Sequence[float], actual: Sequence[float]) -> float:
    errors = [abs(p - a) for p, a in zip(predicted, actual, strict=True) if p - a < 0.0]
    return evallog.macro_mean(errors) if errors else 0.0


@scorer("tpr")
def _tpr(predicted: Sequence[float], actual: Sequence[float]) -> float:
    """Classification on the sign of slack. A violation is negative slack."""
    tp = sum(1 for p, a in zip(predicted, actual, strict=True) if a < 0 and p < 0)
    fn = sum(1 for p, a in zip(predicted, actual, strict=True) if a < 0 <= p)
    return tp / (tp + fn) if tp + fn else 0.0


@scorer("tnr")
def _tnr(predicted: Sequence[float], actual: Sequence[float]) -> float:
    tn = sum(1 for p, a in zip(predicted, actual, strict=True) if a >= 0 <= p)
    fp = sum(1 for p, a in zip(predicted, actual, strict=True) if a >= 0 > p)
    return tn / (tn + fp) if tn + fp else 0.0


def score(
    task_id: str, metric_id: str, predicted: Sequence[float], actual: Sequence[float]
) -> float:
    """One metric for one circuit. Refuses a metric the paper never defined."""
    reg.task(task_id)
    if reg.metric(metric_id).formula != PUBLISHED:
        raise UnpinnedFormula(
            f"{metric_id} has no published equation, only prose on p.25. "
            f"That is PLAN.md open decision 4 and it needs Pratik. Refusing to "
            f"reproduce a formula we invented."
        )
    return SCORERS[metric_id](predicted, actual)


def display_floor(task_id: str, metric_id: str) -> float:
    """Half a unit in the last published decimal place, in STORAGE units.

    precision counts decimals of the DISPLAY number, and a percent metric is
    displayed after multiplying by the percent scale, so its floor divides by the
    same constant. This is the one line where a hundredfold error hides.
    """
    half_ulp = 0.5 * 10.0 ** -reg.precision(task_id, metric_id)
    if reg.metric(metric_id).percent:
        return half_ulp / ranking.PERCENT_SCALE
    return half_ulp


def tolerance(task_id: str, metric_id: str, declared: float) -> float:
    return max(REL_TOL * abs(declared), display_floor(task_id, metric_id))


def agrees(task_id: str, metric_id: str, declared: float, reproduced: float) -> bool:
    return abs(reproduced - declared) <= tolerance(task_id, metric_id, declared)


def counts_agree(n_positive: int | None, reproduced_n_positive: int | None) -> bool:
    """R2 carries a count beside its median, and a count is not a measurement."""
    return n_positive == reproduced_n_positive
```

The record types and the runner:

```python
@dataclass(frozen=True, slots=True)
class Reproduction:
    """One combo re-run. Carries both numbers, always, agreeing or not."""

    task: str
    pdk: str
    stage: str
    state: V
    scope: str
    declared: dict[str, float]
    reproduced: dict[str, float]
    tolerances: dict[str, float]
    disagreements: tuple[str, ...]
    skipped: tuple[str, ...]
    n_circuits: int


@dataclass(frozen=True, slots=True)
class Record:
    model_id: str
    scope: str
    ran_at: str
    tool_version: str
    results: tuple[Reproduction, ...]


def _circuit_rows(
    targets: Path, circuit: str, target_column: str
) -> tuple[list[dict[str, float]], list[float]]:
    """Feature rows and the target column for one circuit."""
    with (targets / f"{circuit}.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    actual = [float(row[target_column]) for row in rows]
    features = [
        {k: float(v) for k, v in row.items() if k != target_column} for row in rows
    ]
    return features, actual


def reproduce_unit(
    unit: submissions.Unit,
    targets: Path,
    scope: str = "declared_split",
    _stub_predictions: Callable[[list[float]], list[float]] | None = None,
) -> Reproduction:
    """Re-run one claimed combo and compare, metric by metric.

    _stub_predictions exists for the tests and for nothing else: it replaces the
    subprocess with a pure function so agreement and disagreement are both
    exercised without shipping a fixture model. Production always passes None and
    goes through the guard's sandbox.
    """
    document = unit.document
    task_id, target = unit.task, document["target"]
    circuits = tuple(document["split"]["test"])

    declared_per_metric: dict[str, list[float]] = {}
    n_positive: int | None = None
    skipped: list[str] = []

    for circuit in circuits:
        features, actual = _circuit_rows(targets, circuit, target)
        if _stub_predictions is not None:
            predicted = _stub_predictions(actual)
        else:
            with tempfile.TemporaryDirectory() as tmp:
                _write_slice(Path(tmp) / "slice.csv", features)
                result = run_predict(
                    unit.directory / document["predict_entrypoint"], Path(tmp)
                )
            if not result.ok:
                raise RuntimeError(f"{unit.model_id} {circuit}: {result.message}")
            predicted = list(result.predictions)

        for metric_id in document["metrics"]:
            if reg.metric(metric_id).formula != PUBLISHED:
                if metric_id not in skipped:
                    skipped.append(metric_id)
                continue
            declared_per_metric.setdefault(metric_id, []).append(
                score(task_id, metric_id, predicted, actual)
            )

    reproduced: dict[str, float] = {}
    for metric_id, values in declared_per_metric.items():
        if reg.metric(metric_id).direction == ranking.HIGHER and metric_id == "r2":
            reproduced[metric_id], n_positive = evallog.median_positive(values)
        else:
            reproduced[metric_id] = evallog.macro_mean(values)

    declared = {
        metric_id: float(value)
        for metric_id, value in document["metrics"].items()
        if metric_id in reproduced
    }
    tolerances = {
        metric_id: tolerance(task_id, metric_id, declared[metric_id])
        for metric_id in declared
    }
    disagreements = tuple(
        metric_id
        for metric_id in sorted(declared)
        if not agrees(task_id, metric_id, declared[metric_id], reproduced[metric_id])
    )

    state = V.DISPUTED if disagreements else SCOPES[scope]
    return Reproduction(
        task=task_id,
        pdk=unit.pdk,
        stage=unit.stage,
        state=state,
        scope=scope,
        declared=declared,
        reproduced=reproduced,
        tolerances=tolerances,
        disagreements=disagreements,
        skipped=tuple(skipped),
        n_circuits=len(circuits),
    )
```

`write_record` serialises deterministically to `verification.record_path(model_id)` with `model_id` inside the payload as well as in the filename, and `main()` is the `eda-reproduce` entry point:

```bash
uv run eda-reproduce --model acme-mlp --targets ~/Downloads/eda-ml-targets \
                     --scope declared_split --write
```

Without `--write` it prints the comparison table and exits, which is what the reviewer runs.
With `--write` it writes the record, and the record is committed by a human in a separate step.
`main()` refuses `--write` when `--targets` is not a directory, so a run that silently scored nothing cannot produce a promoting record.

- [ ] **Step 6: Write the target fixtures**

`tests/fixtures/targets/{systemcaes,systemcdes,tv80}.csv`, three rows each, a handful of feature columns and one `total_area` column.
**These are ours, invented, not the lab's**, for the same reason no checkpoint is committed: the lab's data is CC BY-NC-SA and this repository is MIT.
Numbers are chosen so the fixture bundle's declared metrics agree exactly and doubling the predictions disagrees on every metric, which is what makes both branches of the state machine live.

- [ ] **Step 7: Wire the entry point**

`pyproject.toml`:

```toml
[project.scripts]
eda-validate = "tools.validate:main"
eda-baseline = "tools.baseline:main"
eda-ingest = "tools.ingest:main"
eda-reproduce = "tools.reproduce:main"
```

`Makefile`, and note it is deliberately **not** in `check`, for the same reason `ingest` is not: a gate that regenerates tracked files lets a changed input silently rewrite committed data instead of failing.

```make
TARGETS ?= ../eda-schema-targets

reproduce:
	@if [ ! -f tools/reproduce.py ]; then echo "reproduce: tools/reproduce.py does not exist yet (Phase 10)"; exit 1; fi; uv run eda-reproduce --targets $(TARGETS) $(ARGS)
```

- [ ] **Step 8: Run the tests**

Run: `uv run pytest tests/test_reproduce.py tests/test_registry.py tests/test_ranking.py tests/test_cells.py -v`
Expected: all pass, including the Phase 4 and Phase 5 suites after the `PERCENT_SCALE` promotion.

Then look at the tolerance table by hand, because the reviewer will:

```bash
uv run python -c "
from tools import reproduce
for task, metric, declared in [
    ('cell_arc_delay_prediction', 'mae', 0.0031),
    ('total_area_prediction', 'mape', 0.0742),
    ('total_area_prediction', 'mae', 911.9777),
]:
    print(f'{task:34} {metric:5} declared={declared:<12} '
          f'floor={reproduce.display_floor(task, metric):<10.3g} '
          f'tol={reproduce.tolerance(task, metric, declared):.6g}')
"
```

Expected: the three rows of the worked table above, with the floor winning on the first and the relative term on the other two.

- [ ] **Step 9: Commit**

```bash
git add tools/reproduce.py tools/ranking.py tools/cellpage.py tools/guard/runnability.py \
        tools/registry.py data/registry/metrics.json docs/DATA_CONTRACT.md \
        pyproject.toml Makefile tests/fixtures/targets tests/test_reproduce.py \
        tests/test_registry.py
git commit -m "feat(reproduce): score a submission against ground truth within a stated tolerance"
```

---

### Task 4: From `submission.yaml` to a shard entry, and back out through `shards.load`

The task the phase exists for.
It writes and it reads in one task, because a writer whose output nothing reads is the audit finding this whole plan is shaped around.

**Files:**
- Create: `tools/publish.py`
- Modify: `tools/shards.py`, `tools/ingest.py`, `pyproject.toml`, `Makefile`
- Create: `data/published/**` (generated)
- Modify: `tests/test_ingest.py`, `tests/test_shards.py`
- Test: `tests/test_publish.py`

**Interfaces:**
- Consumes: `tools.submissions`, `tools.verification`, `tools.reproduce`, `tools.evallog`, `tools.ingest`, `tools.shards` (`PUBLISHED_DIR`, `published_shard_path`), `tools.registry`.
- Produces: `ingest.Entry.verification: str`, `ingest.Entry.reproduction: dict[str, Any] | None`, `ingest.LAB_VERIFICATION: str`, `shards.PUBLISHED_DIR: Path`, `shards.published_shard_path(task_id, pdk_id, stage_id) -> Path`, `shards.Record.verification: str`, `shards.merge_entries(lab, published) -> tuple[Entry, ...]`, `publish.entry_for(unit, record) -> ingest.Entry`, `publish.shard_for(task_id, pdk_id, stage_id, units) -> ingest.Shard | None`, `publish.publish(root, out) -> tuple[Path, ...]`, `publish.main() -> int`, the `eda-publish` console script.

#### Two trees, one reader

```
data/cells/<task>/<pdk>/<stage>.json         eda-ingest owns it, from the lab's results tree
data/published/<task>/<pdk>/<stage>.json     eda-publish owns it, from submissions/
```

Each command is a **full regeneration of its own tree from its own source**.
That is what makes the merge safe without a merge algorithm: `make ingest` after a fresh lab training run cannot delete a community entry, because it never opens the file the community entry is in, and `make publish` cannot delete the lab's, for the same reason.
The alternative, both writing one file and one of them merging, has a failure mode where a regeneration silently truncates and the diff looks like a legitimate rewrite.

`shards.load` is the single union point, which it already was between `ingest.Entry` and `shards.Record`.
Lab entries come first, published entries follow in `model_id` order, and a `model_id` present in both raises.
That collision is unreachable through the supported path, because `publish` rejects `ingest.LAB_MODEL_ID` as a submission directory name, so if it ever fires somebody hand-edited `data/`, which the contract forbids.
It raises rather than picking a winner, because either winner is wrong.

`PUBLISHED_DIR` lives in `shards.py` rather than `publish.py` on purpose: `shards` is imported by `build.py` on every page, and having it import `publish` would drag `submissions`, `guard` and `jsonschema` into the site build. The reader owns both paths; the writer imports the one it needs.

#### `entry_for`, the one constructor from untrusted input

```
per_circuit  ->  evallog.macro_mean / evallog.median_positive  ->  MetricValue.macro
                                    \
declared metrics  -----------------> compared at reproduce.tolerance, never stored
```

**We never store the submitter's aggregate.**
A single declared number carries no evidence of how it was reduced, so enforcing "macro-mean across circuits, median for R2 with a positive count" against it is impossible.
Against per-circuit evidence it is not only possible, it is the same two function calls the lab's own ingest makes, so both sides of the leaderboard are reduced by identical code.

The declared aggregate is still checked.
A submitter who pooled instead of macro-meaning disagrees with our recomputation, and that is caught **before their model is ever run**, at publish time, with no ground truth needed.
The disagreement is recorded as `aggregate_dispute` on the entry and flagged by `make validate`.

Four refusals, all before an `Entry` exists:

| Refusal | Why |
|---|---|
| `reg.is_void(task, stage)` | the paper says the cell does not exist; a shard there resurrects a structural hole |
| `model_id == ingest.LAB_MODEL_ID` | the reserved seed identity |
| `per_circuit` keys differ from `split.test` | dropping the circuit you did worst on is cherry-picking, and it is invisible in an aggregate |
| a `tpr` or `tnr` outside `[0, 1]` | a true rate cannot exceed 1, so the assertion is free and catches a 100x error outright. There is deliberately **no** MAPE range guard: it is unbounded above and 48 real published cells exceed 150 %. |

- [ ] **Step 1: Write the failing tests**

Create `tests/test_publish.py`:

```python
"""A submission becomes a shard entry, and the lab's entries survive it.

Expected values live here, in tests. They must never appear in tools/.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import ingest, publish, shards, submissions
from tools import registry as reg
from tools.verification import VerificationState as V

TREES = Path(__file__).resolve().parent / "fixtures" / "submissions_tree"
COMBO = ("total_area_prediction", "ng45", "floorplan")


@pytest.fixture
def published(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A real publish run into a temp tree, with every reader cache cleared."""
    out = tmp_path / "published"
    monkeypatch.setattr(shards, "PUBLISHED_DIR", out)
    shards.load.cache_clear()
    shards.populated_combos.cache_clear()
    publish.publish(TREES / "valid", out)
    yield out
    shards.load.cache_clear()
    shards.populated_combos.cache_clear()


def test_a_submission_becomes_an_entry_in_the_combo_it_claims(published: Path) -> None:
    payload = json.loads(
        (published / "total_area_prediction" / "ng45" / "floorplan.json").read_text(
            encoding="utf-8"
        )
    )
    assert [e["model_id"] for e in payload["entries"]] == ["acme-mlp", "beta-gnn"]


def test_nothing_is_written_for_a_combo_nobody_claimed(published: Path) -> None:
    """Partial coverage is the normal case. No placeholder entry, no empty file,
    because an empty file is indistinguishable from a combo that was published
    and then emptied."""
    assert not (published / "cell_arc_slew_prediction").exists()


def test_the_aggregate_is_recomputed_and_the_declared_one_is_never_stored(
    published: Path,
) -> None:
    """A single declared number carries no evidence of how it was reduced. We
    reduce the per-circuit evidence ourselves, with the same two functions the
    lab's ingest uses, so both sides of the leaderboard use one estimator."""
    payload = json.loads(
        (published / "total_area_prediction" / "ng45" / "floorplan.json").read_text(
            encoding="utf-8"
        )
    )
    entry = payload["entries"][0]
    assert entry["metrics"]["mae"]["macro"] == pytest.approx((700 + 900 + 950) / 3)
    assert entry["metrics"]["mae"]["ranked_on"] == "macro"
    assert entry["metrics"]["mae"]["n_circuits"] == 3
    assert "declared" not in entry["metrics"]["mae"]


def test_r2_is_a_median_with_a_positive_count_and_not_a_mean(published: Path) -> None:
    payload = json.loads(
        (published / "total_area_prediction" / "ng45" / "floorplan.json").read_text(
            encoding="utf-8"
        )
    )
    r2 = payload["entries"][0]["metrics"]["r2"]
    assert r2["macro"] == pytest.approx(-1.8)
    assert r2["n_positive"] == 0


def test_a_submitter_who_pooled_instead_of_macro_meaning_is_caught(
    tmp_path: Path,
) -> None:
    """Before their model is ever run, and with no ground truth needed."""
    paths = publish.publish(TREES / "declared_aggregate_wrong", tmp_path)
    payload = json.loads(paths[0].read_text(encoding="utf-8"))
    assert payload["entries"][0]["aggregate_dispute"]


def test_every_published_entry_declares_its_source_and_its_verification(
    published: Path,
) -> None:
    for path in sorted(published.rglob("*.json")):
        for entry in json.loads(path.read_text(encoding="utf-8"))["entries"]:
            assert entry["source"] == ingest.SUBMISSION
            assert entry["verification"] == V.SELF_REPORTED.value


def test_a_submission_with_a_reproduction_record_is_promoted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """And the ONLY input that promotes it is the record."""
    from tools import verification

    monkeypatch.setattr(verification, "RECORDS_DIR", TREES / "records")
    verification._record.cache_clear()
    paths = publish.publish(TREES / "valid", tmp_path)
    entries = [
        e
        for path in paths
        for e in json.loads(path.read_text(encoding="utf-8"))["entries"]
        if e["model_id"] == "acme-mlp"
    ]
    assert {e["verification"] for e in entries} == {V.REPRODUCED.value}
    verification._record.cache_clear()


def test_a_disputed_entry_publishes_both_numbers_and_is_not_corrected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ruling 1. The declared value stays the published one and the reproduced
    value sits beside it. Overwriting would publish a number under a name that
    never claimed it, and would erase the evidence they disagree."""
    from tools import verification

    monkeypatch.setattr(verification, "RECORDS_DIR", TREES / "records_disputed")
    verification._record.cache_clear()
    paths = publish.publish(TREES / "valid", tmp_path)
    entry = next(
        e
        for path in paths
        for e in json.loads(path.read_text(encoding="utf-8"))["entries"]
        if e["model_id"] == "acme-mlp"
    )
    assert entry["verification"] == V.DISPUTED.value
    assert entry["metrics"]["mae"]["macro"] == pytest.approx((700 + 900 + 950) / 3)
    assert (
        entry["reproduction"]["reproduced"]["mae"] != entry["metrics"]["mae"]["macro"]
    )
    assert "mae" in entry["reproduction"]["disagreements"]
    verification._record.cache_clear()


def test_re_submission_replaces_in_place_and_does_not_duplicate(
    tmp_path: Path,
) -> None:
    """model_id is the directory name and is the identity. Editing the file and
    re-publishing is an update, not a second row, and not a reordering."""
    first = publish.publish(TREES / "valid", tmp_path)
    before = json.loads(first[0].read_text(encoding="utf-8"))
    second = publish.publish(TREES / "valid_edited", tmp_path)
    after = json.loads(second[0].read_text(encoding="utf-8"))
    assert [e["model_id"] for e in before["entries"]] == [
        e["model_id"] for e in after["entries"]
    ]
    assert (
        before["entries"][0]["metrics"]["mae"]["macro"]
        != after["entries"][0]["metrics"]["mae"]["macro"]
    )


def test_a_submission_may_not_take_the_lab_s_reserved_id(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=ingest.LAB_MODEL_ID):
        publish.publish(TREES / "reserved_id", tmp_path)


def test_a_void_combo_is_refused(tmp_path: Path) -> None:
    """The registry says the cell does not exist. Task 1 refuses it at parse
    time and this refuses it again at construction, because the two boundaries
    have different callers."""
    with pytest.raises(ValueError):
        publish.publish(TREES / "void_combo", tmp_path)


def test_per_circuit_keys_must_be_exactly_the_declared_test_split(
    tmp_path: Path,
) -> None:
    """Dropping the circuit you did worst on is invisible in an aggregate."""
    with pytest.raises(ValueError, match="test split"):
        publish.publish(TREES / "cherry_picked_circuits", tmp_path)


def test_a_rate_outside_the_unit_interval_is_refused(tmp_path: Path) -> None:
    """tpr and tnr are true rates and cannot exceed 1, so this catches a 100x
    error outright. There is no MAPE range guard, deliberately."""
    with pytest.raises(ValueError, match="tpr"):
        publish.publish(TREES / "percent_as_display_units", tmp_path)


def test_no_mape_range_assertion_exists() -> None:
    """48 real published cells exceed 150 percent and its ceiling is the
    >10000 % sentinel. A range guard here would reject them."""
    text = (Path(__file__).resolve().parent.parent / "tools" / "publish.py").read_text(
        encoding="utf-8"
    )
    assert "mape" not in text.lower().split("def _rates")[0]


def test_a_saturated_cell_still_stores_the_entry(tmp_path: Path) -> None:
    """Saturated cells are never RANKED. That is a display and ordering rule,
    not a reason to discard a real measurement."""
    paths = publish.publish(TREES / "saturated_claim", tmp_path)
    payload = json.loads(paths[0].read_text(encoding="utf-8"))
    assert reg.is_saturated(payload["task"], "mae", payload["stage"])
    assert payload["entries"][0]["metrics"]["mae"]["macro"] > 0


def test_the_json_is_deterministic(published: Path) -> None:
    path = published / "total_area_prediction" / "ng45" / "floorplan.json"
    first = path.read_text(encoding="utf-8")
    publish.publish(TREES / "valid", published)
    assert path.read_text(encoding="utf-8") == first
```

Append to `tests/test_shards.py`:

```python
def test_the_reader_unions_the_lab_tree_and_the_published_tree(
    published_combo,
) -> None:
    """Two generators, two trees, one reader. Neither command opens the other's
    file, so a full regeneration of either cannot delete the other's entries."""
    records = shards.load(*COMBO)
    assert {r.model_id for r in records} == {ingest.LAB_MODEL_ID, "acme-mlp"}


def test_the_lab_entry_comes_first_and_submissions_follow_in_id_order(
    published_combo,
) -> None:
    ids = [r.model_id for r in shards.load(*COMBO) if r.metric == "mae"]
    assert ids[0] == ingest.LAB_MODEL_ID
    assert ids[1:] == sorted(ids[1:])


def test_a_model_id_present_in_both_trees_raises(published_collision) -> None:
    """Unreachable through the supported path, because publish rejects the
    reserved id. If it fires, data/ was hand edited, and either winner is
    wrong."""
    with pytest.raises(ValueError, match="appears in both"):
        shards.load(*COMBO)


def test_every_record_carries_a_verification_state(published_combo) -> None:
    """A record without one is an error, not a default. The same rule as source:
    make validate fails rather than guessing."""
    for record in shards.load(*COMBO):
        assert V(record.verification)


def test_a_shard_entry_without_a_verification_state_raises(tmp_path) -> None: ...
```

Append to `tests/test_ingest.py`:

```python
def test_the_lab_s_own_entries_are_self_reported_too() -> None:
    """Their numbers come from the lab's eval.log and nothing here reproduced
    them. Promoting them for who produced them is exactly the trust this project
    refuses to extend to anyone else."""
    entry = ingest.combo_shard(COMBO).entries[0]
    assert entry.verification == V.SELF_REPORTED.value
    assert entry.reproduction is None
```

and amend the existing `test_the_json_round_trips_and_is_deterministic` entry key set to include `verification` and `reproduction`.

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_publish.py tests/test_shards.py tests/test_ingest.py -v`
Expected: FAIL, `ImportError: cannot import name 'publish' from 'tools'`, and the two amended Phase 4 tests fail on the entry key set.

- [ ] **Step 3: Write the remaining fixture trees**

Under `tests/fixtures/submissions_tree/`: `valid_edited` (one metric changed), `declared_aggregate_wrong` (a pooled-looking declared aggregate), `reserved_id` (a directory named `lab-fixed-mlp`), `void_combo`, `cherry_picked_circuits`, `percent_as_display_units` (`tpr: 87.0`), `saturated_claim` (a `global_route` combo).
Plus `records/acme-mlp.json` and `records_disputed/acme-mlp.json`, two reproduction records written by hand to the format `reproduce.write_record` emits.

- [ ] **Step 4: Extend `ingest.Entry` and regenerate the lab shards**

In `tools/ingest.py`:

```python
LAB_VERIFICATION = verification.VerificationState.SELF_REPORTED.value
"""The lab's numbers arrive from their own eval.log and nothing here reproduced
them. Promoting them for who produced them is the trust this project refuses to
extend to anyone else, and the lab is a submitter here like any other."""
```

Add `verification: str` and `reproduction: dict[str, Any] | None` to `Entry`, set them in `combo_shard`, and serialise them in `to_json` between `source` and `architecture`.
Then regenerate:

```bash
make ingest
git diff --stat data/cells
```

Expected: 20 files changed, two added lines each.
A larger diff means something other than the new fields moved and the run must be rejected rather than committed.

- [ ] **Step 5: Implement `tools/publish.py`**

```python
"""Turn merged submissions into shards under data/published/.

This is the publish path the first nine phases did not have. A third party could
submit, clear every guard layer, get merged, and appear nowhere on the site.

Two trees, one reader. eda-ingest owns data/cells/ and this owns
data/published/; each is a full regeneration of its own tree from its own source,
so neither can delete the other's entries. shards.load unions them.

The aggregate is RECOMPUTED from the submitter's per-circuit evidence with the
same two functions the lab's ingest uses. The declared aggregate is never stored.
A single number carries no evidence of how it was reduced, so the rule cannot be
enforced against it; against per-circuit values it is enforced by construction,
and a submitter who pooled instead of macro-meaning is caught here, before their
model is ever run.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools import evallog, ingest, reproduce, shards, submissions, verification
from tools import registry as reg

RATE_METRICS_NOTE = "a true rate cannot exceed 1"


def _rates(document: dict[str, Any]) -> None:
    """tpr and tnr must land in [0, 1] after no conversion at all.

    They are rates, so the assertion is free and catches a submission written in
    display units outright. There is deliberately no MAPE guard: MAPE is
    unbounded above, its ceiling is the >10000 % sentinel, and 48 real published
    cells exceed 150 %.
    """
    for metric_id, value in document["metrics"].items():
        metric = reg.metric(metric_id)
        if metric.percent and metric.direction == "higher" and not 0.0 <= value <= 1.0:
            raise ValueError(
                f"{metric_id}={value} is outside [0, 1]; {RATE_METRICS_NOTE}. "
                f"Percent metrics are declared as fractions."
            )


def _aggregate(unit: submissions.Unit) -> dict[str, ingest.MetricValue]:
    """One MetricValue per metric, reduced from the per-circuit evidence."""
    document = unit.document
    per_circuit = document["per_circuit"]
    declared_test = set(document["split"]["test"])
    if set(per_circuit) != declared_test:
        raise ValueError(
            f"{unit.model_id} {unit.task}: per_circuit covers {sorted(per_circuit)} "
            f"but the declared test split is {sorted(declared_test)}. Aggregating "
            f"over a subset of your own test split is not the same measurement."
        )

    metrics: dict[str, ingest.MetricValue] = {}
    for metric_id in document["metrics"]:
        values = [float(per_circuit[c][metric_id]) for c in sorted(per_circuit)]
        if reg.metric(metric_id).direction == "higher" and metric_id == "r2":
            macro, positive = evallog.median_positive(values)
        else:
            macro, positive = evallog.macro_mean(values), None
        metrics[metric_id] = ingest.MetricValue(
            macro=macro,
            pooled=None,
            ranked_on=ingest.MACRO,
            n_circuits=len(values),
            n_positive=positive,
        )
    return metrics


def _aggregate_dispute(
    unit: submissions.Unit, metrics: dict[str, ingest.MetricValue]
) -> tuple[str, ...]:
    """Metrics where the submitter's own aggregate disagrees with ours.

    The signature of pooling instead of macro-meaning, visible with no ground
    truth and before any model runs.
    """
    return tuple(
        metric_id
        for metric_id, declared in sorted(unit.document["metrics"].items())
        if not reproduce.agrees(
            unit.task, metric_id, float(declared), metrics[metric_id].macro
        )
    )


def entry_for(unit: submissions.Unit) -> ingest.Entry:
    """The one constructor of an Entry from untrusted input."""
    if reg.is_void(unit.task, unit.stage):
        raise ValueError(f"refusing a void combo: {unit.task} {unit.stage}")
    if unit.model_id == ingest.LAB_MODEL_ID:
        raise ValueError(f"{ingest.LAB_MODEL_ID} is reserved for the seed entry")

    _rates(unit.document)
    metrics = _aggregate(unit)
    state = verification.state_for(unit.model_id, unit.task, unit.pdk, unit.stage)

    return ingest.Entry(
        model_id=unit.model_id,
        model_label=str(unit.document["model_label"]),
        family=str(unit.document["model"]["family"]),
        source=ingest.SUBMISSION,
        architecture=None,
        metrics=metrics,
        verification=state.value,
        reproduction=verification.reproduction_for(
            unit.model_id, unit.task, unit.pdk, unit.stage
        ),
        aggregate_dispute=_aggregate_dispute(unit, metrics),
    )
```

`shard_for` groups the units of every bundle by combo, sorts entries by `model_id`, and returns `None` for a combo nobody claimed so that `publish` writes no file at all.
`publish(root, out)` clears the output tree first, so a deleted submission directory removes its shards rather than leaving an orphan, and returns the paths it wrote.
`main()` is `eda-publish`, printing `publish: wrote N shards for M submissions` and returning 1 when `submissions.discover()` reports any error, so a malformed tree cannot produce a partial publish that looks complete.

- [ ] **Step 6: Extend `tools/shards.py`**

```python
PUBLISHED_DIR = ROOT / "data" / "published"


def published_shard_path(task_id: str, pdk_id: str, stage_id: str) -> Path:
    """data/published/<task>/<pdk>/<stage>.json.

    Lives here rather than in publish.py because build.py imports this module on
    every page, and importing publish would drag submissions, guard and
    jsonschema into the site build. The reader owns both paths.
    """
    return (
        PUBLISHED_DIR
        / reg.task(task_id).id
        / reg.pdk(pdk_id).id
        / f"{reg.stage(stage_id).id}.json"
    )
```

`load` reads both paths through one `_records_from(path, ...)` helper, adds `verification=entry["verification"]` to every `Record` and raises when the key is missing, exactly as it already raises on a missing `source`.
The union raises on a `model_id` in both trees:

```python
    lab = _records_from(shard_path(task_id, pdk_id, stage_id), task_id, pdk_id, stage_id)
    published = _records_from(
        published_shard_path(task_id, pdk_id, stage_id), task_id, pdk_id, stage_id
    )
    collisions = {r.model_id for r in lab} & {r.model_id for r in published}
    if collisions:
        raise ValueError(
            f"{sorted(collisions)} appears in both data/cells and data/published; "
            f"either winner would be wrong"
        )
    return lab + published
```

- [ ] **Step 7: Wire the entry point and generate**

`pyproject.toml` gains `eda-publish = "tools.publish:main"`.
`Makefile` gains a `publish` target with the same "does not exist yet" guard as the others, and it stays **out** of `check`.

```bash
make publish
find data/published -name '*.json' | wc -l
```

Expected on a repository whose `submissions/` holds only the README: `publish: wrote 0 shards for 0 submissions`, and no `data/published/` tree.
That is the correct day-one state and the tests cover it.

- [ ] **Step 8: Run the tests**

Run: `uv run pytest tests/test_publish.py tests/test_shards.py tests/test_ingest.py -v`
Expected: all pass.

Then prove the union by hand, which is the claim the whole task rests on:

```bash
uv run python -c "
from tools import publish, shards
from pathlib import Path
publish.publish(Path('tests/fixtures/submissions_tree/valid'), shards.PUBLISHED_DIR)
shards.load.cache_clear()
for r in shards.load('total_area_prediction', 'ng45', 'floorplan'):
    if r.metric == 'mae':
        print(f'{r.model_id:16} {r.source:11} {r.verification:14} {r.value_macro:.4f}')
"
make ingest
uv run python -c "
from tools import shards
shards.load.cache_clear()
print(sorted({r.model_id for r in shards.load('total_area_prediction','ng45','floorplan')}))
"
git checkout data/published 2>/dev/null; rm -rf data/published
```

Expected: the lab entry and both submissions before the re-ingest, and **the same three after it**.
A re-ingest that drops the submissions is the exact failure this design exists to make impossible.

- [ ] **Step 9: Commit**

```bash
git add tools/publish.py tools/shards.py tools/ingest.py pyproject.toml Makefile \
        data/cells tests/fixtures/submissions_tree tests/test_publish.py \
        tests/test_shards.py tests/test_ingest.py
git commit -m "feat(publish): turn a merged submission into ranked shard entries"
```

---

### Task 5: Rendering trust, without colour, from untrusted strings

Two rules that pull in opposite directions: the verification state must be loud, and everything a submitter wrote must be inert.

**Files:**
- Modify: `tools/cellpage.py`, `templates/pages/cell.html`, `templates/pages/matrix.html`, `static/css/cell.css`, `static/css/base.css`, `build.py`
- Test: `tests/test_publish_render.py`, `tests/test_cells.py`

**Interfaces:**
- Consumes: `tools.verification` (`LABELS`, `NOTES`, `RANKABLE`, `parse`), `tools.shards.Record.verification`, `tools.ranking`.
- Produces: `cellpage.Entry.verification`, `cellpage.Entry.verification_label`, `cellpage.Entry.reproduced_display`, `cellpage.Entry.tolerance_display`, `cellpage.MetricRow.disputed: int`, `cellpage.MetricRow.self_reported: int`, `CellPage.verification_labels`, `CellPage.verification_glyphs`, a `has_self_reported` and `has_disputed` key on every matrix cell context, and the DOM contract `tr[data-model][data-source][data-verdict][data-verification]`.

#### Distinguishable without colour

The four states are told apart by a **rendered text label**, `verification.LABELS[state]`, in its own column.
That is the primary channel, and it works in greyscale, in a screen reader and in a printout.
A glyph runs alongside it and is `aria-hidden`, because it is a redundant second channel and announcing it would double every row.
Colour is the third channel and carries nothing on its own.

This is deliberately the same shape as Phase 7's synthetic marker: a glyph beside the state colour rather than instead of it.
Two markers can co-occur on one entry, a synthetic-source row that is also self-reported, so they occupy different columns rather than competing for one badge.

`disputed` gets more than a badge.
A panel above the ranking table, in the same position Phase 5 put the saturated notice and Phase 7 put the synthetic notice, naming the metric that disagreed, both numbers and the tolerance that was applied.
Above the table, not below: a reader who stops at the first number must have seen it.

#### Disputed entries are listed and not ranked

```python
bounds = tuple(
    shards.bound_of(r) for r in records
    if verification.parse(r.verification) in verification.RANKABLE
)
state = ranking.cell_state(task_id, metric_id, stage_id, bound, bounds)
```

The entry list is built from **all** records.
Phase 5 already separated "what colours the row" from "what is listed", for the degenerate cells; this is the second consumer of that separation and it is why the separation was worth having.
A disputed entry renders with an empty verdict and no rank, exactly like an entry on a degenerate cell.

#### Untrusted strings

`model_label`, `authors` and `family` are written by a submitter and rendered into HTML.
Three surfaces carry them: the cell page, the inlined payload the filter JS reads, and the model page JSON.
Jinja2 autoescaping covers the first, `textContent` covers the second, and `json.dumps` plus a `</script>` escape covers the third.

The test is not "we remembered to escape".
It is a fixture whose `model_label` is `<img src=x onerror=alert(1)>` published into a real build, with an assertion on every one of the three surfaces.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_publish_render.py`:

```python
"""Trust, rendered. And submitter strings, rendered inert."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tools import verification
from tools.verification import VerificationState as V

XSS = "<img src=x onerror=alert(1)>"


def test_every_verification_state_renders_its_text_label(published_site: Path) -> None:
    """The label IS the without-colour channel. A class name is not a channel."""
    html = (published_site / "cell" / "total_area_prediction" / "ng45" /
            "floorplan" / "index.html").read_text(encoding="utf-8")
    assert verification.LABELS[V.SELF_REPORTED.value] in html
    assert 'data-verification="self_reported"' in html


def test_the_glyph_is_hidden_from_assistive_technology(published_site: Path) -> None:
    """It is a redundant second channel. Announcing it doubles every row."""
    html = (published_site / "cell" / "total_area_prediction" / "ng45" /
            "floorplan" / "index.html").read_text(encoding="utf-8")
    for match in re.finditer(r'<span class="glyph[^"]*"([^>]*)>', html):
        assert "aria-hidden" in match.group(1)


def test_a_self_reported_entry_is_never_presentable_as_verified(
    published_site: Path,
) -> None:
    """Ruling 1. Checked on the rendered bytes, not on the context dict."""
    html = (published_site / "cell" / "total_area_prediction" / "ng45" /
            "floorplan" / "index.html").read_text(encoding="utf-8")
    for row in re.findall(r"<tr [^>]*data-verification=\"self_reported\".*?</tr>", html, re.S):
        assert verification.LABELS[V.VERIFIED.value] not in row
        assert verification.LABELS[V.REPRODUCED.value] not in row


def test_a_disputed_entry_shows_both_numbers_above_the_ranking(
    disputed_site: Path,
) -> None:
    html = (disputed_site / "cell" / "total_area_prediction" / "ng45" /
            "floorplan" / "index.html").read_text(encoding="utf-8")
    assert "notice-disputed" in html
    assert html.index("notice-disputed") < html.index("<table")
    assert verification.LABELS[V.DISPUTED.value] in html


def test_a_disputed_entry_is_listed_and_carries_no_verdict(disputed_site: Path) -> None:
    """Listed, because hiding a disagreement is worse than publishing one. No
    verdict, because we have measured that the number driving it is wrong."""
    html = (disputed_site / "cell" / "total_area_prediction" / "ng45" /
            "floorplan" / "index.html").read_text(encoding="utf-8")
    row = re.search(r"<tr [^>]*data-verification=\"disputed\".*?</tr>", html, re.S)
    assert row is not None
    assert 'data-verdict=""' in row.group(0)


def test_a_disputed_entry_does_not_colour_its_cell(disputed_site: Path) -> None:
    """The cell state is a claim about a comparison and this comparison is
    against a number we measured to be wrong."""
    html = (disputed_site / "index.html").read_text(encoding="utf-8")
    cell = re.search(
        r'<td[^>]*data-task="total_area_prediction"[^>]*data-metric="mae"[^>]*'
        r'data-pdk="ng45"[^>]*data-stage="floorplan"[^>]*>',
        html,
    )
    assert cell is not None
    assert 'data-state="no_entry"' in cell.group(0)


def test_the_matrix_marks_a_cell_whose_entries_are_all_self_reported(
    published_site: Path,
) -> None:
    html = (published_site / "index.html").read_text(encoding="utf-8")
    assert 'data-self-reported="true"' in html
    assert "legend" in html.lower()


@pytest.mark.parametrize("page", ["index.html", "cell", "model"])
def test_a_submitter_string_never_reaches_the_dom_as_markup(
    xss_site: Path, page: str
) -> None:
    """THE test. Not "we remembered to escape" but a real payload through a real
    build, on all three surfaces that carry a submitter string."""
    if page == "index.html":
        text = (xss_site / "index.html").read_text(encoding="utf-8")
    elif page == "cell":
        text = (xss_site / "cell" / "total_area_prediction" / "ng45" /
                "floorplan" / "index.html").read_text(encoding="utf-8")
    else:
        text = (xss_site / "data" / "models" / "index.json").read_text(encoding="utf-8")
    assert XSS not in text
    assert "onerror=alert" not in text


def test_the_inlined_payload_cannot_close_its_own_script_element(
    xss_site: Path,
) -> None:
    """A model label containing </script> ends the element early and everything
    after it is parsed as markup. json.dumps does not escape it."""
    html = (xss_site / "cell" / "total_area_prediction" / "ng45" /
            "floorplan" / "index.html").read_text(encoding="utf-8")
    start = html.index('id="cell-payload"')
    end = html.index("</script>", start)
    payload = html[html.index(">", start) + 1 : end]
    json.loads(payload)
    assert "</script" not in payload


def test_no_template_marks_a_submitter_string_safe() -> None:
    """| safe on a submission-derived value is the whole XSS surface in one
    filter. The rendered markdown guide is the only allowed use."""
    root = Path(__file__).resolve().parent.parent / "templates"
    for template in sorted(root.rglob("*.html")):
        for line in template.read_text(encoding="utf-8").splitlines():
            if "| safe" in line or "|safe" in line:
                assert "guide_html" in line or "card_html" in line, (
                    f"{template.name}: {line.strip()}"
                )


def test_no_javascript_assigns_innerhtml() -> None:
    root = Path(__file__).resolve().parent.parent / "static" / "js"
    for script in sorted(root.rglob("*.js")):
        assert "innerHTML" not in script.read_text(encoding="utf-8"), script.name
```

Append to `tests/test_cells.py`:

```python
def test_the_saturated_count_is_unchanged_by_a_published_submission(
    published_site: Path,
) -> None:
    """Saturation is a stage rule. Publishing into global_route must not move a
    single cell out of it."""
    html = (published_site / "index.html").read_text(encoding="utf-8")
    found = re.findall(r'data-state="([a-z_]+)"', html)
    assert found.count("saturated") == 120


def test_a_published_entry_on_a_degenerate_cell_gets_no_comparison(
    published_site: Path,
) -> None:
    """Nothing can beat a baseline that was never measured."""
    html = (published_site / "cell" / "worst_slack_prediction" / "ng45" /
            "global_route" / "index.html").read_text(encoding="utf-8")
    section = html[html.index('data-metric="mpe"') :]
    assert 'data-mode="no_comparison"' in section[:400]
```

Add the three site fixtures to `tests/conftest.py`, each publishing a fixture tree into a temp `PUBLISHED_DIR` and building into a temp `dist`, alongside the existing session-scoped `site` fixture.
They are function-scoped and slow; mark them so the suite budget stays visible.

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_publish_render.py -v`
Expected: FAIL, `KeyError: 'verification'` from `cellpage.entry_from`.

- [ ] **Step 3: Extend `tools/cellpage.py`**

`Entry` gains `verification: str`, `verification_label: str`, `reproduced_display: str` and `tolerance_display: str`; the last two are `""` unless a reproduction exists.
`MetricRow` gains `disputed: int` and `self_reported: int`.
`CellPage` gains `verification_labels` and `verification_glyphs`, both plain dicts from `tools.verification`, so the template looks up rather than branching.

In `metric_row`, the state is computed from rankable bounds only, and `_ranked` skips disputed entries when numbering, appending them after the ranked ones with an empty verdict, exactly as it already does for entries with no value:

```python
    rankable = [e for e in entries if verification.parse(e.verification) in verification.RANKABLE]
    unrankable = [e for e in entries if e not in rankable]
```

`format_value` is unchanged and remains the only display boundary; `reproduced_display` goes through it too, so a reproduced number and a declared number are formatted by one function and a reader comparing them is comparing like with like.

- [ ] **Step 4: Extend the templates**

`templates/pages/cell.html`: one new column, and the row gains `data-verification`.

```jinja
        <th scope="col">Verification</th>
...
      <tr data-model="{{ entry.model_id }}"
          data-source="{{ entry.source }}"
          data-verification="{{ entry.verification }}"
          data-verdict="{{ entry.verdict }}">
...
        <td class="verification verification-{{ entry.verification }}">
          <span class="glyph" aria-hidden="true">{{ page.verification_glyphs[entry.verification] }}</span>
          {{ entry.verification_label }}
        </td>
```

Above `table.ranking`, when `row.disputed`:

```jinja
  {% if row.disputed %}
  <p class="notice notice-disputed" role="note">
    {{ page.verification_notes["disputed"] }}
  </p>
  {% endif %}
```

`{{ entry.model_label }}` is already autoescaped and stays that way.
The `colspan` on the filtered-empty row moves from 6 to `row.columns`, which Phase 5 Task 6 already computes, so adding a column does not silently break the empty state.

`templates/pages/matrix.html`: `data-self-reported` and `data-disputed` on the cell, a glyph inside it, and two legend rows.
The glyph runs alongside the state colour rather than replacing it, so the four states stay distinguishable without colour and the markers are further channels.

`static/css/cell.css` and `static/css/base.css`: one rule block per state, every colour a `var()`, and the distinguishing treatment is a border style and a glyph rather than a new hue, so it survives greyscale and a colourblind reader.

- [ ] **Step 5: Run the tests and look at it**

Run: `make build && uv run pytest tests/test_publish_render.py tests/test_cells.py -v`
Expected: all pass.

```bash
uv run python -m http.server -d dist 8000
```

Open a cell page with a published submission on it and check by eye, in both themes, in greyscale:

- [ ] the verification column reads as a word, not only as a colour
- [ ] a disputed row's panel sits above the table and names both numbers
- [ ] the saturated notice, the degenerate note and the disputed panel are three visually distinct things
- [ ] the matrix legend explains both markers

Then the budget, which is the phase's own risk:

```bash
find dist -name '*.html' -size +88k | head
du -sh dist
```

Expected: no output from the first, and `dist/` well under 20 MB.
A new column across 232 pages is the kind of change that breaks the cap, and Phase 3 documented the lever: split the matrix into one page per stage at `/stage/<id>/`.
Pull it rather than raising the cap.

- [ ] **Step 6: Accessibility**

```bash
uv run pa11y-ci
lychee --no-progress dist/
```

Expected: 0 errors, both themes, WCAG AA.

- [ ] **Step 7: Commit**

```bash
git add tools/cellpage.py templates static/css build.py tests/conftest.py \
        tests/test_publish_render.py tests/test_cells.py
git commit -m "feat(cells): render verification state without relying on colour"
```

---

### Task 6: Cells won, cells tied, and the six exclusions

One definition, in one module, with `build.py` calling it in this task.

**Files:**
- Create: `tools/tally.py`
- Modify: `build.py`, `tools/modelpage.py`, `templates/pages/matrix.html`, `templates/pages/model.html`
- Test: `tests/test_tally.py`, `tests/test_synth_marker.py`

**Interfaces:**
- Consumes: `tools.shards`, `tools.baseline`, `tools.ranking`, `tools.verification`, `tools.registry`.
- Produces: `tally.is_countable(record) -> bool`, `tally.cells_won_by_model() -> dict[str, int]`, `tally.cells_tied_by_model() -> dict[str, int]`, `tally.cells_won() -> int`, `tally.cells_tied() -> int`, `cells_won` and `cells_tied` on the matrix context, `cells_won` on every model payload.

#### What a win is, and the six things it is not

A model wins a cell when `ranking.compare(task, metric, its bound, the published bound)` is `BETTER`.
Everything else follows from that one call, which is why the tally cannot drift from the colouring: they read the same function.

| Excluded | Why |
|---|---|
| void cells | not in `reg.live_cells()`; the paper says the cell does not exist |
| saturated cells | never ranked, by a stage-and-task rule and never a numeric test |
| degenerate cells | the baseline is `ABSENT`, so `compare` returns `UNDECIDABLE`. Nothing can beat a baseline that was never measured, and awarding a win there is the exact failure `baseline_state: "degenerate"` was introduced to prevent |
| sentinel cells the entry does not clear | `UNDECIDABLE`. Against `MAPE > 10000 %` a submission at 15000 % is genuinely unknowable, and 32 cells would otherwise get a guessed verdict |
| ties | `EQUAL`, counted separately as **cells tied**. Tying is the best achievable outcome on roughly 132 cells, so folding it into wins inflates the tally with cells nobody could win and dropping it silently discards the achievement |
| synthetic and disputed records | a tally is a claim about measured results |

**Cells tied ships beside cells won rather than instead of it.**
A leaderboard that reports only wins tells a model that hit the theoretical optimum on twelve cells that it scored zero.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_tally.py`:

```python
"""A cells-won count is a claim about measured results.

Expected values live here, in tests. They must never appear in tools/.
"""

from __future__ import annotations

import pytest

from tools import baseline, ranking, shards, tally
from tools import registry as reg
from tools.baseline import Bound, BoundKind
from tools.verification import VerificationState as V


def test_a_win_is_exactly_what_colours_the_cell(published_combo) -> None:
    """One function decides both, so the tally cannot drift from the colouring."""
    won = 0
    for task_id, metric_id, pdk_id, stage_id in reg.live_cells():
        for record in shards.load(task_id, pdk_id, stage_id):
            if record.metric != metric_id or not tally.is_countable(record):
                continue
            bound = baseline.lookup(task_id, metric_id, pdk_id, stage_id).bound
            if ranking.compare(
                task_id, metric_id, shards.bound_of(record), bound
            ) is ranking.Comparison.BETTER:
                won += 1
    assert won == sum(tally.cells_won_by_model().values())


def test_no_saturated_cell_is_ever_won(published_saturated) -> None:
    """A stage and task rule, never a numeric test."""
    for model_id, cells in tally.won_cells_by_model().items():
        for task_id, metric_id, _pdk, stage_id in cells:
            assert not reg.is_saturated(task_id, metric_id, stage_id), model_id


def test_no_degenerate_cell_is_ever_won(published_degenerate) -> None:
    """Nothing can beat a baseline that was never measured. This is the failure
    that baseline_state: degenerate exists to prevent."""
    for cells in tally.won_cells_by_model().values():
        for task_id, metric_id, _pdk, stage_id in cells:
            assert not reg.is_degenerate(task_id, metric_id, stage_id)


def test_an_undecidable_sentinel_is_not_a_win() -> None:
    """15000 percent against a > 10000 percent bound is unknowable, not a loss
    and not a win."""
    sentinel = Bound(BoundKind.GREATER_THAN, 100.0)
    assert ranking.compare(
        "total_area_prediction", "mape", Bound(BoundKind.EXACT, 150.0), sentinel
    ) is ranking.Comparison.UNDECIDABLE
    assert not tally.counts_as_win(
        "total_area_prediction", "mape", 150.0, sentinel
    )


def test_a_tie_is_counted_and_is_not_a_win() -> None:
    """Tying is the best achievable outcome on roughly 132 cells. Folding it into
    wins inflates the tally; dropping it discards the achievement."""
    assert tally.cells_tied_by_model() != {}
    overlap = set(tally.cells_won_by_model()) & set(tally.cells_tied_by_model())
    for model_id in overlap:
        won = set(tally.won_cells_by_model()[model_id])
        tied = set(tally.tied_cells_by_model()[model_id])
        assert not won & tied


def test_a_disputed_record_is_not_countable(published_disputed) -> None:
    record = next(
        r for r in shards.load("total_area_prediction", "ng45", "floorplan")
        if r.verification == V.DISPUTED.value
    )
    assert not tally.is_countable(record)


def test_a_synthetic_record_is_not_countable() -> None:
    """Carried from Phase 7 whether or not synthetic ever shipped. A tally is a
    claim about measured results."""
    record = shards.Record(
        task="total_area_prediction", metric="mae", pdk="ng45", stage="floorplan",
        model_id="synth-1", model_label="Synthetic", source="synthetic",
        value_macro=1.0, value_pooled=None, ranked_on="macro", n_circuits=18,
        n_positive=None, verification=V.SELF_REPORTED.value,
    )
    assert not tally.is_countable(record)


def test_a_self_reported_record_is_countable() -> None:
    """The hybrid trust model. Publishing immediately with a label is the ruling;
    withholding until reproduction would be a different, unshipped product."""
    records = shards.load("total_area_prediction", "ng45", "floorplan")
    assert any(tally.is_countable(r) for r in records)


def test_the_matrix_reports_both_numbers() -> None:
    import build

    context = build.matrix_context()
    assert context["cells_won"] == tally.cells_won()
    assert context["cells_tied"] == tally.cells_tied()


def test_the_tally_is_bounded_by_the_rankable_cells_that_have_entries() -> None:
    """A sanity bound that moves with the data instead of a magic number."""
    rankable = [
        cell for cell in reg.live_cells()
        if not reg.is_saturated(cell[0], cell[1], cell[3])
        and not reg.is_degenerate(cell[0], cell[1], cell[3])
    ]
    assert tally.cells_won() + tally.cells_tied() <= len(rankable)
```

Append to `tests/test_synth_marker.py`, or create it as a stub if Phase 7 ruled no synthetic:

```python
def test_cells_won_still_ignores_synthetic_entries() -> None:
    """Phase 7 put this rule in build.py. It moved to tools/tally.py and the rule
    is unchanged, so the test that guards it moved with it and did not weaken."""
    from tools import tally

    assert all(
        not tally.is_countable(r) for r in _synthetic_records()
    )
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_tally.py -v`
Expected: FAIL, `ImportError: cannot import name 'tally' from 'tools'`

- [ ] **Step 3: Implement `tools/tally.py`**

```python
"""How many cells each model wins, and how many it ties.

A win is exactly what colours the cell: ranking.compare returning BETTER against
the published bound. Reading the same function is what stops the tally and the
colouring drifting apart.

Six exclusions, each for its own reason:

  * void cells are not in reg.live_cells() at all
  * saturated cells are never ranked, by a stage and task rule
  * degenerate cells have an ABSENT baseline, so compare returns UNDECIDABLE.
    Awarding a win against a baseline that was never measured is the failure
    baseline_state: degenerate was introduced to prevent.
  * a sentinel the entry does not clear is UNDECIDABLE, not a win and not a loss
  * a tie is EQUAL and is counted separately. Tying is the best achievable
    outcome on many cells, so folding it into wins inflates the tally with cells
    nobody could win, and dropping it discards the achievement.
  * synthetic and disputed records are not measured results.
"""

from __future__ import annotations

from collections import defaultdict
from functools import cache

from tools import baseline, ranking, shards, verification
from tools import registry as reg
from tools.baseline import Bound
from tools.ingest import SUBMISSION

Cell = tuple[str, str, str, str]

SYNTHETIC = "synthetic"


def is_countable(record: shards.Record) -> bool:
    """Whether this record's verdict may enter a tally.

    A tally is a claim about measured results, so a generated record and a record
    we re-ran and disagreed with are both out.
    """
    if record.source == SYNTHETIC:
        return False
    return verification.parse(record.verification) in verification.RANKABLE


def counts_as_win(
    task_id: str, metric_id: str, value: float, bound: Bound
) -> bool:
    return (
        ranking.compare(
            task_id, metric_id, Bound(ranking.BoundKind.EXACT, value), bound
        )
        is ranking.Comparison.BETTER
    )


@cache
def _verdicts() -> tuple[dict[str, tuple[Cell, ...]], dict[str, tuple[Cell, ...]]]:
    """Won and tied cells per model, in one pass over the live cells."""
    won: dict[str, list[Cell]] = defaultdict(list)
    tied: dict[str, list[Cell]] = defaultdict(list)

    for task_id, metric_id, pdk_id, stage_id in reg.live_cells():
        if reg.is_saturated(task_id, metric_id, stage_id):
            continue
        bound = baseline.lookup(task_id, metric_id, pdk_id, stage_id).bound
        for record in shards.load(task_id, pdk_id, stage_id):
            if record.metric != metric_id or not is_countable(record):
                continue
            cell = (task_id, metric_id, pdk_id, stage_id)
            verdict = ranking.compare(
                task_id, metric_id, shards.bound_of(record), bound
            )
            if verdict is ranking.Comparison.BETTER:
                won[record.model_id].append(cell)
            elif verdict is ranking.Comparison.EQUAL:
                tied[record.model_id].append(cell)

    return (
        {k: tuple(v) for k, v in won.items()},
        {k: tuple(v) for k, v in tied.items()},
    )
```

with `won_cells_by_model`, `tied_cells_by_model`, `cells_won_by_model`, `cells_tied_by_model`, `cells_won` and `cells_tied` as thin readers over `_verdicts()`.
The degenerate exclusion needs no branch: `compare` returns `UNDECIDABLE` against an `ABSENT` bound and neither arm fires.
Writing an explicit `is_degenerate` check as well would be a second encoding of the same rule, and the test asserts the outcome rather than the branch.

- [ ] **Step 4: Give it its consumers, in this task**

In `build.py`, the matrix context gains `cells_won` and `cells_tied` from `tally`, replacing whatever Phase 7 computed inline.
`templates/pages/matrix.html` renders them in the page header, as text, beside the entry count.

In `tools/modelpage.py`, `model_payload` gains `cells_won` and `cells_tied` from `tally.cells_won_by_model().get(model_id, 0)`, and `templates/pages/model.html` renders both.
A model page that cannot say how many cells its model wins is the page a submitter came to see.

- [ ] **Step 5: Run the tests**

Run: `make build && uv run pytest tests/test_tally.py tests/test_synth_marker.py -v`
Expected: all pass.

Then read the tally out loud, because a wrong number here is a wrong headline:

```bash
uv run python -c "
from tools import tally
won, tied = tally.cells_won_by_model(), tally.cells_tied_by_model()
for model in sorted(set(won) | set(tied)):
    print(f'{model:20} won {won.get(model, 0):4}  tied {tied.get(model, 0):4}')
print(f'{\"total\":20} won {tally.cells_won():4}  tied {tally.cells_tied():4}')
"
```

- [ ] **Step 6: Commit**

```bash
git add tools/tally.py build.py tools/modelpage.py templates tests/test_tally.py \
        tests/test_synth_marker.py
git commit -m "feat(tally): count cells won and tied, excluding what was never measured"
```

---

### Task 7: The drift detector, the guide, and the end-to-end proof

Every piece exists.
This task makes it impossible to merge a submission and not publish it, and proves the whole path with one test that starts at a `submission.yaml` a stranger wrote and ends at a rendered page.

**Files:**
- Create: `tools/checks/publish.py`, `tests/test_publish_e2e.py`
- Modify: `tools/checks/__init__.py`, `tools/validate.py`, `docs/SUBMISSION.md`, `templates/pages/submit.html`, `.github/workflows/validate-submission.yml`, `CLAUDE.md`, `PLAN.md`, `docs/plans/README.md`
- Test: `tests/test_publish_e2e.py`, `tests/test_guard_workflow.py`

**Interfaces:**
- Consumes: `tools.submissions`, `tools.publish`, `tools.shards`, `tools.checks.register`.
- Produces: `checks.publish.check() -> list[str]`, registered as `"publish"`.

#### The detector, which is why no write token is needed

`data/published/**` is generated and committed, exactly like `data/cells/**`.
Nothing auto-commits it, because a workflow that writes to the repository needs a token, and a repository that runs submitter code and holds a write token is one self-merge away from being owned.

Instead `make validate` **regenerates in memory and diffs against disk**.
A merged submission that nobody published is a failing check with the file name in the message, and so is a `data/published/` entry whose submission was deleted.
Report rather than repair, the same posture as Phase 4's ingest check, and for the same reason: a gate that fixes the thing it is checking cannot fail.

Three message classes, and only the first two block:

| Message | Blocks | Cause |
|---|---|---|
| `REJECT` from `submissions.discover` | yes | a malformed tree, which is Ruling 3 |
| `REJECT drift` | yes | `data/published/` and `submissions/` disagree |
| `FLAG disputed` / `FLAG aggregate` | no | a published disagreement, visible in CI output without blocking a merge |

`tools/validate.py` already needs the flag-versus-failure split from Phase 6 Task 8 Step 3; this check is its second consumer and the phase gate asserts the counts print separately.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_publish_e2e.py`:

```python
"""A stranger's submission.yaml, all the way to a rendered page.

This is the test the phase exists for. Every other test in this phase checks one
joint; this one checks that the joints connect. Before Phase 10 a third party
could submit, clear every guard layer, get merged, and appear nowhere on the
site, and every individual test still passed.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from tools import publish, shards, submissions, tally
from tools import verification

ROOT = Path(__file__).resolve().parent.parent
TREES = Path(__file__).resolve().parent / "fixtures" / "submissions_tree"


def test_a_third_party_submission_reaches_the_rendered_page(
    stranger_site: Path,
) -> None:
    """The whole path: discover, guard, expand, publish, load, rank, render."""
    html = (stranger_site / "cell" / "total_area_prediction" / "ng45" /
            "floorplan" / "index.html").read_text(encoding="utf-8")
    assert 'data-model="acme-mlp"' in html
    assert 'data-verification="self_reported"' in html


def test_the_matrix_cell_it_wins_is_coloured_for_it(stranger_site: Path) -> None:
    html = (stranger_site / "index.html").read_text(encoding="utf-8")
    cell = re.search(
        r'<td[^>]*data-task="total_area_prediction"[^>]*data-metric="mae"'
        r'[^>]*data-pdk="ng45"[^>]*data-stage="floorplan"[^>]*>',
        html,
    )
    assert cell is not None
    assert 'data-state="beats_baseline"' in cell.group(0)


def test_it_appears_in_the_tally_and_on_its_own_model_page(
    stranger_site: Path,
) -> None:
    payload = json.loads(
        (stranger_site / "data" / "models" / "acme-mlp.json").read_text("utf-8")
    )
    assert payload["cells_won"] >= 1
    assert payload["cells_won"] == tally.cells_won_by_model()["acme-mlp"]


def test_it_is_reachable_from_the_explore_page(stranger_site: Path) -> None:
    """A page nothing links to is a page nobody finds."""
    payload = json.loads(
        (stranger_site / "data" / "explore.json").read_text(encoding="utf-8")
    )
    assert any("acme-mlp" in json.dumps(row) for row in payload["rows"])


def test_the_lab_entry_is_still_there_beside_it(stranger_site: Path) -> None:
    """The merge, end to end. Publishing must not displace the seed entry."""
    from tools.ingest import LAB_MODEL_ID

    html = (stranger_site / "cell" / "total_area_prediction" / "ng45" /
            "floorplan" / "index.html").read_text(encoding="utf-8")
    assert f'data-model="{LAB_MODEL_ID}"' in html


def test_a_merged_submission_that_nobody_published_fails_validate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """THE detector for the bug this phase closes. A submission in the tree with
    no shard on disk is exactly the pre-Phase-10 state, and it must be red."""
    from tools.checks import publish as check

    monkeypatch.setattr(submissions, "SUBMISSIONS_DIR", TREES / "valid")
    monkeypatch.setattr(shards, "PUBLISHED_DIR", tmp_path / "empty")
    messages = check.check()
    assert any(m.startswith("REJECT") and "drift" in m for m in messages)


def test_a_published_shard_whose_submission_was_deleted_fails_validate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.checks import publish as check

    out = tmp_path / "published"
    publish.publish(TREES / "valid", out)
    monkeypatch.setattr(submissions, "SUBMISSIONS_DIR", TREES / "single_result")
    monkeypatch.setattr(shards, "PUBLISHED_DIR", out)
    assert any("drift" in m for m in check.check())


def test_an_empty_submissions_tree_is_green(monkeypatch: pytest.MonkeyPatch) -> None:
    """Day one. A leaderboard with no community entries yet must pass its own
    gate, or the gate gets disabled the first time it fires."""
    from tools.checks import publish as check

    assert check.check() == []


def test_a_disputed_entry_flags_and_does_not_block(disputed_tree_check) -> None:
    messages = disputed_tree_check
    assert any(m.startswith("FLAG") for m in messages)
    assert not any(m.startswith("REJECT") for m in messages)


def test_validate_prints_failures_and_flags_separately() -> None:
    """A flag that blocks a merge is a rejection wearing a different word, and a
    flag that vanishes is a check nobody ran."""
    result = subprocess.run(
        [sys.executable, "-c", "from tools.validate import main; raise SystemExit(main())"],
        capture_output=True, text=True, cwd=ROOT, check=False,
    )
    assert re.search(r"validate: \d+ checks, \d+ failures, \d+ flags", result.stdout)


def test_the_guide_documents_the_format_the_parser_reads() -> None:
    """The bug this phase fixes was a guide and a parser disagreeing about a
    filename. This is the assertion that stops it recurring."""
    text = (ROOT / "docs" / "SUBMISSION.md").read_text(encoding="utf-8")
    assert submissions.BUNDLE_NAME in text
    assert "submission.json" not in text
    for key in ("results", "per_circuit", "split"):
        assert key in text


def test_the_guide_documents_every_verification_state_and_the_tolerance() -> None:
    text = (ROOT / "docs" / "SUBMISSION.md").read_text(encoding="utf-8")
    for state in verification.VerificationState:
        assert verification.LABELS[state.value] in text
    assert "0.1" in text or "1e-3" in text


def test_the_guide_says_a_disagreement_is_published_not_corrected() -> None:
    """A submitter must know this before they submit, not after."""
    text = (ROOT / "docs" / "SUBMISSION.md").read_text(encoding="utf-8").lower()
    assert "disputed" in text
    assert "not corrected" in text or "never corrected" in text
```

Append to `tests/test_guard_workflow.py`:

```python
def test_the_workflow_runs_the_publish_check_on_a_submission_pr() -> None:
    """A PR that adds a submission must fail until the shards are regenerated,
    otherwise the merge lands and the site never changes."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "eda-validate" in text


def test_no_workflow_writes_to_the_repository() -> None:
    """The reason the drift check reports rather than repairs. A runner that
    executes submitter code and holds a write token is one self-merge from
    owning the repo."""
    root = WORKFLOW.parent
    for path in sorted(root.glob("*.yml")):
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        for name, job in (document.get("jobs") or {}).items():
            steps = job.get("steps") or []
            if any("submissions" in str(step) for step in steps):
                assert job["permissions"].get("contents") != "write", f"{path.name}:{name}"
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_publish_e2e.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'tools.checks.publish'`

- [ ] **Step 3: Implement the check**

```python
"""Is every merged submission actually published, and nothing else?

The bug this closes: a third party could submit, clear every guard layer, get
merged, and appear nowhere on the site, because nothing turned a submission into
a shard.

This regenerates in memory and diffs against disk. It reports rather than
repairs, because a gate that fixes what it is checking cannot fail, and because
auto-committing would need a write token on a repository that runs submitter
code.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from tools import publish, shards, submissions
from tools.checks import register


@register("publish")
def check() -> list[str]:
    found = submissions.discover()
    messages = [f"REJECT {error}" for error in found.errors]
    if found.errors:
        return messages

    with tempfile.TemporaryDirectory() as tmp:
        expected_root = Path(tmp)
        publish.publish(submissions.SUBMISSIONS_DIR, expected_root)
        expected = {
            path.relative_to(expected_root): path.read_text(encoding="utf-8")
            for path in sorted(expected_root.rglob("*.json"))
        }

    actual = {
        path.relative_to(shards.PUBLISHED_DIR): path.read_text(encoding="utf-8")
        for path in sorted(shards.PUBLISHED_DIR.rglob("*.json"))
    } if shards.PUBLISHED_DIR.is_dir() else {}

    for name in sorted(set(expected) | set(actual)):
        if name not in actual:
            messages.append(f"REJECT drift: {name} is merged but never published; run make publish")
        elif name not in expected:
            messages.append(f"REJECT drift: {name} has no submission behind it; run make publish")
        elif expected[name] != actual[name]:
            messages.append(f"REJECT drift: {name} is stale; run make publish")

    messages.extend(_flags())
    return messages
```

`_flags()` walks the published shards and emits one `FLAG disputed ...` per disputed entry and one `FLAG aggregate ...` per entry carrying an `aggregate_dispute`, each naming the model and the cell.

Register it in `tools/checks/__init__.py` beside the others.

- [ ] **Step 4: Update the guide and the page**

`docs/SUBMISSION.md` gains four sections, and Task 1's test asserts the filename and Task 7's tests assert the rest:

- **The file you write**, with the full bundle example from Task 1, the `results` list, and the sentence that `per_circuit` is required because we recompute the aggregate rather than trusting it. Delete every mention of `submission.json`.
- **Partial coverage is normal.** Claim the combos you have. Nothing is inferred for the ones you do not.
- **Verification.** The four states, what earns each, and the tolerance with its two terms and the reason for each. State that reproduction is a maintainer run against ground truth, not something CI can do, and that the smoke slice proves your code runs and nothing more.
- **What happens if we disagree with you.** Both numbers are published, your number stays the published one, the entry is labelled `disputed`, and it is listed but not ranked. It is **not corrected**. A new maintainer run that agrees promotes it.

Plus one line in **What we do not rank**: a disputed entry joins the saturated and degenerate cells in that list.

`templates/pages/submit.html` renders the four tiers from `submission.TIERS`, which now includes `disputed`, so the page and the guide stay in step through the Phase 8 consistency test rather than through care.

- [ ] **Step 5: Update the project documents**

`CLAUDE.md`: a short section under the guard paragraph naming the publish path, the two shard trees, the four verification states, and the one sentence that a submission is not on the site until `make publish` has run and `make validate` is green.

`PLAN.md`: add Phase 10 to the phase table and to the roadmap, and close the open item this phase resolves.
`docs/plans/README.md`: add the row.

- [ ] **Step 6: Run the whole gate**

```bash
make check
```

Expected: lint clean, mypy clean, `validate: 5 checks, 0 failures, 0 flags`, every test passing, build clean.

Then the end-to-end, by hand, because the gate passing on an empty `submissions/` proves less than a real submission does:

```bash
cp -r tests/fixtures/submissions_tree/valid/acme-mlp submissions/
make publish && make build
uv run eda-validate
grep -o 'data-model="acme-mlp"' dist/cell/total_area_prediction/ng45/floorplan/index.html | head -1
uv run python -c "from tools import tally; print(tally.cells_won_by_model())"
rm -rf submissions/acme-mlp data/published && make publish
```

Expected: `publish: wrote 2 shards for 1 submissions`, a green validate, one match from the grep, a nonzero tally, and a clean tree afterwards.
Run `uv run eda-validate` once more between `make publish` and `make build` with the submission present but `data/published/` deleted, and confirm it goes **red** with a `drift` message.
That negative run is the whole point of the check and is the one people skip.

- [ ] **Step 7: Commit and open the PR**

```bash
git add tools/checks/publish.py tools/checks/__init__.py tools/validate.py \
        docs/SUBMISSION.md templates/pages/submit.html CLAUDE.md PLAN.md \
        docs/plans/README.md .github/workflows/validate-submission.yml \
        tests/test_publish_e2e.py tests/test_guard_workflow.py
git commit -m "feat(publish): fail validate when a merged submission is not on the site"
git push -u origin phase-10/publish-path
gh pr create --title "Phase 10: the publish path" --body "Closes the gap between a merged submission and a rendered cell. One submission format, discovery that fails closed, a hybrid trust model with four verification states, a stated reproduction tolerance justified against the display precision table, and a drift check that fails when a merged submission is not published."
```

---

## Phase gate

Every item must pass before this phase is called done.

```bash
make check
uv run pytest tests/test_submissions.py tests/test_verification.py \
              tests/test_reproduce.py tests/test_publish.py \
              tests/test_publish_render.py tests/test_tally.py \
              tests/test_publish_e2e.py -v
uv run pa11y-ci
lychee --no-progress dist/
```

**The gap is closed**

- [ ] a fixture submission written by a stranger reaches a rendered cell page, a coloured matrix cell, its own model page and the explore payload
- [ ] the lab's seed entry is still beside it after a full `make ingest`, and the submission is still there after a full `make publish`
- [ ] `make validate` goes **red** when a submission is merged and `data/published/` was not regenerated, with the file name in the message
- [ ] `make validate` goes red when a published shard has no submission behind it
- [ ] an empty `submissions/` tree is green

**Ruling 3, the fail-closed format**

- [ ] every one of the fourteen malformed trees produces at least one error message
- [ ] a `submission.json` produces an error naming `submission.yaml`
- [ ] a missing `submissions/` directory is an error, not an empty result
- [ ] YAML is read through `tools/yamlsafe.py`; the Phase 4 grep assertion still finds no `torch.load`, `yaml.full_load`, `UnsafeLoader` or `add_safe_globals` anywhere in `tools/`
- [ ] every expanded unit passes Phase 6's schema layer unchanged, and a one-result bundle expands to the Phase 6 fixture verbatim

**Ruling 1, the hybrid trust model**

- [ ] every entry in both shard trees carries a verification state, and a missing one raises rather than defaulting
- [ ] the state is distinguishable without colour: the rendered text label is asserted, and the glyph is `aria-hidden`
- [ ] no module outside `verification.py` and `reproduce.py` can assign `REPRODUCED` or `VERIFIED`
- [ ] the bundle schema rejects a submitter-declared `verification` key
- [ ] the lab's own ingested entries are `self_reported`
- [ ] the tolerance is `max(1e-3 * |declared|, half an ulp of the published precision)`, the floor of a percent metric is in storage units, and both branches win on a real cell
- [ ] `r2` disagrees when `n_positive` moves even if the median holds
- [ ] a disagreement publishes **both** numbers, corrects nothing, sets `disputed`, is listed, is not ranked, wins no cell, and prints a `FLAG` in `make validate`
- [ ] `{tier.id for tier in submission.TIERS} == {s.value for s in VerificationState}`, and every `requires` names a layer in `guard.LAYERS`

**The merge, and the shard shape**

- [ ] `eda-ingest` and `eda-publish` write disjoint trees and neither opens the other's file
- [ ] `shards.load` unions them, lab first, and raises on a `model_id` in both
- [ ] `ingest.LAB_MODEL_ID` is refused as a submission directory name
- [ ] re-publishing an edited submission replaces in place and does not duplicate or reorder
- [ ] a submission covering two of the live combos writes two shards and nothing else
- [ ] the aggregate is recomputed with `evallog.macro_mean` and `evallog.median_positive`; the declared aggregate is stored nowhere and a pooled-looking one is flagged
- [ ] `per_circuit` keys must equal the declared test split exactly
- [ ] `tpr` and `tnr` outside `[0, 1]` are refused; there is **no** MAPE range guard
- [ ] a void combo is refused at both the parse and the construction boundary

**Ranking, and the three special cell classes**

- [ ] publishing into `global_route` leaves the saturated count exactly where it was, and the entry is still stored and listed
- [ ] an entry on a degenerate cell renders `no_comparison`, wins nothing, and is listed
- [ ] a sentinel the entry does not clear is `UNDECIDABLE` and is not a win
- [ ] cells-won excludes void, saturated, degenerate, undecidable, tied, synthetic and disputed; cells-tied ships beside it
- [ ] `build.py` and the model page both call `tally`, so it has a consumer in its own phase

**Untrusted input**

- [ ] a `model_label` of `<img src=x onerror=alert(1)>` appears escaped on the matrix, the cell page and the model JSON, and nowhere as markup
- [ ] the inlined payload cannot close its own `script` element
- [ ] no template marks a submission-derived string `| safe`; no JavaScript assigns `innerHTML`
- [ ] no workflow that touches `submissions/` holds `contents: write`, and none references a secret

**Budget and the standing constraints**

- [ ] no page exceeds 88 KB after the new column; `dist/` is well under 20 MB
- [ ] `pa11y-ci` passes in both themes, WCAG AA, and the disputed panel, the saturated notice and the degenerate note are three visually distinct things
- [ ] no count literal appears anywhere in `tools/`
- [ ] no em dash in any file this phase touched

## Review prompt

```
Use a security reviewer on tools/submissions.py, tools/publish.py,
tools/reproduce.py, tools/verification.py, tools/tally.py,
tools/checks/publish.py, schema/submission_bundle.schema.json and the templates
this phase touched, against docs/plans/2026-08-11-phase-10-publish-path.md.

Assume an adversarial submitter whose goal is a green cell, a promoted badge, or
code execution, without a working model. Name every way through, and for each say
whether it is blocked, flagged or undetected. Work through at least these, then
find the ones this list does not contain:

- reach the reproduced or verified state without a maintainer run: through the
  bundle, through a crafted data/reproductions file in the PR, through the
  directory name, through a symlink, through the check's temp directory
- get a string into the DOM as markup: model_label, authors, family, model_id,
  the inlined payload, the model JSON, the CSV export, a filename
- win a cell that cannot be won: saturated, degenerate, void, a sentinel that is
  not cleared, or by declaring an aggregate that does not match the per-circuit
  values
- displace or overwrite another model's entry, including the lab's seed entry,
  through the model_id, through case, through a path that leaves submissions/
- pass validate with a submission that is merged but not published, or published
  but not submitted
- exploit the difference between what the guard validates and what publish
  constructs: a key the schema allows that publish reads differently, or a
  results item that expands into a document the guard sees as valid and publish
  sees as something else

Then verify three things against the sources rather than against the code:

1. that the reproduction tolerance in tools/reproduce.py is consistent with the
   display precision table in docs/DATA_CONTRACT.md for a 4dp cell and for a
   percent cell, and that the percent floor is in storage units
2. that every percent metric is a fraction everywhere under data/published/, by
   reading a published shard rather than by reading the loader
3. that docs/SUBMISSION.md, templates/pages/submit.html and
   tools/submissions.py agree on the filename, the required keys and the
   verification vocabulary. A guide and a parser disagreeing about a filename is
   the exact bug this phase was written to fix.

Report only exploitable gaps, correctness gaps and source mismatches. Do not
report style preferences.
```
