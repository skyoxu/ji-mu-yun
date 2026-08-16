---
name: vdd-execution-plan
description: Create or repair a complete verification-driven execution-plan directory when the user explicitly requests that outcome. Do not use for direct implementation of one standalone requirements Markdown file.
---

# VDD Execution Plan

Create plans that make observable behavior and current validation decide completion. This repository is maintained by one trusted person and an AI assistant: do not add multi-writer, signer, reviewer-identity, or adversarial-custody controls unless a separate requirement explicitly needs them.

Before acting, read [references/solo-maintainer-vdd-standard.md](references/solo-maintainer-vdd-standard.md), [references/clarification-gate.md](references/clarification-gate.md), and [references/lifecycle-state-contract.md](references/lifecycle-state-contract.md). When maintaining this Skill, also run `py -3 scripts/validate_skill_contract.py --skill-root <skill-root>` and its unit tests.

## Route Input Before Profile

One standalone requirements Markdown file routes to direct implementation and creates no VDD directory, lifecycle bundle, 95 report, or Bootstrap run. Only an explicit request to create a complete execution-plan directory routes to VDD `create`; only an explicit request to repair a complete existing directory routes to VDD `repair`. Never infer either VDD route from file contents or growing task complexity.

## Choose The Profile First

Choose the least complex profile that serves a real consumer. Record the selected profile and reason in the plan.

| Profile | Use when | Required additions |
| --- | --- | --- |
| `standard` | Ordinary feature, fix, documentation change, or bounded refactor | One compact plan document, lifecycle state, Git baseline/current scope, implementation slice(s), one RED or declared legacy-regression path, targeted commands, and one terminal full validation command. |
| `resumable` | Work crosses sessions, has dependent slices, or can leave partial state | `standard` plus compact resume state, dependency-scoped slice status, recovery instructions, and an indexed append-only `95-*.md` report. |
| `self-hosted` | The work changes VDD, Quick Dev, acceptance/review routing, or a controlling validator | `resumable` plus only the protocol fixtures and migration checks consumed by the changed workflow. Stabilize the changed layer with targeted checks before one end-to-end replay. |

Do not create fixed `00-08`/`96-99` books, custom schemas, a custom validator, mutation fixtures, a 95 report, Bootstrap Review, trust roots, attempt ledgers, or effect-fold records for a `standard` plan unless a concrete consumer cannot use an existing repository command or contract. One owner artifact may map requirements, sources, acceptance, and coverage.

## Model Route Decision

Select `standard`, `resumable`, or `self-hosted` entirely from the profile table
before model routing. Then pass that already-selected profile to
`scripts/model_routing.py`; do not add another VDD complexity classifier.
All three ordinary profiles currently request Sol/high. Only a closed typed
complex-recovery trigger may request Sol/max, and that route remains blocked
until an exact backend/model/effort/sandbox capability probe and its shadow
predicate both pass. Free-form recovery reasons fail closed.

The emitted route decision is hash-bound and non-authorizing. The shared
workflow launcher alone may start a child process. In `observe_only`, continue
planning in the current caller session; the decision neither launches a child
nor replaces that session's model.

The canonical policy owns VDD's independent consumer enablement. A disabled
VDD consumer emits `disabled` without changing Quick Dev or Refactor
Acceptance. Sol/max recovery evidence is loaded only from policy-bound
path/hash references under the controlled capability-evidence root. Callers
cannot supply or synthesize a capability-proof dictionary; activation requires
the bound producer receipt, its successful process result, and representative
shadow execution receipts to replay against the requested route identity.

## Clarify Only Material Boundaries

Inspect repository authority, current state, relevant callers, protected paths, and existing tests before asking. Ask only when an answer changes scope, compatibility, destructive behavior, protected-path approval, or acceptance. Zero questions is valid.

An initial explicit write authorization is enough to begin writing when no material blocker remains. Persist a minimized clarification/resume record only when an unresolved decision must survive a session boundary; do not create an active-run registry, cross-process lock, or identity attestation by default. `clarification_state.py` is an optional single-writer resume helper, not a default plan artifact. Its current state uses typed, acyclic CQ dependencies and explicit invalidate/reopen; legacy state is hash-bound and read-only, and sensitive current state terminates in a sanitized quarantine envelope.

## Lifecycle And Implementation

Use the static transition contract in [references/lifecycle-state-contract.json](references/lifecycle-state-contract.json):

`draft -> plan-ready -> implementation-authorized -> implementation-complete -> acceptance-passed -> archived`

VDD owns `draft` and `plan-ready`. The maintainer may explicitly publish `implementation-authorized` without Bootstrap evidence. Bootstrap Review is optional supplemental evidence and never publishes a lifecycle state. Quick Dev may publish only `implementation-complete`; acceptance and archive are separately owned. New plans emit no old state names; repair plans may read them only through the documented compatibility adapter.

For each slice, name its intended behavior, RED or controlled negative command, GREEN/acceptance command, declared downstream dependents, and recovery action. Existing behavior found after implementation uses a declared legacy/regression path: never invent historical RED evidence. A RED command must not rely on the slice's GREEN output or a future slice.

During repair, first stabilize the smallest affected layer. A slice-local change invalidates that slice and its declared downstream dependents only. A shared lifecycle contract, global validator semantic, baseline identity, or dependency used by every slice requires one terminal full replay after targeted stabilization. Targeted validation never authorizes completion. Before publishing `implementation-complete`, run one current terminal full validation.

## In-Place Repair Rounds

An explicit VDD `repair` updates the original execution-plan directory. Append
each repair under `repair/round-<n>/`, binding the exact finalized finding set,
predecessor review, bounded repair slices, RED/GREEN/regression commands, and
a hash-bound `repair-closure.json`. Initial slices and historical evidence stay
immutable. The original directory remains the only acceptance target; use a
successor only after an explicit supersede or incompatible-scope decision.

When the plan opts into Bootstrap implementation review, declare one stable `lineageFamilyId` derived from the original plan target. Keep that family for
all in-place repairs and successor history that still evaluates the same
acceptance target. The default budget is two semantic rounds and the hard
limit is three. A successor does not reset that budget. Round 3 requires one
typed trigger: `novel_p0_p1`, `authority_context_graph_changed`, or
`high_risk_boundary_changed`; exhaustion routes to `manual_pause`.
Require a current hash-bound `inspect-lineage` projection even when it reports zero rounds; omission must not create a fresh budget.
If approved legacy `changeId` history predates the target-derived family,
require an explicit Bootstrap `adopt-lineage` record bound to an Accepted ADR
or decision. Never solve migration by editing historical review manifests or
automatically absorbing every run under the plan directory.

Before a repaired target can re-enter review, generate a read-only root-cause callsite inventory from the affected source roots. Every discovered sibling
callsite must be changed or carry an explicit exclusion. Run at least one
registered producer/consumer composition command and bind its successful
controlled receipt. Handwritten callsite counts and unit-only producer or
consumer checks do not establish repair completeness.
Derive the complete changed set from hash-bound baseline and candidate content
manifests. Bind each present changed path by content hash and each deleted path
by its baseline hash. Composition receipts must bind the current producer and
consumer bytes as controlled-command input paths.
Require each composition check to cover a changed path, declare its consumer as a direct consumer, and expose its receipt as a validation reference.
Require the generated review scope to contain every repair path, inventory match,
composition binding, command registry, receipt, targeted test, and validation
reference; keep consumers and tests in their named context classes.

## Knowledge Preflight

After mandatory authority reads and before freezing plan sources, run the
mandatory knowledge-consumption sequence in
`references/knowledge-consumption.md`. The sequence invokes
`scripts/python/knowledge_locator.py` through JSON stdin, then invokes this
Skill's `scripts/vdd_knowledge_preflight.py` with the request, result, and
adapter-owned decisions. A required module without a matched, reread,
hash-verified Locator candidate blocks `plan-ready`; optional insufficient
matches remain explicit and non-authorizing. `catalog_stale` alone does not
block: the context records `knowledge_freshness=degraded` and continues only
after the same source/read-set verification. Invalid publication and every
selection-shape or Locator integrity failure remain blocking. A hash-only drift of
an already selected read-set is refreshed automatically without widening its
catalog path/module/resource selection; unavailable sources or a selection-shape
change remain blocking.

Use `scripts/prepare_knowledge_context.py` to create the request and frozen
Locator result. Its `--accept` arguments are explicit adapter decisions; it
requires `--target-plan execution-plans/<one-plan>`, rejects output outside
that exact directory, and never promotes a search result automatically. Run
`vdd_knowledge_preflight.py` on the emitted context before publishing
`plan-ready`.

The producer writes no formal context or receipt when preflight is blocked.
Ready output is restricted to one `execution-plans/<plan>/` directory, stages
complete bytes before publication, and can finish an identical orphan context
by publishing its missing receipt after an interrupted first attempt.

## Skill Input Gate

After route selection and authority reads, load
`references/skill-input-contract.v1.json` and run the shared adapter
`scripts/python/prepare_skill_input_consumption.py` for `create` or `repair`.
The adapter must receive the explicit requirements/target-plan/finding paths;
it must not discover them from logs. Launch the typed semantic child only through
`scripts/python/launch_skill_input_consumer.py`: first use `--create-request`
with the candidate receipt and actual backend/model, then use
`--run-semantic-child` with that generated request. Never hand-author its
execution identity. Then run
`scripts/python/validate_skill_input_consumption.py --require-ready` before the
knowledge freeze or any plan artifact is generated. A candidate or failed gate
routes to clarification/repair and cannot be returned as raw source content.
When using `vdd_knowledge_preflight.py`, pass the same receipt with
`--skill-input-receipt` and `--skill-input-operation`.

## Candidate, Review, And Reports

Use a declared Git baseline plus either a frozen commit range or a complete scoped worktree identity. A dirty identity binds `HEAD`, canonical scoped tracked/index diff hash, and a manifest of relevant untracked paths and content hashes. Bind current contracts, implementation, and validators; exclude append-only logs and explanatory reports from normative hashes. Preserve old evidence as historical after invalidation.

Review is optional unless requested by the maintainer or a protected-path rule requires it. Batch accepted findings, run deterministic targeted checks, and do not rerun a complete semantic review for P2-only findings automatically. Review validates the supplied requirements or implementation; it is not an unbounded discovery loop.

Bootstrap history indexes, cost-calibration candidates, and synthetic shadow
corpora are non-authorizing operational inputs. VDD may use their cost signal
when presenting an optional review, but it never treats a historical finding,
similar sample, or prior clean run as current plan readiness. Exact finalized-
envelope reuse belongs to the consuming acceptance workflow and requires a
fresh Bootstrap validation plus byte-identical current candidate binding; VDD
does not select or import that envelope.

When a plan includes Bootstrap Review, freeze a `minimal-complete-closure`,
not an entire repository area by default. For implementation conformance, list
the changed production files, direct consumers, targeted tests and acceptance,
plan acceptance authority, referenced standards, repository rules, and current
runtime or acceptance evidence as explicit files. A directory scope requires a
written assertion that it is itself the minimal complete closure.

Separate transport attempts from semantic rounds. Malformed child JSON, an
invalid Artifact View receipt, or a failed Codex process retries the same role
inside the same run and does not create a repair round or successor lineage.
P2-only findings are disposed in that run and closed or rechecked with targeted
deterministic validation; they do not start another complete semantic review.
Repair evidence stays under the original execution-plan directory, which
remains the acceptance target unless an explicit supersede or incompatible-
scope decision says otherwise.

Round 1 reviews the minimal complete implementation-conformance closure.
After a P0/P1 repair, Round 2 defaults to the repair delta: changed files,
direct consumers, targeted tests, and validation references, while retaining
reachable authority context. After two consumed rounds, a passing repair
completeness audit with no typed Round 3 trigger routes to deterministic
closure instead of another full review. P2-only repair never opens a new
semantic round.

`resumable` and `self-hosted` plans create `95-*.md` before implementation and add its entry to `execution-plans/95-implementation-report-index.v1.json` in the same change. The report is append-only, non-authorizing, records corrections and the final implementation result, and is excluded from candidate hashes. `standard` may omit it unless requested.

Keep the package generic. Never read a mutable live execution-plan directory or embed dated plan names, plan-local paths, RMAP IDs, live plan hashes, user-profile paths, or machine-specific paths. Detached fixtures prove package behavior; repository-level tools own live 95-index containment and existence checks.

## Completion

Do not claim completion until the selected profile's required artifacts exist, each active requirement has an observable acceptance path, the declared RED/negative or legacy path is recorded, targeted repairs are stable, and the current terminal full validation passed. `plan-ready`, `implementation-authorized`, `implementation-complete`, `acceptance-passed`, and `archived` remain distinct.
