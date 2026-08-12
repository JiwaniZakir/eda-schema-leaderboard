# Phase plans

Task-level implementation plans, one per phase.
`PLAN.md` at the repo root is the roadmap and holds scope, gates and open
decisions; these hold the steps.

Where the two disagree, the roadmap is authoritative on **scope** and the phase
plan is authoritative on **implementation detail**.

## How to use one

Each plan is written for an engineer who knows Python well and knows nothing
about this project or about EDA.
Every task is self-contained: exact file paths, the interfaces it consumes and
produces, a failing test before an implementation, and a commit at the end.

Two ways to run one:

1. **Subagent-driven, recommended.** Dispatch a fresh subagent per task and
   review each task's diff before starting the next. Context from task N is
   noise in task N+1.
2. **Inline.** Work the tasks in order in one session, pausing at the commit
   steps for review.

Either way the phase is not done until its `## Phase gate` checklist passes,
`make check` exits 0 with its output shown, and the `## Review prompt` has been
run against the diff.

## The plans

| Phase | Plan | Ships |
|---|---|---|
| 1 | [registries](2026-08-11-phase-1-registries.md) | the five registry files and the typed loader |
| 2 | [baseline](2026-08-11-phase-2-baseline.md) | `data/baseline.json` from the paper CSV |
| 3 | [matrix](2026-08-11-phase-3-matrix.md) | **a real page on GitHub Pages** |
| 4 | [ingest and ranking](2026-08-11-phase-4-ingest-ranking.md) | the 20 real combos, and ranking with a consumer |
| 5 | [cell pages](2026-08-11-phase-5-cell-pages.md) | 232 pre-rendered pages |
| 6 | [guard](2026-08-11-phase-6-guard.md) | the five contamination layers |
| 7 | [synthetic decision](2026-08-11-phase-7-synthetic-decision.md) | a decision, and possibly no code |
| 8 | [explore, card, submit, model](2026-08-11-phase-8-explore-card-submit-model.md) | the remaining pages |
| 9 | [themes, deploy, transfer](2026-08-11-phase-9-themes-deploy-transfer.md) | two themes, the citation and its DOI, and the handover |

## Rules that apply to every phase

These came out of the audit that caused the 2026-08-11 reset.
They are why the plans are shaped the way they are.

- **Ship the consumer with the abstraction.** A module with no caller in its own
  phase is in the wrong phase. The pre-reset build had a 217-line ranking module
  with zero non-test consumers, so it was only ever tested against itself.
- **No guard before its subject.** 266 lines and 40 tests guarded unpickling in a
  repo that had no checkpoint reader, while 54 transcribed circuit attributes had
  no check at all.
- **Test against an independent source.** A test that reads the same JSON it
  asserts against verifies nothing. `docs/sources/` is the independent source.
- **Assert partitions, not totals.** 880 stays correct while degeneracy and
  saturation are swapped. 40 / 24 / 120 does not.
- **Percent metrics are fractions in storage.** The CSV is in display units and is
  divided by 100 on read; `eval.log` is already a fraction and is not converted.
  Getting this backwards is silent and looks like a plausible finding.
- **Never use an em dash.**
