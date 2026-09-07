# Observed behavior routing: CER-R4--R6

Decision: ADR-0041, Observed Behavior Routing (2026-09-07).
This extends the existing VDD compiler, Quick Dev dispatcher and Q7/Q8 predicates.
The phase-1 [case evidence contract](case-evidence-contract.md) remains mandatory.

## Planning and classification

The compiler embeds `behavior_routing` with schema
`vdd.behavior-routing-intent.v1`, an exact `intents` projection and `deferred`.
Each intent names the obligation, Acceptance/assertion IDs, production owners,
write paths, selector intent, observable, expected result and dependencies.
Workers cannot replace that projection with present/missing labels. No test or
live backend is invoked to produce this planning projection.

The controlled `probe` uses the ordinary descriptor, process receipt, structured
pytest collector and independent judge. The stage result includes
`behavior_dispositions`, `behavior_plan_sha256` and `production_hashes` for the
slice's owners and declared dependency closure. A disposition includes its
obligation/Acceptance IDs, resolved assertion case sets and an observed reason.

| Case facts for one obligation | Disposition | Authority |
| --- | --- | --- |
| All required cases execute and pass | present | Current regression may run. |
| All required cases satisfy the behavioral RED contract | missing | Formal RED may run; the probe itself is not RED authority. |
| Missing mapping, skip, setup/import/teardown failure, timeout, ambiguous attempt, or mixed pass/fail inside the obligation | unverifiable | Repair the environment/contract or split the obligation; no implementation. |

The existing oracle and semantic chain still determine whether cases check the
intended behavior. Case identity does not solve arbitrary oracle quality.
A shared selector may execute both subsets. Unmapped results never fill another
obligation's proof. Partial presence is not an authorizing coarse classification.

## Stable entry

Use `scripts/quick_dev/run.py` and a fresh explicit `--run-dir`:

1. Run preflight as usual. `author-red` prepares tests/mappings and freezes a
   probe descriptor for capability-bearing plans. Existing mapped tests need no
   model-backed author call. Production remains outside test-author writes.
2. `run-probe` records observed dispositions and returns the next action.
3. For missing obligations, use `run-red`, `implement`, `run-green`, and
   `run-refactor`. Only the missing subset appears in these descriptors.
4. For present obligations, use `run-regression`. In a mixed slice do this after
   the missing subset is GREEN/REFACTOR. Pure present slices require no RED,
   implementation worker or refactor stage. Required extra validation commands
   still run via the existing regression gate.
5. `validate-slice` freezes the terminal descriptor before computing Q7's current
   snapshot. Run `run-terminal`, then `implementation-complete` with the existing
   explicit predecessor and snapshot inputs.

`route-behaviors` rereads the explicit probe and stage results to report the next
action. It does not scan logs, choose a latest successful run or authorize writes.
The low-level `execute-stage` entry applies the same probe/descriptor scope guards.
Standalone callers must freeze the terminal descriptor before Q7, as before.

## Binding and closure

Non-probe descriptors embed `behavior_route` with schema
`quick-dev.behavior-route.v1` and `probe_result_sha256`. A probe descriptor has a
null probe hash. The materializer selects assertion scope, but execution rereads
and re-derives the actual route before accepting it. Plan/target/fixture drift,
changed case mappings, edited disposition rows or stale probe lineage block use.
Formal RED additionally requires the probe's production state still be current.

GREEN/REFACTOR preserve their RED case set. Regression preserves the present
probe's case set and executes against current production. A changed relevant
owner or declared dependency invalidates current regression/refactor proof;
an unrelated owner's bytes are not included. Failed present behavior never
implicitly grants production writes. Repair/re-probe in a fresh run before
switching to missing. Old runs are immutable and remain historical.

Q7 derives required stages per Acceptance from the actual obligation route and
checks every assertion/case. Q8 re-derives that route, rereads every required
stage edge, checks terminal coverage and current production/snapshot bindings,
and closes the entire current obligation set. A mixed plan may have different
routes across slices; neither numbering nor directory order defines dependencies.
The existing declared dependency/explicit predecessor contracts remain owners
of scheduling. This extension does not add an automatic global scheduler.

Historical `stage_scope=[red,green,refactor,terminal]` remains mandatory for
bundles without the new capability. In capable bundles it is the potential
missing path; the observed route determines the actual runtime tuple set.
No historical evidence is rewritten or retroactively promoted.

## Minimal Deferred rules

Every row names `type`, `reason`, `resolution_owner`, `resolution_stage` and a
nonempty `affected_obligation_ids` set from current scope.

| Type | Rule |
| --- | --- |
| implementation-resolvable | Internal implementation strategy only, resolved at implementation with observable, assertions, selectors and legal write paths already specified. All runtime proof remains required. |
| external-owner | An unresolved current-scope external prerequisite blocks; it is not current implementation completion. |
| blocking | Blocks current scope until the missing contract/authority is resolved. |

The validator derives blocking; an author-supplied `blocking=false` is ignored.
Unknown types, incomplete records, missing current coverage or deferral of the
proof contract fail closed. A genuine out-of-scope decision uses the established
source/scope mechanism; a Deferred row cannot make that decision by itself.

## Validation boundary

Use deterministic case/probe/route/closure tests and the affected VDD contract
and Skill package checks. Representative tests cover all-present, mixed,
regressed-present, stale evidence, environment failures and Deferred escapes.
Windows confirmation and later ordinary-task experience are recorded separately;
this increment does not require repeating historical CH456 live acceptance.
