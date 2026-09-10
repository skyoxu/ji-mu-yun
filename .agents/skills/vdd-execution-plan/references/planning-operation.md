# Create Or Repair A Plan

Read this guide only for the operation selected in SKILL.md. Commands run from the repository root unless stated otherwise; inline paths retain their original repository/Skill-root meaning.

## Current Behavior Routing (CER)

New compiler output includes `vdd.behavior-routing-intent.v1` in the existing
semantic bundle. It projects each obligation's Acceptance/assertions, production
entry, selector intent, observable, expected result and dependencies. These are
probe intentions only: VDD does not execute tests or assign present/missing from
files, model opinion or historical pass records.

Quick Dev's controlled case probe derives `present`, `missing` or `unverifiable`
per obligation. Present behavior stays in current regression/terminal coverage;
missing behavior requires real RED/GREEN/REFACTOR; an unverifiable or mixed
result inside one obligation requires contract/environment repair or finer
atomic decomposition. Do not remove present obligations from the coverage set.
The [behavior routing contract](../../quick-dev-tdd-adapter/references/behavior-routing-contract.md)
owns runtime details under ADR-0041.

The optional `behavior_routing.deferred` list records type, reason,
resolution_owner, resolution_stage and affected_obligation_ids. Only an internal
implementation strategy with a complete proof/write contract may use
`implementation-resolvable` at the implementation stage. An unresolved
`external-owner` or `blocking` item in current scope blocks that scope; an
artifact author's `blocking=false` cannot override the rule. Deferral never
subtracts current obligations from final coverage. An actual scope change must
use the existing explicit source/scope decision path.

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
