# Audit, Evidence, And Logs Architecture

## Intent

Audit, evidence, and logs make Phase service behavior recoverable, reviewable, and safe for account-scoped readback. They are product features and operational safeguards, but they can also leak secrets if exposed without scope and redaction rules.

## Boundary

In scope:

- Runtime logs under `logs/phase-a-innernet/runtime/`.
- Run rows and artifacts in the metadata DB.
- Account action audit events.
- LLM usage and LLM run audit summaries.
- Prototype evidence, route state, repair ledgers, package readback, asset inventories, preview manifests, and project-health artifacts.
- Phase B/C readiness, capability, and evidence bundle concepts when produced from source-linked validators.

Out of scope:

- Manually edited green status as acceptance authority.
- Raw command environments or raw prompt bodies as default browser/API readback.
- Rewriting generated evidence to hide failed runs.

## Key Decisions

- Evidence must be derived from scripts, validators, logs, database rows, imported assets, package outputs, route state, tests, or stable diagnostics.
- Screenshots and rendered frames are useful evidence, but they are not sufficient acceptance unless objective properties are validated.
- Readback should expose logical artifact IDs or sanitized workspace-relative paths, not raw host paths.
- Admin readback can aggregate, but raw cross-account evidence blobs require a later explicit security decision.
- Phase B/C readiness catalogs and evidence bundles must be generated, not hand-authored.

## Invariants

- Token material, provider keys, bearer tokens, and secret values must be absent from logs intended for readback.
- Account-scoped readback must hide other accounts' artifacts, packages, assets, runs, and projects.
- Evidence must carry enough context to diagnose producer, project, account, run, route, status, and path ownership.
- Failure evidence is preserved; new evidence is added as sidecars.

## Change Rules

- New evidence types must define raw path, sanitized path, readback scope, redaction status, and producer.
- New admin readback must define whether it exposes aggregate summaries or raw items.
- New acceptance/readiness state must be backed by validators and bounded status enums.
- New telemetry events must keep stable names and avoid raw private project content.

## Related Code And Docs

- `PhaseA.Platform/Readback/**`
- `PhaseA.Platform/Data/PhaseAMetadataStore.cs`
- `docs/workflows/phase-b-agf-godogen-absorption.md`
- `docs/workflows/cloud-user-telemetry-and-feedback-plan.md`
- `docs/workflows/phase-c-platform-hardening-and-agent-asset-governance.md`
