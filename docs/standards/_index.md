# Standards Index

Status: Living index
Language: English
Scope: Current scope is Phase service standards; future cross-cutting repository standards may be added here.

## Reading Order

1. `docs/standards/phase-service.md` for Phase service API, database, error handling, logging, security, testing, and status conventions.

## Current Standards

- [Phase Service Standards](phase-service.md)

## Maintenance Rules

- Keep this index small. It is a router, not a duplicate standards catalog.
- Add new standards here only when they define cross-cutting team conventions, not one-off feature notes.
- If a standard conflicts with an accepted ADR or a hard rule in `AGENTS.md`, update the standard instead of weakening the higher-authority source.

- When adding a new standards file, update `README.md`, `docs/PROJECT_DOCUMENTATION_INDEX.md`, relevant architecture indexes such as `docs/architecture/phase-service/_index.md`, and any agent-facing routing in `AGENTS.md` when the standard becomes part of normal work.
