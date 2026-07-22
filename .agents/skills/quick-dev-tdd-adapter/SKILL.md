---
name: quick-dev-tdd-adapter
description: Resume one explicit Repository Maintenance execution-plan directory through hash-bound TDD slices, observed RED, minimal GREEN, refactor, evidence capture, and its plan-local terminal predicate.
---

# Repository Maintenance TDD Adapter

Use this Skill only with an explicit plan file or plan directory containing a valid `implementation-contract.v1.json`. It is a plan-directory execution loop; it is not a review authority, commit authority, or release authority.

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
4. After `slice-ready`, route the next unlocked slice automatically. Stop only at the plan-local terminal predicate, `external-repair-required`, `await-external-envelope`, or a repeated failure fingerprint.
5. S7 may read and validate a referenced finalized Bootstrap envelope, but this Skill never launches Bootstrap Review, changes review evidence, or creates a successor policy.

Use the bounded driver for a declared slice write set:

```powershell
py -3 .agents/skills/quick-dev-tdd-adapter/tools/loop_plan_directory.py `
  --repository-root C:\jimuyun `
  --plan-dir C:\jimuyun\execution-plans\<target-plan> `
  --snapshot-path <declared-write-path> `
  --max-actions 8
```

The caller supplies explicit snapshot paths from the current slice's declared write set. The driver creates a new append-only run, compiles only the target plan's registered commands, executes all declared refactor invocations, and re-routes after a current terminal predicate. It must not guess a write set or create implementation changes absent from the backend's declared allowed writes.

The adapter never treats backend text, a Capsule, an adapter decision, run state, a clean process exit, or this Skill as acceptance authority. Only the plan-local registered predicate may authorize its declared state.

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
