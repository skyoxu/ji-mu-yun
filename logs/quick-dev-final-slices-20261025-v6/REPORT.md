# Stage 5 Q8 closeout after the approved minimal performance repair

Completed at 2026-10-25T18:48:14.195385+00:00. Execution is stopped. This is a production evidence index, not external A/B or final Acceptance.

## Result and identity

- Native implementation-complete Q8: **pass**, exit 0, 388.415 seconds. Exactly 12 predecessors and 610 runtime closure tuples cover 305 active Acceptances through regression and terminal. The native exact-closure predicate passed.
- Plan: `execution-plans/2026-10-25-vdd-knowledge-query-caller-runtime-role`; semantic bundle SHA256 `7b4c69ff7e4a64bafbc3a8d6dd0ed4c83c1ab3c21935bd1f9d3e581f5e583276`.
- Local host: `d86539b9602d9cff7cfe1d96ae6a58b287ce7b3d`. The isolated host commit contains exactly the three repair files listed below. No push, PR or merge occurred.
- Q8 result byte SHA256: `9a6620fc66ec0530475b4b60396ab8e7888d6e73147c54aae4210055ff2c5f20`.
- Terminal input semantic SHA256: `sha256:c0cdb4cde0213e0bbc0e4bc0b51d00585b698cdb91951be0e22e110f17ea9117`; runtime closure semantic SHA256: `sha256:b32ee96a9e442c9a8db334bf5d144c2cc4189f9da7781828011a6373fe425824`.
- The twelve post-terminal current snapshots were independently reread after execution and still match their Q7 results. Frozen source hashes and the host HEAD also match final-inputs.json. Native receipts, observations, descriptors, output bytes and target/fixture hashes were checked; the report does not upgrade older receipts.

## Minimal repair and its verification

Committed host files: `.agents/skills/quick-dev-tdd-adapter/tools/coverage_predicates.py`, its `tools/tests/test_coverage_predicates.py`, and `references/shared-execution.md`.

Q8 uses an invocation-local original-check collector separately within each predecessor replay context, and finishes it before leaving that context. Complete descriptor/receipt/environment/profile/output policy identities distinguish originals. Every edge and tuple is still independently checked, current snapshots are reread, and file/directory/environment seals reject observable mutation. Output hashes are checked. No cross-call cache, path-only trust, producer/evaluator compatibility split or new protocol was introduced.

The successful path references 27 distinct originals (12 main, 12 terminal, 3 additional S12 Q6) instead of the prior static full-success estimate of 1749 repeated original-validation invocations. These are source/graph counts, not claimed measured I/O. The full run produced 1578 genuine completed-progress events, 1273 distinct digests; repeated canonical checks retain duplicate digests and cannot renew inactivity. One Q8 unit retained 1800 total / 600 genuine-inactivity limits, without per-predecessor resets or heartbeats. The earlier 600-second timeout remains preserved and is not treated as a business RED.

Focused verification: 25 relevant Q7/Q8 cases passed, plus 1 native shared-original/terminal/Q8 fixture passed. The tiny closure retains all 11 edge checks while performing four original checks. Negative coverage includes different contexts, invalid/missing/duplicate lineage, corrupt outputs/fixtures, concurrent observable mutation and no cross-call cache. Initial failures and fixes are retained in `logs/quick-dev-q8-performance-fix-20261025`.

A separately included, pre-existing ADR-0058 transfer fixture still fails its old behavior_routing.py owner pin. The current file bytes equal the pre-repair parent, as recorded in that repair report; this unrelated adapter was not modified. This is not a blanket all-repository test-success claim.

The only business test-source adjustment was the exact approved-host provenance guard: it recognizes this three-file child while retaining prior exact ancestry, file-set and publication checks. Business requirements, oracle, runtime test body, production compiler, frozen contract and source inputs were not changed during this refresh.

## Current slices

| Slice | Q7 | Terminal | Current snapshot | Main selected cases |
|---|---|---|---|---|
| S2 | pass | pass | matches | 108 |
| S5 | pass | pass | matches | 108 |
| S6 | pass | pass | matches | 619 |
| S1 | pass | pass | matches | 619 |
| S3 | pass | pass | matches | 619 |
| S7 | pass | pass | matches | 619 |
| S8 | pass | pass | matches | 619 |
| S4 | pass | pass | matches | 619 |
| S11 | pass | pass | matches | 619 |
| S12 | pass | pass | matches | 619 |
| S10 | pass | pass | matches | 619 |
| S9 | pass | pass | matches | 619 |

## Execution and reuse

- 39 necessary new test-stage attempts: 12 probe, 12 main, 12 terminal, and 3 distinct S12 Q6 commands. All exited 0 with valid native results. No failure retry or model author call was needed.
- Q6 directly references the same-run primary 12 times, avoiding 12 duplicate executions. The three extra S12 commands are distinct frozen-contract commands and passed, selecting 1857 case calls in total.
- Primary-stage call events: 19218 passed, zero failing/skipped call events. This counts repeated executions across stages; it is not a unique-scenario count.
- Old proofs actually observed the changed reader and boundary test; positive manifests bind those bytes. Their current-host rejection is substantive, not Git-SHA-only. They remain intact as history and were not rewritten or given invented fields. Safe automatic shared publication remains unavailable for these Git/subprocess fixtures because their external-effect observations are incomplete; no shared hit is claimed.
- The prior real Windows 13-pass artifact remains scoped to its unchanged runtime dependencies. This Linux closeout does not claim that the new compiler/Q8 implementation was itself executed on Windows. No Actions query or new CI run occurred.
- Unrelated existing host diagnostics and original documents/evidence were preserved; no BMAD skill or reviewer, external A/B, Acceptance, model change or publication was performed.

## Evidence entry points and stopping point

- `final-proof-summary.json`: twelve current snapshots and stage receipt checks.
- `completion-metrics.json`: exact execution/reuse counts, Q8 supervision and event paths.
- `evidence-index.json`: artifact byte hashes, including raw supervision and outputs.
- `Q8/implementation-complete-result.v2.json` and `Q8/terminal-input.v2.json`: native authority; no author-generated replacement.
- `Q8/native-command.json`: actual native argv and supervision limits.
- `current-slice-status.json`, `checkpoint.json`, and `progression.stdout.txt`: author navigation and stopped-process trace.

The stage 5 technical Q1–Q8 closure is complete. External stage-end review and final Acceptance remain **not run**. No active coordinator or Q8 child remains; no follow-on stage was started. Existing local production changes and unrelated dirty work were preserved. This step stops here for the user's next decision.
