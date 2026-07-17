# ADR-0041: Bootstrap Review Execution Control Plane Ownership

- Status: Accepted
- Date: 2026-07-16

## Context

Bootstrap Review started as a plan-local manual review gateway. Repeated real runs proved the semantic review model useful, but process launch, artifact access, lease handling, retries, recovery, and lifecycle inspection became duplicated across temporary run helpers and a historical execution-plan directory.

A top-level router would add stateful dispatch without resolving authority. Extending historical script directories would also blur durable protocol ownership, plan-specific acceptance, and append-only evidence.

## Decision

Bootstrap Review uses a documented protocol with stateless adapters and explicit ownership boundaries.

- `docs/standards/bootstrap-review-control-plane.md` owns durable semantics, authority, lifecycle, and recovery rules.
- `.agents/skills/run-phase-bootstrap-review/` owns executable protocol, generic schemas, Artifact View, the Codex Exec runner, attempt/event records, repair closure, lifecycle inspection, and common validation tools.
- `execution-plans/<plan>/` owns contract instances, implementation-contract instances, plan-specific predicates, fixtures, and current-plan evidence. A plan-local validator remains the business acceptance authority for that plan.
- `execution-plans/2026-07-12-llm-review-evidence-gate-hardening/` is a compatibility adapter and migration fixture, not the durable implementation owner.
- `logs/` owns append-only run, attempt, review, audit, and recovery evidence.
- The external global `run-phase-bootstrap-review` Skill is a revision-bound thin route into the repository-owned Skill.

The runner is an execution backend only. It does not own candidate acceptance, severity, review completion, done state, commit, handoff, or release authority. It must not become a hidden provider scheduler and must support evidence-based recovery without hidden mutable state.

Subprocess invocation uses argument arrays with shell execution disabled, an explicit environment-variable allowlist, and typed placeholders. Concurrency blocks only overlapping write sets, while freezing the Git index and detecting concurrent authority drift across the execution read set and dependency closure.

New plans formally bootstrap the protocol. Historical plans may receive read-only backfill and shadow validation only. A new run may supersede a stale run, but it starts from a fresh authority snapshot and is not itself born stale.

## Consequences

- Protocol changes are made once in the repository-owned Skill and projected through compatibility adapters.
- Plan-local validators retain domain acceptance authority.
- Generic schemas cannot drift independently across plans.
- Historical evidence remains immutable; annotations and indexes are additive and reproducible.
- Reviews cannot close with an open accepted P0/P1. Every P2 must have an explicit disposition; high-risk P2 cannot be deferred, and expired deferrals block automatically.
- This ADR is superseded only when these ownership or authority decisions change. Ordinary execution plans reference it instead of creating another ownership ADR.

## References

- `decision-logs/2026-07-16-bootstrap-review-self-audit-and-hardening-proposal.md`
- `docs/standards/bootstrap-review-control-plane.md`
- `execution-plans/2026-07-12-llm-review-evidence-gate-hardening/09-bootstrap-review-operator-guide.md`
