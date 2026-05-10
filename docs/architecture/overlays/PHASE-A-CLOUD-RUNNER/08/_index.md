---
PRD-ID: PHASE-A-CLOUD-RUNNER
Title: Phase A Cloud Runner Architecture Index
Arch-Refs: [CH01, CH02, CH03, CH04, CH06, CH07, CH09, CH10, CH11]
Updated: true
---

# Phase A Cloud Runner Architecture Index

This overlay records the Phase A architecture for hosting the existing repository workflow on a single Windows ECS machine.

Authoritative inputs:

- Requirements: `execution-plans/2026-05-10-phase-a-cloud-runner-requirements.md`
- Roadmap: `docs/workflows/cloud-platform-evolution-plan.md`
- Base architecture index: `docs/architecture/base/00-README.md`
- ADR index: `docs/architecture/ADR_INDEX_GODOT.md`

Architecture documents:

- `08-Phase-A-Cloud-Runner-Architecture.md` - component model, deployment topology, execution flows, data ownership, and implementation boundaries.

Placement rule:

- This overlay may define Phase A platform-specific structure and integration decisions.
- Cross-cutting policy remains in base chapters and ADRs.
- Runtime security, test, performance, and delivery thresholds are referenced, not duplicated.
