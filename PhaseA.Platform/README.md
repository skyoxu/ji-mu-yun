# Phase A Platform Service

`PhaseA.Platform` is the ASP.NET Core 8 application that exposes the Ji Mu Yun
Phase A/B platform through browser and HTTP APIs. It wraps the repository's
Godot prototype kernel, controlled scripts, Hosted workspaces, and evidence
contracts without making browser input an arbitrary process or filesystem
interface.

This README describes the application process. Stable host startup, watchdog,
Caddy, and public recovery live in `../runtime/phase-a/README.md`.

## Component Map

| Area | Responsibility |
| --- | --- |
| `Program.cs` | Dependency registration, middleware, and HTTP endpoint map |
| `Browser/` | Server-rendered browser experience and browser callers |
| `Configuration/` | Environment-backed options and fail-closed validation |
| `Data/` | SQLite schema, metadata store, accounts, runs, and manifests |
| `Security/` | Bearer-token authentication and account identity |
| `Projects/` | Project creation, import, initialization, and recovery |
| `Runs/` | GDD, prototype, iteration, repair, package, and Codex workflows |
| `Llm/` | LLM routing, provider binding, usage, and Hosted Context gates |
| `Skills/` | Published Phase action catalog and route dispatch |
| `Workspaces/` | Workspace layout, seeding, maintenance, and path containment |
| `Readback/` | Artifacts, assets, packages, previews, and safe browser readback |
| `Workflow/` | Code projections of route and Godot workflow contracts |

## Runtime Flow

```text
browser/API request
  -> authentication and account/project ownership
  -> route service and recovery-source validation
  -> structured LLM or executable Codex shared entrypoint
  -> project-scoped workspace/run
  -> acceptance, metadata, artifacts, and browser-safe readback
```

The service is a parent control plane. Hosted game-project identity and current
execution state come from project metadata, route profiles, project contracts,
latest route state, ledgers, and acceptance evidence. They do not come from
placeholder fields in this directory.

## Hosted Workspace Entry Documents

New Hosted workspaces receive project-specific root entry documents from:

- `Workspaces/HostedProjectTemplate/AGENTS.template.md`
- `Workspaces/HostedProjectTemplate/README.template.md`

The Seeder copies these as project-root `AGENTS.md` and `README.md`. Existing
project-owned entry files are preserved. The templates are Workspace lifecycle
inputs, not platform repository authority and not a substitute for structured
route state or a signed run context.

## Knowledge And Context Status

- ADR-0044 defines repository, template, project, and run lifecycle isolation.
- Hosted Context gates bind Phase LLM/Codex dispatches to server-issued
  identities and snapshots when the dedicated signing key ring is configured.
- The repository Knowledge Locator currently integrates with VDD, Quick Dev,
  and Bootstrap Review. It is not yet a Phase browser-route knowledge adapter.
- A future Phase adapter must reuse the stable Locator contracts, apply a
  server-owned consumer policy, verify source hashes, freeze accepted context,
  and bind the assembled artifact manifest before dispatch.

## Configuration Ownership

`Configuration/PhaseAPlatformOptionsLoader.cs` parses application settings.
The canonical live values and secret-resolution path are owned by
`../runtime/phase-a/start-phasea.ps1` and the host environment. Never commit
real tokens, signing secrets, provider credentials, or live hashes.

`PHASEA_SERVICE_STATE` accepts `development`, `test`, or `production`.
It defaults to `development`. Quick Dev governance checks are disabled in
development and enabled automatically in test and production; callers may
override that decision with `--governance-mode on|off|auto` or
`JIMUYUN_GOVERNANCE_MODE`. This switch does not disable authentication,
runtime safety, TDD stages, declared write sets, or semantic predicates.

The metadata database and Hosted workspace roots are protected live state.
Unit and integration tests must use temporary roots and temporary SQLite files.

## Run And Validate

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File runtime/phase-a/ensure-phasea.ps1
py -3 scripts/python/phase_a_ops_check.py
dotnet test PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj
```

Use `runtime/phase-a/start-phasea.ps1` for the live process. Ordinary
`dotnet run` is not the live startup or recovery contract.

## Architecture

- `../docs/architecture/phase-service/_index.md`
- `../docs/architecture/phase-service/system-overview.md`
- `../docs/architecture/phase-service/hosted-workspaces-and-artifacts.md`
- `../docs/architecture/phase-service/prototype-routes-and-recovery.md`
- `../docs/architecture/phase-service/llm-codex-execution.md`
- `../docs/architecture/ADR_INDEX_PHASE.md`
- `../docs/standards/phase-service.md`
- `AGENTS.md`
