# Acceptance Current Closeout

Decision date: 2026-09-08. Authority: Accepted ADR-0053 and the 2026-09-08
addendum to ADR-0058 (Acceptance Coordinator Persisted Evidence Ownership).
The maintainer approved these three bounded changes as functional/process
equivalence for the three historical requirements directories.

## Fixed Scope And End Condition

| Change | Required observable result |
| --- | --- |
| Explicit Bootstrap | Default intent never requires or launches Bootstrap, including control-plane/high-risk paths. Explicit intent selects the existing review route. Missing deterministic evidence still blocks. |
| Current Quick Dev handoff | Native Q8 proof supports present-only regression, missing-only TDD and mixed routes; all obligations/assertions remain covered. Blocking deferred records and stale proof reject. Acceptance executes its own registered checks. |
| Real Coordinator and replay | Actual input loading, Skill-input gate, candidate/knowledge validation, persisted execution and finalization compose successfully. Identical replay executes no action. Mutated inputs, events, receipts or finalization cannot reuse success. Failed commands stop once. |

Passing these deterministic checks closes the implementation scope. Windows
verification is a platform confirmation of the same scope, not a new discovery
round. This work does not reopen CH456 or require a live semantic/Bootstrap run.

## Requirement Reconciliation

| Original scope | Current disposition |
| --- | --- |
| 8-15 explicit-request Bootstrap (ARBE-005/021/022) | Implemented by decision v11 and current Coordinator explicit intent. Risk classification remains diagnostic. |
| 8-15 candidate custody, controlled execution, review ownership | Existing mechanisms retained; current handoff and real execution compose with them. |
| 8-15 complete automatic consumer closure and efficiency rollout | Explicit frozen consumer refs remain the supported contract. Full graph construction and empirical performance rollout are not required by the approved practical equivalence. No measured speedup is claimed. |
| 8-17 S0 identity and authority | Current Q8 plan/snapshot/predecessor proof replaces plan-local terminal receipt generation for current plans. Candidate manifests and ready Skill input are independently checked by Acceptance. |
| 8-17 S1 deterministic route | Current Q8 replay plus passed Acceptance-owned registered actions provides the deterministic route. Explicit review requests return a typed handoff. |
| 8-17 S2/S3 recovery and coordination | Persisted action ownership is retained; real entry is repaired, failed actions stop, successful replay revalidates evidence without duplicate execution. |
| 8-18 R0 trusted evidence | Actual loader checks target, prepared hash, manifests, knowledge and Skill input. The bound prerequisite bundle supplies actions and registry; caller route/action overrides reject. |
| 8-18 R1/R3 legacy successor and prior RED | Replaced for current plans by the existing explicit predecessor and immutable stage-reentry protocol. No duplicate legacy lifecycle is implemented. Incomplete runs fail closed rather than fabricate completion. |
| 8-18 R2 knowledge authorization/freshness | Existing shared validator and ready gate are retained and exercised with a small published fixture catalog. No new publication or authorization workflow is introduced. |
| 8-18 R4 old dogfood replay | Replaced for current use by real current Q8-to-Acceptance deterministic composition tests. Old evidence is not rewritten. |
| 8-18 R5 completion handoff | Native Q8 proof and explicit candidate custody replace legacy receipt synthesis. Acceptance independently publishes its own result; evidence-only additions do not change the declared Q8 runtime roots. |

Historical completion records retain their original schemas and candidate
bindings. This document records current equivalence; it does not rebind or
retroactively upgrade historical acceptance results. After the bounded checks
and platform confirmation, only a demonstrated usage defect or a new explicit
requirement opens new work.

## Current Operation

Use the existing `project-compact-vdd`, `prepare-run` and `run-coordinator`
commands. Add this field to a current compact projection request:

```json
{
  "currentQuickDev": {
    "semanticPlan": {"path": "<repository-relative-plan>", "sha256": "<file-byte-hash>"},
    "receipt": {"path": "<repository-relative-Q8-result>", "sha256": "<file-byte-hash>"},
    "snapshotRoots": ["<the exact eight Q8 root descriptors>"],
    "sourceCommit": "<original Q8 source commit>",
    "baseCommit": "<original Q8 base commit>"
  }
}
```

The placeholders above are descriptive, not executable example values.
`implementationReceiptPath/Hash` must match `currentQuickDev.receipt`.
Keep the explicit changed paths, baseline/candidate revisions, consumers,
required commands/actions, policy and Acceptance knowledge context.
Current plans need no fabricated legacy implementation contract or terminal runner.

The native Q8 terminal input carries a snapshot manifest. Read-only replay
rechecks all eight runtime roots and the original plan, predecessors, case and
edge proofs. The original Git-delta identity remains frozen; new Acceptance
outputs are outside that runtime proof. Acceptance separately validates its
candidate manifests and each controlled command result. If a summary predates
the manifest, publish a new Q8 result in a new output directory using explicit
existing predecessors. This invokes no model or test process; invalid/stale
predecessors still require current Quick Dev recovery.

A Coordinator request uses `jimuyun.acceptance-coordinator-request.v3`, one
`targetPlan`, `preparedRunInput`, `skillInputReceipt`, `skillInputContract` and
`authorizes=[]`. File references are path/byte-hash pairs relative to the request
directory. Omit `maintainerIntent` for deterministic Acceptance. Set it to
`request` only after an explicit user request for Bootstrap. The Coordinator
returns a typed handoff without launching a review.

Never edit stale cached evidence to make reentry succeed. Preserve it and supply
fresh explicit owner-produced inputs. A failed action returns waiting and cannot
be retried automatically by replaying that stored result.

## Validation Scope

Evidence and the Windows command list are in
`logs/acceptance-current-closeout-e76c0dfc/`.
The new composition tests use the real public Coordinator CLI dispatch, loader,
ready gate, knowledge validator, projection, command process, Q8 proof replay and
finalization. Only the external semantic-child backend is injected by the existing
test helper; it performs no live call. Production predicates are not mocked.

This session uses pinned repository file snapshots plus the explicit changed set,
not a full Git checkout. Integration fixtures create real isolated Git repositories.
The one historical 8-01 candidate test needs repository artifacts/history unavailable
in that snapshot environment; it remains in the Windows follow-up list.
