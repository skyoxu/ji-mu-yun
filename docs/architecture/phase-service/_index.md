# Phase Service Architecture Index

Status: Living architecture notes
Language: English
Scope: Phase A/B platform service, Phase browser-consumed prototype routes, and Phase C evolution constraints.

## Purpose

This folder explains why the Phase service is designed the way it is. It is intentionally lighter than a full arc42 overlay and is optimized for humans and AI agents that need to preserve architectural boundaries while changing code.

These notes are a derived rationale and navigation layer. They do not replace canonical decisions. If this folder disagrees with an accepted ADR, the Phase A overlay, or an explicitly scoped Phase B/C workflow decision, the ADR or source workflow document wins and this folder must be corrected.

Use these notes together with:

- `README.md` for product overview and startup entry.
- `AGENTS.md` for non-negotiable agent operating rules.
- `docs/architecture/ADR_INDEX_PHASE.md` for Phase service ADRs.
- `docs/standards/_index.md` for the standards index.
- `docs/standards/phase-service.md` for API, database, error, logging, security, testing, and status conventions.
- `docs/standards/godot-engine-semantics.md` for Godot runtime semantics, viewport modes, feature-family reading gates, and reference example rules used by hosted implementation routes.
- `docs/standards/godot-ui-capability-contract.md` for Godot UI capability domains, profiles, workflow injection points, and UI closure governance.
- `docs/standards/godot-ui-style-contract.md` for Godot UI style catalog, component coverage, style selection, and drift taxonomy.
- `docs/architecture/overlays/PHASE-A-CLOUD-RUNNER/08/08-Phase-A-Cloud-Runner-Architecture.md` for the original Phase A overlay.
- `docs/workflows/phase-b-account-isolation.md` for the completed Phase B account-isolation slice.
- `docs/workflows/phase-b-agf-godogen-absorption.md` for Phase B machine-closed evidence and prototype-route governance direction.
- `docs/workflows/phase-c-platform-hardening-and-agent-asset-governance.md` and its backlog for Phase C hardening and governance roadmap.

## Source Baseline

Last reviewed for this architecture set: 2026-06-28.

Primary sources scanned:

- `PhaseA.Platform/**` and `PhaseA.Platform.Tests/**`.
- `runtime/phase-a/**`.
- `scripts/python/phase_a_*.py`, `scripts/python/phase_b_*.py`, `scripts/python/run_prototype_workflow.py`, and `scripts/python/run_prototype_tdd.py`.
- `scripts/sc/_llm_backend.py` and `scripts/sc/tests/test_llm_backend.py`.
- `docs/architecture/overlays/PHASE-A-CLOUD-RUNNER/08/**`.
- `docs/workflows/phase-b-account-isolation.md`.
- `docs/workflows/phase-b-agf-godogen-absorption.md` and `docs/workflows/phase-b-agf-godogen-implementation-backlog.md`.
- `docs/workflows/phase-c-platform-hardening-and-agent-asset-governance.md` and `docs/workflows/phase-c-platform-hardening-and-agent-asset-governance-backlog.md`.
- `docs/workflows/cloud-platform-evolution-plan.md` and `docs/workflows/cloud-user-telemetry-and-feedback-plan.md`.

## Reading Order

1. `system-overview.md`
2. `auth-and-accounts.md`
3. `metadata-db.md`
4. `hosted-workspaces-and-artifacts.md`
5. `prototype-routes-and-recovery.md`
6. `llm-codex-execution.md`
7. `runtime-caddy-and-recovery.md`
8. `audit-evidence-and-logs.md`
9. `roadmap-and-hardening.md`

## One-Sentence Architecture Rule

The Phase service is a hosted product shell around repository-native game-prototype workflows: scripts and route contracts own execution truth; the platform hosts, scopes, queues, records, reads back, and recovers that truth.

- Diagnostic spool, failure-family taxonomy, preview/package readiness, interaction-region evidence, and resource lifecycle rules are standardized in `docs/standards/godot-diagnostics-quality-gates.md` and implemented by `PhaseA.Platform/Workflow/GodotDiagnosticsQualityGate.cs`.

- GDD-to-module phase prerequisites, route dependency matrix, and phase exit review evidence are standardized in `docs/workflows/phase-a-gdd-to-module-implementation-phases.md` and implemented by `PhaseA.Platform/Workflow/GddToModuleImplementationPhases.cs`.

- GDD-to-module risk register, DoD layering, ADR/decision evidence, and open-question defaults are standardized in `docs/workflows/phase-a-gdd-to-module-risk-dod-open-questions.md` and implemented by `PhaseA.Platform/Workflow/GddToModuleRiskDodOpenQuestions.cs`.

- GDD-to-module recommended first-slice ordering, full-target capability consumption schedule, source-history gate, and full-target ledger closure rules are standardized in `docs/workflows/phase-a-gdd-to-module-first-slice.md` and implemented by `PhaseA.Platform/Workflow/GddToModuleFirstSlice.cs`.

- GDD-to-module global review authority, review modes, mechanical checks, prior-finding ledger validation, and output contract are standardized in `docs/workflows/phase-a-gdd-to-module-global-review-standard.md` and implemented by `PhaseA.Platform/Workflow/GddToModuleGlobalReviewStandard.cs`.

- GDD-to-module split-added hardening requirements, coverage statuses, owner-doc refs, and phase review coverage rules are standardized in `docs/workflows/phase-a-gdd-to-module-split-added-requirements.md` and implemented by `PhaseA.Platform/Workflow/GddToModuleSplitAddedRequirements.cs`.

- GDD-to-module original source coverage, split output inventory, source-history boundary, and no-gap/no-overlap audit rules are standardized in `docs/workflows/phase-a-gdd-to-module-original-split-audit.md` and implemented by `PhaseA.Platform/Workflow/GddToModuleOriginalSplitAudit.cs`.

- GDD-to-module compact source coverage ranges, audit-range parity, JSON fixture source coverage, and split-added boundary rules are standardized in `docs/workflows/phase-a-gdd-to-module-source-coverage-map.md` and implemented by `PhaseA.Platform/Workflow/GddToModuleSourceCoverageMap.cs`.
