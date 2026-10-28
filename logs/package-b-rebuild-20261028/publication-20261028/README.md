# Package B reviewed publication

This branch publishes the six-requirement, five-package Package B migration and its necessary bounded prerequisites. Package A is reused. Bootstrap remains optional. BMAD device configuration, Phase application changes and Chapter 2-7 work remain excluded.

## Run and publication identity

The actual native Quick Dev/Acceptance candidate was `13bd5b598ffde513cd75acea072f0e433f6c91b0`; original delivery base was `fb676bc398f653a2ffa869c95d6c8d632f6f9796`. This publication is a separate commit whose parent is the verified remote main, not a push of the private local checkpoint history. All 39 shared source/test/contract/requirement blobs match the accepted candidate. The exact mapping, selected raw files, hashes and exclusions are in [publication-manifest.v1.json](publication-manifest.v1.json). This new publication SHA did not execute the original Acceptance run.

## Requirement and evidence entrypoints

- [Original Package B](../../../docs/workflows/skill-control-plane-evolution-requirements.md) and [canonical input](../../../docs/workflows/inputs/package-b-rebuild-20261028-r2/requirements.md).
- [Current native r3 directory](../../../execution-plans/2026-10-28-skill-compliance-package-b-rebuild-r3/) with r1/r2 lineage preserved.
- [Current Q8](../proof-refresh-final-inputs-r16/Q8.json) and [causal RED](../quick-dev-s1-r6/canonical-evidence/red/observation.v2.json).
- [Formal acceptance-passed](../../../execution-plans/2026-10-28-skill-compliance-package-b-rebuild-r3/acceptance-runs/acceptance-4b4e9ae76fdd229b/finalization/acceptance-passed.v1.json): native Coordinator exit 0, nine actions passed, final controlled pytest 129/0 failures/errors/skips.
- [Fresh independent A report](../reviews/final-independent-acceptance-020/A.md), [B report](../reviews/final-independent-acceptance-020/B.md), [comparison](../reviews/final-independent-acceptance-020/COMPARISON.md). New separate Astra/high contexts; each zero confirmed P0/P1/P2. This is external support for the native outcome, not a newly minted authority receipt.

## Portable test prerequisites

From the repository root, use a compatible Python and pytest installation and run `python -B -m pytest scripts/sc/tests/test_skill_quality_package_b.py -q`. Owning-package regression selectors are in `agent-context/S1/agent-context.json` under the r3 plan. Preserve the original stage003 ZIP and receipt at their existing repository-relative paths; its 661 payload records are hash-verified locally with no Library download/login. The non-credential historical Library IDs in those originals are not access tokens. A full clone, or explicit availability of the original `fb676bc3...` baseline objects, is required by `git show` preservation tests; a depth-one checkout may omit them.

## Limits and deliberate exclusions

The 15 local derived Knowledge payloads and 45 identical snapshot copies are excluded, as are private recovery ZIP/bundle chains and unrelated old CRLF status. Their unchanged historical references/hashes may remain in raw receipts. The main baseline Knowledge content is preserved. Therefore this is a shared implementation and original-evidence publication, not a self-contained restore of the former device or every historical runtime dependency. Fresh full Acceptance elsewhere must prepare local command/environment bindings and a legal local Knowledge generation; do not reuse absolute paths, old environment hashes, or claim the old candidate was run in that new environment.

Actual execution evidence is Linux. Real Windows full-flow deployment and optional Bootstrap model launch were not performed; no fresh second-device deployment is claimed. Private Library creation acknowledgment plus local restore checks are not remote download-hash verification. No BMAD device config, model settings or credentials are published. CI, review and merging are handled by the user; no CI monitoring or automatic merge is requested.

Full duplicate generated source snapshot payloads are excluded as well; their native manifest/hash records remain. Device synchronization, cache-cleanup and backup housekeeping is not promoted into the shared product package. Historical source identities remain explicit, and the public tree is not represented as a full device recovery image.
