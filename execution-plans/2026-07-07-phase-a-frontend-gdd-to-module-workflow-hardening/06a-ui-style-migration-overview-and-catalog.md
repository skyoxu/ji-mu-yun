# TapTapMarker UI Style Migration Overview, Checklist, Catalog

Source: `../2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening.md` lines 1231-1377.

## 11.3 Godot UI Style Theme Contract Migration

This section migrates TapTapMarker's UI style skill system into a Godot-only workflow contract. It is not a runtime migration. The source capability idea is: style should be selected before UI generation, frozen as a versioned contract, implemented through centralized theme tokens and component defaults, validated with visual evidence, and reused by repair/UI closure so the prototype does not drift between unrelated visual languages.

TapTapMarker source capabilities observed:

- `urhox-libs/UI` provides a Widget tree, layout layer, rendering layer, input/event flow, style/theme layer, UI inspector, serializer/loader, built-in widgets, and game composition components.
- `ui-astroon`, `ui-brawlforge`, and `ui-pixelforge` each provide trigger rules, design DNA, font setup, theme initialization templates, token tables, component notes, and rules that visual properties should come from the theme rather than ad hoc per-component styling.
- The style skills encode concrete token families: palette, semantic colors, typography, radius, shadow, spacing, density/scale assumptions, component defaults, state tokens, rarity/HUD colors, and component-specific exceptions.
- The UI framework documentation treats layout scale, pixel alignment, event hit testing, and component state behavior as part of UI correctness. In this repo those concepts belong in Godot `Control` layout, viewport evidence, focus/input states, and style validation rather than TapTapMarker runtime APIs.

Full TapTapMarker non-technology UI capability target:

| Capability ID | Capability package | Godot/Phase translation | Primary split doc |
| --- | --- | --- | --- |
| `ui_component_system` | Widget/component system | Godot `Control` scenes, composed controls, component family baseline, component coverage matrix, and game composition templates. | This document and `06b-ui-style-snapshot-schema.md` |
| `ui_theme_token_system` | Theme token system | Machine-readable tokens, canonical token value format, Godot `Theme` slot mapping, `StyleBox`/`FontFile`/`Texture2D` resources, and token coverage evidence. | `06b-ui-style-snapshot-schema.md` |
| `ui_layout_scale_coordinates` | Layout, scale, and coordinates | Godot anchors, containers, size flags, viewport classes, display scale, DPI, safe area, layout bounds, and hit-test coordinate readback. | `06b-ui-style-snapshot-schema.md` |
| `ui_input_pointer_gesture` | Input, pointer, and gestures | `Control.gui_input`, `_unhandled_input`, InputMap actions, pointer event shape, gesture phases, drag/drop payload lifecycle, keyboard/gamepad equivalents, and validation evidence. | `06b-ui-style-snapshot-schema.md` |
| `ui_state_data_binding` | State and data binding | Stateless/stateful/controlled/uncontrolled rules, route state binding, form state, IME/composition input, selection/cursor, disabled/readonly/placeholder semantics. | `06b-ui-style-snapshot-schema.md` |
| `ui_lifecycle_ownership` | UI lifecycle | Godot lifecycle hooks, signal connect/disconnect ownership, timers, tweens, process mode, cleanup, orphan diagnostics, and duplicate subscription guards. | `06b-ui-style-snapshot-schema.md` |
| `ui_scroll_virtualization` | Scroll and virtualization | Scroll/list/grid/timeline visible range, clipping, item extent or measurement, keying, buffer window, recycling, and performance evidence. | `06b-ui-style-snapshot-schema.md` |
| `ui_overlays_feedback` | Overlays and feedback | Modal/drawer/popover/tooltip focus and dismissal, Toast queue/duration/enter-exit, status feedback, and visual evidence. | `06b-ui-style-snapshot-schema.md` and `06c-style-aware-ui-closure.md` |
| `ui_diagnostics_visual_evidence` | Diagnostics and visual evidence | Screenshot/canvas/exported visual evidence, deterministic substitute limits, UI tree readback, style drift findings, and repair prompts. | `06b-ui-style-snapshot-schema.md`, `06c-style-aware-ui-closure.md`, and `07-godot-diagnostics-quality-gates.md` |
| `ui_security_gated_tooling` | Security-gated tooling UI | File upload and similar tool/admin UI only when Phase service security policy, account isolation, readback safety, and cleanup rules exist. | This document and `06b-ui-style-snapshot-schema.md` |

### 11.3.1 Conflict Assessment

| TapTapMarker style capability | Conflict in this repo | Godot decision |
| --- | --- | --- |
| UrhoX UI Widget library | This repo targets generated Godot projects, not UrhoX | Translate the architecture concept into Godot `Control` scene composition, `Container` layout, `CanvasLayer` HUD layering, centralized `Theme` resources, and route evidence. |
| Yoga layout layer | Godot has its own anchors, containers, size flags, theme metrics, and safe-area handling | Use Godot `Container` nodes, anchors, `Control.custom_minimum_size`, size flags, viewport-safe scaling, and screenshot/viewport evidence. Do not introduce Yoga. |
| NanoVG rendering layer | Godot uses CanvasItem drawing, theme resources, materials, and shaders | Use `Control._draw`, `CanvasItem`, `StyleBoxFlat`, `StyleBoxTexture`, `ShaderMaterial`, `CanvasItemMaterial`, and exported visual evidence. Do not introduce NanoVG calls. |
| Lua theme initialization templates | This repo is C#/.NET-centered for Godot prototypes | Express examples as Godot `Theme` resources, `.tres`/`.res`, C# setup helpers, typed GDScript only where existing projects already use it, and JSON route contracts. |
| Skill-specific font files | Fonts have licensing, storage, and runtime packaging implications | Define a repo-owned font asset and license policy. Style contracts may name font roles and fallback stacks, but implementation must use approved project assets or generated/open licensed fonts. |
| "Visual properties come from theme, not per-component" | Godot allows direct per-node overrides, which can cause drift | Require style-critical colors, fonts, radius, borders, shadows, spacing, and state tokens to come from a frozen style contract and generated Godot theme resources. Per-node overrides need structured exceptions. |
| UI inspector/serializer concepts | Phase A uses browser readback and hosted workspace evidence rather than TapTapMarker local inspector tools | Translate into route readback: selected style ID/version/hash, style token snapshot, generated theme resource refs, style-drift findings, screenshots, and UI closure evidence. |

Acceptance criteria:

- No implementation prompt, route state, style guide, generated Godot code, or durable workflow standard requires UrhoX widgets, Yoga, NanoVG, Lua theme templates, EmmyLua annotations, or TapTapMarker font assets.
- Every migrated style capability has a Godot-owned equivalent, a route artifact, a validation check, and a readback surface.
- Every capability package has a stable `capability_id`; ledgers, validators, and Phase exit evidence use this ID rather than mutable prose headings.
- The only permitted TapTapMarker runtime terms are in conflict-assessment documentation, migration rationale, or technology-leakage denylist fixtures.
- Review records zero unresolved P0/P1/P2 findings for technology-stack leakage, missing Godot equivalent, font policy ambiguity, style-drift acceptance, or untestable style validation.

### 11.3.2 Full UI Style Theme Migration Checklist

The workflow must treat the following style-system capabilities as first-class contracts for UI-touching work:

1. Style catalog, trigger taxonomy, and selection
   - Godot ownership: `docs/ui-style-guides/*.md`, `docs/standards/godot-ui-style-contract.md`, project-level `uiStyleId`, and route-visible style recommendation.
   - Required workflow data: repo-owned style ID, style name, version, source guide hash, trigger tags, suitable game genres/moods, suitable reference directions, explicit user/admin override, and selected/fallback reason.
2. Frozen style snapshot
   - Godot ownership: deterministic JSON snapshot stored with the prototype contract and copied into UI-touching route state.
   - Required workflow data: `ui_style_id`, `ui_style_version`, `ui_style_snapshot_hash`, source guide hash, token hash, font policy hash, and canonical hash exclusions.
3. Token families
   - Godot ownership: palette tokens, semantic colors, typography roles, spacing, density, scale, radius, border, shadow, opacity, state colors, rarity/HUD colors, and composition exceptions.
   - Required workflow data: token name, token value, intended component use, forbidden substitutions, and validation rule.
4. Semantic usage and action-role rules
   - Godot ownership: style-specific semantic rules for primary/secondary/destructive/dismiss actions, modal footer layout, button casing, status/HUD meaning, rarity meaning, and component-specific semantic exceptions.
   - Required workflow data: rule ID, affected action/component role, required token or layout behavior, forbidden substitution, not-applicable rationale, validation refs, and repair guidance.
5. Godot theme resource generation
   - Godot ownership: generated or checked-in `Theme` resources, `StyleBoxFlat`/`StyleBoxTexture`, `FontFile` references, component default mappings, and scene template refs.
   - Required workflow data: resource paths, node/control owner, token source, font source, generated/hand-authored status, and packaging evidence.
6. Component defaults and exceptions
   - Godot ownership: central style defaults for Button, Panel/Card, Modal/Dialog, Tabs/Menu/List, TextField, Slider, ProgressBar, Tooltip/Toast, HUD/status bars, deck/card/reward panels, and any other built-in UI family declared by the style catalog.
   - Required workflow data: component family, default tokens, allowed overrides, exception rationale, and tests.
7. Component coverage matrix
   - Godot ownership: per-style support matrix for built-in UI families such as Button, Checkbox, Toggle, Slider, TextField, Card, Badge, Chip, Alert, Avatar, ProgressBar, Tabs, Menu, Stepper, Breadcrumb, Pagination, Toast, Tooltip, Modal, Drawer, Popover, Dropdown, Table, List, Accordion, Rating, DatePicker, TimePicker, Calendar, ColorPicker, Timeline, Tree, Carousel, FileUpload, and game composition families.
   - Required workflow data: component family, coverage status `required|style_optional|conditional|admin_tooling_or_security_gated|not_applicable|deferred|not_consumed_by_first_slice`, required tokens, state coverage, component-specific exceptions, validation refs, and rationale for gaps.
8. Visual state system
   - Godot ownership: hover, pressed, focused, disabled, selected, active, error, success, warning, info, drag-hover, drop-valid, and drop-invalid states where the component supports them.
   - Required workflow data: state token mapping, input path, focus behavior, visual evidence refs, and unavailable-state rationale.
9. Font asset and license policy
   - Godot ownership: repo-approved fonts, generated/open licensed fonts, fallback stacks, `FontFile` import settings, packaging checks, and missing-font blockers.
   - Required workflow data: font role, asset path, license/source, fallback, packaging status, and readback-safe name.
10. Style composition rules
   - Godot ownership: rules for one primary style per project/screen, explicit mixed-style exceptions, sub-surface overrides, and scene-specific style compatibility.
   - Required workflow data: composition owner, affected scene IDs, allowed mixed tokens, rationale, and review evidence.
11. Style drift detection
   - Godot ownership: route-state validators, prompt/evidence checks, screenshot/canvas-pixel/exported visual evidence, token diff checks, and UI closure style findings.
   - Required workflow data: drift family, expected token/source, observed artifact, severity, remediation goal, and evidence refs.
12. Density, scale, and responsive layout policy
   - Godot ownership: viewport breakpoints, safe-area behavior, minimum interactive target sizes, pixel-alignment requirements for pixel styles, `Control.custom_minimum_size`, size flags, and theme metric mapping.
   - Required workflow data: target viewport set, style density mode, scale constraints, minimum hit target, overflow strategy, text measurement rule, and screenshot/exported evidence refs.
13. Source-name and public alias policy
   - Godot ownership: repo-owned internal style IDs, source inspiration metadata, optional public aliases, approval references, and route-state guards that prevent source skill names from becoming execution identity.
   - Required workflow data: internal style ID, source inspiration label, public alias, approval reference, reviewer/owner, approval date or decision log ref, and validation status.
14. Game composition templates
   - Godot ownership: style-aware scene templates for combat HUD, route map, deck/card hand, reward selection, inventory, dialog, status bars, modal settings, and toast/notification flows.
   - Required workflow data: template ID, required requirement IDs, scene/node paths, style tokens used, input states, and validation refs.
15. Design DNA and custom-style equivalence
   - Godot ownership: machine-readable style principles, forbidden visual behavior, and custom-style equivalence rows.
   - Required workflow data: rule ID, affected component families, required visual behavior, custom requirement family, validation rule, and validation refs.
16. Pointer, gesture, and input event behavior
   - Godot ownership: `InputMap`, `Control.gui_input`, `_unhandled_input`, focus navigation, mouse/touch/gamepad/keyboard paths, drag/drop, pan, tap, long press, wheel, and cancel behavior.
   - Required workflow data: gesture type, supported devices, event flow, coordinate space, propagation/default-action policy, focus policy, and validation refs.
17. UI state ownership and data binding
   - Godot ownership: stateless/stateful controls, controlled/uncontrolled values, route-state binding, autoload or scene-node ownership, signals, and update sources.
   - Required workflow data: state owner, controlled mode, source signal refs, update method, persistence scope, and validation refs.
18. UI lifecycle and subscription ownership
   - Godot ownership: dynamically created nodes, signal connections, timers, tweens, process callbacks, input subscriptions, scene-tree ownership, and `QueueFree` cleanup.
   - Required workflow data: dynamic owner, subscription owner, cleanup method, duplicate-subscription guard, lifecycle validation refs, and orphan diagnostics.
19. Scroll, clipping, and virtualization
   - Godot ownership: `ScrollContainer`, clipping masks, overflow behavior, virtualized list/grid policies, item keying, visible range readback, and large-list performance limits.
   - Required workflow data: overflow axis, clipping owner, virtualization requirement, item key policy, visible-range readback, performance limit, and validation refs.
20. Font-size unit and text measurement policy
   - Godot ownership: Godot `Theme` font sizes, design-pixel mapping, line height, min/max readable sizes, text measurement, and per-style typography refs.
   - Required workflow data: design unit, Godot unit, conversion rule, line-height rule, min/max sizes, text measurement rule, and validation refs.
21. Localization and text overflow policy
   - Godot ownership: localized UI copy expansion, CJK/Latin fallback font behavior, wrapping, max lines, ellipsis, clipping, and safe overflow state.
   - Required workflow data: supported locales or input-language class, expansion factor, wrapping rule, max-lines rule, overflow behavior, fallback font role, and validation refs.
22. Visual evidence matrix and UI tree readback rows
   - Godot ownership: matrix rows that bind viewport, scene, component family, state, source hash, screenshot/exported evidence, and readback node rows.
   - Required workflow data: matrix ID, route ID, viewport or scene, required component families, required states, evidence refs, and UI tree readback row refs.

Acceptance criteria:

- A UI-touching P0/P1 requirement cannot reach execution without `ui_style_id`, `ui_style_version`, `ui_style_snapshot_hash`, and `source_ui_style_contract_hash`. `style_not_applicable` is valid only when evidence proves no visible UI style contract applies; it does not remove any separate UI surface requirement.
- UI style selection occurs before iteration-plan generation for UI-facing requirements and is frozen into the prototype contract before execute-next-goal can create UI.
- UI-touching prompts contain the frozen Godot UI style snapshot and generated theme resource refs, not mutable broad style-guide excerpts.
- Style-critical visual decisions are represented as tokens or component defaults. Per-node/per-control overrides require an exception with component, token, rationale, and validation evidence.
- Style drift findings are grouped by the normalized bounded families in this document: `design_dna`, `palette`, `typography`, `radius`, `border`, `shadow`, `opacity`, `spacing`, `density_scale`, `rarity_hud`, `gradient_glow`, `bottom_accent`, `component_defaults`, `component_coverage`, `component_family_baseline`, `variant_coverage`, `component_exception_rules`, `forbidden_patterns`, `motion_transition`, `game_composition_templates`, `theme_resource_refs`, `theme_resource_coverage`, `semantic_usage`, `action_role`, `contrast_readability`, `font_policy`, `font_size_unit`, `localization_overflow`, `pointer_gesture`, `gesture_phase`, `pointer_event_shape`, `drag_drop_payload`, `state_ownership`, `ui_lifecycle`, `scroll_virtualization`, `state_tokens`, `composition`, `ui_tree_readback`, `source_name_ownership`, `runtime_environment`, `file_upload_security`, `visual_evidence`, and `visual_evidence_method`.
- Built-in style selection must use repo-owned internal IDs. Source skill names may appear only in migration rationale, external-label metadata, or an approved product/legal alias record.
- High-risk UI style changes include screenshot/canvas-pixel/exported visual evidence or an approved deterministic substitute with harness-limitation rationale, owner, expiry, and recheck trigger. Deterministic substitutes cannot replace interaction behavior validation such as drag/drop, focus trap, keyboard navigation, gamepad navigation, pointer event handling, or route-state mutation.
- `style_not_applicable` exempts only the style contract requirement. It does not exempt UI surface, interaction, feedback, diagnostics, source-boundary, or final-readiness evidence for a visible feature.
- If a feature has no visible UI, route state may record both `no_ui_needed` and `style_not_applicable`, but each exemption needs its own reason, decision role, timestamp, requirement IDs, and evidence refs.
- System-created P0/P1 `style_not_applicable` exemptions remain blocking `needs_review` until confirmed by an admin or by an explicitly allowed user confirmation flow.
- The Godot UI style theme migration cannot pass unless review records zero unresolved P0/P1/P2 findings for style selection, snapshot freshness, runtime environment identity, design DNA rules, structured token coverage and canonical token format, semantic usage/action-role rules, component coverage, component family baseline, variant coverage, component exception refs, forbidden patterns, pointer/gesture behavior, gesture phases, pointer event shape, drag/drop payload lifecycle, state ownership/data binding, UI lifecycle/subscription ownership, scroll/virtualization policy, motion/transition rules, structured composition rules, game composition templates, density/scale policy, font-size unit policy, localization/overflow policy, contrast/readability rules, font policy, icon/texture policy, structured component defaults, state tokens, style drift, safe theme/visual refs, Godot theme slot mapping, UI tree readback, visual evidence matrix coverage and evidence method, deterministic substitute approval/expiry/recheck metadata, file upload security gating, custom style metadata and built-in-equivalent checks, source-name ownership, structured alias approval, or technology-stack leakage.

### 11.3.3 Recommended Built-In Godot Style Catalog

The plan should introduce Godot-native equivalents inspired by TapTapMarker's style families. Internal IDs must be repo-owned and neutral; source skill names can be reused only as product-facing labels if legal/product review approves and the approval is recorded.

| Proposed style ID | Borrowed idea | Godot-native contract intent |
| --- | --- | --- |
| `godot_cosmic` | Cosmic cartoon, dark gradient, glowing accents, readable sans text, pill buttons, rarity colors | Space/fantasy UI with `Theme` tokens for cosmic backgrounds, gold primary CTA, glow-style shadows through Godot-compatible style resources, and layered panels. |
| `godot_combat_hud` | Competitive combat HUD, sharp silhouettes, thick borders, bold typography, vivid state colors | Action/combat UI with hard-edged `StyleBox` defaults, strong borders, dedicated HUD bar colors, bold font roles, and clear pressed/focused/disabled states. |
| `godot_pixel_arcade` | Retro pixel-art, zero radius, hard shadows, pixel fonts, high-contrast saturated accents | Pixel/arcade UI with zero-radius defaults, pixel-friendly scale policy, approved pixel fonts or fallbacks, no blur shadows, and square component templates. |

UI family tiers:

| Tier | Component families | Godot-owned implementation equivalents | Phase posture |
| --- | --- | --- | --- |
| `core_minimum` | `button`, `checkbox`, `toggle`, `slider`, `text_field`, `text_area`, `panel_card`, `modal`, `tooltip`, `progress_bar`, `tabs`, `menu`, `dropdown`, `scroll_view`, `list_view` | `Button`, `CheckBox`, `CheckButton`, `HSlider`/`VSlider`, `LineEdit`, `TextEdit`, `PanelContainer`, `Window`/`PopupPanel`, `ProgressBar`, `TabContainer`, `PopupMenu`, `OptionButton`, `ScrollContainer`, and composed `Control` scenes. | Required for built-in styles once the style contract is implemented. Cannot be deferred without a P1 blocker. |
| `game_minimum` | `stat_bar`, `hud_cluster`, `deck_hand`, `card_view`, `reward_panel`, `route_map`, `combat_hud`, `dialog_box` | `CanvasLayer`, `Control`, `Container`, `TextureRect`, `ProgressBar`, route-state-backed composed scenes, and interaction-region evidence. | Required when the GDD/default prototype contract needs the gameplay surface. |
| `conditional_builtin` | `badge`, `chip`, `alert`, `toast`, `drawer`, `popover`, `table`, `grid_view`, `timeline`, `carousel`, `accordion`, `tree`, `stepper`, `breadcrumb`, `pagination`, `rating`, `calendar`, `date_picker`, `time_picker`, `color_picker`, `item_slot`, `inventory_grid`, `quest_tracker` | Composed Godot `Control` scenes, `GridContainer`, `Tree`, `ColorPickerButton`, and route-state-backed validation. | Supported by the full TapTapMarker capability target, but Phase 0/1 may mark not applicable unless a requirement needs them. |
| `admin_tooling_or_security_gated` | `file_upload`, account/admin-only asset tools, raw diagnostic viewers | Phase service API/readback, upload policy, account isolation, storage cleanup, redacted admin evidence, and browser-safe metadata. | Must be `not_applicable` for normal-user game UI unless a Phase service security policy exists. |

Acceptance criteria:

- Each built-in style guide includes design DNA, trigger/use cases, structured token/default schemas, semantic usage/action-role rules, Godot theme mapping, component defaults, variant coverage, game composition templates, state-token rules, font policy, forbidden patterns, theme resource refs, visual evidence examples, and known non-applicable cases.
- Each built-in style guide includes a component coverage matrix for the declared built-in UI families, including component-specific exceptions inspired by the source style only when translated into Godot-owned tokens and validation refs.
- Each built-in style guide must classify every UI family in the tier table with `coverage_status` as `required`, `style_optional`, `conditional`, `admin_tooling_or_security_gated`, `not_applicable`, `deferred`, or `not_consumed_by_first_slice`. `core_minimum` rows cannot be `deferred` or `not_consumed_by_first_slice` without a P1 blocker and owner.
- Scroll/list/grid families cannot be marked complete without `scroll_virtualization_rules` rows that bind `scroll_view`, `list_view`, `grid_view`, or the applicable Godot equivalent to clipping, overflow, visible-range, keying, and performance policy.
- `file_upload` cannot be marked required, supported, or style-optional for normal-user workflows without a Phase service security policy that defines allowed file types, maximum size, storage location, account isolation, content validation, temporary file cleanup, readback-safe metadata, and admin-only raw evidence access. If the policy is absent, `file_upload` must be `not_applicable` for normal-user game UI; admin-only tooling rows may use `admin_tooling_or_security_gated` only when they remain hidden from normal users and record the missing security-policy blocker.
- Each built-in style guide includes a machine-readable JSON or YAML contract used by tests; prose-only style guides are not sufficient.
- Built-in styles do not depend on TapTapMarker assets, Lua templates, UrhoX widgets, Yoga, NanoVG, or EmmyLua.
- Built-in internal style IDs are repo-owned. Any source-inspired public alias must be optional metadata with recorded approval and must not become route identity.
- A reviewer can add or update a style only by updating its contract, tests, visual evidence fixtures, docs index entry, and style-selection policy together.
- Review records zero unresolved P0/P1/P2 findings for style catalog completeness, Godot-native implementation, source-name ownership, licensing, or testability.
