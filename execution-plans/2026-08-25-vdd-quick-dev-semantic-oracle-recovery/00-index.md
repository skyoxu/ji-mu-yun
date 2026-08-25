---
plan_id: vdd-quick-dev-semantic-oracle-recovery
profile: self-hosted
state: plan-ready
canonical_selection: sha256:4cf516d611eb0aba633adcebc37df679e6270dd74f231fd98c782a6e754def40
authority: _bmad-output/specs/canonical-spec-package-selections/current/SPEC-vdd-quick-dev-semantic-oracle-recovery.json
---

# VDD Quick Dev Semantic Oracle Recovery

## Scope

This self-hosted architectural plan consumes the canonical current selection,
not the provenance PRD. It changes the VDD, Quick Dev, independent
executor/judge and coverage-gate boundary so that every active Acceptance ID
has one admissible manifest-to-observation evidence path. The candidate Quick
Dev remains SUT for N to N+1 promotion.

Repair rounds 1-4 rebound skill-input to selection `sha256:4cf516d611eb0aba633adcebc37df679e6270dd74f231fd98c782a6e754def40`; the round-4 semantic child produced typed artifacts and the gate is ready.

VDD writes only `semantic-verification.v1`, `active-acceptance-manifest.v1`,
`failure-taxonomy.v1`, and hash-free `semantic-rejection.v1`. Quick Dev alone
writes descriptors, recommendation/reuse decisions, live blockers, recovery
artifacts and pre-execution failure IDs. Executor/judge alone writes receipts,
observations and post-execution IDs. Coverage gate alone writes coverage,
snapshots, completion and promotion.

## Non-goals

- Implementing the top-level external coordinator, review/commit authority,
  Chapter 5 processing, or legacy-plan mutation.
- Allowing VDD to create commands, descriptors, receipts, observations, hashes
  or failure IDs.
- Treating a deferred policy as a Quick Dev default.

## Slice Order

| Slice | Behavior | RED / negative intent | GREEN / acceptance target | Recovery |
| --- | --- | --- | --- | --- |
| S1 | VDD semantic intent, active manifest, taxonomy and hash-free rejection. | Intent that embeds executable or hash, omits an active ID, producer, fixture class or taxonomy member rejects. | Semantic contract has FR-1/2/10 fields and no downstream-written field. | Repair VDD intent; do not generate a run artifact. |
| S2 | Quick Dev compiles immutable descriptor and publishes recommendation/reuse/blocker/recovery projections. | Mutable target/cwd/fixture, VDD command, or recovery-created result quartet rejects. | Descriptor/recovery ownership and invalidation fixtures pass. | Create a fresh descriptor or blocker revision. |
| S3 | Independent executor/judge produces raw receipt, observation and layered result. | SUT self-report, zero execution, copied expected matrix, or noncanonical ID rejects. | Positive, negative and mutation fixtures prove receipt/observation ownership and AD-6/16 legality. | Preserve receipt as historical; create a new judge observation. |
| S4 | Coverage gate proves exact cover, coherent snapshot and completion. | Missing graph arrow, stale identity, orphan Acceptance ID, forked snapshot or invalid evidence rejects. | Sound-and-complete many-to-many manifest-to-observation cover and completion predicate pass. | Recompute from one closed snapshot; never compose newest leaves. |
| S5 | Self-hosted N to N+1 promotion and nine false-green regressions. | Candidate self-judging, unfrozen predecessor, or any of `FG-01`, `FG-02`, `FG-03`, `FG-04`, `FG-05`, `FG-06`, `FG-07`, `FG-08`, `FG-09` blocks promotion. | Frozen independent judge blocks all nine known false-green fixtures; corrected fixtures pass; coverage writes promotion. | Candidate remains SUT; retain blocked evidence. |
| S6 | End-to-end replay and recovery publication. | Tampered selection, deferred-gate bypass, profile weakening, or stale recovery root rejects. | One terminal replay validates all active IDs, exact cover, independent judge, fixture corpus and recovery projection. | Return to the earliest invalid slice and rerun declared downstream slices. |

## Deferred Decision Gates

No implementation slice may infer these decisions. A versioned decision artifact
is a prerequisite at the indicated trigger.

| Gate | Deferred decision | Trigger before execution |
| --- | --- | --- |
| DG-1 | Comparator types and output normalization | First case-matrix schema or cross-platform receipt fixture (S3). |
| DG-2 | Judge retention, revocation and upgrade lifecycle | More than one predecessor judge or any revocation workflow (S5). |
| DG-3 | Runnable rollback-probe interface | First recovery-class oracle (S1). |
| DG-4 | Unexpected-green existing-behavior proof | Regression-mode conversion of an unexpected green (S3). |
| DG-5 | Stop-loss repetition threshold | Profile retry policy or repeated-fingerprint stop-loss (S2/S3). |
| DG-6 | Cross-platform schema/hash successor policy | Non-Python or cross-platform receipt writer (S3). |
| DG-7 | Detailed semantic-change partial-reuse matrix | Reuse beyond coverage recomputation from identity-valid observations (S2/S4). |

## Lifecycle

VDD has published `plan-ready`. The maintainer alone may publish
`implementation-authorized`; Quick Dev alone may later publish
`implementation-complete` after the terminal command. Acceptance and archive
remain separately owned.

## Validation

Use only the structured descriptors in `command-registry.v1.json`. Each
validator, executor and schema change needs positive, negative and mutation
fixtures. S5 owns exactly nine `FG-01`..`FG-09` regressions and corrected
fixture pairs. S4 owns a sound-and-complete many-to-many Acceptance ID
evidence-path exact cover. S6 is the one terminal full replay.
