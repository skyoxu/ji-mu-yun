# ADR-0034: Account-Scoped Token Auth For Phase B Prototype Hardening

- Status: Accepted
- Date: 2026-06-28

## Context

Phase A began as a single-admin hosted console. Phase B needed account boundaries without prematurely committing to a full production identity system.

The immediate risk was cross-account project, run, artifact, package, asset, chat, workflow, and LLM usage leakage. The deferred product questions include password login, OAuth/OIDC, self-service registration, and runner OS account isolation.

## Decision

Use host admin token plus database-backed user tokens for the current Phase B prototype-hardening scope.

- User tokens are returned once and stored only as hashes.
- Admins create users, disable or enable users, rotate tokens, set limits, and read audit summaries.
- Project, run, artifact, package, asset, chat, workflow, and LLM readback must resolve the current account before access.
- Password login, password reset, OAuth/OIDC, self-service registration, and OS-level runner accounts are deferred to Phase C or pre-production hardening.

## Consequences

- The platform gets account-scoped behavior without overbuilding identity.
- Token material must never be logged or stored in git-tracked docs.
- New readback surfaces must declare account/user/admin scope.
- Phase C identity decisions must record migration, recovery, and threat-model impact.

## References

- `docs/architecture/phase-service/auth-and-accounts.md`
- `docs/workflows/phase-b-account-isolation.md`
- `scripts/python/phase_b_account_smoke.py`
