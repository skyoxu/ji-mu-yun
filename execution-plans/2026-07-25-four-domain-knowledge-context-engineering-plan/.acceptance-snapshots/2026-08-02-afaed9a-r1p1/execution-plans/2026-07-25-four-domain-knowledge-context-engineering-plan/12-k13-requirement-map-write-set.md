# K13 Requirement Map Enforce Write-Set

Status: prepared for the next authorized K13 mutation-capable caller.

Authority: ADR-0044 and ADR-0046. This write set follows the completed
read-only K13 batch. It grants no E2 release and does not authorize any
unrelated run, prototype, Codex, runtime, or live-state change.

## Target

- Operation: `llm:gdd-requirement-map`.
- Route: `POST /api/projects/{projectId}/gdd/requirements-map`.
- Caller: `PhaseA.Platform/Runs/GameDesignRequirementMapService.cs`.
- Existing behavior: read server-owned project identity and current GDD/scene
  artifacts, obtain a structured LLM result or deterministic fallback, then
  persist the requirement-map, redacted prompt evidence, and database binding.

## Allowed Changes

- Add a server-owned `HostedContextManifestIssuer` dependency and issue an
  envelope after source recovery/forbidden-source validation but before LLM
  dispatch.
- Bind account, project, operation, a deterministic current source snapshot,
  policy revision, signature key id, signature, nonce, and bounded expiry.
- Send the envelope and `OperationKey` through `ILlmRouteEngine`.
- Add the server-only policy override and focused tests proving envelope
  identity and conservative fallback.

## Failure And Rollback Contract

- Missing or failed issuance must not dispatch the LLM.
- It must enter the existing deterministic `needs_review` requirements path
  with the stable `context_manifest_issue_failed` marker; normal evidence and
  database bindings may still be written because they are the established
  recovery representation of an unavailable LLM.
- Rollback removes only the server policy override and the caller's envelope
  issuance/transport fields, restoring the previous observe behavior. It must
  not delete existing project artifacts, run history, manifests, or nonce
  records.

## Exclusions

- No live metadata DB mutation, Hosted workspace access, service restart,
  Caddy change, Browser route shape change, or release-evidence assertion.
- No Codex executable/workspace-write caller migration.

## Required Evidence

- A focused test captures the request envelope and proves account/project/
  operation binding.
- A focused test proves issuance failure produces the deterministic fallback
  and makes no LLM call.
- Rebuild inventory and migration ledger, run E2 readiness, run the caller,
  manifest, and shared-entrypoint tests, terminal whole-directory validation,
  and `git diff --check`.
