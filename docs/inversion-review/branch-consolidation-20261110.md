# Branch consolidation, November 10, 2026

Keep `main` and the consolidated development branch, `test/inversion-replay-toolbox`. The consolidation preserves original commit history with ordinary merges; it does not squash or rebase the engines used by recorded replays. Main remains at `3be55ea33024ba9ef998207c1a6de9eb3e482a56`, and its untracked planning files remain untouched. No server files or production deployment change.

## Retained engine and archive references

Superseded branch names map to these annotated tags. Source/runtime SHAs in historical case contracts and actual execution receipts remain unchanged. The MDR/RADLEX registry uses `production_code_tag` alongside its existing exact `production_code_ref`.

| Previous branch or purpose | Retained tag | Commit |
|---|---|---|
| `November 3 production import` | `production-snapshot-20261103` | `3b125ed` |
| `baseline/meme-edit-20261103` | `archive/branches/20261110/baseline-meme-edit-20261103` | `bc085a3` |
| `baseline/meme-edit-additions-20261105` | `production-sources-20261105` | `36f1e10` |
| `fix/nci-explicit-pt` | `replay-engine/nci-explicit-pt-0de8ca2` | `0de8ca2` |
| `fix/nci-stable-context-order` | `replay-engine/nci-stable-context-order-bfda2ce` | `bfda2ce` |
| `fix/mth-consistent-identity-state` | `replay-engine/mth-identity-state-b2611ab` | `b2611ab` |
| `fix/mdr-consistent-history-context` | `replay-engine/mdr-history-context-dd7ae66` | `dd7ae66` |
| `Canonical NCIt configuration engine` | `replay-engine/nci-common-configuration-2a22938` | `2a22938` |
| `NM-271-inversion-rework` | `archive/branches/20261110/NM-271-inversion-rework` | `d65d9f6` |
| `Working branch before consolidation` | `archive/branches/20261110/replay-toolbox-before-consolidation` | `01161ca` |

The original `36f1e10` additions commit remains available even though the working branch previously carried a patch-equivalent cherry-pick. The MDR merge now also retains its original ancestry. The legacy `NM-271-inversion-rework` tip is archived only; its prototype changes are not merged into this production-derived implementation. Candidate engine tags identify reviewed replay code, not production releases.

## Merge and verification

MTH merge `e9a7d6dce1146fa53d4836e1cf0a38988efbf227` brings in its two original correction commits and actual-source regression tests. MDR merge `af55edbfe2753451a4d7b06cff35a67e85d51caf` retains its production-additions parent and reviewed correction. The only conflicts were add/add conflicts in `sources/MDR_29_1/bin/append_atn.pl` and `sources/MDR_29_1/bin/invert_mdr.pl`; both resolve to the exact reviewed `dd7ae66` bytes and modes. The stable shared runtime remains unchanged.

Eleven tree/path comparisons verify exact tested source/runtime/test bytes and modes, covering MTH, MDR, RADLEX, both captured NCIt versions, canonical NCIt, SNOMED and INV/ENV. All six obsolete local branch heads are ancestors of the consolidated working branch; the legacy prototype tip is not.

The local checks pass: common request 80, NCIt generator 37, common worker 27, MTH acceptance 55, MTH retained atoms 12, MTH context identity 15, and MDR actual-source corrections 8 (234 total). The bounded shared-runtime impact review also passes for all 169 runtime files and five reviewed source cases. Full historical inversion evidence remains in [current coverage](core-replay-coverage.md); this Git consolidation does not claim a new native replay. Exact revisions and validation counts are in the [machine-readable record](branch-consolidation-20261110.json).

## Publication and cleanup safeguards

Publish and verify the working branch and all retention tags before deleting redundant remote branches. Remote deletions must match the inventoried heads, so concurrent changes stop cleanup. Remove only the six clean registered baseline/fix worktrees after preserving their commits; keep the main and replay-toolbox worktrees, private capture/evidence directories and rollback bundle. The local pre-cleanup inventory and verified complete Git bundle are under ignored `.baseline-private/20261110-branch-consolidation/`.

Fetch the working branch and retained tags when preparing another checkout:

```sh
git fetch origin test/inversion-replay-toolbox
git fetch origin 'refs/tags/*:refs/tags/*'
```

Continue using the pinned engine/runtime commits from reviewed cases rather than treating the working branch tip as every historical engine. General release creation, production eligibility and NCIt's new-subsource/new-termgroup preparation remain separate migration work.
