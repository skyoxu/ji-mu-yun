# Governance-Enabled Operations

Read this guide only for the operation selected in SKILL.md. Commands run from the repository root unless stated otherwise; inline paths retain their original repository/Skill-root meaning.

## In-Place Repair Rounds

The review lineage, semantic-round, callsite-attestation, and repair-closure
rules in this section apply only when governance is enabled. In development,
repair the current plan in place, preserve actual historical TDD evidence, and
invalidate only affected slices and declared downstream dependents; do not
materialize governance successors.

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

When governance is enabled, after mandatory authority reads and before freezing
plan sources, run the mandatory knowledge-consumption sequence in
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
by publishing its missing receipt after an interrupted first attempt. When
governance is disabled, do not run this receipt/freeze protocol; read only the
explicit current sources required by the plan.

## Skill Input Gate

When governance is enabled, after route selection and authority reads, bind
`requirements` for create, or `target_plan` and `repair_finding` for repair.
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
Use the same operation with `vdd_knowledge_preflight.py --skill-input-operation`.

## Candidate, Review, And Reports

Use a declared Git baseline plus current scoped worktree identity for functional
TDD freshness. When governance is enabled, freeze the commit range or complete
scoped identity, bind current contracts, implementation, and validators, and
exclude append-only logs and explanatory reports from normative hashes.
Preserve old evidence as historical after invalidation.

Review exists only when governance is enabled and is then optional unless
requested by the maintainer or a protected-path rule requires it. Batch
accepted findings, run deterministic targeted checks, and do not rerun a
complete semantic review for P2-only findings automatically. Review validates
the supplied requirements or implementation; it is not an unbounded discovery
loop.

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

When governance is enabled, `resumable` and `self-hosted` plans create
`95-*.md` before implementation and add its entry to
`execution-plans/95-implementation-report-index.v1.json` in the same change.
The report is append-only, non-authorizing, records corrections and the final
implementation result, and is excluded from candidate hashes. `standard` may
omit it unless requested. When governance is disabled, every profile omits this
report and index entry.

Keep the package generic. Never read a mutable live execution-plan directory or embed dated plan names, plan-local paths, RMAP IDs, live plan hashes, user-profile paths, or machine-specific paths. Detached fixtures prove package behavior; repository-level tools own live 95-index containment and existence checks.
