# Phase B AGF And godogen Capability Absorption Plan

Status: Draft
Date: 2026-06-24
Owner: Phase B platform workflow
Scope: Windows-only Godot C# hosted game-project platform and prototype-generation capabilities that can be closed by deterministic system evidence.

## Purpose

This document defines the Phase B absorption plan for selected ideas from AGF and godogen under one hard constraint:

- Exclude any capability whose final pass/fail depends on AI inventing requirements or on a human making the final acceptance decision. Human review artifacts may be produced, but they cannot be the system-of-record acceptance gate.

Prototype generation, prototype routes, and type-kit expansion are in scope when they can be governed by deterministic contracts, route state, tests, acceptance markers, evidence bundles, and account-scoped readback.

The target is not to copy AGF or godogen. The target is to absorb their useful operating patterns into this repository's Phase B platform and prototype-generation layer while preserving this repository's authority model: repository-native scripts and route services own workflow decisions; the browser and hosted platform provide controlled execution, readback, audit, and recovery.

## Source Snapshots

- AGF local research snapshot: `logs/research/agf`, commit `96c8e15e450fc6fa4c96c60d1ddef41b0df43276`.
- godogen local research snapshot: `logs/research/godogen`, commit `51954f9f34d18044c501a09c0645ff0e680edbdf`.
- This document treats both as external pattern sources, not runtime dependencies.

## Existing Repository Baseline

This repository already has several Phase B-compatible foundations:

- Account-scoped project, run, package, asset, chat, artifact, and workflow readback.
- Admin/user token isolation, LLM binding, LLM usage tracking, admin audit, CSV export, and Phase B smoke verification.
- Hosted project route recovery order with project-level sources, route state, repair evidence, and latest blocker priority.
- Shared LLM/Codex invocation entrypoints for C# and Python routes.
- BMAD/GDS 24 game-type guides as design semantics, not direct executable promises.
- Prototype type kits as executable-route input contracts.
- Active executable route profiles for default, RPG/JRPG, survivorslike, and deckbuilder flows.

## Non-Goals

- No browser replacement for the Godot editor.
- No browser drag-edit promise for engine-owned scene concepts. Browser surfaces may provide readback, review annotation, and route control only. Review annotation does not affect machine acceptance. Any future write path for collision boxes, spawn points, regions, tilemaps, or scene geometry must execute through a Godot-native tool, plugin, or validated repository script and then pass deterministic verification.
- No AGF OGF schema adoption as a replacement for Godot scenes, C# scripts, or project files.
- No duplicate game-type taxonomy that competes with BMAD/GDS guides.
- No subjective visual-quality gate where AI or a human decides whether the game looks good.
- No multi-engine publishing model from godogen; this repository remains Windows-only Godot C#.
- No Android export target unless a later roadmap explicitly changes the desktop-only premise.

## Absorption Principles

### 1. System-Closed Before User-Visible

Every Phase B capability in this document must have deterministic acceptance evidence. A UI page may expose the evidence, but the pass/fail state must be derived from scripts, schema validation, logs, database rows, imported assets, package outputs, route state, tests, and stable diagnostics.

### 2. Evidence, Not Opinion

Screenshots, videos, and rendered frames are allowed as evidence artifacts. They are not sufficient acceptance by themselves unless the system validates objective properties such as existence, duration, dimensions, nonblank pixels, frame count, console assertions, expected marker text, import success, exit status, or bounded frame checks.

### 3. Derived Catalogs, Not Manual Truth

AGF-style matrices, type readiness tables, and asset-centric views must be derived from project files, manifests, run records, route profiles, package outputs, and validation scripts. A manually edited green status is not authoritative.

### 4. Engine-Native Project Remains The Source

Godot project files, C# code, assets under `res://`, package outputs, and repo sidecars remain the source of truth. Any schema introduced by Phase B must be a sidecar for planning, readback, audit, validation, or route recovery, not a replacement scene format.

### 5. Prototype Routes Are Contracted, Not Implied

BMAD/GDS guide coverage does not imply executable prototype support. A game type becomes executable only after it has a type kit, route profile, strategy, skill contract, plan guard, route recovery inputs, acceptance markers, and tests.

## Authority And Integration Rules

This document is a Phase B governance and absorption plan. It must not create a parallel prototype-route implementation model. Existing route framework documents and runtime classes remain the execution authority:

- `docs/workflows/game-type-route-framework-guide.md` remains the detailed route implementation guide.
- `docs/workflows/game-type-route-profile-guide.md` remains the detailed route profile onboarding guide.
- `PrototypeGoalAcceptanceContract` and `PrototypeGoalAcceptanceValidator` remain the execution-time acceptance contract and validator surface.
- `PrototypeRouteStateWriter` remains the route-state writer unless explicitly superseded by an ADR or implementation plan.
- `GameTypeRouteProfiles` and `GameTypeRouteStrategies` remain the executable route dispatch surfaces.

New Phase B sidecars such as `route-acceptance.json`, evidence bundles, readiness catalogs, and ledgers must be derived from or linked to those existing surfaces. They may summarize, audit, or expose route state; they must not redefine route semantics independently.

## Security And Redaction Rules

Evidence and readback are product features, but they are also leakage risks. Any implemented bundle or sidecar in this plan must follow these rules before browser/API exposure:

- Never expose plaintext token material, gateway credentials, provider keys, bearer tokens, environment secrets, or admin tokens.
- Redact command lines, environment blocks, stdout, stderr, and logs before account-scoped readback when they may contain secrets or host-local sensitive paths.
- Store raw logs only under server-side evidence paths with account ownership metadata; browser readback should prefer sanitized summaries.
- Enforce size limits and truncation markers for logs and JSON blobs.
- Redaction validator fixtures must cover fake bearer tokens, fake provider keys, raw prompt bodies, stdout/stderr samples, command lines, environment blocks, and absolute host paths.
- Record `redaction_status`, `raw_evidence_path`, `sanitized_evidence_path`, and `readback_scope` in evidence metadata.
- Prompt text, prompt references, generation metadata, and provider response snippets may contain user IP, unreleased design, or private business context; browser/API readback must expose references or sanitized summaries by default, not raw prompt bodies.
- Public package or asset tickets must resolve the owning account before reading files.
- Admin readback may include cross-account summaries, but not raw command logs or evidence blobs unless a later security decision explicitly allows it.

## Schema Shape Defaults

All machine-readable artifacts introduced by this plan should include these fields unless a narrower schema explains why they are omitted:

- `schema_version`
- `producer_id` and `producer_version`
- `validator_id` and `validator_version` when validated
- `project_id`, `account_id`, and `run_id` when applicable
- `route_id`, `profile_id`, `session_id`, and `goal_id` when route-scoped
- `created_at_utc` and `validated_at_utc`
- `source_hashes` or equivalent stale-state inputs
- `status` from a bounded enum such as `passed`, `failed`, `blocked`, `unknown`, or `stale`
- `manual_override` is not supported for readiness or acceptance status; status must be derived from validators and evidence
- `evidence_refs` with logical artifact ids, workspace-relative sanitized paths, hashes, and sanitized/readback scope
- `retention_policy` and `expires_at_utc` for logs, captures, and large evidence blobs when applicable

For type kits, the human-readable Markdown remains the explanatory surface, but the machine-validated contract defaults to a sidecar JSON file such as `docs/prototype-type-kits/<type>.contract.json` or an equivalent generated JSON artifact. The contract JSON is the machine SSoT for Phase B validation. If Markdown and contract JSON disagree, validators must fail closed until the mismatch is resolved. Free-form Markdown alone is not sufficient for Phase B machine closure.

Minimum type-kit contract shape:

```json
{
  "schema_version": "phaseb-type-kit-contract-v1",
  "game_type_id": "deckbuilder",
  "profile_id": "godot-deckbuilder-v1",
  "always_on_capabilities": ["starter_deck_readability"],
  "conditional_capabilities": [
    {
      "id": "map_or_route_choice",
      "activation_sources": ["current_request", "contract_intent", "selected_capabilities"],
      "negative_semantics": ["no map", "single battle only"]
    }
  ],
  "first_goal_boundary": "Prove starter deck readability before adding route-map choice or shop systems.",
  "acceptance_markers": [
    {
      "id": "starter_deck_visible",
      "capability_id": "starter_deck_readability",
      "evidence_sources": ["scene", "test_output", "route_state"]
    }
  ],
  "recovery_inputs": ["meta/prototype-route/latest.json", "route ledger", "evidence bundle"],
  "authority_order": ["current request", "contract intent", "selected capabilities", "route state"],
  "stale_state_rules": ["session_id mismatch blocks reuse", "capability mismatch blocks final acceptance"]
}
```

## Path Defaults

While the live hosted runtime continues to use `logs/phase-a-innernet/` as its stable runtime root, Phase B evidence and readiness outputs should stay under that root for operational continuity:

- Evidence bundles: `logs/phase-a-innernet/evidence/`
- Readiness catalogs: `logs/phase-a-innernet/readiness/`
- Sanitized readback summaries: `logs/phase-a-innernet/readback/` or the current equivalent runtime evidence directory

Browser/API readback must expose logical artifact ids or workspace-relative sanitized paths. Raw absolute Windows paths stay server-side.

A future directory rename should be handled as a broader runtime migration, not as an isolated AGF/godogen absorption change.

## Integrated Capability Backlog

### B-AG-01: Capability Readiness Catalog

Source pattern: AGF Genre Support Matrix.

Adaptation:

Build a repository-native readiness catalog that records platform and prototype-route capability maturity by lifecycle area, not by optimistic product claims. This should not duplicate BMAD/GDS game-type templates. It should answer: which platform and prototype-route capabilities are machine-verified for a project, route, or game type?

Candidate row groups:

- Platform operations: account boundary, project workspace recovery, artifact readback, package availability, audit/export availability.
- Godot execution: import diagnostics, build diagnostics, runtime smoke evidence, capture evidence availability.
- Prototype routes: design guide, type kit, route profile, route strategy, skill contract, plan guard, goal acceptance, final acceptance, route recovery state.
- Assets: asset inventory, manifest validation, package inclusion, import status, regeneration audit.

Candidate columns:

- `contract`: a documented schema or command contract exists.
- `producer`: platform, route, or script writes the artifact.
- `validator`: deterministic validator exists.
- `readback`: browser/API can read the result.
- `account_scope`: data is account-scoped.
- `recovery_scope`: recovery source order is documented.
- `latest_evidence`: latest successful evidence path exists.
- `blocking_gap`: latest deterministic blocker.

Acceptance standard:

- A generated JSON readiness catalog exists under the Path Defaults readiness location, currently `logs/phase-a-innernet/readiness/`, or a documented stable equivalent evidence path.
- The catalog is produced by a script or service from existing artifacts, route profiles, tests, and database state; it is not hand-authored.
- Each green status references a validator, a timestamp, and an evidence path.
- Missing evidence produces `unknown` or `blocked`, never green.
- Account-scoped readback hides projects and artifacts from other accounts.
- A smoke test proves at least one positive row, one missing-evidence row, and one prototype-route row.

### B-AG-02: Asset-Centric Readback Index

Source pattern: AGF Asset-Centric View.

Adaptation:

Provide an asset-centric project readback index for generated, imported, and prototype-route projects. The goal is to let the platform group assets by runtime entity, scene, package role, prototype goal, and usage, without promising visual editing.

The index can group:

- Runtime assets under `Game.Godot` or hosted project `assets/`/`res://` paths.
- Generated image/model/audio files and sidecars.
- Scene references discovered from `.tscn`, `.tres`, `.cs`, or project-specific manifests.
- Prototype goal references and route acceptance markers that rely on the asset.
- Package inclusion status.
- Import diagnostics and missing-reference diagnostics.

Acceptance standard:

- The index is generated from files, route state, and existing manifests, not manually authored.
- Each indexed asset has path, type, size, hash, usage count, usage source, usage confidence, account/project id, route reference when applicable, and last validation status.
- Missing files, orphan files, duplicate hashes, failed imports, and references outside allowed roots are flagged deterministically.
- Browser/API readback can display the index without granting write access to the project files.
- Regeneration actions, if later added, must target explicit asset groups and must create before/after manifests plus rollback metadata.
- No acceptance criterion depends on a human deciding whether an asset looks good.

### B-AG-03: Sidecar Scene, Prototype, And Run Context Export

Source pattern: AGF schema-first and scene-context sidecars.

Adaptation:

Export sidecar context for platform readback, prototype-route recovery, and diagnostics only. Do not replace Godot scene files with an AGF-style JSON scene schema. Sidecars should describe what the platform can safely show, validate, and resume.

Candidate sidecars:

- `meta/scene-readback/latest.json`: scene list, main scene, referenced scripts, referenced assets, import status.
- `meta/prototype-route/latest.json`: selected type kit, selected capabilities, current goal, acceptance markers, stale-state guard, route profile id.
- `meta/run-context/latest.json`: command, environment profile, account/project ids, tool versions, start/end time, exit status, evidence paths.
- `meta/package-readback/latest.json`: package path, hash, size, included files, export profile, validation status.

Sidecar placement rule:

- Readback and route sidecars must live outside Godot runtime import paths or be explicitly excluded from package/export outputs. They are platform evidence, not shipped game content.

Acceptance standard:

- Sidecars are generated by scripts/services after real filesystem, route, and command execution.
- Sidecars contain no secret values, token material, or provider credentials.
- Validators fail closed when sidecars reference files outside the hosted workspace or allowed project roots.
- Browser/API readback uses sidecars for display and does not infer success from assistant text.
- A stale sidecar is marked stale when its source files, route session id, selected capabilities, or run id no longer match.

### B-GO-01: Machine-Closed Evidence Bundle

Source pattern: godogen frame-grounded verification and final proof bundle.

Adaptation:

Create a Phase B evidence bundle contract that captures objective runtime and prototype-route proof without requiring AI or human visual acceptance. The bundle is an audit, diagnostics, and route-acceptance artifact, not a subjective quality gate.

Candidate bundle layout:

```text
logs/phase-a-innernet/evidence/<project-id>/<run-id>/
  evidence.json
  command.log
  godot-import.log
  godot-runtime.log
  frames/
  capture.mp4
  assertions.json
  route-acceptance.json
  asset-index.json
  package-readback.json
```

Acceptance standard:

- `evidence.json` records schema version, producer version, validator version, project id, account id, run id, command id, route id when applicable, tool versions, start/end time, exit status, redaction status, sanitized readback scope, and evidence file hashes.
- Godot import/build/runtime logs are captured and scanned for deterministic fatal patterns.
- If frame capture is enabled, validators check dimensions, frame count, duration, nonblank pixel ratio, and expected file hashes where applicable.
- Console or script assertions are machine-readable and any `FAIL` blocks success.
- Prototype-route acceptance is represented by `route-acceptance.json`, including selected capabilities, required markers, observed markers, missing markers, and stale-state status.
- If capture is unavailable due to host limitations, the bundle records `capture_unavailable` with a deterministic reason and does not claim visual verification success.
- A Phase B smoke or integration test creates a fixture bundle and verifies readback, account scoping, stale detection, route marker classification, and failure classification.

### B-GO-02: Asset Budget And Manifest Contract

Source pattern: godogen asset planner and asset manifest.

Adaptation:

Introduce a provider-neutral asset manifest for generated, imported, or prototype-route assets. This does not require this repository to adopt godogen's Gemini/Grok/Tripo3D providers. The manifest records enough objective metadata for cost control, reuse, package inclusion, route acceptance, and diagnostics.

Candidate fields:

- `asset_id`, `project_id`, `account_id`, `route_id`, `goal_id`, `path`, `kind`, `role`, `source`, `provider`, `prompt_ref`, `cost_units`, `size_hint`, `runtime_scale_hint`, `hash`, `created_at`, `validated_at`, `validation_status`.
- Optional relationship fields: `anchor_asset_id`, `derived_from`, `variant_group`, `regeneration_group`, `required_by_capability`.

Acceptance standard:

- Manifest validation fails when runtime assets lack paths, hashes, type, or project/account ownership.
- If a cost or budget value is present, total project cost can be computed deterministically.
- If `size_hint` or `runtime_scale_hint` is present, it is parsed into a normalized value and exposed in readback.
- Generated package readback can prove whether each runtime asset was included or excluded.
- Prototype-route acceptance can reference manifest assets by id instead of fragile prompt text.
- Regeneration or replacement updates the manifest with a new hash and preserves prior evidence for audit.
- The system never marks visual quality as accepted from prompt text alone.

### B-GO-03: Godot C# Diagnostics Knowledge Base

Source pattern: godogen `quirks.md`.

Adaptation:

Curate recurring Godot C# failure modes into machine-checkable diagnostic rules where possible, and into documented repair hints where not possible. Route-specific diagnostics should attach findings to the current prototype goal when possible.

Project-local propagation model:

- Platform bootstrap owns the curated generic Godot/C# pitfalls source. When a new hosted project is created, Phase A copies the current generic source into the project as the project-local engineering memory seed.
- Project routes may update `docs/prototype/MEMORY.md` when module execution, lightweight validation, needs-fix repair, or asset replacement produces a stable engineering lesson. These updates are project-local constraints, not global route rules by default.
- Every automatic `MEMORY.md` update must also append a sanitized candidate entry to the default system-level temporary collection area, `logs/phase-a-innernet/prototype-memory-candidates/`, for administrator review. Candidate entries must not contain secrets or raw user credentials.
- Candidate records should use a JSONL-friendly minimum schema: `candidate_id`, `created_at`, `project_id`, `route_run_id`, `source_module`, `source_path`, `before_summary`, `after_summary`, `proposed_rule_text`, `severity_suggestion`, `evidence_refs`, `promotion_status`, and optional `admin_notes`.
- Administrators periodically curate the temporary collection and promote durable, generic lessons into the platform-level Godot/C# pitfalls source. Promotion must remove project-specific design choices and keep only broadly valid Godot/C# or route-safety constraints.

Initial candidate rules:

- Wrong C# SceneTree script signatures.
- Missing or stale Godot import after asset changes.
- `.gdignore` under runtime asset folders.
- References outside `res://` or `user://` boundaries.
- Missing main scene or missing package output.
- Prototype acceptance marker missing from scene, script, test output, or route state.
- Collision layer bitmask mistakes when detectable from project config and scene files.
- Known fatal log patterns from Godot import/build/runtime.

Acceptance standard:

- Diagnostic rules have ids, severity, match source, repair hint, false-positive notes, and optional route capability mapping. Severity must use a bounded enum: `P0`, `P1`, `P2`, or `info`. P0/P1 findings may block readiness; P2/info findings may be advisory unless a route-specific validator upgrades them.
- A deterministic script or service emits diagnostic findings as JSON.
- Findings are linked into evidence bundles, project readback, and route recovery when applicable.
- New project creation seeds project-local `docs/prototype/MEMORY.md` from the platform generic Godot/C# pitfalls source without making the project copy authoritative for other projects.
- Route-written `MEMORY.md` updates also write sanitized promotion candidates to `logs/phase-a-innernet/prototype-memory-candidates/` using the minimum candidate schema above.
- Administrator promotion from the temporary area to the platform generic pitfalls source is auditable, records `promotion_status`, and never happens automatically from a single project.
- At least one test fixture proves each P0/P1 rule can detect a known bad state.
- Documentation-only hints are allowed but cannot be counted as closed capabilities.

### B-GO-04: Toolchain And Capture Capability Probe

Source pattern: godogen capture setup and toolchain check.

Adaptation:

Before running hosted project validation or prototype-route execution, collect a Windows-specific capability probe for Godot, .NET, export templates, display/capture availability, ffmpeg availability, configured paths, and known host blockers.

Acceptance standard:

- Probe output is JSON and includes Godot version, .NET version, configured Godot path, export template availability, capture support, ffmpeg availability, and known blockers. Capture gates default to disabled unless the probe reports stable capture support; capture artifacts may still be collected best-effort without blocking build, package, or prototype-route validation.
- Hosted routes and evidence bundles reference the probe id used for the run.
- Missing optional capture tools disable capture with a deterministic reason; they do not fail unrelated build/package/prototype validations.
- Missing required Godot/.NET tools block the run before spending LLM or Codex execution budget.
- Probe results are account-safe and contain no secrets.

### B-PT-01: Type Kit Expansion Contract

Source pattern: AGF capability matrix plus this repository's game-type route framework and godogen staged execution discipline.

Adaptation:

Define a stable contract for adding or upgrading a prototype type kit. The contract should make type-kit expansion machine-reviewable before implementation work begins.

Required sections:

- `game_type_id` and `profile_id`.
- Always-on capabilities.
- Conditional capabilities and activation sources.
- Negative semantics that prevent accidental capability activation.
- First-goal boundary.
- Goal-to-acceptance marker map.
- Required scenes, scripts, tests, assets, and evidence markers.
- Recovery inputs and authority order.
- Stale-state rules.

Acceptance standard:

- A validator can parse the type kit contract sidecar or generated JSON artifact and reject missing required sections.
- Conditional capabilities cannot be activated by generic taxonomy words alone.
- Each capability maps to at least one deterministic acceptance marker.
- Each marker declares where evidence may come from: file, scene, test output, route state, package, or manifest.
- At least one negative test proves a template example or stale summary cannot activate an unrequested capability.
- The type kit contract sidecar is linked from the readiness catalog before the type can be marked executable.

### B-PT-02: Prototype Route Execution Ledger

Source pattern: godogen PLAN/STRUCTURE/MEMORY discipline and AGF disk-contract principle.

Adaptation:

Add a route execution ledger that records each prototype route step as structured data instead of relying on assistant summaries. This ledger complements existing route state and repair ledgers.

Candidate fields:

- `ledger_entry_id`, `previous_entry_id`, `correlation_id`, `causation_id`, `route_id`, `profile_id`, `session_id`, `goal_id`, `capability_ids`, `started_at`, `completed_at`, `status`, `inputs`, `commands`, `changed_files`, `evidence_bundle`, `diagnostics`, `next_recovery_source`.

Acceptance standard:

- Each route step writes a `started` or `running` ledger entry before execution and a `passed`, `failed`, `blocked`, or `stale` ledger entry after execution. The after-entry must reference the before-entry through `previous_entry_id` or `causation_id`.
- A completed step must reference evidence and acceptance markers.
- A failed step must reference deterministic diagnostics or missing evidence.
- Resume logic can select the next action from the ledger without reading assistant prose.
- Account-scoped readback hides ledger entries from other accounts.

### B-PT-03: Prototype Visual Evidence Without Subjective Judgement

Source pattern: godogen visual target and capture loop.

Adaptation:

Allow prototype routes to produce visual evidence, but keep final acceptance objective. A visual target or screenshot can guide implementation and support user review, but it cannot be the only pass condition.

Allowed objective checks:

- Frame files exist and match expected dimensions.
- Frames satisfy bounded objective checks such as nonblank pixel ratio, frame count, frame delta when motion is required, and expected resolution.
- Expected machine-readable assertion markers appear in logs or assertion artifacts. HUD text counts only if a declared OCR, pixel, or engine-side text-extraction validator exists.
- Capture duration and frame count match the route goal.
- Required scenes and scripts are loaded without fatal errors.

Acceptance standard:

- Visual evidence is linked from `route-acceptance.json` and the evidence bundle.
- A route cannot pass only because a prompt says the screenshot looks correct.
- When visual evidence is unavailable, the route records the blocker and falls back only to nonvisual deterministic markers that are declared in the type kit.
- User-facing preview remains a review aid, not the acceptance authority.

## Conflict Resolution

| Source Idea | Conflict | Resolution |
| --- | --- | --- |
| AGF browser drag-edit | Requires browser-side visual editing of engine-owned scene concepts. This repository is Windows-only Godot C# and should not overpromise browser scene editing. | Exclude broad browser editing. Browser sidecars may propose, annotate, or request changes only. Any actual scene write must execute through a Godot-native tool, plugin, or validated repository script, then pass deterministic verification. |
| AGF schema-first scene model | Could replace Godot scene files with an intermediate schema. | Use sidecars for readback, route recovery, and validation only. Godot project files remain authoritative. |
| AGF genre capability matrix | Could duplicate BMAD/GDS 24 game-type templates. | Convert to platform and prototype-route readiness catalog. Do not create another taxonomy. |
| godogen visual self-repair | Often relies on AI or human visual judgement. | Keep capture artifacts; acceptance is only objective checks, assertions, and route markers. |
| godogen asset quality planning | May require subjective quality approval. | Absorb manifest, budget, size, hash, import, route reference, and package checks; exclude subjective art approval. |
| godogen multi-engine publishing | Conflicts with Windows-only Godot C# premise. | Exclude. Keep only Godot C# operational and prototype-route patterns. |
| Prototype route expansion | Can become unsafe if taxonomy examples activate runtime systems by accident. | Include it only through type-kit contracts, selected capabilities, route guards, stale-state checks, and deterministic acceptance markers. |

## Implementation Backlog Index

The implementation backlog for this plan is tracked in `docs/workflows/phase-b-agf-godogen-implementation-backlog.md`. The backlog converts the P0/P1/P2 capability order below into task-sized implementation slices with outputs and acceptance standards.

## Implementation Order

### P0

1. Define security/redaction metadata, sanitized-readback rules, and redaction validator fixtures for evidence, logs, prompts, and provider metadata.
2. Define the evidence bundle JSON schema and validator.
3. Define the route ledger schema before any route-ledger readback.
4. Define `route-acceptance.json` for selected capabilities, markers, stale-state status, and missing evidence.
5. Define the toolchain/capture capability probe.
6. Define deterministic Godot C# diagnostic output schema.
7. Add account-scoped evidence bundle and route ledger readback only after sanitized summaries exist.

### P1

1. Define and validate the type kit expansion contract.
2. Generate asset-centric readback index.
3. Generate scene, prototype-route, and package readback sidecars.
4. Add asset manifest validation and package inclusion checks.
5. Add readiness catalog derived from existing evidence, profiles, validators, and tests.

### P2

1. Add optional frame capture validation for dimensions, duration, frame count, nonblank ratio, and frame-change checks.
2. Add regeneration-group audit records for asset replacement.
3. Expand diagnostics with more Godot C# known-failure rules.
4. Add browser presentation for readiness, route ledger, and asset readback once the JSON contracts are stable.

## Definition Of Done

This Phase B absorption is complete when:

- Every implemented capability has a machine-readable contract.
- Every green status is derived from a validator and evidence path.
- Account scoping is tested for evidence, assets, packages, readiness, route ledgers, and prototype readback.
- Redaction validator fixtures pass before any browser/API evidence readback is considered complete.
- Stale, missing, and failed evidence states are represented explicitly.
- Prototype route support is represented through type kits, selected capabilities, route guards, acceptance markers, and tests.
- No acceptance criterion depends on AI self-judgement or final human approval.
- README links this document as a Phase B platform evolution source.

## Implementation Defaults

- Deterministic validators should start in `scripts/python/` so they can run in CI, local recovery, and hosted routes without coupling validation rules to the web service. PhaseA.Platform may call those validators or read their JSON outputs. Move validation into PhaseA.Platform only when low-latency API behavior requires it and tests preserve CLI parity.
- Readiness catalogs should refresh after each completed run. On-demand generation is allowed as a rebuild or repair path, not the primary freshness mechanism.
- Asset manifests should use sidecars as the SSoT. SQLite may store readback summaries or cache projections for browser performance.
- Route ledgers should use sidecars as the SSoT. SQLite may store pagination/index projections for browser performance.

## Open Decisions

No blocking open decisions remain for this draft. Future implementation plans may reopen storage, refresh, or API placement decisions if measured performance or security evidence requires it.
