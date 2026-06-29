# Phase Service System Overview

## Intent

The Phase service exists to turn a Windows-only Godot + C# repository workflow into a browser/API usable prototype-generation and hosting product without rewriting the repository workflow kernel.

The platform gives users project creation, hosted prototype routes, GDD workflows, package/readback, asset previews, account-scoped access, LLM bindings, audit surfaces, and runtime evidence. It does not make the browser or Web API the owner of workflow decisions.

## Boundary

In scope:

- ASP.NET Core 8 Minimal API and static browser UI in `PhaseA.Platform/**`.
- SQLite metadata for accounts, projects, workspaces, runs, artifacts, iteration state, chat, audit, and LLM usage.
- Hosted workspaces under `logs/phase-a-innernet/workspaces/**`.
- Runtime state and evidence under `logs/phase-a-innernet/**`.
- Phase browser-consumed prototype routes, including project creation, prototype execution, iteration, repair, GDD, asset, package, and preview flows.
- Shared LLM/Codex execution entrypoints used by platform routes and Python scripts.

Out of scope:

- Rewriting repository scripts into a new platform-native workflow engine.
- Treating browser/UI sidecars as workflow authority.
- Strong multi-node or object-storage scale-out before Phase C storage and runner-isolation decisions.
- Treating external pattern sources such as AGF, godogen, or ECC as runtime dependencies.

## Key Decisions

- The first hosted product is single-node Windows because Godot, C#/.NET, export tooling, and existing scripts are already Windows-oriented.
- The Web Service is ASP.NET Core 8 Minimal API because it can serve browser UI, HTTP APIs, background queues, and local process orchestration with low deployment complexity.
- SQLite is the metadata store because Phase A/B are single-node and need durable local state more than distributed database scale.
- Local disk remains the workspace and artifact backend until Phase C storage abstraction is explicitly designed.
- The platform delegates real workflow execution to repository scripts and route services instead of reimplementing decisions in controllers.
- The platform is account-scoped in Phase B, but OS-level runner isolation, NTFS ACLs, identity product flows, and storage abstraction are Phase C/pre-production concerns.

## Current Implemented Shape

Primary code surfaces:

- `PhaseA.Platform/Program.cs`: HTTP API and page routes.
- `PhaseA.Platform/Data/SqliteMetadataSchema.cs`: additive metadata schema and triggers.
- `PhaseA.Platform/Data/PhaseAMetadataStore.cs`: metadata read/write service.
- `PhaseA.Platform/Projects/**`: project creation, deletion, initialization, and recovery.
- `PhaseA.Platform/Workspaces/**`: workspace layout and path policy.
- `PhaseA.Platform/Runs/**`: hosted process execution, prototype routes, route state, iteration, repair, GDD, and runner queues.
- `PhaseA.Platform/Readback/**`: artifact, package, asset, preview, run, usage, and admin readback.
- `PhaseA.Platform/Llm/**`: chat, account bindings, route LLM calls, usage, and gateway integration.
- `PhaseA.Platform/Security/**`: bearer/header token handling and token hashing.
- `runtime/phase-a/**`: stable live-server startup, recovery, watchdog, and Caddy config.

## Invariants

- Browser/API surfaces must not become the source of workflow truth.
- Repository scripts, route state, validated sidecars, database rows, and generated evidence are the authority chain.
- Project and account boundaries must be enforced before readback.
- Metadata paths and workspace paths must be normalized and checked before file access.
- Long-running mutating work must go through controlled runner/queue services, not arbitrary process launches.
- New hosted routes must preserve recovery, evidence, and account scoping.

## Change Rules

- If a change affects platform API, update the server route, browser caller, tests, and public behavior docs together.
- If a change affects workflow authority, create or update an architecture note, overlay, decision log, or ADR before implementation.
- If a change affects Phase B/C roadmap claims, update `roadmap-and-hardening.md` and the source workflow/backlog docs.
- If a change affects Phase service safety, update `AGENTS.md` only with concise non-negotiable rules and link to deeper architecture docs.

## Related Tests

- `PhaseA.Platform.Tests/**`
- `scripts/python/phase_a_*` smoke/drill scripts
- `scripts/python/phase_b_account_smoke.py`
- `scripts/sc/tests/test_llm_backend.py`
