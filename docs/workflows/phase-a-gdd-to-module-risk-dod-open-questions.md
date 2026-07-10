# Phase A GDD-To-Module Risks, DoD, And Open Questions

Status: Living workflow standard
Language: English
Register ID: `phase-a-gdd-to-module-risk-dod-open-questions`
Scope: Phase A GDD-to-module hardening risks, mitigation acceptance, DoD layering, ADR/decision evidence, open questions, and Phase 1 defaults.

## Authority

This document is the durable workflow source for `execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/09-risks-dod-open-questions.md`. The machine-readable registry is `PhaseA.Platform/Workflow/GddToModuleRiskDodOpenQuestions.cs`.

## Risk Register

| Risk ID | Risk | Mitigation | Acceptance |
| --- | --- | --- | --- |
| `too_many_stages` | Too many new stages overwhelm users | Use recommendation-driven primary action and hide advanced controls. | User always sees one recommended next action. |
| `llm_requirement_map_misses_details` | LLM requirement map misses details | Add coverage validation and needs-review fallback. | Empty map is invalid unless GDD has no requirements. |
| `contract_stale_blocks_legacy` | Contract stale blocks old users unexpectedly | Treat legacy as unknown; allow explicit refresh and hash-bound continuation only. | Existing preview/package works; new execution from unknown-source legacy plans remains blocked. |
| `strictness_slows_prototype_creation` | Too much strictness slows prototype creation | P0/P1 block runtime by default; tracked P2 can be advisory for ordinary execution only. | Fast path remains usable and implementation acceptance has zero unresolved P0/P1/P2 findings. |
| `ui_closure_delays_playability` | UI closure delays early playability | UI closure is late-stage final-readiness gate, not skeleton gate. | Prototype creation does not require UI closure. |
| `formatting_hash_churn` | Formatting-only GDD changes cause hash churn | Normalize text before hashing or classify formatting-only stale as advisory. | Formatting-only changes can avoid hard stale if normalized hash is unchanged. |
| `taptap_patterns_copied_literally` | Borrowed TapTap patterns are copied too literally | Adapt boundary and guard patterns only; keep Phase A C# architecture. | No TypeScript/MCP feature layout is required. |
| `brittle_guard_snapshots` | Guard tests become brittle string snapshots | Guard stable names, enums, source-boundary markers, and contract fields. | Tests fail on real contract drift, not harmless copy changes. |
| `hidden_admin_mutation_paths` | Admin scripts become hidden mutation paths | Require explicit admin intent, idempotency notes, and append-only evidence. | Bulk maintenance stays auditable. |
| `diagnostic_spool_leaks_private_evidence` | Project diagnostic spool leaks private evidence | Store spool outside workspaces with redaction status, account ownership, admin-only raw access, and user-safe summaries. | Normal-user readback cannot expose cross-account diagnostics, raw host paths, raw prompts, token material, provider secrets, or admin-only evidence. |
| `project_delete_removes_diagnostics` | Project deletion accidentally removes diagnostics | Keep diagnostic spool outside hosted workspaces and make deletion cleanup ignore preserved diagnostics. | Deleted-project admin lookup still finds unresolved diagnostics. |
| `package_download_mistaken_for_final_readiness` | Package download is mistaken for final readiness | Separate ordinary package download compatibility from final readiness labels. | Download can remain available while final readiness remains blocked. |
| `diagnostic_cleanup_erases_repair_evidence` | Diagnostic cleanup erases repair evidence | Preserve unresolved blockers and keep replacement evidence for eligible compaction/redaction. | Unresolved P0/P1/P2 diagnostics survive deletion and cleanup. |

## Definition Of Done Layers

- Program DoD: the full GDD-to-package workflow and full non-technology UI target closure. Program DoD is not claimed by the first implementation slice.
- Phase exit DoD: zero unresolved P0/P1/P2 evidence for the phase or route set being implemented, including consumed Phase 0A/0B items, standards sync, ADR/decision classification, tests, smoke, and readback evidence.
- First-slice DoD: Phase 0A plus the smallest Phase 1 slice, with proof that unconsumed full-target capabilities are tracked and not misreported as covered.

Implementation summaries must state which DoD layer is being claimed. Program DoD cannot be claimed while any consumed capability, final-readiness blocker, or split-added requirement remains unresolved.

## DoD Item Register

The machine-readable register tracks representative DoD items by layer, including requirement map coverage, canonical prototype contract path, stale-source execution refusal, API backward compatibility, zero unresolved P0/P1/P2 findings, diagnostics quality gate consumption, diagnostic spool retention, UI style contract consumption, package-download versus final-readiness separation, split primary source readiness, phase exit review evidence, full-target closure ledger, and split-added requirement classification.

## ADR And Decision-Log Matrix

| Change type | Required durable decision |
| --- | --- |
| New or changed public/browser API semantics, auth behavior, account isolation, metadata DB ownership, shared LLM/Codex invocation behavior, diagnostic retention policy, or runtime/protected-path behavior | `adr_or_update` |
| New route module contract, action descriptor, source-boundary rule, readiness label policy, admin review queue behavior, or style/diagnostic standard without architecture ownership change | `decision_log_or_standards` |
| Pure execution-plan sequencing, first-slice ordering, or non-binding implementation notes | `execution_plan_only` |
| Phase service standards update for API/status/error/readback/no-store semantics introduced by this plan | `standards_update` |

Review fails if an architectural contract is implemented only from an execution plan without the required durable decision record. Phase exit evidence must classify every implemented Phase 0A/0B item as `adr_or_update`, `decision_log_or_standards`, `standards_update`, or `execution_plan_only`.

## Open Questions

| Question ID | Question | Owner | Current Phase 1 non-blocking proof |
| --- | --- | --- | --- |
| `requirement_map_manual_edits` | Should users manually edit requirement map rows? | Product + Phase A platform | Phase 1 forbids normal-user direct edits and regenerates from GDD/scene route. |
| `contract_stale_continuation` | Should contract_stale block execute-next-goal for all statuses? | Phase A platform | Phase 1 blocks new execution and allows only hash-bound old session continuation. |
| `ui_closure_package_gate` | Should UI closure become mandatory before package download? | Product + Phase A platform | Phase 1 keeps ordinary package download non-blocking and final readiness blocked. |
| `requirement_map_generation_architecture` | Should requirement mapping stay hybrid deterministic plus structured LLM? | Phase A platform | Phase 1 uses deterministic collection/validation plus structured LLM and fallback rows. |
| `hash_normalization_scope` | Should source hash normalization ignore more Markdown changes? | Phase A platform | Phase 1 normalizes line endings/trailing whitespace and keeps raw diagnostic hashes. |
| `ui_style_selection_ux` | Should users choose UI style manually during GDD? | Product + Phase A platform | Phase 1 starts with workflow recommendation plus explicit override. |

These questions are scoped out of first-slice completion. If one becomes a discovered implementation issue, it must be reclassified under the P0/P1/P2 acceptance severity standard.

## Phase 1 Default Decisions

- Requirement map rows are not directly editable by normal users in Phase 1.
- `contract_stale` blocks new iteration plan creation by default.
- UI closure is not required for early prototype creation or ordinary package download in Phase 1.
- Requirement map generation starts as hybrid deterministic plus structured LLM with deterministic fallback rows.
- UI style selection starts as workflow-recommended from project game type/reference direction with explicit user/admin override.
- Source hashes use normalized Markdown/text content for Markdown/text artifacts and deterministic canonical JSON ordering for JSON/schema contracts.

## Closure Review Schema

Closure review evidence uses `docs/schemas/gdd-to-module-dod-closure-review.v1.example.json`. It records claimed DoD layer, completed DoD item IDs, unresolved consumed capabilities, decision classifications, open-question reclassifications, evidence refs, and standards sync refs. Chat text alone cannot satisfy this review.
