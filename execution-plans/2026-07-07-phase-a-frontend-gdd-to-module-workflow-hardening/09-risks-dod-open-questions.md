# Risks, Definition Of Done, Open Questions, Phase 1 Defaults

Source: `../2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening.md` lines 2622-2717.

## 13. Risks And Mitigations

| Risk | Mitigation | Acceptance |
| --- | --- | --- |
| Too many new stages overwhelm users | Use recommendation-driven primary action; hide advanced controls | User always sees one recommended next action |
| LLM requirement map misses details | Add coverage validation and needs-review fallback | Empty map is invalid unless GDD has no requirements |
| Contract stale blocks old users unexpectedly | Treat legacy as unknown; allow explicit refresh; allow continue only for old hash-bound sessions/goals | Existing preview/package still works; new execution from unknown-source legacy plans remains blocked |
| Too much strictness slows prototype creation | Enforce P0/P1 as runtime blockers by default; allow P2 to be advisory for ordinary user execution only when it is tracked under the acceptance severity standard | Fast path remains usable, and implementation acceptance still has zero unresolved P0/P1/P2 findings |
| UI closure delays early playability | UI closure is a late-stage gate, not a skeleton gate | Prototype creation does not require UI closure |
| Formatting-only GDD changes cause hash churn | Normalize text before hashing or classify as advisory stale | Formatting-only changes can avoid hard stale if normalized hash is unchanged |
| Borrowed TapTap patterns are copied too literally | Adapt boundary and guard patterns only; keep Phase A C# service architecture | No TypeScript/MCP feature layout is required for Phase A |
| Guard tests become brittle string snapshots | Guard only stable names, enums, source-boundary markers, and contract fields | Tests fail on real contract drift, not harmless copy changes |
| Admin scripts become hidden mutation paths | Require explicit admin intent, idempotency notes, and append-only evidence | Browser user flows remain decision-focused and bulk maintenance stays auditable |
| Capability allowlist hides needed user recovery actions | Route descriptors separate safe secondary actions from admin/script-only actions | User can still recover through visible safe actions while dangerous maintenance stays gated |
| Context boundary rules duplicate existing service authorization | Treat context rules as tests over existing authorization/readback boundaries, not a second auth system | Tests prove server-derived context wins without adding competing auth logic |
| Progress states become optimistic and mask failed runs | Success requires validated sidecar/readback artifact, not only process exit | Browser never shows success for a missing or invalid route artifact |
| Preflight checks become a new dependency on external services | Keep preflight local and deterministic unless admin explicitly requests external probes | Preflight failures are actionable without Steam/LLM/network availability |
| Secret validators produce false confidence | Combine variable-name denylist, token-like pattern scan, and route-specific redaction tests | Prompt/evidence/admin export samples pass redaction tests before acceptance |
| Godot UI capability contract becomes too broad to implement | Phase-gate the contract: Phase 0 defines it, Phase 1 freezes/classifies it, Phase 2 plans from it, Phase 4 injects it, Phase 5 validates it | No phase claims completion for a touched UI domain without tests/evidence and zero unresolved P0/P1/P2 findings |
| UI capability migration accidentally imports TapTap technology | Keep TapTap-only terms in conflict assessment only and add prompt/evidence denylist tests | Route prompts, sidecars, UI closure output, and durable standards contain Godot-only implementation terms |
| UI style migration accidentally imports TapTapMarker runtime technology | Keep TapTapMarker-only terms in conflict assessment only and add denylist tests for UI prompts, generated code, route state, and style guides | Route prompts, sidecars, generated Godot files, UI closure output, and durable standards contain Godot-only style implementation terms |
| UI style contracts become prose-only design advice | Require machine-readable style contracts, generated Godot theme resource refs, design DNA rules, component baselines, composition rules, motion/transition rules, UI tree readback requirements, token tests, and visual evidence fixtures | Style selection, execution, repair, and UI closure can validate tokens, UI tree readback, and drift without reading chat history |
| Font assets create licensing or packaging risk | Use repo-approved fonts, generated/open licensed fonts, fallback stacks, and packaging checks; never copy TapTapMarker skill font files | Normal-user packages include only approved font assets and readback exposes no host-local font paths |
| Style selection becomes arbitrary or inconsistent | Freeze `ui_style_id`, version, source hash, and selection reason in the prototype contract before UI execution | A reviewer can explain why the style was selected and prove downstream routes used the same snapshot |
| Centralized style tokens block necessary local exceptions | Allow structured component exceptions with token, rationale, scope, and evidence | Exceptions stay auditable and final review still records zero unresolved P0/P1/P2 findings |
| UI closure produces generic "missing UI" items that are not actionable | Use gap families and required Godot fields in `ui_surface_matrix` | Each UI closure blocker names requirement IDs, scene/node or missing owner, gap family, and follow-up validation method |
| Visual validation becomes impossible in headless runs | Use layered evidence: route-state validators first, Godot headless/screenshot/canvas-pixel/exported visual evidence for high-risk visual changes, and a recorded deterministic substitute only when the harness limitation is concrete, approved, expiring or rechecked, and not substituting for interaction behavior | High-risk visual UI changes include machine-checkable evidence or an approved deterministic substitute with limitation metadata; interaction behavior still requires behavior evidence |
| Godot UI contract conflicts with the non-goal of not refactoring the generator | Keep this plan at workflow contract, prompt, validation, and readback level; generator internals change only when later implementation explicitly scopes them | Acceptance can be met by route contracts and generated goals without requiring a generator architecture rewrite in this plan |
| Diagnostics gate slows iteration | Run diagnostics at route boundaries and reuse current source hashes instead of rerunning unchanged checks | Routes block only on changed or stale diagnostic scope, and accepted phases still record zero unresolved P0/P1/P2 findings |
| Project diagnostic spool leaks private evidence | Store spool outside workspaces with redaction status, account ownership, admin-only raw access, and user-safe summaries | Normal-user readback cannot expose cross-account diagnostics, raw host paths, raw prompts, token material, provider secrets, or admin-only evidence |
| Project deletion accidentally removes diagnostics | Keep diagnostic spool outside hosted workspaces and make deletion cleanup ignore preserved diagnostics | Deleted-project admin lookup still finds unresolved diagnostics, and unresolved P0/P1/P2 records survive ordinary project deletion |
| Symptom table becomes stale documentation | Treat failure-family taxonomy and remediation table as tested route contract inputs | New known failure families cannot ship without a table row, domain code, user-safe summary policy, and test coverage |
| Temporary debug logs become permanent acceptance evidence | Require debug-log lifecycle checks and sanitized evidence replacement before acceptance | No changed route can pass with temporary stdout/print output as the only evidence |
| Interaction-region artifacts become busywork | Require them only for UI/input/physics/camera-heavy P0/P1 goals and allow structured alternatives to ASCII | Deckbuilder route-map and hand-dragging goals have useful hit-zone/collision artifacts, not decorative documentation |
| Prototype contract path drifts between recovery and readback | Make `routes/prototype-contract/latest.json` canonical and treat `meta/routes/prototype-contract/latest.json` only as a mirror/cache | Recovery, stale checks, and tests use the canonical path; stale mirrors fail validation instead of becoming authority |
| Recommendation strings drift from browser actions | Require route action descriptors or non-action display mappings for every recommendation in the complete canonical workflow action set | Workflow recommendation tests fail before browser shows an unmapped primary action |
| Admin review blockers remain hidden in route rows | Use an admin review queue sidecar/API with normal-user redacted summaries | Admin can triage every system-detected P0/P1 blocker, and normal users cannot see cross-account or raw admin evidence |
| Package download is mistaken for final readiness | Separate ordinary package download compatibility from final package readiness labels | Existing successful prototypes remain downloadable, but final readiness stays blocked by unresolved UI closure, diagnostics, source-boundary, style, or admin review blockers |
| Exemption fields bypass the wrong requirement | Keep `no_ui_needed` scoped to UI surface and `style_not_applicable` scoped to style contract | Tests fail when either exemption is used as a substitute for the other, and system-created P0/P1 exemptions require review/confirmation |
| Diagnostic cleanup erases repair evidence | Classify spool retention and allow only non-destructive compaction/redaction for eligible resolved records | Unresolved P0/P1/P2 diagnostics survive project deletion and cleanup; compacted records retain replacement evidence for audit and repair explanation |

## 14. Definition Of Done

## 14.0 DoD Layers

- Program DoD: the full GDD-to-package workflow and full TapTapMarker non-technology UI target closure. Program DoD is not claimed by the first implementation slice.
- Phase exit DoD: the zero-unresolved-P0/P1/P2 evidence for the phase or route set being implemented, including consumed Phase 0A/0B items, standards-sync, ADR/decision classification, tests, smoke, and readback evidence.
- First-slice DoD: Phase 0A plus the smallest Phase 1 slice listed in `10-recommended-first-slice.md`, with explicit proof that unconsumed full-target capabilities are tracked as `not_consumed_by_first_slice` and not misreported as covered.

Acceptance criteria:

- Implementation summaries state which DoD layer is being claimed.
- First-slice completion cannot claim Program DoD or final full-target UI closure.
- Program DoD cannot be claimed while any consumed capability, final-readiness blocker, or split-added requirement remains unresolved.


This refactor is done when:

1. A new project can complete the full stage flow from GDD form to package with visible stage statuses.
2. GDD requirements are represented in `meta/routes/gdd-requirements/latest.json` with coverage status.
3. Scene route confirmation is represented in `meta/routes/scene-route/latest.json` with a stable `confirmed_scene_route_hash`, confirmation metadata, relationships, and browser-safe blockers.
4. GDD document generation records `source_generated_gdd_hash` back to `meta/routes/scene-route/latest.json`, and requirement map generation blocks when the generated GDD hash and scene route confirmation state disagree without reconfirmation or a mismatch blocker.
5. `source_game_type_structured_hash` is computed from canonical English structured game-type metadata owned by the Phase project metadata service/metadata DB read model, not directly from raw `GameTypeSource`.
6. `routes/prototype-contract/latest.json` records source hashes and stale status can be read back.
7. Iteration goals and required modules trace back to GDD requirements or explicit default contract reasons.
8. Execute-next-goal refuses stale/missing source state before executable work is handed to `CodexHostedProcessCommandFactory`.
9. Frontend primary action is recommendation-driven.
10. UI closure identifies missing player-facing surfaces for completed P0/P1 capabilities.
11. Tests and smoke evidence cover the deckbuilder reference path.
12. No existing public/browser API field is removed or renamed.
13. Route module contracts and deterministic guard tests cover action names, status enums, source hashes, error envelope shape, and source-boundary prompt rules.
14. Phase path/readback policy prevents normal-user host path leakage and cross-account evidence leakage.
15. Admin/backfill operations are scriptable, auditable, and evidence-backed without bypassing user-facing decision flows.
16. Runtime lifecycle guidance distinguishes expected exits, failures, preserved evidence, and orphan-process diagnostics.
17. Capability exposure classes, context-boundary tests, progress/readback states, duplicate-run controls, secret redaction, and local preflight checks are implemented for the routes touched by each phase.
18. Durable TapTap-derived governance rules are moved or linked into the relevant standards/workflow docs before implementation is called complete.
19. The final review records zero unresolved P0, P1, or P2 findings under the acceptance severity standard.
20. Runtime recovery, restart, or protected runtime-state behavior, when changed by implementation, follows the `AGENTS.md` Phase Runtime Recovery Order and records evidence under `logs/`.
21. The Godot UI capability contract is frozen into prototype contracts, consumed by requirement map, iteration plan, execute-next-goal, needs-fix/repair, and UI closure, and exposed through account-safe readback.
22. P0/P1 player-facing requirements cannot complete final readiness without UI surface, layout/input/focus/feedback/camera-layer/state evidence or an explicit `no_ui_needed` rationale.
23. Godot UI capability tests prove no TapTap runtime technology is required or leaked into executable route prompts and artifacts.
24. The Godot diagnostics and quality-gate contract is linked from durable docs, consumed by build/validation, execute-next-goal, needs-fix, repair, UI closure, preview/package, and project-delete diagnostics, and covered by guard tests.
25. Project diagnostic spool preserves unresolved P0/P1/P2 diagnostics outside hosted workspaces, supports deleted-project admin lookup and triage, and protects normal users from raw or cross-account evidence.
26. Preview/package readiness, resource lifecycle cleanup, orphan diagnostics, interaction-region artifacts, and symptom-to-remediation table coverage are validated before final readiness.
27. The Godot UI style contract is frozen into prototype contracts, consumed by iteration plan, execute-next-goal, needs-fix/repair, UI closure, and preview/package readiness, and exposed through account-safe readback.
28. P0/P1 visible UI requirements cannot complete final readiness with stale style snapshot, source-name identity leakage, missing custom style owner/version/source-hash/readback metadata when applicable, missing structured alias approval metadata, missing design DNA rules, missing structured style tokens including border/opacity/rarity-HUD/gradient-glow/bottom-accent families when applicable, missing component defaults, missing semantic usage/action-role rules, missing component family baseline, missing component coverage matrix, missing variant coverage, missing component exception rule refs, missing structured composition rules, missing pointer/gesture rules, missing state ownership rules, missing UI lifecycle/subscription rules, missing scroll/virtualization policy, missing motion/transition rules, missing game composition templates, missing game composition requirement level/source reason, missing UI tree readback requirements or rows, missing visual evidence matrix coverage, missing contrast/readability validation, missing font-size unit policy, missing localization/overflow policy, missing density/scale policy, unapproved font assets, unsafe theme/visual refs, untracked per-component style overrides, custom style failing built-in-equivalent checks, or unresolved style drift.
29. Godot UI style tests prove no TapTapMarker runtime technology, font assets, Lua templates, UrhoX widget APIs, Yoga layout calls, NanoVG calls, or EmmyLua annotations are required or leaked into executable route prompts and generated artifacts.
30. The canonical prototype contract path is `routes/prototype-contract/latest.json`; optional mirrors are validated as readback/cache only and cannot become recovery authority.
31. Prompt-producing route states record the common source-boundary schema, hosted-route recovery source order, and authority source hashes, and saved prompt evidence proves only declared authority sources and artifact versions were used after contract freeze.
32. Admin review queue sidecar/API/readback/mutation/deleted-project tombstone paths exist for system-detected P0/P1 blockers, generated exemptions, and admin decisions, with metadata DB query ownership, account isolation, redacted normal-user summaries, and auditable decision metadata.
33. Every primary `recommended_action` in `schemas/workflow-action-contracts.v1.json` maps to a route action descriptor, browser action ID, or explicit non-action display mapping. Current primary set: `create_gdd`, `complete_gdd`, `import_gdd_form`, `analyze_game_type`, `confirm_scene_route`, `generate_gdd_document`, `generate_requirement_map`, `freeze_contract`, `refresh_contract`, `create_prototype`, `create_iteration_plan`, `execute_next_goal`, `run_needs_fix`, `run_ui_closure`, `preview_package`, and `inspect_first`.
    - `repair` remains a file-changing route alias/sub-operation under `run_needs_fix`, not a second canonical recommendation ID.
    - `delete_project` remains an account-scoped destructive secondary or forbidden action and never becomes the stage-driven primary recommendation.
34. Status vocabulary is dimensioned and tested across stage timeline, route/readback state, requirement coverage, scene route confirmation, admin review queue, UI surface matrix, readiness labels, prototype-skeleton source state, diagnostic triage, style/capability coverage, full-target closure, and operation status values.
35. Ordinary package download compatibility is separate from final package readiness; final readiness cannot pass with unresolved UI closure, diagnostics, source-boundary, style, or admin review blockers.
36. `no_ui_needed` and `style_not_applicable` exemption semantics are tested as separate scopes, and system-created P0/P1 exemptions cannot pass final readiness without required review/confirmation metadata.
37. Diagnostic spool retention/cleanup preserves unresolved P0/P1/P2 records and retains auditable replacement evidence for compacted or redacted resolved records.
38. Project-delete has route governance coverage for ordinary user deletion, admin diagnostic/admin-review preservation, deleted-project tombstones, account-boundary behavior, idempotency, duplicate request handling, diagnostic spool preservation, and browser-safe errors.
39. New durable standards, route governance contracts, source-boundary rules, admin review queue behavior, readiness policy, and diagnostic retention policy are backed by a Phase ADR, ADR update, or decision log when they change architecture or service contracts; `docs/architecture/ADR_INDEX_PHASE.md` is updated when an ADR is created.
40. The split directory is committed as the primary plan and the monolithic source document is either unchanged source history or has a recorded source-history maintenance note in `98-original-to-split-audit.md`.
41. New-project full closure and legacy package compatibility have separate evidence. A legacy package/download success cannot satisfy the new-project full-stage DoD.
42. Every deferred governance item has owner, affected routes, severity, expiry or recheck trigger, current-scope non-impact proof, and a Phase 6 closure test.
43. Each phase exit review writes append-only structured phase review JSON under the agreed `logs/phase-a-innernet/reviews/gdd-to-module-hardening/phase-<n>-exit-review-<run_id>.json` path or links an explicitly justified alternative. Latest pointer files are readback copies only and cannot replace run-id evidence.
44. The full TapTapMarker non-technology UI target has a closure ledger in which every capability package is `covered`, `reviewed_not_applicable`, or `explicitly_deferred` with owner, affected routes, expiry or recheck trigger, and validation evidence. No full-target row may remain only `not_consumed_by_first_slice` after the phase that consumes it.
45. Workflow recommendation phase eligibility is tested: actions whose route contracts are not active for the current phase can appear only in `forbiddenActions[]` with browser-safe disabled reasons, never as the primary `recommendedAction`.
46. Preview/package readback has a minimum readiness contract even when no full route module contract is required: source hash set, preview ticket/package artifact refs, ordinary-download compatibility, final-readiness eligibility, unresolved blocker counts, account boundary, diagnostic/style/UI/admin review blockers, and evidence refs.
47. Diagnostic spool, admin review queue, project delete, and exports share identity fields for `diagnosticId`, `queueEntryId`, `deletionEventId`, and `projectTombstoneId` using snake_case in artifacts and camelCase in API DTOs.
48. Phase service standards are updated for every implemented API/status/error/readback/no-store behavior introduced by this refactor, including workflow action descriptors, action gating domain codes, route source-boundary fields, evidence-ref kind fixtures, preview/package readiness, admin review queue behavior, diagnostic spool retention, project-delete tombstones, and game-type matching maintenance records.
49. Split-added hardening requirements in `97-split-added-requirements-ledger.md` are classified in phase exit evidence as implemented, not applicable, or explicitly deferred with evidence.

### 14.1 ADR And Decision-Log Matrix

Use this matrix before implementing any plan item:

| Change type | Required durable decision |
| --- | --- |
| New or changed public/browser API semantics, auth behavior, account isolation, metadata DB ownership, shared LLM/Codex invocation behavior, diagnostic retention policy, or runtime/protected-path behavior | Phase ADR or ADR update; update `docs/architecture/ADR_INDEX_PHASE.md` when an ADR is created |
| New route module contract, action descriptor, source-boundary rule, readiness label policy, admin review queue behavior, or style/diagnostic standard that does not change architecture ownership | Decision log or standards update linked from the implementation evidence |
| Pure execution-plan sequencing, first-slice ordering, or non-binding implementation notes | Execution-plan update is enough, unless it changes an accepted ADR/standard |

Current Phase 0A/0B mapping:

| Plan item | Minimum durable decision before implementation |
| --- | --- |
| Admin review queue metadata DB ownership, deleted-project tombstones, admin-only mutation, or cross-account readback | Phase ADR or ADR update |
| Diagnostic spool metadata DB index ownership, retention/cleanup, protected runtime evidence path, or deleted-project lookup | Phase ADR or ADR update |
| Public/browser API additions for structured game-type analysis/backfill, scene route confirmation, GDD document generation/status, requirement map, prototype contract, prototype-skeleton status, workflow recommendation, UI closure, project-delete, or admin review queue | Phase ADR or ADR update by default, because these are browser-consumed Phase service semantics; a standards-only update is allowed only when an accepted Phase ADR already covers the exact additive route family and the implementation evidence links that ADR |
| Shared `ILlmRouteEngine`, `CodexHostedProcessCommandFactory`, or `scripts/sc/_llm_backend.py` invocation protocol changes | Phase ADR or ADR update |
| Route action descriptor registry, status vocabulary fixture, source-boundary schema, evidence-ref kind fixture, and readiness label policy | Decision log plus standards update; upgrade to Phase ADR if it changes public API semantics or persistence ownership |
| Godot UI capability contract, Godot UI style contract, and Godot diagnostics standards files | Standards update plus decision log; upgrade to Phase ADR if they add runtime protected-path behavior, metadata DB ownership, or browser/API semantics |
| First-slice ordering only | Execution-plan update is enough |
| `not_consumed_by_first_slice` classification that affects validators, final readiness, route consumption, or capability matrix semantics | Decision log plus standards/update evidence; upgrade to Phase ADR if it changes public/browser readiness semantics or persisted API/readback fields |
| Workflow recommendation phase eligibility or preview/package readiness semantics | Phase ADR or ADR update when public/browser behavior changes; otherwise decision log plus standards update |
| Phase service standards update for API/status/error/readback/no-store semantics introduced by this plan | `docs/standards/phase-service.md` update plus fixture/test parity; upgrade to Phase ADR if the standard changes public API compatibility, metadata DB ownership, auth/account isolation, or retention behavior |

Acceptance criteria:

- Implementation evidence states which row applies and links the ADR, ADR update, decision log, standards update, or execution-plan section.
- Review fails if an architectural contract is implemented only from this execution plan without the required durable decision record.
- Phase exit evidence includes this current-plan mapping and marks every implemented Phase 0A/0B item as `adr_or_update`, `decision_log_or_standards`, or `execution_plan_only`; unclassified items block phase completion.
- Phase exit evidence includes a standards-sync checklist for `docs/standards/phase-service.md`; implementation cannot be accepted when API/status/error/readback/no-store semantics changed but the standards checklist is empty or marked not applicable without evidence.

## 15. Open Questions For Later Phases

These are product/design decisions intentionally scoped out of the first implementation slice. They are not accepted P2 defects. If any item becomes a discovered implementation issue, it must be reclassified under the P0/P1/P2 acceptance severity standard with owner, scope, and proof.

| Question | Owner | Scope | Current proof that Phase 1 is not blocked |
| --- | --- | --- | --- |
| After Phase 1, should users be allowed to manually edit requirement map rows, or should edits continue to happen only by changing GDD/scene route and regenerating? | Product + Phase A platform | Requirement map editing UX and audit policy | Phase 1 default forbids normal-user direct edits and requires regeneration from GDD/scene route, so no unowned edit path exists. |
| After Phase 1, should `contract_stale` block execute-next-goal for all statuses, or allow broader continuation of already-running sessions with an explicit warning? | Phase A platform | Execute-next-goal stale handling beyond hash-bound continuations | Phase 1 default blocks new execution from stale/unknown sources and allows continuation only when goal/session hashes match the original source set. |
| After Phase 1, should UI closure become mandatory before package download or remain limited to "final package" readiness labeling? | Product + Phase A platform | Package readiness policy | Phase 1 default keeps early package download non-blocking while preserving final readiness blockers, so playable prototype creation remains recoverable. |
| After Phase 1, should requirement map generation remain hybrid deterministic + structured LLM, or move toward a fully deterministic/fully LLM-based approach? | Phase A platform | Requirement extraction architecture | Phase 1 default uses deterministic source collection/validation plus structured LLM and deterministic fallback, so invalid or empty LLM output fails closed. |
| After Phase 1, should source hash normalization ignore more than whitespace-only Markdown changes, such as heading punctuation or table formatting? | Phase A platform | Hash canonicalization policy | Phase 1 minimum canonicalization handles line endings and trailing whitespace while retaining raw diagnostic hashes, so stale decisions stay explainable. |
| Should users choose a UI style manually during GDD, or should workflow recommend one from project genre/reference direction first? | Product + Phase A platform | UI style selection UX | Phase 1 default allows workflow recommendation with explicit user/admin override and records selection reason before freezing the prototype contract. |

## 15.1 Phase 1 Default Decisions

These defaults apply to the first implementation slice so Phase 1 can proceed without resolving every open question:

1. Requirement map rows are not directly editable by normal users in Phase 1. Users change GDD or scene route and regenerate the map. Admin-only defer/conflict decisions are allowed when they include the structured audit fields defined above.
2. `contract_stale` blocks new iteration plan creation by default. Continuing an old session is allowed only when the session/goal source hashes match the contract and requirement map that were current when the session was created. Missing hashes are `source_unknown` and block new-project execution.
3. UI closure is not required for early prototype creation or ordinary package download in Phase 1. It affects final readiness labeling and can become a hard final-package gate in a later product decision. Ordinary package download compatibility must be labeled separately from final package readiness and cannot satisfy new-project full closure evidence.
4. Requirement map generation starts as hybrid deterministic + structured LLM: deterministic source collection and validation, structured LLM mapping, deterministic fallback to `needs_review` rows.
5. UI style selection starts as workflow-recommended from project game type/reference direction and style trigger taxonomy with explicit user/admin override. The selected repo-owned style ID, version, snapshot hash, and selection reason are frozen into the prototype contract before UI execution.
6. Source hashes use normalized Markdown/text content for Markdown and text artifacts to avoid whitespace-only churn. Minimum canonicalization is: normalize line endings to `\n`, trim trailing whitespace, preserve heading text, preserve table cell content, and optionally exclude known volatile frontmatter fields such as `updatedUtc`. JSON/schema contracts, including the Godot UI capability contract and Godot UI style contract, use deterministic canonical JSON ordering and exclude documented volatile fields before hashing. Route-state and evidence-reference source hashes use deterministic canonical JSON ordering, sorted evidence refs, and exclude volatile timestamps, process IDs, request IDs, and run IDs unless a field is explicitly declared part of source identity. The Godot UI capability contract template at `docs/standards/godot-ui-capability-contract.md` and the Godot UI style contract template at `docs/standards/godot-ui-style-contract.md` must declare canonical hash exclusion lists; an empty exclusion list is valid. Raw hash can be retained as diagnostic metadata if needed.

Acceptance criteria:

- Phase 1 implementation follows these defaults unless a newer decision log supersedes them.
- Frontend copy and API errors reflect these defaults.
- Tests cover the default decisions for map editability, stale blocking, UI closure non-blocking package behavior, UI style recommendation/override, style snapshot hashing, runtime environment hash identity/readback, frozen style readback, normalized style taxonomy references, core UI family tier enforcement, game-minimum family enforcement only when required by the GDD/default contract, security-gated family non-applicability without policy, theme resource slot mapping and token coverage, visual evidence self-description, deterministic substitute approval/expiry/recheck metadata and substitution boundaries, and the Phase 1 subset of pointer/gesture, lifecycle, virtualization, localization, and Toast behavior required by the touched prototype routes.
- Tests also cover canonical prototype-contract path authority, optional mirror validation, common source-boundary fields and source hash maps, admin review queue blockers, complete canonical workflow action mapping, status vocabulary separation, exemption scope separation, final-readiness blockers, and diagnostic spool retention/cleanup boundaries.
- Tests cover the ADR/decision-log matrix, deferred governance expiry/recheck metadata, and source-history/primary-split commit readiness.
