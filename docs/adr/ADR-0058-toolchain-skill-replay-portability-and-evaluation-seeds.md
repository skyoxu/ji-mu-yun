# ADR-0058: Toolchain Skill Replay Portability and Evaluation Seeds

Status: Accepted

## Context

Historical Skill validation records contain machine-bound validator paths. Future
replays need a repository-owned entrypoint with bounded capability resolution,
detached probes, and non-authorizing receipts.

## Decision

Use `scripts/sc/skill_package_replay.py` with the checked-in capability
descriptor. The descriptor resolves only the declared validator root and the
replay output remains `authorizes: []`. Historical evidence is referenced by
hash and is never rewritten or promoted to a quality baseline.

## Consequences

Compatibility and evaluation artifacts can be replayed on another checkout
while preserving the historical 2026-08-01 bytes and lifecycle ownership.


## 2026-10-06 Bounded Execution Binding Repair

The existing decision now uses child-process read observations rather than
parent-side enumeration as its target witness. Both detached Probes execute at
the same copied location; only the declared JSON defect changes. A negative
Probe must produce its frozen defect diagnostic. Infrastructure failures do
not qualify as rejection evidence.

Existing validator content, descriptor, independent source and owning resources
are checked against an immutable Git input outside the evaluated change. Local
imports expand the source closure to a fixed point. Whole owner directories
include resources not reached by a Probe. The default existing-validator input
is commit `e289d7d3f8572595ca28c498adc798d1fa2a2bf7`; test fixtures may supply an
independent pre-change Git input through `TC_D1_TRUST_COMMIT`. That input is a
content binding, not a product-scope approval or an alternative-validator Trust
Approval. Joint validator/source/descriptor drift fails closed. C3 remains OPEN.

Current Matrix execution uses `jimuyun.stable-candidate-replay-matrix.v3`. Stable
has an explicit immutable Git commit and complete subject bindings. Candidate
must contain an executable AST change, not a renamed folder or comment. Each
subject executes its own package replay entry and an independent native
scenario process. The six scenarios exercise valid and invalid packages,
historical machine-bound limits, actual contamination and repair, an actual
read-set collision and repair, and a real closed policy/index gap and repair.
Legacy v2 inputs remain historical and non-promotable; prepare new v3 inputs
under a new repair/evidence directory without rewriting old inputs.

The Consumer Manifest reconciles actual Python call surfaces and known native
command factories. It includes both package checks declared by Knowledge
workflow integration. Their bounded adapters execute only the declared package
checks, not the unrelated full Knowledge workflow. Freeze each interface,
target and dependency before route evaluation. Capture Prior Route from the
immutable pre-change input, then execute enable, disable, rollback and re-enable
for every Consumer and applicable valid/invalid fixture. Required failures,
wrong defect diagnostics and missing effective target reads invalidate replay.

The wrapper snapshot codec is `jimuyun.skill-package-current-snapshot.v2`.
File, directory, absence and inline manifest identities are explicitly typed.
It binds current Git identity, repository sources/resources, Consumer surfaces,
validator source, Python executable/stdlib and the sanitized child environment.
Fresh replay reconstructs every bound candidate file before execution and
compares semantic outcomes and coverage, not only a target hash. This wrapper
snapshot does not replace Quick Dev, Skill-input, Phase or user-sandbox current
state or lifecycle ownership.

Outputs are captured as UTF-8 while preserving native CRLF bytes, with isolated
Python validators, finite time/output budgets and append-only new evidence.
Neither replay nor archival preflight publishes Acceptance or authorizes any
later state. Old Q7/Q8 and failed evidence are preserved. A repaired candidate
requires new current evidence before formal Acceptance can consume it.

## 2026-10-06 Native Contract Integration Repair

This section supersedes the earlier environment-based test-input mechanism.
Production trust stays pinned to the existing-validator commit above. A different
`TC_D1_TRUST_COMMIT` value is rejected; setting an environment variable is not
independent Trust Approval. This variable is not forwarded to child processes.
Isolated tests patch their fixture authority in test code and copied test
entrypoints only. Their private Git tag is not a production configuration API.
C3 remains OPEN and no alternate approval route is introduced.

A Probe's `input.target` is the requested logical package. Its `actual_target`
and `read_witness` come from the native child observation, including the actual
detached location. Requested and detached targets must not be conflated.
`replay_identity` is the observed package identity, preserving the existing
Consumer contract without inventing an independent inspection result.

Rollback reports one baseline-observation group per frozen Consumer and retains
each applicable fixture's command, process, reads, exit, verdict and diagnostic.
Consumer counts and fixture counts are separate. Every expected fixture must be
present exactly once and reproduce its captured Prior Route behavior; missing
negative fixtures cannot pass through a positive Consumer count. Aggregate
success means matched postconditions, not that negative commands returned zero.

Native v3 Matrix execution honors declared aggregate time/output bounds, capped
by the adapter's 60-second and 8-MiB ceilings. Both wrapper and scenario processes
consume the remaining aggregate budget. Budget exhaustion and infrastructure
timeouts remain unsuccessful terminal states. Contract refusals never claim
execution. Stable and Candidate source identities are recomputed after native
execution and must match their independently frozen pre-execution bindings.

Current CER selectors retain their assertion identities but consume the native
v3 input and real Consumer/Probe contracts. Historical Matrix documents, Q7/Q8,
PRD, Spec and execution-plan contracts remain unchanged. Targeted unit validation
does not establish Windows support or current Acceptance eligibility.

### 2026-10-06 Windows transport and binding repair

The existing validator's immutable owner membership is a set of exact,
case-sensitive repository-relative POSIX paths. Enumeration order is not a
membership change. Directory, package, dependency and standard-library identity
manifests use literal UTF-8 path ordering, independently of Windows Path
case-folded ordering. Git owner paths are read as NUL-delimited raw names so
quoted non-ASCII output cannot become a false dependency change. Real path
additions, removals, case-only renames and byte changes still require the
existing independent Trust Approval gate. C3 remains OPEN; this correction does
not approve any changed validator, capability or Consumer exception.

Prior Route materialization reads regular immutable Git blobs in bounded
object batches. Working-tree and archive EOL conversion, export attributes and
global checkout settings cannot rewrite those bytes. Symlinks and submodules
are refused; executable blob modes are preserved where supported. Fresh replay
still reconstructs the frozen candidate inputs, executes the real child and
requires exact semantic verdict, coverage, inspected identity and snapshot
agreement. No output normalization or relaxed comparison is introduced.

Native v3 Matrix input bindings are checked before subject execution. Copied
actual input bytes invalidate the aggregate even under different paths or
case labels; refusal names all conflicting case IDs and does not claim an
unexecuted control passed. Current CER positive controls execute the native
v3 Stable and Candidate scenarios; legacy v2 inputs remain non-promotable.
Structured target refusals remain unsuccessful, non-authorizing receipts.

CER test harnesses integrating parent lifecycle checks and a fresh child allow
180 seconds for that multi-process integration. The adapter's native child
execution and aggregate Matrix time/output budgets remain unchanged at 60
seconds and 8 MiB; a harness deadline cannot turn a timed-out execution into a
success. The original 60-second outer-fixture timeout is preserved as direct
failure evidence.

The raw local Windows failure evidence at commit
`080005d24ebae015425a0e61e9f9e89f1366d80f` and earlier Q7/Q8 records stay
unchanged. Direct Linux regression evidence is append-only and does not grant
Acceptance authority or replace local Windows verification.

### 2026-10-06 Direct verification observability

An interrupted pytest process without JUnit is not a pass. Direct verification
uses `scripts/sc/verify_skill_replay.py` to preserve the requested scope and
collect its exact node manifest before execution. Its explicit progress plugin
only observes collection and setup/call/teardown reports. It must not deselect,
skip, rewrite outcomes or bypass fixtures. Successful direct validation needs
every collected node and all three actual phase reports, a zero session exit,
no skips or xfail outcomes, and unchanged source bytes and HEAD. It grants no
Acceptance, Q8, scope, Trust Approval or Consumer exception authority.

The supervisor keeps native stdout/stderr, an append-only event stream, periodic
console heartbeats and timed pytest-parent stack dumps. A 300-second default
per-test/startup/idle supervisor deadline stops its own launched process tree
and writes an unsuccessful result with the active node and phase. Operator
interruptions also remain unsuccessful. It never fabricates native pytest
JUnit after a forced stop. Windows cleanup targets only that root PID with
`taskkill /T /F`; POSIX cleanup targets only its newly created process group.
Native child and aggregate Matrix budgets remain 60 seconds and 8 MiB.

Default scope is the two replay test files plus `tc_d1_cer`, currently 340
collected tests. Broader scopes must be explicit repository toolchain selectors
in a scope JSON file; an optional expected count rejects scope mismatches before
execution. The reported r2 count of 587 cannot be silently replaced with 340.
Third-party pytest auto-loading and environment selector/plugin injection are
disabled for this deterministic entry; missing required fixtures/plugins fail
visibly. Source and failures stay separate from formal workflow state.

Closure performance memoization caches only exact-byte syntax and repeated
filesystem queries within one traversal. A subsequent traversal rebuilds its
file index and rehashes actual resources. New, deleted and changed imports must
remain visible. Whole-owner resources, ambiguous local imports, fixed-point
closure and immutable Git trust verification remain unchanged; neither a
Probe result nor a prior trust verdict is cached.

### 2026-10-07 Replay computation and process ownership repair

The Windows fixed-source verification at candidate
`69bb7f87e28a67ee7a017d805088e2ecff7d5d35` ended unsuccessfully at S17 after
46 completed nodes. Seven earlier call failures and seven setup errors are
also failures, not completed positive coverage. The original stdout, events,
stacks, process result and missing native JUnit remain unchanged.

Reuse immutable syntax analysis by exact source bytes across Candidate, Prior
Route and fresh-checkout locations. The bounded cache holds only import names
and call-site line numbers. Every invocation still reads current bytes,
enumerates the full owning resources, computes current identities, rejects new
undeclared call surfaces and performs immutable trust checks. No dependency
closure, manifest, snapshot, read witness, execution result or trust verdict is
cached. A one-pass syntax analysis preserves the existing import/alias/native
call selection semantics.

Native commands use file-backed UTF-8 transport with unchanged raw newline
bytes, a 60-second execution ceiling and an 8-MiB aggregate output ceiling.
Output exhaustion is observed while the child runs. Timeout or interruption
reaps the owned process tree rather than only its leader. Windows uses the
existing PID-scoped `taskkill /T /F` mechanism. POSIX cleanup includes nested
process groups in the launched ancestry; Linux PID namespace and start-time
identities prevent mixing container-local IDs with host `/proc` IDs. This is
bounded Python transport, not an arbitrary-binary OS sandbox.

CER integrations of parent lifecycle checks plus fresh child execution use the
same file-backed transport with their existing 180-second outer ceiling;
Matrix fixtures retain their 90-second harness ceiling. These are harness
deadlines, not extensions of native or aggregate Matrix execution budgets.
S17 and source-identity harnesses now have the same finite parent deadline.
S17 launches the active bound Python executable rather than reselecting a
runtime through the Windows launcher. All original assertions and selectors
remain, with no deselection, fake execution or relaxed semantic comparison.

The direct verifier writes each failed report's bounded diagnostic immediately
to the event stream, marking truncation explicitly. A later interrupted test
cannot erase all preceding error details by preventing pytest's final summary.
Its POSIX supervisor also handles nested owned groups. Historical failures,
Q7/Q8, plans and capability authority remain unchanged. C3 stays OPEN;
successful direct validation is not formal Acceptance approval.
