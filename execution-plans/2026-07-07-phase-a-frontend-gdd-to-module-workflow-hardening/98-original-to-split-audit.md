# Original-To-Split Comparison Audit

Status: Complete comparison for the split execution plan. Future implementation work should use this split directory as the primary plan and treat the monolithic source document as source history.

Original source: `../2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening.md`

Primary index: [00-index.md](00-index.md)

Coverage map: [99-source-coverage.md](99-source-coverage.md)

Machine-readable contract example/schema fixture: [schemas/godot-ui-style-contract.v1.example.json](schemas/godot-ui-style-contract.v1.example.json)

## Comparison Method

- The original monolithic document has 2739 lines.
- The split coverage ranges are contiguous from source line 1 through source line 2739.
- Every original top-level and subsection heading is mapped to the split output that owns it. Most headings map to one split Markdown document; intentionally split headings such as route governance and the large style schema block map to multiple split outputs plus the machine-readable JSON fixture.
- Normalization patches in the split documents supersede weaker or ambiguous wording from the source history. These normalizations are intentional hardening changes, not omissions.
- The full TapTapMarker non-technology UI framework capability target is preserved in [06a-ui-style-migration-overview-and-catalog.md](06a-ui-style-migration-overview-and-catalog.md). TapTapMarker runtime technology remains excluded.

## Source Range Coverage

| Original source lines | Split output | Coverage result |
| --- | --- | --- |
| 1-99 | [01-overview-workflow.md](01-overview-workflow.md) | Covered |
| 100-321 | [02a-route-state-artifacts.md](02a-route-state-artifacts.md) | Covered |
| 322-466 | [02b-backend-api-contracts.md](02b-backend-api-contracts.md) | Covered |
| 467-574 | [02c-frontend-migration-compatibility.md](02c-frontend-migration-compatibility.md) | Covered |
| 575-750 | [03-testing-observability-admin.md](03-testing-observability-admin.md) | Covered |
| 751-890 | [04a-route-contracts-and-guards.md](04a-route-contracts-and-guards.md) | Covered |
| 891-982 | [04b-route-readback-recovery-and-freshness.md](04b-route-readback-recovery-and-freshness.md) | Covered |
| 983-1111 | [04c-route-operation-governance.md](04c-route-operation-governance.md) | Covered |
| 1112-1230 | [05-godot-ui-capability-contract.md](05-godot-ui-capability-contract.md) | Covered |
| 1231-1377 | [06a-ui-style-migration-overview-and-catalog.md](06a-ui-style-migration-overview-and-catalog.md) | Covered |
| 1378-2178 | [06b-ui-style-snapshot-schema.md](06b-ui-style-snapshot-schema.md), [schemas/godot-ui-style-contract.v1.example.json](schemas/godot-ui-style-contract.v1.example.json), and [06d-ui-style-schema-acceptance.md](06d-ui-style-schema-acceptance.md) | Covered through schema map, machine-readable contract example/schema fixture, and acceptance rules |
| 2179-2236 | [06c-style-aware-ui-closure.md](06c-style-aware-ui-closure.md) | Covered |
| 2237-2412 | [07-godot-diagnostics-quality-gates.md](07-godot-diagnostics-quality-gates.md) | Covered |
| 2413-2621 | [08-implementation-phases.md](08-implementation-phases.md) | Covered |
| 2622-2717 | [09-risks-dod-open-questions.md](09-risks-dod-open-questions.md) | Covered |
| 2718-2739 | [10-recommended-first-slice.md](10-recommended-first-slice.md) | Covered |

Result: no source-line gap or overlap remains in the split plan.

## Original Heading Coverage

| Original heading | Source line | Split output |
| --- | ---: | --- |
| Phase A Frontend GDD-To-Module Workflow Hardening Plan | 1 | [01-overview-workflow.md](01-overview-workflow.md) |
| 1. Background | 8 | [01-overview-workflow.md](01-overview-workflow.md) |
| 2. Goals | 20 | [01-overview-workflow.md](01-overview-workflow.md) |
| 3. Non-Goals | 32 | [01-overview-workflow.md](01-overview-workflow.md) |
| 4. Target Frontend Workflow | 44 | [01-overview-workflow.md](01-overview-workflow.md) |
| 4.1 Naming Conventions | 73 | [01-overview-workflow.md](01-overview-workflow.md) |
| 4.2 Acceptance Severity Standard | 83 | [01-overview-workflow.md](01-overview-workflow.md) |
| 5. Proposed Artifacts | 100 | [02a-route-state-artifacts.md](02a-route-state-artifacts.md) |
| 5.1 `meta/routes/gdd-requirements/latest.json` | 102 | [02a-route-state-artifacts.md](02a-route-state-artifacts.md) |
| 5.2 `routes/prototype-contract/latest.json` Extensions | 177 | [02a-route-state-artifacts.md](02a-route-state-artifacts.md) |
| 5.3 `meta/routes/workflow-recommendation/latest.json` | 210 | [02a-route-state-artifacts.md](02a-route-state-artifacts.md) |
| 5.4 `meta/routes/ui-wiring/latest.json` | 247 | [02a-route-state-artifacts.md](02a-route-state-artifacts.md) |
| 6. Backend Changes | 322 | [02b-backend-api-contracts.md](02b-backend-api-contracts.md) |
| 6.1 New Service: `GameDesignRequirementMapService` | 324 | [02b-backend-api-contracts.md](02b-backend-api-contracts.md) |
| 6.2 New/Extended Service: `PrototypeContractFreezeService` | 344 | [02b-backend-api-contracts.md](02b-backend-api-contracts.md) |
| 6.3 Extend `PrototypeIterationPlanService` | 362 | [02b-backend-api-contracts.md](02b-backend-api-contracts.md) |
| 6.4 Extend `PrototypeIterationGoalService` | 386 | [02b-backend-api-contracts.md](02b-backend-api-contracts.md) |
| 6.5 Extend `ProjectWorkflowRouteService` | 407 | [02b-backend-api-contracts.md](02b-backend-api-contracts.md) |
| 7. API Changes | 420 | [02b-backend-api-contracts.md](02b-backend-api-contracts.md) |
| 8. Frontend Changes | 467 | [02c-frontend-migration-compatibility.md](02c-frontend-migration-compatibility.md) |
| 8.1 Stage Timeline | 469 | [02c-frontend-migration-compatibility.md](02c-frontend-migration-compatibility.md) |
| 8.2 Requirement Map Review UI | 489 | [02c-frontend-migration-compatibility.md](02c-frontend-migration-compatibility.md) |
| 8.3 Contract Freshness Banner | 513 | [02c-frontend-migration-compatibility.md](02c-frontend-migration-compatibility.md) |
| 8.4 Module Plan Confirmation UI | 524 | [02c-frontend-migration-compatibility.md](02c-frontend-migration-compatibility.md) |
| 8.5 UI Wiring Closure UI | 535 | [02c-frontend-migration-compatibility.md](02c-frontend-migration-compatibility.md) |
| 9. Migration And Compatibility | 548 | [02c-frontend-migration-compatibility.md](02c-frontend-migration-compatibility.md) |
| 10. Testing Strategy | 575 | [03-testing-observability-admin.md](03-testing-observability-admin.md) |
| 10.1 Unit Tests | 577 | [03-testing-observability-admin.md](03-testing-observability-admin.md) |
| 10.2 Integration / Smoke Tests | 603 | [03-testing-observability-admin.md](03-testing-observability-admin.md) |
| 10.3 Browser Tests | 627 | [03-testing-observability-admin.md](03-testing-observability-admin.md) |
| 10.4 Godot UI Capability Tests | 637 | [03-testing-observability-admin.md](03-testing-observability-admin.md) |
| 10.5 Godot Diagnostics And Quality Gate Tests | 659 | [03-testing-observability-admin.md](03-testing-observability-admin.md) |
| 10.6 Godot UI Style Theme Contract Tests | 683 | [03-testing-observability-admin.md](03-testing-observability-admin.md) |
| 11. Observability And Admin | 721 | [03-testing-observability-admin.md](03-testing-observability-admin.md) |
| 11.1 TapTap-Derived Hardening Patterns | 751 | [04a-route-contracts-and-guards.md](04a-route-contracts-and-guards.md), [04b-route-readback-recovery-and-freshness.md](04b-route-readback-recovery-and-freshness.md), [04c-route-operation-governance.md](04c-route-operation-governance.md) |
| 11.1.1 Conflict Assessment Against This Plan | 755 | [04a-route-contracts-and-guards.md](04a-route-contracts-and-guards.md) |
| 11.1.2 Route Module Contract Template | 779 | [04a-route-contracts-and-guards.md](04a-route-contracts-and-guards.md) |
| 11.1.3 Unified Route Action Descriptor | 813 | [04a-route-contracts-and-guards.md](04a-route-contracts-and-guards.md) |
| 11.1.4 Deterministic Guard Tests For Workflow Invariants | 837 | [04a-route-contracts-and-guards.md](04a-route-contracts-and-guards.md) |
| 11.1.5 CLI/Script-First Admin And Backfill Operations | 861 | [04a-route-contracts-and-guards.md](04a-route-contracts-and-guards.md) |
| 11.1.6 Phase Path And Readback Policy | 884 | [04b-route-readback-recovery-and-freshness.md](04b-route-readback-recovery-and-freshness.md) |
| 11.1.7 Runtime Logs, Expected Exit, And Orphan Process Hygiene | 904 | [04b-route-readback-recovery-and-freshness.md](04b-route-readback-recovery-and-freshness.md) |
| 11.1.8 Cache And Freshness Policy | 923 | [04b-route-readback-recovery-and-freshness.md](04b-route-readback-recovery-and-freshness.md) |
| 11.1.9 Directory-Scoped Agent Instructions | 942 | [04b-route-readback-recovery-and-freshness.md](04b-route-readback-recovery-and-freshness.md) |
| 11.1.10 User-Guided Ambiguity Resolution | 961 | [04b-route-readback-recovery-and-freshness.md](04b-route-readback-recovery-and-freshness.md) |
| 11.1.11 Capability Allowlist And Action Exposure | 979 | [04c-route-operation-governance.md](04c-route-operation-governance.md) |
| 11.1.12 Context Boundary And DTO Hygiene | 997 | [04c-route-operation-governance.md](04c-route-operation-governance.md) |
| 11.1.13 Progress And Long-Running Operation Feedback | 1015 | [04c-route-operation-governance.md](04c-route-operation-governance.md) |
| 11.1.14 Idempotent Recovery And Duplicate-Run Control | 1032 | [04c-route-operation-governance.md](04c-route-operation-governance.md) |
| 11.1.15 Credential, Token, And Secret Boundary | 1050 | [04c-route-operation-governance.md](04c-route-operation-governance.md) |
| 11.1.16 Configuration And Environment Preflight | 1069 | [04c-route-operation-governance.md](04c-route-operation-governance.md) |
| 11.1.17 Documentation Indexing And Route Discoverability | 1089 | [04c-route-operation-governance.md](04c-route-operation-governance.md) |
| 11.2 Godot UI Capability Contract Migration | 1112 | [05-godot-ui-capability-contract.md](05-godot-ui-capability-contract.md) |
| 11.2.1 Conflict Assessment | 1116 | [05-godot-ui-capability-contract.md](05-godot-ui-capability-contract.md) |
| 11.2.2 Full Godot Capability Checklist | 1136 | [05-godot-ui-capability-contract.md](05-godot-ui-capability-contract.md) |
| 11.2.3 Workflow Injection Points | 1186 | [05-godot-ui-capability-contract.md](05-godot-ui-capability-contract.md) |
| 11.2.4 Godot Governance Rules | 1208 | [05-godot-ui-capability-contract.md](05-godot-ui-capability-contract.md) |
| 11.3 Godot UI Style Theme Contract Migration | 1231 | [06a-ui-style-migration-overview-and-catalog.md](06a-ui-style-migration-overview-and-catalog.md) |
| 11.3.1 Conflict Assessment | 1242 | [06a-ui-style-migration-overview-and-catalog.md](06a-ui-style-migration-overview-and-catalog.md) |
| 11.3.2 Full UI Style Theme Migration Checklist | 1261 | [06a-ui-style-migration-overview-and-catalog.md](06a-ui-style-migration-overview-and-catalog.md) |
| 11.3.3 Recommended Built-In Godot Style Catalog | 1343 | [06a-ui-style-migration-overview-and-catalog.md](06a-ui-style-migration-overview-and-catalog.md) |
| 11.3.4 Godot Style Snapshot Schema | 1378 | [06b-ui-style-snapshot-schema.md](06b-ui-style-snapshot-schema.md), [schemas/godot-ui-style-contract.v1.example.json](schemas/godot-ui-style-contract.v1.example.json), [06d-ui-style-schema-acceptance.md](06d-ui-style-schema-acceptance.md) |
| 11.3.5 Style-Aware UI Closure | 2179 | [06c-style-aware-ui-closure.md](06c-style-aware-ui-closure.md) |
| 11.4 Godot Diagnostics And Quality Gate Migration | 2237 | [07-godot-diagnostics-quality-gates.md](07-godot-diagnostics-quality-gates.md) |
| 11.4.1 Conflict Assessment | 2241 | [07-godot-diagnostics-quality-gates.md](07-godot-diagnostics-quality-gates.md) |
| 11.4.2 Full Quality Gate Migration Checklist | 2260 | [07-godot-diagnostics-quality-gates.md](07-godot-diagnostics-quality-gates.md) |
| 11.4.3 Project Diagnostic Spool | 2299 | [07-godot-diagnostics-quality-gates.md](07-godot-diagnostics-quality-gates.md) |
| 11.4.4 Symptom-To-Remediation Table | 2344 | [07-godot-diagnostics-quality-gates.md](07-godot-diagnostics-quality-gates.md) |
| 11.4.5 Interaction-Region Design Gate | 2371 | [07-godot-diagnostics-quality-gates.md](07-godot-diagnostics-quality-gates.md) |
| 11.4.6 Resource Lifecycle And Orphan Diagnostics Gate | 2392 | [07-godot-diagnostics-quality-gates.md](07-godot-diagnostics-quality-gates.md) |
| 12. Implementation Phases | 2413 | [08-implementation-phases.md](08-implementation-phases.md) |
| Phase 0: Cross-Cutting Governance Prerequisites | 2415 | [08-implementation-phases.md](08-implementation-phases.md) |
| Phase 1: Requirement Map And Contract Freshness | 2453 | [08-implementation-phases.md](08-implementation-phases.md) |
| Phase 2: Iteration Plan Traceability Gate | 2486 | [08-implementation-phases.md](08-implementation-phases.md) |
| Phase 3: Workflow Recommendation | 2510 | [08-implementation-phases.md](08-implementation-phases.md) |
| Phase 4: Execute Goal Freshness And Needs-Fix Tightening | 2527 | [08-implementation-phases.md](08-implementation-phases.md) |
| Phase 5: UI Wiring Closure | 2554 | [08-implementation-phases.md](08-implementation-phases.md) |
| Phase 6: Route Governance Guardrails | 2579 | [08-implementation-phases.md](08-implementation-phases.md) |
| 13. Risks And Mitigations | 2622 | [09-risks-dod-open-questions.md](09-risks-dod-open-questions.md) |
| 14. Definition Of Done | 2657 | [09-risks-dod-open-questions.md](09-risks-dod-open-questions.md) |
| 15. Open Questions For Later Phases | 2688 | [09-risks-dod-open-questions.md](09-risks-dod-open-questions.md) |
| 15.1 Phase 1 Default Decisions | 2701 | [09-risks-dod-open-questions.md](09-risks-dod-open-questions.md) |
| 16. Recommended First Implementation Slice | 2718 | [10-recommended-first-slice.md](10-recommended-first-slice.md) |

Result: every original heading is represented in the split plan.

## Split Output Inventory

| Split output | Purpose |
| --- | --- |
| [00-index.md](00-index.md) | Primary execution index and task order |
| [01-overview-workflow.md](01-overview-workflow.md) | Overview, goals, workflow, severity |
| [02a-route-state-artifacts.md](02a-route-state-artifacts.md) | Route-state artifact schemas |
| [02b-backend-api-contracts.md](02b-backend-api-contracts.md) | Backend and API contracts |
| [02c-frontend-migration-compatibility.md](02c-frontend-migration-compatibility.md) | Frontend and compatibility |
| [03-testing-observability-admin.md](03-testing-observability-admin.md) | Tests, observability, admin |
| [04a-route-contracts-and-guards.md](04a-route-contracts-and-guards.md) | Route contracts and guard tests |
| [04b-route-readback-recovery-and-freshness.md](04b-route-readback-recovery-and-freshness.md) | Readback, recovery, freshness |
| [04c-route-operation-governance.md](04c-route-operation-governance.md) | Operation governance |
| [05-godot-ui-capability-contract.md](05-godot-ui-capability-contract.md) | Godot UI capability contract |
| [06a-ui-style-migration-overview-and-catalog.md](06a-ui-style-migration-overview-and-catalog.md) | Full TapTapMarker non-technology UI capability target and Godot style catalog |
| [06b-ui-style-snapshot-schema.md](06b-ui-style-snapshot-schema.md) | Style schema map |
| [schemas/godot-ui-style-contract.v1.example.json](schemas/godot-ui-style-contract.v1.example.json) | Machine-readable style contract example/schema fixture |
| [06c-style-aware-ui-closure.md](06c-style-aware-ui-closure.md) | Style-aware UI closure |
| [06d-ui-style-schema-acceptance.md](06d-ui-style-schema-acceptance.md) | Schema acceptance criteria |
| [07-godot-diagnostics-quality-gates.md](07-godot-diagnostics-quality-gates.md) | Diagnostics and quality gates |
| [08-implementation-phases.md](08-implementation-phases.md) | Implementation phase order |
| [09-risks-dod-open-questions.md](09-risks-dod-open-questions.md) | Risks, DoD, open questions, defaults |
| [10-recommended-first-slice.md](10-recommended-first-slice.md) | First implementation slice |
| [96-global-review-standard.md](96-global-review-standard.md) | Frozen review authority, severity standard, standard-change protocol, and regression-control rule for repeated global reviews |
| [97-split-added-requirements-ledger.md](97-split-added-requirements-ledger.md) | Split-added hardening requirements ledger |
| [98-original-to-split-audit.md](98-original-to-split-audit.md) | This comparison audit |
| [99-source-coverage.md](99-source-coverage.md) | Compact source coverage map |

## Normalization Notes

- Split-added hardening requirements are tracked separately in [97-split-added-requirements-ledger.md](97-split-added-requirements-ledger.md); original source-line coverage alone is not sufficient implementation readiness evidence.
- The original document remains useful as source history only. Implementation decisions should be made from the split documents.
- The monolithic source document is not a live mirror after the split. Any later monolithic edit must be documented here as source-history maintenance or reverted before the split plan is accepted for implementation.
- New normative requirements after the split must not be added to the monolithic source document. They belong in the split directory or in durable standards/ADR/workflow docs linked from the split index.
- Source-history maintenance note for the current split work: the monolithic source document may remain modified only to mark itself as source history and to preserve pre-split TapTap/TapTapMarker capability additions that are fully represented in this split directory. It must be committed together with the split directory or reverted before implementation starts; leaving the monolith modified while the split directory is untracked is not an accepted ready state.
- Commit/PR readiness requires this split directory, the `schemas/` fixture directory, this audit, and the source coverage map to be included together with no untracked split-plan files.
- The large original style schema block is intentionally not kept as a giant Markdown block. It is represented by a schema map, a machine-readable JSON contract example/schema fixture, and separate schema acceptance criteria.
- The split plan strengthens acceptance language where previous wording could permit drift, including runtime identity, Godot theme slot mapping, normalized style drift taxonomy, UI family tiers, deterministic substitute boundaries, file upload security gating, and full TapTapMarker non-technology UI capability preservation.
- These strengthened rules are additive hardening and do not remove source requirements.
- The GDD document-generation sidecar/status/action, admin review queue, and prototype-skeleton compatibility guard are split-plan hardening additions inside `02a-route-state-artifacts.md` and related API/frontend/test/phase documents; they are intentionally listed in the split output inventory and normalization notes rather than as original source headings.

## Audit Result

The split plan covers the original monolithic plan without intentional omissions. The split directory is the primary plan for future implementation work.
