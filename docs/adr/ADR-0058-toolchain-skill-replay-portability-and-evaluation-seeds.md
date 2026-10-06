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
