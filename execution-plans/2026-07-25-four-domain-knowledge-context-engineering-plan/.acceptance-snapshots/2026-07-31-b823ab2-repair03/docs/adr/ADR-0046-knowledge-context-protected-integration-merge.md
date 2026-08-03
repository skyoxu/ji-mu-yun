# ADR-0046: Knowledge Context Protected Integration Merge Decision

- Status: Accepted
- Date: 2026-07-26
- Decision scope: K11-K13 relationship to the paused frontend-boundary hardening plan

## Context

ADR-0044 defines knowledge projection and the E2 Hosted Context Envelope. The
2026-07-11 frontend-boundary hardening plan remains paused until its protected
BH-HANDOFF completes. Treating that paused plan as a blanket prohibition on all
knowledge integration would unnecessarily couple unrelated work; treating a
local plan validator as a BH-HANDOFF substitute would weaken the protected
frontend boundary.

## Decision

This is a `formal_merge_decision` for the narrow Knowledge Context K11-K13
integration path. It permits that path only when its actual write set is proven
not to overlap the protected frontend-boundary surface and the maintainer gives
separate explicit write authorization.

- K11 may generate only read-only caller inventory and direct-invocation guard
  evidence.
- K12 and K13 may implement the ADR-0044 Context Envelope only above the
  ADR-0037 shared entrypoints and while preserving ADR-0038 evidence/readback
  contracts.
- This decision does not authorize `/ui-v2`, Permit/Preflight, browser session
  paths, Change Origin Gate, legacy freeze, Platform SemVer, Caddy/runtime,
  live metadata DB, live Hosted workspaces, or a production release.
- Any K11-K13 write set that reaches one of those surfaces, or cannot be proven
  non-overlapping before mutation, fails closed and waits for BH-HANDOFF.
- A successful local validator, Bootstrap Review, or this ADR is not
  BH-HANDOFF and does not satisfy any 2026-07-11 downstream phase gate.

## Relationships

This ADR extends ADR-0044, complements ADR-0037 and ADR-0038, and does not
supersede ADR-0037, ADR-0038, ADR-0044, or the 2026-07-11 frontend-boundary
hardening plan. It records a merge of compatible scopes, not a replacement of
the frontend-boundary authority.

## Consequences

K11-K13 retain their declared predecessor order, deterministic tests, exact
write-set preflight, and explicit maintainer authorization. K14 remains a
separately authorized post-K13 slice.
