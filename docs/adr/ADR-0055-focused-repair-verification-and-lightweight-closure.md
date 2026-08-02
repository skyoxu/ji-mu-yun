# ADR-0055: Focused Repair Verification And Lightweight Closure

- Status: Accepted
- Date: 2026-08-02

## Context

ADR-0051 bounded repair re-entry, but its Round 2 implementation still reused
the three discovery layers. A precise repair therefore paid almost the same
semantic cost as the initial review. P2 disposition also required a complete
authority and process sidecar chain for routine deterministic closure, and the
strict Quick Dev TDD adapter was sometimes selected for inputs that did not
contain its required implementation contract.

Historical Bootstrap runs and the accepted 2026-08-01 model-routing target
must remain replayable under their frozen profiles and envelopes.

## Decision

New implementation-acceptance lineages use an additive focused repair lane.

- Round 1 remains a complete review with Blind Hunter, Edge Case Hunter, and
  Acceptance Auditor. Accepted P0/P1 findings still require the existing
  independent verifier.
- After a complete Round 1 P0/P1 repair, deterministic repair completeness,
  targeted tests, callsite inventory, and composition receipts run first.
- With no repository-derived escalation trigger, Acceptance selects
  `focused_repair_verification`. Bootstrap then runs exactly one independent
  `focused_repair_verifier`, bound to the predecessor findings, repair
  mappings, changed paths, direct consumers, tests, and validation receipts.
- `focused_repair_verifier` is a repair verifier, not a discovery reviewer and
  not the gate-after-discovery `independent_verifier`. Its output carries no
  acceptance, commit, release, or handoff authority.
- A novel P0/P1, authority/context graph change, or high-risk boundary change
  selects `full_implementation_conformance`. Unknown or incomplete trigger
  evidence fails closed. A focused verifier that reports one of those facts
  also routes the next action to a complete review.
- A successful focused verification closes the repair semantically without
  creating a second three-layer discovery run. The lineage records the focused
  verification separately from full semantic-round accounting.
- New P2-only closure may use `bootstrap-p2-closure.v2`: one hash-bound bundle
  covers the exact accepted P2 set and deterministic evidence. Fixed and
  refuted findings require current successful validation. Normal-risk deferral
  requires owner, expiry, non-impact evidence, recheck evidence, and trigger in
  the same bundle. V2 evidence binds the current review, input, candidate,
  authority revision, production time, and a controlled success predicate.
  High-risk P2 uses the v1 controlled closure path and cannot enter v2.
  Stored v1 disposition chains remain readable and are never rewritten.
- Acceptance imports a focused result only by repository-relative Bootstrap
  run directory and canonical producer replay. Caller-supplied envelope bytes
  cannot establish focused closure.
- Quick Dev first classifies an explicit input as `standalone_requirement`,
  `strict_tdd_plan`, `verified_compact_vdd`, or `invalid`. Only a schema-valid
  implementation contract selects the strict adapter. Compact status requires
  verified VDD state and bindings; absence of a contract alone is not compact.
  Every executable lane reuses the existing four-class model classification.

New profiles and schemas are additive. Existing profile revisions, finalized
envelopes, and historical run bytes remain governed by their frozen contracts.
This ADR extends ADR-0051 and ADR-0054 and supersedes none of them.

## Consequences

- Ordinary precise repair needs one semantic child instead of three discovery
  children, while risky repair still escalates to the complete review.
- Repair verification has its own typed evidence and cannot be confused with
  discovery-gate verification.
- Routine P2-only closure is materially smaller without weakening exact-set,
  freshness, expiry, or high-risk rules.
- Quick Dev compatibility improves without weakening the strict TDD adapter.
- Protocol consumers must distinguish full rounds, focused verifications, and
  deterministic closures when reconstructing lineage.

## References

- `docs/adr/ADR-0051-bootstrap-lineage-family-and-bounded-repair-reentry.md`
- `docs/adr/ADR-0054-refactor-acceptance-manual-pause-closure.md`
- `docs/standards/bootstrap-review-control-plane.md`
- `.agents/skills/run-phase-bootstrap-review/SKILL.md`
- `.agents/skills/run-refactor-implementation-acceptance/SKILL.md`
- `.agents/skills/bmad-quick-dev/SKILL.md`
- `.agents/skills/quick-dev-tdd-adapter/SKILL.md`
