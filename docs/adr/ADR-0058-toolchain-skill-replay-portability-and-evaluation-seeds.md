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

### 2026-10-07 Full-scope CER fixture portability

The unchanged 340-node direct scope completed on Linux at candidate
`de6e6a4b0427bc53a8dd9d03b528be075ce0e3d5` with 333 passes and seven
failures, a real native JUnit report, and unchanged source bytes and HEAD.
Six S14/S15/S18 failures were hard-coded temporary-root creation failures;
S26 required a Windows platform label even when the real child ran on Linux.
This failed result remains append-only evidence.

S14, S15 and S18 use the standard-library temporary directory selection
instead of requiring a machine-specific Windows drive. S14 discovers either
`powershell` or `pwsh` to execute the same production PowerShell verifier;
an unavailable host still fails visibly. No verifier substitute or test skip
is introduced. Frozen-byte and membership positive and negative controls stay
intact, including added, deleted and renamed historical members.

S26 retains its selector, assertion identity and real fresh replay. Its
platform declaration must match the platform that actually executed the child.
A Windows execution still requires `win32`; a Linux execution requires
`linux`. Linux success is not local Windows verification. No child platform
label is spoofed and no execution output is normalized to claim Windows.

Required Python schema and PowerShell runtimes and immutable Git inputs are
execution prerequisites, not authority inputs. Their actual versions and
preparation failures are recorded separately. Native execution stays bounded
at 60 seconds and 8 MiB, and the direct per-node budget stays 300 seconds.
All original 340 selectors remain selected, with no skip or xfail. C3 stays
OPEN and direct test results grant no formal Acceptance or Trust Approval.

### 2026-10-07 Windows process lifetime and closure traversal repair

The native Windows replay of source `12e37e9fd2b543ba66e8bebb07bd66756292bf41`
completed 318 of the original 340 nodes, recorded 54 unique failing nodes and
exited with `0xC0000005`. Its evidence is preserved in
`logs/08-05-real-skill-replay/observable-verification-20261007T150204Z-ec03037f`.
It is unsuccessful; the final active S7 node and 22 unfinished nodes have no
native JUnit result. Linux success does not supersede this Windows result.

Windows native transports and the direct supervisor now create an unnamed,
non-inheritable Job Object with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`. The exact
Popen child starts with `CREATE_SUSPENDED`, joins the job, and only then resumes
its initial thread. All kernel handles have explicit pointer-width signatures;
Toolhelp selects only a thread owned by the launched PID. Assignment/resumption
errors fail closed. No breakaway flag is enabled. Nested jobs require Windows 8
or later. Job termination waits for active descendants to drain before closing
inherited transport files, including after a normal leader exit. It contains
descendants after the leader dies, which PID-based `taskkill /T` cannot ensure.
The non-Windows transport also drains its owned process group on normal exit.
These lifetime guarantees do not claim an arbitrary-code security sandbox.

Dependency closure traversal indexes directory membership and repeated import
lookups only within that invocation. Root containment is resolved once per
enumeration. The next invocation rebuilds these indexes and rereads/hashes all
selected bytes; new/deleted modules, owner resources, changed imports and trust
drift remain observable. No closure, trust result, manifest or execution result
is cached. The independent S2/S4 package digest oracles retain equality checks
and order repository-relative names by POSIX UTF-8 bytes, matching Git identity
instead of Windows case-folded Path ordering.

CER package replay parents use the owned file-backed transport and the existing
180-second integration ceiling. Matrix parents use a 90-second harness ceiling;
other validation calls remain finite. The native child and aggregate Matrix
ceilings stay 60 seconds and 8 MiB, and the direct per-node ceiling stays 300
seconds. No test body, assertion identity, selector, skip or expected verdict is
removed. S19 uses the bound interpreter instead of selecting another runtime.

The Windows fatal report shows a wait frame and a periodic trace cut off during
stack dumping. This does not prove the access violation originated in either
the wait or CPython's diagnostic thread. Replace the recurring C-level
`dump_traceback_later` watchdog with periodic Python frame snapshots; join the
sampler before closing its file. Pytest's fatal exception handler remains
enabled. This mitigates the known class of concurrent frame-walking faults
without declaring this crash resolved before another native Windows run.
Primary references: CPython issues
[140815](https://github.com/python/cpython/issues/140815) and
[158200](https://github.com/python/cpython/issues/158200), and Microsoft's
[Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)
and [ResumeThread](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-resumethread)
contracts.

The direct verifier records per-process diagnostic start, native exit or
unsuccessful termination events with actual PID, parent PID, command, cwd,
budget and elapsed time. Each process has a fresh append-only file, so nested
writers cannot overwrite another process's record. Diagnostic command fields
are bounded and marked if truncated; stdin and credentials are never logged.
The explicit diagnostic directory is propagated in the sanitized environment
and included in its binding. These diagnostics grant no execution, trust or
Acceptance authority. All prior evidence stays unchanged. C3 remains OPEN and
Acceptance remains blocked until the required native Windows evidence exists.
