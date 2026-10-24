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

## CER handoff compatibility

Current preflight and route validation reject a production owner that is also
a frozen execution snapshot, a missing authorable primary pytest entry, and
an executable behavior without a legal expected-red role. Explicit argv test
targets take precedence over fixture names mentioned in selector prose. A
planned test path may be absent until Q2; absence is not an observed RED.

Read `handoff-repair.v1.json` when consuming an execution-only successor. Start
a fresh current run because the plan/selector identity changed. Prior slice
receipts remain historical. Author every exact assertion mapping and preserve
its independent oracle, including fixture-based replacement of old raw CLI
commands. Existing guard failures keep their non-authorizing family.

## Q4 no-production-change failure

After expected RED, the implementation worker and Q4 finish gate both require
an actual content delta under a declared production owner. No change, restored
bytes, or changes only to other allowed paths yield task-implementation-failure
(reason no-production-change), a nonzero CLI exit, and no GREEN descriptor.
Do not proceed to run-green or retry the same unchanged attempt. Retain its
evidence and resolve the worker/control-plane cause before a fresh run.
No-op refactoring of already-GREEN behavior is still permitted.


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


## First-use entry preparation

ADR-0041's 2026-10-20 first-use decision adds an explicit pre-Q2 action for new
production entries. This narrowly supersedes the previous blanket prohibition
on pre-RED production entry creation. Ordinary feature implementation still
requires real expected RED; Q2 remains test-only. No action automatically opts
in or derives permission from a missing import.

After Q1, author `quick-dev.first-use-contract.v1` with exactly `schema`,
`plan_sha256`, `slice_id`, the actual checked-out `source_commit`, and `entries`.
Each entry has `path` and `exports`. A Python export has `name`, `parameters`
(required positional names) and `keyword_parameters` (names defaulting to None).
Only deterministic `def name(...): return None` bodies are generated. A JSON
entry has `exports=[]` and always generates `{}`. These are deliberately
unimplemented interfaces, not accepted policy/schema or product behavior.

```text
python -B scripts/quick_dev/run.py --plan <plan> --slice <slice> --action prepare-entry --first-use-contract <input.json> --out logs/<run>/entry-prepared.json
python -B scripts/quick_dev/run.py --plan <plan> --slice <slice> --action author-red --first-use-receipt logs/<run>/entry-prepared.json --run-dir logs/<fresh-run>
```

The native preparation action reruns Q1, checks the plan hash, slice and actual
Git HEAD, and requires every entry to be an exact member of production owners,
allowed writes and planned new files. Frozen tests/fixtures, forbidden paths,
existing paths (including tracked-but-deleted files), symlinks, test paths and
other file types are rejected before creation. There is no overwrite, arbitrary
source body, candidate-supplied JSON data, implicit dependency installation or
model call. Partial filesystem failure creates no success receipt; preserve
those bytes and repair explicitly rather than overwriting them.

The receipt is non-authorizing and records exact generated hashes. Supplying it
to Q2 rechecks the generated bytes before authoring. An exact repeated prepare
can reuse its original receipt; drift blocks. A source commit change requires a
new first-use decision, not relabeling the old receipt. Normal Q2 write checks
continue to exclude production, and probe/RED bind the resulting candidate and
frozen tests through the existing case collectors and independent judge.

Tests must call the real prepared entry and assert its required result. A None
return may expose a genuine unmet result contract; it does not count as RED
without actual bound AssertionError cases and failure IDs. Missing imports,
setup errors, unconditional failures, fake implementations and file-existence
assertions remain invalid RED. Q4 remains the first feature-implementation step.
The entry receipt cannot satisfy Q4, Q7, Q8 or Acceptance.

Current stage selection also recognizes Python `-B`. Combine compatible pytest
commands only for frozen snapshot files; broader agent-context commands remain
required Q6 regressions. An assertion marker elsewhere in the same file does
not prove it belongs to a selected node. Full-file selectors subsume duplicate
node selectors from that file. Case evidence still checks actual selection.

## Literal shared-module selection

Current CER authoring may resolve complete literal assertion markers to exact
pytest node IDs inside the declared file/node scope, without importing tests.
All required parameter instances stay included. Unsupported mappings retain the
original declared selector; they never become inferred case proof. Nonterminal
stages reuse the frozen probe inputs. Agent-context commands still run as
required Q6 regressions. Use `--worker-timeout-seconds 300` when the plan requires
a 300-second targeted descriptor; terminal remains independently bounded.

Q2 recomputes literal case bindings after bounded test authoring and freezes them
before probe execution. The terminal descriptor retains the full declared module
selection, including unmarked regression cases; CER narrowing applies only to
nonterminal stages. This does not replace required Q6 commands.

## Session preparation and selection diagnostics

Use `preflight-session` before a long sequential run and `advance-session` for
bounded deterministic progression; see [Session](session-operation.md). Worker
implementation and refactoring keep their existing local/caller-session routes.
Use `inspect-selection` to see narrowed argv, full terminal argv, required Q6
commands, repeated declarations and the static selection/fallback reason.
Literal explicit parameter IDs and simple test classes are supported; dynamic
IDs, inherited test classes and unsupported mappings preserve declared selectors.
No candidate test is imported for this inspection.

For a partially implemented obligation, the probe may contain passing and bound
expected-failing cases. Formal RED preserves that exact outcome pattern. All
cases must pass after implementation; see the behavior routing contract.

For cross-slice successful execution reuse, follow [shared execution](shared-execution.md).
The shared content index is an explicit keyed registry, not a latest-run scan.
Same-run reentry still validates its immutable descriptor and stage lineage.
