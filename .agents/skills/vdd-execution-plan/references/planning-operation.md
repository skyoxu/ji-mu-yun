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

## Bounded V3 cache repair

For an unchanged frozen input, resume the original failed output directory with the canonical compiler's `--resume-from first-failed-stage`. Keep its disk caches; `--worker-cache` is explicit fixture injection and is not a resume-cache selector. An invalid inline V3 chunk is checked per obligation so valid peer contracts are retained and only invalid contracts are requested again. Invalid cache bytes remain in sidecars. Missing-selector diagnostics guide the worker but never create path authority or relax execution-contract validation. A changed source identity still requires its affected stages to be revalidated; there is no V3-only bypass.


## Execution-only handoff repair

Use the public compiler's `--repair-quick-dev-handoff-from` only for a
hash-bound plan-ready predecessor with valid semantic alignment and exact
atomic recall. Keep the original requirements path and choose a distinct empty
successor under the same repair scope. Do not combine this with worker caches,
resume, companions, V1 reuse overrides or V4 repair overrides.

The mode retains obligations, oracles, assertions, slice membership, production
owners and terminal predicates. It declares dedicated pytest authoring entries,
separates frozen tests from production writes and adds missing expected-red
roles only for eligible executable behaviors. It records every original command
and its retained regression or bounded-test oracle replacement. Quick Dev must
author those real tests; VDD creates no test placeholders or execution evidence.

The successor report explicitly records reused V1/V4 checks and the exact
unchanged semantic projection. A stale source byte hash can be rebound only
when the entire current text equals all frozen source entries; changed source
meaning or dropped text requires ordinary recompilation. New deterministic
source, semantic preflight, exact cover, feasibility and handoff checks must
pass. The predecessor, caches, prior failures and C3 approvals stay unchanged.

Publication and current consumption reject production/snapshot overlap, missing
primary authorable pytest entry, and missing RED roles for eligible behavior.
A constraints/governance failure still blocks; never manufacture expected RED
just to keep the implementation loop running.

### Slice-local runtime-role correction

If a real machine assertion was excluded only because its requirement is
categorized Governance or its diagnostic family is non-RED, first review the
actual production entry and bound acceptance oracle. Then explicitly select
its existing failure intent using `--runtime-red-intent` together with
`--repair-quick-dev-handoff-from`. This variant appends a separate expected-red
intent with the same runtime marker, preserves the original diagnosis and
changes only selected slice contexts. It does not re-author other selectors
or rerun semantic workers. Never use it for a missing human approval, Trust
Approval, Consumer exception, setup failure or invalid execution evidence.
Only fresh controlled probe/RED case evidence can authorize implementation.
