# Godot UI Style Snapshot Schema Map

Source plan coverage: original `../2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening.md` lines 1378-2178. The embedded JSON object extracted for field-level comparison occupies source lines 1383-2146; surrounding schema prose and acceptance text remain covered by this map and `06d`.

Enum-declaration example fixture: [`schemas/godot-ui-style-contract.v1.example.json`](schemas/godot-ui-style-contract.v1.example.json)

Machine-readable schema contract profile: [`schemas/godot-ui-style-contract.v1.profile.json`](schemas/godot-ui-style-contract.v1.profile.json)

Exhaustive bidirectional source-field contract: [`schemas/godot-ui-style-contract.v1.field-map.json`](schemas/godot-ui-style-contract.v1.field-map.json)

Canonical capability inventory: [`schemas/gdd-to-module-capability-inventory.v1.json`](schemas/gdd-to-module-capability-inventory.v1.json)

Stable owner and acceptance registry: [`schemas/split-added-acceptance-registry.v1.json`](schemas/split-added-acceptance-registry.v1.json)

Acceptance rules: [`06d-ui-style-schema-acceptance.md`](06d-ui-style-schema-acceptance.md)

## Purpose

This document is the map for the Godot UI style snapshot contract. The JSON artifacts are intentionally kept separate so Markdown remains reviewable. The example fixture declares the complete field shape and pipe-delimited enum examples; the schema contract profile is the machine-readable validation entrypoint; the field map is the exhaustive bidirectional field contract from original source pointers and lines to normalized fixture paths; the capability inventory is the canonical cross-document capability set; and the acceptance registry resolves stable owner and acceptance IDs.

Phase 0 schema authority:

- Phase 0 acceptance uses `schemas/godot-ui-style-contract.v1.profile.json` as the machine-readable validation entrypoint, `schemas/godot-ui-style-contract.v1.field-map.json` as the exhaustive source-to-fixture and fixture-to-source field authority, and `schemas/godot-ui-style-contract.v1.example.json` as the enum-declaration example fixture.
- The profile resolves the fixture, field map, capability inventory, acceptance registry, and workflow action contract relative to `path_base=split_directory`. Absolute paths, drive-qualified paths, and `..` escapes are invalid. The monolithic source uses its separate `source_path_base=repository_root`. The field map distinguishes `source_plan_coverage_line_range=1378-2178` from `source_json_line_range=1383-2146` and encodes every object, array, field, enum, source pointer/line, normalization status, resolvable `profile_rule_path`, and acceptance reference.
- Deterministic validators must validate fixture/profile/field-map parity, reverse-orphan absence, capability inventory parity, and acceptance-ID resolution. Pipe-delimited enum strings in the example fixture are documentation shorthand only; validators consume the machine-readable enum sets from the field map through the profile.
- Any later conversion to formal JSON Schema requires a decision log or ADR update, a compatibility plan for existing style snapshots, and tests proving fixture/schema/profile parity.
- Viewport, runtime environment, input, camera, TileMap/map, and visual evidence fields consume the Godot semantic baseline in `04d-godot-engine-semantics-and-reference-examples.md`; style snapshots must not invent a separate resolution, coordinate, or reference-example vocabulary.

## Top-Level Schema Areas

Stable capability package IDs contributed by this document:

| Capability ID | Owner scope |
| --- | --- |
| `ui_style_snapshot_schema` | Machine-readable style snapshot fields, enum-like values, required nested objects, cardinality, and hash identity rules. |
| `ui_runtime_environment_identity` | Godot/runtime environment participation in style snapshot hash identity and readback validity. |
| `ui_theme_resource_contract` | Godot theme resources, token-to-slot mapping, font/icon/texture policy, package validation, and safe readback refs. |
| `ui_visual_evidence_contract` | UI tree readback, visual evidence matrix, deterministic substitute metadata, and browser-safe evidence refs. |

1. Identity and source ownership
   - `schema_version`, `ui_style_id`, `ui_style_version`, `source_ui_style_contract_hash`, `ui_style_snapshot_hash`, `selected_by`, `selection_reason`, and `capability_packages`.
   - Source-name ownership lives in `source_name_policy`; source skill names cannot become route identity.
2. Design DNA and source inspiration
   - `design_dna_rules`, `source_inspiration`, `public_aliases`, `custom_style_metadata`, `custom_style_equivalence_requirements`.
   - Custom styles must pass built-in-equivalent validation.
3. Runtime environment identity
   - `runtime_environment` freezes Godot version, renderer, export target, platform class, viewport set, display scale, DPI, theme scale, font oversampling, locale, text direction, and font-rendering notes.
   - Active style snapshots require runtime environment participation in hash identity unless a decision log says otherwise.
4. Token systems
   - Palette, typography, spacing, density, scale, radius, border, shadow, opacity, rarity/HUD, gradient/glow, and bottom-accent tokens.
   - Token values require canonical format and Godot conversion rules.
5. Input, gesture, and state
   - `pointer_gesture_rules`, `state_ownership_rules`, `ui_lifecycle_rules`, `scroll_virtualization_rules`, and `motion_transition_rules`.
   - These encode pointer event shape, gesture phase, drag/drop payload lifecycle, form state, Godot lifecycle hooks, signal ownership, and virtualization measurement.
6. Semantic/component systems
   - `semantic_usage_rules`, `action_role_rules`, `component_defaults`, `component_family_baseline`, `component_coverage_matrix`, `component_exception_rules`, `composition_rules`, and `game_composition_templates`.
   - Component family tiers are defined in `06a-ui-style-migration-overview-and-catalog.md`.
7. Font, icon, and resource policy
   - `font_policy`, `godot_theme_resources`, icon/texture policy, Godot theme slot mappings, resource load validation, export/package validation, deterministic diff refs, and safe readback policy.
8. Readback and evidence
   - `ui_tree_readback_requirements`, `ui_tree_readback_rows`, `visual_evidence_matrix`, and `visual_validation_refs`.
   - Evidence must be self-describing and account-safe.
9. Forbidden patterns
   - `forbidden_patterns` blocks TapTapMarker runtime technology leakage in prompts, route state, generated code, style contracts, and visual evidence.

## Review Rule

When schema fields, acceptance criteria, style closure, admin readback, tests, or implementation phases disagree, use this authority order:

1. `06a-ui-style-migration-overview-and-catalog.md` for capability packages, UI family tiers, and normalized style drift taxonomy.
2. `schemas/godot-ui-style-contract.v1.profile.json` for validation modes, path resolution, and bundle entrypoint behavior.
3. `schemas/godot-ui-style-contract.v1.field-map.json` for the exhaustive bidirectional field contract, source pointers/lines, normalization, object/array/cardinality rules, and enum contracts.
4. `schemas/gdd-to-module-capability-inventory.v1.json` for canonical capability IDs, triggers, owners, phases, and acceptance references.
5. `schemas/split-added-acceptance-registry.v1.json` for stable owner IDs and resolvable acceptance IDs.
6. `schemas/godot-ui-style-contract.v1.example.json` for the enum-declaration example fixture and complete field-shape example.
7. `schemas/workflow-action-contracts.v1.json` for primary/secondary workflow action projection and exact repair sub-operation contracts.
8. `06d-ui-style-schema-acceptance.md` for schema validation rules.
9. `06c-style-aware-ui-closure.md` for closure and repair consumption.
10. `08-implementation-phases.md`, `09-risks-dod-open-questions.md`, and `10-recommended-first-slice.md` for phase scoping.

Ledger acceptance:

- The full-target closure ledger must include the capability IDs above in addition to the package IDs from `06a`, `06c`, `06d`, and `07`.
- Validators fail when these IDs are missing, duplicated under a different owner doc, or represented only by mutable prose headings.
