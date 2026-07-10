# Phase A Route Operation Governance

Status: Active policy
Language: English
Scope: Browser-visible actions, route execution context, progress/readback, duplicate-run handling, secret boundaries, and preflight for Phase A GDD-to-module routes.

## Action Exposure

`PhaseA.Platform/Workflow/RouteActionDescriptors.cs` owns action exposure classes. Valid values are `user_visible`, `admin_visible`, `script_only`, and `internal`.

Normal project pages expose only user-safe current-stage actions, secondary actions, and readback views. Bulk backfill, cross-project audits, raw prompt inspection, source-boundary audits, and contract snapshot maintenance stay admin-only or script-first.

## Context Boundary

Route services use server-derived account/project context and validated source artifacts. Client payloads cannot override account ID, project ownership, admin role, source hashes, or route authority. Prompt builders receive explicit source artifacts and sanitized context, not raw request bodies as authority.

## Progress And Operation Status

Long-running routes return either an active run ID with polling/readback URL or an immediately readable route state. Operation status uses the bounded vocabulary `returned_existing`, `active_run_reused`, `created_run`, or `rejected`.

Route/readback `succeeded` maps to display-stage `completed` only after the relevant sidecar/readback artifact validates, including source hashes and source-boundary fields where applicable. Ordinary package download compatibility is not final package readiness.

## Duplicate-Run Control

Repeated calls with unchanged source hashes should return existing results or reuse active runs. Changed source hashes require explicit refresh intent when they invalidate confirmed decisions. Duplicate active run handling must use `operationStatus=returned_existing`, `active_run_reused`, or `rejected`; it must not silently start conflicting runs.

## Secret Boundary

`PhaseA.Platform/Workflow/SecretRedactionPolicy.cs` owns the central route evidence denylist. Prompts, sidecars, route evidence, admin exports, and browser DTOs must not persist provider secrets, bearer tokens, token hashes, admin tokens, API keys, or raw credential material. Secret redaction failure is P0.

## Preflight

`PhaseA.Platform/Workflow/RouteOperationPreflight.cs` owns the workflow-critical preflight capability registry. Capabilities include Codex command, Godot binary, hosted workspace root, metadata DB, and game-type index. Admin/operator readback may show redacted capability details; user readback gets capability status and browser-safe blocked reasons only.

Preflight checks are deterministic and must not invoke external LLM, Steam, GitHub, or public network services unless an admin/operator command explicitly asks for that.

## Evidence

Script-first admin/backfill operations write evidence under `logs/` with `timestamp_utc`, operation label, scoped IDs, and sanitized paths. Read-only audits use `scripts/python/phase_a_gdd_to_module_governance_audit.py`.
