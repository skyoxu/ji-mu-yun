---
PRD-ID: PHASE-A-CLOUD-RUNNER
Title: Phase A Cloud Runner Architecture Acceptance Checklist
Arch-Refs: [CH01, CH02, CH03, CH04, CH06, CH07, CH09, CH10, CH11]
ADRs: [ADR-0015, ADR-0018, ADR-0019, ADR-0025, ADR-0031]
Test-Refs: [scripts/python/dev_cli.py, scripts/python/validate_overlay_execution.py, scripts/python/check_docs_utf8_integrity.py]
Status: Draft
Updated: 2026-05-10
---

# Acceptance Checklist

This checklist defines the architecture acceptance criteria for Phase A Cloud Runner.

## Architecture Boundary

- [ ] The platform hosts the repository workflow without replacing repository-native decisions.
- [ ] Browser and Web API handlers do not reinterpret `preferred_lane`, stop-loss results, forbidden commands, approval transitions, or gate outcomes.
- [ ] Repository scripts remain the execution authority for recovery, routing, task execution, and project health.

## Workspace And Runtime

- [ ] Workspaces are created under `HOSTED_WORKSPACE_ROOT`, with `C:\workspaces` as the default.
- [ ] Multiple projects are supported with a default per-account project limit of `2`.
- [ ] Project creation fails closed when `HOSTED_PROJECT_LIMIT` is reached.
- [ ] Each project has exactly one default workspace in Phase A.
- [ ] Browser users cannot configure arbitrary Git URLs.
- [ ] Project creation uses admin-defined server-side rules or templates.
- [ ] The first project creation rule is `godot-prototype-default`.
- [ ] `godot-prototype-default` allows only Chapter 2 bootstrap and Prototype lane workflows.
- [ ] `godot-prototype-default` blocks Chapter 3 through Chapter 7 workflows.
- [ ] Workspace paths are normalized and checked before any read or write.
- [ ] `repo\`, `runtime\`, and `meta\` ownership boundaries are enforced.
- [ ] Platform runtime logs do not replace repository `logs/**` sidecars.
- [ ] Account, project, workspace, prototype, run, and artifact relationships are represented consistently in SQLite.

## Hosted Entrypoints

- [ ] Hosted commands are script-first and callable by CLI, Web API, and Runner.
- [ ] Hosted commands emit machine-readable summaries.
- [ ] Chapter 2 repository bootstrap is exposed as a hosted top-level route.
- [ ] Prototype top-level routing is exposed through `run-prototype-workflow`.
- [ ] Prototype TDD is exposed through `run-prototype-tdd`.
- [ ] Prototype scene creation is exposed through `create-prototype-scene`.
- [ ] `prototype-7day-playable-godot-zh` guidance is available for the Chinese 7-day playable lane.
- [ ] Chapter 3 through Chapter 7 formal delivery routes are not implemented in Phase A.
- [ ] Runner commands are allowlisted.
- [ ] Each project has at most one active heavy runner in Phase A.
- [ ] Read-only artifact and status requests can continue while a project runner is active.
- [ ] No raw shell command endpoint is exposed to browser users.

## Artifacts And Recovery

- [ ] Active prototype, prototype record, prototype sidecar JSON, TDD summary, TDD report, project health, execution plans, and decision logs are discoverable.
- [ ] Artifact summaries link back to authoritative files.
- [ ] Prototype intake and routing run before prototype TDD execution is offered.
- [ ] Prototype evidence is never presented as formal Chapter 6 delivery evidence.

## Security And Operations

- [ ] Account model starts as single-admin plus password or token.
- [ ] `host-safe` is the default security posture unless explicitly changed.
- [ ] Public browser and API access require authentication.
- [ ] Public access uses HTTPS termination.
- [ ] ECS-local Caddy HTTPS termination is documented or superseded by a decision log.
- [ ] Write operations are auditable by user, project, workspace, operation, timestamp, and result.
- [ ] `GODOT_BIN`, `.NET SDK 8`, Python, Node, Git, Codex, and Godot .NET readiness are checked.
- [ ] Secrets are not stored in SQLite rows or committed docs.
- [ ] OpenAI/Codex runs read secrets only from environment or a host secret provider.
- [ ] OpenAI/Codex runs record backend label, duration, exit state, and cost metadata when available.
- [ ] OpenAI/Codex invocation follows existing repository rules and explicit user actions.
- [ ] LLM retry limits and cost stop-loss are explicit.
- [ ] Default platform LLM cost stop-loss is `2.00 CNY` per run.
- [ ] Default platform LLM cost stop-loss is `20.00 CNY` per account per day.
- [ ] `new-api` is treated as an external replaceable LLM gateway, not as the platform workflow state store.
- [ ] Upstream provider API keys are managed by `new-api`, not by the Phase A platform.
- [ ] Platform accounts can bind to `new-api` users/tokens through `account_llm_bindings`.
- [ ] Phase A `new-api` account binding is manual-admin only; API-driven provisioning is deferred.
- [ ] Runs record `llm_gateway`, `llm_request_id`, `llm_model`, and cost summary when available.
- [ ] Platform-side cost stop-loss is checked before forwarding costly operations to `new-api`.
- [ ] AGPL and public generative AI compliance posture is recorded before public launch; Malaysia-hosted prototype does not apply China mainland generative AI service requirements by default.
- [ ] Production domain and certificate source may be finalized before public launch, not during early prototype implementation.

## Web Service

- [ ] Phase A uses ASP.NET Core 8 Minimal API unless a later decision log supersedes it.
- [ ] The Web Service serves API and the first browser UI without owning workflow decisions.
- [ ] Long-running commands run through a background queue or worker path and do not block status/artifact reads.

## Verification

- [ ] `py -3 scripts/python/check_docs_utf8_integrity.py --root docs` passes.
- [ ] `py -3 scripts/python/validate_overlay_execution.py --prd-id PHASE-A-CLOUD-RUNNER` passes.
- [ ] Pre-implementation baseline command remains available: `py -3 scripts/python/dev_cli.py run-local-hard-checks-preflight --delivery-profile fast-ship`.
