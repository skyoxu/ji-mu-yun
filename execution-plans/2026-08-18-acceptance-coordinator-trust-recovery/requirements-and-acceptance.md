# Acceptance Coordinator Trust Recovery

## Purpose

Repair the Acceptance and Quick Dev control-plane trust and recovery gaps
identified against baseline `3c285bcc`. This plan does not change the
historical evidence in `2026-08-17-acceptance-coordinator-efficiency`.

## Authority

The repair consumes the current repository-owned Acceptance control plane.
Its implementation must preserve lifecycle ownership: Maintainer owns
`implementation-authorized`, Quick Dev owns `implementation-complete`, and
Acceptance owns `acceptance-passed`. Bootstrap is never started automatically.

## R0: Trusted Coordinator Evidence

The coordinator must accept only `acceptance-coordinator-request.v3` inputs
that locate a target plan and hash-bound prepared run input. It must derive the
binding-owned Acceptance run through `start_or_resume_target_run`, inspect and
resume only the persisted action DAG and command registry, and project the
route from persisted route-projection evidence. Request-local route booleans,
producer assertions, action receipts, successor pointers, and telemetry are
invalid current inputs. A v2 request is historical-only and must not publish a
current completion result.

Acceptance: a complete self-consistent evidence graph under a temporary
request directory is rejected; a completed persisted action whose receipt is
not bound to its run, registry, event, candidate, contract, Knowledge, and
Skill-input bindings is rejected.

## R1: Reentrant Successors

Quick Dev successor identity must be reserved before materialization and be
reusable only when its lineage and bindings are byte-identical. A retry after
each successor creation boundary must either resume the same successor or fail
closed on conflicting content; it must not create a duplicate or overwrite
historical observations. GREEN and prior-RED handoff must have one recoverable
transition record.

Acceptance: injected failure after reservation, materialization, lineage, and
closure can be retried to the same terminal result.

## R2: Knowledge Authorization Continuity

Base maintainer authorization binds the implementation contract, authority
manifest, Knowledge selection identity, permitted successor kinds, and
Skill-input contract. A verified refresh successor may advance only a
refresh-eligible, unchanged Knowledge selection to new source bytes. Selection,
scope, contract, command, test, policy, or risk changes require maintainer
reauthorization. Acceptance and Quick Dev must validate the full refresh chain.

Acceptance: a same-selection eligible refresh continues through a
binding-derived successor; a selection or execution-semantics change stops at
`awaiting-implementation-authorization`.

### R2-FRESHNESS: Fast-Evolution Knowledge Degradation

Knowledge freshness is an execution quality signal, not a universal execution
gate. During rapid repository evolution, the coordinator must distinguish
context refresh from authority change:

An Accepted architecture decision must supersede the stale-stop interpretation
in ADR-0057 before this behavior can become `plan-ready`. That decision must
preserve ADR-0050's LKG integrity and publication gate; this plan does not
self-authorize the architecture change.

- A successor starts from the last valid published or LKG catalog and replays
  the frozen Locator selection. It must preserve consumer, policy revision,
  required modules, accepted path/module IDs, `satisfies` mappings,
  resource-set, and the four Knowledge scope dimensions. A ranking change is
  telemetry only; it cannot silently replace an accepted candidate.
- A failed staging generation, invalid pointer or manifest, policy/projection
  mismatch, tampered LKG input, or an LKG that is not an ancestor of current
  `main` is not ordinary staleness and remains hard blocked. The execution path
  may consume only a verified published/LKG catalog.

- `catalog_stale` or a selected read-set byte change triggers a controlled
  frozen-selection replay, source rehash, and successor context. It keeps the same
  selection, scope, and resource semantics and records
  `knowledge_freshness=degraded` or `source_freshness=refreshed`.
- A query-evaluation or publication-quality failure blocks publication of a
  new Knowledge authority, but does not block plan execution when the current
  Locator result, selected read-set, and required modules remain verifiable.
- Selection, scope, resource-set, policy, contract, command/test identity, or
  authority changes remain typed repair or authorization blockers. Bytes of an
  authority-bearing selected source (repository rules, Accepted ADRs,
  contracts, registries, Skill contracts, consumer policies, projections, or
  protected-path rules) also invalidate base authorization even when its path
  and module ID are unchanged. Missing or unreadable required sources remain
  blocking.
- Acceptance and Quick Dev may consume the verified successor context, but
  neither may publish Knowledge authority or rewrite maintainer authorization.

The degraded execution exception applies only when the target is not modifying
the Locator, evaluator, publication gate, catalog builder, Knowledge policy or
projection, or the query contract under test. A Knowledge-system self-change
with a failed query gate requires semantic review and cannot reach deterministic
terminal completion until the query gate is repaired.

Acceptance: stale catalog and same-selection source-byte drift produce one
binding-derived successor and continue in degraded mode without manual context
assembly; query-quality failure is isolated to Knowledge publication; selection
or source-authority drift remains blocked and routes to reauthorization. A
valid LKG is never replaced by a failed staging generation.

### Successor Receipt Contract

The successor receipt is produced by the controlled Knowledge/Acceptance
validator, not asserted by Quick Dev or VDD. It binds the predecessor and
successor context hashes, `knowledgeSelectionHash`, authority-envelope hash,
verified LKG pointer and manifest, selected read-set hashes, validator command
identity, and the complete successor chain. It records
`selectionUnchanged=true`, `authorityUnchanged=true`,
`publicationAuthorized=false`, and `authorizes=[]` only after those values are
recomputed by the validator. A missing or broken predecessor chain is blocking.

## R3: Legacy Prior-RED Compatibility

Support current prior-RED handoff, legacy red-result, and red-basis plus failed
observation only after current selector, test bytes, execution fingerprint, and
expected failure IDs match. Every mismatch fails closed. Terminal closure may
read predecessor RED evidence without copying it.

## R4: 8-17 Dogfood Migration

After R0-R3 pass, inventory existing 8-17 evidence as historical, regenerate
current bindings, obtain a new maintainer authorization, and dogfood S0-S3 to a
fresh terminal result. The old authorization, terminal result, resume state,
and report remain immutable.

Acceptance: the new authorization, Knowledge, Skill-input, resume state,
terminal result, and report all bind the same current candidate. Identical
replay creates no additional action or successor.
