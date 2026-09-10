# Prepare And Run Acceptance

Read this guide only for the operation selected in SKILL.md. Commands run from the repository root unless stated otherwise; inline paths retain their original repository/Skill-root meaning.

## Default Orchestration

Own the complete coordination loop when invoked for a new or existing target.
Do not stop after reporting that another Skill or review is required. Continue
until a typed user-acknowledgement boundary, protected-path boundary,
`manual_pause`, or terminal Acceptance result is reached.

Resolve entry inputs in this order:

1. Require one repository-relative `execution-plans/<target>` directory.
2. Prefer `candidate_mode=commit`. If the caller omits the candidate, use the
   current `HEAD` only when the relevant worktree is clean and report the full
   resolved commit. Otherwise require a frozen dirty-worktree or
   proposed-commit-set snapshot.
3. Read an unambiguous frozen Git baseline from the target plan. If none exists,
   require an explicit baseline revision. Never infer the baseline as
   `candidate^`; one target may span multiple commits.
4. Derive the run directory after creating the typed run request and its
   canonical input hash, but before publishing the `prepare-run` output. Do not
   ask the caller to name it unless they need an explicit recovery identity.

Require either the plan's full implementation contract or one current
`compact-vdd-acceptance-prerequisite-bundle.v1`, plus complete baseline and
candidate content manifests, typed run request, action DAG, and command
registry before starting the persisted run. Resolve their fields from the
target plan and an explicit VDD or Quick Dev handoff. For an
`implementation-complete` compact VDD target, run
`scripts/compact_vdd_projection.py` only with an explicit sorted changed-path
list, consumer refs, commands, actions, policy, and Acceptance-owned knowledge
context. For current Quick Dev Q8, supply `currentQuickDev` on the projection request:
`semanticPlan` and `receipt` are repository-relative file references with byte
SHA-256 hashes; `snapshotRoots`, `sourceCommit`, and `baseCommit` are the exact
Q8 invocation inputs. The result schema is
`quick-dev.implementation-complete-result.v2`. Acceptance invokes the Quick Dev
owner's read-only proof replay, including runtime roots, all assertion/case
edges, behavior routes and deferred gates. It does not rerun tests or a model.
The current terminal input must contain the owner-produced snapshot manifest;
historical results without it are not silently upgraded or rebound.

The compact projection retains explicit changed paths and baseline/candidate
custody. It does not require a current plan to manufacture legacy
`implementation-contract.v1.json` or a plan-local terminal runner. Existing
legacy `quick-dev-implementation-complete.v2` handoffs keep their validation
path. Neither result format grants Acceptance authority. Acceptance must also
execute and validate every required registered action before finalization.

The orchestrator may otherwise materialize prerequisites
deterministically from those bindings and immutable Git bytes, but must not
guess scope, revisions, changed paths, commands, or acceptance actions. If a
required source is missing or ambiguous, report `prerequisite_blocked` with the
missing artifacts and stop before `start-or-resume`.

When a current Q8 receipt is absent or stale, return the exact missing or stale
binding to the current Quick Dev public entry (`scripts/quick_dev/run.py`).
Preserve the predecessor and use its explicit stage recovery requirements;
do not invoke a plan-local legacy terminal loop for current semantic bundles.
Legacy targets retain their declared controlled terminal recovery route.

Treat candidate assembly as one evidence transaction. Complete every
VDD/source-freeze mutation, then publish the knowledge catalog, then create
the Acceptance knowledge context and Skill-input receipt, and only then invoke
the projection. The projection atomically publishes the manifests, snapshot,
run request, and prerequisite bundle. Historical snapshots, `in/` artifacts,
and prior Acceptance inputs are never copied into a successor candidate.

Before `start-or-resume`, bind `implementation_target` and
`acceptance_requirements` for the `acceptance` operation.
Use the v2 request and commands in `docs/workflows/skill-input-v2.md`
(ADR-0060). Bind the real consumer contract, explicit required-input roots,
registry, authority envelope with `skill_input_baseline`, and Knowledge freeze.
The adapter derives candidate changes from Git; never supply an empty changed
set to conceal Knowledge changes. Run `skill_input_v2.py prepare`, consume all
pages, then `finish`. Pass only `<storage>/current.v1.json` as
`--skill-input-receipt`, with the bound `--skill-input-contract`.
The live gate revalidates inputs/candidate and automatically persists a
non-authorizing consumer-use reference before handing off context. V1 CLI
replay requires `--historical-v1`; its output cannot enter a live consumer.
Transport coverage is not semantic approval and does not replace downstream
Knowledge, review, lifecycle, or authorization requirements.

Create the knowledge context only through the canonical Locator and bind the
adapter to exactly one explicit `--target-plan`. `catalog_stale` alone is a
non-authorizing `knowledge_freshness=degraded` condition: record it in the
hash-bound ready context and continue from the current, hash-verified Locator
read-set. This Skill must not invoke publication automatically; catalog
publication remains an explicit maintainer action and is never a prerequisite
for this run. Other knowledge failures, including invalid publication,
unavailable candidate sources, unsatisfied required modules, unsafe paths, or
schema failures, route to
`knowledge-context-repair-required` and stop. Never hand-author candidate
selections, bypass Locator source/read-set validation, or write knowledge
artifacts outside the explicit target plan. The adapter persists a blocked route
append-only under `<target-plan>/knowledge-context-routes/<hash>.json` only for
those blocking failures.

Before a ready context is written, validate the complete Locator read-set
against current worktree bytes. When only bytes have changed, automatically
produce a successor context with `source_refresh=current_worktree_read_set`:
it preserves the catalog-selected paths, modules, and resource-set exactly and
rebinds only their current hashes. A missing source, path/resource-set change,
module mismatch, or schema failure remains a typed repair route and stops; no
automatic refresh may widen the knowledge selection.

Create or resume the target-owned append-only run with the canonical run-input
request hash that `prepare-run` will publish as `inputHash`, plus the
implementation-contract file hash, frozen knowledge-context file hash, and the
ready Skill-input receipt and contract:

```text
py -3 .agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py start-or-resume \
  --repository-root <repo> --target-plan <execution-plans/target> \
  --run-input-hash <sha256:...> --contract-hash <sha256:...> \
  --knowledge-context-hash <sha256:...> \
  --skill-input-receipt <storage>/current.v1.json \
  --skill-input-contract .agents/skills/run-refactor-implementation-acceptance/references/skill-input-contract.v1.json
```

`run-input-hash` is the canonical JSON hash that `prepare-run` computes as
`inputHash`. The next two values are SHA-256 hashes of the exact contract and
frozen context file bytes; use the context `sha256` emitted by
`freeze_knowledge_context`, not its semantic `contextHash`.

Omitting `--run-id` derives `acceptance-<16-hex-binding-id>` from those three
hashes plus the validated Skill-input binding and context-artifact hashes. The
same target and bindings resume the same persisted run without rewriting it.
Any input, contract, knowledge-context, Skill-input receipt, or context drift
invalidates only that derived artifact. Automatically rebuild the owner-owned
artifact and create a binding-derived successor run; never overwrite the stale
predecessor. Fail closed only if deterministic rebuild cannot verify a required
source, scope, schema, or authority.

Treat a historical Acceptance directory without `run-state.json` as an
artifact-only legacy run. Preserve it for replay, never auto-migrate it into
the persisted lifecycle, and create a new binding-derived run directory.

Execute the orchestration in this order:

1. Inspect the target for an existing request and matching persisted run before
   creating new evidence.
2. Resolve or deterministically materialize the complete manifests, action DAG,
   command registry, Acceptance-owned knowledge context, and typed run request;
   then compute the three entry hashes and validate the Skill-input receipt.
3. Run `start-or-resume`, write the `prepare-run` output inside the returned run
   directory, and inspect/resume its existing action evidence with the persisted
   entry bindings. A new persisted run must reject entry resume when the frozen
   knowledge-context or Skill-input binding is omitted.
4. Run the deterministic inventory, policy, matrix, checklist, scan, coverage,
   and evidence actions required by the target contract.
   When the persisted action DAG is closed on the default `deterministic_only`
   route, run `acceptance_cli.py finalize-deterministic-run` with that exact
   prepared run input, action DAG, and command registry. It must replay the
   hash-bound controlled receipts for every completed action, then append the
   candidate evaluation, impact projection, and Acceptance-owned
   `acceptance-passed` result. A missing, failed, or stale receipt fails closed;
   this step does not invoke Bootstrap.

For an explicitly requested Bootstrap route, continue with [Bootstrap operations](bootstrap-operation.md). Otherwise stop at the typed deterministic terminal result.

## Current Core

Before `prepare-run`, create one Refactor Acceptance-owned knowledge context
through the canonical Locator:

```text
py -3 .agents/skills/run-refactor-implementation-acceptance/scripts/prepare_knowledge_context.py \
  --repository-root <repo> --request-id <id> --query <query> \
  --target-plan <execution-plans/target> \
  --required-module acceptance-scope \
  --accept <candidate-path>=acceptance-scope \
  --output <target-plan>/knowledge-context.refactor-acceptance.v1.json
```

The adapter uses `consumer=refactor-acceptance`, records one accepted or
rejected decision for every Locator candidate after reread/hash verification,
and fails closed on publication, snapshot, policy, projection, request/result,
or read-set drift. It never uses unpublished staging inputs.

The formal CLI requires that frozen file at the `acceptance-run-input` freeze
point:

```text
py -3 .agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py prepare-run \
  --input <request.json> --knowledge-context <target-root-relative-path> \
  --out <run-input.json>
```

Historical function-level inputs without a knowledge context remain readable;
new CLI preparations cannot omit it. Later phases consume the frozen summary
and never issue another Locator query. The shared context validator must
byte-match current main, and the complete Locator read-set is revalidated
against both its source commit and current worktree before the summary freezes.

`scripts/acceptance_cli.py prepare-run` validates a hash-bound run input with replayable baseline and candidate content manifests, then writes a new non-authorizing run-input artifact. Commit candidates are checked against raw bytes from resolved immutable Git commits, and the resolved baseline/candidate OIDs are persisted in `candidateCustody`. Dirty-worktree and proposed-commit-set candidates must declare `candidate_frozen_snapshot_path` as `.acceptance-snapshots/<run_id>` beneath the target root; symlinks and live workspace substitutes are rejected, and the snapshot manifest receipt is persisted.

Select `policies/phase-service-code-review.v1.json` only for Phase candidates;
it may retain an explicit unreviewed external partition for mixed candidates.
Select `policies/toolchain-code-review.v1.json` for repository workflow
control-plane candidates. Its closed path rules must cover every changed path,
and its binding records shared Phase entrypoints as cross-domain dependencies.
An uncovered toolchain path fails closed. Pure Godot inputs remain unsupported.

`analyze-diff-coverage` consumes a frozen `phase-changed-line-set.v1` and a current Cobertura report. It uses only added or modified executable `PhaseA.Platform/**/*.cs` lines for the denominator, records every exclusion reason, and returns `incomplete` when a source mapping is missing. It never substitutes repository-wide coverage.

`audit-task-checklist` reads only explicitly declared authority checklist files. A checked item is `verified` only when its stable item identity has current matrix, implementation, test, and evidence references; source hash drift, checkbox-only closure, and request-controlled optionality fail the result. `run-command` resolves an exact descriptor from a hash-bound command registry; it never executes a caller-supplied descriptor. `run-phase-scan` is available only in `controlled_validation`, executes that registered shell-free command from a hash-verified frozen candidate snapshot, and requires its declared Phase read scope to exactly cover the candidate's Phase changed paths.

`audit-repair-completeness` consumes the append-only Quick Dev handoff without
translation. It revalidates the baseline/candidate manifests and rejects an
omitted or invented changed path. Every inventory is discovered from current repository bytes and
every composition check must reference a successful controlled-command
receipt. Feed its result and the Bootstrap `inspect-lineage` projection into
`prepare-bootstrap`; do not hand-author consumed rounds or route kinds.

The matrix, conditional Bootstrap import, action recovery, and final authorization stages are implemented only when their own plan slices and predicates are complete. A passing unit test or a Bootstrap `clean` result is not Program DoD.
