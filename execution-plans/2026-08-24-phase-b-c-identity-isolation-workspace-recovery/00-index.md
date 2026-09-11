# Phase B/C Identity Isolation and Workspace Recovery

> Current repair entry: [implementation-repair-input.md](implementation-repair-input.md) and [LOCAL-HANDOFF.md](LOCAL-HANDOFF.md).
> The 2026-09-11 code review found incomplete semantic coverage and disconnected production boundaries.
> Complete canonical VDD repair before Quick Dev; the historical lifecycle/next-action text below does not establish readiness for this repaired scope.
> This navigation update publishes no lifecycle transition. Historical mapping, authorization and terminal evidence remain unchanged.

- Title: Phase B/C Identity Isolation and Workspace Recovery
- Status: implementation-authorized
- Profile: `resumable` — dependent identity, Runner, Snapshot, Restore, and API slices cross sessions but do not modify the VDD/Quick Dev/Acceptance control plane.
- Branch: main
- Git Head: dcd3cc04051cdb57bde3d40313ba88100ba63b47
- Goal: Implement the accepted Phase B/C identity, execution isolation, Workspace Snapshot, Restore Attempt, and recovery contracts on the current single-node Phase service without expanding into multi-node or frontend rebuild work.
- Scope: Canonical Spec Package `SPEC-phase-b-c-identity-isolation-workspace-recovery` and all six declared companions; PhaseA.Platform plus targeted tests, additive migrations, and required contract docs only.
- Current step: External semantic review is rebound to the current candidate, successor exact-cover is conformant, and maintainer authorization is published; ready for S0 RED.
- Last completed step: Skill-input, knowledge preflight, source-freeze, and repair-round exact-cover projection.
- Stop-loss: Stop on any protected auth/runner/storage boundary conflict, missing required authority, unsafe ownership inference, or failing targeted validation; do not mutate live metadata.
- Next action: Run Quick Dev TDD S0 RED. Authorization does not imply implementation completion, Acceptance, or release.
- Recovery command: Read `00-index.md`, `requirements.v1.json`, `repair/round-1/requirements-acceptance.v1.json`, `repair/round-1/source-freeze.v1.json`, `implementation-slices.md`, `plan-state.v1.json`, `resume-state.v1.json`, and the latest indexed `95-*.md`; resolve semantic review before authorization.
- Open questions: None that change scope. OIDC provider/session mechanics, exact Windows API composition, manifest serialization, storage tables, and migration layout remain implementation-owned seeds constrained by AD-1..AD-13.
- Exit criteria: All active PIWR obligations and PIWR-A01..A18 have an observable acceptance path; targeted tests and one terminal full validation pass; lifecycle remains distinct through acceptance.
- Related ADRs: `docs/adr/ADR-0033-phase-metadata-sqlite-local-disk.md`, `docs/adr/ADR-0034-phase-account-scoped-token-auth.md`, `docs/adr/ADR-0035-phase-controlled-runner-workspace-execution.md`, `docs/adr/ADR-0036-phase-prototype-route-recovery-authority.md`, `docs/adr/ADR-0037-phase-shared-llm-codex-entrypoints.md`, `docs/adr/ADR-0038-phase-evidence-sidecars-readback.md`, `docs/adr/ADR-0039-phase-runtime-caddy-recovery.md`, `docs/adr/ADR-0061-phase-b-c-identity-isolation-workspace-recovery-spine.md`
- Related decision logs: `_bmad-output/specs/spec-phase-b-c-identity-isolation-workspace-recovery/.memlog.md`
- Related task id(s): n/a (no Taskmaster task id linked yet)
- Related run id: n/a (no pipeline run id linked yet)
- Related latest.json: n/a (no task-scoped latest.json pointer resolved yet)
- Related pipeline artifacts: `_bmad-output/specs/spec-phase-b-c-identity-isolation-workspace-recovery/`; `_bmad-output/planning-artifacts/architecture/architecture-phase-b-c-identity-isolation-workspace-recovery-2026-08-23/`
