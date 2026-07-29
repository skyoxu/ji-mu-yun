# PhaseA.Platform Guide

This file scopes work inside `PhaseA.Platform/**`. It inherits the repository
rules from the root `AGENTS.md` and narrows them to the ASP.NET Core service.
Host startup, Caddy, watchdog, and public recovery are owned by
`runtime/phase-a/AGENTS.md`.

## Purpose

- Maintain the Phase A/B Web/API process, browser surface, account boundary,
  metadata persistence, Hosted route orchestration, LLM integration, and
  artifact readback.
- Describe the application runtime model and code-change contract. This file
  is not a Hosted game-project instruction file.
- Keep project identity, route progress, goals, and recovery state in the
  account-scoped Hosted workspace and metadata records.

## Start Here

1. Read `README.md` in this directory for the service component map.
2. Read `../docs/architecture/phase-service/_index.md` for boundary authority.
3. Read `../docs/architecture/ADR_INDEX_PHASE.md` before changing decisions.
4. Read `../docs/standards/phase-service.md` before changing API, DB, error,
   security, logging, test, or status behavior.
5. Read the route-specific architecture and Godot standards before changing a
   Hosted workflow.

## Application Runtime Model

- `Program.cs` is the composition root and HTTP endpoint map.
- `Browser/**` renders the current browser surface.
- `Configuration/**` parses host-supplied configuration and rejects invalid
  security or runtime combinations.
- `Data/**` owns SQLite records, migrations, account-scoped metadata, and
  persisted Hosted Context manifests.
- `Security/**` owns request authentication and account identity.
- `Projects/**` owns project creation, import, initialization, and recovery.
- `Runs/**` owns GDD, prototype, iteration, repair, package, and executable
  Hosted workflows.
- `Llm/**` owns structured LLM routing, binding, usage, and context gates.
- `Skills/**` owns the server-published Phase action catalog and dispatch.
- `Workspaces/**` owns workspace layout, seeding, maintenance, and path policy.
- `Readback/**` owns artifacts, packages, assets, previews, and browser-safe
  result projection.
- `Workflow/**` projects repository standards and route contracts into code.

## Request And Execution Boundary

1. The HTTP endpoint resolves authentication and account/project ownership.
2. The route service recovers current project sources and validates route
   prerequisites.
3. Read-only model work uses `ILlmRouteEngine`; executable Codex work uses
   `CodexHostedProcessCommandFactory`.
4. Mutation-capable work runs inside the server-selected project workspace and
   records run state and additive evidence.
5. Completion is determined by route acceptance and current diagnostics, not
   by assistant prose.

## Hosted Context And Knowledge

- ADR-0044 is the authority for Domain, Visibility, Lifecycle, E1/E2, and the
  Hosted Context envelope.
- Repository knowledge indexes are `derived_cache`; they never override source,
  ADRs, metadata authority, route contracts, or the latest live blocker.
- The repository Locator currently serves VDD, Quick Dev, and Bootstrap
  adapters. Do not claim Phase route integration until a server-owned Phase
  consumer policy and adapter are implemented and validated.
- A future Phase adapter must reuse the canonical Locator core, reread and
  hash-verify accepted sources, freeze its selection before dispatch, and bind
  repository, template, project, and run snapshots into the parent manifest.
- Child Skills and Hosted Codex processes must not expand a frozen context or
  supply trusted Domain, path, policy, budget, or gate fields.

## Local Change Routing

- API or browser behavior: endpoint, caller, auth boundary, readback, and tests.
- Auth or account isolation: `Security/**`, `Data/**`, negative/positive access
  tests, and audit behavior.
- Metadata schema: additive migration, store tests, restore behavior, and ADR
  compatibility.
- Hosted workspace behavior: `Workspaces/**`, project recovery, architecture
  documentation, and temporary-root tests. Never test against live workspaces.
- LLM/Codex behavior: shared entrypoint plus caller tests; prompt transport
  remains UTF-8 stdin-first.
- Route behavior: recovery inputs, current state, failure fallback, acceptance,
  browser-safe output, and route-specific tests.

## Protected Code

Ask before modifying authentication, token hashing, account isolation, audit,
live-state ownership, or these shared execution entrypoints:

- `Llm/LlmRouteEngine.cs`
- `Runs/CodexHostedProcessCommandFactory.cs`
- the server registration and secret path in `Program.cs`

Never read or mutate live metadata or Hosted workspaces as part of a unit test.

## Validation

- Platform suite: `dotnet test PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj`
- Focused workspace tests:
  `dotnet test PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj --filter FullyQualifiedName~ProjectWorkspaceSeederTests`
- Shared LLM/Codex changes also require `LlmRouteEngineTests`,
  `CodexHostedProcessCommandFactoryTests`, `scripts/sc/tests/test_llm_backend.py`,
  and caller-specific tests.
- Live startup and public health validation are owned by
  `../runtime/phase-a/AGENTS.md`; do not use ordinary `dotnet run` as the live
  server entrypoint.

## Definition Of Done

- Behavior remains backward-compatible unless an approved compatibility plan
  says otherwise.
- Account, project, workspace, and run identities remain server-owned.
- Required context or recovery-source failures fail closed before dispatch.
- Tests cover the changed boundary and failures remain preserved as evidence.
- Documentation and Accepted ADR references change with any contract,
  threshold, security posture, or ownership change.
