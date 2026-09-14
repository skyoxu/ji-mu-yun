# Current Execution

Read this guide only for the operation selected in SKILL.md. Commands run from the repository root unless stated otherwise; inline paths retain their original repository/Skill-root meaning.

## Current Required Order

For CER-capable plans, use the observed behavior routing below. The RED/GREEN/REFACTOR steps apply to the missing subset; present obligations use the regression branch. Historical plans without that capability retain the mandatory TDD route.

1. Q0 recommendation-only: validate the semantic plan, current snapshot, explicit predecessors and change-impact state without running tests or writing run state.
2. Q1 preflight: validate plan/slice/candidate identity, environment probe, selector/target/fixture/cwd/argv/timeout, write sets and predecessor state.
3. Q2 RED materialization: create a frozen shell-free descriptor from VDD intent. A RED author may touch only the declared test write set and must bind a real production entry.
4. Q3 RED: dispatch the frozen descriptor through `tools/stage_pipeline.py`. `process_executor_v2.py` writes process facts; `independent_judge_v2.py` classifies those facts; runtime-edge code writes only assertion edges.
5. Q4 implementation: only a current expected-red authorizes an implementation-worker handoff. Exact changed paths must stay inside production write paths; selector/test/fixture/plan/evidence changes invalidate RED. The worker never writes evidence authority.
6. Q5 GREEN: before execution, re-read the explicit frozen RED descriptor and RED stage result; require their bound hash and selector identity to match. Then execute the same selector identity/target/fixture/assertion/cwd contract and require real nonzero test/case evidence with exit zero.
7. Q6 REFACTOR: require the same frozen RED predecessor binding plus current GREEN, allow only production paths, rerun the same selector, then apply `tools/regression_gate.py`. `standard` and `self-hosted` must consume the slice `agent-context.validation_commands`; missing context, an empty required command set, timeout, nonzero exit, or zero-case pytest regression blocks publication before REFACTOR runtime edges/stage result. `fast-ship` may omit extra regressions but never the primary selector truth floor.
8. Q7 slice-ready: `tools/coverage_predicates.py` re-reads RED/GREEN/REFACTOR edge -> observation -> receipt -> descriptor -> target/fixture bytes and proves exact Acceptance assertion coverage.
9. Execute the terminal descriptor through `tools/stage_pipeline.py`; terminal may have its own selector identity and process success alone is not completion.
10. Q8 whole-plan terminal: `tools/coverage_predicates.py` verifies one explicit hash-bound predecessor per slice, exact `(slice, Acceptance, stage)` tuple closure, terminal assertions and a freshly recomputed current snapshot before writing `implementation-complete`.

Stop at `implementation-complete`, `repair-vdd`, `environment-blocked`, or repeated deterministic failure. Never publish `acceptance-passed` here.

Current Q8 terminal inputs also retain the full frozen snapshot manifest for
Acceptance's read-only replay. Hand off the native completion result, semantic
plan and exact snapshot-root/source/base inputs; do not manufacture a legacy
plan-local terminal receipt. Acceptance rechecks runtime roots and every current
case/edge proof without running a process, then applies its own registered checks.
For a historical Q8 summary without the snapshot manifest, publish a fresh Q8
summary in a new output directory from the explicitly bound predecessors. This
is deterministic evidence evaluation, not a new RED/GREEN or model run; invalid
predecessors still require normal recovery. See `docs/acceptance-current-closeout.md`.


## Case Evidence Capability (CER-R1--R3)

Current descriptors require `quick-dev.case-contract.v1`. Bind every assertion to explicit pytest node IDs or mark its required tests with `@pytest.mark.cer_assertion('ASSERTION_ID')`; parameter instances resolve individually. The current materializer defaults to this marker mapping. See [case evidence contract](case-evidence-contract.md) for the schema, supported invocation and migration rules.

The owned collector records collection, selection and setup/call/teardown outcomes. Every required case must execute with the stage's admissible outcome; stdout assertion IDs, a stage pass or a positive count cannot fill missing proof. RED requires an actual failing AssertionError call with the bound failure ID captured from that call. Skips, deselection, xfail/xpass, setup/teardown errors, missing reports and ambiguous repeated attempts cannot satisfy the contract.

GREEN/REFACTOR must preserve the resolved RED case set as well as the frozen selector. Q4 re-reads RED case proof before handoff. Q7/Q8 re-read every assertion's case evidence, including all terminal assertion edges. Historical stage-only evidence is retained but cannot authorize current implementation or completion. CER-R4--R6 use this capability through the observed behavior routing below.

## Observed Behavior Routing (CER-R4--R6)

Read [behavior routing contract](behavior-routing-contract.md) for
current schemas, CLI actions, reuse and Deferred rules. New VDD plans project
probe intent; only controlled pytest case results assign disposition.

| Observed obligation | Required path |
| --- | --- |
| `missing` | Formal RED, bounded implementation, GREEN, REFACTOR, terminal |
| `present` | Current regression and terminal; no synthetic RED or production authorization |
| `unverifiable` | Repair/clarify the affected scope; no implementation or completion |

`author-red` now materializes a probe for a CER-capable plan. It invokes the
bounded test author when paths or current assertion mappings need authoring;
existing correctly mapped tests are reused. Then `run-probe` returns the next
action. `run-red` and `run-regression` materialize their descriptors from the
explicit probe result. A probe never counts as formal RED. Mixed slices retain
both subsets: implement missing behavior, then run present regression before Q7.
`route-behaviors` rereads explicit stage artifacts and reports the next action.

The regression stage also consumes required agent-context validation commands
under the existing profile policy. Production or dependency changes invalidate
current regression proof. A failed present behavior blocks completion and
requires a fresh probe/repair before implementation; do not change production
under a present-only route. Use a fresh run directory for invalidated evidence,
preserving the old run. Terminal descriptors freeze before Q7's snapshot, then
execute before Q8. Current probe, plan, case mappings, production/dependency
hashes and per-disposition assertion coverage are reread at closure.

Deferred rows cannot authorize skipping cases or deleting obligations. Current
blocking/external-owner prerequisites remain blocked even when their author
writes a false blocking flag. Only a fully specified internal strategy may be
resolved during implementation while keeping every proof requirement.

## Profiles

Execution profiles are `fast-ship`, `standard`, and `self-hosted`. Profiles may change scope/cost only; none may bypass real execution, selector identity, exact cover, failure classification, current snapshot or terminal truth. `self-hosted` additionally requires the detached promotion/judge contract when promotion is requested. Its detached bundle must contain external read-only `positive`, `negative`, and `mutation` fixture kinds and must exactly cover every current failure family; missing/unknown family coverage, candidate-local judge/oracle bytes, mutable artifacts, or current evidence-writer imports block promotion. This execution profile is distinct from any older VDD plan-shape profile such as `resumable`.

## Conditional .NET boundary tests through pytest

For a C# owner, retain the current `python -m pytest` CER adapter.
The RED entry guard accepts a literal `subprocess.run` argv list with explicit
`shell=False`, `dotnet test <repository-relative test.csproj>`, one exact
`--filter FullyQualifiedName=<namespace.class.method>` and `--logger trx`.
The project declares `IsTestProject=true` and references the production project.
Freeze the C# Fact/Theory source and all helpers in execution_snapshot_paths
before RED. It must call a declared production type or construct its real
`WebApplicationFactory<Program>` host and client. Dynamic command tables,
substring filters and test-local lookalikes are not admitted.

This is bounded static admission, not .NET execution or semantic proof.
The pytest case must parse fresh invocation-specific TRX, identify the exact
method and all required parameters, and assert the actual product outcome.
Build/discovery/setup/timeout/privilege failures are harness errors. Missing,
stale, skipped or inconclusive results cannot pass or supply causal RED.
Only a real bound product assertion may emit its planned failure ID.
Freeze wrappers, C# cases, helpers and selectors through GREEN/REFACTOR.
