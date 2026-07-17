# Source-To-Split Audit

## Source Preservation

The original source remains `agentbuild.txt` at SHA-256 `1eff0054ca233d70ef00a8b5883f748a8e466e454fc9ff8f8f07a4d4f9dd8807`. It is not copied or rewritten in this directory.

## Section Audit

| Source section | Lines | Split owners | Treatment |
| --- | --- | --- | --- |
| I. Three responsibilities | 1-70 | 01, 02, 04, 97 | Preserved; confidence made advisory and bounded |
| II. Lightweight SDD companion | 74-199 | 02, 03, contract/schema, 97 | Preserved as machine projection; no duplicate prose authority |
| III. Adapter definition | 203-221 | 02, 04, 05 | Preserved; backend v1 changed from stock Quick Dev to repository capsule executor by clarification |
| IV. TDD protocol | 225-360 | 02-07, schemas, fixtures | Preserved and strengthened with shell/env/path/drift/recovery rules plus immutable Capsule context |
| V. BMAD position | 364-416 | 01, 02, 04-07, schemas, fixtures | P0-P3 preserved; backend attempts gain append-only evidence while BMAD removal remains deferred |
| VI. External framework lessons | 420-432 | 01, 02, 08 | Preserved as rationale, not imported runtime dependencies |
| VII. Adapter tests | 436-464 | 03, 06, fixtures | Preserved and expanded with neutral/supportive/competing cases |
| VIII. Minimum layout | 468-513 | 00, 01, 03, schemas/tools | Normalized to three-layer ownership and logs evidence boundary |
| IX. Implementation order | 517-597 | 04, 07 | Preserved as P0-P3; P4 explicitly moved out of scope |

## Clarification Deltas

- `MODIFIED`: all three existing refactor plans are backfilled, not a single pilot.
- `MODIFIED`: backend v1 is repository-owned and implementation-only because stock Quick Dev has no compliant implementation-only route.
- `MODIFIED`: old-plan backfill is additive metadata plus non-authoritative shadow validation.
- `MODIFIED`: reuse accepted ADR-0041 as the shared control-plane ownership precedent and Bootstrap execution authority; add the repository-maintenance adapter standard without allocating a colliding ADR.
- `ADDED`: shell=false, env allowlist, typed placeholders, Windows containment, Git index, execution read set, and dependency closure.
- `ADDED`: append-only recovery with stale predecessor and normally initialized successor.
- `ADDED`: no open accepted P0/P1; every accepted P2 disposed; high-risk and expired deferrals block.
- `ADDED`: implementation-contract instances belong to plans; common schema belongs to the Skill; runtime evidence belongs to logs.
- `REMOVED`: no first-release Bootstrap CLI modification without a proved extension-point gap.
- `REMOVED`: no P4 BMAD removal within this plan.

## Control-Chain Repair Deltas

- `MODIFIED`: plan state is blocked by the durable Round 3 manual-pause projection; local deterministic validation cannot clear it.
- `MODIFIED`: S2 proves lifecycle under `slice-ready`; S6 finalizes the current candidate without Bootstrap output; S7 alone consumes finalized Bootstrap evidence for acceptance.
- `MODIFIED`: command registry owns execution descriptors while each stage invocation owns expected exit, selector, and failure IDs.
- `MODIFIED`: every slice consumes explicit run and stage evidence; repository-wide `logs/**` discovery is removed.
- `ADDED`: executable acceptance registry, complete authority manifest, clarification projection, and review blocking projection.
- `ADDED`: clean-checkout shadow baseline projection, derived requirement-quality hashes, exact earliest-phase validation, and complete candidate identity policy.
- `ADDED`: `RMAP-025` immutable persisted Capsule revisions with typed, exact-union, actual-byte artifact closure and `RMAP-026` complete ordered stage attempts with exact event lifecycle, recomputed diff facts, decision/stage-result binding, ledger-root closure, and S6 candidate binding.
- `MODIFIED`: S6 candidate evidence is a cumulative baseline-to-final diff manifest that must exactly equal scoped Git state and the accepted-attempt fold; test patch bytes are reproducible and rename inference is disabled.
- `MODIFIED`: S6 folds immutable S0-S6 run references, per-slice attempt effects, and final event hashes before comparing the cumulative result with Git.
- `MODIFIED`: S7 replaces `superseded:false` with a hash-bound recovery/event/successor proof and consumes runtime Bootstrap P2/verifier sources.
- `ADDED`: immutable manual-pause successor artifact binds the old blocker hash and requires a distinct policy/authority cycle plus independent semantic closure.
- `MODIFIED`: `RMAP-001/002` reuse Accepted ADR-0041 and classify 7-12 only as a hash-bound compatibility input; `RMAP-012/016` consume repository-owned Bootstrap finalized/runtime evidence; `RMAP-014` owns cross-slice candidate lineage.
- `MODIFIED`: ownership field `framework_adr` is renamed to `ownership_pattern_adr` without changing the accepted ADR-0041 identity.
- `MODIFIED`: Bootstrap finalized-run evidence is producer-recomputed, directly hash-binds verifier and P2 sources, and manual-pause re-entry consumes a schema-valid successor decision plus trusted authorization-event lineage.
- `MODIFIED`: cumulative slice effects are derived from complete validated protocol runs and real diff manifests; first-add paths are distinct from existing-file baseline identity.
- `MODIFIED`: cross-slice predecessor fields are separated from same-slice recovery and supersession fields, and stale transitive inputs invalidate downstream projections.
- `ADDED`: `RMAP-027` applies one exact seven-dimensional proof template to every review-added normative, projection, evidence, lineage, and validator artifact before a predicate may consume it.
- `REMOVED`: mutable single-Capsule overwrite, standalone adapter-decision authority, and any need for a Router or S8.

No requirement is silently dropped. Machine-level delta details live in `schemas/spec-deltas.v1.json`.
