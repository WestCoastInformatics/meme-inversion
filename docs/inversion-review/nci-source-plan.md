# NCIt source plans and generated metadata

Completed November 10, 2026: [the fresh full October replay](nci-source-plan-summary.json) passes historical compatibility. All five core files are byte-exact to the previous accepted candidate, all three TREF files match the archive, and both generated metadata files match their independent archive hashes. [Independent retained-file verification](nci-source-plan-final-verification.json) also confirms the complete 47-entry previous tree and all 169 restored original runtime hashes. Production is unchanged; the two historical findings below remain unresolved.

The source-plan profile generates `sources.src`, `termgroups.src`, the compatibility configuration, and explicit SRC-root/termgroup input files from the common configuration, a pinned metadata catalog and a reviewed release plan. All executable code comes from Git. No previous release executable or completed core output is copied into a candidate.

The common field is still `inputs.source_plan`. Its artifact contains the [typed NCIt source plan](nci-source-plan.schema.json); [October's example](configuration-examples/nci-source-plan-october-2026.json) records its explicit August replacement, one new subsource and two new termgroups. The metadata catalog is selected through `inputs.reference_ncimeta`, with its exact Git model identity bound in the lock. It is a structured, reviewed representation of captured preparation metadata, not a reconstructed historical database or live installed-root inventory.

## Release decisions

Every plan explicitly provides `new_subsources`, `new_termgroups`, `property_updates` and `historical_exceptions`, including empty arrays/objects when applicable. An established subsource stays in generated versioned metadata without emitting its root again. Catalog membership describes known representation; the reviewer determines which roots/termgroups are new to the selected NCImeta transition. A newly accepted definition should be retained in the versioned catalog for subsequent releases; this is a reviewed data/policy change, not an executable copy-forward step.

Use the catalog-promotion preview to retain the entire definition, including source aliases, RSSN settings, term-type mappings and explicit token bindings. Carrying only the source/termgroup rows would lose the bindings needed by a long source name or new term type in the following release.

A new subsource specifies complete named metadata fields, publisher aliases, its insertion position and root preferred/short names. A new termgroup specifies the six actual loader fields, insertion position and native term types. Only reviewed new term-type mappings may extend the existing compatibility policy; conflicting existing mappings are rejected. Planned token bindings handle long source names and term types without adding regular-expression branches to Perl.

Because the legacy TREF format concatenates publisher source and term type, a new binding must not collide with another new binding or any existing native source/type pair. Required official/root names cannot be empty or whitespace.

`low_source` and `low_termgroup` are explicit ranking decisions. They can refer to another member of the current batch. Established-source defaults use the explicitly selected replacement release; no previous calendar month is inferred. Validation rejects duplicate identities/decisions, missing metadata, bad flags, inconsistent source/TTY identities, missing anchors, unknown/cyclic ranking targets, a new definition referring to its nonexistent prior identity, and an ID range too small even for required SRC atoms. Common historical bounds are not production ID reservations.

The producer reads the generated ordered root list. Each new subsource emits the same RPT, RAB, SSN, relationship, two merges and semantic-type attribute as the characterized October producer, at the same point in allocation. Empty lists emit none. New subsource/termgroup decisions require no script edits or comment toggles.

## Preview through the common interface

Use [the source-plan request](request-examples/nci-source-plan.json), keeping the same seven request fields as every other source. In the isolated runner environment:

```sh
python3 -B tools/inversion_request.py resolve docs/inversion-review/request-examples/nci-source-plan.json --run-id nci-source-plan-preview --output source-plan.lock.json
python3 -B tools/nci_configuration.py source-plan.lock.json --output-dir source-plan-preview
python3 -B tools/nci_configuration.py source-plan.lock.json --metadata-policy-preview next-metadata-policy.json
```

The preview creates the five read-only files and their binding receipt in a fresh directory. It does not stage server data or execute an inversion. Submission, status and collection use the existing [common lifecycle](common-interface.md#dev-lifecycle).

The separate metadata-policy preview produces a new read-only catalog candidate for review and a Git policy change. Established-source/termgroup rankings refer to the selected next transition's replacement version. It preserves all mappings needed when the next plan's addition arrays are empty, and does not carry historical exceptions into the next release. It neither updates a repository/server file in place nor asserts that an insertion occurred. Root-state decisions must still follow the actual reviewed NCImeta transition.

An interactive assistant or future skill can explain discovery findings and draft a plan for review. The same deterministic resolver, generator and validation gates apply to interactive and unattended execution; the assistant does not supply undeclared mappings or declare a release production-ready.

## Discovery and immutable preparation

Before publishing a candidate or invoking Perl preparation, scan all five pinned native exports. Reject changed input identities, unknown source/term-type pairs, missing source metadata/mappings, new properties/relationship roles, changed representation labels, malformed termgroup qualifiers and unknown Maps_To meanings. New declarations require a reviewed plan/catalog update; discovery does not invent policy.

The source-plan candidate is seeded with only the five publisher files. Metadata is rendered from the locked model/plan, rather than extracted from archived `src` metadata. In the October compatibility case, the archived metadata hashes are independent expected results checked after generation. Generated files are read-only, rehashed before/after execution and retained with binding/discovery receipts. The original `generated-configuration` case stays pinned to its original engine and remains executable.

## Two historical findings kept explicit

The October scan found `CTCAE 6.0` in 4,111 native term records with no corresponding captured `vsab` mapping. Its existing output behavior is preserved for this compatibility exercise; no corrected mapping or complete representation is claimed.

The preserved October BLOODPAC/SY low-termgroup value is `CELLOSAURUS_2026_10D/SY`, which is absent from that metadata bundle. Existence in the insertion database has not been established. This value is preserved as an expected historical input choice, not silently declared a verified database reference.

Both findings are explicit exceptions bound to the exact version and all five native file hashes. Changed versions or input bundles cannot inherit them. They remain in the preparation/result receipts and do not confer production eligibility. Future release preparation requires reviewed representation and validated ranking targets. No semantic correction to either finding is part of this migration.

## Verification

Run `python3 -B tools/check_nci_source_plan.py` for independent golden metadata hashes, every effective legacy property, actual old/new Perl output equivalence, no-additions behavior, an established subsource without repeated roots, a long new subsource, a new term type and negative discovery/plan cases. Use the isolated runner environment for `tools/check_inversion_request.py`. Historical core replay uses the same common resolver, preservation, runtime lock, dev worker and official per-output references described in [the common interface](common-interface.md).

[The local checks](nci-source-plan-fixtures-20261110.json) pass 205 cases: common interface 89, source-plan/lifecycle 52, original generator 37 and common worker 27. Following-release fixtures execute the actual Perl producer after catalog promotion, with empty addition arrays, for both a long source name and a newly introduced term type. CLI resolution, saved-lock loading, all five read-only preview files and the promotion draft are exercised too.

The native job used source package `b6c60b4` and apparatus `0df06fa`. Subsequent invalid-input guards and the separate catalog-promotion command are tested at `98920a3`; [the complete generated-recipe comparison](nci-source-plan-post-replay-equivalence.json) proves all executed producer/policy blobs and generated inputs remain unchanged. The actual execution receipt retains `0df06fa`; no newer native run is claimed. [Raw result](nci-source-plan-replay-result.json), [preparation](nci-source-plan-preparation.json), [controller and verifier identities](nci-source-plan-controller.json).

An initial setup stopped at recipe verification because of a tuple/JSON-array mismatch, before source preservation, runtime activation or a native worker. The fix adds saved-JSON round trips to every common case. A direct transport then encountered an unsupported sudo form; the working login route was retained. Both setup events remain in the fixture record. The accepted v2 native run is a separate identity, and its detached controller restored the original runtime automatically.

General new-release case registration, publisher acquisition, a fresh NCImeta metadata snapshot/installed-root inventory, source removals, production allocation, legacy database QA, insertion and production eligibility remain separately scoped. The versioned catalog and release-plan machinery do not infer those decisions from a prior folder or today's database.
