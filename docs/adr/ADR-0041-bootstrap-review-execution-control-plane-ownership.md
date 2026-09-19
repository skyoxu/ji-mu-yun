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

The CH456 formal acceptance entry forwards an explicit repair timeout override
to both real-semantic evaluation and the detached live-blind child. Each entry
records the override; omitting it preserves the existing 300-second repair
default. The live-blind 3600-second limit and completion predicates are unchanged.
An optional stop-on-failure mode writes a blocked runner summary after the first
failed prerequisite and does not run later checks or publish final completion.

V3 may reconcile one redundant missing snapshot path against the same hint's
single direct Python script command when the command file exists and the only
spelling difference is omission of its immediate parent directory. This narrow
projection requires no planned files and rejects existing snapshot paths,
multiple commands or snapshots, symlink targets, and paths explicitly mentioned
by frozen source contracts or other hint fields. It does not search the repository
for matching filenames or choose a different command. Acceptance, failure intents,
owner and write scopes remain unchanged. A hash-bound projection sidecar records
the before/after paths; raw worker output and caches remain unchanged. The normal
execution and semantic validators still run on the projected result.

Atomic recall retains the completed worker result under the exact source/index,
obligation payload and prompt identity, including results returned by the bounded
schema-repair path. Later checks of that identical input reuse the result and
recompute the normal recall gate, rather than obtain another model judgment only
because the initial transport timed out. Schema-valid source-gap and invented
findings are retained equally; this is not a passing-result cache. Changed inputs
or prompts require a new result. Hash, schema and frozen-domain validation remain
mandatory. Explicit injected fixtures bypass this run-local result store. Legacy
raw/repair caches are never scanned for a preferred judgment or retrospectively
promoted; historical failures remain unchanged.

### CH456 Practical Closeout (2026-09-07)

The maintainer accepts practical behavior/process equivalence rather than literal
reproduction of the original CH456 draft. The topic-specific supersession table
in [CH456 practical closeout](../ch456-practical-closeout.md) owns the current
interpretation of slice cohesion, optional external acceptance, deferred unseen
task generalization and historical Architecture reconciliation. Other semantic,
execution and evidence truth floors remain binding.

Critical semantic-chain, agent-context and detached structural/family mutation
checks now require complete rejection. One leaked case blocks both its metric
and the final gate even when a legacy summary reports threshold_passed=true.
Historical passing or failing evidence is not rewritten or rebound. Current
gate validation remains separate from the original live candidate evidence.
This decision adds no live run, retry, mandatory review or completion authority.

### Case Evidence Capability, Phase 1 (2026-09-07)

CER-R1--R3 extend the current Quick Dev producer, independent judge and Q7/Q8
consumers. A versioned case contract is embedded in the existing descriptor and
its selector identity; the report is embedded in the immutable process receipt.
The repository-owned pytest adapter runs the frozen selector once, recording
node IDs (including parameters), collection/selection and setup/call/teardown.
A per-run nonce, descriptor digest, stage and collector digest bind the report;
missing, incomplete or ambiguous reports fail closed. No summary-parser fallback
can issue current proof.

Assertion mappings use explicit node IDs or declared cer_assertion markers,
resolved across the collected set before deselection. All required cases must
satisfy the stage contract. RED requires a failing AssertionError call and its
scoped expected failure IDs; GREEN/REFACTOR require passing calls and the same
resolved case set as RED. Existing semantic/oracle review still owns whether
an assertion tests the intended behavior. Case identity is not semantic proof.

Q4 rejects stage-only RED predecessors. Q7/Q8 re-read every assertion edge and
its report, and rehash each mapped test file. Terminal may use its own frozen
selector. This retains existing write boundaries, snapshots, failure families
and implementation-complete ownership; it grants no Acceptance authority.
Historical receipts and CH456 closure remain unchanged. Single-process pytest
is supported; retries, parallel execution and other adapters require a later
explicit contract. CER-R4--R6 and live task validation remain separate work.

### Observed Behavior Routing, Phase 2 (2026-09-07)

The canonical VDD compiler projects per-obligation probe intent into the current
semantic bundle. It publishes no disposition or execution evidence. Quick Dev
adds probe and regression stages to its existing dispatcher and stable CLI.
Probe classification is derived per atomic obligation from the phase-1 case
report: all required cases pass means present, all satisfy expected behavioral
RED means missing, and all other combinations are unverifiable. Probe results
cannot authorize production implementation or stand in for formal RED.

For capability-bearing plans, the frozen four-stage coverage is a possible
missing-behavior path. Runtime Q7/Q8 derive the required path from the explicitly
bound probe: missing retains RED/GREEN/REFACTOR/terminal, present requires
regression/terminal. Every current obligation remains in coverage, including
mixed slices. Case mappings stay bound to the probe; production/dependency
hashes bind current regression and final proof. Extra declared regressions,
profile rules, snapshots and external Acceptance ownership remain unchanged.
Terminal materialization precedes Q7 snapshotting in the stable entry.

The existing run and immutable artifact model owns recovery. No parallel plan
state machine, auto-retry, global test discovery, new requirement type, or
mandatory governance workflow is added. Legacy bundles retain mandatory TDD;
new plans require controlled probes. Invalidated runs are preserved and a fresh
run establishes current behavior. An unverified model label has no routing
power. Static marker inspection only decides whether test authoring is needed.

Typed Deferred records remain in the same intent contract. Internal strategy
may be implementation-resolvable only with a complete observable/assertion and
write contract. Current-scope external-owner or blocking prerequisites fail
closed regardless of author-provided Booleans. Deferral cannot shrink coverage;
a scope exclusion requires the existing explicit source/scope decision.

## References

- `decision-logs/2026-07-16-bootstrap-review-self-audit-and-hardening-proposal.md`
- `docs/standards/bootstrap-review-control-plane.md`
- `execution-plans/2026-07-12-llm-review-evidence-gate-hardening/09-bootstrap-review-operator-guide.md`


## 2026-09-08: bounded Quick Dev stage recovery closeout

Current stage execution reserves an immutable run-local input binding before
starting its process and publishes a result seal only after complete stage
publication. Reentry verifies the original bytes and current inputs before
reusing a result. Incomplete or stale runs stop before process launch and retain
all history. The protocol does not manufacture completion from partial receipts.
The existing two-failure stop-loss applies at the common stage dispatcher using
explicit ordered history; no history discovery or second lifecycle is added.
Refactor checks reentry before worker invocation. Historical results without
these bindings are not silently upgraded. This decision is limited to 8-17
reentry, stop-loss wiring and CER-compatible recovery fixtures; 8-13 advanced
sharding and CH456 live acceptance are outside scope.


## 2026-09-19: reviewed-plan execution handoff repair

The canonical compiler may repair only the execution bindings of an existing
hash-bound, independently reviewed CER plan without rerunning semantic workers.
The public `--repair-quick-dev-handoff-from` mode publishes a distinct successor;
it does not overwrite the predecessor or claim that V1/V4 ran again. The repair
report binds the predecessor, reused reviews and unchanged semantic projection.
Obligations, acceptance Given/When/Then/oracles/assertions, slice membership,
production owners, terminal predicates and existing failure intents are retained.
Only executable non-Governance behavior/quality may gain a test expected-red
role. Subject rejection required by an oracle is a passing test; infrastructure
faults and governance guards never acquire implementation authority.

Dedicated planned test entries are authored by Quick Dev. Production owners
remain candidate-bound but cannot also be frozen execution snapshots. Explicit
command targets outrank prose references to fixtures. Existing test regressions
are retained with proper argv/test-runner syntax; raw diagnostic and negative
validator invocations become explicit bounded-fixture oracle responsibilities
of the bound test, not zero-exit commands or independent behavior proof.

A source byte-identity correction is permitted only if the entire current UTF-8
source text equals the ordered frozen source entries after universal newline
and outer-whitespace normalization. Every affected old/new hash is recorded;
changed text, omitted preambles or new execution metadata require ordinary
semantic recompilation. Source files and historical records remain immutable.

Normal publication, completed-plan resume, and current Quick Dev validation
reject incompatible handoffs. The deterministic gates rerun before publication.
No test execution, present/missing disposition, implementation completion, C3
approval, or Acceptance authority is created; `authorizes` remains empty.
