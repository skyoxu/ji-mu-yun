# Phase Service Standards

Status: Living standards
Language: English
Scope: Phase A/B platform service and Phase browser-consumed prototype routes.

## Purpose

This document is the standards source of truth for Phase service conventions within the authority order below. It turns scattered implementation conventions into stable rules for API naming, database naming, error handling, logging, security, and testing.

Use it when changing:

- GDD-to-module route contracts under `docs/workflows/phase-a-gdd-to-module-route-contracts.md`, `PhaseA.Platform/Workflow/RouteModuleContracts.cs`, and the matching fixture.
- Godot runtime semantic gates under `docs/standards/godot-engine-semantics.md`, `PhaseA.Platform/Workflow/GodotEngineSemantics.cs`, and the matching fixture.
- Godot UI capability gates under `docs/standards/godot-ui-capability-contract.md`, `PhaseA.Platform/Workflow/GodotUiCapabilityContract.cs`, and the matching fixture.
- Godot UI style catalog, snapshot schema profile, drift taxonomy, style-aware closure, and schema acceptance under `docs/standards/godot-ui-style-contract.md`, `docs/standards/godot-ui-style-closure.md`, `docs/standards/godot-ui-style-schema-acceptance.md`, `docs/schemas/godot-ui-style-contract.v1.example.json`, `PhaseA.Platform/Workflow/GodotUiStyleCatalog.cs`, `PhaseA.Platform/Workflow/GodotUiStyleSnapshotSchema.cs`, `PhaseA.Platform/Workflow/GodotUiStyleClosureContract.cs`, and the matching fixtures.
- Godot/Phase diagnostics, project diagnostic spool, failure-family taxonomy, preview/package quality gates, interaction-region evidence, and resource lifecycle rules under `docs/standards/godot-diagnostics-quality-gates.md`, `docs/schemas/project-diagnostic-spool.v1.example.json`, `PhaseA.Platform/Workflow/GodotDiagnosticsQualityGate.cs`, `PhaseA.Platform/Data/SqliteMetadataSchema.cs`, and `PhaseA.Platform/Data/PhaseAMetadataStore.cs`.
- Hosted route readback, recovery, and source-hash freshness policy under `docs/workflows/phase-a-route-readback-recovery-freshness.md`, `RouteReadbackPathPolicy.cs`, and `RouteFreshnessPolicy.cs`.
- Route operation governance, exposure classes, preflight, duplicate-run semantics, and secret redaction policy under `docs/workflows/phase-a-route-operation-governance.md`, `RouteOperationPreflight.cs`, and `SecretRedactionPolicy.cs`.
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

### Administrator Project Purge

- `GET /api/admin/projects` is an administrator-only cross-account project inventory. It returns project identity, owning account, lifecycle status, and timestamps; it does not return host filesystem paths.
- `POST /api/admin/projects/purge` is an administrator-only destructive action. The request must contain selected `projectIds` and the exact confirmation string `PURGE-PROJECTS`.
- Purge rejects queued/running projects and runner-locked projects. For each accepted project it removes project-scoped metadata, historical management relations, and the hosted workspace using a root-checked, no-follow reparse-point deletion path. The account itself is not deleted.
- Purge is per-project idempotent: retrying an already removed ID returns `project_not_found`; a workspace failure rolls back that project's metadata transaction and returns a per-item failure. The administrator audit records only aggregate counts, not deleted project identifiers or names.

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

### Admin Review Queue API

- Cross-project queue readback is admin-only at `GET /api/admin/project-admin-review-queue` and supports bounded filters for `projectId`, `routeId`, `severity`, `status`, `minimumAgeMinutes`, and `limit`.
- Admin decisions use `POST /api/admin/project-admin-review-queue/{entryId}/decision` with `approved|deferred|rejected|backlog|resolved`, a required reason, and an expected decision version.
- Same-payload retries are idempotent. A different payload against a stale version returns `409 conflict`; a missing entry returns `404`; invalid status, version, reason, or deferred metadata returns `400`.
- `deferred` requires `deferredOwner`, `affectedRoutes` containing the current queue entry route, durable decision evidence, and at least one of a future `deferredUntilUtc` or `recheckTrigger`. Same-payload admin decision retries remain idempotent even after the deferred window expires.
- `open|rejected|backlog` remain blocking. `approved|resolved` clear the current blocker. `deferred` clears it only while its future window remains active and route-scoped, or until its owning route producer performs the named recheck. Expired, malformed, or out-of-scope deferred metadata is blocking. A producer upsert for the same stable queue key is the recheck event and must supersede the deferred row with a new `open` row even when the blocker payload is unchanged; this producer transition is distinct from an idempotent admin decision retry. `superseded` is immutable historical state and never participates as a live blocker.
- Regeneration with changed source evidence appends a new queue row and links `supersedesEntryId` / `supersededByEntryId`; it must not overwrite the previous row or its decision history.
- Reconciliation that resolves a no-longer-produced blocker records actor `system`, decision version/time/metadata, and a matching append-only decision row. Legacy duplicate-key migration records all predecessor/successor choices in migration lineage and prioritizes live blocking severity before recency.
- Queue `evidenceRefs` are arrays of structured objects with a closed evidence kind and a workspace-relative `path` or `artifactId`; malformed JSON, external URIs, rooted paths, and traversal are rejected.
- Decision evidence string inputs are compatibility syntax only. Persistence normalizes them to structured sidecar/artifact refs, verifies project ownership/existence for a new version, and rejects traversal, rooted/URI paths, and unknown artifacts.

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
- `project_admin_review_queue` is the cross-project query owner for review blockers. `project_admin_review_decisions` is its append-only decision history and must receive the queue update and new decision version in the same SQLite transaction.
- Project-local `meta/routes/admin-review-queue/latest.json` is a regenerable sidecar for project recovery/readback; it is not the cross-project query authority and must preserve supersession links.

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

### Source-Boundary Evidence

- Enforced route-state boundaries use the shared `hosted-route-recovery-order.v1` contract and preserve its ordered eight-source recovery sequence from `AGENTS.md`.
- Prompt-producing route evidence must be structured JSON and prove the exact recovery contract ID, ordered recovery sources, and every source-hash key/value recorded by the route state. Merely mentioning a hash or contract token in free text is not proof.
- Prompt-producing routes must scan the exact in-memory execution prompt before dispatch using `hosted-route-forbidden-source-scan.v1`. Evidence records the execution prompt SHA-256, exact pattern list, required content-fingerprint hashes, matched hashes, fingerprint-set status, authority-derived allowed references, violations, and `clean|blocked`. The prompt manifest separately records `execution_prompt_hash` and the secret-redacted artifact's `persisted_prompt_hash`.
- The GDD route may use one selected pre-freeze game-type guide only when its stable ID/path/full-content hash is recorded. The allowed relative guide reference is derived from that authority; matching sidecar and evidence declarations cannot create a new allowed source. Unapproved guide chunks are denied before Codex dispatch. After freeze, raw mutable guide chunks are denied using normalized paragraphs plus overlapping word-window fingerprints without a fixed paragraph-count limit, so path removal, late-document copying, light edits, or whitespace changes do not bypass the guard.
- Required guide catalogs/fingerprint sets and prompt artifacts fail closed when missing, unreadable, empty, or unparseable; absence is not evidence of no forbidden source.
- Prompt evidence refs must resolve inside the hosted project boundary. Every accepted prompt-producing route updates `project_route_prompt_evidence_bindings` with the execution hash, redacted persisted hash, prompt artifact ref, and evidence ref; readback must match that DB authority as well as the workspace files. GDD prompt evidence additionally requires a succeeded same-project run carrying the same binding. Missing, unreadable, unparseable, cross-project, reordered, DB-mismatched, or hash-mismatched evidence fails closed as a P0 source-boundary blocker.
- When an upgraded project's existing GDD route state fails specifically with `gdd_document_source_boundary_invalid`, the authenticated GDD document-generation route may enter a server-authorized replacement flow. It must preserve the existing `docs/gdd/GDD.md` and `docs/gdd/gdd-outline.json` under a run-scoped `meta/recovery/gdd-replacements/<run_id>/` backup manifest with SHA-256 bindings, restore those files if generation fails, and publish the replacement only after current prompt authorities and route state pass. No client request field may independently authorize replacement. Other existing-GDD conflicts remain blocked and must never be projected as `ready`.
- Source-hash validation recomputes current structured game-type, scene-route, and contract-snapshot semantics. Sidecar-declared hash fields are continuity metadata, not hash authority.
- Non-prompt routes use the explicit `source_boundary_not_applicable` shape when enforcement does not apply; omission is not an implicit exemption.

### Redaction

- Do not log bearer tokens, admin token material, user token material, token hashes, provider keys, raw secret environment values, raw command environments, or raw prompts in browser-readable evidence. Internal recovery prompt artifacts are secret-redacted before persistence and remain excluded from browser list, direct, and nested artifact projections.
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
- Private account readback includes project inventory, session identity, project-creation failure state, active-run state, account usage, and project-scoped workflow/readback routes; unauthorized and forbidden responses for those API surfaces must also remain `no-store`.
- All `/api/admin/**` responses use `Cache-Control: no-store`, including readback, exports, key management, user/token operations, queue decisions, and maintenance mutations.

## Testing And Smoke Evidence

A Phase service change is not done until the relevant evidence exists or the gap is recorded with the required follow-up.

Use the narrowest test set that proves the changed contract:

- API route or DTO change: route-specific unit/integration tests plus browser caller coverage when browser behavior changes.
- Auth/account change: authorized, unauthorized, disabled-account, and cross-account denial coverage.
- DB schema change: schema creation and persistence/upgrade tests.
- Readback/artifact/package/asset change: account-scoped readback tests and path sanitization tests.
- Prototype route change: recovery input tests, stale-state or missing-source negative tests, bounded status tests, and route-specific acceptance evidence.
- Godot runtime route change: semantic-family declaration, viewport mode evidence where visual work is touched, feature-family reading evidence, and missing reference/recipe/manifest codes from `docs/standards/godot-engine-semantics.md` when sources are absent.
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
| GDD-to-module hardening route contracts | `py -3 scripts/python/phase_a_gdd_to_module_hardening_smoke.py --repository-root <repo>`; add `--project-root <hosted-project-root>` or API readback arguments when validating a concrete hosted project chain. Run evidence is written under `logs/phase-a-gdd-to-module-hardening/`. |
| Godot engine semantic registry | `dotnet test PhaseA.Platform.Tests --filter FullyQualifiedName~GodotEngineSemanticsTests` plus route-specific tests when route prompts/readback consume semantic evidence. |
| Godot UI capability contract | `dotnet test PhaseA.Platform.Tests --filter "FullyQualifiedName~GodotUiCapabilityContractTests|FullyQualifiedName~ProjectRouteStateArtifactServiceTests"` plus browser readback tests when UI closure surfaces change. |
| Godot UI style catalog and snapshot schema | `dotnet test PhaseA.Platform.Tests --filter "FullyQualifiedName~GodotUiStyleCatalogTests|FullyQualifiedName~GodotUiStyleSnapshotSchemaTests"` plus UI closure tests when style evidence is consumed. |
| Godot UI style closure | `dotnet test PhaseA.Platform.Tests --filter "FullyQualifiedName~GodotUiStyleClosureContractTests|FullyQualifiedName~ProjectRouteStateArtifactServiceTests"` for style gap rows, repair prompt inputs, and final-readiness blockers. |

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
- Every registered JSON route artifact must declare and exactly match its registry route ID, string `schema_version`, `status_dimension`, and allowed status subset, with `status` inside both vocabulary sets. Omitting fields or substituting another known route/schema/dimension does not create a legacy exemption.
- Transitional route states use canonical `queued|running`; legacy `writing`, `queued`, and `running` are non-fresh and cannot unlock downstream recommendations.
- `evidence_refs` should be an array of objects with `kind`, `path` or `artifact_id`, optional `run_id`, and optional `summary`. Paths must be sanitized and workspace-relative unless the evidence is an internal-only log.
- `evidence_refs.kind` is a closed enum by default: `log`, `artifact`, `sidecar`, `screenshot`, `db_row`, `smoke`, or `validator`. New kinds must update this standards document.

## Documentation Update Rules

- New durable architectural decisions require a Phase ADR or an update to an existing ADR, and must update `docs/architecture/ADR_INDEX_PHASE.md`.
- New cross-cutting conventions belong in this document, with links from `AGENTS.md`, `README.md`, `docs/PROJECT_DOCUMENTATION_INDEX.md`, and `docs/standards/_index.md` when they become agent-facing.
- New architecture rationale belongs under `docs/architecture/phase-service/**` unless it is a full arc42 overlay slice.
- New Phase architecture docs must update `docs/architecture/phase-service/_index.md`.
- New workflow evidence or operational runbooks belong under `docs/workflows/**` or `runtime/phase-a/**` as appropriate.

## Ordinary Runner Entry And Business Acceptance

- The production Project creation composition must provide the Windows Runner
  provisioner; success requires registered identity, persistent vault credential
  and verified ACLs. Passwords never enter argv, environment, files or logs.
- Native tests use disposable Projects and remove only their own registrations.
  Fresh-process verification reloads persisted registration without fixture setup.
- Final UI readback projects actual source hashes, is no-store, and fails closed
  for an incomplete full-target ledger or missing/changed current sources.
- `scripts/python/phase_a_business_chain_acceptance.py` reads authenticated GET
  evidence and emits passed/blocked/unavailable under logs. No credential means
  unavailable, never a default pass. It neither runs a model nor mutates a project.
- Test the native entry with `ProjectRunnerProvisioningTests`, source/readiness
  consumers with `ProjectRouteStateArtifactServiceTests`, and the Python acceptance
  command with `scripts.python.tests.test_phase_a_business_chain_acceptance`.
- Public behavior: `docs/workflows/phase-service-runner-and-business-acceptance.md`.
  CI fixture success does not prove production deployment or live project acceptance.
