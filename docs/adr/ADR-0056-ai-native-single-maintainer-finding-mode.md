# ADR-0056: AI-Native Single-Maintainer Finding Mode

- Status: Accepted
- Date: 2026-08-02

## Context

Bootstrap Review and Refactor Acceptance serve an AI-led repository maintained
by one person. Reviewers were treating multi-maintainer races and external
requirement injection as ordinary product threats, and focused repair review
could reopen discovery without a distinct user decision. Prompt guidance alone
did not provide a deterministic enforcement boundary.

## Decision

- New Bootstrap and Acceptance routes freeze
  `maintenanceMode=ai-native-single-maintainer` and the same severity policy.
- A candidate classified as multi-maintainer concurrency or external
  requirement injection shifts P0 to P1, P1 to non-blocking P2, and P2 to
  ignored. Runtime product risk is unchanged. Bootstrap's parent CLI applies
  the shift before gate aggregation.
- Round 1 discovery is automatically eligible. Later complete discovery remains
  available only for a typed `novel_p0_p1`,
  `authority_context_graph_changed`, or `high_risk_boundary_changed` route.
- Before later discovery, the orchestrator reports its recommendation,
  confidence, expected benefit, and cost. Explicit user confirmation is recorded
  through an append-only Bootstrap CLI authorization bound to the lineage,
  predecessor, round, trigger, and Acceptance route hash. The recommendation is
  advisory: a user may explicitly confirm re-entry even when the orchestrator
  records `do_not_recommend`.
- The maintainer may instead explicitly decline a Round 2 discovery proposal.
  Refactor Acceptance may then close deterministically only when the current
  repair-completeness producer replays successfully, no novel P0/P1 exists,
  exactly one round was consumed, and the proposal was caused only by a
  repair-derived authority/context or high-risk-boundary change. The closure
  records residual-risk acceptance, publishes `acceptance-passed`, and does
  not authorize commit, release, or archive.
- `prepare`, access proof, and layer launch fail closed when finding mode or its
  re-entry authorization is absent, stale, or substituted.
- Focused repair verification covers only predecessor findings. It cannot emit
  new findings or escalation triggers; a still-broken predecessor finding
  remains blocking.
- Historical run bytes remain read-only compatible under their frozen policy.

This ADR refines ADR-0051 and ADR-0055 and supersedes their statements that a
focused verifier may originate an escalation trigger. It does not change the
three-round hard limit or independent verification of accepted P0/P1 findings.

## Consequences

- Repository-specific threat assumptions affect severity deterministically,
  not through reviewer discretion alone.
- A second discovery pass is possible but visible, justified, and explicitly
  user-approved.
- A declined second discovery pass has a narrow, hash-bound deterministic exit
  instead of becoming an acceptance dead end.
- Ordinary precise repair stays on the single focused verifier path.

## References

- `docs/adr/ADR-0051-bootstrap-lineage-family-and-bounded-repair-reentry.md`
- `docs/adr/ADR-0055-focused-repair-verification-and-lightweight-closure.md`
- `docs/standards/bootstrap-review-control-plane.md`
- `.agents/skills/run-phase-bootstrap-review/SKILL.md`
- `.agents/skills/run-refactor-implementation-acceptance/SKILL.md`
