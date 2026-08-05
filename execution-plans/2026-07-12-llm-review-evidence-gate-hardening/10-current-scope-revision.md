# Current Scope Revision

## Decision Summary

The repository has evolved past the original 7-12 architecture. Durable review
semantics now live in `docs/standards/bootstrap-review-control-plane.md`, and
the executable owner is `.agents/skills/run-phase-bootstrap-review/`. Refactor
Acceptance owns plan-specific acceptance routing and exact finalized-envelope
reuse. The 7-12 CLI and schemas remain compatibility inputs only.

The repair therefore treats the original R0A/R0B and most R1/R2/R5 mechanics
as implemented or superseded by current authority. It cancels the original
R0C/R0D coupling to 7-07/7-11, cancels direct BMAD/GDS customization work,
relocates R4, and rejects the original R6 global-blocking rollout.

## Legacy Disposition

| Legacy scope | Current disposition | Current owner or reason |
| --- | --- | --- |
| R0A/R0B plan-local Bootstrap core | implemented and compatibility-only | Repository Bootstrap Skill, standard, and Accepted ADRs |
| R0C fixed supplemental review of 7-07/7-11 | cancelled | Reviews are target/lineage driven, not permanently bound to dated directories |
| R0D both-upstream handoff prerequisite | cancelled for Toolchain work | Toolchain control-plane evolution is independent of Phase feature completion |
| R1 finding schema and fact gate | implemented/superseded | Current Bootstrap schemas, validators, tests, and standard |
| R2 generic gateway | implemented/superseded | Repository Bootstrap control plane and Refactor Acceptance consumer |
| R3 BMAD/GDS customization | cancelled | Installer-managed BMAD/GDS files and customization are outside this repository-specific core-Skill plan |
| R4 Phase-facing Codex adapter | relocated | 7-11 BH-SF2/BH-SF3/BH-PILOT using existing PBRs |
| R5 broad shadow metrics | split | Bootstrap cost calibration remains here; cross-Skill quality evaluation belongs to TC-D2 |
| R6 global blocking | cancelled/reframed | Only declared high-risk Toolchain entrypoints use mandatory Bootstrap routing |

## Current Repository Capabilities Used As Regression Inputs

- three reviewer layers and independent P0/P1 verification;
- AI-native single-maintainer severity policy;
- bounded semantic rounds, focused repair verification, deterministic closure,
  manual-pause closure, and explicit re-entry authorization;
- process/access proof, profile/model/effort routing, and finalized-run replay;
- `build-review-baseline` history and non-authorizing calibration candidates;
- Refactor Acceptance `toolchain` policy, compact-VDD prerequisite projection,
  thin acceptance routing, and exact envelope reuse.

No current capability is reimplemented in this plan. Each slice begins with a
legacy regression that proves the current owner before adding one missing
behavior.

## Remaining Gaps

### Baseline-Informed Re-entry Recommendation

The current authorization records a caller-supplied `recommendation`,
`confidence`, and rationale. It does not have a deterministic read-only
producer that binds the recommendation to the current lineage projection,
typed trigger, profile/workload cohort, promoted calibration reference,
available baseline history, expected benefit, expected cost, and missing-data
confidence. The new projection remains advisory and carries `authorizes=[]`;
the maintainer may confirm either recommendation.

### Calibration Promotion And Rollback

Bootstrap can build a validated calibration candidate and consume a committed
reference, but the repository lacks one bounded operator workflow that reviews
candidate provenance, publishes a new versioned reference, retains all
run-bound predecessors, selects a conservative fallback, and rolls back the
active reference without deleting failed history. This is operational cost
calibration only. It must not create quality labels or promote itself.

### Entrypoint Census And Selective Routing

The implementation must enumerate active formal review callers in the
repository-owned Bootstrap Skill, Refactor Acceptance, and live `scripts/sc`
surfaces. When a declared high-risk Toolchain caller has already selected a
complete semantic review, it either delegates through the current Bootstrap
owner or is explicitly retired/compatibility-only. The census and router do
not decide that every high-risk change requires semantic review. Ordinary
low-risk AI-led, single-maintainer work remains lightweight. No BMAD/GDS
installed file is modified.

## Non-Overlap Contract

- 7-31 owns evidence catalog identity, adapters, generation, publication, LKG,
  query, and recovery. 7-12 emits only producer-native review evidence.
- TC-D1 owns generic portable Skill validator resolution and the three 8-01
  evaluation seeds. 7-12 consumes that capability only after acceptance.
- TC-D2 owns cross-Skill quality baselines and comparison policy. 7-12 cost
  calibration cannot claim quality, recall, or false-positive labels.
- TC-D3 owns `ordinary_fast_ship_combined`, its shadow-only eligibility
  cohorts, comparison, and activation decision. 7-12 neither creates that mode
  nor changes the ordinary low-risk review topology.
- TC-D6 owns core Skill candidate promotion, stable version publication, and
  Git-backed Skill rollback. 7-12 may version and select only Bootstrap's
  non-authorizing operational cost-calibration reference.
- 7-11 owns Phase account/project/workspace isolation, shared Phase LLM/Codex
  entrypoint integration, route recovery, browser-safe projection, and Phase
  smoke evidence.
- Existing Bootstrap/Acceptance owners retain lifecycle and semantic authority.

## R4 Receiving Contract

7-11 consumes a fresh `bootstrap-finalized-run-validation.v3` envelope only as
a review fact. The Phase adapter binds account, project, workspace, route
action, authority hash, current live acceptance blocker, and browser-safe
projection. It stores account-scoped evidence references and never exposes
host paths or another project's finding/disposition state.

The envelope cannot authorize Permit, Mutation, Acceptance, route success,
browser success, deployment, or release. Missing, stale, non-finalized, or
cross-scope review evidence fails the review-related projection without
inventing a clean result. Phase acceptance continues to follow current route
authority and the latest live blocker.
