---
name: quick-dev-tdd-adapter
description: Implement or resume an explicit VDD execution plan through real RED, bounded GREEN, REFACTOR, deterministic slice-ready coverage, and whole-plan terminal validation. New Chapter 4/5/6 plans use the canonical evidence pipeline; historical implementation-contract.v1 plans are compatibility inputs only.
---

# Repository Maintenance TDD Adapter

Use this Skill only for an explicit plan file or plan directory routed to `strict_tdd_plan`. It is implementation authority for the TDD lifecycle only; it is not review, acceptance, commit, PR, release, or archive authority.

The parent Quick Dev router owns lane selection. Reject standalone requirements, compact inputs, missing plan contracts, schema-invalid inputs, and any attempt to fall back to Stock BMAD Quick Dev after this adapter has been selected.

## Current And Legacy Plan Routes

Determine the plan generation before executing anything:

| Input | Route | Runtime authority |
| --- | --- | --- |
| `vdd.semantic-plan-bundle.v1` / Chapter 4/5/6 current plan | current | `tools/current_lifecycle.py` + `tools/coverage_predicates.py` |
| historical `implementation-contract.v1.json` without the current semantic bundle | compatibility | legacy router/loop may inspect, project, or route repair only |
| standalone requirements or missing contract | reject | none |

For a current plan, never use `loop_plan_directory.py`, `run_slice_lifecycle.py`, `stage_command.py`, a plan-local combined writer, `canonical_lifecycle.py`, or `evidence_pipeline.py` as completion authority. Historical evidence is append-only compatibility input and may be reused only after an explicit current projection proves all required identities.

Before current execution, read [tdd-run-protocol.md](references/tdd-run-protocol.md), [implementation-backend-contract.md](references/implementation-backend-contract.md), and [evidence-and-freshness.md](references/evidence-and-freshness.md).

## Phase Service State And Governance Mode

Resolve governance before reading governance-owned state. `PHASEA_SERVICE_STATE` is `development|test|production`; unset means `development`. `JIMUYUN_GOVERNANCE_MODE` is `auto|on|off`; an explicit CLI mode wins.

`auto` disables heavy governance in development and enables it in test/production. When disabled, do not require or create plan reports, frozen knowledge lineage, Skill-input attestations, source-freeze/conformance, external semantic review, candidate binding, or implementation authorization merely to enter TDD.

Governance mode never disables the truth floor: explicit plan semantics, safe paths, shell-free execution, real RED, same-selector GREEN/REFACTOR, exact assertion coverage, current-byte lineage, current snapshot, append-only evidence, deterministic failure classification, stop-loss, or terminal validation.

## Current Required Order

For every new Chapter 4/5/6 plan, use this order:

1. Validate the VDD semantic-plan bundle before any expensive action. V5 must contain only pre-slice semantic cover; V6 partitions slices; V6A binds the exact ordered `stage_scope=["red","green","refactor","terminal"]`. Runtime facts in VDD output route `repair-vdd`.
2. Run Q0 recommendation/preflight without process execution or state mutation. Resolve and record the actual launcher/interpreter/test-runner environment; exact Python/pytest versions are not universal gates.
3. Materialize a shell-free RED descriptor from the VDD failure intent. Target refs, fixture refs, assertions, cwd, timeout, candidate identity, and selector must be explicit.
4. Execute RED through `tools/current_lifecycle.py`. The executor writes only `process-receipt.v2`; the independent judge writes only `observation.v2`; the runtime-edge validator writes only runtime assertion edges. A timeout, zero-case/harness result, repo noise, wrong failure, or unexpected green cannot satisfy RED.
5. Only after clean expected RED, allow implementation changes inside the declared production write set. Recompute exact Git delta; a selector/test/fixture/plan/evidence mutation invalidates the RED lineage.
6. Execute GREEN and REFACTOR through the same current lifecycle. They must reuse RED selector identity, target refs, fixture refs, assertion IDs, and cwd. Only successor/run/stage identity may change.
7. Run Q7 through `tools/coverage_predicates.py`. `slice-ready` must re-read RED/GREEN/REFACTOR edge→observation→receipt lineage, current target/fixture bytes, and prove the complete assertion-ID set for every active Acceptance. Extras, duplicates, missing assertions, selector drift, candidate drift, or stale snapshot fail closed.
8. Execute the terminal descriptor through the current lifecycle. Terminal process success alone is not completion.
9. Run Q8 through `tools/coverage_predicates.py`. Supply one explicit hash-bound `slice-ready` predecessor per partitioned slice. Q8 verifies terminal assertion coverage, same-selector identity, the exact `(slice, Acceptance, stage)` tuple universe, current edge lineage, and the current snapshot again before writing `implementation-complete`.
10. Stop at `implementation-complete`, `repair-vdd`, `environment-blocked`, or repeated deterministic failure. Never publish `acceptance-passed` here.

## Evidence Ownership

| Artifact | Sole current writer |
| --- | --- |
| descriptor/run orchestration | Quick Dev |
| process receipt | executor trust zone |
| observation/classification | independent judge |
| runtime assertion edge | runtime-edge validator |
| slice-ready | Q7 coverage predicate |
| implementation-complete | Q8 terminal predicate |
| acceptance-passed | external Acceptance Skill |

Evidence writes are immutable create-if-absent. A current writer must never overwrite an existing different artifact, infer a predecessor from filename order, or search for the latest successful run.

Process receipts contain process facts only: actual argv/cwd, timestamps, attempts, test executions, cases, exit/timeout, output hashes, candidate/descriptor/target/fixture hashes, profile identity, and executor identity. Producers do not pre-fill semantic pass/fail.

Observations separate `evidence_state`, `verification_outcome`, `failure_family`, and deterministic `failure_id`. `expected-red` is a failed process observation that authorizes implementation only when it matches the declared failure intent and all truth-floor predicates.

## Snapshot And Invalidation

The current snapshot has exactly eight runtime root kinds:

`candidate_tree`, `plan`, `contract`, `descriptor`, `fixture`, `source`, `validator_judge`, `plan_state_transition`.

Architecture registries, memlogs, spine hashes, review records, candidate bindings, authorizations, and ordinary governance documentation are excluded unless a named product/execution contract explicitly adopts their semantics.

Reject absolute/escaping paths, symlink/junction escape, unknown roots, stale hashes, and changed or untracked files outside the declared runtime roots. Do not use glob, mtime, or latest-success inference for current authority.

Invalidation follows semantic impact: selector/fixture/target/source changes restart from RED; production-owner changes rerun at least GREEN/REFACTOR and restart RED if failure semantics changed; compiler/validator/judge/predecessor changes invalidate their dependent evidence. When uncertain, rerun the stricter closure.

## Failure And Stop-Loss

At minimum distinguish `semantic-contract-gap`, `expected-red`, `unexpected-green`, `task-implementation-failure`, `test-harness-failure`, `target-binding-failure`, `repo-noise`, `timeout-no-observation`, `repeated-deterministic-failure`, and `artifact-integrity`.

Classification comes from current process evidence. Repeating an unchanged deterministic fingerprint twice routes `repair-vdd` or `stop`; do not keep retrying the same inputs. Unexpected green requires regression/current-behavior proof or VDD repair, never direct implementation.

## Implementation Backend Boundary

The implementation worker may change only declared production paths after expected RED. It must not modify the selector, fixture, Acceptance, plan contract, historical evidence, or terminal predicate to manufacture GREEN.

Model routing remains deterministic and non-authorizing. Select the highest applicable class: `architectural`, `complex`, `normal`, or `small_mechanical`. Unknown/contradictory facts are blocked `complex`. A user override may upgrade but not downgrade the detected class. The adapter does not select a provider or make backend text authoritative evidence.

## Governance-Enabled Extras

When governance is enabled, existing repository policy may additionally require target-plan reports, frozen knowledge verification, Skill-input receipts, external review, candidate binding, or implementation authorization. These are supplemental governance inputs and must never replace RED/GREEN/REFACTOR/current-snapshot predicates.

For P0/P1 repair handoff, preserve the exact baseline/candidate manifests, changed files, direct consumers, targeted tests, validation refs, root-cause callsite inventory, and composition receipts required by [repair-review-handoff.md](references/repair-review-handoff.md). This Skill does not launch Bootstrap Review or decide Acceptance scope.

## Knowledge Consumption

When governance is enabled and the plan declares frozen knowledge context, verify its accepted paths and hashes before RED. Do not expand the read set or silently replace a stale source. A reconstructible freshness change routes through the VDD-owned refresh path; an unreconstructible mismatch routes `repair-vdd`.

When governance is disabled, skip governance-only freshness receipts and consume only explicit plan source paths. Governance-byte drift alone must not invalidate runtime TDD evidence.

## Legacy Compatibility

Legacy plan tools may inspect historical v1 state to decide whether it can be projected or must be repaired. They may not emit current `process-receipt.v2`, `observation.v2`, runtime-edge v2, `slice-ready-result.v2`, or `implementation-complete-result.v2` unless execution has actually entered the current pipeline and revalidated all current identities.

Never update historical failed/review evidence in place. Preserve it and create a new successor or compatibility projection with explicit predecessor refs.

## Version Currency Commit Gate

This Skill is not commit authority. If implementation changes a version-sensitive external SDK/framework/CLI/language API, verify documentation for the repository-pinned target version before proposing a commit. Repository-owned code, fixtures, documents, or stable standard-library behavior do not require a network lookup solely for this gate.

Documentation lookup is implementation context only; it never replaces TDD evidence or Acceptance.

## Boundaries

- Use structured argv with `shell=false`; reject raw shell commands.
- Require real target/fixture files and repository-contained cwd.
- Preserve same selector semantics through RED→GREEN→REFACTOR→terminal.
- Require nonzero executed cases for successful lifecycle stages.
- Never let SUT/backend/model text write or authorize evidence.
- Never let governance artifacts become runtime truth by default.
- Never use plan status strings or artifact existence as completion proof.
- Never invoke Stock BMAD Quick Dev as authoritative fallback after strict routing.
- Never publish acceptance, commit, PR, release, or archive authority.
