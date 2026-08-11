# Data contract

The field definitions and vocabularies behind the EDA-Schema leaderboard grid.

Everything here is transcribed from arXiv:2605.06952 (EDA-Schema-V2) or derived
programmatically from its published tables.
Every claim cites its source.
Anything the paper does not state is marked **OPEN** rather than inferred.

`data/registry/` is generated to match this document.
When the two disagree, this document is wrong and gets fixed first.

## Provenance

Verbatim source material is preserved under `docs/sources/`:

| File | Committed | What it is |
|---|---|---|
| `sources/table8_baseline.csv` | **yes** | Table 8 parsed to 920 tidy rows, one per `(task, metric, stage, pdk)` |
| `sources/verbatim/table8_baseline_source.tex` | no | Table 8 as LaTeX, from the arXiv e-print tarball |
| `sources/verbatim/table8_pdf_layout.txt` | no | Table 8 region via `pdftotext -layout`, for cross-checking. **Truncated** - see PROVENANCE.md |
| `sources/verbatim/table8_recovered.md` | no | Human-readable transcription of all 5 stage groups |
| `sources/verbatim/table1_attributes.txt` | no | Table 1, attribute stage-availability |
| `sources/verbatim/table2_circuits.txt` | no | Table 2, circuit characteristics |

`verbatim/` is gitignored on purpose: it is the authors' copyrighted text and
republishing it is not ours to do. The CSV holds measurements, which are facts, and
is the only thing under `docs/` the build reads. See `docs/sources/PROVENANCE.md`.

All 856 published cells in the CSV were cross-checked against the PDF text layer.
Zero mismatches.
Re-verified 2026-08-11 by an independent second parser run directly against the
LaTeX source, diffing positionally: **920/920 cells agree.** The `kind` column also
proved a perfect discriminator of the LaTeX column structure - `VAL` maps to a
single column, `VOID` and `DEGENERATE` to a `\multicolumn` span, with zero
violations - which confirms the classification came from table structure rather
than from inference over values.

### A correction to the build plan

PLAN.md Phase 2 states that only 14 of 20 stage-PDK column groups are recoverable,
that CTS carries NG45 and SKY130 only, that `global_route` is missing entirely,
and that the source CSV must be requested from Pratik.

That is not correct.
Table 8 sits entirely on **page 28**, inside a `\begin{landscape}` block and a
`\resizebox`.
The rotation and rescaling are what shred naive text extraction, not a page break.
The LaTeX source and `pdftotext -layout` both read all 20 groups cleanly.

**No external data request is needed.**
Every baseline entry is `"source": "paper"`.

## The grid

Cell identity is `(task, metric, pdk, stage)`.

Counts are derived in `tests/test_registry.py`, never written as literals:

```
46 metric rows x 4 pdks x 5 stages          = 920 cells
  minus 40 floorplan void (no placement)    = 880
  minus 24 global_route degenerate MPE/MNE  = 856 cells with a published baseline
```

`232` live combos is `12 tasks x 4 pdks x 5 stages = 240`, minus the 8 void
`(task, pdk, floorplan)` combos.

## Tasks

Twelve prediction targets.
The paper never lists these as a task set; they are the twelve row-groups of
Table 8, described in prose in Section 6.2 (p.24).

Every task predicts a **final post-`detailed_route` value** from an earlier stage's
tool estimate.

**IDs are the lab's, not ours.**
An earlier draft of this contract stripped the `_prediction` suffix for shorter
URLs.
That was wrong.
`compute_error_metrics.py` in `drexel-ice/EDA-schema`, the script that generated
Table 8, defines these identifiers in its `PROBLEM_LABELS` map, and the results
tree on disk is laid out as `total_area_prediction/`.
Anyone submitting through the lab's own tooling already has these strings.

Shortening them would have bought slightly tidier URLs and cost a translation layer
at every submission boundary, which is the trade the ID convention exists to avoid.
Use them verbatim.
`label` carries the display text, so nothing is lost by keeping the primary key
faithful.

| ID | Table 8 label | Unit | Granularity |
|---|---|---|---|
| `total_area_prediction` | Total Area | µm² | design |
| `total_power_prediction` | Total Power | µW | design |
| `total_wirelength_prediction` | Total wirelength | µm | design |
| `interconnect_length_prediction` | Interconnect length | µm | net |
| `worst_arrival_time_prediction` | Worst Arrival Time | ns | design |
| `worst_slack_prediction` | Worst Slack | ns | design |
| `total_negative_slack_prediction` | Total Negative Slack | ns | design |
| `timing_path_arrival_time_prediction` | Timing Path Arrival Time | ns | path |
| `timing_path_slack_prediction` | Timing Path Slack | ns | path |
| `net_arc_delay_prediction` | Net Arc Delay | ns | net arc |
| `cell_arc_delay_prediction` | Cell Arc Delay | ns | cell arc |
| `cell_arc_slew_prediction` | Cell Arc Slew | ns | cell arc |

The six design-level tasks are exactly the upstream `NETLIST_LEVEL_PROBLEMS` set:
`total_area`, `total_power`, `total_wirelength`, `worst_arrival_time`,
`worst_slack` and `total_negative_slack`, each `_prediction`.
That distinction is load-bearing, not cosmetic: it selects how records are gathered
before metrics are computed.

> **OPEN (paper inconsistency).**
> The abstract (p.1) says "twelve representative prediction tasks".
> The Section 6 introduction (p.21) says "A baseline analysis of **three**
> prediction tasks".
> Table 8 contains twelve.
> We treat twelve as correct and read the "three" as uncorrected draft text.
> Worth confirming with Savidis before the leaderboard card cites a count.

## Metrics

Eleven distinct metrics across the twelve tasks.

`direction` is what a ranking function optimizes.
It is declared once here and read from `metrics.json` everywhere.

| ID | Label | Direction | Notes |
|---|---|---|---|
| `mae` | Mean Absolute Error | lower | unit-bearing |
| `mape` | Mean Absolute Percentage Error | lower | percent |
| `r2` | Coefficient of determination | higher | |
| `mpe` | Mean Positive Error | lower | bias: `optimistic` |
| `mne` | Mean Negative Error | lower | bias: `conservative` |
| `tpr` | True Positive Rate | higher | percent |
| `tnr` | True Negative Rate | higher | percent |
| `mae_p95` | MAE, 95th percentile | lower | tail robustness |
| `mape_p95` | MAPE, 95th percentile | lower | tail robustness |
| `mae_top5` | MAE on the worst 5% | lower | longest nets / slowest paths |
| `mape_top5` | MAPE on the worst 5% | lower | longest nets / slowest paths |

Equations 9 to 15 (p.25 to 26) define exactly seven metrics: MAE, MAPE, R², MPE,
MNE, TPR and TNR.

> **OPEN (no published formula).**
> The four tail metrics have **no equation in the paper**, only prose on p.25.
> Whoever scores submissions has to pin down four definitions, and would otherwise
> do it silently.
> Note also that `mae_p95` is the 95th-percentile absolute error, a **quantile**,
> not a mean of the top 5%; the name invites the wrong reading.
> `mae_top5` and `mape_top5` are means over the longest 5% of nets or slowest 5% of
> paths, which is a different subset selected by target magnitude rather than by
> error magnitude.
> The reference implementation resolves all four, but it is CC BY-NC-SA and cannot
> be vendored, so these must be restated independently and confirmed with Pratik.

### Why some tasks omit MAPE or R²

Stated explicitly, p.25 to 26.
MAPE is not reported for slack-based metrics, because slack crosses zero and a
percentage error against a near-zero denominator is meaningless.

The paper also says R² is omitted for "all timing-based metrics".

> **Do not derive the metric sets from that sentence.**
> Table 8 contradicts it: `net_arc_delay`, `cell_arc_delay` and `cell_arc_slew` are
> arc-level timing metrics and each carries an R² row.
> All twelve `< -1` sentinels live in those three rows.
> An implementer applying the stated rule drops 3 rows and derives 43 metric rows
> instead of 46, which then fails Phase 1's gate for a reason that looks like an
> arithmetic bug.
> The per-task metric sets below are transcribed from the table itself and are
> authoritative.

This is a rule about the paper's reporting, not about which metrics are
computable.
It is why the per-task metric sets below are ragged rather than uniform.

### Directional bias on MPE and MNE

The paper, p.26:

> conservative predictions that slightly overestimate delay or underestimate slack
> are preferred [...] optimistic predictions that underestimate delay or
> overestimate slack are least desirable

MPE and MNE are reported only for the three slack tasks.
For slack, error is `predicted - actual`, so:

- positive error means predicted slack exceeded actual, an **optimistic** miss that
  hides a real timing violation
- negative error means predicted slack fell below actual, a **conservative** miss

Both are magnitudes to minimize, but a ranking function must penalize `mpe` more
heavily than an `mne` of equal magnitude.
Ranking these two as plain magnitude is a correctness bug, not a style choice.

**Confirmed against the reference implementation.**
`compute_error_metrics.py` computes `err = baseline - target`, then
`MPE = mean(err[err > 0])` and `MNE = mean(abs(err[err < 0]))`.
So the sign convention above is the one that actually produced Table 8, and both
metrics are published as positive magnitudes where lower is better.
This is no longer an inference from prose.

**Ranking rule (approved).**
Rank primarily on `mpe` ascending, then `mne` ascending.
Optimistic error leads the sort because an optimistic timing prediction hides a
real violation, and that is the failure with silicon consequences.
The paper gives no numeric exchange rate, so no weighted blend is invented; the
preference is expressed purely as sort order.

An earlier draft of this document proposed ranking primarily on `mne` while also
asserting that `mpe` should be penalised more heavily.
Those are opposites, and the `mne`-primary version is wrong: it makes the preferred
error the dominant key, so a model with a huge optimistic error and a tiny
conservative one would win.

**Known degenerate case.**
A model that always predicts wildly pessimistic slack never overestimates, scores
`mpe = 0`, and takes first place in the `mpe` cell while being useless.
This is accepted rather than patched, because `mae` is a separate cell in the same
grid and such a model places last there.
Phase 5's plausibility layer should flag a submission that leads an `mpe` cell
while sitting in the tail of the corresponding `mae` cell.

### TPR and TNR are classification metrics

Not regression metrics, and the leaderboard must not rank them as if they were.

The reference implementation classifies on the **sign of slack**: `true_v = target
< 0`, `pred_v = baseline < 0`, then TPR = `TP/(TP+FN)` and TNR = `TN/(TN+FP)`.
A timing violation is negative slack, so TPR is the share of real violations the
estimate caught and TNR the share of clean paths it correctly left alone.

Higher is better for both.
They are stored as fractions in `[0, 1]` and multiplied by 100 only at display,
exactly like MAPE.

## Per-task metric sets

Derived from `docs/sources/table8_baseline.csv`, not hand-copied.

| Task | n | Metrics |
|---|---|---|
| `total_area` | 3 | mae, mape, r2 |
| `total_power` | 3 | mae, mape, r2 |
| `total_wirelength` | 3 | mae, mape, r2 |
| `interconnect_length` | 7 | mae, mape, r2, mae_p95, mape_p95, mae_top5, mape_top5 |
| `worst_arrival_time` | 2 | mae, mape |
| `worst_slack` | 5 | mae, mpe, mne, tpr, tnr |
| `total_negative_slack` | 3 | mae, mpe, mne |
| `timing_path_arrival_time` | 6 | mae, mape, mae_p95, mape_p95, mae_top5, mape_top5 |
| `timing_path_slack` | 5 | mae, mpe, mne, tpr, tnr |
| `net_arc_delay` | 3 | mae, mape, r2 |
| `cell_arc_delay` | 3 | mae, mape, r2 |
| `cell_arc_slew` | 3 | mae, mape, r2 |
| **Total** | **46** | |

## PDKs

Metal layer counts from Section 4.1 (p.11).
Utilization from Section 4.2 (p.11), with the Table 5 sweep range (p.14).

| ID | Label | Metal layers | Base utilization | Sweep |
|---|---|---|---|---|
| `ng45` | Nangate 45 nm | 10 | 0.40 | 0.3, 0.4, 0.5 |
| `sky130` | SkyWater 130 nm | 5 | 0.30 | 0.2, 0.3, 0.4 |
| `ihp130` | IHP SG13G2 130 nm | 7 | 0.30 | 0.2, 0.3, 0.4 |
| `asap7` | ASAP 7 nm | 9 | 0.40 | 0.3, 0.4, 0.5 |

SKY130 and IHP130 use lower utilization to account for their smaller metal stacks.

> **Transcription trap.**
> The Table 8 column header spells the third PDK **`IPH130`**, and does so **5
> times**, once per stage group, in both the LaTeX source and the PDF text layer.
> Everywhere else the paper spells it `IHP130`, which is correct, since IHP is the
> foundry.
> The typo sits in exactly the string a table parser keys on, so a naive parse
> invents a phantom fifth PDK.
> Fix all five, not the first one.
> `docs/sources/table8_baseline.csv` already canonicalizes it to `IHP130`.

Directory names in the results tree are **uppercase** (`default_config_ASAP7_cts`).
Registry IDs are lowercase.
Path parsing must be case-insensitive and normalize to the registry ID.

## Stages

The schema defines eight design stages (Section 3.1, p.4 to 5):
`floorplan` (FP), `global_place` (GP), `place_resize` (PR), `detailed_place` (DP),
`cts` (CTS), `global_route` (GR), `detailed_route` (DR), `final` (F).

The benchmark uses **five stage transitions**, each predicting the same
`detailed_route` target from a different starting stage:

| ID | Order | Table 8 label |
|---|---|---|
| `floorplan` | 1 | floorplan to detailed route |
| `global_place` | 2 | global place to detailed route |
| `detailed_place` | 3 | detailed place to detailed route |
| `cts` | 4 | CTS to detailed route |
| `global_route` | 5 | global route to detailed route |

Stage IDs contain underscores.
`rsplit("_", 2)` on `default_config_ng45_global_place` yields `stage="place"`.
Parse only with the anchored regex in `tools/paths.py`, matched against this
vocabulary.

> **OPEN (paper inconsistency).**
> Section 6.2 prose (p.24) names six starting stages, including `place_resize`.
> Table 8 tabulates five.
> We follow the table.

## Circuits

Eighteen circuits from the IWLS'05 benchmark suite, Table 2 (p.11).
Attributes derive from pre-synthesis RTL.

| Circuit | Inputs | Outputs | Registers |
|---|---|---|---|
| `ac97_ctrl` | 84 | 48 | 2211 |
| `aes_core` | 259 | 129 | 562 |
| `des3_area` | 240 | 64 | 64 |
| `ethernet` | 96 | 115 | 10544 |
| `i2c` | 19 | 14 | 129 |
| `jpeg` | 20 | 27 | 4383 |
| `mem_ctrl` | 115 | 152 | 1083 |
| `pci` | 162 | 207 | 3220 |
| `sasc` | 16 | 12 | 118 |
| `simple_spi` | 16 | 12 | 131 |
| `spi` | 47 | 45 | 229 |
| `ss_pcm` | 19 | 9 | 87 |
| `systemcaes` | 260 | 129 | 670 |
| `systemcdes` | 132 | 65 | 190 |
| `tv80` | 14 | 32 | 361 |
| `usb_funct` | 128 | 121 | 1740 |
| `usb_phy` | 15 | 18 | 108 |
| `wb_dma` | 217 | 215 | 521 |

Aggregate model results across circuits by **macro-mean**, never row-pooled.
For R², report the per-circuit median plus a positive count.
A single R² of -335 destroys a mean.

## The baseline and our models are aggregated differently

This is the most dangerous thing in this document.

`compute_error_metrics.py` builds one pooled array before computing anything.
Design-level tasks read a single concatenated `all_circuits.csv`; the finer-grained
tasks do `np.concatenate` across every per-circuit CSV and compute one set of
statistics over the union.

**Table 8's baseline is therefore row-pooled.**
CLAUDE.md requires our ingest to use macro-mean across the 18 circuits.
Those are different estimators, and they disagree by more the more the circuits
differ in size, which is precisely the situation here: `ethernet` has 10,544
registers and `ss_pcm` has 87.

Pooling weights every row equally, so large circuits dominate.
Macro-mean weights every circuit equally.
Neither is wrong, but a `beats_baseline` verdict computed by comparing a macro-mean
model number against a pooled baseline number is comparing two different
quantities, and the leaderboard's central claim rests on that comparison.

Options, in the order they should be considered:

1. Recompute the baseline by macro-mean from the lab's per-circuit data, so both
   sides use one estimator. Correct, and needs data we do not yet have for 11 of
   the 12 tasks.
2. Report both aggregations per cell and rank on the macro-mean pair, using the
   published pooled figure only as a citation of the paper.
3. Rank on pooled to match the paper, and lose the robustness macro-mean was chosen
   for.

> **OPEN (decision needed, and it gates Phase 3).**
> Recommendation is option 2: compute both, rank on macro-mean, display the
> published pooled value as "as published" so the site never contradicts the paper
> it cites.
> Phase 3's existing ">10x divergence" warning is the detector for this, and its
> plan note already half-anticipated the cause.

## Cell states

Four states drive the matrix colouring.

| State | Meaning |
|---|---|
| `beats_baseline` | at least one entry outperforms the baseline |
| `matches_baseline` | best entry equals the baseline, and none beat it |
| `baseline_leads` | entries exist, none match or beat the baseline |
| `no_entry` | no submission yet |
| `saturated` | baseline is at the optimum; never ranked, never coloured win/loss |

`matches_baseline` exists because tying is the **best achievable outcome** on
roughly 132 cells: the 120 saturated ones plus the 12 already optimal at CTS.
Folding those into `baseline_leads` would render a submission that hit the
theoretical optimum as a loss.
Folding them into `beats_baseline` would inflate the cells-won tally with cells
nobody could win.

Void cells render as structurally absent and are not part of the 880.

### Saturation

**Saturation is a stage-and-task rule, not a numeric test.**

```
saturated  ==  stage is global_route
           and task not in {total_wirelength, interconnect_length}
           and the cell is not degenerate
```

That yields exactly **120 cells**: 36 metric rows across the 10 saturated tasks,
times 4 PDKs, is 144, less the 24 degenerate `mpe`/`mne` cells.

Do not implement this as a predicate over values.
Two ways that goes wrong:

- `mae == 0 and mape == 0 and r2 == 1.0` marks only 5 of the 10 saturated tasks.
  The other five have no MAPE row, no R² row, or neither: `worst_arrival_time` and
  `timing_path_arrival_time` publish no R², and the three slack tasks publish
  neither.
- 16 of the 120 are `tpr`/`tnr` at `100.00 %`: `worst_slack` and
  `timing_path_slack`, two metrics each, across 4 PDKs. A test for "error is
  approximately zero" against a rate sitting at its ceiling returns false.

The underlying fact is real: by global route the tool estimate has converged on the
detailed-route value for every task except the two wirelength ones, whose baseline
error stays live (total wirelength MAE on NG45 is still 13,698.67).
The rule above is simply the reliable way to express it.

> **OPEN.**
> Twelve further cells are already at the theoretical optimum at **CTS** and can
> only be tied, not beaten: `total_area` R² = 1.000 on all 4 PDKs, `total_power`
> R² = 1.000 on NG45/IHP130/ASAP7, `cell_arc_delay` MAE = 0.0000 on IHP130/ASAP7,
> `worst_slack` TPR = 100.00 % on NG45/ASAP7, and `worst_slack` MPE = 0.00 on
> ASAP7.
> The stage rule above does not cover them, so they render as rankable and
> permanently `baseline_leads`.
> Whether to extend saturation to any baseline-optimal cell, or accept the
> stage rule and let these twelve sit, is a decision Phase 6 needs.

## Void and degenerate cells

64 cells are unpopulated in Table 8, from two causes that are **not the same
thing** and must not share a `kind`.

An earlier draft called all 64 "void" while simultaneously claiming the 24
degenerate ones stayed live, which is a contradiction that yields 856 live cells
and fails PLAN.md Phase 1's gate of 880.
`docs/sources/table8_baseline.csv` now stamps three kinds, and the arithmetic is:

```
920 total
 - 40 VOID        (cell does not exist)     = 880 live
 - 24 DEGENERATE  (exists, baseline is 0/0) = 856 with a published baseline
```

`VOID` subtracts from the live count.
`DEGENERATE` does not.

### Class 1: no placement, 40 cells, kind `VOID`

`total_wirelength` (3 metrics) and `interconnect_length` (7 metrics), across 4 PDKs,
at `floorplan` only.

Table 8 footnote, verbatim:

> Estimated wirelength is not available as cells have not been placed yet.

Half-perimeter wirelength is the baseline estimator for both tasks (Section 6.2,
p.24).

These are the 8 void `(task, pdk, stage)` combos, and the reason 240 combos reduce
to 232.

> **OPEN (contradicts Table 1).**
> The intuitive explanation, that HPWL needs placed coordinates which do not exist
> at floorplan, is not what Table 1 says.
> Table 1 lists `Netlist.total_hpwl` as available from **`FP - F`**, which would
> make a floorplan-stage estimate available for `total_wirelength`.
> Per-net `Net.hpwl` is listed `GP - F`, which *is* consistent with
> `interconnect_length` being void.
> So Table 8's footnote and Table 1 disagree for one of the two tasks.
> This matters because Phase 5 guard layer 1 keys on Table 1's stage availability,
> so a rule derived from the footnote will contradict the registry generated from
> Table 1.
> Resolve before generating `attributes.json`.

### Class 2: degenerate MPE/MNE, 24 cells, kind `DEGENERATE`

`mpe` and `mne` for `worst_slack`, `total_negative_slack` and `timing_path_slack`,
across 4 PDKs, at `global_route` only.

Table 8, verbatim:

> No positive or negative error, n_p = n_n = 0

The baseline is exact at global route, so there are no positive and no negative
errors to average.
This is a `0/0`, not a value of zero.

**Decided.**
These 24 stay live, so 880 stands.
The cause is baseline perfection, exactly as with saturation.

Store `baseline_value: null` with `baseline_state: "degenerate"`, so the renderer
can never print `0.00` for an undefined quantity, and a model entry there is shown
without a comparison rather than as an automatic win.

The failure mode this guards against is a leaderboard awarding `beats_baseline`
against a baseline that was never measured.

## Published sentinels

Table 8 prints two sentinel forms, p.26.

**Correction 2026-08-11.** PLAN.md previously required both to "round-trip,
preserving the real value and displaying the sentinel". That is unsatisfiable for
baselines: the paper thresholded the underlying number away, so it does not exist
in any source we have. A sentinel baseline is stored as a **one-sided bound**, not
as a value with a display override. Only submissions carry an exact number on these
32 cells.

| Published | Count | Rule |
|---|---|---|
| `> 10000 %` | 20 cells | MAPE above 10000% |
| `< -1` | 12 cells | very negative R² |

> **OPEN (no comparison semantics).**
> For these 32 cells the underlying value does not exist; the paper thresholded it
> away, so "preserve the real value" is impossible for baselines.
> That leaves win/loss undefined: against `R² < -1`, a submission at −0.5 clearly
> wins and one at −3 is undecidable; against `MAPE > 10000 %`, a submission at
> 15000 % is undecidable.
> 32 cells need a rule before Phase 6 colours them.
> Recommendation is to treat a sentinel baseline as beatable only by a submission
> on the defined side of the threshold, and to render anything else as
> `no_comparison` rather than guessing.

Both are applied at format time, after the percent conversion, over a value stored
as a fraction.

## Percent storage - the single authoritative rule

**Ruled 2026-08-11.**
This is the highest-risk convention in the project and three documents previously
disagreed about it.
`CLAUDE.md` said multiply by 100 at ingest; this contract said never at ingest;
`PLAN.md`'s Phase 3 gate asserted `0.0051 -> 0.51`.
Following the wrong one corrupts published results silently, so the rule is stated
here once and everything else defers to it.

**Percent-format metrics are `mape`, `mape_p95`, `mape_top5`, `tpr` and `tnr`.**

**Everything under `data/` stores them as a fraction in `[0, 1]`.**
The `×100` happens exactly once, at the display boundary, and nowhere else.

Each input source therefore converts differently, and this is the part that bites:

| Source | Native form | Conversion on read |
|---|---|---|
| `docs/sources/table8_baseline.csv` | **display percent** (`12.43 %`, range 0 to 10000) | **divide by 100** |
| the lab's `eval.log` | **fraction** (`0.0051`) | **none** |
| a submission's declared value | fraction, per `schema/submission.schema.json` | none |

The CSV is the trap.
211 of its 252 percent values exceed 1.0, so it is unambiguously in display units
even though it is the baseline source.

### Why getting this wrong is not obvious

If baselines are stored as fractions and model values as percents, model numbers
are 100x larger than baselines for the same true error.
`mape` is lower-better, so **every MAPE cell silently renders `baseline_leads`**.
`tpr` and `tnr` are higher-better, so **every TPR/TNR cell silently renders
`beats_baseline`**.

Neither raises an error, and the result is entirely believable for models the
project already documents as undertrained at 50 gradient steps.
That is what makes it dangerous: the bug looks like a finding.

### How to guard it

A single range check does not work, because the two families have different
bounds. Verified against the CSV:

| Metric | Fraction range in Table 8 | Guard |
|---|---|---|
| `tpr`, `tnr` | 0.0839 to 1.0000 | **assert `0 <= v <= 1`** - a true rate, tight and exact |
| `mape`, `mape_p95`, `mape_top5` | 0.0000 to 100.0000 | **no range guard is possible** |

`tpr`/`tnr` are rates and genuinely cannot exceed 1, so the assertion is free and
catches the 100x error outright: a percent-stored TPR lands in 58.9 to 100.

MAPE is unbounded above. Its largest published value is the `> 10000 %` sentinel,
which is `100.0` as a fraction, and 48 of 244 published MAPE cells legitimately
exceed 150 %. A naive `[0, 1.5]` ceiling would reject all 48. **Do not add one.**

For the MAPE family the detector is the cross-check instead: compare every ingested
value against the published baseline for the same cell and flag an
order-of-magnitude divergence. A systematic 100x offset across a whole metric is
the signature, and it is visible in aggregate where it is invisible per cell.

## Display precision

The reference implementation rounds a specific set of `(task, metric)` pairs to
**4 decimal places**, and formats everything else to 2.

| Task | Metrics rounded to 4dp |
|---|---|
| `timing_path_arrival_time_prediction` | mae, mae_p95, mae_top5 |
| `timing_path_slack_prediction` | mae, mpe, mne |
| `net_arc_delay_prediction` | mae |
| `cell_arc_delay_prediction` | mae |
| `cell_arc_slew_prediction` | mae |

This is the ground truth for Phase 5's plausibility layer, which flags an error
below the dataset's own reported precision.
It is the source for PLAN.md's assertion that `cell_arc_delay` has 4-decimal
ground truth, so a submission claiming `MAE = 0.00001` there is claiming precision
the dataset cannot express.

## Source rules

Every record carries an explicit `source`.
`make validate` fails on any record that lacks one.

| Value | Meaning |
|---|---|
| `paper` | transcribed from Table 8 |
| `synthetic` | generated by `make synth`, rendered with a visible marker, excluded from cells-won |
| `submission` | a real community entry |

All 856 published baseline cells are `paper`.
No baseline is synthetic.

## Known gaps

Carried forward rather than resolved, and none block Phase 1.

1. **Baseline is pooled, our models are macro-mean.** The one gap that affects
   correctness rather than presentation. See the section above; it gates Phase 3.
2. The "three prediction tasks" line on p.21 contradicts the abstract and Table 8.
3. `place_resize` appears in Section 6.2 prose but not in Table 8.
4. Table 1's caption defines eight stage codes, but only `FP-F`, `GP-F`, `CTS-F`,
   `DR-F` and bare `F` were observed in its rows. Confirm before generating
   `attributes.json` in Phase 5.
5. Table 8 reports rounded values. Sub-precision baselines at `global_route` are
   published as `0.00` and may be small but nonzero. Only the lab's source data
   could distinguish these, and nothing in the leaderboard depends on it.
6. The upstream results tree carries no `submission.yaml`, though PLAN.md Phase 3
   expects one. The lab's own seed entry needs a provenance record authored by us.

## Licensing

This repository is MIT.
The lab's analysis code is CC BY-NC-SA 4.0, which is NonCommercial and ShareAlike,
and therefore incompatible.
Read it as a specification, write our own implementation, and take vocabularies
from the paper's published tables rather than from its source.
See `docs/sources/PROVENANCE.md`.

---

# Appendix A - Registry generation reference

**Added 2026-08-11**, when `data/registry/` was deleted in the reset.

The five registry files were verified correct against the CSV on every axis before
deletion, so their content is recorded here rather than discarded.
This appendix plus `docs/sources/table8_baseline.csv` is sufficient to regenerate
all five with no other input.

The `table8_label` column is the **join key** onto the CSV.
It is the single reason a rebuilt registry can be checked against the paper rather
than merely against itself, so it is not optional.

## `tasks.json`

`metrics[]` comes from the per-task metric sets table above.
`precision_overrides` comes from the display precision table above; every task not
listed has `{}` and inherits each metric's default.

| id | table8_label (join key) | unit | granularity | design_level | precision_overrides |
|---|---|---|---|---|---|
| `total_area_prediction` | `Total Area (u m^2)` | µm² | design | true | `{}` |
| `total_power_prediction` | `Total Power (u W)` | µW | design | true | `{}` |
| `total_wirelength_prediction` | `Total wirelength (u m)` | µm | design | true | `{}` |
| `interconnect_length_prediction` | `Interconnect length (u m)` | µm | net | false | `{}` |
| `worst_arrival_time_prediction` | `Worst Arrival Time (ns)` | ns | design | true | `{}` |
| `worst_slack_prediction` | `Worst Slack (ns)` | ns | design | true | `{}` |
| `total_negative_slack_prediction` | `Total Negative Slack (ns)` | ns | design | true | `{}` |
| `timing_path_arrival_time_prediction` | `Timing Path Arrival Time (ns)` | ns | path | false | `{mae:4, mae_p95:4, mae_top5:4}` |
| `timing_path_slack_prediction` | `Timing Path Slack (ns)` | ns | path | false | `{mae:4, mpe:4, mne:4}` |
| `net_arc_delay_prediction` | `Net Arc Delay (ns)` | ns | net_arc | false | `{mae:4}` |
| `cell_arc_delay_prediction` | `Cell Arc Delay (ns)` | ns | cell_arc | false | `{mae:4}` |
| `cell_arc_slew_prediction` | `Cell Arc Slew (ns)` | ns | cell_arc | false | `{mae:4}` |

`design_level: true` marks the six upstream `NETLIST_LEVEL_PROBLEMS`.
It selects how records are gathered before metrics are computed, so it is
load-bearing rather than descriptive.

## `metrics.json`

`percent: true` is exactly the set that is stored as a fraction and multiplied by
100 at display. See the percent storage rule above; this column is that rule in
machine-readable form.

| id | table8_label | direction | bias | percent | precision |
|---|---|---|---|---|---|
| `mae` | `MAE` | lower | null | false | 2 |
| `mape` | `MAPE` | lower | null | **true** | 2 |
| `r2` | `R^2` | **higher** | null | false | 3 |
| `mpe` | `MPE` | lower | `optimistic` | false | 2 |
| `mne` | `MNE` | lower | `conservative` | false | 2 |
| `tpr` | `TPR` | **higher** | null | **true** | 2 |
| `tnr` | `TNR` | **higher** | null | **true** | 2 |
| `mae_p95` | `MAE P95` | lower | null | false | 2 |
| `mape_p95` | `MAPE P95` | lower | null | **true** | 2 |
| `mae_top5` | `MAE TOP5` | lower | null | false | 2 |
| `mape_top5` | `MAPE TOP5` | lower | null | **true** | 2 |

## `stages.json`

The void, saturated and degenerate sets are encoded **on the stage**, because all
three rules are stage-anchored. This is what makes saturation a structural lookup
rather than a predicate over values.

| id | table8_label | order |
|---|---|---|
| `floorplan` | `floorplan to detailed route` | 1 |
| `global_place` | `global place to detailed route` | 2 |
| `detailed_place` | `detailed place to detailed route` | 3 |
| `cts` | `CTS to detailed route` | 4 |
| `global_route` | `global route to detailed route` | 5 |

`floorplan.void_tasks` = `total_wirelength_prediction`,
`interconnect_length_prediction`. Every other stage has `[]`.

`global_route.saturated_tasks` = the ten tasks that are **not**
`total_wirelength_prediction` or `interconnect_length_prediction`. Every other
stage has `[]`.

`global_route.degenerate_tasks` = `worst_slack_prediction`,
`total_negative_slack_prediction`, `timing_path_slack_prediction`, with
`degenerate_metrics` = `mpe`, `mne`. Every other stage has `[]`.

**Precedence is load-bearing: degeneracy is checked before saturation.**
Reversing the two still yields 880 live cells and 232 live combos, so the headline
counts stay green while 24 cells are silently mistyped from `DEGENERATE` to
`SATURATED`. A test asserting only the totals cannot catch it. Assert the
**40 / 24 / 120 partition**, not the 880.

`order` has the same property: a test asserting `sorted(orders) == range(1, n+1)`
passes on a fully reversed sequence. Assert the ids in order, not the set.

## `pdks.json`

`table8_label` is `upper(id)` for all four, but it is stored explicitly so path
parsing and CSV joining share one declared vocabulary rather than a convention.

| id | table8_label | long_label | metal_layers | utilization | utilization_sweep |
|---|---|---|---|---|---|
| `ng45` | `NG45` | Nangate 45 nm | 10 | 0.40 | 0.3, 0.4, 0.5 |
| `sky130` | `SKY130` | SkyWater 130 nm | 5 | 0.30 | 0.2, 0.3, 0.4 |
| `ihp130` | `IHP130` | IHP SG13G2 130 nm | 7 | 0.30 | 0.2, 0.3, 0.4 |
| `asap7` | `ASAP7` | ASAP 7 nm | 9 | 0.40 | 0.3, 0.4, 0.5 |

Results-tree directory names are uppercase (`default_config_ASAP7_cts`).
Parse case-insensitively and normalize to the lowercase id, or all 20 combos
silently fail to resolve.

## `circuits.json`

Eighteen records of `id`, `inputs`, `outputs`, `registers`, transcribed from the
Table 2 section above, which is authoritative.

> **These 54 values had zero verification before the reset.**
> Mutating `ethernet.registers` from 10,544 to 87 left the entire 115-test suite
> green. The same held for `pdks.metal_layers`, `pdks.utilization`, `stages.order`
> and `tasks.unit` - roughly 60 transcribed values that were loaded and typed but
> never checked against any source.
> The rebuilt registry must include a check that these match `docs/sources/`.
