# Package B publication boundary draft

This is preparation only. No publication commit, branch, push, or pull request has been made.

The inspected execution candidate is `13bd5b598ffde513cd75acea072f0e433f6c91b0` on the original `work` branch. The remote `main` was actually queried and resolved to `fb676bc398f653a2ffa869c95d6c8d632f6f9796`. Recheck it before any future write.

## Shared content proposed for publication

`PROPOSED-SHARED-BLOBS.json` enumerates 39 exact shared implementation, test, contract, requirement, and documentation paths. Every worktree byte was verified against the execution candidate Git blob. The manifest contains modes, blob OIDs, SHA-256 and byte lengths. No BMAD device configuration, wrapper, native BMAD installation, Phase application, credential, or model configuration is in this list. This is a source proposal, not a completed public evidence selection or secret audit.

`PUBLICATION-BOUNDARY-DRAFT.json` separately inventories 158 plan-lineage/native Acceptance input/output candidates and 589 raw evidence/custody entries for narrow selection. Retain the original requirement/canonical input, r1-r3 native plan lineage, actual causal RED/GREEN, r16 Q7/Q8 and executed receipts, formal nine-action Acceptance originals and current/final receipts, failed predecessor outcomes, and this fresh A/B review. Never rewrite their candidate SHA or freshness claims.

## Local-only boundaries

The local Git chain includes 15 derived Knowledge files (4,353,123 raw bytes) that were approved only for a local checkpoint. The same byte payload occurs in 45 additional snapshot files. A normal push of `work`, followed by a deletion commit, would still publish those bytes in history. Do not do that. Full generated snapshots (1,127 entries), compiler intermediate history (276 entries), six runtime attempt files, unrelated CRLF status, and six recovery ZIP/bundle files are not a blanket publication list. The private Library recovery chain remains available. Archive name inspection alone does not prove that all nested payload is safe for publication.

Omitting local Knowledge and complete snapshot payloads means the public evidence package is not a self-contained replay of the full accepted runtime tree. The unchanged original receipts remain evidence for the original execution candidate, not proof that a new publication SHA was executed. Record any missing public dependency by path/hash and its private custody location. Do not claim completeness based only on the presence of a green receipt. The parent coordinator must adjudicate this boundary before publication.

## Safe branch assembly proposal

After boundary approval, recheck remote main and branch concurrency. Without switching the original worktree or creating another worktree, a separate temporary Git index can read the verified remote main tree, overlay an explicit approved blob list, and create a distinct publication commit with that main commit as parent using normal Git plumbing. Do not alter the original index, `work` ref, local source files, untracked evidence, or private configuration. Inspect the proposed tree and any secret risks before creating/pushing a new non-main review branch. This avoids publishing the private local checkpoint ancestry. No force update.

The publication manifest must map original run candidate + frozen evidence to publication tree, verify all 39 shared source blobs are identical, list exact exclusions, and disclose that the new commit/tree was assembled for review rather than used for the native Acceptance run. Public source and copied raw evidence hashes may be verified without rerunning the workflows. If the owner instead requires a fully self-contained public runtime snapshot, obtain a precise decision about the previously local-only Knowledge payload; do not infer it from a general PR instruction.

## Required fixture exception to blanket archive exclusion

The existing Package B test oracle `scripts/sc/tests/test_skill_quality_package_b.py::_persistent_input` (lines 312-335) directly reads the immutable `logs/package-b-rebuild-20261028/LIBRARY-STAGE003-DURABLE-RECEIPT.json` and the exact archive designated by that receipt: `stage-vdd-plan-ready-003.zip` (4,506,730 bytes, SHA-256 `0588a3bac1d6d913071327d8686a73b2f109e300e75c43c91d20e4a649da742e`). A source publication that omits these inputs would break a declared test precondition. They are therefore specifically nominated as necessary test evidence, subject to the public payload review; do not change the oracle or receipt to avoid including them. The archive entry names contain no local derived Knowledge/device/transfer path, but that name check is not a full nested content audit. Other recovery archives and Git bundles have no such demonstrated necessity and remain private by default.
