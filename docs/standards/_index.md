# Standards Index

Status: Living index
Language: English
Scope: Current scope is Phase service standards; future cross-cutting repository standards may be added here.

## Reading Order

1. `docs/standards/phase-service.md` for Phase service API, database, error handling, logging, security, testing, and status conventions.
2. `docs/standards/godot-engine-semantics.md` for Godot runtime semantics, viewport modes, feature-family reading gates, and official example usage rules.
3. `docs/standards/godot-ui-capability-contract.md` for Godot UI capability domains, profiles, workflow injection points, and UI closure governance.
4. `docs/standards/godot-ui-style-contract.md` for Godot UI style catalog, style selection, component coverage, and drift taxonomy.
5. `docs/standards/godot-ui-style-closure.md` for style-aware UI closure, style repair prompt inputs, and final-readiness style gates.
6. `docs/standards/godot-ui-style-schema-acceptance.md` for deterministic style snapshot schema acceptance gates.
7. `docs/standards/godot-diagnostics-quality-gates.md` for Godot/Phase diagnostics, project diagnostic spool, failure-family taxonomy, preview/package quality gates, interaction-region evidence, and resource lifecycle rules.
8. `docs/standards/bootstrap-review-control-plane.md` for Bootstrap Review ownership, execution boundaries, evidence recovery, lifecycle, and repair closure.
9. `docs/standards/repository-maintenance-agent-protocol.md` for repository-maintenance TDD adapter ownership, execution boundaries, and predicate authority.

## Current Standards

- [Phase Service Standards](phase-service.md)
- [Godot Engine Semantics Standard](godot-engine-semantics.md)
- [Godot UI Capability Contract](godot-ui-capability-contract.md)
- [Godot UI Style Contract](godot-ui-style-contract.md)
- [Godot UI Style Closure Standard](godot-ui-style-closure.md)
- [Godot UI Style Schema Acceptance Standard](godot-ui-style-schema-acceptance.md)
- [Godot Diagnostics And Quality Gates](godot-diagnostics-quality-gates.md)
- [Bootstrap Review Control Plane Standard](bootstrap-review-control-plane.md)
- [Repository Maintenance Agent Protocol](repository-maintenance-agent-protocol.md)

## Maintenance Rules

- Keep this index small. It is a router, not a duplicate standards catalog.
- Add new standards here only when they define cross-cutting team conventions, not one-off feature notes.
- If a standard conflicts with an accepted ADR or a hard rule in `AGENTS.md`, update the standard instead of weakening the higher-authority source.

- When adding a new standards file, update `README.md`, `docs/PROJECT_DOCUMENTATION_INDEX.md`, relevant architecture indexes such as `docs/architecture/phase-service/_index.md`, and any agent-facing routing in `AGENTS.md` when the standard becomes part of normal work.
