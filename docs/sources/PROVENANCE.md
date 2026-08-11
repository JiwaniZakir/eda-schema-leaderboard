# Provenance

Where the baseline numbers come from, and what may be published.

## What is here

`table8_baseline.csv` is Table 8 of arXiv:2605.06952 parsed into 920 tidy rows,
one per `(task, metric, stage_transition, pdk)`.
`kind` is `VAL` for a published value or `VOID` for a cell the paper leaves
deliberately empty.
`src_line` is the line in the source LaTeX table the value came from, so any cell
can be traced back.

This file holds measurements, which are facts rather than authored expression, and
it is the only thing under `docs/` the build reads.

## What is deliberately not here

`verbatim/` is gitignored.
It holds the paper's LaTeX table source and `pdftotext` extractions, kept locally
so we can re-verify a transcription without re-downloading.
That material is the authors' copyrighted text.
Publishing it from this repo would redistribute it, which is not ours to do even
though the collaboration is friendly.
If the lab wants it published, that is their call to make explicitly.

## Do not vendor the upstream analysis code

`drexel-ice/EDA-schema` contains
`research/eda-schema-v2/baseline_analysis/compute_error_metrics.py`, the script
that produced Table 8.
It is a valuable specification and it settled several open questions in
`docs/DATA_CONTRACT.md`.

It is licensed **CC BY-NC-SA 4.0**: NonCommercial, and ShareAlike.
This repository is MIT.
Copying that file in, or vendoring its dictionaries verbatim, would pull an
incompatible NonCommercial obligation onto the whole site and force derivative
works under ShareAlike.

Read it as a reference.
Write our own implementation.
Take vocabularies from the paper's published tables, which are facts, not from the
script's source.

## Regenerating the verbatim extracts

```bash
curl -sL https://arxiv.org/e-print/2605.06952 -o eprint.tar.gz
tar xzf eprint.tar.gz -C eprint/
# Table 8 is tables/baseline.tex

pdftotext -layout 2605.06952v1.pdf -   # authoritative for dense tables
```

Table 8 sits entirely on page 28, inside a `\begin{landscape}` block and a
`\resizebox`.
The rotation and rescaling are what shred naive text extraction, which is what
produced the mistaken belief that six stage-PDK column groups were missing.

All 856 published cells were cross-checked between the LaTeX source and the PDF,
with zero mismatches, and an independent re-parse of the LaTeX confirmed all 920
cells against the CSV.

One caveat on the artifacts: `verbatim/table8_pdf_layout.txt` is **truncated**.
It ends partway through `Cell Arc Delay`, so it omits that task's R² row and all
four `Cell Arc Slew` rows, 80 cells in total.
`verbatim/table8_recovered.md` is complete and is the file to use for a manual
cross-check.
Regenerate the layout extract with the command above if the full text is needed.
