# Independent MTH correction audit

The corrected MTH run retains the raw archive comparison and its original verdict. A separate audit must explain every permitted difference; passing structural checks alone does not establish that the differences are correct.

The audit uses the frozen official archive's 23 selected output/state files and the same preserved native RRF inputs. Reference outputs are extracted into a temporary QA directory after conversion. They are never seeded into the candidate inversion.

The checks cover:

1. Original atom allocations are byte-identical, including the two deliberately unused CCS IDs. Final atoms are byte-identical to the official final atom file. Retained raw atoms exclude exactly the two known `SRC` / `V-CCS_2005` records.
2. Complete old and new AUI/CUI maps are predicted from those native allocations and unchanged split/moved state. The old prediction must match the official maps before the new prediction is trusted. The new maps must be complete, including the retained LOINCPARTS identity.
3. Native MRSAT, MRSTY, MRDEF and MRREL records predict the exact dependent record additions/deletions. Relationship direction, hierarchy exclusions, CUI roles, normalization, attribute hashes and duplicate multiplicity are retained. Every other native output record must remain in its original order.
4. Every generated native attribute/relationship ID is checked against the complete sequential allocation. Added/deleted native records account for ID shifts; unrelated field changes cannot pass as renumbering.
5. The blank-node context and its CONTEXT attribute are transformed into the known retained identity. Native identity metadata and MD5 are corrected, ordering is reproduced, and the entire expected context/attribute files—including generated attribute IDs—must match the candidate byte-for-byte.
6. Preferred helpers may change only for the two removed CCS atoms and their now-unreferenced preferred target. All other compared files remain exact. The audit also checks that typed output references cannot depend on the generated attribute/relationship IDs being reassigned.

The separate `PASS_REVIEWED_CORRECTIONS` result is available only if every check passes. It does not rewrite a raw `DIFFERENCES_REQUIRE_REVIEW` comparison or approve production insertion. Completed audit reports are published once and made read-only; failed attempts retain their logs.

The initial seventeen regression checks passed locally and on dev, including independent predictions compared against the actual unchanged MTH Perl producer and its captured relationship-normalization stage. They reject a missing retained mapping, lost duplicate, changed CUI role, unexplained generated ID, additional context change and replacement of an existing audit report. [Fixture evidence](mth-2026aa-correction-audit-fixtures.json)

The corrected conversion completed with clean independent validation. Its first full-data audit passed the map/native/context/pref-state predictions, then stopped at the final generated-ID reference guard because that new guard omitted CODE_TERMGROUP. SRCbuilder.pl:338 deliberately emits the unchanged SRC/VPT-to-SRC/RPT relationship with that type, and inv_defaults.cfg permits it in relationship fields 13/15. The correction admits only the exact code/termgroup reference counts in the unchanged frozen rel_src file; generated-ID and other unknown references remain forbidden. The first failed audit logs/result are retained. The full audit retry passed with `PASS_REVIEWED_CORRECTIONS`, exit 0, in 337 seconds. All unchanged records, corrected records and generated-ID shifts were accounted for. The corrected guard has 20 passing fixtures locally and on dev. [Final audit result](mth-2026aa-correction-audit-result.json), [updated fixtures](mth-2026aa-correction-audit-fixtures-v2.json). [First attempt](mth-2026aa-correction-audit-attempt1.json) The existing original baseline and its three invalid rows remain preserved as historical evidence.


Of 19,131,022 native attributes, 19,131,021 retain their content and order; one CCS semantic type is removed and one LOINCPARTS semantic type is added from the preserved MRSTY records. All 6,404,200 relationships retain their content, order and generated IDs. Exactly one context row and one context attribute are corrected; the complete expected context files, MD5 values, ordering and regenerated attribute IDs match byte-for-byte. The allocation of every atom is unchanged. This is core correction acceptance; metadata generation, legacy QA/MRDOC, insertion and production promotion remain separate gates.

## Integration with the common interface

The corrected historical case now selects `comparison_profile: reviewed-corrections`. The common worker freezes this audit with the other apparatus, preserves the raw result, and invokes the audit as a bounded offline subprocess before publishing final acceptance. A run/engine/apparatus mismatch, failed core or identity validation, missing report, changed input/output, or failed audit blocks acceptance. The original archive and raw verdict remain separate from the correction acceptance. The full integrated replay is the next validation gate; the earlier standalone replay/audit retain their original apparatus identities.

The integrated acceptance layer has 55 passing fixtures locally and on dev. The 20 native-audit and 20 worker checks also pass in both environments, and 49 local common-request checks pass. Tests cover missing or mismatched evidence, changed files, audit failure, exact-profile isolation and collection of both raw and reviewed results. [Fixture evidence](common-mth-acceptance-fixtures-20261106.json).
