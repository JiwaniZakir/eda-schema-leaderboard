# EDA-Schema Leaderboard

Static benchmark leaderboard for the EDA-Schema-V2 dataset (arXiv:2605.06952).
Python + Jinja2 to static HTML on GitHub Pages. No framework, no bundler, no Node.

Detail lives in `docs/`. Read those on demand, not by default:
- Build plan and phase gates: @PLAN.md
- Data contract, field definitions and registry generation reference: @docs/DATA_CONTRACT.md

## Current state: post-reset

The repo was reset on 2026-08-11. All Python, tests, schema and generated
registries were deleted; the verified paper data, the data contract and the
GitHub CI infrastructure were kept. See @PLAN.md for what is being rebuilt and in
what order.

**What survives and is trusted:**
- `docs/sources/table8_baseline.csv` - 920/920 cells verified against the paper's
  LaTeX by two independent parsers. This is the most reliable artifact here.
- `docs/DATA_CONTRACT.md` - the vocabularies, the rules, and Appendix A, which is
  sufficient to regenerate all five registries with no other input.
- `.github/` - 7 workflows, branch protection with 7 required checks, both repos.

**What does not exist yet:** `tools/`, `tests/`, `schema/`, `data/`, `templates/`,
`static/`, `build.py`. Do not reference them as if they do.

## Commands

```bash
make install        # uv sync
make check          # the gate: lint, typecheck, validate, test, build
```

Other targets (`ingest`, `synth`, `validate`, `build`, `serve`, `test`) are
declared in the Makefile but only become real as the phases that create them land.
A target whose module does not exist yet fails loudly rather than silently passing.

`make check` is the gate. YOU MUST run it and show the output before claiming a
task is complete. Do not report success from reading the code.

## The grid

Five dimensions, all defined in `data/registry/` once it is regenerated.
Registries are the single source of truth. Never hardcode a task, PDK, stage,
metric or circuit name anywhere else.

- 12 tasks x 4 PDKs x 5 stage transitions = 240 combos, **232 live**
  (8 void: `total_wirelength` and `interconnect_length` have no floorplan estimate)
- 46 metric rows x 4 PDKs x 5 stages = 920, **880 live cells**, of which **856
  have a published baseline**. The other 24 are `mpe`/`mne` for the three slack
  tasks at `global_route`, printed as "No positive or negative error, n_p = n_n =
  0". That is a 0/0, not a zero. They stay live but carry `baseline_value: null`
  and `baseline_state: "degenerate"`, so nothing can win against a baseline that
  was never measured. See @docs/DATA_CONTRACT.md.
- Cell identity is `(task, metric, pdk, stage)`. Shard files are keyed at
  `(task, pdk, stage)`, one file serving all of that task's metric cells.

Five cell states: `beats_baseline`, `matches_baseline`, `baseline_leads`,
`no_entry`, `saturated`. Tying is the best achievable outcome on ~132 cells, so
`matches_baseline` is a real state, not an edge case.

**Saturation is a stage/task rule, never a numeric test:** `global_route`, minus
the two wirelength tasks, minus the degenerate cells, exactly 120. A predicate
like `mae==0 and mape==0 and r2==1` catches only 5 of the 10 saturated tasks,
because the other five publish no MAPE row, no R² row, or neither. Saturated cells
are never ranked and never colored win/loss.

**Assert the partition, not the total.** 40 void / 24 degenerate / 120 saturated.
Checking only "880 live cells" passes even when degeneracy and saturation are
swapped, which silently mistypes 24 cells. Same for stage `order`: assert the ids
in sequence, because `sorted(orders) == range(1, n+1)` passes on a fully reversed
list.

## Data gotchas

These have all bitten us already. They are not hypothetical.

**Percent metrics are stored as fractions.** `mape`, `mape_p95`, `mape_top5`,
`tpr` and `tnr` live in `[0, 1]` everywhere under `data/`, and are multiplied by
100 exactly once, at the display boundary. **The CSV is in display units and must
be divided by 100 on read; `eval.log` is already a fraction and must not be
converted.** Getting this backwards does not raise: every MAPE cell silently
renders `baseline_leads` and every TPR/TNR cell silently renders `beats_baseline`,
which looks like a plausible finding rather than a bug. Guard `tpr`/`tnr` with an
assert that they land in `[0, 1]`; MAPE is unbounded above (its ceiling is the
`> 10000 %` sentinel, `100.0` as a fraction) so a range guard there is wrong and
would reject 48 real cells. Full rule and the reasoning: @docs/DATA_CONTRACT.md.

**Stage names contain underscores.** `rsplit("_", 2)` on
`default_config_ng45_global_place` yields `stage="place"`. Parse only with a regex
anchored on the registry vocabularies, never by splitting.

**PDK directory names are uppercase.** `default_config_ASAP7_cts`, not `asap7`.
Registry IDs are lowercase. Path parsing is case-insensitive and normalizes to the
registry ID, or all 20 combos silently fail to resolve.

**`hparams.yaml` lies about architecture.** It reports `in_features: 7` where the
trained weight is `(64, 41)`, and `params=0` for every layer. Read architecture
from checkpoint tensor shapes only. Same for `default_config.dot`, which is wrong
and is excluded from the sparse checkout.

**Never unpickle a checkpoint.** A `.ckpt` is a pickle, and community submissions
run on our runner. `weights_only=True` is necessary but *not sufficient*: it
rejects all 360 of the lab's own checkpoints, because Lightning pickled
`eda_ml.schema.ModelConfig` into every one of them. Verified, 360 scanned, 360
refused. The error message helpfully suggests `weights_only=False`, which is the
arbitrary-code-execution path this rule exists to prevent. Do not take it, and do
not grow a `safe_globals` allowlist either.

Read tensor shapes with a restricted reader: treat the `.ckpt` as the zip it is,
walk `data.pkl` with an `Unpickler` whose `find_class` returns an inert
placeholder for *any* foreign global, and recover shapes from the
`rebuild_tensor_v2` arguments. Foreign code is never executed, whatever the
checkpoint contains.

**`hparams.yaml` breaks `yaml.safe_load`.** It carries `!!python/object:` tags, so
`safe_load` raises `ConstructorError`. `full_load` and `UnsafeLoader` construct
arbitrary objects and are the same hazard as unpickling. Use a tag-stripping
`SafeLoader` subclass. And remember the file lies anyway; architecture comes from
tensor shapes.

**Never ingest these:** `aggregated_eval_metrics.csv` R² columns (0.982 to 1.000
across every cell, row-pooled, meaningless), the `eval.log` "Overall" block
(also pooled), and all tfevents (z-scored targets, 200 to 700x off).

**Aggregate by macro-mean across the 18 circuits, never row-pooled.** For R²
report the per-circuit median plus a positive count; one -335 outlier destroys
a mean. Note that Table 8's own baseline is row-pooled, so the two sides of a
comparison use different estimators. That is an open decision, not a settled one.
See @docs/DATA_CONTRACT.md.

## Repository etiquette

- Branch naming: `phase-N/short-slug` for plan work, `fix/short-slug` otherwise
- Conventional commits (`feat:`, `fix:`, `chore:`, `docs:`)
- Every PR must pass `make check`; CI enforces it and branch protection blocks merge
- Never commit files over 1 MB. Checkpoints, PNGs and tfevents belong in GitHub
  Releases or Hugging Face, referenced by URL. GitHub Pages caps the published
  site at 1 GB and we intend to stay near 20 MB, so the per-page budget is roughly
  88 KB across 232 cell pages, not the 500 KB an earlier draft implied.
- Never commit anything under `data/` by hand. It is generated.
- Never use an em dash in prose. Use a plain dash.

## Code style

- Python 3.11+, type hints on all public functions, `ruff` and `mypy` clean
- Prefer pure functions in `tools/`; side effects only in `build.py` and CLI entry points
- Templates hold no logic beyond loops and conditionals. Computation happens in
  `build.py` and lands in the context dict
- Vanilla JS only, one file per feature in `static/js/`. Prefer adding a small
  focused file over extending a large one.
- CSS custom properties for all color; both themes implement the same variable
  contract in `static/css/themes/`

## Testing that actually verifies

The pre-reset suite had 115 passing tests, of which 85 survived a wrongly
regenerated registry. Three mutations that left it fully green: hardcoding metric
direction so it bypassed the registry, reversing every stage `order`, and changing
`ethernet.registers` from 10,544 to 87. Avoid repeating that shape:

- A test that reads the same JSON it asserts against verifies nothing. Cross-check
  against `docs/sources/`, which is an independent source.
- Do not write a guard for code that does not exist yet. The pre-reset repo had
  266 lines and 40 tests guarding unpickling in a repo with no checkpoint reader,
  while 54 transcribed circuit attributes had no check at all.
- If a docstring claims coverage, verify the claim. One asserted it derived a
  count "two independent ways" when both sides were the same comprehension.

## Synthetic data

Deferred. The decision on whether to ship synthetic fill at all is made in a later
phase, with evidence from a real matrix rendering real baselines. If it does land,
every record carries `"source": "synthetic"`, renders with a visible marker and is
excluded from cells-won, and `make validate` fails on any record lacking an
explicit `source`.

## Working style

Use plan mode for anything touching ingest, the guard layers, or the registries.
Those three have correctness consequences that spread everywhere. For a one-line
template or CSS change, just make it.

Use subagents for investigation so exploration doesn't fill the main context.
After each phase, run an adversarial review subagent against @PLAN.md and fix
only gaps that affect correctness or stated requirements.

When compacting, always preserve: the current phase number, the list of modified
files, and any failing check output.
