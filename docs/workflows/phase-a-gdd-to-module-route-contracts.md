# Phase A GDD-To-Module Route Contracts

Status: Active route governance contract
Language: English
Scope: Browser-consumed Phase A GDD-to-module and downstream prototype routes.

## Runtime Owner

The runtime registry is `PhaseA.Platform/Workflow/RouteModuleContracts.cs`.

The parity fixture is `PhaseA.Platform.Tests/Fixtures/route-module-contracts.v1.json` and is validated by `PhaseA.Platform.Tests/Workflow/RouteModuleContractsTests.cs`.

## Contract Set

The initial contract set covers:

- `gdd-requirements`
- `gdd-document-generation`
- `scene-route-confirmation`
- `structured-game-type-analysis`
- `prototype-contract`
- `prototype-skeleton`
- `workflow-recommendation`
- `ui-wiring-closure`
- `iteration-plan`
- `execute-next-goal`
- `needs-fix`
- `repair`
- `project-delete`

Each contract records owner, canonical route-state path, mirror/cache path if any, descriptor action IDs, API/readback routes, browser entrypoints or display mappings, required source artifacts, source hash fields, status dimension, exposure class, phase eligibility, admin readback surfaces, and deterministic test owners.

## Recovery Source Order

Prompt-producing route contracts must set `recoverySourceOrderRef=hosted-route-recovery-order.v1`. This means route-local authority sources are merged with the hosted route recovery order from `AGENTS.md` and missing required recovery sources fail closed.

Non-prompt routes must set `recoverySourceOrderRef=source_boundary_not_applicable` and record their non-prompt behavior through route state or metadata readback.

## Prototype Contract Authority

`routes/prototype-contract/latest.json` is the canonical prototype contract path. `meta/routes/prototype-contract/latest.json` is only a mirror/readback cache and must match the canonical contract hash when present.

## Descriptor Mapping

Every action ID in route module contracts must exist in `RouteActionDescriptors.cs`. Workflow recommendation readback may emit only canonical descriptor action IDs. Legacy endpoint names, service method names, or browser function names are projections, not canonical recommendation IDs.

## Admin And Diagnostics Readback

Admin review queue, diagnostic spool, and project delete tombstones are metadata DB-owned readback surfaces. Project deletion preserves unresolved governance rows by writing `project_deleted_utc` and a tombstone row. User-facing readback remains account-scoped; admin aggregation remains admin-only and no-store.

## Guard Tests

The route module contract guard tests are deterministic. They do not call LLM, Steam, GitHub, or public network services. They validate registry/fixture parity, descriptor action mapping, status vocabulary ownership, prompt recovery source order, and prototype contract canonical path ownership.
