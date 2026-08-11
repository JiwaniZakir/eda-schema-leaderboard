## What and why

<!-- What changes, and what problem it solves. Link the phase if this is plan work. -->

## Gate evidence

<!--
Paste the actual output of `make check`. Not a summary of it, not "tests pass".
A claim without output is not evidence, and CI will contradict you shortly.
-->

```
$ make check

```

## Checklist

- [ ] `make check` passes, and its output is pasted above
- [ ] No file over 1 MB; large artifacts go to Releases and are referenced by URL
- [ ] Nothing under `data/` was edited by hand
- [ ] Registries remain the only source of task, metric, PDK, stage and circuit names
- [ ] No new path unpickles data or loads YAML with a tag-executing loader
- [ ] `docs/DATA_CONTRACT.md` updated if this changes what a cell means
