# Phase Service Standards

Status: Living standards
Language: English
Scope: Phase A/B platform service and Phase browser-consumed prototype routes.

## Purpose

This document is the standards source of truth for Phase service conventions within the authority order below. It turns scattered implementation conventions into stable rules for API naming, database naming, error handling, logging, security, and testing.

Use it when changing:

- `PhaseA.Platform/**` and `PhaseA.Platform.Tests/**`.
- Phase runtime scripts and configuration under `runtime/phase-a/**`.
- Phase-facing smoke, drill, and ops scripts under `scripts/python/phase_a_*.py` and `scripts/python/phase_b_*.py`.
- Browser-consumed prototype routes, readback surfaces, audit views, package/asset/preview flows, and LLM/Codex route entrypoints.

## Authority Order

When documents disagree, use this order and correct the lower-priority document:

1. Accepted Phase ADRs, especially the ADRs linked from `docs/architecture/ADR_INDEX_PHASE.md`.
2. Hard operating rules in `AGENTS.md`, including encoding, security, recovery, and protected-path rules.
3. Runtime source-of-truth files and source code compatibility contracts, such as `runtime/phase-a/start-phasea.ps1`, `runtime/phase-a/Caddyfile`, and existing compiled API/DB behavior.
4. Phase architecture rationale under `docs/architecture/phase-service/**`.
5. This standards document.
6. README summaries and high-level navigation docs.

Existing code and DB behavior constrain compatibility, but they are not design authority when they conflict with accepted ADRs, security rules, or explicit recovery rules. Fix the lower-authority source instead of preserving unsafe drift.

If a new change intentionally breaks these standards, record the decision in an ADR or decision log before implementation.

## API Naming And Compatibility

### Auth Transport

- Authenticated API calls use `Authorization: Bearer <token>`.
- Do not pass admin tokens, user tokens, provider keys, or ticket secrets in query strings.
- Download and preview tickets should be created through authenticated POST routes, be short-lived, and be bound to the intended account/project/artifact. If a GET download URL must carry a ticket for browser compatibility, the ticket must be opaque, scoped, expiring, and non-reusable where practical.
- Admin token and user token behavior must stay distinguishable in server-side authorization code and tests.

### Route Shape

- Public and browser-consumed routes live under `/api/...`.
- Route path segments use lowercase kebab case: `/api/project-creation-failures/latest`, `/api/projects/{projectId}/prototype-7day-playable`.
- Route parameters use camelCase inside braces to match current handlers: `{projectId}`, `{runId}`, `{artifactId}`, `{accountId}`, `{sectionId}`, `{sessionId}`, `{fileName}`.
- Collection routes use plural nouns: `/api/projects`, `/api/projects/{projectId}/runs`, `/api/admin/users`.
- Admin-only routes use `/api/admin/...`; current-account user routes use `/api/account/...`; project-scoped routes stay under `/api/projects/{projectId}/...`.

### Action Routes

Action routes are allowed only when the backend starts a command, workflow, ticket, export, validation, or recovery action rather than directly exposing a durable REST resource.

- Keep action names lowercase kebab case and domain-specific: `/download-ticket`, `/execute-next`, `/rotate-token`, `/web-preview`. Full examples include `/api/projects/{projectId}/packages/{fileName}/download-ticket` and `/api/admin/users/{accountId}/rotate-token`.
- Do not add generic verbs such as `/do`, `/run`, `/process`, or `/handle`.
- Document idempotency for new action routes: safe repeat, creates a new run each time, returns an existing active run, or rejects duplicate requests.
- Long-running action routes should return a run, ticket, route state, or evidence pointer that can be read back by a stable GET route.

### Compatibility Rules

- Public and browser-consumed APIs are backward-compatible by default.
- Do not remove, rename, or repurpose routes, request fields, response fields, status codes, auth behavior, artifact IDs, ticket semantics, or artifact paths without explicit approval and a documented compatibility plan.
- Compatibility plans must identify affected browser callers, migration or adapter strategy, dual-read/write behavior when relevant, deprecation window, rollback path, and tests or smoke evidence.
- Compatibility plans must be recorded in an ADR, decision log, PR/task evidence, or another durable source linked from the change.
- Additive response fields are preferred over changing existing field meanings.
- New browser behavior must update the server handler, DTOs/records, browser caller, tests, and relevant docs together.
- Project-scoped routes must resolve the current account before reading or mutating projects, runs, artifacts, packages, assets, chats, workflow state, route state, or LLM state.
- Admin summary routes may aggregate across accounts, but raw cross-account item readback needs an explicit security decision.

### Response Shape

- JSON property names use the existing .NET/ASP.NET Core camelCase output convention.
- Identifiers should be named by domain role: `projectId`, `runId`, `artifactId`, `accountId`, `sessionId`, `stepId`.
- Time fields use UTC and should end in `Utc` in C# contracts or `_utc` in database rows. Browser JSON should preserve clear UTC semantics, normally via `createdUtc`, `updatedUtc`, `startedUtc`, `finishedUtc`, or `timestampUtc`.
- Do not return raw host filesystem paths when a sanitized workspace-relative path, artifact ID, package name, or download ticket can express the same user-visible behavior.

## Database Naming And Migrations

### Naming

- Phase metadata is single-node SQLite at `PHASEA_METADATA_DB_PATH` unless a future ADR supersedes [ADR-0033](../adr/ADR-0033-phase-metadata-sqlite-local-disk.md).
- Tables and columns use snake_case: `project_limits`, `project_creation_failures`, `project_iteration_sessions`, `account_id`, `project_id`, `created_utc`, `updated_utc`.
- JSON cache or snapshot columns end in `_json`: `summary_json`, `evidence_json`, `metadata_json`.
- Indexes use the current `ix_<table>_<columns>` style for new indexes. Existing `idx_...` names may remain for compatibility; do not churn them only for style.
- Unique indexes use `CREATE UNIQUE INDEX IF NOT EXISTS ix_<table>_<columns>` unless an existing table family already has a different stable naming style.

### Schema Change Rules

- Schema changes are additive by default and must preserve existing project, workspace, run, artifact, account, audit, LLM, route, and UI state.
- `PhaseA.Platform/Data/SqliteMetadataSchema.cs` is the schema evolution entrypoint. All schema DDL must live there or in a schema helper explicitly called by it. Do not scatter `CREATE TABLE`, `ALTER TABLE`, or index DDL across services or request handlers.
- New tables must declare ownership in the relevant architecture note or code review context: control-plane metadata, readback cache, route state pointer, or audit record.
- Account-visible rows need enough account/project context for scoped readback and audit investigation.
- Account/project-scoped tables must include lookup indexes for their common account, project, status, or created-time query paths unless a test or decision note explains why the table remains small or write-only.
- Destructive migrations, data rewrites, or live DB repair mutations require explicit approval and a decision log or ADR.
- Do not manually mutate the live Phase metadata DB to hide failures, bypass migrations, or rewrite audit history.
- Path values loaded from the DB must still be validated against allowed workspace roots before filesystem access.

### Persistence Coverage

- DB changes require persistence tests that exercise fresh schema creation and upgrade/reuse of an existing DB shape.
- If upgrade/reuse coverage is genuinely impossible, record the reason, risk, and substitute evidence in the PR, decision log, or task evidence before marking the change done.
- Changes that affect account scoping require authorized and unauthorized readback tests.
- Changes that introduce cached summaries must identify the authoritative source that can regenerate or verify the cache.

## Error Handling

- Error codes use stable lower_snake_case strings, for example `authentication_required`, `project_not_found`, `unknown_error`.
- Preserve HTTP status semantics for existing callers. Do not change a caller-visible status code without a compatibility plan.
- Error responses must not include raw exceptions, stack traces, token material, provider keys, raw command environments, raw prompts, or unsanitized host paths.
- Browser callers should preserve server error payloads where useful instead of replacing them with ambiguous generic text.
- New error codes should describe the durable condition, not the implementation detail: prefer `project_not_found` over `sqlite_project_lookup_failed`.
- Validation errors should identify the invalid field or operation without leaking private project content.

### HTTP Status Mapping

Use stable HTTP status and error-code pairs for new API error responses:

| HTTP status | Preferred code | Notes |
| --- | --- | --- |
| `400` | `validation_failed` | Invalid request shape, invalid field, or unsupported operation. |
| `401` | `authentication_required` | Missing or invalid credentials. |
| `403` | `forbidden` | Authenticated identity lacks permission; avoid revealing cross-account resource existence. |
| `404` | `project_not_found` or resource-specific `*_not_found` | Use when the caller is allowed to know absence, or when hiding existence is safer. |
| `409` | `conflict` | Duplicate active run, state mismatch, or idempotency conflict. |
| `422` | `route_state_invalid` | Semantically valid JSON that cannot be accepted by the route contract. |
| `429` | `rate_limited` | Account, route, or runner concurrency limit. |
| `500` | `unknown_error` | Unexpected server failure after redaction. |
| `503` | `service_unavailable` | Runtime dependency, runner, Caddy, or external service unavailable. |

Auth and account-scope failures must not confirm whether another account's project, artifact, package, or run exists. Prefer generic `forbidden` or `*_not_found` responses without identifying details.

### Structured Error Envelope

New API error responses must use this envelope unless compatibility with an existing route requires the old shape:

```json
{
  "code": "project_not_found",
  "message": "Project not found.",
  "details": {
    "operation": "read_project"
  },
  "requestId": "..."
}
```

- `code` is required and stable.
- `message` is safe for browser display and must not contain secrets or stack traces.
- `details` is optional. Omit it when empty; when present it must be a JSON object, redacted, and must not confirm cross-account resource existence.
- `requestId` is required for HTTP API errors. Legacy compatibility exceptions must be recorded with route evidence.

## Logging, Evidence, And Audit

### Evidence Location

- Logs, smoke output, runtime evidence, and recovery evidence go under `logs/`.
- Stable startup/config files stay under source directories such as `runtime/phase-a/`, not under `logs/`.
- Generated evidence is append-only by default. Preserve failures and add sidecar evidence instead of rewriting generated history.

### Event Fields

Structured evidence and audit records should include the fields needed for recovery and readback:

- `timestamp_utc` for DB rows and JSONL/sidecar files; `timestampUtc` for API JSON.
- `status` from a bounded status set.
- `action`, `route`, `run_type`, or equivalent producer/operation label.
- Scoped identifiers where applicable: `account_id`, `project_id`, `run_id`, `artifact_id`, `session_id`, `step_id`.
- Correlation identifiers where available: `request_id`, `correlation_id`, `trace_id`, or API equivalents `requestId`, `correlationId`, `traceId`.
- A short safe `message` or `reason`.
- Source-linked paths or artifact IDs after path sanitization.

### Correlation Ownership

- HTTP handlers must accept or create a request/correlation identifier and include it in structured errors. If an endpoint cannot expose the identifier for compatibility reasons, record that exception with the route evidence.
- Runner-created evidence must carry `run_id` or `runId` and preserve request/correlation identifiers when the run was started from an API request. Non-HTTP producers must still carry a source run, route, or artifact identifier.
- Sidecars that summarize another producer should keep the source run, route, or artifact identifier instead of inventing a detached ID.

### Redaction

- Do not log bearer tokens, admin token material, user token material, token hashes, provider keys, raw secret environment values, raw command environments, or raw prompts in browser-readable evidence.
- Admin readback may aggregate operational state, but raw cross-account evidence blobs require an explicit security decision.
- Use sanitized workspace-relative paths, artifact IDs, package names, or tickets instead of raw host paths in browser/API output.

## Security Standards

- User tokens are returned once; persisted user tokens are stored only as hashes.
- `PHASEA_ADMIN_TOKEN_HASH` and future token hash variables are loaded from host secret storage or service environment only. Do not commit real values to docs, scripts, config, logs, or fixtures.
- Account-scoped user routes must not list, mutate, or read another account's project data by guessed IDs.
- Admin-only routes must enforce admin identity and must preserve redaction for token material, provider keys, and private project evidence.
- Auth and account-scope failures must not confirm whether another account's project, artifact, package, or run exists; use the error-handling rules for generic `forbidden` or `*_not_found` responses.
- `PUBLIC_BASE_URL` remains HTTPS in runtime configuration unless a future ADR changes that invariant.
- Direct HTTP public health probes are diagnostics for the current Caddy listener only. They may be used by explicit smoke commands with `--allow-http`, but they must not replace `PUBLIC_BASE_URL` or be documented as the canonical public base URL.
- Host boundary rules stay hard in all delivery profiles: `res://` and `user://` only for game runtime file boundaries, HTTPS-only external access where applicable, explicit external host allow lists, offline mode support, and no dynamic external code loading.
- Runner/workspace actions must validate repository roots, hosted workspace roots, and project-relative paths before filesystem access.
- Download tickets, preview tickets, package links, and browser-readable artifact URLs must have explicit expiry or revocation semantics before being exposed beyond local trusted use.
- Local trusted use means loopback-only operator diagnostics on `127.0.0.1` or equivalent host-local tooling. Public Caddy access, account-user browsers, and shared operator browsers are not local trusted use.
- Browser/API responses that expose private account data, token issuance, ticket issuance, or admin audit export data must default to `Cache-Control: no-store` unless the route explicitly defines safe public/static/read-only cache behavior.

## Testing And Smoke Evidence

A Phase service change is not done until the relevant evidence exists or the gap is recorded with the required follow-up.

Use the narrowest test set that proves the changed contract:

- API route or DTO change: route-specific unit/integration tests plus browser caller coverage when browser behavior changes.
- Auth/account change: authorized, unauthorized, disabled-account, and cross-account denial coverage.
- DB schema change: schema creation and persistence/upgrade tests.
- Readback/artifact/package/asset change: account-scoped readback tests and path sanitization tests.
- Prototype route change: recovery input tests, stale-state or missing-source negative tests, bounded status tests, and route-specific acceptance evidence.
- LLM/Codex entrypoint change: shared entrypoint tests before caller-specific tests.
- Runtime/Caddy/recovery change: local health evidence first, then public proxy evidence.

Minimum evidence commands or files by change type:

| Change type | Minimum evidence |
| --- | --- |
| Platform API, DTO, auth, readback, DB, route service | Targeted `PhaseA.Platform.Tests/**` test class or a documented reason why only smoke evidence applies. Typical command: `dotnet test PhaseA.Platform.Tests --filter FullyQualifiedName~<TestClassOrMethod>` |
| Executable Codex route protocol | `PhaseA.Platform.Tests/Runs/CodexHostedProcessCommandFactoryTests.cs` plus caller-specific tests |
| Structured/read-only LLM route protocol | `PhaseA.Platform.Tests/Llm/LlmRouteEngineTests.cs` plus caller-specific tests |
| Python LLM/Codex helper | `scripts/sc/tests/test_llm_backend.py` plus caller script tests |
| Runtime or recovery script | `py -3 scripts/python/phase_a_ops_check.py` and saved evidence under `logs/` |
| Account isolation or admin audit | `py -3 scripts/python/phase_b_account_smoke.py --base-url <url>` with redacted evidence |
| Public endpoint validation | `py -3 scripts/python/phase_a_public_smoke.py --base-url <url>`; use `--allow-http` only for direct HTTP diagnostic probes |
| Browser caller behavior | Route-specific browser smoke or Playwright/E2E evidence by default, with evidence written under `logs/` and linked from task or PR evidence. Manual verification gaps are allowed only when browser automation is unavailable, and must record the blocker, owner, and follow-up evidence path. |

## Status Enums And Readback State

- New route, readiness, evidence, and readback states must use bounded status enums.
- Prefer existing status vocabulary where it fits: `queued`, `running`, `succeeded`, `failed`, `cancelled`, `ready`, `blocked`, `needs_fix`, `unknown`.
- `queued` and `running` are non-terminal.
- `succeeded`, `failed`, and `cancelled` are terminal for a specific run or validation attempt.
- Existing API compatibility may expose `cancel`; new sidecars and API contracts should prefer `cancelled` and document any legacy alias.
- `blocked` is terminal until an external input or repair action changes the condition.
- `needs_fix` is terminal for the current acceptance pass but should point to repair evidence or a next action.
- `ready` must name the readiness scope, such as package readiness, preview readiness, or route readiness.
- `unknown` is diagnostic, not success, and must not be promoted silently.
- Do not infer `succeeded` from assistant prose alone. Completion must be derived from validators, scripts, logs, database rows, route state, package outputs, imported assets, or stable diagnostics.
- Unknown or stale state should remain explicit. Do not silently convert missing evidence into success.
- Browser/UI labels may be friendlier, but API and sidecar status values must remain stable.
- New sidecars should use stable field names: `status`, `status_reason`, `evidence_refs`, `updated_utc`, and scoped IDs such as `project_id`, `run_id`, or `route_id` where applicable.
- `evidence_refs` should be an array of objects with `kind`, `path` or `artifact_id`, optional `run_id`, and optional `summary`. Paths must be sanitized and workspace-relative unless the evidence is an internal-only log.
- `evidence_refs.kind` is a closed enum by default: `log`, `artifact`, `sidecar`, `screenshot`, `db_row`, `smoke`, or `validator`. New kinds must update this standards document.

## Documentation Update Rules

- New durable architectural decisions require a Phase ADR or an update to an existing ADR, and must update `docs/architecture/ADR_INDEX_PHASE.md`.
- New cross-cutting conventions belong in this document, with links from `AGENTS.md`, `README.md`, `docs/PROJECT_DOCUMENTATION_INDEX.md`, and `docs/standards/_index.md` when they become agent-facing.
- New architecture rationale belongs under `docs/architecture/phase-service/**` unless it is a full arc42 overlay slice.
- New Phase architecture docs must update `docs/architecture/phase-service/_index.md`.
- New workflow evidence or operational runbooks belong under `docs/workflows/**` or `runtime/phase-a/**` as appropriate.
