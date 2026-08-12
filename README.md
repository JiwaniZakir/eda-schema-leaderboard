# EDA-Schema Leaderboard

Static benchmark leaderboard for the EDA-Schema-V2 dataset ([arXiv:2605.06952](https://arxiv.org/abs/2605.06952)).

Python and Jinja2 render static HTML to GitHub Pages.
No framework, no bundler, no Node.

## Status

**Rebuilding.**
The repository was reset on 2026-08-11 after an audit of the first build.
The verified paper data, the data contract and the CI infrastructure were kept;
all application code was removed and is being rebuilt in a different order, with
the matrix page shipping before the data pipeline rather than after it.

See [`PLAN.md`](PLAN.md) for the phases, the gates, and what the audit changed.

## Quick start

```bash
make install    # uv sync
make check      # the gate: lint, typecheck, validate, test, build
```

`make check` is the gate.
It must pass before any commit, and CI enforces it.
Targets whose phase has not landed yet report `SKIPPED` and name the phase, so a
green check on an empty repo cannot be mistaken for a green check on a built one.

## The grid

Five dimensions, all defined in `data/registry/`, which is the single source of
truth.
Never hardcode a task, PDK, stage, metric or circuit name anywhere else.

12 tasks x 4 PDKs x 5 stage transitions gives 240 combinations, 232 of them live.
46 metric rows across 4 PDKs and 5 stages gives 920 cells, 880 of them live, and
856 with a published baseline.

Field definitions and the derivation of every one of those numbers are in
[`docs/DATA_CONTRACT.md`](docs/DATA_CONTRACT.md).
Appendix A of that document is sufficient to regenerate every registry file with
no other input.

## Documentation

| Document | What it covers |
|---|---|
| [`docs/DATA_CONTRACT.md`](docs/DATA_CONTRACT.md) | Vocabularies, cell states, aggregation, percent storage, known gaps, registry reference |
| [`docs/sources/PROVENANCE.md`](docs/sources/PROVENANCE.md) | Where the baseline numbers come from, and licensing |
| [`PLAN.md`](PLAN.md) | Build plan, phase gates, open decisions |
| [`CLAUDE.md`](CLAUDE.md) | Working agreements and data gotchas |

## Data provenance

`docs/sources/table8_baseline.csv` is Table 8 of the paper parsed to 920 tidy
rows.
All 920 cells were verified against the arXiv e-print LaTeX by two independent
parsers, with zero mismatches.

The verbatim paper extracts under `docs/sources/verbatim/` are deliberately not
committed; they are the authors' copyrighted text.

## Licence

MIT, see [`LICENSE`](LICENSE).

Benchmark data originates from the EDA-Schema-V2 paper and the Drexel ICE
Laboratory.
The lab's analysis code is CC BY-NC-SA 4.0 and is deliberately not vendored here;
see [`docs/sources/PROVENANCE.md`](docs/sources/PROVENANCE.md).
