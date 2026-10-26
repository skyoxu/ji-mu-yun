# Three bounded toolchain optimizations

Status: implementation input; no generated execution plan or lifecycle authority.

Baseline: `d2fd7405513b90c516e7f65f1771be67efcb1b95`.
Local branch: `toolchain/light-optimizations-20261026`.
Controlling decision: Accepted ADR-0041 and its existing execution ownership,
source freshness, bounded repair, evidence reuse and execution budget rules.

This input records the three optimizations authorized after the knowledge-query
delivery. PR #21 and its branch are outside the write boundary. This input does
not extend that delivery's scope or relabel its execution/Acceptance evidence.

## FR-1: Read-only admission before VDD compilation

Before the first semantic worker starts, provide one bounded admission result
covering readable source inputs, an explicitly selected recovery candidate,
available dependency projection, and the actual Quick Dev public entry.
Keep VDD plan-shape and Quick Dev execution profiles separate and validate each
against its existing policy. Do not infer a model or change model routing.

Reuse current source preflight, native recovery validation, dependency rules and
consumer checks. Admission must not invoke models, execute tests, create run
state, publish a plan, or mutate caches. Missing or corrupt required current
inputs block. Contracts that do not exist before V3 are explicitly pending;
pending does not mean successful end-to-end validation or plan readiness.
V3 execution preflight and final publication gates remain mandatory.

Package owner: VDD public compiler/admission; Quick Dev supplies its existing
consumer-owned read-only checks.

Production boundary:

- `scripts/vdd/compile_plan.py`
- `.agents/skills/vdd-execution-plan/scripts/execution_preflight.py`
- One narrowly scoped admission helper in that same scripts directory, only if
  needed to keep the public CLI small.
- Consumer helper changes shared with FR-2; no duplicated argv/profile policy.

Test boundary:

- Extend `test_execution_preflight.py` or one adjacent focused admission test.
- Public entry: invalid input, explicit corrupt/stale recovery and unavailable
  consumer entry block before any worker; the two profiles remain independent.
- New compilation reports missing future contracts as pending.
- Verify no model/test/process-evidence/cache/state writes on admission.
- Retain applicable source-resume and V3-pause regressions; do not replay the
  original knowledge-query delivery.

## FR-2: Validate what the actual Quick Dev consumer reads

At read-only admission, compare each materialized disk agent-context projection
with the semantic bundle's corresponding projection. Reject missing, ambiguous
or changed context before worker execution. Use the actual consumer's command,
target, fixture and static selector resolution to prove consumability without
importing tests or observing product behavior. A legal planned absent test
remains Q2 work, not a fabricated assertion mapping or RED observation.

Reuse current legal expected-red binding and exact obligation-to-slice dependency
rules. Check explicit dependency projection against the existing authoritative
obligation graph without silently repairing it at the consumer boundary.
Unsupported static mappings retain the existing declared-selector fallback and
must never be promoted to runtime case proof.

Package owner: Quick Dev read-only consumer; VDD calls the same checks for the
candidate representation available at its current stage.

Production boundary:

- `.agents/skills/quick-dev-tdd-adapter/tools/q1_planned_preflight.py`
- `.agents/skills/quick-dev-tdd-adapter/tools/stable_runner.py`
- `.agents/skills/quick-dev-tdd-adapter/tools/case_selection.py`, only if needed
  to expose the existing pure reader without copying its implementation.
- `.agents/skills/quick-dev-tdd-adapter/tools/execution_session.py`, only to use
  the shared reader.
- Existing VDD execution preflight and dependency helpers, only for reuse.

Test boundary:

- Extend `test_ch456_q1_planned_preflight.py` and `test_execution_session.py`.
- Bundle-valid but disk-missing/changed context blocks before a run is created.
- Bundle-valid but unconsumable actual argv/selector blocks; legal planned
  targets and existing static fallback retain their established behavior.
- Wrong explicit slice dependencies reject through the existing graph rule.
- Add one cross-slice transitive dependency drift regression if not already
  covered; retain shared-execution and stage-reentry reuse regressions.

## FR-3: Explicit dependency revisions with bounded impact

Extend an existing successor-repair route only where its authority permits an
explicit dependency revision. Bind the exact predecessor/source identities and
declared old/new edges. Preserve all unselected requirements, oracles, production
owners, slice memberships, write sets, selectors, terminal predicates and
historical failure intents. Reuse existing runtime-role-only repair rather than
introducing another failure-role protocol.

Validate both graphs, reject unknown/duplicate/dangling/cyclic relations and
compute affected slices plus transitive downstream closure across the union of
old and new edges. Removed edges must not hide former dependents. Record the
actual changed contracts and scope; reject unrelated drift. Preserve the
predecessor and publish only to a distinct empty legal successor.

Unchanged source does not authorize reuse of V4 after a semantic dependency
change. Such a change must enter the already-owned semantic repair/gates with
fresh applicable V4 evidence. Projection-only historical omissions continue to
use existing handoff repair. Never relax ordinary dependency-binding validation
or forge plan-ready/semantic-review receipts to make this package fit.

If the current authority cannot safely express this revision, report the exact
boundary after FR-1/FR-2; do not add a general plan mutation protocol.

Package owner: existing VDD successor repair and dependency validation.

Candidate production boundary, subject to authority resolution:

- `scripts/vdd/compile_plan.py`
- `.agents/skills/vdd-execution-plan/scripts/quick_dev_handoff.py`
- `.agents/skills/vdd-execution-plan/scripts/execution_contract.py`
- `.agents/skills/vdd-execution-plan/scripts/semantic_v3_contract_repair.py`
  only where an existing semantic repair route is necessary and sufficient.

Test boundary:

- Extend dependency projection and native successor-repair tests.
- Explicit add/remove edges yield the old/new downstream closure.
- Source/predecessor drift, unsafe output, cycle/dangling edges and nonselected
  contract changes reject without predecessor mutation or successful publication.
- Semantic changes cannot reuse old V4; role-only and projection-only paths keep
  their existing evidence reuse and permissions.
- Unaffected generation inputs remain reusable where existing checks permit;
  cross-successor execution receipts are never relabeled as current proof.

## Validation and delivery boundary

Every new executable behavior needs actual failing behavioral assertions against
its production entry, then minimal implementation and GREEN with frozen tests.
Setup/import errors, artificial failures and plan/admission status are not RED.
Reuse verified applicable evidence; run affected old regressions serially after
freezing shared inputs. Preserve independent-unit budgets of 1800 seconds total
and 600 seconds without genuine progress and the existing evidence engine.

This requirements file is not a Quick Dev `strict_tdd_plan` contract. Native
Quick Dev execution awaits a valid compiler-produced plan for these packages.
Do not use the old knowledge-query bundle, hand-author plan-ready, invoke BMAD,
launch A/B or Acceptance, push, open/merge a PR, or monitor remote CI/Actions.
Model-backed VDD planning, if needed, is coordinated with the parent first.
