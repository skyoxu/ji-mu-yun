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
All three ordinary profiles and the typed complex-recovery route currently
request `gpt-6-sol/high`. Complex recovery remains blocked until its exact
backend/model/effort/sandbox capability probe and shadow predicate both pass.
Free-form recovery reasons fail closed.

The emitted route decision is hash-bound and non-authorizing. The shared
workflow launcher alone may start a child process. In `observe_only`, continue
planning in the current caller session; the decision neither launches a child
nor replaces that session's model.

The canonical policy owns VDD's independent consumer enablement. A disabled
VDD consumer emits `disabled` without changing Quick Dev or Refactor
Acceptance. Sol/high recovery evidence is loaded only from policy-bound
path/hash references under the controlled capability-evidence root. Callers
cannot supply or synthesize a capability-proof dictionary; activation requires
the bound producer receipt, its successful process result, and representative
shadow execution receipts to replay against the requested route identity.

## Bounded V3 cache repair

For an unchanged frozen input, resume the original failed output directory with the canonical compiler's `--resume-from first-failed-stage`. Keep its disk caches; `--worker-cache` is explicit fixture injection and is not a resume-cache selector. An invalid inline V3 chunk is checked per obligation so valid peer contracts are retained and only invalid contracts are requested again. Invalid cache bytes remain in sidecars. Missing-selector diagnostics guide the worker but never create path authority or relax execution-contract validation. A changed source identity still requires its affected stages to be revalidated; there is no V3-only bypass.


## Explicit V3 candidate correction

When V4 finds a wrong executable binding that cannot be repaired as Acceptance
wording, the canonical compiler accepts `--v3-contract-repair <json>` for a
failed or unpublished output directory. This is reviewed authoring input, not
a worker result or readiness receipt. The input contains
`schema: vdd.v3-candidate-repair.v1`, the exact requirements byte hash in
`requirements_sha256`, `authorizes: []`, and `obligation_contracts` using the
existing V3 inline contract shape. Each selected ID retains its frozen source
references; supply its complete Acceptance, failure intents and slice hint.

Resume the original failed directory and retain its caches. Only named
contracts are replaced after cache replay; source extraction and unrelated
contracts are unchanged. The compiler recalculates Acceptance/RED identities,
checks normal V3 execution contracts, and requires independent V4 and all
downstream gates before publication. Missing final targets or unconsumed
corrections fail closed. Projection sidecars preserve the exact correction
input without rewriting old worker output. Do not combine this option with
worker fixtures, companions, recommendation-only or execution-only handoff
repair. It does not extend repair budgets or permit skipping a failed V4.

For a published plan-ready predecessor, add `--repair-published-v3-from` and
use a distinct empty sibling successor with the predecessor profile. The
predecessor source bytes, bundle identity, semantic chain, V4 alignment and
atomic recall must validate before reuse. The compiler reconstructs the
published per-obligation V3 contracts and verifies unchanged identities; it
never copies an old worker cache into the successor. Only the named corrected
contracts change. Unselected Acceptance, failure intents and execution hints
must remain identical or the successor is rejected. V1 is revalidated against
the published source and recall, while V4 and all downstream gates run anew.
If fresh atomic recall reports a source gap, this mode returns `repair-vdd`
with the claims; it does not silently expand V1 or request unrelated V3
contracts. A genuine gap requires a separately scoped source/V1 decision.
The prior plan, prior caches and Quick Dev runs remain immutable. This mode
cannot combine fixtures, companions, resume, recommendation-only, V1 override,
V4 approval override or handoff-only repair.

For a reviewed published-predecessor source-gap decision, add
`--published-v1-gap-extension <json>` to that mode. Its exact source bytes,
`authorizes=[]`, two new active FR-4 V1 obligations, and matching complete V3
inline contracts are validated before compilation. It cannot import a model
failure log as authority. The compiler reuses all predecessor V1/V3 peers,
applies only the named V3 corrections and the two additions, and runs V4 and
downstream gates independently in a new empty sibling. Any further source gap
returns `repair-vdd`; do not widen the extension or repeat all V3 chunks
without a separate reviewed source decision.

For a normative contradiction in frozen V1 semantics, the separate
`--published-v1-replacement` input is required. It is source-bound,
non-authorizing, and must provide complete V3 inline contracts for each new
obligation ID. Replacement is limited to explicitly named obligations;
unselected V1/V3 peers remain semantically stable. An input without complete
contracts fails closed, and no historical worker output is promoted.

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
