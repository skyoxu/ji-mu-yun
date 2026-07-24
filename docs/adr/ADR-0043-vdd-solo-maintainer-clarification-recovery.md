# ADR-0043: VDD Solo-Maintainer Clarification Recovery

- Status: Accepted
- Date: 2026-07-24

## Context

The VDD package serves one trusted maintainer working with an AI assistant. Most changes need no durable clarification state, but an interrupted material decision sometimes must survive a session boundary. The earlier v2 state did not provide typed dependencies, explicit stale recovery, legacy inspection, or bounded handling of accidentally supplied credentials.

Distributed proof controls would add cost without a consumer in this operating model. Git remains the repository and baseline authority, while clarification state remains optional recovery data rather than implementation, review, acceptance, or release evidence.

## Decision

- A standalone requirements Markdown file routes to direct implementation. VDD `create` or `repair` requires an explicit request concerning a complete execution-plan directory.
- New optional clarification state uses `vdd.clarification-resume.v3` as one atomic, single-writer file under a contained evidence root.
- Decisions use typed kinds and acyclic dependencies. Hash drift is byte-preserving until explicit invalidate and reopen operations reset the stale state.
- Legacy v1/v2 files are inspected only against an exact caller-supplied digest. They are never migrated or rewritten implicitly.
- Credential-shaped values and sensitive keys in a location-bound current state cause replacement with a terminal digest-only quarantine envelope. Path ownership is verified before replacement, and invalid or ambiguous ownership fails without mutation.
- Target and run identities use canonical Windows-safe path semantics. A closed state cannot contain unresolved material decisions.
- Windows CI validates the package contract and all VDD unit tests without remote services, signing keys, or Bootstrap authorization.

The package does not add event chains, snapshots, registries, cross-process locks, signatures, reviewer identities, generations, committed pointers, or promotion transactions.

## Consequences

- Recovery remains cheap and local for the solo-maintainer workflow.
- Quarantine is intentionally terminal; the original credential-bearing content is not retained in the state file.
- Sensitive-pattern changes require positive credential tests and benign-text false-positive tests.
- ADR-0041 continues to own Bootstrap Review control-plane boundaries. This ADR grants no Bootstrap, implementation-completion, acceptance, archive, or release authority.
- Existing v2 files remain available for digest-bound read-only inspection but cannot resume as current mutable state.

## References

- `docs/adr/ADR-0041-bootstrap-review-execution-control-plane-ownership.md`
- `execution-plans/2026-07-24-vdd-solo-maintainer-recovery-hardening-requirements.md`
- `_bmad-output/implementation-artifacts/spec-vdd-solo-maintainer-recovery-hardening.md`
