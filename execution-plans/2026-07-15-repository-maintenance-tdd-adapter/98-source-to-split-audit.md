# Source-To-Split Audit

## Source Preservation

The original source remains `agentbuild.txt` at SHA-256 `1eff0054ca233d70ef00a8b5883f748a8e466e454fc9ff8f8f07a4d4f9dd8807`. It is not copied or rewritten in this directory.

## Section Audit

| Source section | Lines | Split owners | Treatment |
| --- | --- | --- | --- |
| I. Three responsibilities | 1-70 | 01, 02, 04, 97 | Preserved; confidence made advisory and bounded |
| II. Lightweight SDD companion | 74-199 | 02, 03, contract/schema, 97 | Preserved as machine projection; no duplicate prose authority |
| III. Adapter definition | 203-221 | 02, 04, 05 | Preserved; backend v1 changed from stock Quick Dev to repository capsule executor by clarification |
| IV. TDD protocol | 225-360 | 02-07, fixtures | Preserved and strengthened with shell/env/path/drift/recovery rules |
| V. BMAD position | 364-416 | 01, 02, 04, 07 | P0-P3 preserved; BMAD removal deferred to separate plan |
| VI. External framework lessons | 420-432 | 01, 02, 08 | Preserved as rationale, not imported runtime dependencies |
| VII. Adapter tests | 436-464 | 03, 06, fixtures | Preserved and expanded with neutral/supportive/competing cases |
| VIII. Minimum layout | 468-513 | 00, 01, 03, schemas/tools | Normalized to three-layer ownership and logs evidence boundary |
| IX. Implementation order | 517-597 | 04, 07 | Preserved as P0-P3; P4 explicitly moved out of scope |

## Clarification Deltas

- `MODIFIED`: all three existing refactor plans are backfilled, not a single pilot.
- `MODIFIED`: backend v1 is repository-owned and implementation-only because stock Quick Dev has no compliant implementation-only route.
- `MODIFIED`: old-plan backfill is additive metadata plus non-authoritative shadow validation.
- `ADDED`: one framework ADR and exact three-layer ownership.
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

No requirement is silently dropped. Machine-level delta details live in `schemas/spec-deltas.v1.json`.
