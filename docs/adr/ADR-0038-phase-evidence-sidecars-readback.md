# ADR-0038: Evidence Sidecars And Account-Scoped Readback

- Status: Accepted
- Date: 2026-06-28

## Context

Phase users and agents need to inspect workflow status, failures, assets, packages, previews, route state, audit, and LLM usage through the browser/API. Raw logs and command outputs can contain host paths, prompts, provider keys, tokens, and private project content.

Manual green status also creates a false source of truth.

## Decision

Use generated sidecars, database rows, artifacts, logs, and sanitized readback as evidence surfaces.

- Evidence must be derived from scripts, validators, logs, database rows, imported assets, package outputs, route state, tests, or stable diagnostics.
- Readback must be account-scoped unless explicitly admin-only.
- Browser/API readback exposes logical artifact IDs, tickets, summaries, or sanitized workspace-relative paths rather than raw host paths.
- New readiness or acceptance status must use bounded status enums and evidence references.
- Phase B browser/API evidence readback, indexes, and catalogs must not expose new raw evidence until B0-01 Redaction Schema And Rules and B0-02 Redaction Fixture Validator pass.
- Evidence bundles must have B0-03 Evidence Bundle Schema And Validator before any readiness catalog or route status marks a route green from that bundle.
- Failure evidence is preserved; new sidecar evidence is added rather than rewriting generated history.
- Prompt-producing route sidecars use the shared hosted-route recovery contract, structured source-hash evidence, and workspace-bound prompt manifests. Validators recompute or resolve authoritative source hashes instead of trusting two matching self-declarations.
- Raw prompt artifacts are internal-recovery-only and are excluded from browser/account artifact listing and direct readback. Browser-readable prompt evidence contains manifests and hashes only.
- Persisted/exported evidence, decision metadata, diagnostics, and LLM telemetry are redacted before write; project-local queue sidecars are atomic projections of the latest DB snapshot.

## Consequences

- Users can inspect platform state without filesystem access.
- Evidence becomes a product feature and an operational safety mechanism.
- Redaction and account scoping are mandatory for new readback surfaces.
- Screenshots and videos are useful artifacts, but not acceptance by themselves unless objective properties are validated.
- Source-boundary evidence fails closed on missing fields, wrong JSON types, reparse-point escapes, stale hashes, or raw-prompt exposure.

## References

- `docs/architecture/phase-service/audit-evidence-and-logs.md`
- `docs/workflows/phase-b-agf-godogen-absorption.md`
- `docs/workflows/phase-b-agf-godogen-implementation-backlog.md`
- `docs/workflows/cloud-user-telemetry-and-feedback-plan.md`
- `PhaseA.Platform/Readback/**`
