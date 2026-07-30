# ADR-0051: Bootstrap Lineage Family And Bounded Repair Re-entry

- Status: Accepted
- Date: 2026-07-30

## Context

ADR-0041 established the repository-owned Bootstrap control plane, ADR-0045
made verifier publication recoverable, and ADR-0049 separated transport
attempts from semantic rounds. Repeated implementation-acceptance work still
used a new `changeId` or successor policy after each repair batch. That made
one unchanged acceptance target appear to have a fresh three-round budget and
caused full high-cost reviews to repeat without a corresponding change in
authority, risk, or consumer scope.

The repository is maintained by one person with AI assistance. The needed
control is deterministic lineage and bounded re-entry, not reviewer signatures
or multi-writer governance.

## Decision

Bootstrap semantic-round accounting uses a stable lineage family.

- Every new review declares `lineageFamilyId`. A consumer derives it from the
  original acceptance target and retains it across in-place repair directories,
  renamed `changeId` values, and successor history that still evaluates that
  target.
- Historical manifests without the field remain read-only compatible by using
  their existing `changeId` as the effective family. New runs fail closed when
  the family is absent.
- Legacy `changeId` history enters a target-derived family only through an
  append-only lineage-adoption record. The record binds explicitly selected
  historical run manifests and an Accepted policy authority by content hash;
  historical manifests remain unchanged and cannot be adopted by competing
  families.
- Bootstrap keeps a Git-local run registry only as a performance index. Every
  registered run and adoption is re-hashed and reparsed before use. Missing,
  stale, or malformed registered history fails closed; the registry does not
  become semantic authority.
- A family has a default budget of two semantic rounds and a hard limit of
  three. A round is consumed only when semantic reviewer execution starts;
  failed access probes and transport attempts stay in the same round.
- Round 1 reviews the minimal complete closure. Round 2 reviews the bounded
  repair delta and its reachable consumers while preserving required authority
  context. It does not rediscover unrelated repository areas.
- Round 3 requires a typed entry decision: `novel_p0_p1`,
  `authority_context_graph_changed`, or `high_risk_boundary_changed`. A clean
  or P2-only predecessor never opens another semantic round.
- A successor does not reset the family budget. After the hard limit the family
  enters `manual_pause`. Only an explicit supersede or incompatible-scope
  decision that creates a genuinely different acceptance target may derive a
  new family; a successor policy alone cannot make the old target new.
- `inspect-lineage` is the hash-bound reproducible view of consumed rounds and
  the next available round. Consumers require it even when the count is zero;
  omission cannot mean a fresh budget. Derived Artifact View, acceptance
  snapshot, and nested worktree copies are not review-history authority.
  `changeId` remains a change label, not a budget identity.

Implementation-acceptance repair re-entry requires deterministic completeness
evidence before another review route is selected.

- Quick Dev emits a non-authorizing handoff with changed files, direct
  consumers, targeted tests, validation references, generated root-cause
  callsite inventories, and controlled producer/consumer composition receipts.
- Acceptance binds present changed files by content hash and deleted files by
  explicit tombstone before choosing a review route. Every composition check
  covers a changed path, uses a declared direct consumer, and binds its receipt
  as a validation reference. All repair evidence paths must belong to the same
  hash-bound minimal review closure, with consumers and tests in their declared
  context classes.
- The Acceptance Skill audits that every discovered sibling callsite is changed
  or explicitly excluded and that each composition command succeeded. It then
  selects `deterministic_only`, `focused_repair_review`,
  `full_implementation_conformance`, or `manual_pause`.
- After two consumed rounds, a complete repair with no typed Round 3 trigger
  uses deterministic closure. The plan-local acceptance predicate remains the
  authority; neither the handoff nor the route authorizes completion.

This ADR extends ADR-0041, complements ADR-0045 and ADR-0049, and supersedes
none of them. It does not change reviewer isolation, independent P0/P1
verification, provider routing, protected handoff, commit, release, or
plan-local acceptance authority.

## Consequences

- Renaming a change or creating a successor directory no longer creates an
  unbounded high-cost review loop for the same acceptance target.
- Repair review input becomes smaller while retaining direct consumer and
  authority context needed to find regressions caused by the repair.
- A third review is exceptional and machine-explainable.
- Existing review and successor evidence remains immutable and readable.
- Consumers must carry one stable family and explicit repair-completeness
  evidence; omitting either fails closed before a new semantic launch.

## References

- `docs/adr/ADR-0041-bootstrap-review-execution-control-plane-ownership.md`
- `docs/adr/ADR-0045-bootstrap-verifier-semantic-commit-and-recovery.md`
- `docs/adr/ADR-0049-bootstrap-controller-owned-coverage-and-attempt-retry.md`
- `docs/standards/bootstrap-review-control-plane.md`
- `.agents/skills/run-phase-bootstrap-review/SKILL.md`
- `.agents/skills/run-refactor-implementation-acceptance/SKILL.md`
- `.agents/skills/vdd-execution-plan/SKILL.md`
- `.agents/skills/quick-dev-tdd-adapter/SKILL.md`
