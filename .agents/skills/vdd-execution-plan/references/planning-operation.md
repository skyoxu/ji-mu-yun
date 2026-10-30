# Create Or Repair A Plan

## Explicit Phase source scope

ADR-0041/0043: an optional public `--source-scope <repository-file.json>`
selects a bounded source route for a Phase task whose protected changes have
already been authorized. It does not grant filesystem permission, authenticate
a user, sign an approval or make a new JSON file an authority. The maintainer
must first resolve real task scope and AGENTS protected-change approval.

The input has exactly `schema: vdd.phase-source-scope.v1`, `task_id`,
`requirements`, `adr`, `authorization`, `write_paths`, `read_paths`,
`support_paths`, and `authorizes: []`. Requirements and authorization each
contain exact repository-relative `path` and raw-byte `sha256`. The ADR also
contains its exact `## ` section heading. The current requirement must contain
that task's Accepted ADR fragment and path; an existing same-workspace task
record must include the task and authorize VDD and Quick Dev TDD. Hash checks
establish integrity, not independent human identity or new approval. Code-span
notation labels in a requirements projection may differ; both raw identities
remain mandatory and are never normalized for hash comparison.

Write/read paths are exact `PhaseA.Platform/*.cs` file paths (nested paths are
allowed). Read paths additionally admit only the existing exact
`PhaseA.Platform/PhaseA.Platform.csproj` and `PhaseA.Platform/packages.lock.json`
production build metadata files, rechecking their existence during consumption.
They may be execution snapshot inputs, never production owners, writes, planned
files, rollback paths or support files. Explicitly selected metadata joins the
existing raw-byte dependency tuple and must be frozen in every slice's execution
snapshots; changed bytes block consumption. This retains the identity algorithm,
cache, resume and repair rules. Support writes are exact test/document files under
`PhaseA.Platform.Tests/`, `scripts/python/tests/`, `tests/` or `docs/`, plus the
exact owning `PhaseA.Platform/README.md`. No
directory, glob, traversal, symlink/junction, runtime or credential-store path
is admitted. The caller selects only necessary source-bound paths; this is not
permission to add unrelated files. Default Toolchain tasks receive no Phase
exception; their existing read-only runtime-source behavior is unchanged, while
runtime writes remain forbidden. A selected Phase route cannot write arbitrary Toolchain files.

Only the public entry loads this input into its private compile context; a
worker/cached candidate cannot self-enable it through payload fields. Ordinary
V3, inline/schema repair and checkpoint validation consult the same context.
All scope/ADR/task-record/requirements dependencies must be in every slice's
execution snapshots. Explicit forbidden paths win for writes and read snapshots,
including after path/write normalization and in final slice/agent-context checks.
Slice cohesion keeps contexts separate when their combined forbidden paths
would reject another context's reads, writes or rollback paths under the same
current route. This preserves exact, prefix and glob exclusions and all atomic
contracts; it never removes a forbidden path to permit a merge.
Context is cleared on return/error; changed dependencies block.
For a selected exact caller route, the compiler preserves authored path roles
instead of applying legacy repair aliases. Both routes retain the existing
finite pytest node-to-file snapshot spelling rule for the same declared or
existing file, preserving the node in command argv. The selected normalizer
then adds only missing current, hash-rechecked scope dependencies to read
snapshots and retains every other contract field. Raw caches and receipts remain unchanged;
the normal strict scope, forbidden-path and semantic gates still decide use.
V3 cache/checkpoint identity includes the scope. Existing explicit fixture-cache
Phase filtering is unchanged; this input is not a fixture-import bypass.
The published semantic bundle also retains the exact source-scope identity.
Completed resume and handoff repair must match that identity, rather than
relabeling an old plan with a changed or absent scope. Final V3 projections
(including repair overlays) and final publication recheck all writes, support
files, frozen dependencies and explicit forbidden paths. Default Toolchain
bundles keep their existing shape when no scope is selected.

Planning consumption includes these real routing dependencies in its required
read scope without turning them into V1 companions or product obligations.
Normal resume keeps its original output, query history and source-content
checks. A genuine scope-input change has a recorded predecessor; do not pad
sources, change IDs or delete records to obtain a fresh budget.

## Interrupted caller-session recovery

Use the normal public compiler with the same requirements, all companions,
out-dir and profile, adding `--resume-from first-failed-stage`. New V1 extraction
stores non-authorizing source-content candidate metadata. The identity retains
the exact section text/ref, interpretation context, extraction prompt and source
role rules. File position/whole-file provenance is rechecked at V0 rather than
used to rerun an otherwise identical section. Advisory query execution metadata
is not source semantics. Candidate schema/source bindings are still revalidated
and V2 runs on the current full set; a cached V1 candidate is never a saved V2
verdict. Missing/changed dependencies can still fail the later owning execution
preflight; this route does not suppress them.

An older interrupted caller-session directory may have raw caches and native
receipts but no new metadata. Select its original transcript explicitly:

```text
py -3 -B scripts/vdd/compile_plan.py --requirements <unchanged-source> --companion <each-original-companion> --out-dir <same-failed-directory> --profile <original-profile> --resume-from first-failed-stage --resume-worker-session <logs/original-session>
```

Use a fresh live caller session for new requests; the original session is a
read-only compatibility witness. It must belong to the same repository/output
scope. Replay requires a returned host result and hash-bound response, original
native output/cache and schema-valid receipt bound to the original input and
prompt. Current normalized content/policy must match, and current native gates
still run. Unknown, timed-out, cancelled or unconsumed responses are not adopted;
corruption or conflicting matching results block rather than selecting a latest
success. There is no fixture-cache import, direct V3 jump or published contract
rewrite. The public result exposes `worker_cache_reuse` counters, which are
diagnostic only. Original witnesses are not rewritten.

Full-domain source-recall caches still bind the actual entire candidate/source
domain and use the existing resolved native receipt checks. A relevant domain
change requires those checks again even when other V1 sections were reusable.
V3 partial contracts retain their existing frozen-domain/native path validators;
an answer file alone is not an accepted contract. Resume continues all required
V3/V4/V5/V6/downstream checks before readiness. Use existing unit budgets, not a
whole-round watchdog, and do not run a real recovery merely to test this route.

## Reference-only planning observation on resume

FR-09 and adopted planning-query AD-8 permit rechecking an already delivered
observation without another query delivery. For the same ordinary native resume,
`--resume-planning-observation-from <logs/session/id/request.json>` selects one
explicit previously returned native V3 group-repair chunk. Other native routes,
recommendation/admission/fixture modes and alternate repair inputs are rejected.
The existing four-field plain `vdd.v3-candidate-repair.v1` authoring input may
combine with this reference only during same-task failed/unpublished ordinary
resume. Extended source-index/test-path/dependency forms, companions, addenda,
published/handoff and V1 replacement/reuse modes are rejected. The native repair
loader, source-ref/target checks, append-only projection, independent V4 and
downstream gates remain mandatory. This neither queries nor redelivers advice,
changes an episode/budget, nor accepts the correction as a worker result.
The original root, output/task, stage/operation, input/scope identity and all
observed/reference source bytes must still match. An old Phase scope cannot
supply a missing or changed current `--source-scope`.

The private VDD check binds the original session/request digest, returned host
response/result, original native output and exact-key chunk cache, and paired
native started/returned call. This route has no per-chunk semantic-worker receipt;
none is synthesized. Existing V1 receipt/replay rules are unchanged. Current
native schema/domain/source checks still apply, and this observation witness
never adopts a cached V3 candidate or replaces any normal compiler gate.

The exact adapter producer row and its original UTF-8 charge must match the
observation in the returned request. Current canonical publication, policy,
projection, configuration and the entire original located/read set are rechecked,
including nested diagnostic candidates when the top-level candidate list is
empty. A valid degraded/source-changed original can remain valid when its
observed worktree hashes still match; it is never relabeled as hit. Unrelated
publication changes do not turn its old index identity into a new query result.

Only a reference/SHA, prior delivery/outcome and current closed-episode fact enter
the existing `planning_source_observations` field. No old query JSON, candidates,
source excerpts or successful query record are delivered again. The compiler privately retains only verified source identity metadata for its
existing consumer-decision writer. After a real validated final candidate or
checkpoint, that writer records accepted/rejected sources and actual scope
impact in the existing execution record. This metadata is never worker context
or a new query/producer-success record; prior delivery alone never means adopted.
The adapter and
its cumulative/repeated-delivery charging are not invoked or changed; closed
stays closed and native unit-budget identity is unchanged. Unknown/new facts,
source changes, revoked access, damaged/unreturned witnesses or an unsupported
route fail closed. A submitted but unconsumed late answer is not returned; an
actually returned historical request does not become invalid merely as its old
deadline passes. The default resume without this explicit option still uses the
original query/closed-episode gate. This option neither renews a timeout nor
authorizes deployment, publication or execution.

## Explicit V3 pause boundary

For ordinary create/resume, add `--stop-after v3` to the same public command.
V3 worker/schema/domain validation, deterministic normalization, V3A semantic
preflight and V3 execution preflight all complete before normal pause. V4 and
all publication/downstream gates remain unexecuted. The result is `paused`,
exit 0, `authorizes=[]`, with a content-bound checkpoint reference; it is not
`plan-ready` or a new lifecycle transition. A timeout/cancel/exception or failed
preflight remains `repair-vdd`, never `paused`.

Only returned native candidates are saved after these checks. Author drafts,
unconsumed responses and injected fixture caches cannot create this checkpoint
through the pause option. Its identity binds repository/output scope, source
index, complete obligations, profile and current V3 rules by content, without
Git-only provenance. It is a revalidatable candidate, not saved permission.
No old cache/receipt or canonical state is rewritten.

Resume with the same inputs/profile/output and `--resume-from first-failed-stage`.
Keep `--resume-worker-session` when the older V1 witness still requires it.
Omit `--stop-after` to continue through V4 and all normal gates, or retain it to
pause again. Current query/security, V0/V2 and both V3 preflights rerun; an exact
checkpoint candidate also passes current V3 schema/domain/execution checks and
normalization before reuse. Invalid current paths block. Source/domain/rule
changes require fresh validation using ordinary matching native caches; a saved
checkpoint does not force an old result into a changed domain. Failed/malformed
matching checkpoints block without replacement author calls. An already
plan-ready directory rejects the pause option rather than downgrading or
relabeling completed state. Ordinary completed-resume semantics are unchanged.

Execution is bounded per independent native unit, not by an aggregate round
deadline: default total 1800 seconds and genuine inactivity 600 seconds. Before
slices exist, source extraction/checks and V3 contract batches are the units.
Retries share the same content-bound cumulative allowance; parent stages do not
charge their children's elapsed time again. The public entry's unit supervisor
retains diagnostics and terminates the owned tree on timeout/cancel. It does not
publish semantic evidence or bypass native cache checks. Do not reuse an old
per-run aggregate watchdog for recovery. See SKILL.md Execution budgets.

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

The configured model is read from `model-routing.toml` beside the active Codex `config.toml`; if that file is absent, the loader uses `config.toml`'s `model` value. Set `CODEX_HOME` when Codex uses a non-default configuration directory.

Select `standard`, `resumable`, or `self-hosted` entirely from the profile table
before model routing. Then pass that already-selected profile to
`scripts/model_routing.py`; do not add another VDD complexity classifier.
All three ordinary profiles and the typed complex-recovery route currently
request `configured Codex model/high`. Complex recovery remains blocked until its exact
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

Successful publication binds atomic recall to the final published obligations.
An older root-level `atomic-recall-alignment.v1.json` remains immutable when
its value differs. The current compiler result names the validated alignment;
the plan-hash-keyed binding under `.compiler-attempts/` lets resume and explicit
predecessor repair resolve the same witness without scanning for a latest file.
Legacy plans without this binding retain their canonical witness validation.

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
worker fixtures, recommendation-only or execution-only handoff
repair. It does not extend repair budgets or permit skipping a failed V4.

For an ordinary failed/unpublished candidate, the bounded test-path form adds
`source_index_sha256` and `test_path_replacements` (an exact old-to-new path
map) to the same JSON object. Pass every original `--companion` explicitly;
there is no automatic recovery of omitted inputs. The compiler rebuilds the
source index and checks its complete identity before any worker. Every supplied
companion must have its complete byte hash bound in that index; an input format
that drops a companion is rejected, not silently summarized.

This V3 test-path form applies only ownerless constraint/governance test-path corrections
before the first V3 execution-contract gate, including cached schema-repair
results. Only selector file prefixes, allowed/snapshot/planned test paths and
exact validation argv path tokens may change. All other fields must match the
original candidate; changing an oracle, kind, owner or production scope fails.
The normal domain, path, ownerless, execution, V4 and publication checks still
run. Append-only receipts record the projected inputs; old caches are not
rewritten. This form cannot be combined with fixtures or recommendation-only.
The legacy four-field correction retains its prior behavior without companions.
This is ADR-0041 authoring input, never permission to replace a stable host.

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

For an observed mixed result inside one published obligation, use the explicit
`--published-v1-split <json>` together with published V3 repair. Replace exactly
one active predecessor obligation by at least two distinct active outcomes bound
to the same exact source. Supply complete per-outcome V3 contracts. Source drift,
cross-source children, predecessor-ID collisions, missing contracts and inactive
targets fail closed. This does not relax V4, atomic recall or downstream gates,
and cannot turn a harness failure into expected RED.

## Source-checked unpublished V1 classification correction

The explicitly authorized `--v1-classification-repair <json>` route permits only
source-supported `quality` to `constraint` corrections on existing frozen IDs.
It requires same-target ordinary unpublished resume and a checked
`--resume-planning-observation-from` reference. It may combine with the existing
four-field plain V3 correction, but not companions, published/handoff/fixture,
recommendation/admission, V1 reuse, extended repair, or V3 pause modes.

The input has exactly `schema: vdd.v1-classification-repair.v1`, `authorizes: []`,
`repository_root`, `task_id` (the original relative output directory),
`requirements_sha256`, `source_index_sha256`, complete current `source_scope`,
`original_obligations_sha256`, and `kind_changes: {existing_oid: constraint}`.
The original-domain digest uses existing `sha256_value` over the complete real
V1 records sorted by `(requirement_id, obligation_id)`. Hashes and source/scope
metadata bind the request; they never prove the claimed classification.

After ordinary V1 replay, an existing read-only `v1-classification-review-*`
worker independently checks the frozen semantic source and original target
records using the existing V1 obligations schema. A runtime/business quality
returned as quality is source-unsupported. Only constraint results with every
other raw and normalized field identical are accepted. Type, status, IDs,
sources, behavior, dependencies and all V3 execution boundaries remain intact.
The compiler writes only an append-only non-authorizing projection; raw V1
caches and original source bytes are not rewritten. Original initialization,
V1 guard/V2, independent recall/V4 and all downstream consumers remain active.

Native semantic/cache and unit-budget identity use canonical source, original
records and old-to-new kind claims, not formatting, filenames, dates or output
directories. Equivalent formatting reuses the same native judgment; it does not
renew an allowance. The closed planning episode remains closed. Classification
cannot manufacture expected RED, ownerless permission, Q4 authority or readiness.
Without this flag, the original flow and classifications are unchanged.

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

Slice dependencies are derived from exact V1 obligation IDs and the original
slice membership. V6 emits this projection. For historical predecessors only,
handoff may fill an omitted `depends_on` field using that immutable graph;
an explicit field (including `[]`) must already match. Successor-authored
edges, prose prerequisites, and shared-owner guesses cannot become authority.
Dangling edges and obligation or slice cycles fail closed. Scope comparison
still protects all obligations, oracles, owners, membership and terminal
predicates; this compatibility rule grants no additional semantic repair.

Publication and current consumption reject production/snapshot overlap, missing
primary authorable pytest entry, and missing RED roles for eligible behavior.
A constraints/governance failure still blocks; never manufacture expected RED
just to keep the implementation loop running.

### Declare an already-bound absent test

For a declarations-only defect, use the existing public handoff producer with
one `--handoff-planned-test <repository-relative-test.py>` per explicit path.
Keep the same requirements, predecessor profile and a distinct empty sibling
successor. This mode does not call the normal dedicated-entry/RED-role repair:
it retains commands, selectors, allowed writes, snapshots, owners, obligations,
full Acceptance/oracles, roles, memberships, dependencies and terminal predicates.
Only affected `planned_new_files` and derived slice/bundle identities change.

Each requested path must be a normalized missing pytest file under a test
segment, already bound by the owning slice's snapshot, pytest argv and selector.
It must not be a production/rollback owner or overlap one, be forbidden by any
owning context, exist, be tracked in HEAD/index (including staged deletion), or
pass through a symlink. Arbitrary paths and duplicate declarations reject before
a result is changed. A successor leaving another missing snapshot undeclared
also rejects, so partial declarations cannot repeat the Q1 gap. This grants no new GREEN/write scope and restores no old
BMAD-positive tests. Q2 must still author the actual retained-scope tests.

The native producer reuses the valid V1/V4 predecessor and runs its existing
source identity, semantic-scope, dependency, coverage, feasibility and handoff
checks. It publishes a non-authorizing repair report with declared paths and
unchanged commands/roles, plus genuine successor identities. Q1 is unchanged;
run its read-only planned preflight on the actual successor workspace. A valid
planned contract is not a materialized test, observed RED or implementation.
Do not combine declarations with runtime-role, launcher or test-root repair.

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


## Execution preflight and classified repair (2026-10-20)

The public compiler projects the V3 candidate through the existing exact-cover,
slice partition, feasibility, final structural and Quick Dev handoff checks
before V4 Acceptance alignment. V1 source recall may run earlier to stabilize
the obligation domain; it is not an Acceptance review. Final gates still run
on the actual candidate after semantic repair.

An execution failure returns `stage=V3-execution-preflight` and
`repair_class=execution-contract`. Its content-addressed diagnostic under
`.compiler-work/execution-preflight/` retains obligations, Acceptances, failures,
hints, findings and `authorizes=[]`. Correct the named contract through the
existing source-bound V3 repair input. Do not keep rerunning V4, change unrelated
contracts, or infer owners from test filenames. Empty production-owner arrays
are structurally representable in ordinary and grouped V3 output, but only a
bounded test-only governance/constraint guard without expected-red or production
rollback scope passes the shared semantic rule.

`consumer_warnings` with `code=planned-production-first-use` identify slices
whose declared future production owners are absent. This is a conservative
handoff warning, not proof that every slice is blocked: a predecessor may create
the owner, or an existing executable may support a legitimate behavioral RED.
Quick Dev must confirm that route before implementation. VDD never seeds
production in Q2 or treats ImportError as behavioral RED. These warnings do not
change historical publications or grant execution authority.

Normal workers, V3 grouped repair, V4 domain recall and source-gap chunks share
one transport policy. Only positively identified transient service errors
receive bounded retries (at most three, or a smaller caller budget).
Configuration/auth/unknown failures, timeout and cancellation stop without
schema repair or timeout-driven group fan-out. Explicit host stops preserve
exit 124/130. Failed output remains diagnostic; successful parsed child caches
remain reusable on resume. Successful but malformed responses retain the
existing one-shot schema repair; semantic gaps retain bounded semantic repair.

For semantically unchanged published plans with execution-only defects, use
`--repair-quick-dev-handoff-from`. It checks exact semantic projection and
reuses bound V1/V4 witnesses. Semantic changes still require V4 and complete
final coverage. This change introduces no new reviewer or review cache.

An explicit runtime-role-only repair keeps already valid execution bindings.
Whole-plan test rebinding is used only for actual binding conflicts. For a
shared multi-file test surface, each existing file's markers are checked against
its own declared domain. Prose source prerequisites remain in obligations and
are not invented as obligation-ID graph edges. Source-index verification and
republication retain the producer's entries/companions identity shape.

## Explicit static primary binding repair

ADR-0041: with `--repair-quick-dev-handoff-from`, repeat
`--handoff-static-primary-slice <slice-id>` only for explicitly selected slices
whose already-bound primary pytest module has a redundant simple OR filter.
The current import-free CER parser must completely map every required assertion,
and every mapped function must remain inside the old filter. The mode removes
only that primary `-k` filter; all other fields/commands, requirements, oracles,
owners, write scopes, roles and dependencies remain unchanged. Q6/terminal
retain the full module. Unknown/missing/unsafe/forbidden targets, symlinks,
unsupported argv or incomplete mappings reject; no arbitrary command is accepted.
It cannot combine with other handoff modes. Default repair remains unchanged.
The normal native predecessor/source/semantic/feasibility gates and successor
publication remain mandatory, with V1/V4 reused and no model/execution evidence
created. A repaired binding is not behavioral verification.
