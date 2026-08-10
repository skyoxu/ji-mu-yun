# PhaseA.Platform Agent Contract

This applies inside `PhaseA.Platform/**` and adds ASP.NET-specific rules. Host startup,
Caddy, watchdog, and public recovery belong to `../runtime/phase-a/AGENTS.md`;
Hosted project state belongs to each project workspace.

## Required Entries

- Component map and runtime flow: `README.md`.
- Phase architecture: `../docs/architecture/phase-service/_index.md`.
- Accepted decisions: `../docs/architecture/ADR_INDEX_PHASE.md`.
- API, DB, error, security, logging, test, and status contracts:
  `../docs/standards/phase-service.md`.
- Hosted Godot behavior: the relevant entry in `../docs/standards/_index.md`.

Read only the route-specific source needed for the task.

## Application Invariants

- `Program.cs` is the composition root and endpoint map; `README.md` owns the
  component map.
- The HTTP boundary resolves authentication and account/project ownership
  before route execution.
- Route services recover current project sources and validate prerequisites
  before dispatch.
- Read-only model work uses `ILlmRouteEngine`; executable Codex work uses
  `CodexHostedProcessCommandFactory`.
- Mutation-capable work runs only in the server-selected project workspace and
  records additive run state and evidence.
- Identity, context scope, and gates remain server-owned; callers cannot widen
  them.
- Completion comes from current acceptance and diagnostics, never assistant
  prose or historical route memory.

## Hosted Context And Knowledge

- ADR-0044 governs Domain, Visibility, Lifecycle, E1/E2, and Hosted Context.
- Knowledge indexes are derived caches and never override source, Accepted
  ADRs, metadata, route contracts, or the latest live blocker.
- The repository Locator currently serves VDD, Quick Dev, and Bootstrap Review.
  Do not claim Phase route integration until a server-owned Phase adapter and
  consumer policy are implemented and validated.
- Any future adapter must reuse the canonical Locator, verify and freeze its
  sources before dispatch, and prevent child context expansion. Details belong
  to the Phase architecture documents.

## Local Change Contract

- API or browser changes update endpoint/DTO, caller, auth boundary, safe
  readback, public behavior documentation, and targeted tests.
- Auth changes cover persistence, positive/negative access, isolation, hashing,
  audit, and redaction.
- Metadata changes use additive migrations by default, preserve existing data,
  cover store/restore behavior, and remain ADR-compatible.
- Workspace changes cover containment, recovery, cleanup, temporary-root tests,
  and architecture. Tests never use live state.
- LLM/Codex changes use shared entrypoints, UTF-8 stdin, and entrypoint/caller
  tests. Extend the abstraction before adding execution behavior.
- Route changes define recovery, current authority, failure behavior,
  acceptance, safe output, and tests. Missing sources fail closed.
- Public/browser contracts remain backward-compatible unless explicitly
  approved with a documented compatibility plan.

## Protected Code

Ask before changing authentication, token hashing, account isolation, audit,
live-state ownership, secret registration, or these shared entrypoints:

- `Llm/LlmRouteEngine.cs`
- `Runs/CodexHostedProcessCommandFactory.cs`
- the server registration and secret path in `Program.cs`

Never read or mutate live metadata or Hosted workspaces from a unit test.

## Validation

- Platform suite:
  `dotnet test PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj`
- Workspace focus: add
  `--filter FullyQualifiedName~ProjectWorkspaceSeederTests`.
- Shared LLM/Codex changes also run both entrypoint test suites,
  `scripts/sc/tests/test_llm_backend.py`, and caller tests.
- Live startup and public health validation belong to the runtime contract. Do
  not use ordinary `dotnet run` for the live service.

## Definition Of Done

- The changed boundary has targeted tests and required smoke evidence.
- Compatibility, server-owned identity, workspace containment, and fail-closed
  recovery remain intact.
- Failures and run evidence remain additive and secrets remain excluded.
- Contract, threshold, security, or ownership changes update their standard,
  architecture source, and Accepted ADR set.

## Maintenance Budget

Keep this file below 4,500 characters. Maps, rationale, status, test matrices,
and host procedures belong to their
owning README, architecture, standard, or runtime document.
