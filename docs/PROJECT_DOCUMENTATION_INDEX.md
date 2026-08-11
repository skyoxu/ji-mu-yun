# Project Documentation Index (Ji Mu Yun Phase A/B Platform)

This file is the top-level navigation for project docs.

## Start Order After Context Reset

1. `README.md`
2. `AGENTS.md`
3. `docs/standards/_index.md`
4. `docs/agents/00-index.md`
5. `docs/agents/01-session-recovery.md`
6. `docs/PROJECT_DOCUMENTATION_INDEX.md`
7. `docs/agents/13-rag-sources-and-session-ssot.md`
8. `DELIVERY_PROFILE.md`
9. `docs/testing-framework.md`
10. `docs/agents/16-directory-responsibilities.md`
11. `docs/workflows/prototype-lane.md`
12. `docs/workflows/prototype-lane-playbook.md`
13. `docs/workflows/prototype-tdd.md`
14. Newest file in `execution-plans/`
15. Newest file in `decision-logs/`
16. If available: `logs/ci/<date>/sc-review-pipeline-task-<task-id>/latest.json`

## Authoritative Sources

- Taskmaster triplet: `.taskmaster/tasks/tasks.json`, `.taskmaster/tasks/tasks_back.json`, `.taskmaster/tasks/tasks_gameplay.json`
- PRD: `docs/prd/**`
- ADR: `docs/adr/ADR-*.md`, `docs/architecture/ADR_INDEX_GODOT.md`, `docs/architecture/ADR_INDEX_PHASE.md`
- Base architecture: `docs/architecture/base/**`
- Overlay slices: `docs/architecture/overlays/**`
- Phase service architecture rationale: `docs/architecture/phase-service/_index.md`
- Standards: `docs/standards/_index.md`, `docs/standards/phase-service.md`, `docs/standards/godot-engine-semantics.md`, `docs/standards/godot-ui-capability-contract.md`, `docs/standards/godot-ui-style-contract.md`, `docs/standards/bootstrap-review-control-plane.md`, `docs/standards/repository-maintenance-agent-protocol.md`
- Bootstrap Review ownership ADR: `docs/adr/ADR-0041-bootstrap-review-execution-control-plane-ownership.md`
- VDD clarification recovery ADR: `docs/adr/ADR-0043-vdd-solo-maintainer-clarification-recovery.md`
- Testing rules: `docs/testing-framework.md`
- Delivery/run protocol: `DELIVERY_PROFILE.md`, `docs/workflows/run-protocol.md`, `docs/workflows/local-hard-checks.md`

## Workflow Docs

- Model-visible tool round contract: `docs/model-visible-tool-round-contract.md`
- Model-visible round summary schema: `scripts/sc/schemas/model-visible-tool-round-summary.v1.schema.json`
- Model-visible preflight schema: `scripts/sc/schemas/model-visible-tool-preflight.v1.schema.json`
- Model-visible measurement schema: `scripts/sc/schemas/model-visible-tool-measurement.v1.schema.json`
- Model-visible round validator/producer: `scripts/python/validate_model_visible_tool_round_summary.py`, `scripts/python/build_model_visible_tool_round_summary.py`
- Daily workflow (authoritative execution order): `workflow.md`
- Example bootstrap workflow: `workflow.example.md`
- Chapter 6 optimization guide: `docs/workflows/chapter-6-t56-optimization-guide.md`
- Chapter 7 UI wiring GDD: `docs/gdd/ui-gdd-flow.md`
- Chapter 7 profile guide: `docs/workflows/chapter7-profile-guide.md`
- Chapter 7 orchestrator: `py -3 scripts/python/dev_cli.py run-chapter7-ui-wiring --delivery-profile fast-ship`
- Chapter 7 backlog-gap route: `py -3 scripts/python/dev_cli.py run-chapter7-backlog-gap --design-doc-path <doc> --epics-doc-path <doc> --duplicate-audit-path <doc>`
- Chapter 7 status patch applier: `py -3 scripts/python/dev_cli.py apply-chapter7-status-patch --patch <path>`
- Upgrade guide: `docs/workflows/business-repo-upgrade-guide.md`
- Template upgrade protocol: `docs/workflows/template-upgrade-protocol.md`
- Cloud platform evolution plan: `docs/workflows/cloud-platform-evolution-plan.md` (Phase A hosted runner boundary, Phase B workspace/ACL isolation, Phase C scale-out/strong isolation)
- Phase B AGF/godogen absorption: `docs/workflows/phase-b-agf-godogen-absorption.md` (machine-closed readiness, prototype routes, route ledger, redacted evidence, asset readback, diagnostics, and toolchain probes; excludes human-only acceptance)
- Phase C hardening and agent asset governance: `docs/workflows/phase-c-platform-hardening-and-agent-asset-governance.md` (deferred Phase A/B closure, ECC absorption, conflict resolution)
- Project health dashboard: `docs/workflows/project-health-dashboard.md`
- Local hard checks: `docs/workflows/local-hard-checks.md`
- Stable entrypoint index: `docs/workflows/stable-public-entrypoints.md`
- Script entrypoint index: `docs/workflows/script-entrypoints-index.md`
- Prototype lane: `docs/workflows/prototype-lane.md`
- Prototype lane playbook: `docs/workflows/prototype-lane-playbook.md`
- Prototype TDD: `docs/workflows/prototype-tdd.md`
- Game type route framework guide: `docs/workflows/game-type-route-framework-guide.md`
- Godot official examples index: `docs/reference/godot-official-examples-index.md`
- Godot UI style snapshot schema fixture: `docs/schemas/godot-ui-style-contract.v1.example.json`
- GDD-to-module recommended first slice: `docs/workflows/phase-a-gdd-to-module-first-slice.md`
- GDD-to-module first-slice review schema: `docs/schemas/gdd-to-module-first-slice-review.v1.example.json`
- Full-target UI closure ledger schema: `docs/schemas/full-target-ui-closure-ledger.v1.example.json`
- GDD-to-module global review standard: `docs/workflows/phase-a-gdd-to-module-global-review-standard.md`
- GDD-to-module global review standard schema: `docs/schemas/gdd-to-module-global-review-standard.v1.example.json`
- GDD-to-module split-added requirements: `docs/workflows/phase-a-gdd-to-module-split-added-requirements.md`
- GDD-to-module split-added requirements schema: `docs/schemas/gdd-to-module-split-added-requirements.v1.example.json`
- GDD-to-module original split audit: `docs/workflows/phase-a-gdd-to-module-original-split-audit.md`
- GDD-to-module original split audit schema: `docs/schemas/gdd-to-module-original-split-audit.v1.example.json`
- GDD-to-module source coverage map: `docs/workflows/phase-a-gdd-to-module-source-coverage-map.md`
- GDD-to-module source coverage map schema: `docs/schemas/gdd-to-module-source-coverage-map.v1.example.json`

## Recovery And Stop-Loss

- Workflow golden examples index: `docs/workflows/examples/README.md`
- Canonical recovery command: `py -3 scripts/python/dev_cli.py resume-task --task-id <task-id>`
- Quick recovery recommendation: `py -3 scripts/python/dev_cli.py resume-task --task-id <task-id> --recommendation-only`
- Quick deep-inspect recommendation: `py -3 scripts/python/dev_cli.py inspect-run --kind pipeline --task-id <task-id> --recommendation-only`
- Chapter 6 go/no-go route: `py -3 scripts/python/dev_cli.py chapter6-route --task-id <task-id> --recommendation-only`
- Deep inspection command: `py -3 scripts/python/dev_cli.py inspect-run --kind pipeline --task-id <task-id>`
- Recovery reading order: `docs/agents/01-session-recovery.md`
- Stable recovery/entry routing: `docs/workflows/stable-public-entrypoints.md`
- Sidecar and consumer contract: `docs/workflows/run-protocol.md`

Read these recovery signals before reopening a full Chapter 6 pipeline:

- `latest_summary_signals.reason`
- `latest_summary_signals.run_type`
- `latest_summary_signals.reuse_mode`
- `latest_summary_signals.artifact_integrity`
- `chapter6_hints.next_action`
- `chapter6_hints.blocked_by`
- `recommended_action_why` from `active-task` or project-health when available

High-value interpretation rules:

- `run_type = planned-only` or `reason = planned_only_incomplete` means the newest bundle is evidence-only, not a resumable producer run.
- `artifact_integrity` means you should fall back to the previous real producer bundle before rerunning Chapter 6.
- `recommended_action = needs-fix-fast` usually means the deterministic evidence is already good enough and you should close targeted anchors instead of paying for another full rerun.
- `chapter6-route` is the stable place to turn those signals into an explicit lane decision before you reopen `6.7` or pay for `6.8`.

Current stop-loss families:

- `rerun_guard`
- `llm_retry_stop_loss`
- `sc_test_retry_stop_loss`
- `waste_signals`
- `artifact_integrity`

## Evidence and Logs

- CI and local evidence: `logs/ci/<YYYY-MM-DD>/`
- Review pipeline artifact entry: `logs/ci/<YYYY-MM-DD>/sc-review-pipeline-task-<task>/latest.json`
- Local hard-check latest pointer: `logs/ci/<YYYY-MM-DD>/local-hard-checks-latest.json`
- Project-health latest pointer: `logs/ci/project-health/latest.json`
- Project-health dashboard page: `logs/ci/project-health/latest.html`
- Project-health report catalog: `logs/ci/project-health/report-catalog.latest.json`

- Game Type Guides: `docs/game-type-guides/README.md`
- Prototype Type Kits: `docs/prototype-type-kits/README.md`
- Prototype 7-Day Playable Godot ZH Skill: `.agents/skills/prototype-7day-playable-godot-zh/SKILL.md`

- `docs/standards/godot-diagnostics-quality-gates.md`

- `docs/workflows/phase-a-gdd-to-module-implementation-phases.md`
- `docs/workflows/phase-a-gdd-to-module-risk-dod-open-questions.md`
