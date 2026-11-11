# NCIt backend state contract and preflight v2

This is an offline contract and semantic review tool based on the [pinned backend-code discovery](nci-backend-state-discovery.md). **No real exporter/deployment acceptance profile exists. Every v2 result remains blocked pending capture verification**, including a structurally complete synthetic fixture. The tool performs no API/database request, installation, native inversion, source staging or historical-case update.

The [state schema](nci-installed-state-v2.schema.json) names the artifact `ncimeta-installed-state-v2`. [nci_backend_preflight.py](../../tools/nci_backend_preflight.py) provides:

```python
analyze_backend(configuration, source_plan, metadata_model, properties,
                installed_state, expected_state_sha256, raw_exports)
```

The first four inputs are the existing NCIt source-plan generator inputs. `raw_exports` explicitly maps each declared relative export path to its original bytes. The state identity uses the existing canonical sorted-JSON SHA-256 convention; each raw export uses SHA-256 of its actual bytes and a byte count. Missing, extra or changed bytes, duplicate JSON keys, malformed state and inconsistent declared row values fail closed. Inputs are not mutated. Reports bind state/configuration/plan/model/property identities, raw files and row locations, generated metadata hashes, schema and current preview-code hashes.

## Compatibility boundary

The [v1 analyzer](nci-release-preflight.md), its profile, common preview CLI, historical locks/cases and native modules are unchanged. V1 remains an explicit synthetic/versioned-termgroup preview. There is no implicit v1-to-v2 conversion and no conversion from v2 precedence pairs to fictitious installed VSAB/TTY rows. Existing fixtures and historical recipes retain their original meaning.

V2 is a separate, standalone preview. Its `inputs_from_lock` helper consumes an existing, unchanged NCIt source-plan common lock and revalidates that profile's generated recipe. The v2 state is additional explicit review evidence; it does not silently replace `inputs.reference_ncimeta`, the representation catalog or saved hierarchy-root input. Registering an operational capture profile or integrating this contract into the common worker remains separately reviewed work.

Common NCIt version names still establish candidate/replacement chronology. The actual primary backend version is obtained from the explicit captured baseline alias, never by removing `NCI_` from the common version name. Proposed existing-version checks use each generated metadata row's explicit source/version fields. A backend version can therefore differ from the NCIt release suffix when the selected raw metadata alias establishes that identity.

## State and evidence roles

The schema requires these roles rather than collapsing them into one installed-termgroup list:

| Field | Meaning and binding |
|---|---|
| `scope` | Exact NCI candidate and explicit replacement baseline from the common configuration; October replacing August is valid. |
| `project` | Explicit backend project ID, terminology, version, branch, assigned precedence-list ID and source-SAID alternate-ID key. The key must equal the selected project terminology plus `-SRC`. Raw project fields are bound independently; the project is not inferred from source `NCI`. |
| `deployment` | Declared build/artifact/commit identities and project/SRC graph-handler names, with original evidence reference. These are unverified claims pending a real accepted producer/deployment contract. There is no `reviewed: true` bypass. |
| `capture` | Exporter profile, start/end times, declared consistent-state identity/boundary and separately referenced completeness evidence. Evidence hashes or equal timestamps alone cannot prove truth, consistency or exhaustive scope. |
| `raw_exports` | Unique relative paths, original byte hashes/counts and encoding. JSON rows can be bound by exact JSON pointers; opaque bytes remain pinned but cannot establish unparsed row meanings. |
| `families` | Source/root-terminology abbreviation and family, bound to raw `terminology`/`family` metadata fields. Family is not inferred from a name suffix or the representation catalog. |
| `source_versions` | Explicit source, raw backend version and current flag, bound to raw terminology metadata. Multiple retained versions are allowed; ambiguous current state becomes a finding. |
| `version_aliases` | Exact VSAB/source/backend-version identity mappings, bound to source-metadata `source_name`, `stripped_source` and `version` values. Captured and generated mappings for the same VSAB must agree. Neither underscores nor longest-prefix matching determine the source. |
| `replacement_sources` | Explicit source/backend-version membership selected for this NCImeta transition. Members must have matching captured current NCI-family metadata. This remains a reviewed transition selection, not a folder inventory. |
| `source_roots` | Each source's individually selected SRC/RPT atom, code `V-<source>`, atom version/branch, backend atom ID and separate source atom ID. All raw atom fields must match, and the selected `project-SRC` alternate value must equal the source SAID. Positive exact integers exclude booleans/floats. Duplicate/ambiguous roots and SAIDs are rejected. |
| `precedence_lists.default` | Ordered root-source/TTY pairs from the default list for the explicit project terminology/version, bound to the raw list ID and key/value sequence. |
| `precedence_lists.project` | The separately captured ordered list assigned to the selected project. Its ID must match the raw project assignment. Lists are never unioned; the same list ID cannot have conflicting states. |
| `term_types` | Generic TTY flags for the selected project terminology/version, independently bound to raw definitions. These are distinct from source/TTY rank membership. |

`binding` is a raw file path plus RFC 6901 JSON pointer selecting the original object. The initial JSON binding rules use explicit backend/source-metadata fields; **they are not a claim that a complete deployed exporter emits the synthetic fixture's combined JSON shape**. Original responses/files must remain original. Creating a new hand-normalized JSON projection does not turn it into verified raw capture. Textual `.src`/client output needs its own reviewed parser/provenance contract before its field meanings can be verified; this implementation does not fabricate one.

The full-concept response route identified in backend research remains a candidate to investigate. Default atom/code graph resolution can remove alternate IDs. Correct handler behavior, exact individual root selection, raw identifier retention, paging/index completeness and deployed producer identity still need real evidence. The SRC/RPT inventory also does not automatically validate or rebind the converter's separately saved hierarchy anchor.

## Semantic review behavior

The existing generator still validates the reviewed source plan and produces metadata in memory. V2 then uses exact generated/captured source identity maps to resolve versioned termgroup labels to root-source/TTY pairs. An absent external alias/anchor remains a finding; a guessed source prefix cannot satisfy it. Generator restrictions on source-plan metadata/ranking remain in effect; v2 is not a way to bypass an unsupported external ranking declaration.

The default list must satisfy the loader's low-pair rule: each required low pair already exists or is another incoming high pair. Missing-pair insertion is simulated independently for the default and project lists. A current/previous label that normalizes to the same **existing** pair is valid; only absent pending pairs need progress through their dependencies. Unresolved dependencies or genuine pending cycles remain findings. The tool does not claim that an existing high pair is repositioned by the backend, and does not delete existing pairs omitted from this batch. Such retained extra pairs appear as observations. New-pair decisions that conflict with installed pairs, and undeclared additions/reconciliation, remain review findings.

Existing generic TTY flag differences are explicit because the reviewed backend does not apply those changes from subsequent source metadata. Incoming rows that disagree on one global TTY's flags also require review. The preserved October representation model has source-specific CA2/CNU flag differences. The fixtures retain that fact and make no correction or claim about actual deployed generic flag values. A separate coherent-policy fixture harmonizes only its copied synthetic test model to exercise the otherwise clean path; it is not a proposed policy update.

Historical CTCAE/ranking exceptions remain findings even if a synthetic captured rank pair demonstrates target membership. Existence does not approve a semantic mapping or new ranking choice. No original source plan, policy, archived output or native producer was edited.

## Status and CLI

Every current v2 report has:

```json
{
  "status": "BLOCKED_PENDING_CAPTURE_VERIFICATION",
  "production_eligible": false,
  "execution_authorized": false
}
```

`semantic_status` is independently `PASS`, `FINDINGS_REQUIRE_REVIEW`, or `NOT_EVALUATED` when raw field meanings could not be checked. Six fixed capture blockers cover deployed build identity, project binding, exporter acceptance, handler selection, export completeness and a coherent capture boundary. Supplying plausible names, hashes, references or a complete synthetic artifact cannot clear them. Enrolling real acceptance behavior requires a separately reviewed change supported by real retained exports/deployment evidence.

In the existing isolated Python environment with `jsonschema` installed:

```sh
python -B tools/nci_backend_preflight.py --lock source-plan.lock.json --installed-state backend-state-v2.json --installed-state-sha256 <canonical-state-hash> --raw-export-directory preserved-original-exports --output fresh-review-report.json
```

The standalone CLI emits the report and exits **3** because the current capture status is blocked, matching the common preview convention. Invalid/tampered input exits **2** with clean stderr and no new report; **1** is reserved for unexpected/internal errors. `--output` creates a fresh read-only file and refuses to overwrite an existing report; stdout is available by omitting it. It generates no candidate files and starts no job. The common CLI is unchanged.

## Verification and next gate

Run `python -B tools/check_nci_backend_preflight.py` in that environment. The checks exercise raw-byte/field binding, exact SAID versus backend identity, skipped-month scope, alias conflicts and underscores, independent default/project dependency handling, retained extra pairs, TTY policy findings, malformed/ambiguous capture, fixed operational blockers, standalone CLI behavior and unchanged v1/lock inputs. All inventories and combined response-like payloads used by these fixtures are explicitly synthetic.

The next gate is actual producer/deployment discovery and a coherent read-only capture, followed by independent retained-export comparison against the selected NCImeta project. Native publisher discovery, production allocation, legacy QA and insertion remain separate requirements after that gate. No execution/production eligibility follows from this preview.
