# Godot UI Style Snapshot Schema Map

Source: original `../2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening.md` lines 1378-2151, normalized into this schema map plus the machine-readable contract example/schema fixture below.

Machine-readable contract example/schema fixture: [`schemas/godot-ui-style-contract.v1.example.json`](schemas/godot-ui-style-contract.v1.example.json)

Acceptance rules: [`06d-ui-style-schema-acceptance.md`](06d-ui-style-schema-acceptance.md)

## Purpose

This document is the map for the Godot UI style snapshot contract. The JSON artifact is intentionally kept separate so Markdown remains reviewable while the machine contract remains complete and parseable. It is an example contract instance and schema fixture that defines expected fields, nested objects, enum-like values, and validator coverage.

Phase 0 schema authority:

- Phase 0 acceptance uses the JSON fixture plus deterministic validators as the machine contract authority.
- A formal JSON Schema file is not required for Phase 0, but the implementation must provide a machine-readable schema contract profile for `schemas/godot-ui-style-contract.v1.example.json`. The profile may be JSON Schema, a validator fixture, or generated validator metadata, but it must encode required top-level fields, required nested fields for active rows, enum-like allowed values, minimum array cardinality for active required sections, stable `capability_id` references, and optional-empty-array versus missing-required-array behavior.
- Deterministic validators must treat the fixture and its schema contract profile as structural contracts, not examples. Pipe-delimited enum strings in the example fixture are documentation shorthand only; validators must consume the machine-readable enum set from the schema contract profile or a generated equivalent.
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
2. `schemas/godot-ui-style-contract.v1.example.json` for the machine-readable example contract instance/schema fixture.
3. `06d-ui-style-schema-acceptance.md` for schema validation rules.
4. `06c-style-aware-ui-closure.md` for closure and repair consumption.
5. `08-implementation-phases.md`, `09-risks-dod-open-questions.md`, and `10-recommended-first-slice.md` for phase scoping.

Ledger acceptance:

- The full-target closure ledger must include the capability IDs above in addition to the package IDs from `06a`, `06c`, `06d`, and `07`.
- Validators fail when these IDs are missing, duplicated under a different owner doc, or represented only by mutable prose headings.
