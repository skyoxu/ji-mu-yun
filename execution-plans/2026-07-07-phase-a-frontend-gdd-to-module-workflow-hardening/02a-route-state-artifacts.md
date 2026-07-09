# Route-State Artifacts

Source: `../2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening.md` lines 100-321.

## 5. Proposed Artifacts

### 5.0 Common Route-State Conventions

Canonical hosted-project recovery paths must follow `AGENTS.md` and `README.md`. The prototype contract recovery source is `routes/prototype-contract/latest.json`. If existing readback code also uses a `meta/routes/**` mirror, the implementation may write a mirror, but recovery authority and source-hash comparisons must resolve the canonical `routes/prototype-contract/latest.json` first.

Prompt-producing route states must include source-boundary fields whenever a prompt or LLM/Codex input was built from project artifacts:

```json
{
  "source_boundary_enforced": true,
  "source_boundary": {
    "recovery_source_order_ref": "hosted-route-recovery-order.v1",
    "recovery_source_order": ["parsed game-type route profile", "meta/project-execution-guide.md", "routes/prototype-contract/latest.json", "current route latest state", "current goal/step/session state when applicable", "repair ledger and failing acceptance/Godot diagnostic evidence when applicable", "latest live platform acceptance blocker"],
    "route_authority_sources": ["docs/gdd/GDD.md"],
    "authority_sources": ["parsed game-type route profile", "meta/project-execution-guide.md", "routes/prototype-contract/latest.json", "docs/gdd/GDD.md", "current route latest state", "latest live platform acceptance blocker"],
    "source_hashes": {
      "meta/project-execution-guide.md": "sha256",
      "routes/prototype-contract/latest.json": "sha256",
      "docs/gdd/GDD.md": "sha256",
      "meta/routes/<route>/latest.json": "sha256"
    },
    "forbidden_source_patterns": ["docs/game-type-guides/** raw excerpts"],
    "prompt_evidence_refs": [],
    "checked_utc": "..."
  }
}
```

Prompt-producing route states must use the hosted-route recovery source order from `AGENTS.md`:

1. Parsed game-type route profile and selected route skill prompt block.
2. `meta/project-execution-guide.md`.
3. `routes/prototype-contract/latest.json`.
4. Current route latest state.
5. Current goal, step, repair step, or session state when applicable.
6. Repair ledger and failing acceptance/Godot diagnostic evidence for repair routes.
7. Latest live platform acceptance blocker.

Route-specific examples below may list only the route-local `authority_sources` that make the artifact stale or fresh. Implementation must expand them with `recovery_source_order_ref=hosted-route-recovery-order.v1` before prompt construction, and the saved prompt evidence must prove both the hosted-route recovery order and the route-local source hashes. Missing required recovery sources fail closed; route state and repair ledger memory cannot override the latest live platform acceptance blocker.

Non-prompt route states that do not build LLM/Codex input must use this explicit not-applicable shape instead of omitting the boundary silently:

```json
{
  "source_boundary_enforced": false,
  "source_boundary_not_applicable": {
    "reason": "readback_only|deterministic_state_transition|static_browser_projection",
    "checked_utc": "...",
    "decision_by": "system",
    "evidence_refs": []
  }
}
```

Acceptance criteria:

- Before GDD generation and prototype-contract freeze, game-type guides/default prototype contracts may be used only as declared upstream inputs and must be captured into GDD, scene route, requirement map, or frozen contract artifacts.
- After prototype-contract freeze, execute-next-goal, needs-fix, repair, UI closure, preview/package readiness, and downstream recommendation prompts must use the frozen project artifacts instead of rereading raw mutable guide excerpts as gameplay authority.
- `source_boundary_enforced=true` means saved prompt/evidence was built only from the declared authority sources and did not include raw mutable guide excerpts or unapproved cross-route memory.
- Prompt-producing route states must record the recovery authority source order, source hashes for every authority artifact used, and saved prompt evidence refs. Route completion is invalid when the saved prompt evidence cannot prove the exact artifact versions used.
- Route contract tests must fail when a prompt-producing route omits `meta/project-execution-guide.md`, current route latest state, repair ledger/evidence where applicable, or latest live platform acceptance blocker from its declared recovery source order.
- Route-local source-boundary examples are incomplete unless the route module contract declares how they are merged with `hosted-route-recovery-order.v1`; validators fail when a route uses only local `authority_sources` as the complete prompt authority.
- Missing or false `source_boundary_enforced` is valid only for route states that do not build prompts or LLM/Codex inputs; those routes must record the structured `source_boundary_not_applicable` object above.
- Prompt-source guard tests read saved prompt/evidence artifacts, not only this summary field.
- Canonical and mirrored artifact paths must record which path is authority and which path is a readback/cache mirror.
- Route states that refer to route action descriptors must record descriptor identity (`descriptor_id`, `descriptor_version`, or `descriptor_hash`) so recommendation readback can prove it used the same action catalog as the browser and API layer.
- Artifact-local `status` fields must declare their central vocabulary dimension and allowed subset. A sidecar may use a subset of the central dimension from `02c-frontend-migration-compatibility.md`, but it must not redefine a dimension or introduce unregistered values. Validators fail when a sidecar status is outside its declared dimension/subset.

### 5.1 `meta/routes/gdd-requirements/latest.json`

Add a project-level sidecar. This is the frontend equivalent of the Chapter 3 coverage matrix.

Recommended schema:

```json
{
  "schema_version": "gdd-requirements.v1",
  "route": "gdd-requirements",
  "project_id": "...",
  "source_gdd_path": "docs/gdd/GDD.md",
  "source_gdd_hash": "sha256",
  "source_scene_route_hash": "sha256",
  "source_contract_snapshot_hash": "sha256",
  "godot_ui_contract_version": "godot-ui-capability.v1",
  "source_godot_ui_contract_hash": "sha256",
  "status": "ready|needs_review|blocked|stale",
  "readiness_scope": "requirement_map",
  "status_reason": "",
  "updated_utc": "...",
  "source_boundary_enforced": true,
  "source_boundary": {
    "authority_sources": ["docs/gdd/GDD.md", "confirmed scene route", "project contract snapshot"],
    "forbidden_source_patterns": ["docs/game-type-guides/** raw excerpts"],
    "prompt_evidence_refs": [],
    "checked_utc": "..."
  },
  "evidence_refs": [],
  "coverage_summary": {
    "requirement_count": 0,
    "covered_count": 0,
    "missing_scene_count": 0,
    "missing_module_count": 0,
    "explicitly_deferred_count": 0,
    "conflict_count": 0
  },
  "requirements": [
    {
      "requirement_id": "REQ-001",
      "source_section": "Core Loop",
      "normalized_source_summary": "Player chooses a route node before each battle.",
      "source_language": "en",
      "source_excerpt_policy": "normalized_english_summary|redacted_project_owned_excerpt",
      "normalized_requirement": "Player chooses a route node before each battle.",
      "priority": "P0|P1|P2",
      "kind": "scene|mechanic|ui|state|asset|validation|meta",
      "mapped_scene_ids": ["route_map"],
      "mapped_required_module_ids": ["route_map_path_selection"],
      "mapped_iteration_goal_ids": [],
      "status": "mapped|missing_scene|missing_module|needs_review|explicitly_deferred|conflict",
      "defer_reason": "",
      "conflict_reason": "",
      "decision_by": "",
      "decision_role": "admin|system",
      "decision_utc": "",
      "decision_reason": "",
      "affected_requirement_ids": [],
      "acceptance_markers": ["Route node selection changes current path."]
    }
  ]
}
```

Acceptance criteria:

- A GDD with concrete scene and mechanic requirements produces at least one requirement row per concrete gameplay, scene, or UI requirement.
- Every `Always` scene from the confirmed scene route appears in at least one mapped requirement or has an explicit no-requirement rationale.
- Every `Always` required module from the project contract snapshot appears in at least one mapped requirement unless explicitly contradicted by the GDD.
- Every new requirement map created after Phase 0 records the Godot UI capability contract version/hash. Legacy maps without these fields are treated as `unknown` and require refresh before new contract freeze or new iteration plan creation.
- If the Godot UI capability contract hash changes, the previous requirement map is stale for new contract freeze or new iteration plan creation.
- If any P0 requirement is `missing_scene`, `missing_module`, `needs_review`, or `conflict`, the workflow blocks `prototype-contract-freeze` by default.
- The artifact is readable from the project route-state location and mirrored to the repo `meta/routes/gdd-requirements/latest.json` if current route-state conventions require mirroring.
- Tests cover normal mapping, missing scene, missing module, explicit defer, system conflict fallback, admin-approved conflict suppression, stale hash, and invalid JSON fallback.
- Artifact-local `explicitly_deferred` and `conflict` decisions require structured audit fields: `decision_by`, `decision_role`, `decision_utc`, `decision_reason`, and `affected_requirement_ids`; browser/API readback exposes the same data as camelCase.
- P0/P1 `explicitly_deferred` decisions are admin-only by default unless a later product decision grants normal users that authority with an explicit confirmation flow.
- `decision_*` fields are required only for `explicitly_deferred` and `conflict`; for all other requirement statuses they must be empty or omitted.
- `decision_role=system` may mark deterministic conflict or needs-review decisions, but it cannot explicitly defer P0/P1 requirements.
- When the GDD explicitly conflicts with a default required module, the requirement map first records `conflict`; suppressing that default module is allowed only after an admin records the required `decision_*` fields. A system-detected conflict does not automatically unblock contract freeze.
- System-detected conflicts must be surfaced in admin review/readback queues with blocking context instead of remaining only as hidden requirement-map rows.
- Admin review/readback queue entries include at least `account_id`, `project_id`, `requirement_id`, `blocking_reason`, `source_section`, `created_utc`, and `status`.
- User-facing readback must not expose cross-account admin review queue entries.
- A deferred or conflicted requirement is still visible in readback and cannot be deleted from the map; downstream plans must carry the defer/conflict reason when it affects generated modules.
- Requirement-map structured fields are English by default. Raw user-language excerpts are not stored in normal-user route-state readback; when needed for admin evidence they must be redacted, project-owned, and referenced through evidence refs rather than copied into `requirements[]`.

### 5.1.1 `meta/routes/scene-route/latest.json`

Add a project-level scene route confirmation sidecar. This is the authority for scene count, relationships, entry paths, exits, confirmation state, and the `source_scene_route_hash` consumed by requirement maps and prototype contracts.

Game-type structured source authority:

- `source_game_type_structured_hash` is computed from the canonical project structured game-type metadata owned by the Phase project metadata service and persisted through the metadata DB/project metadata read model.
- The canonical structured payload uses English normalized fields derived from the project creation Steam/game-type analysis, including selected game-type ID, selected guide ID, English Steam category/tag evidence, normalized `genre_tags` matches, match confidence/status, and maintenance-record ID when matching fails or is ambiguous.
- `GameTypeSource` remains the user's raw input and is not translated or used as the direct hash authority. It may appear only as a source ref or redacted evidence input for the structured analysis.
- The project contract snapshot may mirror the structured game-type payload for route recovery, but the metadata DB/project metadata read model remains the canonical owner unless a later Phase ADR changes ownership.
- Hash canonicalization uses English field names, sorted keys, normalized line endings, trimmed string values, deterministic array ordering for normalized tags/matches, and excludes volatile timestamps, run IDs, and raw prompt text.
- If the canonical structured payload is missing, stale, or cannot prove the selected game-type ID/guide ID, scene route generation or reconfirmation returns `game_type_structured_missing` or `game_type_structured_stale` before requirement map generation can continue.

Canonical structured game-type metadata payload:

```json
{
  "schema_version": "project-game-type-structured.v1",
  "project_id": "...",
  "raw_game_type_source_ref": "metadata_db:project.GameTypeSource",
  "raw_game_type_source_hash": "sha256",
  "selected_game_type_id": "card-game",
  "selected_guide_id": "card-game",
  "steam_app_refs": [],
  "steam_category_tags_en": [],
  "steam_genre_tags_en": [],
  "normalized_genre_tags_en": [],
  "matched_game_types_csv_row_id": "card-game",
  "matched_genre_tags": [],
  "match_status": "matched|ambiguous|unmatched|stale|missing",
  "match_confidence": "high|medium|low|unknown",
  "maintenance_record_id": "",
  "analysis_evidence_refs": [],
  "canonical_hash": "sha256",
  "updated_utc": "..."
}
```

The metadata DB/project metadata read model owns this payload. Project-local snapshots may mirror it only as recovery context and must not become the canonical hash source.

Recommended schema:

```json
{
  "schema_version": "scene-route.v1",
  "route": "scene-route-confirmation",
  "project_id": "...",
  "source_gdd_form_path": "meta/routes/gdd-question-form/latest.json",
  "source_gdd_form_ref": "...",
  "source_gdd_form_hash": "sha256",
  "source_game_type_structured_hash": "sha256",
  "source_contract_snapshot_hash": "sha256",
  "source_generated_gdd_hash": "",
  "scene_route_draft_hash": "sha256",
  "confirmed_scene_route_hash": "sha256",
  "status": "draft|needs_review|confirmed|stale|blocked",
  "status_reason": "",
  "stale_reasons": [],
  "confirmed_by": "",
  "confirmed_utc": "",
  "updated_utc": "...",
  "source_boundary_enforced": true,
  "source_boundary": {
    "authority_sources": ["gdd form answers", "game type structured fields", "project contract snapshot"],
    "source_hashes": {
      "meta/routes/gdd-question-form/latest.json": "sha256",
      "project-game-type-structured": "sha256",
      "project-contract-snapshot": "sha256"
    },
    "forbidden_source_patterns": ["unfrozen broad game-type guide excerpts after confirmation"],
    "prompt_evidence_refs": [],
    "checked_utc": "..."
  },
  "scenes": [
    {
      "scene_id": "route_map",
      "display_name": "Route Map",
      "purpose": "Choose the next reachable route node.",
      "entry_paths": ["class_select"],
      "exit_paths": ["battle"],
      "relationships": [
        {
          "target_scene_id": "battle",
          "relationship": "leads_to",
          "condition": "reachable node selected"
        }
      ],
      "ui_surface_expectations": ["route node list", "path highlight"],
      "no_ui_needed_reason": ""
    }
  ],
  "blocking_issues": [],
  "evidence_refs": []
}
```

Acceptance criteria:

- The scene route confirmation flow writes this sidecar before requirement map generation, whether confirmation is implemented through a new API or an existing browser flow.
- `confirmed_scene_route_hash` is the only scene-route hash consumed by requirement map generation, prototype-contract freeze, prototype-skeleton guard, and downstream stale detection.
- Downstream artifacts record this value as `source_scene_route_hash`; validators fail if a requirement map, prototype contract, skeleton guard, iteration plan, execution goal, or UI closure uses a `source_scene_route_hash` different from the current `confirmed_scene_route_hash`.
- Scene route freshness is computed from `source_gdd_form_hash`, `source_game_type_structured_hash`, `source_contract_snapshot_hash`, and the confirmed scene payload. If any of those upstream hashes changes, `status=stale` and `stale_reasons[]` records the changed source before requirement map generation or contract freeze may continue.
- `source_generated_gdd_hash` is recorded after full GDD generation when available. If `docs/gdd/GDD.md` changes without a matching scene route reconfirmation or a requirement-map conflict/needs-review record, downstream requirement map generation fails closed with `scene_route_unconfirmed` or a specific GDD/scene mismatch blocker.
- The GDD document-generation route is responsible for writing or refreshing `source_generated_gdd_hash` on this sidecar after `docs/gdd/GDD.md` is generated. If that write fails, the scene route sidecar becomes invalid for downstream requirement map generation.
- Requirement map generation fails closed when this sidecar is missing, not `confirmed`, stale, or has blocking issues.
- Workflow recommendation emits `confirm_scene_route` only when the route action descriptor maps to a confirmation API or browser flow that writes this sidecar.
- `scene_route_unconfirmed` blockers are represented in workflow recommendation `blocking_issues[]`, API error `details.domainCode`, and diagnostic spool records with evidence refs.
- Normal-user readback exposes scene IDs, display names, relationships, and user-actionable blockers, but not raw prompts, host paths, provider details, or cross-account evidence.

### 5.1.2 `meta/routes/gdd-document/latest.json`

Add a project-level GDD document-generation sidecar. This is the route-state authority for whether `docs/gdd/GDD.md` was generated from the current GDD form, confirmed scene route, project contract snapshot, and structured game-type metadata.

Recommended schema:

```json
{
  "schema_version": "gdd-document-generation.v1",
  "route": "gdd-document-generation",
  "project_id": "...",
  "source_gdd_form_hash": "sha256",
  "source_scene_route_hash": "sha256",
  "source_game_type_structured_hash": "sha256",
  "source_contract_snapshot_hash": "sha256",
  "generated_gdd_path": "docs/gdd/GDD.md",
  "generated_gdd_hash": "sha256",
  "scene_route_sidecar_path": "meta/routes/scene-route/latest.json",
  "scene_route_recorded_generated_gdd_hash": "sha256",
  "status_dimension": "route_readback",
  "status_allowed_values": ["queued", "running", "ready", "blocked", "failed", "stale", "unknown"],
  "status": "queued|running|ready|blocked|failed|stale|unknown",
  "status_reason": "",
  "stale_reasons": [],
  "updated_utc": "...",
  "source_boundary_enforced": true,
  "source_boundary": {
    "authority_sources": ["gdd form answers", "confirmed scene route", "project contract snapshot", "game type structured fields"],
    "source_hashes": {
      "meta/routes/gdd-question-form/latest.json": "sha256",
      "meta/routes/scene-route/latest.json": "sha256",
      "project-contract-snapshot": "sha256",
      "project-game-type-structured": "sha256"
    },
    "forbidden_source_patterns": ["unfrozen broad game-type guide excerpts after document generation"],
    "prompt_evidence_refs": [],
    "checked_utc": "..."
  },
  "blocking_issues": [],
  "evidence_refs": []
}
```

Acceptance criteria:

- GDD document generation writes this sidecar whenever it creates or refreshes `docs/gdd/GDD.md`.
- `generated_gdd_hash` is computed from normalized `docs/gdd/GDD.md` content and must equal `source_generated_gdd_hash` in `meta/routes/scene-route/latest.json` before requirement map generation may continue.
- If the generated GDD document is unchanged and all source hashes match, repeat POST calls return the existing route state or active run instead of creating duplicate work.
- If the scene route sidecar cannot be updated with `generated_gdd_hash`, the route records `gdd_scene_hash_write_failed`, returns a structured blocker, and does not allow requirement map generation to continue.
- If `source_gdd_form_hash`, `source_scene_route_hash`, `source_game_type_structured_hash`, or `source_contract_snapshot_hash` changes, the GDD document route state becomes `stale` and workflow recommendation must offer `generate_gdd_document` or the appropriate upstream reconfirmation action before `generate_requirement_map`.
- Normal-user readback exposes generated GDD status, source hash refs, browser-safe blockers, and next action only; it does not expose raw prompts, host paths, provider details, or cross-account evidence.

### 5.2 `meta/routes/admin-review-queue/latest.json`

Add an admin-only readback sidecar for project-level requirement and contract review blockers. This is the durable queue backing system-detected conflicts and admin-only defer/conflict decisions.

Persistence ownership:

- The project-local sidecar is the project readback cache, not the only durable admin index.
- Cross-project admin review, deleted-project lookup, and periodic maintenance require a deletion-safe persistence owner.
- Default owner for Phase 0A and Phase 1 is an additive metadata DB table with migration/recovery tests. An append-only diagnostic/admin index under the approved runtime evidence root may be added as evidence or rebuild source, but it is not the default browser/admin query owner unless a later Phase ADR or decision log changes that.
- Project sidecars are project-local readback caches only. They cannot be the persistence owner for unresolved admin queue entries, deleted-project lookup, or periodic maintenance.
- If both metadata DB and diagnostic/admin index are used, the metadata DB owns current query/index state and the project sidecar owns project-local recovery context. They must share queue entry IDs and source artifact hashes.
- Ordinary project deletion must preserve unresolved queue entries or write tombstone records that keep queue entry ID, account/project identity, route, severity, status, source artifact hash, decision history, and redacted summary.
- Deleted-project tombstone identity is shared across admin review queue and diagnostic spool records: `deletion_event_id` identifies one delete request/transaction and `project_tombstone_id` identifies the deleted project snapshot. Both IDs must appear on preserved admin queue tombstones and diagnostic spool/index records created by the same deletion.
- The project deletion route must call the admin review queue persistence service before destructive workspace cleanup. That service writes deleted-project tombstones or deleted-project markers through the metadata DB owner in the same logical delete operation, then mirrors sanitized evidence to any approved diagnostic/admin index. A project-local sidecar is never the tombstone write authority.
- Admin review queue owns human decisions and workflow blocker status. Project diagnostic spool owns failure diagnostics and remediation evidence. A single blocker may link both records by ID, but resolving a queue decision must not delete diagnostic spool history, and resolving a diagnostic must not approve/defer a requirement without a queue decision when admin decision metadata is required.

Minimum metadata DB table contract for admin review queue ownership:

- Table owner: Phase service metadata DB through additive migration/reuse; project sidecars are cache/readback only.
- Required stable key: `queue_entry_id` globally unique, plus `(account_id, project_id, route, requirement_id, source_artifact_hash, blocking_reason)` uniqueness for active open/superseding entries.
- Required columns: `queue_entry_id`, `account_id`, `project_id`, `project_name_snapshot`, `route`, `requirement_id`, `severity`, `blocking_reason`, `source_artifact_ref`, `source_artifact_hash`, `status`, `decision_by`, `decision_role`, `decision_utc`, `decision_reason`, `decision_payload_hash`, `decision_evidence_refs_json`, `created_utc`, `updated_utc`, `superseded_by_queue_entry_id`, `deletion_event_id`, and `project_tombstone_id`.
- Required indexes: active blockers by `(account_id, project_id, status, severity)`, admin maintenance by `(status, severity, updated_utc)`, deleted-project lookup by `(project_tombstone_id, deletion_event_id)`, and source refresh by `(project_id, source_artifact_hash)`.
- Concurrency rule: decision mutation uses current `status` plus `decision_payload_hash`; same-payload retry is idempotent, conflicting payload returns `409`, and supersede creates a new audit-backed state instead of rewriting history.
- Export rule: admin export reads from the metadata DB owner, joins only account-safe evidence refs, and never depends on scanning hosted project workspaces.

Minimum metadata DB table contract for game-type maintenance records:

- Table owner: Phase service metadata DB/project metadata read model through additive migration/reuse; project snapshots are recovery mirrors only.
- Required stable key: `maintenance_record_id` globally unique, plus `(account_id, project_id, raw_game_type_source_hash, selected_game_type_id, match_status)` uniqueness for active unresolved records.
- Required columns: `maintenance_record_id`, `account_id`, `project_id`, `project_name_snapshot`, `raw_game_type_source_ref`, `raw_game_type_source_hash`, `selected_game_type_id`, `selected_guide_id`, `matched_game_types_csv_row_id`, `matched_genre_tags_json`, `match_status`, `match_confidence`, `analysis_evidence_refs_json`, `review_status`, `decision_by`, `decision_role`, `decision_utc`, `decision_reason`, `created_utc`, `updated_utc`, `superseded_by_maintenance_record_id`, `deletion_event_id`, and `project_tombstone_id`.
- Required indexes: unresolved maintenance by `(review_status, match_status, updated_utc)`, project lookup by `(account_id, project_id, review_status)`, source refresh by `(raw_game_type_source_hash, selected_game_type_id)`, and deleted-project lookup by `(project_tombstone_id, deletion_event_id)`.
- Concurrency rule: maintenance decisions compare current `review_status` plus source hash; same decision retry is idempotent, conflicting decision or changed source hash returns `409`, and changed source evidence creates a superseding record.
- Export rule: admin maintenance export reads from the metadata DB owner, exposes only account-safe structured fields and evidence refs, and never exports raw prompts or provider payloads.

Minimum metadata DB table contract for project-delete tombstones:

- Table owner: Phase service metadata DB through additive migration/reuse. Diagnostic spool files and admin-review sidecars may mirror tombstone identity, but they are not the tombstone write authority.
- Required stable keys: `deletion_event_id` identifies one delete request/transaction and `project_tombstone_id` identifies the deleted project snapshot. The pair is shared by admin review queue tombstones, diagnostic index records, and project-delete readback.
- Required columns: `deletion_event_id`, `project_tombstone_id`, `account_id`, `project_id`, `project_name_snapshot`, `requested_by`, `requested_role`, `request_utc`, `delete_status`, `workspace_delete_status`, `diagnostic_preservation_status`, `admin_review_preservation_status`, `preserved_queue_entry_ids_json`, `preserved_diagnostic_ids_json`, `failure_domain_code`, `user_safe_summary`, `evidence_refs_json`, `created_utc`, and `updated_utc`.
- Required indexes: project tombstone lookup by `(account_id, project_id, project_tombstone_id)`, delete transaction lookup by `(deletion_event_id)`, failed cleanup review by `(delete_status, workspace_delete_status, updated_utc)`, and admin preservation review by `(admin_review_preservation_status, diagnostic_preservation_status, updated_utc)`.
- Concurrency rule: repeated delete for the same account/project returns the existing in-progress or completed tombstone when the request scope matches; conflicting delete scopes return `409`. Tombstone updates are append-or-advance only and cannot remove preserved admin review or diagnostic references.
- Export rule: admin export reads project-delete tombstones from the metadata DB owner, joins only redacted queue/diagnostic summaries, and keeps normal-user readback limited to the caller's project and browser-safe status.

Recommended schema:

```json
{
  "schema_version": "admin-review-queue.v1",
  "route": "admin-review-queue",
  "query_owner": "metadata_db",
  "mirror_owner": "none|diagnostic_index",
  "index_ref": "...",
  "updated_utc": "...",
  "status_dimension": "route_readback",
  "status_allowed_values": ["ready", "blocked", "stale"],
  "status": "ready|blocked|stale",
  "evidence_refs": [],
  "entries": [
    {
      "queue_entry_id": "ARQ-001",
      "deletion_event_id": "",
      "project_tombstone_id": "",
      "account_id": "...",
      "project_id": "...",
      "route": "gdd-requirements",
      "requirement_id": "REQ-001",
      "blocking_reason": "default_module_conflict",
      "source_section": "Core Loop",
      "source_artifact_path": "meta/routes/gdd-requirements/latest.json",
      "severity": "P0|P1|P2",
      "status": "open|approved|deferred|rejected|backlog|superseded|resolved",
      "blocking_effect": "blocks|unblocks|defer_until_recheck",
      "decision": "",
      "decision_by": "",
      "decision_role": "admin",
      "decision_utc": "",
      "decision_reason": "",
      "decision_evidence_refs": [],
      "defer_owner": "",
      "defer_expires_utc": "",
      "defer_recheck_trigger": "",
      "defer_affected_routes": [],
      "created_utc": "...",
      "updated_utc": "..."
    }
  ]
}
```

Acceptance criteria:

- Admin review queue entries are admin-only readback; normal-user project readback may show a redacted blocking summary but must not expose cross-account queue entries or raw admin evidence.
- Admin review queue implementation is invalid if unresolved P0/P1 entries can be lost by deleting the hosted workspace or by rewriting the project-local sidecar.
- Metadata DB ownership requires an additive schema migration/reuse test. Diagnostic-index ownership requires retention, redaction, cleanup, and deleted-project lookup tests.
- `query_owner` is always `metadata_db` for Phase 0A/Phase 1. `mirror_owner=diagnostic_index` is allowed only as append-only mirror/rebuild evidence and cannot become the browser/admin query authority without a later ADR or decision log.
- System-detected P0/P1 conflicts create or update queue entries and block contract freeze until an admin decision records `decision_by`, `decision_role`, `decision_utc`, and `decision_reason`.
- Admin queue decision mutation writes `decision`, `decision_by`, `decision_role`, `decision_utc`, `decision_reason`, and `decision_evidence_refs`. Queue `status` must be one of the schema values above and must match the durable result of the latest accepted decision.
- Admin queue status blocking semantics are explicit: `open`, `rejected`, and `backlog` keep P0/P1 downstream gates blocked; `approved` and `resolved` unblock only the specific queue entry they decide; `deferred` uses `blocking_effect=defer_until_recheck` and requires owner, expiry or recheck trigger, and affected route scope before any downstream gate may proceed.
- Deferred decisions must populate `defer_owner`, `defer_expires_utc` or `defer_recheck_trigger`, and `defer_affected_routes`; missing deferred metadata keeps `blocking_effect=blocks`.
- Queue entries are append-or-supersede, not deleted from history, when requirement maps are regenerated.
- Queue readback and mutation APIs enforce admin identity, account/project scope, redaction, and audit evidence.

### 5.3 `routes/prototype-contract/latest.json` Extensions

Extend the current prototype contract with provenance and freshness metadata.

Add fields:

```json
{
  "contract_hash": "sha256",
  "source_gdd_hash": "sha256",
  "source_scene_route_hash": "sha256",
  "source_requirement_map_hash": "sha256",
  "source_contract_snapshot_hash": "sha256",
  "godot_ui_contract_version": "godot-ui-capability.v1",
  "source_godot_ui_contract_hash": "sha256",
  "ui_style_id": "godot_cosmic",
  "ui_style_version": "1",
  "source_ui_style_contract_hash": "sha256",
  "ui_style_snapshot_hash": "sha256",
  "source_boundary_enforced": true,
  "source_boundary": {
    "authority_sources": ["docs/gdd/GDD.md", "confirmed scene route", "meta/routes/gdd-requirements/latest.json", "project contract snapshot"],
    "source_hashes": {
      "docs/gdd/GDD.md": "sha256",
      "meta/routes/scene-route/latest.json": "sha256",
      "meta/routes/gdd-requirements/latest.json": "sha256",
      "project-contract-snapshot": "sha256"
    },
    "forbidden_source_patterns": ["docs/game-type-guides/** raw excerpts"],
    "prompt_evidence_refs": [],
    "checked_utc": "..."
  },
  "freshness": {
    "status": "fresh|stale|unknown",
    "stale_reasons": []
  },
  "requirement_traceability": []
}
```

Acceptance criteria:

- `contract_hash` is computed from the canonical frozen contract payload, excluding volatile fields such as `updated_utc`/`updatedUtc`, `freshness`, and `contract_hash` itself.
- New contracts always include all source hash fields when source artifacts exist.
- If `docs/gdd/GDD.md`, scene route, requirement map, contract snapshot, Godot UI capability contract hash, Godot UI style contract hash, or frozen UI style snapshot hash changes, readback reports the contract as `stale`.
- Browser/API readback projects artifact-local `godot_ui_contract_version`, `source_godot_ui_contract_hash`, `ui_style_id`, `ui_style_version`, `source_ui_style_contract_hash`, and `ui_style_snapshot_hash` as `godotUiContractVersion`, `sourceGodotUiContractHash`, `uiStyleId`, `uiStyleVersion`, `sourceUiStyleContractHash`, and `uiStyleSnapshotHash`.
- Existing contracts without these fields load as `unknown`, not failed.
- New iteration plan creation blocks or returns `contract_stale` when the contract is stale. The user can refresh/freeze the contract and then create a new plan, but cannot bypass stale state with a plain continue confirmation.
- Execute-next-goal refuses to start against a stale contract unless the existing goal was created against the same stale contract hash and the user explicitly continues repair. Default behavior is to block.
- `routes/prototype-contract/latest.json` is the canonical recovery path. Any `meta/routes/prototype-contract/latest.json` file is a readback/cache mirror and must carry the same `contract_hash` or be treated as stale.

### 5.4 `meta/routes/workflow-recommendation/latest.json`

Frontend equivalent of Chapter 6 `chapter6-route --recommendation-only`.

Recommended schema:

```json
{
  "schema_version": "project-workflow-recommendation.v1",
  "project_id": "...",
  "action_descriptor_ref": {
    "descriptor_id": "phasea-workflow-actions",
    "descriptor_version": "1",
    "descriptor_hash": "sha256"
  },
  "recommended_action": "create_gdd|complete_gdd|import_gdd_form|analyze_game_type|confirm_scene_route|generate_gdd_document|generate_requirement_map|freeze_contract|refresh_contract|create_prototype|create_iteration_plan|execute_next_goal|run_needs_fix|run_ui_closure|preview_package|inspect_first|delete_project",
  "reason": "...",
  "status_dimension": "route_readback",
  "status_allowed_values": ["ready", "blocked", "stale", "needs_fix"],
  "status": "ready|blocked|stale|needs_fix",
  "readiness_scope": "workflow_recommendation",
  "status_reason": "",
  "blocking_issues": [],
  "allowed_actions": [
    {
      "action_id": "generate_requirement_map",
      "descriptor_hash": "sha256",
      "exposure_class": "user_visible|admin_visible|script_only|internal",
      "phase_eligibility": "active|not_active|blocked",
      "api_route": "",
      "browser_action_id": "",
      "display_label_key": "",
      "operation_scope": "project|route|run|readback|non_action",
      "readback_url": "",
      "blocking_issue_refs": []
    }
  ],
  "forbidden_actions": [
    {
      "action_id": "create_iteration_plan",
      "descriptor_hash": "sha256",
      "exposure_class": "user_visible|admin_visible|script_only|internal",
      "phase_eligibility": "not_active|blocked",
      "disabled_reason": "Route contract is not active for the current phase.",
      "disabled_domain_code": "route_contract_not_active|phase_gate_blocked|source_stale|admin_review_blocked|diagnostic_blocked|account_forbidden|not_applicable",
      "missing_contract_ref": "",
      "required_phase": "2",
      "blocking_issue_refs": []
    }
  ],
  "stale_artifacts": [],
  "updated_utc": "...",
  "evidence_refs": []
}
```

Acceptance criteria:

- The frontend primary action is driven by this recommendation instead of hardcoded button order.
- This recommendation is implemented as a structured read model from the existing `ProjectWorkflowRouteService` authority, or the existing service is extended to emit it; the platform must not keep two independent next-action engines.
- `recommended_action` values are canonical route action descriptor IDs. Existing endpoint names or service method names may be stored only as descriptor aliases/projections.
- The complete canonical workflow action set is exactly `create_gdd`, `complete_gdd`, `import_gdd_form`, `analyze_game_type`, `confirm_scene_route`, `generate_gdd_document`, `generate_requirement_map`, `freeze_contract`, `refresh_contract`, `create_prototype`, `create_iteration_plan`, `execute_next_goal`, `run_needs_fix`, `run_ui_closure`, `preview_package`, `inspect_first`, and `delete_project` until a later decision log extends it. Every value in this set must have a descriptor, browser action, or explicit non-action display mapping before it can appear in `recommended_action`, `allowed_actions`, or `forbidden_actions`.
- Phase 1 recommendation readback may expose only governed Phase 1 actions as `recommended_action`: `create_gdd`, `complete_gdd`, `import_gdd_form`, `analyze_game_type`, `confirm_scene_route`, `generate_gdd_document`, `generate_requirement_map`, `freeze_contract`, `refresh_contract`, and `inspect_first`. Phase-gated downstream subset actions such as `create_prototype`, `create_iteration_plan`, `execute_next_goal`, `run_needs_fix`, `run_ui_closure`, and `preview_package` must remain disabled in `forbidden_actions` with browser-safe reasons until their route contracts and descriptors pass the applicable phase gate.
- `allowed_actions[]` and `forbidden_actions[]` use the item schema above. Browser code must not infer disabled reasons from display text; it uses `disabled_domain_code`, `blocking_issue_refs`, and descriptor metadata.
- Stable disabled domain codes for workflow action gating are `route_contract_not_active`, `phase_gate_blocked`, `source_stale`, `admin_review_blocked`, `diagnostic_blocked`, `account_forbidden`, and `not_applicable`. Adding a new code requires status/error vocabulary fixture updates and browser mapping tests.
- If GDD is incomplete, recommendation is `create_gdd` or `complete_gdd`, and module generation actions are disabled.
- `complete_gdd` is a recommendation alias for returning to the existing GDD form/draft-completion browser flow. It must map to a route action descriptor or browser action ID before it can be emitted.
- `import_gdd_form` is the canonical workflow action for legacy projects where `docs/gdd/GDD.md` exists but `meta/routes/gdd-question-form/latest.json` is missing. It must map to a non-destructive import/backfill or confirmation flow that writes an explicit legacy import sidecar and user/admin confirmation evidence before scene confirmation, GDD document generation, requirement-map generation, or contract freeze can proceed.
- The canonical legacy import sidecar path is `meta/routes/gdd-question-form/legacy-import/latest.json`. It records `schema_version=legacy-gdd-form-import.v1`, `route=import_gdd_form`, `project_id`, `source_gdd_path`, `source_gdd_hash`, optional `source_gdd_form_hash` when a form draft is reconstructed, `import_mode=backfill|confirm_existing_gdd`, `status_dimension=route_readback`, `status_allowed_values=["ready","blocked","failed","stale"]`, `status`, `confirmation_required`, `confirmed_by`, `confirmed_utc`, `blocking_issues`, `evidence_refs`, and `updated_utc`.
- `import_gdd_form` cannot unblock scene confirmation, GDD document generation, requirement-map generation, or contract freeze until the legacy import sidecar exists, references the current `docs/gdd/GDD.md` hash, and records either a user confirmation, an admin confirmation, or a deterministic backfill evidence ref. If `docs/gdd/GDD.md` changes after the sidecar is written, the sidecar becomes `stale`.
- If canonical structured game-type metadata is missing, stale, ambiguous, or unmatched, recommendation is `analyze_game_type`; that action must map to a project metadata analysis/backfill API or browser/admin-safe flow that writes the canonical English structured metadata payload before scene confirmation or GDD document generation proceeds.
- If scene route is missing, recommendation is `confirm_scene_route`; that action must map to the existing scene-route confirmation browser flow or a concrete confirmation API before it can be emitted.
- If scene route is confirmed but `docs/gdd/GDD.md` is missing, stale, or not reflected in `source_generated_gdd_hash`, recommendation is `generate_gdd_document`, not `generate_requirement_map`.
- If the requirement map has P0/P1 gaps, recommendation is `inspect_first` or `generate_requirement_map`, not `create_iteration_plan`; the route/readback status uses `needs_fix` or `blocked`, while stage-display UI may map that to `needs_review`.
- `inspect_first` is a non-action display mapping unless a later implementation adds a concrete inspection API. It must open the existing project workflow/readback surface focused on `blocking_issues`, stale artifacts, requirement gaps, admin review summaries, and diagnostic summaries, and it must not start a run or mutate project state.
- If the contract is stale, recommendation is `freeze_contract` or `refresh_contract`.
- If prototype state is missing, recommendation is `create_prototype`.
- If an iteration plan exists and has a pending goal, recommendation is `execute_next_goal`.
- If latest validation has a P0/P1 blocker, recommendation is `run_needs_fix`.
- `delete_project` is a route action descriptor for the existing user project deletion flow; it must map to the ordinary project-delete API/browser action and preserve admin review/diagnostic tombstone evidence before destructive workspace cleanup.
- Tests cover each recommendation transition and fail if a `recommended_action` value has no route action descriptor, browser action, or explicit non-action display mapping.
- Tests fail if workflow recommendation uses an action descriptor hash/version that differs from the browser/API action catalog.

### 5.5 `meta/routes/prototype-skeleton/latest.json` Compatibility Guard

The target workflow includes `prototype-skeleton`, but the first implementation slice does not refactor skeleton creation. To avoid a grey zone between old prototype creation and the new contract chain, skeleton creation must still consume the frozen prototype contract when the new chain is active.

Acceptance criteria:

- New projects using this refactor cannot create or refresh a skeleton from stale, missing, or unknown prototype-contract sources.
- Skeleton route readback records at least `source_contract_hash`, `source_requirement_map_hash`, `source_gdd_hash`, `source_scene_route_hash`, `updated_utc`, and `evidence_refs`, or records a legacy compatibility reason that blocks new module execution until the contract chain is refreshed.
- Existing skeleton/prototype compatibility does not become final readiness evidence unless preview/package readiness separately validates current source hashes, diagnostics, tickets, and browser-safe readback.

### 5.6 `meta/routes/ui-wiring/latest.json`

Frontend equivalent of Chapter 7 UI wiring closure.

Recommended schema:

```json
{
  "schema_version": "ui-wiring-closure.v1",
  "project_id": "...",
  "source_iteration_session_id": "...",
  "source_iteration_session_hash": "sha256",
  "source_validation_input_hash": "sha256",
  "source_contract_hash": "sha256",
  "source_requirement_map_hash": "sha256",
  "source_godot_ui_contract_hash": "sha256",
  "source_ui_style_contract_hash": "sha256",
  "ui_style_snapshot_hash": "sha256",
  "status": "ready|needs_fix|succeeded|blocked|stale",
  "readiness_scope": "ui_wiring_closure",
  "status_reason": "",
  "updated_utc": "...",
  "source_boundary_enforced": true,
  "source_boundary": {
    "authority_sources": ["routes/prototype-contract/latest.json", "meta/routes/gdd-requirements/latest.json", "current iteration session", "latest validation blockers"],
    "forbidden_source_patterns": ["docs/game-type-guides/** raw excerpts"],
    "prompt_evidence_refs": [],
    "checked_utc": "..."
  },
  "reference_example_copy_evidence": {
    "source_example_id": "",
    "source_example_path": "",
    "reference_index_path": "docs/reference/godot-official-examples-index.md",
    "manifest_path": "",
    "manifest_hash": "",
    "manifest_missing_rationale": "",
    "directory_inspection_summary": "",
    "copy_mode": "read_only_reference|copy_all|include_patterns|blocked_manifest_missing|not_applicable",
    "copied_files": [],
    "skipped_files": [],
    "target_root": "",
    "license_refs": [],
    "required_input_actions": [],
    "required_project_settings": [],
    "validation_refs": []
  },
  "feature_family_reading_evidence": [
    {
      "feature_family": "ui|input|physics_collision|camera|third_person_camera|save_load|materials_rendering|audio_video|ads_platform|other",
      "standards_read": [],
      "recipes_read": [],
      "reference_examples_read": [],
      "reference_index_path": "docs/reference/godot-official-examples-index.md",
      "recipe_index_path": "docs/reference/godot-recipes-index.md",
      "missing_source_diagnostics": [],
      "relevance_summary": "",
      "checked_utc": "..."
    }
  ],
  "evidence_refs": [],
  "godot_ui_contract_version": "godot-ui-capability.v1",
  "ui_style_id": "godot_cosmic",
  "ui_style_version": "1",
  "player_flows": [],
  "ui_surface_matrix": [
    {
      "feature": "route_map_path_selection",
      "source_requirement_ids": ["REQ-001"],
      "source_goal_ids": [],
      "ui_surface": "RouteMapView",
      "godot_scene_path": "res://...",
      "godot_node_path": "Main/CanvasLayer/RouteMapView",
      "godot_surface_type": "control|hud_canvas_layer|custom_canvas_item|world_space_2d|world_space_3d|subviewport|no_ui_needed",
      "layout_strategy": "container_theme|anchors_safe_area|fixed_board_with_responsive_bounds|world_overlay|explicit_no_ui",
      "ui_construction_owner": "tscn_scene|packed_scene_instance|ready_built_tree|dynamic_item_factory|static_scene|not_applicable",
      "ui_update_ownership_mode": "retained_typed_references|registered_control_map|state_apply_pass|dynamic_item_factory|no_dynamic_update|not_applicable",
      "ui_state_owner": "typed_csharp_state|typed_gdscript_state|view_model|presenter|route_state|scene_owner|not_applicable",
      "ui_cleanup_policy": "scene_tree_owner|queue_free_dynamic_items|registry_unregister|signal_scope_dispose|not_applicable",
      "input_paths": ["mouse_left", "touch_press"],
      "focus_navigation": {
        "keyboard": "covered|not_applicable|missing",
        "gamepad": "covered|not_applicable|missing",
        "mouse_touch": "covered|not_applicable|missing"
      },
      "feedback_states": ["idle", "hover", "pressed", "selected", "disabled"],
      "camera_layer_boundary": "ui_canvas_layer_separate_from_world_camera",
      "camera_controller_profile": "none|third_person_camera_rig|camera2d_fixed|camera2d_follow|camera3d_custom_approved|not_applicable",
      "camera_rig_scene_path": "res://Game.Godot/Scenes/Camera/ThirdPersonCameraRig.tscn",
      "camera_rig_script_path": "res://Game.Godot/Scripts/Camera/ThirdPersonCameraRig.cs",
      "camera_input_actions": ["camera_yaw", "camera_pitch", "camera_zoom"],
      "camera_collision_policy": "spring_arm_collision|raycast_occlusion|disabled_with_rationale|not_applicable",
      "asset_size_source": "theme_metric|control_min_size|texture_import_metadata|documented_builtin_primitive|generated_artifact_metadata|aabb|get_aabb|collision_shape|not_applicable",
      "custom_drawing_surface": "none|Control._draw|CanvasItem._draw|Line2D|Polygon2D|MeshInstance2D|ArrayMesh|ImmediateMesh|SubViewport",
      "animation_state_ref": "AnimationPlayer:RouteMapSelection",
      "animation_profile": "animation_player_simple|animation_tree_state_machine|animation_tree_blendspace|repo_character_animation_profile|animation_not_applicable",
      "animation_state_owner": "AnimationPlayer|AnimationTree|repo_character_animation_profile|not_applicable",
      "animation_transition_policy": "typed_state_enum|mapping_table|profile_owned|not_applicable",
      "material_rendering_policy": "solid_3d_standard|transparent_3d_standard|solid_2d_canvas|canvas_item_material|shader_material|existing_material_resource|not_applicable",
      "rendering_atmosphere_profile": "ambient_3d_default|directional_key_light|local_light_group|environment_fog_atmosphere|postprocess_profile|rendering_not_applicable",
      "rendering_environment_owner": "WorldEnvironment|Environment_resource|scene_owned_lights|not_applicable",
      "rendering_readability_evidence_refs": [],
      "typed_state_ref": "RouteMapSelectionState",
      "player_action": "Select reachable next node",
      "system_response": "Highlight path and advance to battle",
      "state_boundary": "Run route state changes only after confirmed selection",
      "validation_refs": [],
      "exemption": {
        "kind": "none|no_ui_needed|style_not_applicable",
        "reason": "",
        "decision_by": "",
        "decision_role": "system|admin|user",
        "decision_utc": "",
        "evidence_refs": []
      },
      "status": "covered|missing_ui|missing_feedback|needs_fix|no_ui_needed"
    }
  ],
  "summary": {}
}
```

Acceptance criteria:

- UI closure cannot start until the core module plan has no unresolved P0/P1 goals, unless the user explicitly runs preview mode.
- Preview mode produces advisory UI closure output only; it cannot mark final readiness as passed and cannot generate final-package readiness approval.
- Every completed P0/P1 gameplay requirement has a UI surface or explicit `no_ui_needed` rationale.
- `no_ui_needed` exempts only the UI surface requirement. `style_not_applicable` exempts only the style contract requirement. A feature with no player-visible UI may record both, but each exemption needs its own reason, decision role, timestamp, and evidence refs.
- P0/P1 `no_ui_needed` or `style_not_applicable` decisions created by the system are blocking `needs_review` until confirmed by an admin or by an explicit user confirmation flow allowed by a later product decision.
- Missing player action, system response, or state boundary marks the item `needs_fix`.
- UI closure can produce follow-up iteration goals for missing UI wiring.
- Frontend displays UI closure status separately from gameplay module status.
- UI closure records the iteration session hash, validation input hash, frozen contract hash, requirement map hash, Godot UI capability contract hash, Godot UI style contract hash, and UI style snapshot hash that produced the closure result.
- UI closure validation inputs include latest validation blockers, Godot diagnostics, screenshot/canvas/exported visual evidence references, UI closure mode, manual needs-fix inputs used for closure, and any repair evidence selected as current acceptance authority.
- UI closure returns `stale` or `blocked` instead of final readiness when current iteration session, validation inputs, contract, requirement map, Godot UI capability contract hash, Godot UI style contract hash, or UI style snapshot hash differs from the recorded source hash set.
- Tests cover UI closure `stale` status when the recorded iteration session, validation input, contract, requirement map, Godot UI capability contract hash, Godot UI style contract hash, or UI style snapshot hash does not match current sources.
- Every non-`no_ui_needed` P0/P1 UI surface records a Godot scene path or node path, surface type, layout strategy, input path, feedback state list, and validation reference.
- UI closure blocks final readiness when a required UI surface uses absolute-position-only layout without an explicit fixed-format rationale, when keyboard/gamepad/mouse-touch focus status is missing for an interactive surface, or when camera/layer boundaries are not stated.
- Custom drawing requirements must name the Godot drawing surface (`Control._draw`, `CanvasItem._draw`, `Line2D`, `Polygon2D`, `ArrayMesh`, `ImmediateMesh`, or `SubViewport`) and include redraw/input/state validation evidence.
- 2D/3D asset and geometry sizing cannot be guessed. The closure record must cite a measurable source such as theme metrics, `Control.custom_minimum_size`, texture import metadata, `AABB`, `get_aabb()`, collision shapes, or an explicit not-applicable rationale.
- UI closure acceptance uses the P0/P1/P2 severity standard; a phase cannot pass with unresolved Godot UI contract gaps.
