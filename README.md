# EDA-Schema Leaderboard

Static benchmark leaderboard for the EDA-Schema-V2 dataset ([arXiv:2605.06952](https://arxiv.org/abs/2605.06952)).

Python and Jinja2 render static HTML to GitHub Pages.
No framework, no bundler, no Node.

## Quick start

```bash
make install    # uv sync
make check      # lint, typecheck, validate, test, build
make serve      # dist/ on :8000
```

`make check` is the gate.
It must pass before any commit, and CI enforces it.

## The grid

Five dimensions, all defined in `data/registry/`, which is the single source of
truth.
Never hardcode a task, PDK, stage, metric or circuit name anywhere else.

12 tasks x 4 PDKs x 5 stage transitions gives 240 combinations, 232 of them live.
46 metric rows across 4 PDKs and 5 stages gives 920 cells, 880 of them live, and
856 with a published baseline.

Field definitions and the derivation of every one of those numbers are in
[`docs/DATA_CONTRACT.md`](docs/DATA_CONTRACT.md).

## Documentation

| Document | What it covers |
|---|---|
| [`docs/DATA_CONTRACT.md`](docs/DATA_CONTRACT.md) | Vocabularies, cell states, aggregation, known gaps |
| [`docs/sources/PROVENANCE.md`](docs/sources/PROVENANCE.md) | Where the baseline numbers come from, and licensing |
| [`PLAN.md`](PLAN.md) | Build plan and phase gates |
| [`CLAUDE.md`](CLAUDE.md) | Working agreements and data gotchas |

## Licence

MIT, see [`LICENSE`](LICENSE).

Benchmark data originates from the EDA-Schema-V2 paper and the Drexel ICE
Laboratory.
The lab's analysis code is CC BY-NC-SA 4.0 and is deliberately not vendored here;
see `docs/sources/PROVENANCE.md`.
