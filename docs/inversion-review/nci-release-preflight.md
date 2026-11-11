# NCIt release-state preflight

The November 10 offline preflight compares generated NCIt source-plan metadata with an explicitly supplied inventory under a synthetic versioned-termgroup model. It distinguishes those declared identities from representation catalog membership. The later [primary backend discovery](nci-backend-state-discovery.md) establishes that real ranking state is held in separate default/project RSAB/TTY precedence lists, and SAIDs require explicitly selected alternate identifiers. This v1 artifact does not prove those deployed semantics or bind its root IDs to raw atom evidence. Its `PASS_RELEASE_PREFLIGHT` result is a bounded preview status, never operational readiness. It does not query a database, stage files, run a converter, reserve IDs, authorize insertion, or alter historical replay locks. Full dev inversions remain serialized through the existing global runtime lock.

The implementation is [nci_release_preflight.py](../../tools/nci_release_preflight.py). Its API is:

```python
analyze(configuration, source_plan, metadata_model, properties,
        installed_state, expected_state_sha256)
```

`configuration` uses the existing common vocabulary; `source_plan`, `metadata_model` and base compatibility `properties` are the same inputs used by the source-plan generator. The preflight calls that generator itself, preserving its strict metadata/addition validation. No inputs are mutated. Result bindings retain the canonical content hashes of all inputs and the generated metadata hashes.

The `installed_state` argument is additional, explicitly supplied preview evidence. The existing historical profile's `inputs.reference_ncimeta` still selects its reviewed representation model. This preflight does not silently replace that model with inventory or assert that the historical database has been reconstructed. A future composite `reference_ncimeta` artifact could bind both representation metadata and installed-state capture; that integration is proposed, not implemented here.

## Inventory contract

The snapshot uses this shape; the short example is illustrative and is not sufficient for the full October catalog:

```json
{
  "schema_version": 1,
  "profile": "ncimeta-installed-state-v1",
  "scope": {
    "source": "NCI",
    "replacement_baseline": {"source": "NCI", "version": "NCI_2026_08E"}
  },
  "capture": {
    "snapshot_id": "reviewed-capture-identifier",
    "captured_at": "2026-11-10T18:00:00Z",
    "evidence_sha256": "0000000000000000000000000000000000000000000000000000000000000000"
  },
  "complete_for": {"sources": true, "source_roots": true, "termgroups": true},
  "sources": [
    {"source": "NCI", "version": "NCI_2026_08E", "source_family": "NCI"}
  ],
  "replacement_sources": ["NCI_2026_08E"],
  "source_roots": [{"source": "NCI", "root_atom_id": 123456}],
  "termgroups": ["NCI_2026_08E/PT", "NCI_2026_08E/SY"]
}
```

`sources` and `termgroups` describe installed metadata identities available for ranking. Multiple versioned source identities may share one source abbreviation. `replacement_sources` explicitly identifies the NCI-family sources belonging to the selected installed replacement transition, at most one version per source. It must include the selected primary NCI baseline. Extra retained historical metadata is not automatically treated as an active source removal.

NCI-family versions use the reviewed monthly NCI identity convention. External ranking anchors retain their explicitly captured source/version identity; an external version is not required to start with its source abbreviation. Distinct source roots cannot share one atom ID.

`source_roots` identifies installed SRC source roots by source abbreviation. These are separate from the saved hierarchy root supplied to the NCIt converter. A metadata row alone does not prove a source root exists. The snapshot must declare complete coverage of the selected source/replacement scope and every external ranking anchor relevant to the proposed plan. A missing ranking target therefore becomes a finding rather than an inferred reference.

`expected_state_sha256` is SHA-256 of canonical JSON: sorted keys, compact separators, ASCII escapes, no non-finite numeric values. `content_sha256` implements it. Changed content, a wrong source/replacement scope, a missing selected baseline, incomplete inventories, duplicate identities and malformed values are rejected. Capture time is retained for provenance. Wall-clock age alone does not make a frozen historical snapshot stale.

Capture provenance must be reviewed and its raw evidence retained. Content hashes prove the selected bytes have not changed; they do not prove that declared inventories are truthful or complete database exports. No real installed-state snapshot was acquired during this offline development task.

## Findings and boundaries

Blocking findings cover an already-installed proposed version, new source/termgroup decisions that duplicate installed identities, missing established source roots, undeclared new sources/termgroups, absent ranking targets, and sources/termgroups omitted from the selected replacement transition. Source removal behavior remains a reviewed future policy, rather than an automatic deletion.

The result is `BLOCKED` when findings exist, otherwise `PASS_RELEASE_PREFLIGHT`. Both results have `production_eligible: false` and `execution_authorized: false`. Publisher discovery against all five native files, production ID allocation, legacy database QA, source-plan review and insertion remain separate gates. In particular, removing a historical exception from a plan does not establish that the corresponding publisher representation has been corrected; native discovery must still validate it.

The [captured October preparation](nci-source-plan-preparation.json) and [source-plan evidence](nci-source-plan.md) establish two unresolved findings:

- `CTCAE 6.0` occurs in 4,111 native term records. The captured configuration and canonical template map CTCAE, CTCAE_3 and CTCAE_5, while the native normalizations cover only versions 3.0 and 5.0. The evidence does not establish whether the intended representation is a distinct CTCAE_6 subsource, an existing subsource, or another reviewed treatment. No mapping or metadata was invented here.
- The captured BLOODPAC/SY ranking points to `CELLOSAURUS_2026_10D/SY`. The generated October catalog defines CELLOSAURUS/PT but no CELLOSAURUS/SY. No captured installed-state export establishes whether the SY target existed in NCImeta. A snapshot can establish target existence; choosing a different ranking still needs domain review.

Every retained historical exception remains an explicit blocking finding. Its compatibility waiver cannot authorize operational preparation. The existing historical reference and producer bytes are unchanged.

## Verification

Run `python3 -B tools/check_nci_release_preflight.py`. Its inventories are explicitly synthetic. The checks exercise coherent preparation, October replacing August, installed/new conflicts, missing roots and termgroups, ranking targets, retained historical versions, removals, unchanged input objects, deterministic saved-JSON execution, incomplete/mismatched state, and both historical findings. `fixture(historical=False)` returns the six analyzer arguments for isolated integration tests; `fixture(historical=True)` preserves the original October findings. The synthetic passing fixture uses an explicitly different SY ranking solely to test the preflight and is not a proposed semantic correction.
