# Skill Authoring Standard Execution Plan

- Status: `plan-ready`
- Profile: `self-hosted`
- Profile reason: this package introduces a repository-wide Skill contract,
  controlling validator semantics, capability-conditioned safety checks, and
  future Skill acceptance gates.
- Plan ID: `skill-authoring-standard`
- Source requirements: `docs/workflows/skill-control-plane-evolution-requirements.md#Package-A-Skill-Authoring-Standard`
- Git baseline: `49c5cff216646cf82179d906db60426d5f1ef314`
- Baseline tree: `bb82574606412a36a235a9c8ab49a1cc1b2a246e`
- Current step: Bootstrap Round 3 finalized `blocked`; deterministic repair is
  complete and the lineage is in `manual_pause`. Implementation remains
  unstarted and unauthorized.
- Recovery command: `py -3 -B execution-plans/2026-08-06-skill-authoring-standard/tools/validate_plan.py`

## Outcome

Create one accepted repository standard and deterministic validator that
governs future and migrated non-BMAD, non-Chapter-2-7 Skills. The standard
must express scope, single responsibility, input/output contracts, three
branch-distinct examples, conditional routing diagrams, dependencies,
references, scripts, tests, FAQ reachability, version lookup, and capability-
conditioned safety rules without changing existing Skill authority.

## First-Class Directory Boundary

This plan owns only Package A. It does not create or repair Package B and does
not modify any existing Skill package. Package B is a separate acceptance
target; delivery-loop orchestration is outside this plan.

## Authority

Authority order:

1. `AGENTS.md` and `README.md`.
2. Accepted ADR-0041, ADR-0043, ADR-0048, and ADR-0057.
3. `docs/standards/repository-maintenance-agent-protocol.md`.
4. `docs/workflows/skill-control-plane-evolution-requirements.md` Package A.
5. This plan's frozen source and machine contracts.
6. Explanatory prose and historical evidence.

The authority manifest also binds the exact hashes of the external VDD
knowledge preflight and Quick Dev contract validators before this plan invokes
either executable.

This plan may add ADR-0060 as an implementation artifact. A Proposed ADR is
not implementation authority until accepted.

## Scope

Production/documentation:

- `docs/standards/skill-authoring-standard.md`
- `docs/adr/ADR-0060-repository-skill-authoring-contract.md`
- `docs/architecture/ADR_INDEX_PHASE.md`
- `scripts/sc/config/skill-authoring-standard.v1.json`
- `scripts/sc/schemas/skill-quality-contract.v1.schema.json`
- `scripts/sc/schemas/skill-quality-result.v1.schema.json`
- `scripts/sc/validate_skill_quality.py`
- `scripts/sc/skill_quality_examples.py`

Tests and fixtures:

- `scripts/sc/tests/test_validate_skill_quality.py`
- `scripts/sc/tests/test_skill_quality_examples.py`
- `scripts/sc/tests/fixtures/skill-quality/**`

Plan-local artifacts and validation tools under this directory are also in
scope. All output is repository-relative and machine-independent.

## Forbidden Changes

- `.agents/skills/**` existing package contents, including all five Package B
  targets.
- `.agents/skills/bmad-*/**`, `.agents/skills/gds-*/**`, and
  `.agents/skills/workflow-chapter*/**`.
- `PhaseA.Platform/**`, `PhaseA.Platform.Tests/**`, `runtime/phase-a/**`,
  `logs/phase-a-innernet/**`, `knowledge/indexes/current.json`, live database,
  hosted workspaces, authentication, Caddy, and shared LLM entrypoints.
- Secrets, real token material, user-profile paths, absolute machine paths,
  automatic publication, commit, release, deploy, or archive.

## Implementation Order

`SAS-S0 -> SAS-S1 -> SAS-S2 -> SAS-S3`

- `SAS-S0`: normative standard, accepted ownership ADR, contract vocabulary,
  and RED fixtures.
- `SAS-S1`: machine-readable contract schemas and deterministic validator.
- `SAS-S2`: capability-conditioned security checks, example replay, FAQ
  reachability, and validator tests.
- `SAS-S3`: migration policy, repository integration bindings, terminal full
  replay, and documentation closure.

Only `SAS-S3` may publish `implementation-complete`, and only after the
terminal validator replays the command IDs explicitly listed in
`command-registry.v1.json` for Package A tests and the standard package
validator. Acceptance remains owned by
`run-refactor-implementation-acceptance`.

## Validation

- Draft: `py -3 -B execution-plans/2026-08-06-skill-authoring-standard/tools/validate_plan.py --allow-draft`
- Plan-ready: `py -3 -B execution-plans/2026-08-06-skill-authoring-standard/tools/validate_plan.py`
- Plan tests: `py -3 -B -m unittest discover -s execution-plans/2026-08-06-skill-authoring-standard/tools/tests -p test_*.py`
- Future terminal implementation predicate:
  `py -3 -B execution-plans/2026-08-06-skill-authoring-standard/tools/validate_implementation.py`

## Repair Round 3

- Predecessor: `logs/ci/2026-08-07/bootstrap-review-skill-authoring-standard-r2`
  (finalized `blocked`; five confirmed P1 and one refuted candidate).
- VDD closure: `repair/round-3/repair-closure.json`.
- Repair evidence binds complete baseline/candidate manifests, generated
  root-cause callsite inventory, and the controlled producer/consumer receipt
  under `logs/tdd-adapter/skill-authoring-standard/repair-round-2/`.
- The repair is plan-local and non-authorizing. It does not grant a new
  semantic review, implementation authorization, acceptance, release, or
  archive authority.

## Deterministic Repair After Round 3

- Predecessor: `logs/ci/2026-08-07/bootstrap-review-skill-authoring-standard-r3`
  (finalized `blocked`; 14 confirmed P1 findings).
- VDD closure: `repair/round-4/repair-closure.json`. The name identifies the
  fourth in-place repair batch, not a fourth Bootstrap semantic round.
- The closure replays its root-cause inventory and registered
  producer/consumer composition command, binds the exact blocked Round 3
  envelope, and records current/baseline content manifests.
- The stable lineage remains `manual_pause`; no new Bootstrap discovery route,
  implementation authorization, acceptance, release, or archive authority is
  created by this repair.

All plan outputs carry `authorizes=[]` except the VDD-owned `plan-ready`
state. No plan artifact authorizes implementation, acceptance, release, or
archive.
