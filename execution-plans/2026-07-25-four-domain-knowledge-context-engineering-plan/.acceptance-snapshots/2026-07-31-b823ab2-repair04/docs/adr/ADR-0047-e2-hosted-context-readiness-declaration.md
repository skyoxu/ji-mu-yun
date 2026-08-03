# ADR-0047: E2 Hosted Context Readiness Declaration

- Status: Accepted
- Date: 2026-07-26
- Decision scope: Current K13 E2 readiness evidence declaration

## Context

ADR-0044 defines the E2 envelope and ADR-0046 permits the narrow K11-K13
integration while deliberately withholding a production deployment decision.
The current source-derived inventory records every reachable Hosted caller as
enforced through the ADR-0037 shared entrypoints. The signed-manifest
lifecycle, nonce consumption, key rotation, shared entrypoints, route callers,
and complete platform test suite have current local evidence. The plan's
mechanical readiness check needs a formal decision that distinguishes this
evidence declaration from an operational deployment.

## Decision

The maintainer authorizes a current E2 readiness declaration for the K13
integration only when all of the following remain true:

- The current source snapshot has zero direct Hosted LLM/Codex invocation
  violations, zero unknown reachable callers, and every reachable caller is
  server-policy `enforce`.
- Current validation proves signing, retained-key verification, tamper and
  expiry rejection, exact manifest persistence, atomic nonce consumption,
  shared LLM/Codex entrypoint validation, and route-caller regression paths.
- The declaration records the current source snapshot, validation commands,
  and the server-controlled rollback fact: removing an operation from the
  enforce policy revokes readiness on the next mechanical evaluation.
- The declaration is invalidated by source snapshot drift, a gate rollback,
  invalidated tests, a direct invocation, unknown reachability, or a
  non-enforced reachable caller.

This decision authorizes only the repository and plan-local declaration in
`e2-release-evidence.v1.json`. It does not authorize a service restart,
runtime configuration change, Caddy/public deployment change, live metadata
DB mutation, Hosted workspace mutation, or a claim that an already-running
service has loaded the new policy.

## Relationships

This ADR extends ADR-0044 for readiness evidence, complements ADR-0037 and
ADR-0038, and narrows the production-release exclusion in ADR-0046 only for
the non-operational readiness declaration above. It does not supersede any of
those ADRs or the paused 2026-07-11 frontend-boundary plan.

## Consequences

- `tools/check_e2_readiness.py` may report `ready=true` only while the
  snapshot-bound release evidence is current.
- An operational production rollout still requires its own runtime/deployment
  decision and must follow the Phase recovery and protected-path rules.
- K14 may proceed as the separately authorized post-K13 plan slice without
  treating E2 readiness as E3 isolation or frontend-boundary completion.
