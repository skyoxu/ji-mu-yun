---
name: quick-dev-tdd-adapter
description: Resume or implement one explicit Repository Maintenance execution-plan directory containing a schema-valid implementation-contract.v1.json through hash-bound TDD slices, observed RED, minimal GREEN, refactor, evidence capture, and its plan-local terminal predicate. Use this Skill instead of bmad-quick-dev whenever that contract exists.
---

# Repository Maintenance TDD Adapter

Use this Skill only with an explicit plan file or plan directory containing a valid `implementation-contract.v1.json`. It is a plan-directory execution loop; it is not a review authority, commit authority, or release authority.

The parent Quick Dev input router owns lane selection. This strict adapter must
reject standalone requirements, compact VDD inputs, missing contracts, and
schema-invalid contracts. It must never infer a compact lane or synthesize a
contract. All lanes reuse the same four-class model classification, but only a
`strict_tdd_plan` may enter this adapter.

Before reading plan state or selecting an action, run the parent router with
`--caller quick-dev-tdd-adapter`. A nonzero result is a hard routing failure:
do not enter this adapter, create run evidence, or fall back to Stock BMAD
Quick Dev. The successful route must name both `lane: strict_tdd_plan` and
`backend: quick-dev-tdd-adapter`.

The parent CLI requires caller identity. For this Skill the only valid caller
value is `quick-dev-tdd-adapter`; omitting it or substituting
`bmad-quick-dev` must fail before any BMAD spec or adapter evidence is created.

## Target Plan Report Lifecycle

Complete this lifecycle before `prepare` or any implementation identity freeze:

1. Require `--plan-dir execution-plans/<plan-dir>` or one plan file inside that directory. Reject paths outside `execution-plans/`.
2. Read only the supplied file and its containing target directory. Do not enumerate, index, or infer state from any other execution-plan directory.
3. Resolve at most one `95-*.md` inside the target directory. A duplicate, stale, escaping, or ambiguous report fails closed and routes to VDD repair.
4. Treat the report and `logs/tdd-adapter/<plan-id>/run-state.v1.json` as non-authoritative continuity data. Both carry `authorizes: []` and cannot authorize acceptance, commit, handoff, release, or completion.
5. Audit the target plan, route material defects through the target directory's declared repair gate, validate the repaired plan, and refreeze every affected identity before observing RED.

After the target plan's current declared terminal predicate passes, append its overall implementation result to the same report. Never use report text or an index entry to satisfy that predicate.

## Required Order

1. Run `tools/loop_plan_directory.py` before every expensive action. It reads only the explicit target directory and its plan-local evidence and emits one next action.
2. For `run-slice`, generate a plan-local `run_context` and invoke `tools/run_slice_lifecycle.py`; it uses the shared `LifecycleRunner` and `stage_artifact_composer`. Never handwrite stage, Capsule, attempt, or ledger JSON.
3. Run the declared RED command and require its expected nonzero failure before a production write; then run GREEN, REFACTOR, and the plan-local slice predicate.
4. After `slice-ready`, route the next unlocked slice automatically. Stop only at the plan-local terminal predicate, `external-repair-required`, or a repeated failure fingerprint.
5. A plan may consume an already-published implementation authorization before its first implementation slice. This Skill never launches Bootstrap Review, changes review evidence, or creates a successor policy. Its terminal result may only be `implementation-complete`; acceptance remains external.
6. After a P0/P1 repair reaches the plan-local terminal predicate, read
   [repair-review-handoff.md](references/repair-review-handoff.md), generate the
   standard Acceptance request, and immediately run the Acceptance-owned
   `audit-repair-completeness` command. Preserve the current predecessor,
   hash-bound baseline and complete candidate manifests, changed files, direct
   consumers, targeted tests, validation references, the generated root-cause callsite inventory, and controlled producer/consumer composition receipts.
   The Acceptance audit derives the exact changed set from the candidate
   manifest, binds present paths by current content hash, and binds deleted
   paths by their baseline hash before routing continues. Run each registered
   composition command with every producer and consumer supplied as an
   `--input-path`. Supply every
   preserved repair and composition artifact to the same minimal review closure;
   do not let the handoff and Bootstrap scope describe different file sets.
   Do not select an acceptance route, launch Bootstrap, create a review
   successor, or change the stable lineage family.

## Skill Input Gate

After the parent route and minimum target discovery, load
`references/skill-input-contract.v1.json` and prepare a strict receipt with
`scripts/python/prepare_skill_input_consumption.py --operation execute`.
Pass the explicit plan directory and target file paths as source roles. Use
`scripts/python/launch_skill_input_consumer.py --create-request` with the
candidate receipt and actual backend/model, then run the typed semantic child
with that generated request. Never hand-author its execution identity. Require
`validate_skill_input_consumption.py --require-ready` before
action selection, `prepare`, or RED. `ready=false`, source drift, or a missing
sidecar is a hard stop and must route to plan repair; no raw snapshot or log is
fallback input. In the Python adapter, use `tools/adapter.py`'s
`prepare_with_skill_input` wrapper so the gate result and context artifact are
bound into the prepared slice.

## Model Route Decision

Before a slice backend is selected, derive the closed typed fact set consumed
by `tools/model_routing.py` from the explicit plan, protected-path rules,
declared write roots, consumers, tests, and unresolved boundaries. Select the
highest matching class:

- `architectural`: an ADR or invariant, public API, database schema,
  auth/security, runtime/deployment, shared LLM entrypoint, protected path, or
  workflow control-plane ownership changes.
- `complex`: no architectural trigger, but cross-module consumers, state or
  recovery semantics, concurrency/idempotency, multiple production write
  roots, or an unresolved behavioral boundary exists.
- `small_mechanical`: no higher trigger, the transform and behavior are fully
  specified, at most one production root and one matching test root change,
  and no contract or dependency is introduced.
- `normal`: every other bounded implementation task.

Unknown or contradictory facts route to blocked `complex`. An explicit user
override may upgrade the class; it cannot downgrade the highest matched class.
Emit the hash-bound decision as non-authorizing evidence. The adapter must not
select a provider or invoke a model process. The shared workflow launcher owns
child execution. In `observe_only`, continue with the current caller session;
the decision neither launches a child nor replaces that session's model.

The canonical policy owns Quick Dev's independent consumer enablement. When it
is disabled, classification evidence remains deterministic but the route
status is `disabled`; VDD and Refactor Acceptance controls are unaffected.
Only the canonical policy may authorize execution, so a caller-supplied policy
or capability assertion cannot turn a non-authorizing decision into a launch.

The adapter does not read Bootstrap history baselines, promote cost
calibration, or select a finalized run for reuse. Refactor Acceptance alone may
reuse a run after revalidating the prepared Acceptance candidate, custody,
Bootstrap candidate binding, scope, profile, policy, authority, and clean
status. A historical match never changes this adapter's terminal predicate or
its non-authorizing handoff.

## Knowledge Consumption

When a VDD plan contains frozen knowledge context, verify its accepted decisions
and source hashes before RED. Do not issue a new Locator query or expand its
paths, candidates, classifications, or satisfied modules. Any difference routes
to VDD repair. See `references/knowledge-consumption.md`.

`tools/route_plan_directory.py` verifies a declared
`knowledge-context.v1.json` and its VDD-owned
`knowledge-context.freeze.v1.json` receipt before any slice can start. A
binding, receipt, or source-hash mismatch routes to VDD repair.
The shared context validator must byte-match current main, and every accepted
Locator read-set path must still match its hash in the worktree before RED.

Use `tools/persistent_plan_loop.py` for unattended execution. It re-routes after every completed slice and consumes only the slice's explicit, no-wildcard `execution_snapshot_paths` declaration. The plan validator requires that declaration to name an existing repository file covered by that slice's allowed write set; a missing or invalid declaration fails closed. A plan-owned contract may explicitly declare `planned_new_files` for files intentionally created by its current-session bridge. Only those exact paths may be absent at preparation; the bridge must require test files before RED, production files before GREEN, and every planned path before REFACTOR. Its state file belongs under `logs/tdd-adapter/<plan-id>/controller/`.

Use the bounded driver for one declared slice write set:

```powershell
py -3 .agents/skills/quick-dev-tdd-adapter/tools/loop_plan_directory.py `
  --repository-root C:\jimuyun `
  --plan-dir C:\jimuyun\execution-plans\<target-plan> `
  --snapshot-path <declared-write-path> `
  --max-actions 8
```

The caller supplies explicit snapshot paths from the current slice's declared write set. The driver creates a new append-only run, compiles only the target plan's registered commands, executes all declared refactor invocations, and re-routes after a current terminal predicate. It must not guess a write set or create implementation changes absent from the backend's declared allowed writes.

The adapter never treats backend text, a Capsule, an adapter decision, run state, a clean process exit, a repair review handoff, or this Skill as acceptance authority. Only the plan-local registered predicate may authorize its declared state.

## Version Currency Commit Gate

The adapter is not commit authority. Before a caller commits a completed slice, inspect the staged diff and its declared target runtime or dependency versions.

1. If the diff changes a version-sensitive external SDK, framework, CLI, or language API, resolve the library with Context7 and query documentation for the exact target version before proposing the commit.
2. Compare the documentation with the repository-pinned version and local contract. Missing, ambiguous, or version-mismatched documentation blocks the commit until the caller resolves the discrepancy.
3. Treat Context7 output as read-only implementation context, never as acceptance proof or a replacement for declared RED, GREEN, REFACTOR, or plan-local predicates. Preserve the version and source reference in existing slice evidence when the protocol already requires candidate evidence.
4. If the diff changes only repository-owned code, fixtures, documents, or stable standard-library behavior, record the gate as not applicable and do not create a network dependency merely to commit.

## Boundaries

- Use structured command descriptors with `shell: false`; do not accept raw shell commands.
- Reject authority, command, validator, contract, write-set, read-set, dependency, baseline, or predecessor drift.
- Preserve failed evidence and create a stale-linked successor instead of overwriting a run.
- Do not invoke Stock BMAD Quick Dev as an authoritative backend or consume its review/done state.

Read [implementation-backend-contract.md](references/implementation-backend-contract.md), [tdd-run-protocol.md](references/tdd-run-protocol.md), and [evidence-and-freshness.md](references/evidence-and-freshness.md) before implementing a slice.
