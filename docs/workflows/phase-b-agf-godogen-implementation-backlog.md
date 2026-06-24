# Phase B AGF And godogen Implementation Backlog

Status: Draft
Date: 2026-06-24
Source plan: `docs/workflows/phase-b-agf-godogen-absorption.md`
Scope: Implementation backlog for machine-closed AGF/godogen absorption in Phase B.

## Backlog Rules

- Keep deterministic validators in `scripts/python/` first unless an implementation story proves that PhaseA.Platform must own the rule for low-latency API behavior.
- Keep sidecars as the SSoT for asset manifests and route ledgers. SQLite may store readback summaries, cache projections, or pagination indexes.
- Browser/API readback must use sanitized summaries by default.
- No task may rely on AI self-judgement or final human approval as acceptance evidence.
- No task may introduce browser drag-editing for Godot scene concepts.

## Global Definition Of Done

The backlog is complete only when:

- Every implemented validator has unit or fixture tests.
- `git diff --check` passes.
- Redaction fixture validation passes before any browser/API evidence readback is exposed.
- New contract documents or generated schemas are linked from the source plan or workflow index when they become durable docs.
- New task-facing scripts are added to the stable/script entrypoint index or explicitly documented as internal helper scripts.
- Browser/API readback uses sanitized summaries and account-scoped authorization.
- Sidecar SSoTs remain the authoritative storage for asset manifests and route ledgers; SQLite stores projections only.
- No task introduces browser drag-editing for Godot scene concepts.

## Cross-Task Gates

- P1 browser/API readback, index, and catalog tasks must not expose data until B0-01 and B0-02 are complete.
- B1-05 readiness catalog must not mark prototype routes green until B0-03, B0-04, B0-05, and B1-01 are complete for that route.
- B2 browser presentation tasks must consume sanitized summaries only.

## Execution Metadata

When converting this backlog into stories, add `Owner surface`, `Expected test command`, and `Estimated size` to each story. They are intentionally omitted here to keep this backlog focused on sequencing and acceptance.

## P0 Tasks

### B0-01 Redaction Schema And Rules

Depends on: none.

Objective: Define the shared redaction metadata and sanitized-readback rules for evidence, logs, prompts, provider metadata, command lines, environment blocks, stdout/stderr, and host paths.

Primary outputs:

- `docs/workflows/phase-b-agf-godogen-redaction-contract.md`
- JSON schema for redaction metadata or an equivalent documented schema block.
- Source-plan or workflow-index link updates when the contract becomes durable.

Acceptance:

- Schema includes `redaction_status`, `raw_evidence_path`, `sanitized_evidence_path`, `readback_scope`, `retention_policy`, and `expires_at_utc`.
- Browser/API readback exposes logical artifact ids or workspace-relative sanitized paths only.
- Raw absolute Windows paths remain server-side.

### B0-02 Redaction Fixture Validator

Depends on: B0-01.

Objective: Implement a deterministic validator with fixtures for fake bearer tokens, fake provider keys, raw prompt bodies, stdout/stderr samples, command lines, environment blocks, and absolute host paths.

Primary outputs:

- `scripts/python/validate_phase_b_redaction.py`
- `scripts/python/tests/test_phase_b_redaction.py`
- Fixture files under `scripts/python/tests/fixtures/phase_b_redaction/`

Acceptance:

- Validator fails when raw secrets, prompt bodies, or absolute host paths appear in sanitized readback.
- Validator passes sanitized fixture outputs.
- Validator fails the local hard check or review-pipeline stage when sanitized output leaks forbidden patterns. The exact CI hook may be added later, but local failure must exist before browser/API exposure.
- Test output can be referenced by evidence bundle smoke tests.

### B0-03 Evidence Bundle Schema And Validator

Depends on: B0-01, B0-02.

Objective: Define and validate the Phase B evidence bundle shape.

Primary outputs:

- `scripts/python/validate_phase_b_evidence_bundle.py`
- Evidence schema documentation in the absorption plan or a dedicated contract file.

Acceptance:

- `evidence.json` includes schema version, producer version, validator version, project/account/run ids, route id when applicable, tool versions, redaction status, sanitized readback scope, evidence file hashes, and retention fields.
- Missing required fields fail validation.
- Invalid evidence references outside allowed roots fail validation.

### B0-04 Route Ledger Schema Before Readback

Depends on: B0-01, B0-02.

Objective: Define route ledger sidecar schema before implementing any route-ledger readback UI/API.

Primary outputs:

- Route ledger schema document or JSON schema.
- Default sidecar path: `meta/route-ledger/latest.json`.
- `scripts/python/validate_phase_b_route_ledger.py`

Acceptance:

- Ledger supports `ledger_entry_id`, `previous_entry_id`, `correlation_id`, `causation_id`, route/profile/session/goal ids, capabilities, status, inputs, commands, changed files, evidence bundle, diagnostics, and next recovery source.
- A `passed`, `failed`, `blocked`, or `stale` entry references its prior `started` or `running` entry.
- Resume fixtures can select the next action without assistant prose.

### B0-05 Route Acceptance Sidecar

Depends on: B0-04 and existing `PrototypeGoalAcceptanceContract` / `PrototypeGoalAcceptanceValidator` behavior.

Objective: Define `route-acceptance.json` for selected capabilities, required markers, observed markers, missing markers, and stale-state status.

Primary outputs:

- `scripts/python/validate_phase_b_route_acceptance.py`
- Route acceptance schema documentation.

Acceptance:

- Sidecar derives from existing `PrototypeGoalAcceptanceContract` / `PrototypeGoalAcceptanceValidator` concepts instead of redefining route semantics.
- Missing required markers fail validation.
- Stale session/capability mismatch is represented explicitly.

### B0-06 Toolchain And Capture Probe

Depends on: none.

Objective: Define a Windows-specific capability probe for Godot, .NET, export templates, capture support, ffmpeg availability, configured paths, and host blockers.

Primary outputs:

- `scripts/python/phase_b_toolchain_probe.py`
- Default output path: `logs/phase-a-innernet/toolchain-probe/latest.json` or the run-scoped evidence bundle.
- Fixture or unit tests for stable and unstable capture cases.

Acceptance:

- Probe emits JSON with bounded status values.
- Capture gates default to disabled unless the probe reports stable capture support.
- Missing required Godot/.NET tools block before LLM/Codex execution budget is spent.

### B0-07 Godot C# Diagnostics Schema

Depends on: B0-03.

Objective: Define the diagnostic finding schema and initial severity rules for Godot C# failure modes.

Primary outputs:

- `scripts/python/godot_csharp_diagnostics.py`.
- Default rule source: `scripts/python/godot_csharp_diagnostics_rules.json`.
- Tests for initial P0/P1 diagnostic rules.
- Rule JSON schema validation before diagnostic execution.

Acceptance:

- Rule JSON schema validation fails before diagnostic execution when required fields are missing.
- Severity enum is `P0`, `P1`, `P2`, or `info`.
- P0/P1 findings can block readiness.
- Findings link to evidence bundle, project readback, and route recovery where applicable.

### B0-08 Project-Local Godot C# Pitfalls Propagation

Depends on: B0-07.

Objective: Seed each hosted project with the platform generic Godot/C# pitfalls source, capture project-local `MEMORY.md` updates as promotion candidates, and keep administrator curation as the only path back into the platform generic source.

Primary outputs:

- Platform generic pitfalls source path and schema or documented format.
- Project creation hook that seeds `docs/prototype/MEMORY.md` or a project-local pitfalls section from the platform source.
- System-level temporary candidate area for sanitized project-originated `MEMORY.md` updates. Default path: `logs/phase-a-innernet/prototype-memory-candidates/`.
- Candidate JSONL minimum schema: `candidate_id`, `created_at`, `project_id`, `route_run_id`, `source_module`, `source_path`, `before_summary`, `after_summary`, `proposed_rule_text`, `severity_suggestion`, `evidence_refs`, `promotion_status`, and optional `admin_notes`.
- Admin curation workflow or checklist for promoting candidates into the platform generic source.

Acceptance:

- New project creation copies the current platform generic Godot/C# pitfalls content into project-local engineering memory.
- Module execution, needs-fix repair, lightweight validation, and asset replacement routes can append stable lessons to `docs/prototype/MEMORY.md` without rewriting unrelated memory.
- Each route-written memory update also writes a sanitized candidate record to `logs/phase-a-innernet/prototype-memory-candidates/` with project, run, module, source path, summary, proposed rule, severity, evidence, and promotion status fields.
- Candidate records are not promoted automatically. Admin review is required before updating the platform generic source, and the candidate `promotion_status` records the decision.
- Promotion strips project-specific gameplay choices and preserves only generic Godot/C# or route-safety constraints.

## P1 Tasks

### B1-01 Type Kit Contract Sidecar Validator

Depends on: B0-04, B0-05.

Objective: Validate `docs/prototype-type-kits/<type>.contract.json` as the machine SSoT for executable prototype type-kit readiness.

Primary outputs:

- `scripts/python/validate_type_kit_contract.py`
- Tests for valid, missing-field, stale, and Markdown/JSON mismatch cases.

Acceptance:

- Contract includes game type id, profile id, always-on capabilities, conditional capabilities, first-goal boundary, acceptance markers, recovery inputs, authority order, and stale-state rules.
- Markdown/contract mismatch fails closed.
- Type cannot be marked executable in readiness catalog without a passing contract sidecar.

### B1-02 Asset-Centric Readback Index

Depends on: B0-01, B0-02, B0-03.

Objective: Generate an asset-centric readback index for generated, imported, and prototype-route projects.

Primary outputs:

- `scripts/python/generate_phase_b_asset_index.py`
- `asset-index.json` schema or documented schema block.

Acceptance:

- Indexed assets include path, type, size, hash, usage count, usage source, usage confidence, account/project id, route reference when applicable, and validation status.
- Missing files, orphan files, duplicate hashes, failed imports, and references outside allowed roots are flagged.
- Fixtures cover strong and weak usage sources across `.cs`, `.tscn`, `.tres`, manifest, and route-state references.
- Browser/API readback does not grant write access.

### B1-03 Readback Sidecars

Depends on: B0-01, B0-02, B0-03, B0-04, B0-05. Run-context tool/probe fields depend on B0-06; before B0-06 they must be absent or `unknown`, never green.

Objective: Generate scene, prototype-route, run-context, and package readback sidecars.

Primary outputs:

- `meta/scene-readback/latest.json`
- `meta/prototype-route/latest.json`
- `meta/run-context/latest.json`
- `meta/package-readback/latest.json`

Acceptance:

- Sidecars live outside Godot runtime import paths or are explicitly excluded from package/export outputs.
- Sidecars contain no secrets.
- Stale sidecars are marked stale when source hashes, route session id, selected capabilities, or run id no longer match.

### B1-04 Asset Manifest Validation

Depends on: B0-01, B0-02, B0-03.

Objective: Validate provider-neutral asset manifests for generated, imported, or prototype-route assets.

Primary outputs:

- `scripts/python/validate_phase_b_asset_manifest.py`
- Asset manifest schema documentation.

Acceptance:

- Runtime assets require path, hash, type, project/account ownership, and validation status.
- Cost and budget totals are computable when present.
- Package readback can prove asset inclusion or exclusion.

### B1-05 Readiness Catalog Generator

Depends on: B0-03, B0-04, B0-05, B0-07, B1-01. Asset readiness rows can only go green after B1-02 and B1-04.

Objective: Generate readiness catalog rows from evidence, profiles, validators, and tests.

Primary outputs:

- `scripts/python/generate_phase_b_readiness_catalog.py`
- Readiness output under `logs/phase-a-innernet/readiness/`

Acceptance:

- Green status requires validator id, timestamp, and evidence path.
- Missing evidence produces `unknown` or `blocked`, never green.
- Catalog refreshes after each completed run; on-demand rebuild is supported as repair.

## P2 Tasks

### B2-01 Optional Frame Capture Validator

Depends on: B0-03, B0-06.

Objective: Add optional frame validation for dimensions, duration, frame count, nonblank ratio, and frame-change checks.

Primary outputs:

- `scripts/python/validate_phase_b_frame_capture.py`
- Frame capture fixture tests.

Acceptance:

- Validator runs only when the toolchain probe reports stable capture support.
- Capture artifact failures do not block build/package/prototype validation unless a route-specific contract declares capture as required.

### B2-02 Asset Regeneration Audit

Depends on: B1-02, B1-04.

Objective: Add regeneration-group audit records for asset replacement.

Primary outputs:

- Regeneration audit schema or documented schema block.
- Fixture tests for before/after hash and rollback metadata.

Acceptance:

- Replacement preserves before/after hashes and rollback metadata.
- Regeneration audit links to asset manifest and evidence bundle.

### B2-03 Expanded Godot C# Diagnostics

Depends on: B0-07.

Objective: Expand diagnostics beyond the initial P0/P1 rules.

Primary outputs:

- Updated `scripts/python/godot_csharp_diagnostics_rules.json`.
- Additional diagnostic fixture tests.

Acceptance:

- New rules include fixture tests and false-positive notes.
- Admin-promoted temporary candidates can be converted into diagnostics only after they gain rule ids, false-positive notes, fixture tests, and severity.
- Advisory P2/info rules do not block readiness unless explicitly upgraded by a route contract.

### B2-04 Browser Presentation

Depends on: B0-01, B0-02, B0-04, B1-02, B1-03, B1-05.

Objective: Add browser presentation for readiness, route ledger, and asset readback after JSON contracts stabilize.

Primary outputs:

- Browser/API readback views or endpoint contracts for sanitized readiness, route ledger, and asset index summaries.
- Account-scope tests for each exposed readback surface.

Acceptance:

- Browser reads sanitized summaries only.
- Browser controls do not write Godot scene concepts directly.
- Account scoping is tested.
