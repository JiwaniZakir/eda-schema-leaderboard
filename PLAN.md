# EDA-Schema Leaderboard — Build Plan

Twelve phases. Each has a machine-checkable exit gate. Nothing proceeds until the
gate passes and an adversarial reviewer signs off.

---

## How to run this plan

The plan is written for the four-phase Claude Code workflow: **explore → plan →
implement → commit**. Per phase:

1. **Start a fresh session.** `/clear` between phases. Context from phase N is
   noise in phase N+1, and performance degrades as context fills.
2. **Enter plan mode** (`Shift+Tab` until `⏸ plan mode on`) and paste the phase's
   *Kickoff prompt*. Claude explores and produces a plan without editing.
3. **Read the plan.** Press `Ctrl+G` to open it in your editor. Challenge it.
   Changing a plan costs nothing; changing code costs hours.
4. **Approve and implement.**
5. **Run the gate.** The phase is not done until the gate command exits 0 and
   Claude has shown you the output. Claude will say tests pass without running
   them — require the evidence, every time.
6. **Adversarial review.** Paste the phase's *Review prompt*. It runs in a fresh
   subagent that sees only the diff and the criteria, not the reasoning that
   produced the change.
7. **Commit and PR.**

A reviewer asked to find gaps will find some, even when the work is sound. Every
review prompt below says to flag only correctness and requirement gaps. Treat
style findings as optional and resist the urge to chase them — that path leads to
defensive code and tests for cases that can't happen.

**Model selection.** Opus for phase planning and for the security and data-integrity
subagents. Sonnet for implementation. Haiku for mechanical subagent work (file
inventory, link checking, vocabulary sweeps).

---

## Subagent roster

Create these in `.claude/agents/` during Phase 0. They are referenced by name
throughout.

| Agent | Model | Tools | Purpose |
|---|---|---|---|
| `plan-auditor` | opus | Read, Grep, Glob, Bash | Reviews a diff against PLAN.md. Reports only correctness and requirement gaps. |
| `data-integrity` | opus | Read, Grep, Bash | Checks parsed metrics for sanity: macro-mean vs pooled, MAPE scale, Table 8 order-of-magnitude cross-check, sentinel handling. |
| `security-reviewer` | opus | Read, Grep, Glob, Bash | Pickle loading, secrets, fork-PR workflow safety, untrusted-input paths. |
| `eda-domain` | sonnet | Read, Grep, Glob | Registry vocabulary compliance, stage-legality logic, void/saturated cell handling. |
| `frontend-reviewer` | sonnet | Read, Glob, Bash | Contrast ratios, keyboard nav, semantic markup, responsive behavior, both themes. |
| `perf-auditor` | haiku | Read, Bash, Glob | `dist/` size, per-page payload, largest assets, Pages 1 GB headroom. |
| `repo-scout` | haiku | Read, Grep, Glob | Fast codebase search. Keeps exploration out of the main context. |

Example definition:

```markdown
---
name: plan-auditor
description: Reviews a diff against PLAN.md for correctness and requirement gaps
tools: Read, Grep, Glob, Bash
model: opus
---
You are reviewing a diff against a written plan. You see only the diff and the
plan, not the reasoning that produced the change.

Report ONLY:
- Requirements in the plan that are not implemented
- Implemented behavior that contradicts the plan
- Correctness bugs: wrong logic, unhandled cases the plan names, silent failures
- Changes outside the stated scope of this phase

Do NOT report style preferences, naming opinions, or speculative refactors.
If the work is sound, say so plainly. Cite file and line for every finding.
```

---

# Phase 0.5 — Data contract

Added 2026-08-10. Phase 1 said the tasks, metric sets, PDKs, stages, circuits and
void combos were "all specified in the data contract", but no such document
existed. Everything downstream inherits its errors, so it is written and approved
before any registry code.

### Scope

`docs/DATA_CONTRACT.md`, derived from arXiv:2605.06952 and its e-print source.
Paper-only: every claim cites a table and page, and anything the paper does not
state is marked **OPEN** rather than inferred. The counts are permitted not to
reconcile on a first pass, because that is the signal working.

Verbatim source material is preserved under `docs/sources/` so later phases can
re-derive rather than trust a transcription.

### Gate

Human approval. Specifically, a ruling on the two OPEN items that Phase 1 encodes:
the treatment of the 24 degenerate `mpe`/`mne` cells, and the MPE/MNE penalty
weight.

---

# Phase 0 — GitHub foundation and CI/CD

Nothing else starts until this is green. A leaderboard that other labs cite is
infrastructure, and infrastructure earns trust through its guardrails.

### Kickoff prompt

```
Read PLAN.md Phase 0 and CLAUDE.md. We are setting up two GitHub repos from
scratch: eda-schema-leaderboard (the site) and eda-schema-experiments (results).

Use `gh` for all GitHub operations. Explore what the SWE-bench site repo does
for CI as a reference point, then produce a plan covering repo creation, branch
protection, CODEOWNERS, issue and PR templates, and every workflow listed in
Phase 0. Do not create anything yet.
```

### Scope

**Both repos**
- Created under your personal account (transfer to `drexel-ice` in Phase 12)
- MIT license on the site, CC-BY-4.0 on results data
- Branch protection on `main`: require PR, require status checks, dismiss stale
  approvals, no force push, no deletion. **The required approving review is
  deferred to Phase 12**, because GitHub will not let an author approve their own
  PR and the repo is solo until transfer. Adding it now would block every merge;
  adding it at transfer is when it starts having someone to enforce against.
- `CODEOWNERS`: `* @zakir` initially; add `@pratik` for `submissions/**` and
  `@savidis` for `docs/CARD.md` and `docs/SUBMISSION.md`
- Secret scanning and push protection enabled
- Dependabot for Actions and pip, weekly
- CodeQL for Python and JavaScript

**Site repo workflows** (`.github/workflows/`)

| Workflow | Trigger | Does |
|---|---|---|
| `ci.yml` | PR, push to main | ruff, mypy, pytest, `make validate`, `make build`, artifact upload |
| `deploy.yml` | push to main, `repository_dispatch` | build → deploy to Pages via `actions/deploy-pages` |
| `link-check.yml` | PR touching templates, weekly cron | lychee over `dist/` |
| `a11y.yml` | PR touching templates or CSS | pa11y-ci on matrix, cell, model pages, both themes |
| `size-guard.yml` | PR | fails if `dist/` exceeds 200 MB or any single file exceeds 1 MB |
| `claude-review.yml` | PR | `anthropics/claude-code-action@v1`, review-only |

**Experiments repo workflows**

| Workflow | Trigger | Does |
|---|---|---|
| `validate-submission.yml` | PR | JSON Schema, guard layers 1–5, smoke run |
| `notify-site.yml` | push to main | `repository_dispatch` to site repo |
| `parser-repair.yml` | on `validate-submission` failure | Claude Code patches the parser, commits to a branch |

**Security notes for `claude-review.yml` and `parser-repair.yml`**
- Use `anthropics/claude-code-action@v1`, not the base action — the full action
  does actor permission checks and handles fork-PR contexts, which is exactly the
  untrusted-input case once submissions open.
- Grant `id-token: write` and authenticate by workload identity federation rather
  than a long-lived secret. Federation exchanges the workflow's OIDC token, so
  nothing static sits in repo secrets. If using a key instead, use a Console API
  key, not an OAuth token — the latter is tied to whoever ran `claude setup-token`.
- The action commits to a branch and returns a PR-creation link rather than
  opening PRs itself. Keep that human-in-the-loop step.
- Both repos are public, so standard runners are free and unmetered.

### Gate

```bash
# Both repos exist with protection
gh api repos/:owner/eda-schema-leaderboard/branches/main/protection | jq -e '.required_pull_request_reviews'

# CI runs and is green on an empty scaffold
gh run list --workflow=ci.yml --limit 1 --json conclusion -q '.[0].conclusion'   # → success

# The negative test — this is the one that matters
git checkout -b test/ci-negative
# introduce a deliberate ruff error, a schema violation, and a 2MB binary
gh pr create --title "CI negative test" --body "must fail"
# ALL THREE checks must report failure. If any passes, the guard is decorative.
```

**Exit criteria:** the negative-test PR fails on lint, on schema, and on size,
independently. Delete the branch afterward.

### Review prompt

```
Use the security-reviewer subagent to review the .github/ directory against
PLAN.md Phase 0. Check specifically: can a pull request from a fork trigger a
workflow that has write permissions or access to secrets? Are permissions scoped
per-job rather than globally? Is any credential static where federation was
specified? Report only findings that create a real exposure.
```

---

# Phase 1 — Registries and JSON Schema

Everything downstream reads from here. Get it wrong and every later phase
inherits the error.

### Kickoff prompt

```
Read PLAN.md Phase 1, CLAUDE.md, and docs/DATA_CONTRACT.md. Build the five
registry files and the submission JSON Schema. Use the repo-scout subagent if
you need to find anything; do not read the whole repo into context.

The 12 tasks, their per-task metric sets, the 4 PDKs, the 5 stage transitions,
the 18 circuits, and the void combinations are all specified in the data
contract. Derive the 880-cell count programmatically and assert it in a test —
do not hardcode 880.
```

### Deliverables

```
data/registry/tasks.json      # id, label, unit, level, metrics[]
data/registry/metrics.json    # id, label, direction, bias, format
data/registry/stages.json     # id, label, order, void_tasks[]
data/registry/pdks.json       # id, label, metal_layers, utilization
data/registry/circuits.json   # id, inputs, outputs, registers  (Table 2)
schema/submission.schema.json
schema/cell.schema.json
tools/registry.py             # typed loaders, the only import path for vocab
```

`metrics.json` carries direction once, globally. Every ranking function reads it.
`mpe` and `mne` also carry `bias: conservative | optimistic` — the paper ranks a
pessimistic prediction above an optimistic one of equal magnitude, and the
ranking function must encode that rather than treating both as plain magnitude.

### Gate

```bash
make test   # must include:
# - 12 tasks, 4 pdks, 5 stages, 18 circuits load
# - metric rows sum to 46
# - live cells compute to 880, live combos to 232
# - every task's metrics[] ⊆ metrics.json keys
# - every metric has a direction
# - schema validates a known-good fixture and rejects 6 known-bad fixtures
```

**Exit criteria:** derived counts match 46 / 880 / 232 with no literals in the
source.

### Review prompt

```
Use the eda-domain subagent to review data/registry/ and schema/ against
PLAN.md Phase 1 and docs/DATA_CONTRACT.md. Verify: the per-task metric sets match
Table 8 of the paper exactly; void combinations are the 8 specified and no
others; metric directions are correct, especially R² (higher) versus MAE (lower)
and the conservative-versus-optimistic bias on MPE/MNE. Report only mismatches.
```

---

# Phase 2 — Baseline data

### Scope

Transcribe Table 8 into `data/baseline.json`, keyed `(task, metric, pdk, stage)`.

**Corrected 2026-08-10.** This phase previously said only 14 of 20 stage-PDK
column groups were recoverable, that global_route was missing entirely, and that
the source CSV had to be requested from Pratik. That was an extraction artifact,
not a gap in the paper: Table 8 is a `\begin{landscape}` table spanning pages 28
and 29, and naive text extraction shreds it. The arXiv e-print LaTeX source and
`pdftotext -layout` both read all 20 groups. All 856 published cells were
cross-checked between the two, with zero mismatches.

**There is no Pratik dependency and no synthetic baseline.** Every entry is
`"source": "paper"`. Transcribe from `docs/sources/table8_baseline.csv`, which is
already tidy at `(task, metric, stage, pdk)`.

Two published sentinels must round-trip, preserving the real value and displaying
the sentinel: `> 10000 %` (20 cells) and `< -1` (12 cells).

64 cells are void, from two distinct causes that the UI must not conflate: 40 at
floorplan where HPWL needs placement that does not exist yet, and 24 degenerate
`mpe`/`mne` cells at global_route where n_p = n_n = 0. See @docs/DATA_CONTRACT.md.

Mark saturated cells: at `global_route`, baseline error is ≈0 for all tasks except
`total_wirelength` and `interconnect_length`. Confirmed empirically in Pratik's
folder — baseline `mae=0.0, mape=0.0, r2=1.0` across all four PDKs.

### Gate

```bash
make validate
pytest tests/test_baseline.py
# - every live cell has a baseline entry
# - every entry has an explicit source
# - saturated flags match the registry's saturation rule
# - no baseline value is negative where its metric is defined non-negative
```

### Review prompt

```
Use the data-integrity subagent to spot-check data/baseline.json against the
paper PDF for ten randomly chosen cells across different tasks and stages.
Report any transcription error. Then confirm every cell marked synthetic is
genuinely absent from the source, and no paper-sourced cell is mislabeled.
```

---

# Phase 3 — Ingest

The highest-risk code in the project. Use plan mode. Do not skip the review.

### Kickoff prompt

```
Read PLAN.md Phase 3 and the "Data gotchas" section of CLAUDE.md. Build
tools/ingest.py, which parses the lab's results tree into cell shards.

Input tree shape:
  <task>_prediction/<family>/<config>_<PDK>_<STAGE>/<circuit>/version_0/

Read only: eval.log, aggregated_eval_metrics.csv, submission.yaml, and one
hparams.yaml and one .ckpt per architecture. Everything else is excluded.

Write a failing test first for the stage-name underscore case, then implement.
```

### Rules

- Path parsing anchored on registry vocabularies, never `rsplit`
- MAPE ×100 exactly once, at the parse boundary
- Macro-mean across circuits for MAE and MAPE; median for R², plus `n_positive`
- Sentinels: R² < −1 → `display: "<-1"`, real value preserved
- Ignore CSV R², the `eval.log` "Overall" block, and all tfevents
- Cross-check parsed baseline against `data/baseline.json`; warn (don't fail) on
  >10× divergence, since one is macro-averaged and the other pooled
- Architecture from checkpoint tensor shapes via the restricted reader in
  `tools/ckpt.py`, run once per architecture and cached by shape signature.
  **Corrected 2026-08-10:** `weights_only=True` alone does not work. It refuses all
  360 of the lab's checkpoints, which carry a pickled `eda_ml.schema.ModelConfig`.
  Never unpickle; walk the zip with a placeholder-returning `Unpickler`. See the
  gotchas in CLAUDE.md.
- `hparams.yaml` needs the tag-stripping loader in `tools/yamlsafe.py`; plain
  `safe_load` raises `ConstructorError` on its `!!python/object:` tags

### Gate

```bash
pytest tests/test_ingest.py -v
# - parses all 5 stage names correctly, including the 3 with underscores
# - MAPE scale conversion applied exactly once (0.0051 → 0.51)
# - macro-mean ≠ pooled on a fixture where they differ
# - R² median chosen, not mean, on a fixture containing -335
# - ingesting the real sample folder produces exactly 20 combos
# - no unpickling path exists at all: grep asserts torch.load, yaml.full_load,
#   yaml.UnsafeLoader and torch.serialization.add_safe_globals are absent from tools/
# - tools/ckpt.py recovers 41 -> 64 -> 32 -> 16 -> 1 from a real .ckpt fixture
# - hparams.yaml parses through tools/yamlsafe.py and its in_features:7 is IGNORED
make ingest && make validate
```

**Exit criteria:** the sample folder ingests to 20 combos of `total_area`, and
every number in the output is traceable to a line in an `eval.log`.

### Review prompt

```
Use the data-integrity subagent to review tools/ingest.py against PLAN.md Phase 3.
Trace one metric end to end: pick ac97_ctrl at NG45 floorplan, find its line in
eval.log, and confirm the value in the emitted shard is that number with the
documented transformations applied and nothing else. Then confirm no code path
reads the CSV R² columns, the Overall block, or tfevents. Report only
correctness gaps.
```

---

# Phase 4 — Synthetic fill

232 combos exist; 20 have data. The other 212 need plausible fill so every UI
path is exercised at real scale before real data lands.

### Scope

`tools/synth.py` generates records that are *plausible*, not random: error
decreasing monotonically across stages, magnitudes scaled per PDK from Table 6
ranges, per-circuit variation correlated with circuit size, ~60% of cells with at
least one model beating baseline.

Every record: `"source": "synthetic"`. `make validate` fails on any record
lacking an explicit source. Seeded and deterministic — same seed, same bytes.

### Gate

```bash
make synth && make validate
pytest tests/test_synth.py
# - all 232 live combos populated
# - all 880 live cells resolve to a state
# - zero synthetic records in void or saturated cells
# - byte-identical output across two runs with the same seed
```

---

# Phase 5 — Contamination guard

### Scope

`tools/guard/` implementing layers 1–5:

1. **Feature-stage legality** — every declared feature checked against Table 1's
   stage availability. Requires `data/registry/attributes.json`, generated from
   Table 1, mapping each attribute to its earliest stage. The lab's 41 features
   need a group→namespace lookup: `netlist` and `power_metrics` and
   `timing_metrics` map directly; `cell_metrics` splits between Cell Metrics and
   Area Metrics. All 41 are FP–F, so they pass — the guard proves the mechanism
   works rather than catching this submission.
2. **Split overlap** — reject train/test intersection
3. **Divisions** — closed requires canonical split, features, target
4. **Runnability** — `predict.py` executes on the smoke slice under 10 min
5. **Plausibility** — error below the dataset's own reported precision is flagged

### Gate

```bash
pytest tests/test_guard.py
# each layer has a passing fixture and a failing fixture
# layer 1 rejects a submission declaring net.length at floorplan (DR–F only)
# layer 1 accepts all 41 of the lab's declared features
# layer 5 flags MAE 0.00001 on cell_arc_delay (4-decimal ground truth)
make validate   # full guard over all current data
```

### Review prompt

```
Use the security-reviewer subagent to review tools/guard/ against PLAN.md Phase 5.
Assume an adversarial submitter who wants a green cell without a working model.
Name every way through the guard you can find, and for each say whether it is
blocked, flagged, or undetected. Report only exploitable gaps.
```

---

# Phase 6 — Build system and matrix page

### Scope

`build.py` on the SWE-bench pattern: load Jinja2 env, load registries and shards,
render `templates/pages/*.html` into `dist/`, copy static assets. No Node.

Matrix page: 12 task rows collapsing to metric sub-rows, 4 PDK columns, stage
pill strip, track toggle, four cell states with an icon channel alongside color.
`matrix.json` inlined; cell data lazy-loaded.

### Gate

```bash
make build
pytest tests/test_build.py
# - dist/index.html exists and contains 880 cell elements
# - every cell has exactly one state class
# - zero cells render an undefined or NaN value
# - build completes under 60s (Pages deploys time out at 10 min)
python -m http.server -d dist  # manual: click through all 5 stages
```

### Review prompt

```
Use the frontend-reviewer subagent on dist/index.html and static/css/.
Check: contrast ratio ≥4.5:1 for every cell state in both themes; state is
distinguishable without color; the table is keyboard navigable; stage pills are
real buttons with aria-pressed. Report only failures against WCAG AA.
```

---

# Phase 7 — Cell pages

232 pre-rendered pages. Baseline pinned above the ranking, filters, ECharts
plots, CSV and JSON export.

Until raw predictions exist, the predicted-vs-actual panel falls back to the
static PNG from the Release URL. Template handles both — a conditional, not a
rewrite.

### Gate

```bash
make build
pytest tests/test_cells.py
# - 232 cell pages generated, zero 404s from the matrix
# - baseline row present and visually distinct on every page
# - saturated pages render the saturated notice and no ranking
# - no page exceeds 500 KB
lychee dist/   # --exclude-mail was removed from lychee; mail is skipped by default
```

---

# Phase 8 — Model pages and architecture renderer

Client-hydrated at `/model/?id=`, not pre-rendered — the record count makes
static generation counterproductive.

The architecture renderer takes `architecture.json` and draws layer blocks with
height proportional to layer width. One renderer for MLP, GNN, CNN and AutoML;
only the layer list differs.

### Gate

```bash
pytest tests/test_arch_render.py
# - the lab's fixed MLP renders as 41 → 64 → 32 → 16 → 1 with 5,313 params
# - a GNN fixture with pooling renders without overlap
# - a 40-layer fixture degrades gracefully rather than overflowing
# - feature legality badge reflects the guard result, never hardcoded
```

---

# Phase 9 — Explore, card, submit

- `/explore/` — flat table, five filters, Tabulator with virtual scroll
- `/about/card/` — leaderboard card rendered from `docs/CARD.yaml`
- `/submit/` — submission guide, `predict.py` signature, badge criteria

### Gate

```bash
pytest tests/test_pages.py
# - explore loads every record and filters correctly on each of the 5 axes
# - card renders every required section; missing section fails the build
# - submit page links resolve
```

---

# Phase 10 — Themes

Two stylesheets against one CSS-variable contract, switched by one line in
`build.py`.

- `drexel` — `#07294D` navy, `#FFC600` gold, serif headings
- `neutral` — near-white ground, near-black text, one accent, dense table headers

Both share the colorblind-safe four-state data palette.

### Gate

```bash
THEME=drexel make build && cp -r dist dist-drexel
THEME=neutral make build && cp -r dist dist-neutral
pytest tests/test_themes.py    # both implement every variable in the contract
# a11y workflow runs against both
# manual: view side by side, pick one
```

---

# Phase 11 — Deploy

### Gate

```bash
gh workflow run deploy.yml && gh run watch
curl -sI https://<domain>/ | head -1          # 200
du -sh dist/                                   # well under 1 GB
# repository_dispatch from experiments repo triggers a rebuild
```

---

# Phase 12 — Transfer

```bash
gh repo transfer <repo> drexel-ice
```

Re-apply branch protection and CODEOWNERS after transfer — they do not always
survive. Update the CNAME. Re-run the Phase 0 negative test against the
transferred repo: protection that silently didn't survive is worse than none,
because you'll believe it's there.

---

## Cross-phase discipline

**Every phase ends the same way.** Gate command run, output shown, adversarial
review passed, committed, `/clear`.

**When a gate fails twice on the same issue,** stop correcting. The context is
polluted with failed approaches. `/clear` and restart the phase with a prompt
that incorporates what you learned.

**Scope investigations.** "Understand the ingest pipeline" reads forty files into
the main context. Hand it to `repo-scout` instead.

**Hooks over instructions** for anything that must happen every time. A Stop hook
running `make check` is deterministic where a CLAUDE.md line is advisory. Add one
once the check runs in under ~30 seconds.

**Things that will need Savidis or Pratik, not code:**
- ~~The full Table 8 CSV (Phase 2 blocker)~~ — **cleared 2026-08-10.** Recovered
  complete from the arXiv e-print source; see Phase 2 and @docs/DATA_CONTRACT.md
- Raw predictions on the canonical subset (unblocks correct R²)
- ~~Confirmation that the 360 checkpoints are genuinely one architecture~~ —
  answerable in code once `tools/ckpt.py` exists; do not ask a human for this
- Whether the paper's "three prediction tasks" line on p.21 is stale draft text,
  since the abstract and Table 8 both say twelve
- The MPE/MNE penalty weight, which the paper states only qualitatively
- Whether launch waits for a real training run — current models are undertrained
  at 50 gradient steps with a training R² median of 0.020
