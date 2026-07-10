# Source Coverage Map

Source: `../2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening.md`

| Source lines | Split document | Notes |
| --- | --- | --- |
| 1-99 | [01-overview-workflow.md](01-overview-workflow.md) | Overview, Goals, Workflow, Severity |
| 100-321 | [02a-route-state-artifacts.md](02a-route-state-artifacts.md) | Route-state sidecars, including scene route, GDD document generation, requirement map, workflow recommendation, source hashes, freshness fields, UI closure artifact |
| 322-466 | [02b-backend-api-contracts.md](02b-backend-api-contracts.md) | Backend services, API routes, DTO projections, route execution boundaries |
| 467-574 | [02c-frontend-migration-compatibility.md](02c-frontend-migration-compatibility.md) | Frontend workflow surfaces, migration, compatibility |
| 575-750 | [03-testing-observability-admin.md](03-testing-observability-admin.md) | Testing Strategy, Observability, Admin Readback |
| 751-890 | [04a-route-contracts-and-guards.md](04a-route-contracts-and-guards.md) | Route contracts, action descriptors, deterministic guards, admin/backfill operations |
| 891-982 | [04b-route-readback-recovery-and-freshness.md](04b-route-readback-recovery-and-freshness.md) | Path/readback policy, runtime evidence, cache/freshness, ambiguity handling |
| 983-1111 | [04c-route-operation-governance.md](04c-route-operation-governance.md) | Action exposure, DTO hygiene, progress, idempotency, secrets, preflight, docs indexing |
| 1112-1230 | [05-godot-ui-capability-contract.md](05-godot-ui-capability-contract.md) | Godot UI Capability Contract Migration |
| 1231-1377 | [06a-ui-style-migration-overview-and-catalog.md](06a-ui-style-migration-overview-and-catalog.md) | TapTapMarker UI Style Migration Overview, Checklist, Catalog |
| 1378-2178 | [06b-ui-style-snapshot-schema.md](06b-ui-style-snapshot-schema.md), [schemas/godot-ui-style-contract.v1.profile.json](schemas/godot-ui-style-contract.v1.profile.json), [schemas/godot-ui-style-contract.v1.field-map.json](schemas/godot-ui-style-contract.v1.field-map.json), [schemas/gdd-to-module-capability-inventory.v1.json](schemas/gdd-to-module-capability-inventory.v1.json), [schemas/split-added-acceptance-registry.v1.json](schemas/split-added-acceptance-registry.v1.json), [schemas/godot-ui-style-contract.v1.example.json](schemas/godot-ui-style-contract.v1.example.json), [06d-ui-style-schema-acceptance.md](06d-ui-style-schema-acceptance.md) | Godot UI style snapshot map, validation profile, exhaustive bidirectional field contract, canonical capability inventory, stable owner/acceptance registry, enum-declaration example fixture, and acceptance rules |
| 2179-2236 | [06c-style-aware-ui-closure.md](06c-style-aware-ui-closure.md) | Style-Aware UI Closure |
| 2237-2412 | [07-godot-diagnostics-quality-gates.md](07-godot-diagnostics-quality-gates.md) | Godot Diagnostics And Quality Gate Migration |
| 2413-2621 | [08-implementation-phases.md](08-implementation-phases.md) | Implementation Phases |
| 2622-2717 | [09-risks-dod-open-questions.md](09-risks-dod-open-questions.md) | Risks, Definition Of Done, Open Questions, Phase 1 Defaults |
| 2718-2739 | [10-recommended-first-slice.md](10-recommended-first-slice.md) | Recommended First Implementation Slice |

## Coverage Assertion

The split documents and machine-contract bundle cover source lines 1-2739 with no intentional omissions. Later normalization patches in the split documents supersede inconsistent wording from the monolithic source where noted in the affected split document, including the explicit GDD document-generation sidecar/status/action needed by the current frontend workflow. For source lines 1378-2178, the embedded JSON occupies lines 1383-2146 and `schemas/godot-ui-style-contract.v1.field-map.json` is its exhaustive bidirectional field contract: each JSON source pointer maps to a preserved or explicitly normalized fixture path, each fixture path reverses to source or is marked `split_added`, source lines are checked against actual source keys, and each row resolves a profile rule and acceptance reference. The surrounding prose and acceptance lines are covered by `06b` and `06d`. The profile is the validation entrypoint; the capability inventory validates required owner/phase/trigger/scope/acceptance metadata but does not claim runtime closure; the acceptance registry resolves stable ownership and section-bounded acceptance IDs; and the example fixture proves the complete field shape remains parseable.

## Split-Added Requirements

- Split-added hardening requirements are tracked separately in [97-split-added-requirements-ledger.md](97-split-added-requirements-ledger.md); original source-line coverage alone is not sufficient implementation readiness evidence.
- `04d-godot-engine-semantics-and-reference-examples.md` is post-split hardening coverage for Godot engine semantics and curated official reference examples; it is intentionally tracked through the split-added ledger rather than original source-line coverage.
