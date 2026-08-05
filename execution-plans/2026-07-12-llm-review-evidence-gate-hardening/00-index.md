# LLM Review Evidence Gate Hardening - Revised Execution Plan

- Status: `draft`
- Profile: `self-hosted`
- Plan ID: `llm-review-evidence-gate-hardening`
- Repair: `repair/round-1`
- Git baseline: `2154485bc07e1fe6c8830b350492fc107e3dc61a`
- Current authority: `docs/standards/bootstrap-review-control-plane.md` and `.agents/skills/run-phase-bootstrap-review/`
- Recovery command: `py -3 execution-plans/2026-07-12-llm-review-evidence-gate-hardening/tools/validate_revised_plan.py`

## Current Outcome

The original 7-12 plan has already produced the repository-owned Bootstrap
Review control plane and its compatibility artifacts. This repair removes the
completed, cancelled, relocated, and duplicated work from the active
implementation queue. The remaining outcome is intentionally narrow:

1. close the legacy 7-12 compatibility surface without adding durable behavior
   to the old plan-local CLI;
2. add a read-only, baseline-informed recommendation for complete finding-mode
   re-entry after Round 1;
3. add reviewed promotion, version binding, fallback, and rollback for
   Bootstrap cost calibration candidates;
4. inventory active formal review entrypoints and make a declared high-risk
   Toolchain caller delegate to the repository Bootstrap owner when that
   caller has already selected complete semantic review;
5. keep ordinary low-risk AI-led, single-maintainer work on the existing
   lightweight route.

The plan does not recreate finding schemas, the Bootstrap runner, lineage,
focused repair verification, exact envelope reuse, Refactor Acceptance's
toolchain domain, or compact-VDD projection. Those are current repository
capabilities and regression inputs.

## R4 Relocation

Original Phase R4 is relocated to
[`2026-07-11-phase-frontend-boundary-hardening-execution-plan`](../2026-07-11-phase-frontend-boundary-hardening-execution-plan/00-index.md).
The receiving plan uses existing `PBR-026`, `PBR-044`, `PBR-024`, and
`PBR-062` rather than creating a second review authority. BH-SF2 owns the
Phase/Hosted adapter and preflight binding, BH-SF3 owns mutation and acceptance
recovery, and BH-PILOT owns first route observation. The adapter consumes a
fresh repository Bootstrap finalized-run validation envelope; it does not copy
Bootstrap schemas, routing, lifecycle, finding memory, or cost policy.

7-07 receives no R4 work. Its planned large Phase workflow refactor remains
independent of Toolchain review-control implementation.

## First-Class Directory Boundaries

### Existing 7-31 Evidence Catalog

[`2026-07-31-toolchain-workflow-evidence-catalog-v1`](../2026-07-31-toolchain-workflow-evidence-catalog-v1/00-index.md)
owns pull-only producer adapters, native evidence identities, immutable
generations, Current/LKG publication, bounded queries, and derived catalog
recovery. This plan does not implement or depend on that catalog at runtime.
New 7-12 outputs remain producer-native evidence that a later accepted Catalog
adapter may index without gaining review authority.

### TC-D1 From `docs/know.md`

The next new VDD directory owns portable core-Skill validator resolution,
historical compatibility replay, and non-authorizing evaluation seeds for the
three 8-01 repair families. This plan does not create that directory, copy its
seeds, or implement its generic replay capability. Implementation of this
revised 7-12 waits for TC-D1 `acceptance-passed` so every Bootstrap Skill delta
can carry a distinct Evaluation delta through the portable mechanism.

### Future Evaluation Baseline

Cross-Skill Anchor/Frontier/Challenge/Holdout sets, label provenance, Pareto
comparison, workflow observability, Miner, memory, version governance, and RL
remain in the independent directories reserved by `docs/know.md`. In
particular, 7-12 does not create TC-D3's `ordinary_fast_ship_combined` mode,
eligibility cohorts, or shadow activation, and it does not create TC-D6's core
Skill version promotion or Git rollback workflow. A Bootstrap cost calibration
is an operational estimate, not a Skill quality baseline or Skill version.

## Active Slices

1. `RFG2-S0`: legacy authority closure and active-entrypoint census.
2. `RFG2-S1`: baseline-informed finding-mode re-entry recommendation.
3. `RFG2-S2`: reviewed cost-calibration promotion and rollback.
4. `RFG2-S3`: selective high-risk routing and terminal migration replay.

The detailed behavior, RED/legacy paths, GREEN commands, dependents, and
recovery actions are owned by `implementation-contract.v2.json`.

## Lifecycle

`draft -> plan-ready -> implementation-authorized -> implementation-complete -> acceptance-passed -> archived`

This repair remains `draft` while the mandatory VDD knowledge preflight is
blocked by a stale Current Catalog and uncommitted changes to the knowledge
publication controls. The blocked Locator result grants no authority. VDD
cannot publish a knowledge generation. After the controls match current main,
the maintainer must separately confirm a target-bound publication request and
`maintain-knowledge-base` must publish the fresh generation. VDD may then
freeze `knowledge-context.v1.json` plus its receipt, run the terminal plan
validator, and only then publish `plan-ready`.

## Current And Historical Artifacts

- Current requirements: `requirements.v2.json`.
- Current implementation contract: `implementation-contract.v2.json`.
- Current command registry: `command-registry.v2.json`.
- Non-authorizing VDD route decision: `model-route-decision.v1.json`.
- Current lifecycle/resume state: `plan-state.v1.json`.
- Current scope rationale: `10-current-scope-revision.md`.
- Repair record: `repair/round-1/repair-plan.md`.
- Append-only continuity: `95-implementation-evolution-and-completion-report.md`.
- Historical compatibility books: `01` through `09` and `96` through `99`.
- Historical compatibility adapter: `implementation-contract.v1.json`,
  `tools/run_bootstrap_review.py`, schemas, fixtures, and profile snapshot.

Historical compatibility artifacts remain readable and byte-preserving. Their
old `active` labels are historical source-state, not the current implementation
queue. `requirements.v2.json` is the current disposition authority.

兼容性不变量：7 月 7 日既有历史 review run、prompt、输出和 ledger 保持不变。
