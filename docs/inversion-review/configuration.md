# Common inversion configuration

Status: proposed contract, November 3, 2026. This design and its schema/examples do not change the current inverters. The example artifact references and ID ranges are illustrative, not verified historical inputs or production reservations.

## One vocabulary for all three sources

Use one configuration model for NCIt (`NCI`), `SNOMEDCT_US`, and `MTH`. A run uses one `inversion.json` in the same format regardless of source. Shared defaults and source profiles belong in Git; operators provide the release and reviewed decisions rather than maintain three independently named configurations. The profiles can live in one repository file if convenient. The important constraint is one schema and one meaning for each common field.

The [proposed schema](configuration.schema.json) and examples for [NCI](configuration-examples/nci.json), [SNOMEDCT_US](configuration-examples/snomedct_us.json), and [MTH](configuration-examples/mth.json) make the contract concrete. JSON keeps this consistent with the existing test request. YAML could be an authoring convenience later, provided it produces exactly the same validated model.

| Common field | Meaning for every source | Existing names or mechanisms it replaces |
|---|---|---|
| `source` | Stable source abbreviation: `NCI`, `SNOMEDCT_US`, or `MTH` | `RSAB`; source inferred from directory/script |
| `version` | Exact versioned source abbreviation, such as `MTH_2026AA` | `VSAB`; release suffixes embedded in `rel`, `newrel`, and `release` |
| `engine_ref` | Candidate code revision, resolved to an immutable commit | Copied `bin`/scripts; whichever shared installation is selected |
| `policy_ref` | Versioned representation rules, mappings, and defaults | Copied configuration; manual RELMAP/MRDOC edits; code comment toggles |
| `replacement_baseline` | Source version actually being replaced in NCImeta | SNOMED's documented previous-inserted version; MTH `old`; NCIt low-source lineage |
| `comparison_baseline` | Release whose artifacts are used for change detection/QA | Prior NCIt TDE inputs; previous-version comparison files |
| `publisher_history` | Explicit ordered native-history dependencies needed for this transition | History inferred from a prior folder or an overloaded `prevrel` |
| `inputs.native_data` | References to the original publisher packages/files | `ORIGDIR`, `File.INP.*`, external UMLS links, hardcoded native paths |
| `inputs.reference_ncimeta` | Frozen NCImeta metadata/inventory bundle used by preparation or QA | Live database/API lookups; SNOMED's separately selected MRCONSO; MTH saved exports |
| `inputs.identity_state` | Prior persistent identity maps, independently identified | MTH `old/src/cui_said_map` and related identity state |
| `inputs.source_plan` | Reviewed decisions for this particular transition | NCIt new-subsource decisions; SNOMED metadata decisions; MTH source dispositions |
| `source_atom_ids.start`, `.end` | Inclusive bounds of the entire permitted SAID range, including generated SRC atoms | `SaidStart`/`SaidEnd`; MTH range specifications plus SRCbuilder offset |
| `environment_profile` | Named worker/runtime/storage settings, resolved and recorded for the run | ENV files, hardcoded hosts, shared scratch paths |
| `validation_profile` | Versioned mandatory checks and output expectations | Differing QA scripts, copied lists, broad informal waivers |

The legacy column is a migration map, not a set of equivalent assignments. A legacy field must be traced to its actual consumers before the adapter translates it. In particular, `VSABOLD`/`EngNumOld` and MTH `prevrel` can serve more than one role. A field used only to copy or edit inherited code should disappear instead of becoming a new historical data requirement. [Evidence for the naming and offset differences](evidence.md#e16-common-configuration-and-legacy-name-mapping)

## Preserve distinct meanings

Avoid a generic `previous_version`. The following is a valid NCIt transition shape:

```json
{
  "source": "NCI",
  "version": "NCI_2026_10D",
  "replacement_baseline": {"source": "NCI", "version": "NCI_2026_08E"},
  "comparison_baseline": {"source": "NCI", "version": "NCI_2026_09D"},
  "publisher_history": []
}
```

This illustrates October replacing August while September is used only for comparison. It is not a finding about the exact preparation of an archived October result. An actual replay must use its verified historical inputs. Comparison can instead use August, and September need never be inserted or retrieved if no declared stage needs it. An empty history array means no additional publisher-history inputs are required by the reviewed plan; it must not cause the runner to infer the previous month.

Likewise, SNOMED's legacy `Release = Snapshot` describes an RF2 view. MTH's `release = 2026AA` describes a publisher release. Those values must not share one field just because the scripts use similar names. The former becomes `source_options.rf2_view`; the latter is derived from the exact `version` and checked against publisher metadata. Publisher dates and filename suffixes should be read from the native artifact manifest or derived by a tested adapter, rather than entered repeatedly under different names.

The canonical SAID bounds describe the complete allocation. For MTH, the inspected scripts pass `SourceAtomIdBase - 2` to SRCbuilder. Translation therefore sets `SourceAtomIdBase = start + 2`, `SourceAtomIdLimit = end`, and SRCbuilder's start to `start`. The common model must not copy `start` unchanged into every legacy field. NCI/SNOMED use the shared `SaidStart` generator path; the adapter and independent validator must account for every generated atom and enforce both bounds even where legacy configuration omits an end. Historical replay retains the historical complete range inside the isolated worker; a release build requires matching allocation evidence. Preliminary estimation uses a separate run and never silently changes a final range.

## Small source-specific sections

Keep only genuinely unique choices under `source_options`. The initial examples deliberately keep these sections small:

- NCI uses an empty section. Its native-file selection, subsource decisions, and representation rules are carried by the declared inputs, source plan, and policy.
- SNOMED uses `rf2_view: Snapshot`. Full input remains unsupported until a tested Full-to-Snapshot interpretation exists. Relationship mappings and inverses belong in the reviewed policy, not duplicate inline settings.
- MTH references a MetamorphoSys profile. The source-plan artifact carries `KEEP`/`UPDATE`/`NEW`/`EXCLUDE`/`REMOVE`/`SPECIAL` decisions and VSAB mapping inputs; prior identity maps remain a separate common input.

Each source-plan/profile artifact also needs a versioned, source-aware content contract. The enclosing schema only validates references and configuration shape; it does not adjudicate representation or source dispositions. Do not add a free-form shell-command field, arbitrary environment overrides, or a bypass-validation setting.

## A short request expands into the same configuration

The existing [test request](request-template.json) remains the small operator interface: source, version, engine revision, case variant, and comparison settings. A reviewed case supplies the rest. Its fields `source`, `version`, and `engine_ref` retain the same names in the common configuration; `case_variant`, `reference_stage`, and `comparison_profile` retain their names inside the optional `replay` section.

```text
shared defaults + source profile + reviewed release/case + request
    -> inversion.json       complete configuration in the common schema
    -> case.lock.json       immutable resolved configuration and dependencies
    -> generated legacy files at the agreed source-release paths on dev
    -> execution, validation, comparison, and report
```

These are stages of one contract, not independently maintained operator configurations. Profiles may supply reviewed defaults, while an explicit request selects the candidate revision. Required baselines, input identities, and ID ranges must resolve explicitly. Conflicts with the reviewed case require an intentional new case variant rather than silent merging. Record the effective configuration and where each value came from.

The resolver freezes all Git/profile/artifact references to commits, runtime identities, object identities/versions where available, file inventories, and hashes. A catalog reference in the examples is a proposed logical identifier, not a new archive service. Resolution delegates to the existing S3 tools and the worker's verified cache. The replay reference is the official result; it must not be made an undeclared candidate input. Archived preparation metadata used as candidate input is recorded and the reduced workflow coverage is stated.

Validate the actual release identity of selected reference files as well as their directory/stage label. The October NCIt archive contains October `src` output and older August-labeled `insert` state; the latter must not become October's expected result merely because it is in the same archive. An archive can legitimately contain multiple versions and workflow states. The resolver selects declared artifacts instead of treating its entire contents as one uniform input/output package.

Paths such as `ORIGDIR`, `TEMPDIR`, `SRCDIR`, and MTH's links are resolved from the environment profile and artifact manifests. The initial dev profile mirrors meme-edit's physical layout under `/local/content/MEME/MEME5`; the host name changes, while operational paths retain their production meaning. A relocation requires an explicit design decision and profile revision, rather than an automatic new replay root. Credentials are supplied by the worker's account/secret mechanism, not committed in configuration.

Configuration selects required source versions and dependency roles. It does not require matching the complete folder inventories of dev and production. Reuse verified local folders and retrieve required absent dependencies; extra folders are irrelevant to the selected run.

## Validation and migration

Reject unknown fields, unsupported schema versions, and options belonging to another source. Require an explicit null for an inapplicable baseline/input; omission must not silently mean "use latest." Before execution, additionally validate source/version compatibility, baseline roles, required history, artifact existence/hashes, range order/capacity/evidence, runtime availability, and reference-stage compatibility. JSON Schema alone cannot establish these semantic or provenance checks.

Start this work with the isolated test apparatus and canonical-code inventory, across all three sources.

That inventory starts from the verified operational deployment on meme-edit. The translation targets are the scripts/configuration actually used there, rather than the earlier project automation branches. See the [implementation starting-point decision](assessment.md#implementation-starting-point-operational-code-on-meme-edit).

A common configuration is useful before any parser rewrite:

1. Agree the vocabulary/schema and produce a translation table for every consumed legacy parameter, identifying values that are derived or obsolete.
2. Implement adapters that generate the current `.cfg`, `.spec`, native-file lists, and compatibility links from this model. Preserve generated files in run evidence. Move copied-script decisions into reviewed policy or source-plan inputs.
3. Replay unchanged engines on the development worker using these generated settings. Compare to official frozen results and investigate configuration translation differences separately from intended semantic changes.
4. Replace internals incrementally; migrated components read the same common model directly. Retire the corresponding legacy translations only after their acceptance gates pass.

No legacy parser, configuration generator, resolver, or runner has been implemented by this design. The common schema is an early deliverable under priorities 1–2 and becomes the lifecycle contract under priority 3.
