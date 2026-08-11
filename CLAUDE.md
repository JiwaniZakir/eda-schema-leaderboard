# EDA-Schema Leaderboard

Static benchmark leaderboard for the EDA-Schema-V2 dataset (arXiv:2605.06952).
Python + Jinja2 → static HTML → GitHub Pages. No framework, no bundler, no Node.

Detail lives in `docs/`. Read those on demand, not by default:
- Build plan and phase gates: @PLAN.md
- Data contract and field definitions: @docs/DATA_CONTRACT.md
- Submission rules and verification tiers: @docs/SUBMISSION.md

## Commands

```bash
make install        # uv sync
make ingest         # parse experiments repo → data/ shards
make synth          # regenerate synthetic fill for unpopulated cells
make validate       # JSON Schema + guard layers 1-5; exits non-zero on failure
make build          # render dist/
make serve          # dist/ on :8000
make test           # pytest
make check          # validate + test + build — run this before any commit
```

`make check` is the gate. YOU MUST run it and show the output before claiming a
task is complete. Do not report success from reading the code.

## The grid

Five dimensions, all defined in `data/registry/`. Registries are the single
source of truth — never hardcode a task, PDK, stage, metric, or circuit name
anywhere else.

- 12 tasks × 4 PDKs × 5 stage transitions = 240 combos, **232 live**
  (8 void: `total_wirelength` and `interconnect_length` have no floorplan estimate)
- 46 metric rows × 4 PDKs × 5 stages = 920, **880 live cells**, of which **856
  have a published baseline**. The other 24 are `mpe`/`mne` for the three slack
  tasks at `global_route`, printed as "No positive or negative error, n_p = n_n =
  0". That is a 0/0, not a zero. They stay live but carry `baseline_value: null`
  and `baseline_state: "degenerate"`, so nothing can win against a baseline that
  was never measured. See @docs/DATA_CONTRACT.md.
- Cell identity is `(task, metric, pdk, stage)`. Shard files are keyed at
  `(task, pdk, stage)` — one file serves all of that task's metric cells.

Five cell states: `beats_baseline`, `matches_baseline`, `baseline_leads`,
`no_entry`, `saturated`. Tying is the best achievable outcome on ~132 cells, so
`matches_baseline` is a real state, not an edge case.

**Saturation is a stage/task rule, never a numeric test:** `global_route`, minus
the two wirelength tasks, minus the degenerate cells — exactly 120. A predicate
like `mae==0 and mape==0 and r2==1` catches only 5 of the 10 saturated tasks,
because the other five publish no MAPE row, no R² row, or neither. Saturated cells
are never ranked and never colored win/loss.

## Data gotchas

These have all bitten us already. They are not hypothetical.

**Stage names contain underscores.** `rsplit("_", 2)` on
`default_config_ng45_global_place` yields `stage="place"`. Always parse with the
anchored regex in `tools/paths.py`, which matches against registry vocabularies.

**`hparams.yaml` lies about architecture.** It reports `in_features: 7` where the
trained weight is `(64, 41)`, and `params=0` for every layer. Read architecture
from checkpoint tensor shapes only. Same for `default_config.dot` — it is wrong
and is excluded from the sparse checkout.

**Never unpickle a checkpoint.** A `.ckpt` is a pickle, and community submissions
run on our runner. `weights_only=True` is necessary but *not sufficient*: it
rejects all 360 of the lab's own checkpoints, because Lightning pickled
`eda_ml.schema.ModelConfig` into every one of them. Verified - 360 scanned, 360
refused. The error message helpfully suggests `weights_only=False`, which is the
arbitrary-code-execution path this rule exists to prevent. Do not take it, and do
not grow a `safe_globals` allowlist either.

Read tensor shapes with the restricted reader in `tools/ckpt.py`: treat the `.ckpt`
as the zip it is, walk `data.pkl` with an `Unpickler` whose `find_class` returns an
inert placeholder for *any* foreign global, and recover shapes from the
`rebuild_tensor_v2` arguments. Foreign code is never executed, whatever the
checkpoint contains.

**`hparams.yaml` breaks `yaml.safe_load`.** It carries `!!python/object:` tags, so
`safe_load` raises `ConstructorError`. `full_load` and `UnsafeLoader` construct
arbitrary objects and are the same hazard as unpickling. Use the tag-stripping
`SafeLoader` subclass in `tools/yamlsafe.py`. And remember the file lies anyway -
architecture comes from tensor shapes.

**PDK directory names are uppercase.** `default_config_ASAP7_cts`, not `asap7`.
Registry IDs are lowercase. Path parsing is case-insensitive and normalizes to the
registry ID, or all 20 combos silently fail to resolve.

**Never ingest these:** `aggregated_eval_metrics.csv` R² columns (0.982–1.000
across every cell, row-pooled, meaningless), the `eval.log` "Overall" block
(also pooled), and all tfevents (z-scored targets, 200–700× off).

**`eval.log` MAPE is a fraction; the paper reports percent.** Multiply by 100 at
ingest, exactly once, in `tools/ingest.py`.

**Aggregate by macro-mean across the 18 circuits, never row-pooled.** For R²
report the per-circuit median plus a positive count — one −335 outlier destroys
a mean.

## Repository etiquette

- Branch naming: `phase-N/short-slug` for plan work, `fix/short-slug` otherwise
- Conventional commits (`feat:`, `fix:`, `chore:`, `docs:`)
- Every PR must pass `make check`; CI enforces it and branch protection blocks merge
- Never commit files over 1 MB. Checkpoints, PNGs and tfevents belong in GitHub
  Releases or Hugging Face, referenced by URL. GitHub Pages caps the published
  site at 1 GB and we intend to stay near 20 MB.
- Never commit anything under `data/` by hand. It is generated by `make ingest`
  and `make synth`.

## Code style

- Python 3.11+, type hints on all public functions, `ruff` and `mypy` clean
- Prefer pure functions in `tools/`; side effects only in `build.py` and CLI entry points
- Templates hold no logic beyond loops and conditionals — computation happens in
  `build.py` and lands in the context dict
- Vanilla JS only, one file per feature in `static/js/`. Prefer adding a small
  focused file over extending a large one.
- CSS custom properties for all color; both themes implement the same variable
  contract in `static/css/themes/`

## Synthetic data

Until real submissions land, most cells are filled by `make synth`. Every
synthetic record carries `"source": "synthetic"` and renders with a visible
marker. Prefer failing loudly over silently mixing synthetic and real data —
`make validate` errors if a record lacks an explicit `source`.

## Working style

Use plan mode for anything touching `tools/ingest.py`, the guard layers, or the
registries — those three have correctness consequences that spread everywhere.
For a one-line template or CSS change, just make it.

Use subagents for investigation so exploration doesn't fill the main context.
After each phase, run an adversarial review subagent against @PLAN.md and fix
only gaps that affect correctness or stated requirements.

When compacting, always preserve: the current phase number, the list of modified
files, and any failing check output.
