# Route Readback, Recovery, And Freshness

Source: `../2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening.md` lines 891-982.

### 11.1.6 Phase Path And Readback Policy

Borrowed capability: TapTap documents path resolution so users, tools, and hosted environments agree on how paths are interpreted.

Phase A should add a Phase-specific path/readback policy for hosted prototype routes:

- Host filesystem paths stay internal.
- Browser/API output uses workspace-relative paths, artifact IDs, package names, or short-lived tickets.
- Route-state sidecars store stable project-relative paths where possible.
- Admin raw evidence can include more detail only behind admin auth and redaction rules.
- Prompt/evidence artifacts referenced by tests use sanitized paths.
- Package/preview/download routes never accept caller-provided absolute host paths.
- `routes/prototype-contract/latest.json` is the canonical recovery/readback authority for the prototype contract; any `meta/routes/prototype-contract/latest.json` file is a mirror/cache path and must be rejected as stale when `contract_hash` differs.
- Admin review queue raw entries are admin-only readback; normal-user surfaces may show redacted blocker summaries but not cross-account queue entries, raw prompt evidence, or host paths.

Acceptance criteria:

- A path/readback policy document or section exists before implementing new route-state readback surfaces.
- Tests cover path sanitization for user readback, admin readback, prompt evidence, package paths, and preview/download references.
- Browser/API responses never expose absolute host paths for normal users.
- Cross-account guessed project IDs cannot reveal whether a path, artifact, package, or prompt evidence exists.
- Readback tests prove canonical prototype-contract path resolution wins over stale mirror/cache files.
- Admin review queue readback tests prove normal users cannot list or infer cross-account queue entries.

### 11.1.7 Runtime Logs, Expected Exit, And Orphan Process Hygiene

Borrowed capability: TapTap separates expected lifecycle exits from crashes and bounds runtime log growth.

Phase A should extend runtime/route evidence guidance with:

- expected exit vs failure distinction for Codex/LLM helper processes
- bounded runtime/evidence log size or retention policy
- orphan-process diagnostics for route runners and preview/package helpers
- preserved failure evidence as sidecars, not overwritten summaries
- cleanup guidance that never deletes user workspaces silently

Acceptance criteria:

- Expected process exits are logged as lifecycle events, not crash evidence.
- Route runner failures preserve stderr/stdout or summarized evidence with redaction and size limits.
- Runtime diagnostics identify orphaned route/helper processes without killing them unless an explicit recovery script is invoked.
- Evidence cleanup rules preserve failure artifacts needed for repair and audit.

### 11.1.8 Cache And Freshness Policy

Borrowed capability: TapTap documents TTL, forced refresh, and write-through behavior for cached app data.

Phase A should define cache/freshness behavior for project-level workflow artifacts:

- Requirement map and prototype contract freshness is source-hash based, not time based.
- Admin readback summaries may be cached only when they record source hashes or `updated_utc`.
- Write operations that change GDD, scene route, contract snapshot, requirement map, or prototype contract must invalidate dependent recommendations.
- Manual refresh must be explicit and recorded.
- Old `unknown` freshness must remain diagnostic and cannot be promoted to success.
- Source-boundary freshness is invalid when prompt-producing routes lack `source_boundary_enforced=true` or saved prompt evidence includes forbidden mutable guide excerpts.
- Final readiness freshness depends on current UI closure, diagnostics, source-boundary, style snapshot, package artifact, preview ticket, and browser-safe readback; ordinary package download compatibility is not the same state.

Acceptance criteria:

- Freshness rules name source artifacts and invalidation edges.
- Write-through or invalidation tests cover GDD changes, scene route changes, contract snapshot changes, requirement map refresh, and contract freeze.
- Cached readback responses expose freshness status and source hash references.
- No route treats a stale or unknown cache as fresh without an explicit compatibility rule and test.
- Cache invalidation tests include source-boundary changes, admin review queue blocker resolution, style snapshot changes, and diagnostic spool blocker status changes when those affect final readiness.
- Freshness/readiness status uses the vocabulary from `02c-frontend-migration-compatibility.md` instead of reusing stage-display `completed`.

### 11.1.9 Directory-Scoped Agent Instructions

Borrowed capability: TapTap uses directory-scoped instructions for feature modules rather than relying only on one large repository guide.

Phase A should avoid expanding `AGENTS.md` for every route detail. Instead, use focused docs or instructions near the relevant route family.

Recommended targets:

- `docs/standards/phase-service.md` for service-wide invariants.
- A new route-module template document under `docs/workflows/` or `docs/standards/`.
- Route-specific notes near GDD/scene/prototype workflow docs.
- Execution plans for durable project-specific intent.

Acceptance criteria:

- New durable rules are placed in the narrowest authoritative document that owns the topic.
- `AGENTS.md` remains a routing map and does not duplicate detailed route-module schemas.
- Route implementation PRs link to the relevant route contract or standards section instead of relying on hidden conversation history.

### 11.1.10 User-Guided Ambiguity Resolution

Borrowed capability: TapTap tools explicitly instruct the agent to present choices to users when automatic selection would be unsafe.

Phase A should apply the same principle to ambiguous game-design workflow decisions:

- Multiple plausible scene routes require scene confirmation, not automatic selection.
- Multiple candidate required modules require requirement-map review or admin/user decision depending on priority.
- Multiple repair options require recommendation plus visible alternatives.
- Default type contract conflicts require admin-approved defer/conflict decisions when they affect P0/P1 behavior.

Acceptance criteria:

- The workflow recommendation can present one primary action while preserving safe secondary actions.
- Ambiguous P0/P1 scene/module decisions cannot be silently auto-selected.
- User-facing flows ask for confirmation when scene count, scene relation, or module priority changes the prototype scope.
- Admin-only decisions remain admin-only even when the LLM suggests a resolution.
