# Style-Aware UI Closure

Source: `../2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening.md` lines 2179-2236.

### 11.3.5 Style-Aware UI Closure

UI closure should validate both "can the player use it?" and "does it still belong to the selected style?".

Closure uses the normalized taxonomy from `06a-ui-style-migration-overview-and-catalog.md`. If this document and `06a` disagree, update this document to match `06a`; do not create a second taxonomy.

Required style gap families:

- `palette`
- `typography`
- `radius`
- `border`
- `shadow`
- `opacity`
- `spacing`
- `density_scale`
- `rarity_hud`
- `gradient_glow`
- `bottom_accent`
- `design_dna`
- `component_defaults`
- `component_coverage`
- `component_family_baseline`
- `variant_coverage`
- `component_exception_rules`
- `forbidden_patterns`
- `pointer_gesture`
- `gesture_phase`
- `pointer_event_shape`
- `drag_drop_payload`
- `state_ownership`
- `ui_lifecycle`
- `scroll_virtualization`
- `motion_transition`
- `game_composition_templates`
- `theme_resource_refs`
- `theme_resource_coverage`
- `runtime_environment`
- `file_upload_security`
- `font_policy`
- `semantic_usage`
- `action_role`
- `contrast_readability`
- `font_size_unit`
- `localization_overflow`
- `state_tokens`
- `composition`
- `ui_tree_readback`
- `source_name_ownership`
- `visual_evidence`
- `visual_evidence_method`

Stable capability package IDs contributed by this document:

| Capability ID | Owner scope |
| --- | --- |
| `ui_style_closure_gap_taxonomy` | Normalized style gap families, severity, affected requirement/scene/node refs, and follow-up recommendation shape. |
| `ui_style_repair_prompt_contract` | Repair prompt inputs for frozen style snapshot, component defaults, pointer/gesture, lifecycle, theme resource coverage, visual evidence, and UI tree readback. |
| `ui_final_readiness_style_gate` | Final-readiness blocker semantics for unresolved P0/P1 style drift and `not_consumed_by_first_slice` rows. |

Acceptance criteria:

- UI closure output includes style gap rows with requirement IDs, scene/node paths, expected style token or rule, observed drift, severity, affected viewport/component/state evidence, UI tree readback ref when applicable, visual evidence method, and follow-up goal recommendation.
- Repair prompts for style gaps include the frozen style snapshot, runtime environment, affected node paths, component defaults, exception rules, composition rules, motion/transition rules, pointer event shape, gesture phase, drag/drop payload policy where applicable, theme resource token coverage, visual evidence method, and UI tree readback refs, not broad mutable style-guide prose.
- UI closure cannot mark final readiness when a P0/P1 visible UI requirement has unresolved style drift in `design_dna`, `palette`, `typography`, `radius`, `border`, `shadow`, `opacity`, `spacing`, `density_scale`, `rarity_hud`, `gradient_glow`, `bottom_accent`, `component_defaults`, `component_coverage`, `component_family_baseline`, `variant_coverage`, `component_exception_rules`, `forbidden_patterns`, `pointer_gesture`, `gesture_phase`, `pointer_event_shape`, `drag_drop_payload`, `state_ownership`, `ui_lifecycle`, `scroll_virtualization`, `motion_transition`, `game_composition_templates`, `theme_resource_refs`, `theme_resource_coverage`, `runtime_environment`, `file_upload_security`, `semantic_usage`, `action_role`, `contrast_readability`, `font_size_unit`, `localization_overflow`, `font_policy`, `state_tokens`, `composition`, `ui_tree_readback`, `source_name_ownership`, `visual_evidence`, or `visual_evidence_method`.
- Full-target UI closure ledger status values are `covered`, `reviewed_not_applicable`, and `explicitly_deferred`; `not_consumed_by_first_slice` is an interim Phase 1 coverage value only and cannot satisfy final readiness or full TapTapMarker non-technology UI target closure.
- P2 style drift may be advisory for ordinary user execution only when it is tracked under the acceptance severity standard and final implementation review still records zero unresolved P0/P1/P2 findings.
- Review records zero unresolved P0/P1/P2 findings for missing style closure, stale style snapshot, or unvalidated style drift.
- The full-target closure ledger includes the stable capability IDs from this document and rejects mutable heading-derived IDs.
