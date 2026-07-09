# Route Operation Governance

Source: `../2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening.md` lines 983-1111.

### 11.1.11 Capability Allowlist And Action Exposure

Borrowed capability: TapTap's Maker flow exposes only a small allowlist of runtime tools through MCP while keeping broader setup and maintenance behind CLI/admin flows.

Phase A should apply the same posture to browser-visible project actions:

- User project pages expose only the safe current-stage actions, safe secondary actions, and readback views.
- Bulk backfill, cross-project audits, raw prompt inspection, contract snapshot refresh inspection, and source-boundary audits stay admin-only or script-only.
- Admin UI can list these operations, but mutation still requires explicit admin intent, scoped IDs, and evidence creation.
- Route descriptors identify whether an action is `user_visible`, `admin_visible`, `script_only`, or `internal`.

Acceptance criteria:

- Every route action descriptor includes an exposure class: `user_visible|admin_visible|script_only|internal`.
- Browser tests assert normal users cannot see or invoke admin/script-only mutation actions.
- API tests assert hidden actions are not only hidden in the UI; unauthorized direct calls also fail with the standard account/auth error behavior.
- Adding a new action without an exposure class fails a guard test.

### 11.1.12 Context Boundary And DTO Hygiene

Borrowed capability: TapTap separates business context from transport-layer extras so handlers do not accidentally depend on hidden client details.

Phase A should define route execution context boundaries:

- Account/project authorization context.
- Route source context: GDD, scene route, requirement map, frozen contract, run state.
- Transport context: request ID, correlation ID, browser session, polling/readback concerns.
- Admin context: admin identity, scoped operation, redaction level.

Acceptance criteria:

- Route services do not accept browser-only DTOs as their internal source of authority; they receive validated account/project/source context.
- Tests cover that spoofed project IDs, account IDs, source hashes, or admin flags in client payloads cannot override server-derived context.
- Prompt builders receive explicit source artifacts and sanitized context, not raw request bodies.
- Readback DTOs omit internal-only context fields unless the route is admin-authenticated and redacted.

### 11.1.13 Progress And Long-Running Operation Feedback

Borrowed capability: TapTap tool handlers support progress notification channels for long-running work.

Phase A should express long-running progress through existing run state and readback surfaces:

- GDD requirement map generation, contract freeze, iteration planning, execute-next-goal, repair, UI closure, preview, and package should expose stable progress states.
- Progress should distinguish route/readback `queued|running|ready|blocked|needs_fix|succeeded|failed|cancelled|stale|unknown`, and the browser may map those into display-stage `not_started|ready|running|needs_review|blocked|completed|stale`.
- Browser polling should show the last meaningful status instead of only a spinner.

Acceptance criteria:

- Long-running POST routes either return an immediately readable route state or an active `runId` with polling/readback URL.
- Browser tests cover queued/running/blocked/failed/succeeded rendering for at least requirement map, iteration plan, and execute-next-goal.
- A failed long-running operation exposes a sanitized failure reason and evidence reference, not only `unhandled_request_failed`.
- Progress status cannot mark success unless the required sidecar/readback artifact exists and validates.
- Route/readback `succeeded` maps to stage `completed` only after the route artifact, source hashes, source-boundary fields where applicable, and browser-safe readback validate.
- Preview/package progress distinguishes ordinary package download compatibility from final package readiness.

### 11.1.14 Idempotent Recovery And Duplicate-Run Control

Borrowed capability: TapTap release guards include recovery behavior for existing PRs and avoid duplicating release state.

Phase A should apply this to route operations:

- Repeated POST calls with unchanged source hashes return existing results or reuse active runs.
- Changed source hashes require explicit refresh intent when they would invalidate confirmed user decisions.
- Duplicate active run creation is rejected or reused consistently.
- Recovery reads authoritative route state before starting new work.

Acceptance criteria:

- Tests cover double-click, browser retry, network retry, and concurrent duplicate POST behavior for requirement map, contract freeze, iteration plan, execute-next-goal, and UI closure.
- Duplicate run handling returns `operationStatus=returned_existing`, `active_run_reused`, or `rejected`; it must not silently start two conflicting runs.
- Recovery logic compares source hashes and operation scope before reusing a run.
- Existing active runs from another account are never visible or reusable across account boundaries.
- Recovery cannot reuse a run whose admin review queue blocker, diagnostic spool blocker, source-boundary status, or prototype-contract canonical hash no longer matches the current operation scope.

### 11.1.15 Credential, Token, And Secret Boundary

Borrowed capability: TapTap docs separate local credential preparation from runtime operations and avoid treating tokens as ordinary workflow data.

Phase A already has token hashing and secret rules. This plan should reinforce them for GDD/prototype workflow changes:

- Prompts, sidecars, route evidence, admin exports, and browser DTOs must not include provider secrets, auth tokens, token hashes, or raw credential material.
- Script/admin evidence records operation scope without copying secret-bearing environment variables.
- LLM/Codex prompt artifacts redact credentials before persistence.

Acceptance criteria:

- Tests or validators scan generated route evidence and prompt artifacts for known secret variable names and token-like fields.
- Redaction tests include fixture-based examples for environment variable names, provider keys, token hashes, bearer-like tokens, local absolute paths that contain user/account identifiers, and prompt/evidence/admin export samples.
- The validator owns a documented denylist and allowlist update path; adding a new secret-bearing variable or evidence field requires updating the fixture set or recording a non-applicability rationale.
- Admin exports redact token hashes and provider credentials even for admin users.
- Any new script that reads environment variables documents which ones are secret and proves they are not written to evidence.
- Secret redaction failure is P0 and blocks acceptance.

### 11.1.16 Configuration And Environment Preflight

Borrowed capability: TapTap Maker CLI performs setup and environment checks before exposing runtime operations.

Phase A should add deterministic preflight checks for workflow-critical capabilities:

- Codex command availability and shared invocation protocol.
- Godot binary availability where a route requires validation or preview/package.
- Hosted workspace root and project boundary availability.
- Metadata DB path readability through the platform service, without manual mutation.
- Game-type guide and `game-types.csv` availability for project creation/matching only.

Preflight relationship to workflow recommendation:

- Preflight output is an input to `ProjectWorkflowRouteService`, not a parallel source of truth.
- Blocking preflight failures produce `blockingIssues[]`, disabled `forbiddenActions[]`, and route/readback status reasons through the workflow recommendation state.
- Non-blocking preflight warnings may appear in admin/operator readback, but they cannot override source-hash or route-state authority.

Acceptance criteria:

- Admin/operator preflight can report missing Codex, Godot, workspace root, metadata DB access, and game-type guide/index inputs without starting a GDD/prototype run.
- User-facing project actions show blocked reasons when a required runtime dependency is unavailable.
- Normal-user preflight/readback responses expose capability status and blocked reason only; host paths, metadata DB paths, environment values, and workspace roots are visible only in admin-authenticated, redacted evidence.
- Preflight checks write sanitized evidence under `logs/`.
- Preflight does not validate by invoking external LLM/Steam/network services unless explicitly requested by an admin/operator command.
- Workflow recommendation tests cover missing Codex, missing Godot, workspace boundary failure, metadata DB access failure, and missing game-type guide/index inputs where those capabilities are required by the recommended action.

### 11.1.17 Documentation Indexing And Route Discoverability

Borrowed capability: TapTap keeps targeted docs for maker, paths, logs, guards, and feature modules, making operational behavior discoverable without reading code.

Phase A should keep this execution plan as intent and move durable implementation rules into authoritative docs during implementation:

- Route module contract template.
- Path/readback policy.
- Guard-test invariant list.
- Admin/backfill script evidence convention.
- Runtime lifecycle and expected-exit guidance.
- Cache/freshness policy.
- Godot diagnostics and quality-gate contract.
- Godot UI style theme contract.
- Project diagnostic spool and symptom-to-remediation guide.


Durable standards destination matrix:

| Durable rule family | Target authoritative destination | Implementation acceptance |
| --- | --- | --- |
| Route module contract template, action descriptor registry, status vocabulary, source-boundary schema, readiness labels, evidence ref kinds, no-store policy | `docs/standards/phase-service.md` plus `docs/standards/_index.md`; route-specific workflow docs may link to it but do not redefine it | Phase 0 standards-sync checklist and fixture parity tests pass. |
| Path/readback policy, cache/freshness policy, duplicate-run convention, progress/readback behavior, preflight behavior | `docs/standards/phase-service.md` and the relevant route workflow doc under `docs/workflows/` | Browser/API tests link the standards section and route workflow doc. |
| Admin review queue, diagnostic spool, project-delete tombstones, game-type maintenance records, audit/export behavior | `docs/standards/phase-service.md`; Phase ADR if metadata DB ownership, retention, auth/account boundary, or public API semantics change | Additive migration/reuse tests and admin export/readback tests pass. |
| Godot UI capability contract | `docs/standards/godot-ui-capability-contract.md`, linked from `docs/standards/_index.md`, README, project docs index, Phase architecture index, and agent routing | UI-touching route phase exit cites the standard and hash/version evidence. |
| Godot UI style contract and built-in style guides | `docs/standards/godot-ui-style-contract.md` plus `docs/ui-style-guides/`, linked from the same indexes | Style fixture/profile parity and style selection/freeze tests pass. |
| Godot diagnostics and quality gates | `docs/standards/godot-diagnostics-quality-gates.md`, linked from `docs/standards/_index.md`, README, project docs index, Phase architecture index, and agent routing | Diagnostic taxonomy/spool/remediation tests pass. |

Destination acceptance:

- Implementation cannot leave a durable rule only in this execution plan once the corresponding code/API/test behavior lands.
- Phase exit evidence includes a standards destination map for every implemented durable rule family above.
- If a rule appears in multiple target docs, exactly one doc is marked authoritative and the others link to it.

Acceptance criteria:

- Each durable rule added by implementation is linked from `docs/standards/_index.md`, `docs/standards/phase-service.md`, or a route workflow doc.
- Execution plan items that become permanent standards are not left only in the plan.
- `AGENTS.md` remains a concise router and links to durable docs instead of duplicating full rule text.
- A reviewer can find route contract, source-boundary, path/readback, guard-test, Godot UI style, Godot diagnostics, project diagnostic spool, and symptom-to-remediation rules from the docs index without scanning conversation history.
