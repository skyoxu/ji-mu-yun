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

V3 grouped wire, chunk recomposition and cached internal candidates apply the
same environment-aware execution-hint projection before cache admission and
execution-contract validation. Declared production owners remain writable;
missing production owners require the exact planned-file declaration in the
returned candidate. Exact source-authorized redundant fields may be projected,
but a validator cannot repair only a private copy and then return different
bytes. Raw semantic worker output and failed history remain unchanged.
V1 receives only semantic source and provenance, excluding V3-only
`execution_context_text`. Existing controller/Q2/RED ownership instructions are
planning/execution context, not new product features. The original frozen
context remains available to V3 for path, write and validation contracts;
independent recall continues to judge the actual product source. No product
obligation is removed by a keyword filter or replaced by a workflow instruction.
For table-authored inputs, V3 also receives the explicit file-level authoring
block from the same V0/V0A-frozen source file. Its source/hash provenance remains
visible in execution_context_sources; it is not another obligation source.
This prevents an individual row's V3 request from losing the common path,
write-set and validation contract stored outside that row. Per-obligation repair
retains applicable file context without changing source refs or V1 semantics.
The projection never rereads current files or supplies another file's context
as authority. Existing candidate validation, independent V4 and current runtime
production binding still decide admissibility; authoring instructions establish
no execution result or readiness.
An explicit empty-owner, all-test envelope retains its verification role across
schema repair and rollback recovery. A repair-stage label or stale rollback
field does not authorize promotion to a production writer. These projections
establish declarations only; current file existence, runtime binding and
independent V4 semantic alignment retain their existing gates and ownership.

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
Automatic handoff repair selects only executable non-Governance behavior/quality
for a new test expected-red role. Subject rejection required by an oracle is a passing test; infrastructure
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


### Explicit runtime RED role for a governance-related machine check

Requirement category and observed test outcome are separate. A Governance
requirement can include an executable independent-verification assertion.
After reviewing that concrete machine oracle, the maintainer-directed repair
may explicitly select its existing failure intent with `--runtime-red-intent`
under the canonical handoff repair mode. This appends an expected-red role
using the existing failure ID and preserves the original diagnostic intent.
It changes only the bound slices and their coverage projections, preserving
all other slice contexts. It does not automatically convert governance or
constraint families. The current CER judge still requires a real case-bound
failing AssertionError after successful setup; a marker alone is insufficient.
Human authorization, substitute Trust Approval and Consumer exception decisions
remain outside this runtime role, regardless of the requirement category.

For 08-05 S1, `FI-6AED86AC07D0` binds a unit-level check of candidate-external
trust in `candidate_workspace.py`. Its unchanged oracle requires independent
verification instead of accepting the candidate declaration. Testing that
behavior is implementable; granting trust approval is not. The original
`target-binding-failure` remains diagnostic intent, and the new role binds
`UNVERIFIED-CANDIDATE-EXTERNAL-TRUST-REJECTED` as a test assertion failure.


### Q4 requires actual production progress (2026-09-19)

An implementation worker entered after clean expected RED must produce a
content change under a declared production owner. A zero exit, prose claim,
non-production-only change or edit restored to its original bytes is not
implementation progress. The worker adapter returns task-implementation-failure
with reason no-production-change; the independent Q4 finish gate enforces the
same rule using resolver-derived changes. Failed Q4 cannot publish a GREEN
descriptor or request run-green, and the public CLI returns a nonzero exit.

This is a necessary progress gate, not proof that a nonempty patch is correct.
Real GREEN and downstream gates remain required. A no-op REFACTOR after valid
GREEN remains legal. Historical attempts are immutable; repeated failures are
not retried until a relevant input or control-plane defect is repaired.

### Bounded V3 Candidate Correction (2026-09-20)

An explicit canonical-compiler input may correct named V3 candidate contracts
when independent V4 has exposed a wrong executable binding. The input is bound
to unchanged requirements bytes, retains exact source references, and has an
empty authorization set. It is authoring input, never a worker result, review
judgment or plan-ready receipt. Unselected contracts and historical caches are
retained. Normal deterministic identity construction, V3 execution validation,
independent V4, coverage, slicing and final publication gates remain required.
The correction cannot reuse a completed plan or increase the repair budget.
Runtime expected-RED is limited to an executable assertion; C3 approvals are
not supplied or inferred by a candidate correction.

### Published V3 Contract Repair Successor (2026-09-25)

The earlier prohibition on applying candidate correction to a completed
output directory remains: published bytes are never repaired in place. A
canonical CLI successor mode may instead use one explicit plan-ready
predecessor and a distinct empty sibling directory. It validates current
source bytes, bundle identity, semantic chain, independent V4 alignment and
atomic recall before deriving the unchanged per-obligation V3 contracts from
the published bundle. It does not copy an old worker cache or reuse V4 as a
current verdict. Only explicitly named contracts can change; drift in other
Acceptance, failure-intent or execution-hint semantics fails closed. The
successor still requires fresh V4 and every downstream gate. Historical plan,
cache, Quick Dev evidence, authorization and C3 status remain unchanged. If
fresh atomic recall discovers a source gap, this successor stops at V4; it
does not silently expand V1 under an Acceptance-only correction.

### Explicit caller-session transport (2026-10-20)

The maintainer authorized an additional host-session transport for VDD, Quick
Dev and deterministic Acceptance in online workspaces. The shared backend may
publish bound pending requests for the trusted current caller and consume its
actual responses, without requiring a Codex executable or API credentials.
Requests bind repository/session, nonce, exact prompt, mode and deadline; replies
are single-use non-authorizing inputs. Native consumers still own schema,
semantic, write-set, test and lifecycle checks. This is not an adversarial
sandbox or proof of a separate reviewer process. Local CLI defaults and optional
Bootstrap/complex-recovery capability policy remain unchanged. See
`docs/workflows/caller-session-execution.md`.


### Execution preflight and transport repair boundaries (2026-10-20)

The maintainer authorized bounded VDD stability repairs after the 08-06 online
compilation and review of retained 08-05/08-24 evidence. V3 candidates now have
a non-authorizing projection through existing execution and handoff gates before
V4 Acceptance alignment. Source recall remains distinct and may precede V3.
Preview operates on copies, records diagnostics by content hash and never
changes worker inputs. Final semantic, coverage and publication gates remain
mandatory; published historical evidence is not rewritten or reclassified.

Ordinary and grouped V3 schemas permit an empty owner array only as a shape.
The shared semantic rule allows it for bounded test-only governance/constraint
guards without expected-red or production rollback scope. An ownerless product
behavior remains invalid. Pytest node selectors retain their identity in argv;
filesystem checks use the file component. Conditional failure descriptions are
not unconditional failure programs; static checks do not establish real RED.

Normal/V3-group/V4-domain/V4-source-gap transports share a bounded retry policy.
Only positively identified transient service failures retry. Environment,
unknown failures, timeout and cancellation stop without schema repair or group
fan-out. Successful malformed responses retain one-shot schema repair, and
successful exact child caches survive interruption. Provider/model defaults
and shared backend ownership remain unchanged.

Absent declared future production owners are reported as consumer warnings.
Their first-use protocol belongs to Quick Dev; this change cannot authorize Q2
production seeding or missing-import RED. Existing exact semantic-projection
handoff repair remains the reuse route. Semantic changes require fresh V4.

Evidence and limits: `logs/vdd-stability-20261020/README.md`. This maintenance
does not implement Package A, certify acceptance, enable Bootstrap or change
Phase runtime behavior.


### Explicit new-entry preparation before RED (2026-10-20)

Following the actual blocked 08-06 online trial, the maintainer explicitly
requested repair of the first-use execution protocol and another online trial.
This decision narrowly replaces the blanket ban on ALL production file creation
before RED. It does not permit implementing feature behavior before RED or
letting the Q2 test author create its own production subject.

The stable Quick Dev CLI owns opt-in `prepare-entry`. It reruns Q1 and consumes
an explicit plan/slice/HEAD-bound input containing exact missing planned owner
paths and function signatures. Its deterministic renderer can only create
Python callables returning None and empty JSON interfaces. It rejects existing
or tracked-but-deleted paths, test/frozen/forbidden paths, symlinks, unknown
fields, arbitrary bodies/data and undeclared owners before mutation. The native
non-authorizing receipt records exact generated bytes; Q2 can revalidate it.
No worker, model verdict or preparation receipt can grant implementation.

Actual importable production entries therefore exist before tests are frozen,
without supplying the requested behavior. Controlled probe and formal RED must
still observe real result-contract AssertionError cases, exact failure IDs and
nonzero case counts. Missing-import/setup/file-presence failures remain invalid.
Q2 cannot modify production; Q4 still requires the native expected-red lineage.
All normal CLI and online transports share this same native opt-in action.

A Python -B invocation and multiple exact selectors must retain the complete
slice case surface. Broader terminal/regression commands do not become Q2 test
writers' targets and remain required Q6 checks. Static file-wide marker presence
cannot substitute for selected-node proof.

This is a bounded repository-maintainer protocol, not sandbox execution or a
new lifecycle state. Historical failures and 08-06 source/semantic bindings are
preserved. The entry preparation is not Package A or Skill-standard acceptance.
See `logs/quick-dev-first-use-20261020/README.md` for tests and actual evidence.


### Source-bound atomic repair after a controlled mixed probe (2026-10-20)

The authorized online 08-06 continuation found one published obligation that
combined three missing dependency diagnostics with an already-present static
execution boundary. It also misclassified a harness failure as expected RED.
The current probe correctly stopped; no production implementation is authorized
by that mixed or invalid proof.

The existing explicit published V1 split route is source-bound rather than
hard-coded to the historical FR-6 label or exactly two outcomes. A caller may
replace exactly one active predecessor obligation with two or more distinct
active outcomes bound to the same exact current source. The route rejects
unknown/duplicate/inactive targets, cross-source records, collisions with any
predecessor obligation, stale source bytes and incomplete V3 contracts. It is
non-authorizing authored input. Independent V4/atomic recall, downstream checks
and the canonical compiler remain mandatory, and all predecessor evidence is
immutable. Unrelated obligations/contracts are retained. This is a VDD repair
capability, not a Package A product feature or permission to bypass RED.

Published predecessor admission also verifies the exact source-index identity
shape emitted by V0: ordinary indexes hash entries, while case-section indexes
hash entries plus companions, including an explicitly empty companion list.
The full declared shape must match; entries-only fallback cannot hide companion
mutations. Historical index bytes are not rewritten.

When a shared planned pytest module has been partially authored by Q2, a
published repair may admit its incomplete static mapping only if every existing
marker belongs to this same plan and exact frozen test surface. Empty mappings,
unknown markers and markers assigned only to another file remain binding
errors. This is Q2 authoring admission, not case coverage: native probe/RED,
frozen selectors, runtime collectors and Q7/Q8 still require every exact case.
No marker, file or plan string is promoted to execution evidence.

Published V3 rehydration preserves each Acceptance's own preflight metadata
through its source-bound hint, instead of recomputing it from the merged slice's
broader owners. Unselected complexity/context/verification contracts must remain
unchanged; the final drift gate is retained and semantic edits still fail.

### Narrow Runtime Role Repair (2026-10-21)

An explicit runtime-role repair retains all valid current test paths, snapshots,
planned files and validation commands. Missing behavior RED roles alone do not
authorize whole-plan test rebinding. Conflicting execution bindings still use
the existing bounded repair path and report that disposition. No role is an
observed failure or human approval. Published handoff source identities use the
producer's exact shape: entries for legacy sources, or entries plus companions
when that key exists, including an empty companion list. Both validation and
republication use the same identity calculation.

### Shared Test Surface Selection (2026-10-21)

Handoff admission checks each existing planned test file against that file's
own assertion domain; markers in the first file cannot stand in for another
file. Current CER materialization may narrow a declared pytest file to complete
literal marker-bound node IDs without importing tests. Every parameter carrying
a required marker remains selected. Unsupported or incomplete static mappings
retain the declared selector and all existing runtime gates. The frozen probe's
argv, cwd, targets, fixtures and timeout remain identical through nonterminal
stages. Required agent-context regressions remain unchanged and execute through
the existing regression gate. No unknown failure, deselected required case, or
other slice's assertion becomes RED authority.

### 2026-10-21 terminal selector correction

Recompute Q2 literal CER bindings after test authoring, before the initial probe
freeze. Preserve that exact selector through nonterminal stages. Terminal uses
the original declared frozen module selection, including unmarked regressions,
with its independent timeout. Exact-marker narrowing cannot silently reduce
whole-plan terminal coverage. Native evidence writers and Q7/Q8 gates are unchanged.

### 2026-10-21 Package A runtime profile

Package A is an ordinary static-validator implementation, not a promotion of a
new detached judge. Its final fresh implementation replay selects the standard
runtime profile at Q1 and retains all process/case, Q6 regression, snapshot, Q7
and Q8 requirements. VDD plan-shape profiles remain independent. Historical
self-hosted slice runs are diagnostic/TDD history only; they are not relabelled
as standard receipts or detached-judge promotion evidence.

### 2026-10-21 documentary guard runtime dependency closure

A pure documentary/test-only guard with no production owners has an empty
production hash map. Its exact frozen tests, fixtures, plan and runtime roots
remain required. Actual production and transitive owner dependencies still use
the existing strict hash_refs path. This neither creates an implementation
owner nor grants production-write or expected-RED authority.
