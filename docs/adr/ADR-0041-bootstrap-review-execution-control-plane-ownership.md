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
- Profile-declared formal companions, including `acceptance-inventory-attestation@1.0`, remain repository-owned Bootstrap protocol capabilities. Consumers bind and import their outputs but cannot create a competing reviewer, schema, launch authorization, or Artifact View.

The runner is an execution backend only. It does not own candidate acceptance, severity, review completion, done state, commit, handoff, or release authority. It must not become a hidden provider scheduler and must support evidence-based recovery without hidden mutable state.

Subprocess invocation uses argument arrays with shell execution disabled, an explicit environment-variable allowlist, and typed placeholders. Concurrency blocks only overlapping write sets, while freezing the Git index and detecting concurrent authority drift across the execution read set and dependency closure.

New plans formally bootstrap the protocol. Historical plans may receive read-only backfill and shadow validation only. A new run may supersede a stale run, but it starts from a fresh authority snapshot and is not itself born stale.

## Consequences

### VDD Verification Contract Projection (2026-09-05)

Repository-owned V3 workers may share implementation owner, lane, paths and
slice context. Each active obligation must nevertheless have its own Acceptance
oracle, assertions and failure intents. Splitting obligation IDs while copying
a multi-behavior oracle does not establish atomic semantic coverage. Structural
constraints name an observable artifact/boundary check and its evaluation phase;
they cannot be proved by unrelated runtime return values or assumed in Given.

The V3 repair wire format uses one exact frozen-obligation map. Each required
key contains its own proof and complete execution context. Live workers do not
author group IDs or cross-object assignments: enumerating frozen obligation IDs
did not ensure the corresponding group was actually returned. Matching contexts
remain eligible for V6 merging; this does not require one slice per obligation.
Legacy grouped caches retain strict reference and atomic-contract checks.
Malformed references and multi-obligation shared oracles remain rejected;
historical evidence is never rewritten and cache format versions stay distinct.
The existing bounded repair budget and independent V4 semantic authority remain
unchanged. V5 checks semantic edges, V6 owns partitioning, and the downstream
plan/runtime checks still establish whether the declared constraints hold.

A Governance constraint with only test-harness-failure intents guards its
matched test execution. When frozen source refs, production owners and complete
validation argv match active Product/Platform expected-red behaviors with one
unambiguous lane, V3 projects the guard onto that lane before preflight and V6.
The guard retains its oracle, assertions, failure family and terminal check;
an invocation observation is not a separate implementation environment.
Different or ambiguous execution bindings remain unchanged. V6 continues to
enforce lane, owner, dependency and write/forbidden boundaries.

V1 extraction, source-gap additions and independent atomic recall distinguish
normative targets and explicit verification duties from descriptive current
state. Descriptions of existing defects remain transition/negative-test context;
their presence in source does not require implementing or preserving them.
Explicit baseline-verification duties and temporal qualifiers remain covered.
This is a semantic worker instruction, not a keyword-based deletion rule.
Source-role contract revisions partition affected transport caches; old worker
judgments are not silently reused as fresh judgments under a changed contract.
The exact-ID partition, coverage thresholds and single recheck budget remain.

### Existing Ownership Consequences

Real-semantic evaluation supervises the public compiler CLI with an independent
whole-compile budget (3600 seconds by default, explicitly configurable). This
budget is separate from per-worker repair limits. On timeout the supervisor
terminates its owned process tree and records any cleanup failure; it never
converts incomplete metrics into success. Compiler stages and actual worker
invocations append flushed diagnostic checkpoints before and after execution.
These records are non-authoritative and contain no prompt or backend trace.
Evaluation retains the run directory, cache, progress, process logs and final
result on success or failure. Explicit repair limits propagate to the child CLI.

V4 Acceptance alignment and its independent recheck use active obligations as
their exact proof targets. Deferred/excluded records and unresolved fragments
remain visible in a separate non-active context field, without acquiring an
Acceptance/RED requirement. This does not delete or merge obligations, promote
dispositions, or replace independent source recall. The versioned input scope
changes alignment cache identity; old judgments remain historical and are not
filtered into success. Active missing coverage and misalignment still fail.

When frozen source explicitly names production owners and limits production
writes to those owners, V3 removes those exact paths from model-authored
`execution_snapshot_paths`. Quick Dev treats execution snapshots as immutable
RED test/fixture inputs; production bytes remain bound through production
owners and candidate snapshots. Other paths retain their protection. Missing
source authority is not inferred from write sets or filenames; an explicit
owner also declared as a RED artifact is a source-role conflict, not permission
to weaken the RED freeze. This projection applies to initial V3 and its existing
repair path without changing Acceptance semantics or the GREEN predicate.

- Protocol changes are made once in the repository-owned Skill and projected through compatibility adapters.
- Plan-local validators retain domain acceptance authority.
- Generic schemas cannot drift independently across plans.
- Historical evidence remains immutable; annotations and indexes are additive and reproducible.
- Reviews cannot close with an open accepted P0/P1. Every P2 must have an explicit disposition; high-risk P2 cannot be deferred, and expired deferrals block automatically.
- This ADR is superseded only when these ownership or authority decisions change. Ordinary execution plans reference it instead of creating another ownership ADR.

V3 initial generation and grouped repair receive a bounded, advisory repository
file context with content hashes. Candidate discovery supplies existing paths,
not production-owner assignments or semantic authority. Workers must inspect
source and tests and may search beyond the incomplete candidate list. Repair
reuses the initial context when present. Subject labels and future observation
logs remain invalid substitutes for production entries and RED inputs; existing
path and coverage validators retain authority. This adds no worker retry.

Shared Python Codex execution uses temporary file-backed UTF-8 stdin and output
instead of pipe communication. A worker deadline triggers process-tree cleanup
(`taskkill /T /F` on Windows, a private process group on POSIX), with at most
10 seconds for tree termination and 5 seconds for the direct child to exit.
Cleanup failures remain explicit timeout diagnostics, never successful worker
results. Neither pipe EOF nor context-manager exit may introduce an unbounded
wait. This does not extend worker budgets or authorize another semantic retry;
the outer compiler watchdog remains the independent total runtime bound.

## References

- `decision-logs/2026-07-16-bootstrap-review-self-audit-and-hardening-proposal.md`
- `docs/standards/bootstrap-review-control-plane.md`
- `execution-plans/2026-07-12-llm-review-evidence-gate-hardening/09-bootstrap-review-operator-guide.md`
