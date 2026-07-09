# Split-Added Requirements Ledger

Source: post-split hardening review fixes. This ledger tracks normative requirements added after the original monolithic source coverage. It complements `98-original-to-split-audit.md` and `99-source-coverage.md`; those files prove original source coverage, while this file proves split-added P1/P2 hardening is not lost.

## Ledger Rules

- Every row has a stable `split_added_id`.
- Implementation evidence must cite the relevant row when it implements or intentionally defers the requirement.
- A row cannot be removed unless a later decision log or ADR supersedes it and updates this ledger.
- Phase exit evidence fails if it implements the affected area but does not classify the corresponding row as `implemented`, `not_applicable`, or `explicitly_deferred` with evidence.

## Added Requirements

| split_added_id | Requirement | Primary owner doc | Acceptance reference |
| --- | --- | --- | --- |
| `split_added_workflow_action_import_gdd_form` | Legacy GDD form import/backfill uses canonical workflow action `import_gdd_form` and writes explicit import/confirmation sidecar evidence before scene confirmation or requirement-map generation. | `02a-route-state-artifacts.md`, `02b-backend-api-contracts.md`, `02c-frontend-migration-compatibility.md`, `03-testing-observability-admin.md` | Descriptor, browser, service, and legacy migration tests cover the action and sidecar. |
| `split_added_prototype_alias_boundary` | Prototype-skeleton endpoint operations remain descriptor aliases/projections under canonical `create_prototype` unless a later decision log extends the canonical workflow action set. | `02b-backend-api-contracts.md`, `04a-route-contracts-and-guards.md` | Action registry parity tests reject alias IDs as canonical workflow recommendations. |
| `split_added_status_subset_contract` | Artifact-local statuses declare central vocabulary dimension and allowed subset; sidecars cannot redefine status dimensions. | `02a-route-state-artifacts.md`, `02c-frontend-migration-compatibility.md` | Status fixture and sidecar validator tests reject wrong-dimension or display-only values. |
| `split_added_phase0b_skeleton_guard_dependency` | `prototype-skeleton-guard` has a Phase 0B dependency matrix row and phase-exit enforcement. | `08-implementation-phases.md`, `02b-backend-api-contracts.md`, `03-testing-observability-admin.md` | Phase exit and route module contract tests fail when skeleton guard omits required 0B packages. |
| `split_added_metadata_db_table_contracts` | Admin review queue, diagnostic index, game-type maintenance records, and project-delete tombstones declare minimum metadata DB table contracts, keys, indexes, concurrency, export, and deletion lookup behavior. | `02a-route-state-artifacts.md`, `02b-backend-api-contracts.md`, `07-godot-diagnostics-quality-gates.md` | Additive migration/reuse and export/readback tests cover table contracts. |
| `split_added_style_schema_contract_profile` | The UI style fixture has a machine-readable schema contract profile for required fields, enum sets, cardinality, nested objects, and capability IDs; prose-only schema rules are invalid. | `06b-ui-style-snapshot-schema.md`, `06d-ui-style-schema-acceptance.md` | Fixture/profile/validator parity tests fail on divergence. |
| `split_added_full_target_capability_schedule` | Full-target UI capability packages have scheduled phase, trigger, owner evidence, and closure behavior; consumed capabilities cannot remain `not_consumed_by_first_slice`. | `10-recommended-first-slice.md`, `03-testing-observability-admin.md` | Full-target ledger tests validate schedule fields and consumed capability closure. |
| `split_added_durable_standards_destination_matrix` | Durable rules have one target standards/workflow/index destination before implementation is accepted. | `04c-route-operation-governance.md`, `09-risks-dod-open-questions.md` | Phase 0 standards-sync checklist maps every durable rule to its destination. |
| `split_added_dod_layering` | Program DoD, phase exit DoD, and first-slice DoD are separate so first-slice review does not pretend full program completion. | `09-risks-dod-open-questions.md`, `10-recommended-first-slice.md` | Phase evidence states which DoD layer is being claimed. |

## Acceptance

- `98-original-to-split-audit.md` and `99-source-coverage.md` remain source-coverage evidence for the original monolithic plan only.
- This ledger is the source of truth for split-added hardening requirements.
- Implementation review records zero unresolved P0/P1/P2 findings for missing split-added requirement coverage.
