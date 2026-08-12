# Phase 6 - Contamination Guard Implementation Plan

> **For agentic workers:** Implement this plan task-by-task - either dispatch a fresh subagent per task (recommended) or execute inline with review checkpoints. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** build the five-layer contamination guard that stands between an untrusted community submission and a green cell on the leaderboard.

**Architecture:** `tools/guard/` is a package of five independent layer modules behind one dispatcher. Each layer is a pure function from a parsed submission to a list of `Finding`. Layer 1 reads a new sixth registry, `data/registry/attributes.json`, generated from Table 1 and cross-checked against `docs/sources/verbatim/table1_attributes.txt` as an independent source. Layer 4 is the only layer that executes submitter code, and it does so in a subprocess with a wall clock, no network, and a memory cap. The dispatcher registers into `tools.checks.CHECKS` so `make validate` runs the whole stack.

**Tech stack:** Python 3.11+, `uv`, `jsonschema`, `pytest`, `mypy --strict`, `ruff`. No new runtime dependency.

---

## BLOCKING DECISION - read before writing any code

**`attributes.json` cannot be generated correctly until decision 2 in PLAN.md is ruled.** This is not a footnote and it is not deferrable, because the ruling changes which of the lab's 41 features are legal at floorplan, which is the exact assertion in this phase's gate.

**The contradiction.** Table 1 lists `Netlist.total_hpwl` as available from **`FP - F`**. Table 8's footnote voids `total_wirelength` at floorplan with "Estimated wirelength is not available as cells have not been placed yet". Those cannot both be true. If `total_hpwl` exists at floorplan then a floorplan-stage HPWL estimate for `total_wirelength` exists, and the void has no cause.

Per-net `Net.hpwl` is listed `GP - F`, which **is** consistent with `interconnect_length` being void at floorplan. So the two sources disagree about exactly one of the two void tasks, not both.

**Why it blocks this phase specifically.** `Netlist.total_hpwl` is one of the lab's 41 declared features (see Task 3, where the 41 are derived and reconcile exactly). Layer 1's gate says "accepts all 41 of the lab's declared features". Under the two candidate rulings:

| Ruling | `total_hpwl` earliest stage | Layer 1 on the lab's 41 at floorplan | Consistency with the 40 void cells |
|---|---|---|---|
| **A. Table 1 is right** | `floorplan` | all 41 pass | `total_wirelength`'s floorplan void is unexplained by feature availability |
| **B. The Table 8 footnote is right** | `global_place` | **40 pass, 1 fails** | both void tasks explained by HPWL needing placed coordinates |

Under ruling B the phase gate as written in PLAN.md is false and must be restated as "accepts 40 of 41 at floorplan and all 41 from global place onward". Do not silently pick one. Do not average them. Do not encode `FP - F` because it is what the verbatim file says and then let the layer-1 fixture quietly fail.

**Recommendation: ruling A, with an explicit exception record.** Table 1 is the normative schema of the dataset and is what a submitter reads to know what they may use; Table 8's footnote is prose about one baseline estimator's behaviour, not about attribute availability. Encoding B would mean the guard rejects a feature the published schema says is available, which is the worse failure for an untrusted-input surface: it turns an honest submission into a rejection. Record the disagreement in `attributes.json` as a machine-readable `disputed` flag on that one attribute so the contradiction stays visible rather than being resolved into silence, and so Phase 3's void rendering can cite it.

**Gate on this decision:** Task 1 Step 1 is "write the ruling into `docs/DATA_CONTRACT.md` and get it approved". No other step in this phase starts first.

---

## What Table 1 actually contains

Verified against `docs/sources/verbatim/table1_attributes.txt` on 2026-08-11. Read this section rather than re-deriving it, but re-verify the counts in Task 1's cross-check rather than trusting this prose.

**Stage codes observed in the rows.** The caption defines eight codes (FP, GP, PR, DP, CTS, GR, DR, F). Only **five distinct forms actually appear**:

| Code | Occurrences | Notes |
|---|---|---|
| `FP - F` | 91 | the overwhelming majority |
| `GP - F` | 19 | all coordinate attributes, plus `Net.hpwl` |
| `DR - F` | 19 | routing, resistance, capacitance, IR drop, RUDY |
| `CTS - F` | 6 | the Clock Tree entity's non-routing attributes |
| `F` (bare) | 1 | `Netlist.cell_placement_filler`, and only that |

`PR`, `DP` and `GR` **never appear in any row**. Known gap 4 in `docs/DATA_CONTRACT.md` is confirmed accurate, with the one addition that the bare `F` appears exactly once and belongs to `Netlist.cell_placement_filler`.

**32 attributes carry no stage at all.** The contract does not mention this and the guard needs a rule for it. They are the four `Design Flow` attributes, the eight `Constraints` attributes, the two `Design Stage` attributes, and all eighteen `Standard Cell` attributes. These are static library and constraint data that do not vary by stage. Encode them as `earliest_stage: null` meaning *available at every stage*, never as unavailable, and never by silently defaulting them to `floorplan` - a `null` that means "always" and a `floorplan` that means "from floorplan" are the same thing today and diverge the moment a stage earlier than floorplan is added.

**The arithmetic reconciles.** 91 + 19 + 19 + 6 + 1 = 136 stage-bearing attributes, plus 32 stageless, is **168 attributes total** across 19 entities. Task 1 asserts 168 and the per-code counts, which is what makes a dropped row visible.

**One layout ambiguity, recorded not resolved.** The two-column PDF layout centres each entity label vertically over its rows, and `gate (Gate Instance, FP - F)` on line 49 sits on the boundary between `Timing Path` and `Cell Arc`. Both readings satisfy the centring. Semantically it belongs to `Cell Arc`, since a cell arc traverses a gate and a timing path does not have a single one. Encode it under `cell_arc` and note the ambiguity in the file. It is `FP - F` either way, so no stage decision rides on it.

---

## Global constraints

Copied from `PLAN.md`; every task's requirements implicitly include these.

- Python **3.11+**, type hints on all public functions, `ruff` and `mypy --strict` clean.
- **Registries are the only source of vocabulary.** Never hardcode a task, PDK, stage, metric or circuit name outside `data/registry/`. This phase adds `attributes.json` to that set and the same rule binds it.
- **Counts are derived, never literal.** No guard module contains 41, 46, 168, 232, 880 or any other count. `tests/` may assert them.
- **Percent metrics** (`mape`, `mape_p95`, `mape_top5`, `tpr`, `tnr`) are fractions in `[0, 1]` everywhere under `data/`.
- **Every record carries an explicit `source`.** A submission is `"source": "submission"` and the schema requires it.
- Conventional commits. Branch `phase-6/guard-layers`. Never push to `main`.
- **Never use an em dash** in prose, code comments or generated copy.

## No guard before its subject

The audit that triggered the reset found **266 lines and 40 tests guarding unpickling in a repo that had no checkpoint reader at all**. That guard could not have fired, because nothing in the repo loaded a checkpoint. Meanwhile 54 transcribed circuit attributes had no check of any kind.

This phase runs **after** Phase 4, deliberately, because Phase 4 is where `tools/ckpt.py`, `tools/ingest.py` and `tools/yamlsafe.py` create the risk. The rule for this phase:

**Do not re-introduce a guard for something that does not exist.** Before writing a layer, name the file it protects and the code path an attacker reaches. If neither exists yet, the layer belongs in a later phase.

Concretely, this phase does **not** add:

- a second unpickling guard. Phase 4 already ships the restricted reader and the `grep` assertion that `torch.load`, `yaml.full_load`, `yaml.UnsafeLoader` and `add_safe_globals` appear nowhere in `tools/`. That assertion is extended in Task 8 to cover `tools/guard/` and the sandbox, and that is the whole of the addition.
- a checkpoint-format validator. Submissions declare metrics and ship `predict.py`; they do not ship checkpoints to this repo.
- a schema-version negotiator, a rate limiter, or an author-reputation model. None have a consumer.

## Threat model

Layers 2 through 5 exist because of a specific adversary: **a submitter who wants a green cell without a working model.** Every layer below names the attack it blocks. A layer that cannot name its attack does not ship.

| Attack | Layer | Verdict |
|---|---|---|
| Train on the test circuits, report the resulting near-zero error | 2 | blocked |
| Declare a `detailed_route` feature while claiming a `floorplan`-stage prediction | 1 | blocked |
| Enter the `closed` division with a custom split that happens to be easier | 3 | blocked |
| Ship no runnable model at all and just declare numbers | 4 | blocked |
| Claim an error finer than the dataset can express | 5 | flagged |
| Always predict wildly pessimistic slack, score `mpe = 0`, lead the cell | 5 | flagged |
| Execute arbitrary code on the runner via `predict.py` | 4 | contained, not blocked |
| Exhaust the runner with an infinite loop or a fork bomb | 4 | blocked |

**Layer 4 contains rather than blocks, and that distinction is the security posture of this whole phase.** Running submitter code is the point of layer 4; there is no version of it that does not. The mitigation is that it runs on a fork-PR runner with no secrets, no write token, no network, a hard wall clock and a memory cap, and its result is advisory input to a human merge decision rather than an automatic publish.

## File structure

| File | Responsibility |
|---|---|
| `data/registry/attributes.json` | 168 Table 1 attributes: entity, namespace, name, datatype, earliest stage |
| `tools/registry.py` | extended with `attributes()`, `attribute()`, `attribute_earliest_stage()` |
| `schema/submission.schema.json` | the wire format a submission must satisfy before any layer runs |
| `tools/guard/__init__.py` | `Finding`, `Severity`, `LAYERS`, `@layer`, `run_all()` |
| `tools/guard/schema.py` | layer 0: JSON Schema validation, the parse boundary |
| `tools/guard/features.py` | layer 1: feature-stage legality against Table 1 |
| `tools/guard/splits.py` | layer 2: train/test overlap |
| `tools/guard/divisions.py` | layer 3: closed-division canonicality |
| `tools/guard/runnability.py` | layer 4: sandboxed `predict.py` execution |
| `tools/guard/plausibility.py` | layer 5: sub-precision error, and the `mpe` leader in the `mae` tail |
| `tools/checks/guard.py` | registers the stack into `CHECKS` so `make validate` runs it |
| `tests/fixtures/submissions/` | one passing and one failing fixture per layer |
| `tests/test_attributes.py` | the Table 1 cross-check against the verbatim source |
| `tests/test_guard.py` | per-layer pass and fail, plus the adversary matrix |

---

### Task 1: Rule the contradiction, then generate `attributes.json`

The registry every other task in this phase reads. It is generated from Table 1 and cross-checked against the verbatim text file, because a registry checked only against itself verifies nothing.

**Files:**
- Modify: `docs/DATA_CONTRACT.md`, `PLAN.md`
- Create: `data/registry/attributes.json`
- Modify: `tools/registry.py`
- Test: `tests/test_attributes.py`

**Interfaces:**
- Consumes: `reg._load`, `reg.stage`, `docs/sources/verbatim/table1_attributes.txt`.
- Produces: `reg.Attribute`, `reg.attributes() -> tuple[Attribute, ...]`, `reg.attribute(namespace: str, name: str) -> Attribute`, `reg.attribute_earliest_stage(namespace: str, name: str) -> str | None`.

- [ ] **Step 1: Get the ruling, in writing, before any code**

Take the BLOCKING DECISION section above to the maintainer. Record the answer in `docs/DATA_CONTRACT.md` under "Class 1: no placement, 40 cells, kind `VOID`", replacing the `OPEN (contradicts Table 1)` block with a `Ruled 2026-08-__` block that states which source wins and what `Netlist.total_hpwl.earliest_stage` therefore is. Update PLAN.md's open decision 2 to point at that ruling.

If the ruling is **B**, also correct PLAN.md's Phase 6 gate line from "layer 1 accepts all 41 of the lab's declared features" to "layer 1 accepts 40 of the lab's 41 features at floorplan and all 41 from global place onward", and adjust Task 3's fixture accordingly. Do not proceed with a gate you know to be false.

- [ ] **Step 2: Write the failing test**

Create `tests/test_attributes.py`. It parses the **verbatim text file**, not the registry, so a misreading cannot self-confirm:

```python
"""The attribute registry must agree with docs/sources/verbatim/table1_attributes.txt.

Written against the verbatim table deliberately. A test that reads the same JSON
it asserts against verifies nothing.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tools import registry as reg

TABLE1 = (
    Path(__file__).resolve().parent.parent
    / "docs" / "sources" / "verbatim" / "table1_attributes.txt"
)

STAGE_CODE = re.compile(r"\b(FP|GP|PR|DP|CTS|GR|DR)\s*-\s*F\b")


def _table1_text() -> str:
    return TABLE1.read_text(encoding="utf-8")


def test_only_five_stage_forms_appear_in_table_1() -> None:
    """The caption defines eight codes. Only five forms occur in the rows, and
    PR, DP and GR occur in none of them. A parser that assumes all eight will
    build a vocabulary with three members that never match anything."""
    found = {m.group(0).replace(" ", "") for m in STAGE_CODE.finditer(_table1_text())}
    assert found == {"FP-F", "GP-F", "CTS-F", "DR-F"}


def test_stage_code_occurrence_counts() -> None:
    """Assert the counts, not just the set. A dropped row keeps the set correct."""
    codes = [m.group(0).replace(" ", "") for m in STAGE_CODE.finditer(_table1_text())]
    counts = {c: codes.count(c) for c in set(codes)}
    assert counts == {"FP-F": 91, "GP-F": 19, "DR-F": 19, "CTS-F": 6}


def test_the_single_bare_F_attribute() -> None:
    """Exactly one attribute is available only at final layout."""
    bare = [a for a in reg.attributes() if a.earliest_stage_code == "F"]
    assert len(bare) == 1
    assert (bare[0].namespace, bare[0].name) == ("netlist", "cell_placement_filler")


def test_one_hundred_sixty_eight_attributes_load() -> None:
    assert len(reg.attributes()) == 168


def test_stage_bearing_and_stageless_partition() -> None:
    """136 carry a stage code, 32 carry none. Assert the partition, not the total."""
    staged = [a for a in reg.attributes() if a.earliest_stage_code is not None]
    stageless = [a for a in reg.attributes() if a.earliest_stage_code is None]
    assert len(staged) == 136
    assert len(stageless) == 32
    assert len(staged) + len(stageless) == 168


def test_stageless_attributes_are_the_four_static_entities() -> None:
    """Static library and constraint data. earliest_stage None means available at
    EVERY stage, never unavailable. Defaulting these to floorplan is the bug this
    pins."""
    namespaces = {a.namespace for a in reg.attributes() if a.earliest_stage_code is None}
    assert namespaces == {"design_flow", "constraints", "design_stage", "standard_cell"}


def test_earliest_stage_maps_onto_the_benchmark_stage_vocabulary() -> None:
    """Table 1's codes are not the leaderboard's stage ids. GP maps to
    global_place; DR maps to nothing in the 5-stage benchmark vocabulary because
    the benchmark predicts TO detailed route, never FROM it."""
    assert reg.attribute_earliest_stage("netlist", "no_of_cells") == "floorplan"
    assert reg.attribute_earliest_stage("net", "hpwl") == "global_place"
    assert reg.attribute_earliest_stage("net", "length") is None
    assert reg.attribute_earliest_stage("standard_cell", "drive_strength") is None


def test_net_length_is_detailed_route_only() -> None:
    """The layer-1 rejection fixture depends on this exact fact."""
    assert reg.attribute("net", "length").earliest_stage_code == "DR-F"


def test_total_hpwl_carries_the_ruling(monkeypatch: pytest.MonkeyPatch) -> None:
    """The blocking contradiction, pinned. Whichever ruling landed in Step 1, it
    is asserted here and the disagreement is recorded on the attribute itself."""
    attr = reg.attribute("netlist", "total_hpwl")
    assert attr.disputed is True
    assert attr.dispute_note != ""
    assert attr.earliest_stage_code in {"FP-F", "GP-F"}


def test_attribute_lookup_rejects_unknown_names() -> None:
    with pytest.raises(KeyError):
        reg.attribute("netlist", "not_an_attribute")
    with pytest.raises(KeyError):
        reg.attribute("not_a_namespace", "no_of_cells")
```

- [ ] **Step 3: Run it to make sure it fails**

Run: `uv run pytest tests/test_attributes.py -v`
Expected: FAIL, `AttributeError: module 'tools.registry' has no attribute 'attributes'`

- [ ] **Step 4: Generate `data/registry/attributes.json`**

168 objects, transcribed from `docs/sources/verbatim/table1_attributes.txt`. Keys: `entity` (the display label), `namespace` (the snake_case id the lab's feature groups key on), `name`, `datatype`, `unit`, `earliest_stage_code`, `disputed`, `dispute_note`. Shape:

```json
[
  {
    "entity": "Netlist", "namespace": "netlist", "name": "no_of_cells",
    "datatype": "int", "unit": null, "earliest_stage_code": "FP-F",
    "disputed": false, "dispute_note": ""
  },
  {
    "entity": "Netlist", "namespace": "netlist", "name": "total_hpwl",
    "datatype": "float", "unit": "um", "earliest_stage_code": "FP-F",
    "disputed": true,
    "dispute_note": "Table 1 says FP-F. Table 8's footnote voids total_wirelength at floorplan because cells are not placed, which implies GP-F. Ruled in favour of Table 1 on 2026-08-__; see docs/DATA_CONTRACT.md."
  },
  {
    "entity": "Netlist", "namespace": "netlist", "name": "cell_placement_filler",
    "datatype": "binary map", "unit": null, "earliest_stage_code": "F",
    "disputed": false, "dispute_note": ""
  },
  {
    "entity": "Net", "namespace": "net", "name": "length",
    "datatype": "float", "unit": "um", "earliest_stage_code": "DR-F",
    "disputed": false, "dispute_note": ""
  },
  {
    "entity": "Standard Cell", "namespace": "standard_cell", "name": "drive_strength",
    "datatype": "float", "unit": null, "earliest_stage_code": null,
    "disputed": false, "dispute_note": ""
  }
]
```

The nineteen namespaces are `design_flow`, `constraints`, `design_stage`, `netlist`, `clock_tree`, `power_delivery_network`, `port`, `standard_cell`, `gate`, `net`, `pin`, `timing_path`, `cell_arc`, `net_arc`, `cell_metrics`, `area_metrics`, `power_metrics`, `timing_metrics`, `routability_metric`.

- [ ] **Step 5: Extend the loader**

Append to `tools/registry.py`:

```python
# Table 1's stage codes are not the benchmark's stage ids. The benchmark's five
# stages are the transitions it predicts FROM, so DR-F and bare F have no
# benchmark stage: nothing predicts from detailed route or from final layout.
# None here means "available at every benchmark stage", which is why the two
# unavailable codes map to a sentinel that is checked separately rather than
# folded into None.
_STAGE_CODE_TO_ID: dict[str, str | None] = {
    "FP-F": "floorplan",
    "GP-F": "global_place",
    "CTS-F": "cts",
    "DR-F": None,
    "F": None,
}

_NEVER_AVAILABLE_CODES = frozenset({"DR-F", "F"})


@dataclass(frozen=True, slots=True)
class Attribute:
    entity: str
    namespace: str
    name: str
    datatype: str
    unit: str | None
    earliest_stage_code: str | None
    disputed: bool
    dispute_note: str


@cache
def attributes() -> tuple[Attribute, ...]:
    return tuple(Attribute(**row) for row in _load("attributes"))


@cache
def _attribute_index() -> dict[tuple[str, str], Attribute]:
    return {(a.namespace, a.name): a for a in attributes()}


def attribute(namespace: str, name: str) -> Attribute:
    try:
        return _attribute_index()[(namespace, name)]
    except KeyError:
        raise KeyError(f"unknown attribute {namespace}.{name}") from None


def attribute_earliest_stage(namespace: str, name: str) -> str | None:
    """The earliest benchmark stage at which this attribute may be used.

    None means one of two different things, and the caller must not conflate
    them, so `attribute_is_ever_available` exists alongside this:

    - a stageless attribute (static library or constraint data) is available at
      every stage
    - a DR-F or bare-F attribute is available at NO benchmark stage, because the
      benchmark predicts from floorplan through global route and never from
      detailed route or final layout
    """
    code = attribute(namespace, name).earliest_stage_code
    if code is None:
        return None
    return _STAGE_CODE_TO_ID[code]


def attribute_is_ever_available(namespace: str, name: str) -> bool:
    """False for DR-F and bare-F attributes. This is the distinction that makes
    net.length illegal at every benchmark stage rather than merely at floorplan."""
    return attribute(namespace, name).earliest_stage_code not in _NEVER_AVAILABLE_CODES
```

Add `attributes` and `_attribute_index` to the `cache_clear` lists in `tests/test_mutations.py`.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_attributes.py -v`
Expected: 11 passed

- [ ] **Step 7: Verify lint and types**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy`
Expected: all clean

- [ ] **Step 8: Commit**

```bash
git add docs/DATA_CONTRACT.md PLAN.md data/registry/attributes.json tools/registry.py tests/test_attributes.py tests/test_mutations.py
git commit -m "feat(registry): add the Table 1 attribute registry with the hpwl ruling"
```

---

### Task 2: The submission schema and the guard skeleton

Layer 0. Everything downstream assumes a parsed, well-shaped submission, and this is where that assumption is earned. It is also the first place untrusted bytes are touched, so it is written before any layer that reads them.

**Files:**
- Create: `schema/submission.schema.json`
- Create: `tools/guard/__init__.py`, `tools/guard/schema.py`
- Create: `tests/fixtures/submissions/valid_open.json`, `tests/fixtures/submissions/invalid_missing_source.json`
- Test: `tests/test_guard.py`

**Interfaces:**
- Consumes: `tools.registry`, `jsonschema`.
- Produces: `guard.Severity`, `guard.Finding`, `guard.LAYERS: dict[str, Callable[[Submission], list[Finding]]]`, `guard.layer(name)`, `guard.run_all(sub) -> list[Finding]`, `guard.schema.load_submission(path: Path) -> dict[str, Any]`, `guard.schema.check(sub) -> list[Finding]`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_guard.py`:

```python
"""The five guard layers, each with a passing and a failing fixture.

A layer with only a passing fixture is decorative: it proves the happy path runs,
not that the guard rejects anything.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools import guard

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "submissions"


def load(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def test_a_valid_submission_produces_no_findings() -> None:
    assert guard.schema.check(load("valid_open")) == []


def test_a_submission_without_a_source_is_rejected() -> None:
    findings = guard.schema.check(load("invalid_missing_source"))
    assert findings
    assert all(f.severity is guard.Severity.REJECT for f in findings)
    assert any("source" in f.message for f in findings)


def test_every_layer_is_registered() -> None:
    """Five layers plus schema. A layer that fails to import registers nothing
    and the stack then passes having run less than it claims."""
    assert set(guard.LAYERS) == {
        "schema", "features", "splits", "divisions", "runnability", "plausibility",
    }


def test_run_all_refuses_to_report_success_with_no_layers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The empty-registry bug shipped once in tools/validate.py. Same shape, same
    guard."""
    monkeypatch.setattr(guard, "LAYERS", {})
    with pytest.raises(RuntimeError, match="no guard layers"):
        guard.run_all(load("valid_open"))


def test_unknown_top_level_keys_are_rejected() -> None:
    """additionalProperties: false. A submitter who can add a key we do not read
    can stage data for a later parser change."""
    sub = load("valid_open")
    sub["extra_field"] = "anything"
    assert guard.schema.check(sub)


def test_declared_vocabulary_is_checked_against_the_registry() -> None:
    """The schema enumerates task, pdk, stage and metric ids FROM the registry.
    A hand-written enum drifts the first time a registry changes."""
    sub = load("valid_open")
    sub["task"] = "not_a_task_prediction"
    assert guard.schema.check(sub)
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_guard.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'tools.guard'`

- [ ] **Step 3: Write the two fixtures in full**

`tests/fixtures/submissions/valid_open.json`:

```json
{
  "schema_version": 1,
  "source": "submission",
  "submission_id": "acme-mlp-v1",
  "submitted_at": "2026-08-11T00:00:00Z",
  "authors": ["A. Submitter"],
  "division": "open",
  "task": "cell_arc_delay_prediction",
  "pdk": "ng45",
  "stage": "floorplan",
  "target": "cell_arc_delay",
  "features": [
    {"namespace": "netlist", "name": "no_of_cells"},
    {"namespace": "cell_metrics", "name": "no_of_total_cells"},
    {"namespace": "power_metrics", "name": "total_power"},
    {"namespace": "timing_metrics", "name": "worst_slack"}
  ],
  "split": {
    "train": ["ac97_ctrl", "aes_core", "des3_area", "ethernet", "i2c", "jpeg",
              "mem_ctrl", "pci", "sasc", "simple_spi", "spi", "ss_pcm"],
    "test": ["systemcaes", "systemcdes", "tv80", "usb_funct", "usb_phy", "wb_dma"]
  },
  "metrics": {"mae": 0.0031, "mape": 0.0742, "r2": 0.913},
  "predict_entrypoint": "predict.py",
  "model": {"family": "mlp", "params": 5313}
}
```

`tests/fixtures/submissions/invalid_missing_source.json` is the same document with `"source"` deleted and `"submission_id"` changed to `"acme-mlp-nosource"`. Write it out in full rather than generating it, so the fixture stays readable when it fails.

- [ ] **Step 4: Write the schema**

`schema/submission.schema.json`, draft 2020-12, `"additionalProperties": false` at every object level. `source` is `{"const": "submission"}`. `division` is `{"enum": ["open", "closed"]}`. `metrics` is an object whose values are numbers.

**Vocabulary enums are injected from the registry at load time, not written into the file.** `tools/guard/schema.py` reads the JSON, then fills `task.enum`, `pdk.enum`, `stage.enum`, `split.train.items.enum`, `split.test.items.enum` and `features.items.namespace.enum` from `reg.tasks()`, `reg.pdks()`, `reg.stages()`, `reg.circuits()` and `reg.attributes()`. The file on disk carries `"enum": []` as a marker and a comment field explaining it. A hand-written enum is a second copy of the vocabulary and drifts the first time a registry changes.

- [ ] **Step 5: Write the skeleton**

`tools/guard/__init__.py`:

```python
"""Contamination guard layers.

Each layer is a pure function from a parsed submission to a list of Finding.
Only tools/guard/runnability.py executes submitter code, and it does so in a
subprocess.

Layers import THIS module and register into LAYERS. Import it as a package,
never run it as __main__: running a module as __main__ creates a second copy of
it, so a layer registering into LAYERS lands in a different dict than the one
run_all reads and the stack passes having run nothing. That bug shipped once
already in tools/validate.py.
"""

from __future__ import annotations

import enum
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

Submission = dict[str, Any]


class Severity(enum.Enum):
    """REJECT blocks the merge. FLAG requires a human to look and does not block.

    The split matters: a rejection on a heuristic turns an honest submission away,
    and a flag on a hard rule lets a contaminated one through. Layers 1 to 4
    reject. Layer 5 only flags, because plausibility is a heuristic over numbers
    we did not compute.
    """

    REJECT = "reject"
    FLAG = "flag"


@dataclass(frozen=True, slots=True)
class Finding:
    layer: str
    severity: Severity
    message: str


LayerFn = Callable[[Submission], list[Finding]]
LAYERS: dict[str, LayerFn] = {}


def layer(name: str) -> Callable[[LayerFn], LayerFn]:
    def decorate(fn: LayerFn) -> LayerFn:
        LAYERS[name] = fn
        return fn

    return decorate


def run_all(sub: Submission) -> list[Finding]:
    """Run every layer. Schema first; if it rejects, stop.

    Layers after schema assume a well-shaped document. Running them on a
    malformed one turns a clear schema error into a KeyError traceback from
    inside a guard, which reads like a guard bug rather than a bad submission.
    """
    if not LAYERS:
        raise RuntimeError("no guard layers registered, refusing to report success")

    findings = list(LAYERS["schema"](sub))
    if any(f.severity is Severity.REJECT for f in findings):
        return findings

    for name, fn in LAYERS.items():
        if name != "schema":
            findings.extend(fn(sub))
    return findings


def rejected(findings: list[Finding]) -> bool:
    return any(f.severity is Severity.REJECT for f in findings)


from tools.guard import schema as schema  # noqa: E402
from tools.guard import features as features  # noqa: E402,F401
from tools.guard import splits as splits  # noqa: E402,F401
from tools.guard import divisions as divisions  # noqa: E402,F401
from tools.guard import runnability as runnability  # noqa: E402,F401
from tools.guard import plausibility as plausibility  # noqa: E402,F401
```

The trailing imports land at the bottom because each layer module imports `Finding` and `layer` from this one. Write all six module files in this step, five of them containing only a registered function that returns `[]`, so `test_every_layer_is_registered` passes now and each later task fills one in. That is the one place in this plan where a stub is correct: the registration is the real deliverable and the body arrives in its own task with its own failing test.

`tools/guard/schema.py` implements `load_submission` and `check`. `load_submission` reads with `json.loads` and nothing else. It never touches `yaml.full_load`, `yaml.UnsafeLoader` or `pickle`, and Task 8's grep asserts that.

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/test_guard.py -v`
Expected: 6 passed

- [ ] **Step 7: Commit**

```bash
git add schema/submission.schema.json tools/guard tests/fixtures/submissions tests/test_guard.py
git commit -m "feat(guard): add the submission schema and the layer registry"
```

---

### Task 3: Layer 1 - feature-stage legality

**The attack:** declare a feature that only exists after detailed routing while claiming a prediction made at floorplan. The model then sees the answer. This is the contamination the whole guard is named for, and it is the one an honest submitter can commit by accident.

**Files:**
- Modify: `tools/guard/features.py`
- Create: `tests/fixtures/submissions/lab_41_features.json`, `tests/fixtures/submissions/invalid_net_length_at_floorplan.json`
- Test: `tests/test_guard.py`

**Interfaces:**
- Consumes: `reg.attribute`, `reg.attribute_earliest_stage`, `reg.attribute_is_ever_available`, `reg.stage`, `reg.stages`.
- Produces: `features.check(sub) -> list[Finding]`, `features.resolve(group: str, name: str) -> Attribute`.

#### The lab's 41 features, derived

The lab's feature vector is described by **group**, and a group is not a Table 1 entity. Three groups map to one namespace each and one splits across two:

| Lab group | Table 1 namespace | Count |
|---|---|---|
| `netlist` | `netlist` | 9 |
| `cell_metrics` | `cell_metrics` **and** `area_metrics` | 9 + 10 = 19 |
| `power_metrics` | `power_metrics` | 7 |
| `timing_metrics` | `timing_metrics` | 6 |
| **Total** | | **41** |

**That reconciles exactly, which is the check that the split is right.** The `cell_metrics` group covers both counting attributes (`no_of_total_cells`) and area attributes (`total_area`) because the lab's extractor emits them from one pass over the cell list. Table 1 puts them under two entity labels, `Cell Metrics` and `Area Metrics`. Resolving the group to a single namespace yields 9 or 10 instead of 19 and the total lands at 31 or 32, not 41. The 41 is the arithmetic that tells you the lookup is correct.

The per-group members, all of them `FP - F` in Table 1:

- `netlist` (9): `width`, `height`, `no_of_inputs`, `no_of_outputs`, `no_of_cells`, `no_of_nets`, `no_of_pins`, `utilization`, `total_hpwl`
- `cell_metrics` -> `cell_metrics` (9): `no_of_combinational_cells`, `no_of_sequential_cells`, `no_of_buffers`, `no_of_inverters`, `no_of_fillers`, `no_of_tap_cells`, `no_of_diodes`, `no_of_macros`, `no_of_total_cells`
- `cell_metrics` -> `area_metrics` (10): `combinational_cell_area`, `sequential_cell_area`, `buffer_area`, `inverter_area`, `filler_area`, `tap_cell_area`, `diode_area`, `macro_area`, `cell_area`, `total_area`
- `power_metrics` (7): `combinational_power`, `sequential_power`, `macro_power`, `internal_power`, `switching_power`, `leakage_power`, `total_power`
- `timing_metrics` (6): `total_negative_slack`, `worst_slack`, `worst_arrival_time`, `worst_required_time`, `no_of_endpoints`, `no_of_violating_endpoints`

`timing_metrics` has eight Table 1 attributes; `critical_path_startpoint` and `critical_path_endpoint` are strings and are not in the feature vector. Do not pad the count to eight.

**`total_hpwl` is in the 41.** Under ruling B from the blocking decision it is `GP - F`, and this fixture then fails at floorplan by exactly one feature. That is the concrete consequence the ruling has, and it is why the ruling comes first.

**All 41 pass under ruling A, and that is the point.** The layer is not catching this submission. It proves the mechanism works against a submission we know to be clean, which is the only way to distinguish "the guard passed it" from "the guard did not run".

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_guard.py`:

```python
LAB_GROUP_SIZES = {"netlist": 9, "cell_metrics": 19, "power_metrics": 7, "timing_metrics": 6}


def test_the_lab_declares_forty_one_features() -> None:
    sub = load("lab_41_features")
    assert len(sub["features"]) == 41


def test_the_cell_metrics_group_spans_two_namespaces() -> None:
    """Resolving cell_metrics to one namespace yields 9 or 10, not 19, and the
    total lands at 31 or 32 instead of 41. The arithmetic is the check."""
    sub = load("lab_41_features")
    resolved = [guard.features.resolve(f["group"], f["name"]) for f in sub["features"]]
    namespaces = {a.namespace for a in resolved}
    assert {"cell_metrics", "area_metrics"} <= namespaces
    by_group: dict[str, int] = {}
    for f in sub["features"]:
        by_group[f["group"]] = by_group.get(f["group"], 0) + 1
    assert by_group == LAB_GROUP_SIZES


def test_layer_1_accepts_all_forty_one_lab_features() -> None:
    findings = guard.features.check(load("lab_41_features"))
    assert findings == [], f"expected all 41 legal at floorplan, got {findings}"


def test_layer_1_rejects_net_length_at_floorplan() -> None:
    """Net.length is DR-F. A model that sees routed wire length at floorplan has
    the answer."""
    findings = guard.features.check(load("invalid_net_length_at_floorplan"))
    assert len(findings) == 1
    assert findings[0].severity is guard.Severity.REJECT
    assert "net.length" in findings[0].message
    assert "detailed_route" in findings[0].message


def test_layer_1_rejects_a_gp_feature_at_floorplan_but_accepts_it_later() -> None:
    """The stage comparison is ordinal, not equality. A GP-F feature is illegal
    at floorplan and legal at every later stage, and a layer written with == is
    green on the rejection fixture while wrongly rejecting three legal stages."""
    sub = load("lab_41_features")
    sub["features"] = [{"group": "net", "name": "hpwl"}]
    sub["stage"] = "floorplan"
    assert guard.features.check(sub)
    for later in ("global_place", "detailed_place", "cts", "global_route"):
        sub["stage"] = later
        assert guard.features.check(sub) == [], later


def test_layer_1_rejects_an_unknown_feature_rather_than_ignoring_it() -> None:
    """An unresolvable name must reject. Skipping it is a bypass: declare
    'netlist.total_wirelength_v2' and the guard has no opinion."""
    sub = load("lab_41_features")
    sub["features"] = [{"group": "netlist", "name": "total_wirelength_v2"}]
    findings = guard.features.check(sub)
    assert findings and findings[0].severity is guard.Severity.REJECT


def test_layer_1_rejects_a_feature_from_the_wrong_group() -> None:
    """total_area is an area_metrics attribute reachable through the cell_metrics
    group. It is NOT reachable through netlist, and a resolver that searches all
    namespaces on a miss makes the group declaration meaningless."""
    sub = load("lab_41_features")
    sub["features"] = [{"group": "netlist", "name": "total_area"}]
    assert guard.features.check(sub)


def test_layer_1_rejects_a_stageless_attribute_used_as_a_target_proxy() -> None:
    """Stageless attributes are available at every stage, so they pass. Pinned so
    that a later 'None means unavailable' refactor is caught rather than silently
    rejecting all 18 standard cell features."""
    sub = load("lab_41_features")
    sub["features"] = [{"group": "standard_cell", "name": "drive_strength"}]
    sub["stage"] = "floorplan"
    assert guard.features.check(sub) == []
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_guard.py -v`
Expected: FAIL, `AttributeError: module 'tools.guard.features' has no attribute 'resolve'`, and `test_layer_1_rejects_net_length_at_floorplan` fails with `assert len([]) == 1` because the stub returns `[]`

- [ ] **Step 3: Write both fixtures in full**

`tests/fixtures/submissions/lab_41_features.json` is the `valid_open` document with `submission_id` set to `drexel-ice-mlp-seed`, `task` set to `total_area_prediction`, `stage` set to `floorplan`, and `features` replaced by the 41 objects listed above in `{"group": ..., "name": ...}` form. Write all 41 out; do not generate them in the fixture loader, because a generated fixture asserts the generator rather than the data.

`tests/fixtures/submissions/invalid_net_length_at_floorplan.json` is the same document with `submission_id` set to `contaminated-net-length` and `features` replaced by exactly one entry:

```json
"features": [
  {"group": "net", "name": "length"}
]
```

One feature, not 42, so the test can assert `len(findings) == 1` and the failure names the cause.

- [ ] **Step 4: Implement the layer**

`tools/guard/features.py`:

```python
"""Layer 1: feature-stage legality against Table 1.

A submission declares the stage it predicts from and the features it used. Every
feature must be available at or before that stage. A feature that only exists
after the predicted stage means the model saw information the prediction is
supposed to precede.

The lab's feature vector is described by GROUP, and a group is not a Table 1
entity. Three groups map to one namespace; cell_metrics spans two, because the
lab's extractor emits counts and areas from one pass while Table 1 files them
under Cell Metrics and Area Metrics. Resolving cell_metrics to a single namespace
silently drops half the group.
"""

from __future__ import annotations

from tools import registry as reg
from tools.guard import Finding, Severity, Submission, layer

# A lab feature group resolves to one or more Table 1 namespaces, searched in
# order. The order is not cosmetic: a name present in two namespaces resolves to
# the first, and the tuples below are disjoint by construction, asserted in
# tests/test_guard.py.
GROUP_NAMESPACES: dict[str, tuple[str, ...]] = {
    "netlist": ("netlist",),
    "cell_metrics": ("cell_metrics", "area_metrics"),
    "power_metrics": ("power_metrics",),
    "timing_metrics": ("timing_metrics",),
}


def resolve(group: str, name: str) -> reg.Attribute:
    """Resolve a declared (group, name) to its Table 1 attribute.

    Raises KeyError when the group is unknown or the name is not in any of that
    group's namespaces. It deliberately does NOT fall back to searching every
    namespace: if it did, the group declaration would carry no information and a
    submitter could reach any attribute through any group.
    """
    namespaces = GROUP_NAMESPACES.get(group)
    if namespaces is None:
        # A group that is not a lab group may still be a Table 1 namespace
        # directly, which is how a submission declares a feature the lab did not
        # use. It resolves to that namespace only.
        namespaces = (group,)
    for namespace in namespaces:
        try:
            return reg.attribute(namespace, name)
        except KeyError:
            continue
    raise KeyError(f"no Table 1 attribute for {group}.{name}")


def _stage_order(stage_id: str) -> int:
    return reg.stage(stage_id).order


@layer("features")
def check(sub: Submission) -> list[Finding]:
    findings: list[Finding] = []
    predicted_at = _stage_order(sub["stage"])

    for declared in sub["features"]:
        group, name = declared["group"], declared["name"]
        try:
            attr = resolve(group, name)
        except KeyError:
            findings.append(
                Finding(
                    "features",
                    Severity.REJECT,
                    f"{group}.{name} is not an attribute in Table 1. An unknown "
                    f"feature cannot be checked for stage legality and is "
                    f"rejected rather than skipped.",
                )
            )
            continue

        if not reg.attribute_is_ever_available(attr.namespace, attr.name):
            findings.append(
                Finding(
                    "features",
                    Severity.REJECT,
                    f"{attr.namespace}.{attr.name} is available only from "
                    f"detailed_route onward ({attr.earliest_stage_code}). It is "
                    f"illegal at every benchmark stage, including "
                    f"{sub['stage']}.",
                )
            )
            continue

        earliest = reg.attribute_earliest_stage(attr.namespace, attr.name)
        if earliest is None:
            # Stageless: static library or constraint data, available always.
            continue

        if _stage_order(earliest) > predicted_at:
            findings.append(
                Finding(
                    "features",
                    Severity.REJECT,
                    f"{attr.namespace}.{attr.name} is available from {earliest} "
                    f"onward ({attr.earliest_stage_code}), but this submission "
                    f"predicts from {sub['stage']}.",
                )
            )

    return findings
```

The `_stage_order` comparison is ordinal on purpose. Written as `earliest != sub["stage"]` it passes both fixtures and wrongly rejects every legal use of a `GP - F` feature at `cts`, which is the bug `test_layer_1_rejects_a_gp_feature_at_floorplan_but_accepts_it_later` pins.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_guard.py -v`
Expected: 14 passed

- [ ] **Step 6: Commit**

```bash
git add tools/guard/features.py tests/fixtures/submissions tests/test_guard.py
git commit -m "feat(guard): add layer 1 feature-stage legality against Table 1"
```

---

### Task 4: Layer 2 - split overlap

**The attack:** train on the circuits you are scored against. The error collapses toward zero and the model looks state of the art. This is the single cheapest way to top a leaderboard and it needs no sophistication at all.

**Files:**
- Modify: `tools/guard/splits.py`
- Create: `tests/fixtures/submissions/invalid_split_overlap.json`
- Test: `tests/test_guard.py`

**Interfaces:**
- Consumes: `reg.circuits`.
- Produces: `splits.check(sub) -> list[Finding]`, `splits.CANONICAL_TRAIN`, `splits.CANONICAL_TEST` read from `data/registry/splits.json`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_guard.py`:

```python
def test_layer_2_accepts_a_disjoint_split() -> None:
    assert guard.splits.check(load("valid_open")) == []


def test_layer_2_rejects_any_intersection() -> None:
    findings = guard.splits.check(load("invalid_split_overlap"))
    assert findings
    assert findings[0].severity is guard.Severity.REJECT
    assert "ac97_ctrl" in findings[0].message


def test_layer_2_rejects_a_single_shared_circuit() -> None:
    """One shared circuit out of eighteen is enough. A threshold like 'more than
    10% overlap' is a bypass with a published number attached."""
    sub = load("valid_open")
    sub["split"]["test"] = [*sub["split"]["test"], "ac97_ctrl"]
    assert guard.splits.check(sub)


def test_layer_2_rejects_an_empty_test_set() -> None:
    """Empty sets are trivially disjoint. A guard written only as
    `set(train) & set(test)` passes a submission that was never evaluated."""
    sub = load("valid_open")
    sub["split"]["test"] = []
    findings = guard.splits.check(sub)
    assert findings and any("empty" in f.message for f in findings)


def test_layer_2_rejects_an_unknown_circuit_name() -> None:
    """A name outside the registry cannot be checked for overlap. Silently
    ignoring it lets a submitter hide a real circuit behind a typo."""
    sub = load("valid_open")
    sub["split"]["train"] = [*sub["split"]["train"], "ac97_ctrl_v2"]
    assert guard.splits.check(sub)


def test_layer_2_rejects_duplicates_within_a_set() -> None:
    """Set intersection silently absorbs duplicates. They indicate a generated
    split the submitter did not inspect, which is worth surfacing."""
    sub = load("valid_open")
    sub["split"]["train"] = [*sub["split"]["train"], "ac97_ctrl"]
    assert guard.splits.check(sub)


def test_layer_2_does_not_require_the_union_to_be_all_eighteen() -> None:
    """Holding circuits out entirely is legal in the open division. Requiring
    train + test == all 18 would reject a legitimate three-way split."""
    sub = load("valid_open")
    sub["split"]["train"] = ["ac97_ctrl", "aes_core"]
    sub["split"]["test"] = ["tv80", "usb_phy"]
    assert guard.splits.check(sub) == []
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_guard.py -v`
Expected: FAIL, `test_layer_2_rejects_any_intersection` fails with `assert []` because the stub returns `[]`

- [ ] **Step 3: Write the fixture**

`tests/fixtures/submissions/invalid_split_overlap.json` is `valid_open` with `submission_id` set to `contaminated-split` and `ac97_ctrl` present in **both** lists. Write both lists out in full.

- [ ] **Step 4: Implement the layer**

`tools/guard/splits.py`:

```python
"""Layer 2: train and test must not intersect.

The cheapest possible leaderboard attack. It requires no sophistication: train on
the circuits you are scored against and the error collapses toward zero.

Four things are rejected, and only the first is the obvious one:

- a non-empty intersection
- an empty train or test set, which is trivially disjoint and was never evaluated
- a circuit name outside the registry, which cannot be checked at all
- a duplicate within a set, which set arithmetic silently absorbs
"""

from __future__ import annotations

from tools import registry as reg
from tools.guard import Finding, Severity, Submission, layer


@layer("splits")
def check(sub: Submission) -> list[Finding]:
    findings: list[Finding] = []
    train: list[str] = sub["split"]["train"]
    test: list[str] = sub["split"]["test"]
    known = {c.id for c in reg.circuits()}

    for name, members in (("train", train), ("test", test)):
        if not members:
            findings.append(
                Finding(
                    "splits",
                    Severity.REJECT,
                    f"the {name} set is empty. An empty set is trivially disjoint "
                    f"from every other set, so overlap alone cannot detect it.",
                )
            )
        unknown = sorted(set(members) - known)
        if unknown:
            findings.append(
                Finding(
                    "splits",
                    Severity.REJECT,
                    f"the {name} set names circuits that are not in the registry: "
                    f"{', '.join(unknown)}. They cannot be checked for overlap.",
                )
            )
        if len(members) != len(set(members)):
            duplicates = sorted({m for m in members if members.count(m) > 1})
            findings.append(
                Finding(
                    "splits",
                    Severity.REJECT,
                    f"the {name} set repeats {', '.join(duplicates)}.",
                )
            )

    overlap = sorted(set(train) & set(test))
    if overlap:
        findings.append(
            Finding(
                "splits",
                Severity.REJECT,
                f"train and test intersect on {', '.join(overlap)}. A model "
                f"scored on circuits it trained on has no meaning as a "
                f"generalisation result.",
            )
        )

    return findings
```

There is deliberately no rule that `train | test` covers all 18 circuits. Holding circuits out entirely is a legitimate three-way split and rejecting it would turn away honest work.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_guard.py -v`
Expected: 21 passed

- [ ] **Step 6: Commit**

```bash
git add tools/guard/splits.py tests/fixtures/submissions/invalid_split_overlap.json tests/test_guard.py
git commit -m "feat(guard): add layer 2 train and test overlap rejection"
```

---

### Task 5: Layer 3 - divisions

**The attack:** enter the `closed` division, which exists to make results comparable, while quietly using a split, a feature set or a target that makes the task easier. The number is then not comparable to anything, but it sits in the same ranking.

**Files:**
- Create: `data/registry/splits.json`
- Modify: `tools/guard/divisions.py`, `tools/registry.py`
- Create: `tests/fixtures/submissions/valid_closed.json`, `tests/fixtures/submissions/invalid_closed_custom_split.json`
- Test: `tests/test_guard.py`

**Interfaces:**
- Consumes: `reg.circuits`, `reg.task`, `tools.guard.features.resolve`.
- Produces: `reg.canonical_split() -> tuple[tuple[str, ...], tuple[str, ...]]`, `reg.canonical_features(task_id) -> tuple[tuple[str, str], ...]`, `divisions.check(sub) -> list[Finding]`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_guard.py`:

```python
def test_layer_3_ignores_the_open_division() -> None:
    """Open exists precisely so that a submitter may change the split, the
    features and the preprocessing. Layer 3 has no opinion there."""
    sub = load("valid_open")
    sub["split"]["train"] = ["ac97_ctrl"]
    sub["split"]["test"] = ["tv80"]
    assert guard.divisions.check(sub) == []


def test_layer_3_accepts_a_canonical_closed_submission() -> None:
    assert guard.divisions.check(load("valid_closed")) == []


def test_layer_3_rejects_a_closed_submission_with_a_custom_split() -> None:
    findings = guard.divisions.check(load("invalid_closed_custom_split"))
    assert findings
    assert findings[0].severity is guard.Severity.REJECT
    assert "split" in findings[0].message


def test_layer_3_rejects_a_closed_submission_with_extra_features() -> None:
    sub = load("valid_closed")
    sub["features"] = [*sub["features"], {"group": "netlist", "name": "no_of_nets"}]
    assert guard.divisions.check(sub)


def test_layer_3_rejects_a_closed_submission_with_missing_features() -> None:
    """Dropping a feature is as much a change to the closed protocol as adding
    one, and a subset check catches only the addition."""
    sub = load("valid_closed")
    sub["features"] = sub["features"][:-1]
    assert guard.divisions.check(sub)


def test_layer_3_rejects_a_closed_submission_with_a_different_target() -> None:
    sub = load("valid_closed")
    sub["target"] = "worst_slack"
    assert guard.divisions.check(sub)


def test_layer_3_is_order_insensitive_on_features_and_splits() -> None:
    """Declaration order is not part of the protocol. A list comparison would
    reject an identical submission that listed its features alphabetically."""
    sub = load("valid_closed")
    sub["features"] = list(reversed(sub["features"]))
    sub["split"]["train"] = list(reversed(sub["split"]["train"]))
    assert guard.divisions.check(sub) == []
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_guard.py -v`
Expected: FAIL, `test_layer_3_rejects_a_closed_submission_with_a_custom_split` fails with `assert []`

- [ ] **Step 3: Create `data/registry/splits.json` and the loader**

The canonical split is the 12/6 train/test partition of the 18 circuits, and the canonical feature set per task is the lab's 41. Both are registry data, not constants in a guard module.

```json
{
  "canonical": {
    "train": ["ac97_ctrl", "aes_core", "des3_area", "ethernet", "i2c", "jpeg",
              "mem_ctrl", "pci", "sasc", "simple_spi", "spi", "ss_pcm"],
    "test": ["systemcaes", "systemcdes", "tv80", "usb_funct", "usb_phy", "wb_dma"]
  }
}
```

`data/registry/features.json` carries the canonical feature set, one entry per task, each the 41 `{group, name}` pairs from Task 3.

Append these two loaders to `tools/registry.py`, reading both files through the existing `_load`:

```python
@cache
def canonical_split() -> tuple[tuple[str, ...], tuple[str, ...]]:
    """The canonical train/test circuit split a `closed` submission must use.

    Returned as (train, test). Asserted disjoint and exhaustive in
    tests/test_attributes.py: an overlapping canonical split would make every
    closed submission contaminated by construction, so it is checked where it is
    defined rather than at each use site.
    """
    rows = _load("splits")
    canonical = next(r for r in rows if r["id"] == "canonical")
    return tuple(canonical["train"]), tuple(canonical["test"])


@cache
def canonical_features(task_id: str) -> tuple[tuple[str, str], ...]:
    """The canonical `(group, name)` feature pairs for one task.

    Raises KeyError on an unknown task, deliberately. A silent empty tuple here
    would make layer 3 pass every closed submission for a task it cannot resolve.
    """
    task(task_id)  # raises KeyError if the task is not in the registry
    for row in _load("features"):
        if row["task"] == task_id:
            return tuple((f["group"], f["name"]) for f in row["features"])
    raise KeyError(f"no canonical feature set for task {task_id!r}")
```

Then extend `tests/test_attributes.py`:

```python
def test_the_canonical_split_is_disjoint_and_exhaustive() -> None:
    train, test = reg.canonical_split()
    assert not (set(train) & set(test)), "train and test overlap"
    assert set(train) | set(test) == {c.id for c in reg.circuits()}


def test_canonical_features_rejects_an_unknown_task() -> None:
    with pytest.raises(KeyError):
        reg.canonical_features("not_a_task_prediction")
```

- [ ] **Step 4: Write both fixtures**

`tests/fixtures/submissions/valid_closed.json` is the `lab_41_features` document with `division` set to `closed`, `submission_id` set to `acme-closed-v1`, and `split` set to the canonical 12/6.

`tests/fixtures/submissions/invalid_closed_custom_split.json` is the same document with `submission_id` set to `acme-closed-custom` and the canonical `ethernet` moved from `train` to `test`. Moving the largest circuit into test rather than adding a random one is deliberate: it is what a submitter would actually do, and the fixture should look like the attack rather than like a typo.

- [ ] **Step 5: Implement the layer**

`tools/guard/divisions.py`:

```python
"""Layer 3: the closed division must be closed.

Open exists so a submitter can change the split, the features, the preprocessing
and the architecture. Closed exists so that a number means the same thing across
every entry in it. A closed submission that quietly changes any of the three
pinned axes produces a number that is not comparable to the others while sitting
in the same ranking, which is worse than an open submission that changes all of
them and says so.

Three axes are pinned: the split, the feature set and the target. All three are
compared as SETS, because declaration order is not part of the protocol and a
list comparison would reject an identical submission that sorted its features.
"""

from __future__ import annotations

from tools import registry as reg
from tools.guard import Finding, Severity, Submission, layer

CLOSED = "closed"


@layer("divisions")
def check(sub: Submission) -> list[Finding]:
    if sub["division"] != CLOSED:
        return []

    findings: list[Finding] = []
    train, test = reg.canonical_split()

    if set(sub["split"]["train"]) != set(train) or set(sub["split"]["test"]) != set(test):
        findings.append(
            Finding(
                "divisions",
                Severity.REJECT,
                f"the closed division requires the canonical split. Declared "
                f"train has {len(set(sub['split']['train']))} circuits and test "
                f"has {len(set(sub['split']['test']))}; the canonical split is "
                f"{len(train)} and {len(test)}. Submit to the open division "
                f"instead if the split is intentional.",
            )
        )

    declared = {(f["group"], f["name"]) for f in sub["features"]}
    canonical = set(reg.canonical_features(sub["task"]))
    if declared != canonical:
        extra = sorted(f"{g}.{n}" for g, n in declared - canonical)
        missing = sorted(f"{g}.{n}" for g, n in canonical - declared)
        findings.append(
            Finding(
                "divisions",
                Severity.REJECT,
                f"the closed division requires the canonical feature set. "
                f"Extra: {', '.join(extra) or 'none'}. "
                f"Missing: {', '.join(missing) or 'none'}.",
            )
        )

    expected_target = reg.task(sub["task"]).id.removesuffix("_prediction")
    if sub["target"] != expected_target:
        findings.append(
            Finding(
                "divisions",
                Severity.REJECT,
                f"the closed division requires the canonical target. Task "
                f"{sub['task']} predicts {expected_target}, not {sub['target']}.",
            )
        )

    return findings
```

Both directions of the feature comparison are reported. A subset check catches an addition and misses a removal, and removing a feature changes the closed protocol exactly as much as adding one.

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/test_guard.py -v`
Expected: 28 passed

- [ ] **Step 7: Commit**

```bash
git add data/registry/splits.json data/registry/features.json tools/registry.py tools/guard/divisions.py tests/fixtures/submissions tests/test_guard.py tests/test_attributes.py
git commit -m "feat(guard): add layer 3 closed-division canonicality"
```

---

### Task 6: Layer 4 - runnability

**The attack:** ship no model at all. Declare numbers in `submission.json`, attach a `predict.py` that does nothing, and take the cell. Layers 1 to 3 all pass, because nothing in them requires the model to exist.

**This is the only layer that executes submitter code, and it is the highest-risk code in the phase.** Read the containment notes before implementing.

**Files:**
- Modify: `tools/guard/runnability.py`
- Create: `tests/fixtures/predict/valid_predict.py`, `tests/fixtures/predict/hangs_forever.py`, `tests/fixtures/predict/wrong_shape.py`
- Test: `tests/test_guard.py`

**Interfaces:**
- Consumes: `subprocess`, `resource`, `reg.circuits`.
- Produces: `runnability.SMOKE_TIMEOUT_S`, `runnability.run_predict(entry: Path, workdir: Path) -> RunResult`, `runnability.check(sub) -> list[Finding]`.

#### Containment, not prevention

Running submitter code is the point of this layer. There is no version of it that does not. What the layer owes is containment:

| Control | Mechanism | What it stops |
|---|---|---|
| Wall clock | `subprocess.run(timeout=600)`, then `kill` the **process group** | infinite loops, and children that outlive a killed parent |
| Address space | `resource.setrlimit(RLIMIT_AS)` in `preexec_fn` | memory exhaustion of the runner |
| Process count | `resource.setrlimit(RLIMIT_NPROC)` | fork bombs |
| File size | `resource.setrlimit(RLIMIT_FSIZE)` | filling the runner's disk |
| Network | run under a workflow with no egress, and treat any outbound attempt as a flag | phoning home for the test labels |
| Credentials | fork-PR runner: no secrets, `permissions: contents: read`, no write token | exfiltration and self-merge |
| Working directory | a `tmp_path` containing only the smoke slice | reading the full ground truth off the runner |

**`timeout=` alone is not containment.** `subprocess.run` with a timeout kills the direct child and leaves its children running. Start the process with `start_new_session=True` and kill the whole group with `os.killpg` on timeout, or a submission that forks once survives the guard and keeps the runner busy.

**The smoke slice must not contain the answer.** It carries features for a handful of test-split circuits and no target column. A slice that includes the target lets a `predict.py` that reads its own input file score perfectly, which is a contamination the guard would have introduced itself.

**Do not add an unpickling guard here.** Phase 4 owns that, and the grep assertion in Task 8 covers `tools/guard/` as well. This layer never loads a checkpoint; it invokes a script and reads its stdout as JSON.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_guard.py`:

```python
import os
import sys

PREDICT = Path(__file__).resolve().parent / "fixtures" / "predict"

slow = pytest.mark.slow


def test_layer_4_accepts_a_working_predict(tmp_path: Path) -> None:
    result = guard.runnability.run_predict(PREDICT / "valid_predict.py", tmp_path)
    assert result.ok
    assert result.elapsed_s < guard.runnability.SMOKE_TIMEOUT_S


def test_layer_4_rejects_a_predict_that_never_returns(tmp_path: Path) -> None:
    result = guard.runnability.run_predict(
        PREDICT / "hangs_forever.py", tmp_path, timeout_s=2
    )
    assert not result.ok
    assert result.timed_out


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process groups")
def test_layer_4_kills_the_whole_process_group(tmp_path: Path) -> None:
    """subprocess.run(timeout=) kills the direct child only. A predict.py that
    forks once survives the guard and keeps the runner busy. This is the test
    that catches a timeout implemented without start_new_session."""
    result = guard.runnability.run_predict(
        PREDICT / "forks_then_hangs.py", tmp_path, timeout_s=2
    )
    assert result.timed_out
    orphan = tmp_path / "orphan_still_running"
    assert not orphan.exists(), "a forked child outlived the process group kill"


def test_layer_4_rejects_output_of_the_wrong_shape(tmp_path: Path) -> None:
    """A predict.py that runs cleanly and emits nothing usable is not runnable in
    any sense that matters."""
    result = guard.runnability.run_predict(PREDICT / "wrong_shape.py", tmp_path)
    assert not result.ok
    assert "shape" in result.message


def test_layer_4_rejects_a_missing_entrypoint(tmp_path: Path) -> None:
    sub = load("valid_open")
    sub["predict_entrypoint"] = "does_not_exist.py"
    findings = guard.runnability.check(sub)
    assert findings and findings[0].severity is guard.Severity.REJECT


def test_the_smoke_slice_contains_no_target_column() -> None:
    """A slice carrying the answer lets a predict.py that reads its own input
    score perfectly. That would be a contamination the guard introduced itself."""
    slice_path = guard.runnability.smoke_slice_path()
    header = slice_path.read_text(encoding="utf-8").splitlines()[0].split(",")
    assert not any(c.startswith("target") for c in header)


def test_the_timeout_is_ten_minutes() -> None:
    assert guard.runnability.SMOKE_TIMEOUT_S == 600
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_guard.py -v`
Expected: FAIL, `AttributeError: module 'tools.guard.runnability' has no attribute 'run_predict'`

- [ ] **Step 3: Write the four predict fixtures in full**

`tests/fixtures/predict/valid_predict.py`:

```python
"""A minimal well-behaved predict.py: read the smoke slice, emit one number per
row on stdout as JSON."""

import csv
import json
import sys


def main() -> int:
    with open(sys.argv[1], newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    json.dump({"predictions": [0.0 for _ in rows]}, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

`tests/fixtures/predict/hangs_forever.py`:

```python
"""Never returns. The timeout fixture."""

import time

while True:
    time.sleep(1)
```

`tests/fixtures/predict/forks_then_hangs.py`:

```python
"""Forks a child that touches a file after the parent is killed, then hangs.

If the guard kills only the direct child, the fork survives, the file appears,
and test_layer_4_kills_the_whole_process_group fails. That is the point.
"""

import os
import pathlib
import sys
import time

if os.fork() == 0:
    time.sleep(6)
    pathlib.Path(sys.argv[2]).joinpath("orphan_still_running").touch()
    raise SystemExit(0)

while True:
    time.sleep(1)
```

`tests/fixtures/predict/wrong_shape.py`:

```python
"""Exits 0 and emits output that is not a prediction vector."""

import json
import sys

json.dump({"status": "done"}, sys.stdout)
```

- [ ] **Step 4: Implement the layer**

`tools/guard/runnability.py`:

```python
"""Layer 4: predict.py must run on the smoke slice inside the wall clock.

THIS IS THE ONLY LAYER THAT EXECUTES SUBMITTER CODE. It contains rather than
prevents: running the code is the point, so the controls below bound the blast
radius instead of trying to eliminate it.

- start_new_session puts the child in its own process group, and a timeout kills
  the GROUP. subprocess.run(timeout=) alone kills the direct child and leaves its
  children running, so a submission that forks once survives the guard.
- RLIMIT_AS, RLIMIT_NPROC and RLIMIT_FSIZE cap memory, forks and disk.
- The working directory holds only the smoke slice, which carries no target
  column. A slice containing the answer would let a predict.py that reads its own
  input score perfectly, which is a contamination the guard itself introduced.
- The workflow that calls this runs on a fork PR with contents: read, no secrets
  and no network egress. Nothing here can grant that; it is a workflow property
  and Task 8 asserts it.
"""

from __future__ import annotations

import json
import os
import resource
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from tools.guard import Finding, Severity, Submission, layer

SMOKE_TIMEOUT_S = 600
_ADDRESS_SPACE_BYTES = 4 * 1024 * 1024 * 1024
_MAX_PROCESSES = 64
_MAX_FILE_BYTES = 64 * 1024 * 1024

SMOKE_SLICE = Path(__file__).resolve().parent.parent.parent / "data" / "smoke" / "slice.csv"


def smoke_slice_path() -> Path:
    return SMOKE_SLICE


@dataclass(frozen=True, slots=True)
class RunResult:
    ok: bool
    timed_out: bool
    exit_code: int | None
    elapsed_s: float
    message: str


def _apply_limits() -> None:
    """Runs in the child between fork and exec."""
    resource.setrlimit(resource.RLIMIT_AS, (_ADDRESS_SPACE_BYTES, _ADDRESS_SPACE_BYTES))
    resource.setrlimit(resource.RLIMIT_NPROC, (_MAX_PROCESSES, _MAX_PROCESSES))
    resource.setrlimit(resource.RLIMIT_FSIZE, (_MAX_FILE_BYTES, _MAX_FILE_BYTES))


def run_predict(
    entry: Path, workdir: Path, timeout_s: int = SMOKE_TIMEOUT_S
) -> RunResult:
    started = time.monotonic()
    proc = subprocess.Popen(  # noqa: S603
        [sys.executable, str(entry), str(smoke_slice_path()), str(workdir)],
        cwd=workdir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
        preexec_fn=_apply_limits,  # noqa: PLW1509
        env={"PATH": os.environ.get("PATH", ""), "HOME": str(workdir)},
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        proc.communicate()
        return RunResult(
            ok=False,
            timed_out=True,
            exit_code=None,
            elapsed_s=time.monotonic() - started,
            message=f"predict.py did not finish within {timeout_s}s",
        )

    elapsed = time.monotonic() - started
    if proc.returncode != 0:
        return RunResult(
            False, False, proc.returncode, elapsed,
            f"predict.py exited {proc.returncode}: {stderr.strip()[:500]}",
        )

    try:
        payload = json.loads(stdout)
        predictions = payload["predictions"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return RunResult(
            False, False, proc.returncode, elapsed,
            "predict.py output has the wrong shape: expected JSON "
            '{"predictions": [...]} on stdout',
        )

    if not isinstance(predictions, list) or not predictions:
        return RunResult(
            False, False, proc.returncode, elapsed,
            "predict.py output has the wrong shape: predictions must be a "
            "non-empty list",
        )

    return RunResult(True, False, proc.returncode, elapsed, "")


@layer("runnability")
def check(sub: Submission) -> list[Finding]:
    entry = Path(sub["predict_entrypoint"])
    if not entry.is_file():
        return [
            Finding(
                "runnability",
                Severity.REJECT,
                f"{entry} does not exist. A submission without a runnable model "
                f"is a set of declared numbers.",
            )
        ]

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        result = run_predict(entry, Path(tmp))

    if result.ok:
        return []
    return [Finding("runnability", Severity.REJECT, result.message)]
```

`preexec_fn` is not thread safe and `ruff` will say so. The suppression is deliberate: the guard runs single threaded from a CLI entry point, and `resource.setrlimit` between fork and exec is the only way to cap a child that has not started yet.

- [ ] **Step 5: Create the smoke slice**

`data/smoke/slice.csv`, a handful of rows of the 41 features for test-split circuits, **with no target column**. It is checked in because it is small and because a guard whose input is generated at run time is a guard whose input a submitter can influence. Add a `tools/checks/smoke_slice.py` check asserting the header carries exactly the 41 canonical feature names and nothing else, registered into `CHECKS` so `make validate` catches a target column reappearing.

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/test_guard.py -v`
Expected: 35 passed. The timeout tests take about 2 seconds each; mark them `slow` if the suite budget tightens.

- [ ] **Step 7: Commit**

```bash
git add tools/guard/runnability.py tools/checks/smoke_slice.py data/smoke tests/fixtures/predict tests/test_guard.py
git commit -m "feat(guard): add layer 4 sandboxed runnability with process-group kill"
```

---

### Task 7: Layer 5 - plausibility

**Two attacks, and the second one is documented as deliberately unpatched elsewhere.**

**Attack A: claim precision the dataset cannot express.** `cell_arc_delay` ground truth is rounded to 4 decimal places, so an MAE of `0.00001` is a claim about a quantity finer than the data records. It is not a great model; it is a number that could not have been measured.

**Attack B: the pessimistic slack model.** `docs/DATA_CONTRACT.md` rules that ranking goes `mpe` ascending then `mne` ascending, and records the consequence: a model that always predicts wildly pessimistic slack never overestimates, scores `mpe = 0`, and takes first place in the `mpe` cell while being useless. **That is accepted rather than patched in ranking, on purpose**, because `mae` is a separate cell in the same grid and such a model places last there. The contract then says: "Phase 5's plausibility layer should flag a submission that leads an `mpe` cell while sitting in the tail of the corresponding `mae` cell."

**This layer is where that lands.** It is the only place the degenerate case is caught, and if this layer ships without it the contract carries a promise nothing keeps.

**Layer 5 only ever flags.** It is a heuristic over numbers we did not compute, and a rejection on a heuristic turns honest work away. A flag routes to a human; that is the correct authority for "this looks too good".

**Files:**
- Modify: `tools/guard/plausibility.py`
- Create: `tests/fixtures/submissions/invalid_subprecision_mae.json`, `tests/fixtures/submissions/invalid_pessimistic_slack.json`
- Test: `tests/test_guard.py`

**Interfaces:**
- Consumes: `reg.precision`, `reg.metric`, `reg.task`, `tools.ranking` for the current cell ordering.
- Produces: `plausibility.check(sub) -> list[Finding]`, `plausibility.expressible_floor(task_id, metric_id) -> float`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_guard.py`:

```python
def test_layer_5_accepts_a_plausible_submission() -> None:
    assert guard.plausibility.check(load("valid_open")) == []


def test_layer_5_flags_mae_below_the_expressible_floor() -> None:
    """cell_arc_delay ground truth is 4dp. An MAE of 0.00001 is a claim about a
    quantity the dataset does not record."""
    findings = guard.plausibility.check(load("invalid_subprecision_mae"))
    assert findings
    assert findings[0].severity is guard.Severity.FLAG
    assert "0.0001" in findings[0].message


def test_layer_5_does_not_flag_the_same_value_on_a_2dp_task() -> None:
    """The floor is per (task, metric), from reg.precision. A single global
    epsilon flags legitimate 4dp submissions or misses 2dp ones."""
    assert guard.plausibility.expressible_floor("cell_arc_delay_prediction", "mae") == 0.0001
    assert guard.plausibility.expressible_floor("total_area_prediction", "mae") == 0.01


def test_layer_5_does_not_flag_an_exact_zero() -> None:
    """Zero is not sub-precision, it is zero, and it is the correct answer on
    every saturated cell. Flagging it fires on 120 legitimate cells."""
    sub = load("valid_open")
    sub["metrics"]["mae"] = 0.0
    assert guard.plausibility.check(sub) == []


def test_layer_5_flags_an_mpe_leader_sitting_in_the_mae_tail() -> None:
    """The pessimistic slack model. It never overestimates, so mpe is 0 and it
    leads the cell, while mae puts it last. docs/DATA_CONTRACT.md declines to
    patch this in ranking and names this layer as where it gets caught."""
    findings = guard.plausibility.check(load("invalid_pessimistic_slack"))
    assert findings
    assert any("mpe" in f.message and "mae" in f.message for f in findings)
    assert all(f.severity is guard.Severity.FLAG for f in findings)


def test_layer_5_does_not_flag_a_model_that_leads_both_cells() -> None:
    """A genuinely good slack model leads mpe AND does well on mae. Flagging it
    would make the leaderboard punish the result it exists to find."""
    sub = load("invalid_pessimistic_slack")
    sub["metrics"]["mae"] = 0.0009
    assert guard.plausibility.check(sub) == []


def test_layer_5_never_rejects() -> None:
    """Plausibility is a heuristic over numbers we did not compute. A rejection
    on a heuristic turns honest work away; a flag routes it to a human."""
    for name in ("invalid_subprecision_mae", "invalid_pessimistic_slack"):
        for finding in guard.plausibility.check(load(name)):
            assert finding.severity is guard.Severity.FLAG


def test_layer_5_skips_saturated_and_degenerate_cells() -> None:
    """A degenerate cell has no baseline and a saturated cell is never ranked, so
    'leads the cell' is undefined for both."""
    sub = load("invalid_pessimistic_slack")
    sub["stage"] = "global_route"
    assert guard.plausibility.check(sub) == []
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_guard.py -v`
Expected: FAIL, `AttributeError: module 'tools.guard.plausibility' has no attribute 'expressible_floor'`

- [ ] **Step 3: Write both fixtures**

`tests/fixtures/submissions/invalid_subprecision_mae.json` is `valid_open` with `submission_id` set to `too-precise`, `task` set to `cell_arc_delay_prediction`, and `metrics` set to `{"mae": 0.00001, "mape": 0.0742, "r2": 0.913}`.

`tests/fixtures/submissions/invalid_pessimistic_slack.json` is `valid_open` with `submission_id` set to `always-pessimistic`, `task` set to `timing_path_slack_prediction`, `target` set to `timing_path_slack`, `stage` set to `cts`, and `metrics` set to `{"mae": 4.812, "mpe": 0.0, "mne": 4.812, "tpr": 1.0, "tnr": 0.0}`. Those numbers are the signature of the attack and are worth reading as a set: `mpe` is exactly zero because the model never overestimates, `mne` equals `mae` because every error is conservative, `tpr` is 1.0 because predicting universal violation catches every real one, and `tnr` is 0.0 because it flags every clean path too.

- [ ] **Step 4: Implement the layer**

`tools/guard/plausibility.py`:

```python
"""Layer 5: numbers that could not have been measured.

Two heuristics, both FLAG and never REJECT. A rejection on a heuristic turns
honest work away; a flag routes it to a human, which is the correct authority for
"this looks too good".

Heuristic A: an error below the dataset's own reported precision. The floor is
per (task, metric) and comes from reg.precision, not from a single global
epsilon: cell_arc_delay MAE is 4dp so its floor is 0.0001, while total_area MAE
is 2dp so its floor is 0.01. One epsilon either flags legitimate 4dp submissions
or misses sub-precision 2dp ones.

Heuristic B: the pessimistic slack model. docs/DATA_CONTRACT.md rules that
ranking is mpe ascending then mne ascending, and records that a model always
predicting wildly pessimistic slack scores mpe = 0 and leads the cell while being
useless. That is deliberately NOT patched in ranking, because mae is a separate
cell in the same grid and such a model places last there. This layer is the place
the contract names for catching it, and it is the only place it is caught.
"""

from __future__ import annotations

from tools import ranking, registry as reg
from tools.guard import Finding, Severity, Submission, layer

MAE_TAIL_QUANTILE = 0.75


def expressible_floor(task_id: str, metric_id: str) -> float:
    """The smallest error the dataset can express for this (task, metric)."""
    return 10.0 ** -reg.precision(task_id, metric_id)


def _cell_is_rankable(task_id: str, metric_id: str, stage_id: str) -> bool:
    if reg.is_degenerate(task_id, metric_id, stage_id):
        return False
    return not reg.is_saturated(task_id, metric_id, stage_id)


@layer("plausibility")
def check(sub: Submission) -> list[Finding]:
    findings: list[Finding] = []
    task_id, stage_id, pdk_id = sub["task"], sub["stage"], sub["pdk"]

    for metric_id, value in sub["metrics"].items():
        if reg.metric(metric_id).direction != "lower":
            continue
        if value == 0.0:
            # Zero is not sub-precision, it is zero, and it is the correct answer
            # on every saturated cell. Flagging it fires on 120 legitimate cells.
            continue
        floor = expressible_floor(task_id, metric_id)
        if 0.0 < value < floor:
            findings.append(
                Finding(
                    "plausibility",
                    Severity.FLAG,
                    f"{metric_id} = {value} on {task_id} is below the dataset's "
                    f"reported precision of {floor}. The ground truth is recorded "
                    f"to {reg.precision(task_id, metric_id)} decimal places, so a "
                    f"smaller error is not a measurable quantity.",
                )
            )

    if "mpe" in sub["metrics"] and "mae" in sub["metrics"]:
        if _cell_is_rankable(task_id, "mpe", stage_id) and _cell_is_rankable(
            task_id, "mae", stage_id
        ):
            mpe_rank = ranking.rank_of(task_id, "mpe", pdk_id, stage_id, sub["metrics"]["mpe"])
            mae_pctl = ranking.percentile_of(
                task_id, "mae", pdk_id, stage_id, sub["metrics"]["mae"]
            )
            if mpe_rank == 1 and mae_pctl >= MAE_TAIL_QUANTILE:
                findings.append(
                    Finding(
                        "plausibility",
                        Severity.FLAG,
                        f"this entry leads the mpe cell while sitting in the tail "
                        f"of the matching mae cell (mae percentile "
                        f"{mae_pctl:.2f}). A model that always predicts "
                        f"pessimistic slack never overestimates, so mpe is 0 and "
                        f"it wins the cell while being useless. Confirm the model "
                        f"predicts rather than floors.",
                    )
                )

    return findings
```

`ranking.rank_of` and `ranking.percentile_of` are Phase 4 functions and are the two places this layer needs to know the rest of the cell. If Phase 4 shipped `ranking` without them, add them there rather than reimplementing the ordering here: two copies of a ranking rule that must encode the `mpe` before `mne` bias is exactly the divergence the contract warns about.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_guard.py -v`
Expected: 43 passed

- [ ] **Step 6: Commit**

```bash
git add tools/guard/plausibility.py tests/fixtures/submissions tests/test_guard.py
git commit -m "feat(guard): add layer 5 plausibility including the pessimistic slack case"
```

---

### Task 8: Wire the stack in, and prove it blocks

The layers exist and pass their own tests. Nothing calls them yet, and a guard with no caller is the audit finding this whole plan is shaped around. This task gives the stack a consumer, pins the adversary matrix from the threat model as executable tests, and asserts the workflow properties that layer 4's containment depends on.

**Files:**
- Create: `tools/checks/guard.py`
- Create: `.github/workflows/validate-submission.yml`
- Modify: `tests/test_guard.py`, `CLAUDE.md`
- Test: `tests/test_guard_workflow.py`

**Interfaces:**
- Consumes: `tools.guard.run_all`, `tools.checks.register`.
- Produces: `checks.guard.check() -> list[str]`, registered as `"guard"`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_guard.py`:

```python
ADVERSARY_MATRIX = [
    ("invalid_split_overlap", "splits", guard.Severity.REJECT),
    ("invalid_net_length_at_floorplan", "features", guard.Severity.REJECT),
    ("invalid_closed_custom_split", "divisions", guard.Severity.REJECT),
    ("invalid_missing_source", "schema", guard.Severity.REJECT),
    ("invalid_subprecision_mae", "plausibility", guard.Severity.FLAG),
    ("invalid_pessimistic_slack", "plausibility", guard.Severity.FLAG),
]


@pytest.mark.parametrize(("fixture", "expected_layer", "severity"), ADVERSARY_MATRIX)
def test_every_named_attack_is_caught_by_its_layer(
    fixture: str, expected_layer: str, severity: guard.Severity
) -> None:
    """The threat model table, executable. An attack listed as blocked that no
    test exercises is a claim, not a control."""
    findings = guard.run_all(load(fixture))
    matching = [f for f in findings if f.layer == expected_layer]
    assert matching, f"{fixture} produced no {expected_layer} finding: {findings}"
    assert all(f.severity is severity for f in matching)


def test_a_clean_submission_passes_the_whole_stack() -> None:
    """Both directions. A stack that rejects everything is not a guard."""
    findings = guard.run_all(load("valid_open"))
    assert not guard.rejected(findings)


def test_schema_rejection_short_circuits_the_stack() -> None:
    """Later layers assume a well-shaped document. Running them on a malformed
    one turns a clear schema error into a KeyError from inside a guard."""
    findings = guard.run_all(load("invalid_missing_source"))
    assert {f.layer for f in findings} == {"schema"}


def test_no_unpickling_path_exists_anywhere_in_tools() -> None:
    """Phase 4 owns the checkpoint reader and this assertion. It is EXTENDED to
    tools/guard/ here rather than duplicated, because this phase adds a second
    untrusted-input surface, not a second checkpoint reader.

    Do not grow this into a checkpoint guard. 266 lines and 40 tests once guarded
    unpickling in a repo with no checkpoint reader at all."""
    import re
    from pathlib import Path

    forbidden = re.compile(
        r"\btorch\.load\b|\byaml\.full_load\b|\bUnsafeLoader\b"
        r"|\badd_safe_globals\b|\bpickle\.loads?\b|\beval\(|\bexec\("
    )
    root = Path(__file__).resolve().parent.parent / "tools"
    for py in root.rglob("*.py"):
        code = "\n".join(line.split("#", 1)[0] for line in py.read_text().splitlines())
        assert not forbidden.search(code), f"{py} contains an unsafe load path"
```

Create `tests/test_guard_workflow.py`:

```python
"""Layer 4's containment is half workflow configuration.

The sandbox caps memory and forks. It cannot grant "no secrets" or "no write
token" - those are properties of the workflow that invokes it, and a submission
runner with a write token is a self-merge away from owning the repo.
"""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW = (
    Path(__file__).resolve().parent.parent
    / ".github" / "workflows" / "validate-submission.yml"
)


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_the_submission_workflow_triggers_on_pull_request_not_target() -> None:
    """pull_request_target runs the BASE ref's workflow with a write token and
    secrets, in the context of a fork PR. It is the single most exploited
    misconfiguration in GitHub Actions and it is exactly wrong here."""
    triggers = _workflow()["on"]
    assert "pull_request" in triggers
    assert "pull_request_target" not in triggers


def test_every_job_scopes_permissions_and_none_can_write() -> None:
    for name, job in _workflow()["jobs"].items():
        assert "permissions" in job, f"job {name} inherits repository permissions"
        for scope, level in job["permissions"].items():
            assert level in {"read", "none"}, f"job {name} has {scope}: {level}"


def test_no_job_references_a_secret() -> None:
    """A fork PR runs submitter code. Any secret in its environment is
    exfiltrated by the first print statement."""
    assert "secrets." not in WORKFLOW.read_text(encoding="utf-8")


def test_the_guard_job_does_not_persist_credentials() -> None:
    for job in _workflow()["jobs"].values():
        for step in job["steps"]:
            if str(step.get("uses", "")).startswith("actions/checkout"):
                assert step.get("with", {}).get("persist-credentials") is False
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_guard.py tests/test_guard_workflow.py -v`
Expected: FAIL, `FileNotFoundError: .github/workflows/validate-submission.yml`

- [ ] **Step 3: Give the stack a consumer**

`tools/checks/guard.py`:

```python
"""Run the guard stack over every submission under submissions/.

This is the guard's consumer. A guard with no caller is only ever tested against
itself, which is the audit finding this plan is shaped around.
"""

from __future__ import annotations

import json
from pathlib import Path

from tools.checks import register
from tools.guard import Severity, run_all

SUBMISSIONS = Path(__file__).resolve().parent.parent.parent / "submissions"


@register("guard")
def check() -> list[str]:
    if not SUBMISSIONS.is_dir():
        return []

    messages: list[str] = []
    for path in sorted(SUBMISSIONS.rglob("submission.json")):
        sub = json.loads(path.read_text(encoding="utf-8"))
        for finding in run_all(sub):
            prefix = "REJECT" if finding.severity is Severity.REJECT else "FLAG"
            messages.append(f"{prefix} {path}: [{finding.layer}] {finding.message}")
    return messages
```

Add `from tools.checks import guard as _guard  # noqa: E402,F401` to `tools/checks/__init__.py` next to the existing `registry_csv` import.

**A `FLAG` appears in `make validate` output but does not fail the build**, because layer 5 never rejects. Give `tools/validate.py` a returned-message convention that distinguishes them: count only `REJECT` lines toward the failure total, and print `validate: N checks, F failures, G flags`. Without that, a flag either blocks a merge it should not or vanishes entirely.

- [ ] **Step 4: Write the workflow**

`.github/workflows/validate-submission.yml`. `on: pull_request` with a `paths: ['submissions/**']` filter. Two jobs, each with its own `permissions` block:

```yaml
name: validate-submission

on:
  pull_request:
    paths:
      - 'submissions/**'

permissions: {}

jobs:
  static:
    name: schema and layers 1-3, 5
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v4
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@v5
      - run: make install
      - run: uv run eda-validate

  runnable:
    name: layer 4, executes submitter code
    runs-on: ubuntu-latest
    needs: static
    timeout-minutes: 15
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v4
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@v5
      - run: make install
      - run: uv run pytest tests/test_guard.py -k runnability
```

`permissions: {}` at the top level and an explicit block per job. The top-level empty map means a job that forgets its block gets nothing rather than inheriting the repository default. `needs: static` means submitter code does not run until the static layers have passed, so a submission that fails layer 1 never reaches the executor.

**`pull_request`, never `pull_request_target`.** `pull_request_target` runs the base ref's workflow with a write token and full secret access in the context of a fork PR. It is the most exploited misconfiguration in GitHub Actions and it is precisely inverted for this use.

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -v`
Expected: 55 passed

- [ ] **Step 6: Document the guard in `CLAUDE.md`**

Add a short section naming the five layers, the `REJECT` versus `FLAG` split, and the one-line rule that layer 4 executes submitter code and must never run under `pull_request_target`. Keep it to a paragraph; the detail lives in this plan and in `tools/guard/`.

- [ ] **Step 7: Run the gate**

Run: `make check`
Expected: lint clean, mypy clean, `validate: 3 checks, 0 failures, 0 flags`, all tests pass, build clean.

- [ ] **Step 8: Commit and open the PR**

```bash
git add tools/checks/guard.py tools/checks/__init__.py tools/validate.py .github/workflows/validate-submission.yml tests/test_guard.py tests/test_guard_workflow.py CLAUDE.md
git commit -m "feat(guard): wire the guard stack into validate and the fork-PR workflow"
git push -u origin phase-6/guard-layers
gh pr create --title "Phase 6: guard layers" --body "Five contamination guard layers plus data/registry/attributes.json generated from Table 1 and cross-checked against the verbatim source. Each layer has a passing and a failing fixture. The threat model table is executable as a parametrised adversary matrix. Includes the ruling on the total_hpwl contradiction between Table 1 and Table 8's footnote."
```

---

## Phase gate

Every item must pass before Phase 7 starts.

```bash
make check
uv run pytest tests/test_guard.py tests/test_guard_workflow.py tests/test_attributes.py -v
```

**The blocking decision**

- [ ] the `Netlist.total_hpwl` contradiction is **ruled in writing** in `docs/DATA_CONTRACT.md`, and PLAN.md open decision 2 points at the ruling
- [ ] `attributes.json` carries `disputed: true` and a `dispute_note` on that attribute, so the disagreement stays visible
- [ ] if ruling B was taken, PLAN.md's Phase 6 gate line about "all 41" is corrected before the fixture is written

**The attribute registry**

- [ ] 168 attributes load; the partition asserts 136 stage-bearing and 32 stageless
- [ ] the per-code counts assert 91 `FP-F`, 19 `GP-F`, 19 `DR-F`, 6 `CTS-F`, 1 bare `F`
- [ ] `PR`, `DP` and `GR` are asserted **absent** from Table 1's rows
- [ ] stageless attributes are the four static entities, and `None` means available at every stage rather than at none
- [ ] `net.length` resolves to `DR-F` and is illegal at every benchmark stage

**The layers**

- [ ] every layer has a passing fixture **and** a failing fixture, both written out in full
- [ ] layer 1 accepts all 41 of the lab's declared features, and the 9 + 19 + 7 + 6 group arithmetic reconciles to 41
- [ ] layer 1 rejects a submission declaring `net.length` at floorplan
- [ ] layer 1's stage comparison is ordinal: a `GP-F` feature is rejected at floorplan and accepted at all four later stages
- [ ] layer 2 rejects a single shared circuit, an empty test set, an unknown name and a duplicate
- [ ] layer 3 rejects a closed submission with a custom split, extra features, missing features or a changed target, and is order insensitive
- [ ] layer 4 kills the **process group**, not just the child, and the fork fixture leaves no orphan
- [ ] layer 4's smoke slice carries no target column
- [ ] layer 5 flags `MAE 0.00001` on `cell_arc_delay` against a 4dp floor, and does not flag exact zero
- [ ] layer 5 flags the `mpe` leader sitting in the `mae` tail, and does not flag a model that leads both
- [ ] layer 5 never returns `REJECT`

**Wiring, and the audit findings this phase is shaped by**

- [ ] the guard has a real consumer: `tools/checks/guard.py` is registered and `make validate` runs it
- [ ] the adversary matrix is parametrised over every attack the threat model claims is blocked
- [ ] `validate` distinguishes flags from failures, and a flag does not block a merge
- [ ] the workflow triggers on `pull_request`, never `pull_request_target`
- [ ] every job scopes `permissions` explicitly; none can write; no job references a secret
- [ ] no new unpickling guard was added; the Phase 4 grep assertion was **extended** to cover `tools/guard/`
- [ ] no count literal appears anywhere in `tools/`

## Review prompt

```
Use a security reviewer on tools/guard/, schema/submission.schema.json,
data/registry/attributes.json and .github/workflows/validate-submission.yml
against docs/plans/2026-08-11-phase-6-guard.md.

Assume an adversarial submitter who wants a green cell without a working model.
Name every way through the guard you can find, and for each say whether it is
blocked, flagged or undetected. Work through at least these, and then find the
ones this list does not contain:

- declare a legal feature, use an illegal one at run time inside predict.py
- pass a closed-division check with the canonical split declared and a different
  one used
- return cached predictions from a file shipped alongside predict.py
- escape the layer 4 subprocess: process group, resource limits, network, the
  working directory, the environment
- reach a write token or a secret from a fork PR
- exploit the ordering of layers, or a layer that returns early
- submit a value that is legal on every axis but impossible in combination

Separately, verify two things against the sources rather than against the code:
that data/registry/attributes.json matches
docs/sources/verbatim/table1_attributes.txt on every row, and that the ruling on
Netlist.total_hpwl is recorded in docs/DATA_CONTRACT.md and is what the registry
actually encodes.

Report only exploitable gaps and source mismatches. Do not report style
preferences.
```
