# Godot UI Style Schema Acceptance Standard

Status: Living standard
Language: English
Scope: Deterministic acceptance for Godot UI style snapshot schema fields, hash identity, token/resource resolution, custom-style equivalence, gesture/state/lifecycle/virtualization rows, visual evidence, and capability inventory parity.

## Purpose

This standard owns acceptance rules for the style snapshot schema profile defined by `docs/standards/godot-ui-style-contract.md` and `docs/schemas/godot-ui-style-contract.v1.example.json`.

Stable capability ID: `ui_style_schema_acceptance_gate`.

## Machine-Readable Acceptance

The schema profile and acceptance metadata live in `PhaseA.Platform/Workflow/GodotUiStyleSnapshotSchema.cs`.
The deterministic test owner is `PhaseA.Platform.Tests/Workflow/GodotUiStyleSnapshotSchemaTests.cs`.

The acceptance profile owns:

- Required fields and active-array cardinality.
- Enum-like allowed values.
- Capability inventory parity across 06a, 06b, 06c, 06d, and 07 capability IDs.
- Hash identity fields and documented volatile exclusions.
- Custom style required metadata.
- Public alias approval metadata.
- Theme resource validation/readback fields.
- Deterministic visual substitute limitation metadata.

Pipe-delimited enum strings in the fixture are documentation shorthand. Validators consume enum sets from the machine-readable profile.

## Acceptance Rules

- Schema fields use English stable snake_case artifact names. Browser/API projections may use camelCase under Phase standards.
- Required fields, enum-like values, minimum active-array cardinality, stable capability IDs, and optional-empty-array distinctions must exist in the machine-readable profile.
- `runtime_environment.participates_in_hash_identity` is true for active snapshots unless a future decision log records otherwise.
- Runtime environment must freeze Godot version, renderer, export target, platform class, viewport set, display scale, DPI, theme scale, font oversampling, locale policy, text direction policy, and font rendering notes before UI execution.
- `ui_style_id` must be a repo-owned stable ID or `custom`. Source skill names may appear only in source inspiration or approved alias metadata.
- Custom styles require owner, version, source hash, artifact ref, created UTC, and readback path policy.
- Public aliases require alias, approval ref, reviewer owner, approved UTC, decision log ref, and validation status.
- Theme resources require resource ref/type, owner, token source, theme slot mappings, load validation, export/package validation, deterministic diff evidence, packaging evidence, and safe readback policy.
- Deterministic visual substitutes require limitation type, owner, approver, approval timestamp, expiry or recheck trigger, replacement evidence plan, and `cannot_substitute_for`.
- Capability packages must include every stable capability ID declared by 06a, 06b, 06c, 06d, and the diagnostic capability IDs already represented in the fixture. Duplicate, orphan, or ownerless IDs are invalid.

## Validation

Minimum deterministic validation:

```powershell
dotnet test PhaseA.Platform.Tests --filter FullyQualifiedName~GodotUiStyleSnapshotSchemaTests
```
