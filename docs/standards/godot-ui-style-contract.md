# Godot UI Style Contract

Status: Living standard
Language: English
Scope: Godot UI style catalog, style selection, frozen style snapshots, style drift taxonomy, component coverage, style guide identity, and UI-touching hosted route evidence.

## Purpose

This standard migrates the useful style-system ideas from TapTapMarker into a Godot-only workflow contract. It is not a runtime migration. Style must be selected before UI generation, frozen as a versioned contract, implemented through centralized Godot theme tokens and component defaults, validated with visual evidence, and reused by repair/UI closure so prototypes do not drift between unrelated visual languages.

This standard consumes `docs/standards/godot-engine-semantics.md` and `docs/standards/godot-ui-capability-contract.md`.

## Machine-Readable Catalog

The runtime registry is `PhaseA.Platform/Workflow/GodotUiStyleCatalog.cs`.
The parity fixture is `PhaseA.Platform.Tests/Fixtures/godot-ui-style-catalog.v1.json`.
The style snapshot schema fixture is `docs/schemas/godot-ui-style-contract.v1.example.json`, mirrored into `PhaseA.Platform.Tests/Fixtures/godot-ui-style-contract.v1.example.json`.
The schema profile owner is `PhaseA.Platform/Workflow/GodotUiStyleSnapshotSchema.cs`.
The deterministic test owners are `PhaseA.Platform.Tests/Workflow/GodotUiStyleCatalogTests.cs` and `PhaseA.Platform.Tests/Workflow/GodotUiStyleSnapshotSchemaTests.cs`.
Style guide seeds live under `docs/ui-style-guides/`.

The registry owns:

- Catalog id/version/hash.
- Repo-owned style IDs and guide paths.
- Trigger tags and design DNA.
- Component family tiers and coverage statuses.
- Style capability IDs.
- Normalized style drift families.
- Technology denylist terms.
- Snapshot schema required fields, enum-like values, active array cardinality, and hash identity fields through the schema profile.

Do not add a built-in style, style capability, component tier, coverage status, or drift family in docs only. Update registry, fixture, tests, and this document together.

## Technology Boundary

No implementation prompt, route state, style guide, generated Godot code, or durable workflow standard may require UrhoX widgets, Yoga, NanoVG, Lua theme templates, EmmyLua annotations, TapTapMarker font assets, or TapTapMarker runtime APIs.

Allowed references to those terms are limited to migration rationale, conflict assessment, or denylist fixtures. Built-in internal style IDs are repo-owned and neutral. Source-inspired public aliases are optional metadata only after product/legal approval and must not become route identity.

## Style Capabilities

Stable capability IDs:

- `ui_component_system`
- `ui_theme_token_system`
- `ui_layout_scale_coordinates`
- `ui_input_pointer_gesture`
- `ui_state_data_binding`
- `ui_lifecycle_ownership`
- `ui_scroll_virtualization`
- `ui_overlays_feedback`
- `ui_diagnostics_visual_evidence`
- `ui_security_gated_tooling`

Ledgers, validators, Phase exit evidence, and review findings must use these IDs rather than mutable prose headings.

## Built-In Style Catalog

Current repo-owned built-in style IDs:

| Style ID | Intent |
| --- | --- |
| `godot_cosmic` | Space/fantasy UI with cosmic backgrounds, gold primary CTA, Godot-compatible glow-style shadows, layered panels, and rarity colors. |
| `godot_combat_hud` | Action/combat UI with sharp silhouettes, thick borders, bold typography, vivid state colors, and hard-edged HUD bars. |
| `godot_pixel_arcade` | Pixel/arcade UI with zero-radius defaults, pixel-friendly scale policy, approved pixel font fallback, and square component templates. |

The guide seeds are:

- `docs/ui-style-guides/godot-cosmic.md`
- `docs/ui-style-guides/godot-combat-hud.md`
- `docs/ui-style-guides/godot-pixel-arcade.md`

Guide prose is not execution authority by itself. UI-touching execution uses frozen route state, prototype contract hashes, and machine-readable snapshots.

## Component Tiers

| Tier | Default status | Notes |
| --- | --- | --- |
| `core_minimum` | `required` | Button, checkbox, toggle, slider, text fields, panel/card, modal, tooltip, progress bar, tabs, menu, dropdown, scroll view, and list view. Cannot be deferred without a P1 blocker and owner once the style contract is active. |
| `game_minimum` | `conditional` | Stat bar, HUD cluster, deck hand, card view, reward panel, route map, combat HUD, dialog box. Required when GDD/prototype contract needs the gameplay surface. |
| `conditional_builtin` | `conditional` | Badge, chip, alert, toast, drawer, popover, table, grid, timeline, carousel, accordion, tree, steppers, pickers, inventory, quest tracker, and similar families. |
| `admin_tooling_or_security_gated` | `admin_tooling_or_security_gated` | File upload, account/admin asset tools, and raw diagnostic viewers require Phase service security policy before normal-user exposure. |

Coverage statuses must use `style_capability_coverage`: `required`, `style_optional`, `conditional`, `admin_tooling_or_security_gated`, `not_applicable`, `deferred`, or `not_consumed_by_first_slice`.

`file_upload` cannot be marked required, supported, or style-optional for normal-user workflows without a Phase service security policy defining allowed file types, size, storage, account isolation, content validation, cleanup, readback-safe metadata, and admin-only raw evidence access.

## Style Snapshot Schema Profile

Phase 0 uses the durable JSON fixture and schema profile as the machine-readable style snapshot contract. The profile records required top-level fields, required active arrays, optional-empty arrays, enum-like value sets, 06b capability IDs, and hash identity fields.

Required 06b capability IDs:

- `ui_style_snapshot_schema`
- `ui_runtime_environment_identity`
- `ui_theme_resource_contract`
- `ui_visual_evidence_contract`

Runtime environment participates in style snapshot hash identity unless a future ADR or decision log explicitly changes that rule.

## Style Selection And Snapshot Rules

A UI-touching P0/P1 requirement cannot reach execution without:

- `ui_style_id`
- `ui_style_version`
- `ui_style_snapshot_hash`
- `source_ui_style_contract_hash`

UI style selection occurs before iteration-plan generation for UI-facing requirements and is frozen into the prototype contract before execute-next-goal can create UI. UI-touching prompts use the frozen Godot UI style snapshot and generated theme resource refs, not mutable broad style-guide excerpts.

`style_not_applicable` is valid only when evidence proves no visible UI style contract applies. It does not remove separate UI surface, interaction, feedback, diagnostics, source-boundary, or final-readiness requirements. System-created P0/P1 `style_not_applicable` exemptions remain blocking `needs_review` until confirmed by admin or by an explicitly allowed user confirmation flow.

## Drift Taxonomy

Style drift findings must use these bounded families from the registry:

- `design_dna`
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
- `component_defaults`
- `component_coverage`
- `component_family_baseline`
- `variant_coverage`
- `component_exception_rules`
- `forbidden_patterns`
- `motion_transition`
- `game_composition_templates`
- `theme_resource_refs`
- `theme_resource_coverage`
- `semantic_usage`
- `action_role`
- `contrast_readability`
- `font_policy`
- `font_size_unit`
- `localization_overflow`
- `pointer_gesture`
- `gesture_phase`
- `pointer_event_shape`
- `drag_drop_payload`
- `state_ownership`
- `ui_lifecycle`
- `scroll_virtualization`
- `state_tokens`
- `composition`
- `ui_tree_readback`
- `source_name_ownership`
- `runtime_environment`
- `file_upload_security`
- `visual_evidence`
- `visual_evidence_method`

Style-critical visual decisions must be represented as tokens or component defaults. Per-node/per-control overrides require exception records with component, token, rationale, and validation evidence.

High-risk UI style changes require screenshot/canvas-pixel/exported visual evidence or an approved deterministic substitute with harness-limitation rationale, owner, expiry, and recheck trigger. Deterministic substitutes cannot replace interaction behavior validation such as drag/drop, focus trap, keyboard navigation, gamepad navigation, pointer event handling, or route-state mutation.

## Validation

Minimum deterministic validation for this catalog:

```powershell
dotnet test PhaseA.Platform.Tests --filter "FullyQualifiedName~GodotUiStyleCatalogTests|FullyQualifiedName~GodotUiStyleSnapshotSchemaTests"
```

When style snapshot, schema, or UI closure behavior changes, also run `docs/standards/godot-ui-style-closure.md` tests and the follow-on acceptance tests.
