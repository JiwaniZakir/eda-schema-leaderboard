# EDA-Schema Leaderboard - Build Plan

> **For agentic workers:** implement phase by phase. Each phase has a
> machine-checkable gate. Nothing proceeds until the gate command exits 0, its
> output has been shown, and an adversarial reviewer has signed off.

**Goal:** a static, citable benchmark leaderboard for the EDA-Schema-V2 dataset
(arXiv:2605.06952), showing how submitted models compare against the paper's
published baseline across a 12 task x 4 PDK x 5 stage grid.

**Architecture:** Python reads registries and data shards, Jinja2 renders static
HTML into `dist/`, GitHub Actions deploys to Pages. No framework, no bundler, no
Node. Every vocabulary lives in `data/registry/`, generated from
`docs/DATA_CONTRACT.md` and cross-checked against `docs/sources/`.

**Tech stack:** Python 3.11+, `uv`, Jinja2, `ruff`, `mypy`, `pytest`, vanilla JS,
CSS custom properties, GitHub Actions, GitHub Pages.

---

## Why this plan was rewritten

Reset on **2026-08-11** after a full audit of the first build. The audit is worth
reading once, because the failure modes it found are what this plan is shaped to
avoid.

**What the first build got right, and which is kept:** the paper data
(920/920 cells verified by two independent parsers), the data contract, and the
GitHub infrastructure (two repos, branch protection with 7 required checks, and a
negative test that proved the guards block rather than decorate).

**What went wrong, and what changed as a result:**

| Audit finding | Change in this plan |
|---|---|
| Three documents disagreed on percent storage. Following the wrong one makes every MAPE cell read `baseline_leads` and every TPR/TNR cell read `beats_baseline`, silently. | Ruled once in `docs/DATA_CONTRACT.md`. Phase 1 encodes it, Phase 2 asserts it. |
| Guard code (721 lines) exceeded product logic (548). 266 lines and 40 tests guarded unpickling in a repo with no checkpoint reader. | **No guard ships before the thing it guards.** Phase 5 builds the guards, after Phase 3 builds the readers. |
| 85 of 115 tests survived a wrongly regenerated registry. Reversing every stage order, hardcoding metric direction, and corrupting a circuit attribute each left the suite green. | Every registry value is cross-checked against `docs/sources/`, which is an independent source. Assert the 40/24/120 partition, not the 880 total. |
| A 217-line ranking module had zero non-test consumers, so it was only ever tested against itself. | Ranking ships **in the same phase as its first consumer** (Phase 3). |
| All UI was scheduled last, so every unknown sat behind three data phases. `dist/` was 279 bytes after 17 hours. | **Phase 2 ships a real matrix to Pages** before ingest, synth or guards exist. |
| Synthetic fill was committed to up front, planning a launch that was 91% synthetic. | Deferred to Phase 6 and decided **with evidence** from a real matrix. "No synthetic" is an allowed outcome. |
| `claude-review.yml` never ran once; no secrets were configured. Review value came from coderabbit, which was not in the plan. | Phase 0 resolves the review stack to one tool. |

---

## Global constraints

Every phase's requirements implicitly include these.

- Python **3.11+**, type hints on all public functions, `ruff` and `mypy` clean.
- **Registries are the only source of vocabulary.** Never hardcode a task, PDK,
  stage, metric or circuit name outside `data/registry/`.
- **Counts are derived, never literal.** 46, 232, 880, 856, 120, 40, 24 are all
  computed and asserted, never written into source.
- **Percent metrics** (`mape`, `mape_p95`, `mape_top5`, `tpr`, `tnr`) are stored
  as fractions in `[0, 1]`, multiplied by 100 exactly once at display. The CSV is
  in display units and is divided by 100 on read; `eval.log` is already a fraction
  and is not converted.
- **Every record carries an explicit `source`** (`paper`, `synthetic`,
  `submission`). `make validate` fails without one.
- **Never commit files over 1 MB**, and never commit anything under `data/` by
  hand.
- `dist/` targets **~20 MB**, so the per-page budget is roughly **88 KB** across
  232 cell pages.
- Conventional commits. Branch `phase-N/short-slug`. Never push to `main`.
- **Never use an em dash** in prose or generated copy.

---

## Detailed phase plans

This file is the roadmap: scope, gates and open decisions.
The task-level implementation plans live in `docs/plans/`, one per phase, each
with bite-sized TDD steps, real code and exact commands.

| Phase | Plan | Ships |
|---|---|---|
| 1 | [registries](docs/plans/2026-08-11-phase-1-registries.md) | the five registry files and the typed loader |
| 2 | [baseline](docs/plans/2026-08-11-phase-2-baseline.md) | `data/baseline.json` from the paper CSV |
| 3 | [matrix](docs/plans/2026-08-11-phase-3-matrix.md) | **a real page on Pages** |
| 4 | [ingest and ranking](docs/plans/2026-08-11-phase-4-ingest-ranking.md) | the 20 real combos, and ranking with a consumer |
| 5 | [cell pages](docs/plans/2026-08-11-phase-5-cell-pages.md) | 232 pre-rendered pages |
| 6 | [guard](docs/plans/2026-08-11-phase-6-guard.md) | the five contamination layers |
| 7 | [synthetic decision](docs/plans/2026-08-11-phase-7-synthetic-decision.md) | a decision, and possibly no code |
| 8 | [explore, card, submit, model](docs/plans/2026-08-11-phase-8-explore-card-submit-model.md) | the remaining pages |
| 9 | [themes, deploy, transfer](docs/plans/2026-08-11-phase-9-themes-deploy-transfer.md) | two themes and the handover |
| 10 | [publish path](docs/plans/2026-08-11-phase-10-publish-path.md) | **submissions actually reach the grid** |

Read the roadmap for *why* and the phase plan for *how*.
Where they disagree, the roadmap is authoritative on scope and the phase plan is
authoritative on implementation detail.

---

## Phase 0 - Reset and corrections

**Status: this PR.**

### Scope

- Delete `tools/`, `build.py`, `tests/`, `schema/`, `data/registry/`, `dist/`.
  All recoverable from git history at `d7f32f2`.
- Record everything the registries knew that the contract did not into
  `docs/DATA_CONTRACT.md` **Appendix A**, so the strip is lossless. Verified:
  metrics 11/11, tasks 12/12, pdks 4/4, stages 5/5 match exactly.
- Rule the percent convention once, in the contract.
- Correct the contract: the `tpr`/`tnr` saturated count (8 to **16**), the
  provenance file paths (they live under `verbatim/`), and the unsatisfiable
  sentinel round-trip requirement.
- Rewrite `CLAUDE.md` and this file.
- Resolve the review stack to one tool.

### Gate

```bash
git ls-files | grep -E '^(tools|tests|schema|data)/' && echo "STRIP INCOMPLETE" || echo "strip clean"
grep -c "Appendix A" docs/DATA_CONTRACT.md      # >= 1
grep -n "Multiply by 100 at" CLAUDE.md && echo "LANDMINE PRESENT" || echo "percent rule fixed"
```

**Exit criteria:** the repo contains no Python; the contract alone is sufficient
to regenerate every registry; no document instructs a ×100 at ingest.

---

## Phase 1 - Registries

Everything downstream reads from here. Get it wrong and every later phase inherits
the error.

### Kickoff prompt

```
Read PLAN.md Phase 1, CLAUDE.md, and docs/DATA_CONTRACT.md including Appendix A.
Generate the five registry files and the loader that is the only import path for
vocabulary. Appendix A plus docs/sources/table8_baseline.csv is sufficient input;
you need nothing else.

Derive every count programmatically and assert it. Do not write 46, 880, 232, 120,
40 or 24 as a literal anywhere in source.
```

### Deliverables

```
data/registry/tasks.json       # id, label, table8_label, unit, granularity,
                               # design_level, metrics[], precision_overrides
data/registry/metrics.json     # id, label, table8_label, direction, bias,
                               # percent, precision
data/registry/stages.json      # id, label, table8_label, order, void_tasks,
                               # saturated_tasks, degenerate_tasks,
                               # degenerate_metrics
data/registry/pdks.json        # id, label, table8_label, metal_layers,
                               # utilization, utilization_sweep
data/registry/circuits.json    # id, inputs, outputs, registers  (Table 2)
tools/registry.py              # typed loaders, the only import path for vocab
tools/checks/registry_csv.py   # cross-check against docs/sources/, set-based
```

`table8_label` is the join key onto the CSV. It is what lets a rebuilt registry be
checked against the paper rather than against itself, so it is mandatory on four
of the five files.

### Gate

```bash
make test
# - 12 tasks, 11 metrics, 5 stages, 4 pdks, 18 circuits load
# - metric rows derive to 46; live cells to 880; live combos to 232
# - the PARTITION asserts: 40 void, 24 degenerate, 120 saturated
# - stage ids assert IN ORDER, not as a set
# - every task's metrics[] is a subset of metrics.json keys
# - every metric has a direction; mpe=optimistic, mne=conservative
# - percent flag is exactly {mape, mape_p95, mape_top5, tpr, tnr}
# - every table8_label joins to the CSV with ZERO unmatched, all 4 dimensions
# - circuits, metal_layers, utilization and units cross-check against docs/sources/
```

**Exit criteria:** no count literal in source, and every transcribed value is
checked against an independent source.

**Regression guard.** These three mutations all left the pre-reset suite green.
The new suite must fail on each:

1. reverse every `stages.json` `order`
2. change `ethernet.registers` from 10,544 to 87
3. hardcode metric direction so the registry is bypassed

### Review prompt

```
Use a domain reviewer on data/registry/ and tools/registry.py against
docs/DATA_CONTRACT.md Appendix A. Verify per-task metric sets match Table 8
exactly, the 8 void combos are the specified ones, directions are right
(especially R² higher versus MAE lower), and the mpe/mne bias is encoded.
Then apply the three regression mutations above and confirm each one fails the
suite. Report only mismatches.
```

---

## Phase 2 - Baseline

### Scope

`data/baseline.json`, keyed `(task, metric, pdk, stage)`, generated from
`docs/sources/table8_baseline.csv` by joining on `table8_label`.

**This is a mechanical join, already verified: all four dimensions map with zero
unmatched.** It is not a research task.

Three `kind` values from the CSV map to three different stored shapes:

| CSV `kind` | Count | Stored as |
|---|---|---|
| `VAL` | 856 | exact value, or a one-sided bound for the 32 sentinels |
| `VOID` | 40 | absent; the cell is not part of the 880 |
| `DEGENERATE` | 24 | `baseline_value: null`, `baseline_state: "degenerate"` |

**Percent metrics are divided by 100 on read.** The CSV is in display units.

**Sentinels are one-sided bounds, not values with a display override.** `> 10000 %`
becomes a `greater_than` bound at `100.0`; `< -1` becomes a `less_than` bound at
`-1.0`. The underlying number does not exist and must not be invented.

### Gate

```bash
make validate && pytest tests/test_baseline.py
# - every one of the 880 live cells resolves: 856 published + 24 degenerate
# - all 40 void cells are absent, not null
# - every entry has "source": "paper"
# - 20 greater_than bounds and 12 less_than bounds, all on the right metrics
# - tpr and tnr all land in [0, 1] after conversion    <- catches the 100x error
# - no MAPE range assertion exists                     <- 48 real cells exceed 150%
# - saturated flags match the registry rule, not a numeric test
```

### Review prompt

```
Use a data-integrity reviewer to spot-check data/baseline.json against
docs/sources/table8_baseline.csv for ten cells across different tasks and stages,
including at least one sentinel, one degenerate and one saturated. Confirm every
percent metric was divided by 100 exactly once. Report any transcription error.
```

---

## Phase 3 - The matrix page

**This is the vertical slice, and it is the most important reordering in this
plan.** It ships a real, useful page to Pages before ingest, synthetic fill or any
guard exists.

There are no submissions yet, so every live cell renders `no_entry` or
`saturated`. That is not a limitation, it is the point: the grid is exercised at
full scale against 856 real published baselines, and every rendering question gets
answered before any of it is built on top of.

### What this phase de-risks

- the 880-cell grid at real scale, including scroll and layout behaviour
- saturation, degeneracy and sentinel rendering, which are three distinct visual
  cases that are easy to conflate
- the stage strip, the track toggle and the task/metric row collapse
- contrast and keyboard navigation, in both themes' variable contract
- the real page-weight budget, measured rather than assumed

### Scope

```
build.py                       # load registries + baseline, render, copy assets
templates/base.html
templates/pages/matrix.html
static/css/base.css
static/css/themes/            # the variable contract, one file per theme
static/js/matrix.js           # stage switching, vanilla, one file
```

Templates hold loops and conditionals only. All computation lands in the context
dict from `build.py`.

Four states are distinguishable **without colour**: an icon or glyph channel runs
alongside the colour channel.

### Gate

```bash
make build && pytest tests/test_matrix.py
# - dist/index.html contains exactly 880 cell elements, derived not hardcoded
# - every cell carries exactly one state class
# - the 40 void cells render as structurally absent, not as empty cells
# - the 24 degenerate cells never print a number
# - the 32 sentinel cells render the sentinel, never a bare bound value
# - zero cells render undefined, NaN or null
# - build completes in under 60s
# - no page exceeds 88 KB
lychee dist/
pa11y-ci                       # both themes, WCAG AA
```

**Exit criteria: the page is live on GitHub Pages and a human has clicked through
all five stages.** Not "the build succeeded".

### Review prompt

```
Use a frontend reviewer on dist/ and static/css/. Check contrast >= 4.5:1 for
every cell state in both themes, that state is distinguishable without colour,
that the table is keyboard navigable, and that stage pills are real buttons with
aria-pressed. Separately confirm the three visually distinct cases - saturated,
degenerate and sentinel - are not rendered identically. Report only WCAG AA
failures and case conflations.
```

---

## Phase 4 - Ingest and ranking

Now the 20 real combos light up the comparison states, and the ranking logic gets
a real consumer on the same day it is written.

### Kickoff prompt

```
Read PLAN.md Phase 4 and the "Data gotchas" section of CLAUDE.md. Build the
ingest pipeline and the ranking module together. Ranking must be called by
build.py in this phase; do not ship it uncalled.

Input tree:
  <task>_prediction/<family>/<config>_<PDK>_<STAGE>/<circuit>/version_0/

Read only eval.log, submission.yaml, and one hparams.yaml and one .ckpt per
architecture. Write the failing test for the stage-name underscore case first.
```

### Scope

```
tools/paths.py     # anchored regex against registry vocab, never rsplit
tools/ingest.py    # eval.log -> shards
tools/ckpt.py      # restricted zip reader, never unpickles
tools/yamlsafe.py  # tag-stripping SafeLoader
tools/ranking.py   # direction, bias, sentinels, cell state
```

**Available data is one task.** `total_area_prediction`, one architecture family,
20 combos, 34 MB. The other 11 tasks have no data at all. This phase ingests what
exists; it does not wait for the rest.

Rules that have already cost time:

- Parse paths with an anchored regex. `rsplit("_", 2)` on
  `default_config_ng45_global_place` yields `stage="place"`.
- PDK directory names are uppercase; normalize case-insensitively.
- `eval.log` MAPE is already a fraction. **Do not convert it.**
- Macro-mean across circuits for MAE and MAPE; median for R², plus `n_positive`.
- Never unpickle. `weights_only=True` refuses all 360 of the lab's checkpoints and
  the suggested `weights_only=False` is the exact hazard. Walk the zip.
- `hparams.yaml` lies about architecture and breaks `safe_load`. Shapes come from
  checkpoint tensors.
- Ignore the CSV R² columns, the `eval.log` "Overall" block and all tfevents.
- Cross-check every ingested value against the Phase 2 baseline and **flag an
  order-of-magnitude divergence**. This is the detector for a percent error, which
  no range guard can catch on MAPE.

### Gate

```bash
pytest tests/test_ingest.py tests/test_ranking.py -v
# - all 5 stage names parse, including the 3 containing underscores
# - eval.log MAPE is NOT rescaled; stored value stays a fraction
# - macro-mean differs from pooled on a fixture where they differ
# - R² uses median, not mean, on a fixture containing -335
# - the real sample folder yields exactly 20 combos of total_area
# - ckpt reader recovers 41 -> 64 -> 32 -> 16 -> 1 from a real fixture
# - hparams in_features:7 is parsed and then IGNORED
# - grep asserts torch.load, yaml.full_load, yaml.UnsafeLoader and
#   add_safe_globals appear nowhere in tools/
# - ranking is imported by build.py            <- no uncalled module
make ingest && make validate && make build
```

**Exit criteria:** every number in the output traces to a line in an `eval.log`,
and the matrix shows real `beats_baseline` / `matches_baseline` /
`baseline_leads` states on the 20 combos.

### Review prompt

```
Use a data-integrity reviewer on tools/ingest.py and tools/ranking.py. Trace one
metric end to end: pick ac97_ctrl at NG45 floorplan, find its line in eval.log,
and confirm the emitted value is that number with the documented transformations
and nothing else. Confirm no path reads the CSV R² columns, the Overall block or
tfevents. Confirm percent metrics were not rescaled at ingest. Report only
correctness gaps.
```

---

## Phase 5 - Cell pages

232 pre-rendered pages. Baseline pinned above the ranking, filters, plots, CSV and
JSON export.

Saturated pages render the saturated notice and no ranking. Degenerate cells show
the entry without a comparison. Sentinel cells show the bound and, where the
comparison is undecidable, say so rather than guessing.

### Gate

```bash
make build && pytest tests/test_cells.py
# - 232 pages generated, zero 404s from the matrix
# - baseline row present and visually distinct on every page
# - saturated pages render the notice and no ranking
# - degenerate pages render no comparison
# - no page exceeds 88 KB; dist/ total under 20 MB
lychee dist/
```

---

## Phase 6 - Guard layers

Submissions are not open until this lands. It is built **after** the readers it
guards, not before.

Layers:

1. **Feature-stage legality** against Table 1, via `data/registry/attributes.json`
2. **Split overlap** - reject train/test intersection
3. **Divisions** - closed requires canonical split, features, target
4. **Runnability** - `predict.py` runs on the smoke slice under 10 min
5. **Plausibility** - error below the dataset's own reported precision is flagged,
   and an entry leading an `mpe` cell while sitting in the tail of the matching
   `mae` cell is flagged

### Gate

```bash
pytest tests/test_guard.py
# each layer has a passing fixture and a failing fixture
# layer 1 rejects a submission declaring net.length at floorplan
# layer 1 accepts all 41 of the lab's declared features
# layer 5 flags MAE 0.00001 on cell_arc_delay (4-decimal ground truth)
make validate
```

**Blocked on an open decision:** Table 1 lists `Netlist.total_hpwl` as available
from `FP-F`, which contradicts Table 8's footnote voiding `total_wirelength` at
floorplan. Resolve before generating `attributes.json`.

### Review prompt

```
Use a security reviewer on tools/guard/. Assume an adversarial submitter who
wants a green cell without a working model. Name every way through the guard, and
for each say whether it is blocked, flagged or undetected. Report only
exploitable gaps.
```

---

## Phase 7 - Synthetic fill decision

**This is a decision point, not a task.** By now a real matrix has been live for
several phases against 856 real baselines and 20 real combos, so the question can
be answered with evidence instead of a guess.

The question: does the leaderboard launch with generated fill for the 212 combos
that have no data?

| Option | Consequence |
|---|---|
| No synthetic | Honest on day one. A mostly-`no_entry` grid, which is exactly what a new leaderboard looks like. |
| Synthetic, marked | Every UI path exercised at scale, but a leaderboard other labs cite is ~91% generated on launch. |
| Wait for real data | Launch slips to the lab's training run. |

If synthetic ships: `tools/synth.py`, seeded and deterministic, every record
`"source": "synthetic"`, visible marker, excluded from cells-won, and zero
synthetic records in void or saturated cells.

**Recommendation: no synthetic.** The audit's judgement was that a grid honestly
showing 20 real combos is a stronger artifact for a citable leaderboard than one
showing 232 combos of which 212 are invented. Revisit against the live page.

---

## Phase 8 - Explore, card, submit, model pages

- `/explore/` - flat table, five filters, virtual scroll
- `/about/card/` - leaderboard card from `docs/CARD.yaml`
- `/submit/` - submission guide, `predict.py` signature, badge criteria.
  **Creates `docs/SUBMISSION.md`**, which `CLAUDE.md` referenced before it existed.
- `/model/?id=` - client-hydrated, with the architecture renderer drawing layer
  blocks proportional to layer width

### Gate

```bash
pytest tests/test_pages.py tests/test_arch_render.py
# - explore filters correctly on each of the 5 axes
# - card renders every required section; a missing section fails the build
# - the lab's fixed MLP renders as 41 -> 64 -> 32 -> 16 -> 1 with 5,313 params
# - a 40-layer fixture degrades gracefully rather than overflowing
# - submit page links resolve
```

---

## Phase 9 - Themes, deploy and transfer

Two stylesheets against one CSS-variable contract, switched by one line in
`build.py`. `drexel` (#07294D navy, #FFC600 gold, serif headings) and `neutral`.
Both share the colourblind-safe four-state data palette.

Then transfer to `drexel-ice`, re-apply branch protection and CODEOWNERS, add the
required approving review that Phase 0 deferred, update the CNAME, and **re-run
the negative test against the transferred repo**. Protection that silently did not
survive is worse than none, because you will believe it is there.

> **`gh repo transfer` does not exist.** Verified against gh 2.83.2:
> `unknown command "transfer" for "gh repo"`. An earlier draft of this plan
> quoted it. Use the REST endpoint instead:
>
> ```bash
> gh api -X POST repos/JiwaniZakir/eda-schema-leaderboard/transfer \
>   -f new_owner=drexel-ice
> ```

### Gate

```bash
pytest tests/test_themes.py     # both implement every variable in the contract
gh workflow run deploy.yml && gh run watch
curl -sI https://<domain>/ | head -1     # 200
du -sh dist/                             # well under 1 GB
# repository_dispatch from the experiments repo triggers a rebuild
```

---

## The 2026-08-11 goal review, and what it changed

After all nine plans were written, an adversarial reviewer was asked one
question: does this plan deliver the goal? It found that **it did not**, and the
gap was the same shape as the one the reset was meant to fix, one level up.

**The plan built a baseline browser, not a leaderboard.** `data/cells/**` is the
only entry source the site reads, and across nine phases it was written by
exactly two things: `tools/ingest.py`, reading the lab's own results tree, and
`tools/synth.py`, which is conditional. Phase 6 builds a five-layer guard over
`submissions/`, emits advisory findings, and stops. Nothing turned a merged,
guard-passing submission into a shard. A third party could clear every layer and
appear nowhere on the site, so "showing how **submitted models** compare against
the paper's published baseline" was delivered by no phase.

That is now **Phase 10**, and two rulings shape it:

- **Trust is hybrid.** Declared metrics publish immediately behind a visible
  `self-reported` marker and are promoted to `verified` only when our own runner
  reproduces them within tolerance. A self-reported number must never be
  presentable as a verified one, and a reproduction that disagrees is itself a
  published state rather than a silent correction.
- **It ships after the site is live**, for the same reason Phase 3 comes before
  Phase 4: the live page is what de-risks everything built on it.

Four further findings were confirmed and fixed immediately, because each was a
gate that passes while the thing it checks is wrong:

| Finding | Consequence if unfixed | Fix |
|---|---|---|
| `SITE_BASE` asserted by Phase 3, set nowhere | every stylesheet and script 404s on the deployed site while `index.html` still returns 200, so a curl smoke check passes on a visibly broken page | `deploy.yml` runs `configure-pages` **before** the build and passes `base_path` |
| CI's `build` job runs `build.py`, a Phase 3 deliverable | the required check is unsatisfiable on the Phase 1 and Phase 2 PRs, so branch protection blocks the two phases everything else is built on | the job runs `make build`, which skips loudly until the file exists |
| Phase 3 called `bl.baseline(...)` and built `Bound("exact", ...)` from raw strings | `AttributeError` on the first cell rendered, plus `mypy --strict` failures, three phases after Phase 2 shipped | reconciled to `baseline.lookup(...)` and `BoundKind.EXACT` |
| Phase 1's gate claimed a cross-check against `docs/sources/` that only held `table8_baseline.csv` | 51 transcribed circuit values and the metal-layer counts were checked against literals in the test file, which is the exact gap the audit named, while the gate declared it fixed | `docs/sources/table2_circuits.csv` and `pdk_physical.csv` extracted from the paper, so the check is real and works in CI |

The reviewer also confirmed what the plan gets right, which is worth recording:
no gate asserts a total where a partition is required, Phase 3 depends on nothing
scheduled after it, `tools/ckpt.py` has a real in-phase consumer, ranking ships
with its caller, and Phase 7's 1,150 conditional lines are a labelled contingency
rather than dead weight.

**One number to keep in view.** With synthetic ruled out, the site launches with
48 of 736 rankable cells populated, from one task of twelve. The plan is honest
about that rather than evasive, but no phase raises the number, and Phase 10 is
the only mechanism that ever could without waiting on a lab training run that
open decision 6 says has not happened.

---

## Open decisions

Four of these gate a phase. Two need a human other than the maintainer.

| # | Decision | Gates | Needs |
|---|---|---|---|
| 1 | **Baseline is row-pooled, our models are macro-mean.** Comparing them is comparing two different estimators, and the leaderboard's central claim rests on that comparison. Recommendation: compute both, rank on macro-mean, display the published pooled figure as "as published". | Phase 4 | maintainer |
| 2 | **Table 1 says `Netlist.total_hpwl` is available at `FP-F`**, contradicting Table 8's footnote voiding `total_wirelength` at floorplan. | Phase 6 | maintainer |
| 3 | **Twelve cells are already optimal at CTS** and can only be tied, not beaten. The stage saturation rule does not cover them, so they render as permanently `baseline_leads`. Extend saturation, or accept them. | Phase 3 | maintainer |
| 4 | **The four tail metrics have no published formula**, only prose. `mae_p95` is a quantile, not a mean of the top 5%; `mae_top5` selects by target magnitude, not error magnitude. | Phase 4 | **Pratik** |
| 5 | The paper's p.21 "three prediction tasks" contradicts the abstract and Table 8, which both say twelve. | before the card cites a count | **Savidis** |
| 6 | Whether launch waits for a real training run. Current models are undertrained at 50 gradient steps with a training R² median of 0.020. | Phase 7 | **Savidis** |

---

## Cross-phase discipline

**Every phase ends the same way.** Gate command run, output shown, adversarial
review passed, committed, `/clear`.

**Ship the consumer with the abstraction.** The pre-reset build had a 217-line
ranking module with no caller, so it was only tested against itself. If a module
has no consumer in its own phase, it is in the wrong phase.

**No guard before its subject.** 266 lines and 40 tests guarded unpickling in a
repo with no checkpoint reader, while 54 transcribed circuit attributes had no
check at all. Guards belong in the phase that creates the risk.

**Test against an independent source.** A test that reads the same JSON it
asserts against verifies nothing. `docs/sources/` is the independent source; use
it.

**Assert partitions, not totals.** 880 stays correct while degeneracy and
saturation are swapped. 40/24/120 does not.

**When a gate fails twice on the same issue,** stop correcting. The context is
polluted with failed approaches. `/clear` and restart the phase with a prompt that
incorporates what you learned.

**Scope investigations to subagents** so exploration does not fill the main
context.

**A reviewer asked to find gaps will find some, even when the work is sound.**
Every review prompt says to report only correctness and requirement gaps. Treat
style findings as optional and resist chasing them; that path leads to defensive
code and tests for cases that cannot happen.
