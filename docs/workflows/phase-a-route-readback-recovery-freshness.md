# Phase A Route Readback, Recovery, And Freshness Policy

Status: Active policy
Language: English
Scope: Hosted prototype route readback, source recovery, and cache freshness for Phase A GDD-to-module workflows.

## Path And Readback Policy

Host filesystem paths stay internal. Normal browser/API readback uses project-relative paths, artifact IDs, package names, preview/download tickets, or redacted summaries.

Allowed normal-user path forms include examples such as:

- `meta/routes/gdd-requirements/latest.json`
- `routes/prototype-contract/latest.json`
- `project-package.zip`

Normal-user readback must not expose:

- Windows or Unix absolute host paths
- `file://` URLs
- external HTTP/HTTPS URLs as file evidence paths
- parent traversal such as `../outside.txt`
- raw prompt evidence, provider secrets, token material, or cross-account entries

`PhaseA.Platform/Workflow/RouteReadbackPathPolicy.cs` owns deterministic path checks used by tests and route governance. Package and preview/download routes must never accept caller-provided absolute host paths.

Admin readback may show more operational context only behind admin auth, no-store responses, and redaction. Admin review queue raw entries are admin-only; normal users may see redacted blocker summaries scoped to their own project.

## Prototype Contract Readback Authority

`routes/prototype-contract/latest.json` is the canonical recovery and readback authority for prototype contracts. `meta/routes/prototype-contract/latest.json` is a mirror/cache only. When both exist, mismatched `contract_hash` or content hash is stale and blocks downstream workflow readiness.

## Runtime Evidence And Process Lifecycle

Expected helper-process exits are lifecycle events, not crash evidence. Route runner failures preserve bounded stdout/stderr or summarized evidence with redaction. Runtime/orphan-process diagnostics identify candidate orphaned helpers without killing them unless an explicit recovery script is invoked.

Cleanup rules preserve failure artifacts needed for repair and audit. Cleanup must not silently delete user workspaces or unresolved P0/P1/P2 diagnostic evidence.

## Freshness Policy

Requirement map, prototype contract, skeleton, iteration, execution, and UI closure freshness is source-hash based, not time based.

`PhaseA.Platform/Workflow/RouteFreshnessPolicy.cs` owns the initial invalidation graph. Critical edges include:

- GDD document hash -> requirement map `source_gdd_hash`
- scene route hash -> requirement map and prototype contract `source_scene_route_hash`
- requirement map hash -> prototype contract, iteration plan, and UI closure `source_requirement_map_hash`
- prototype contract hash -> skeleton, iteration plan, and UI closure `source_contract_hash`
- admin review queue update -> workflow recommendation `admin_review_queue_updated_utc`
- diagnostic spool update -> workflow recommendation `diagnostic_spool_updated_utc`

`unknown` freshness remains diagnostic and cannot be promoted to success without an explicit compatibility rule and test. Stage-display `completed` is not a freshness value and must not replace route/readback `ready`, `blocked`, `stale`, `unknown`, or operation status values.

## Ambiguity Resolution

Ambiguous P0/P1 scene, module, repair, or default contract conflicts cannot be silently auto-selected. Workflow recommendation may present one primary action, but safe secondary actions and blocker summaries must remain visible. Admin-only conflict/defer decisions remain admin-only even when an LLM suggests a resolution.

## Narrow Documentation Rule

Detailed route-module rules live here, in `docs/workflows/phase-a-gdd-to-module-route-contracts.md`, or in `docs/standards/phase-service.md`. `AGENTS.md` remains a routing map and must not duplicate route schemas.
