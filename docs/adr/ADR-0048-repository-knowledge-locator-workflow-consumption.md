# ADR-0048: Repository Knowledge Locator Workflow Consumption

- Status: Accepted
- Date: 2026-07-26

## Context

Repository-maintenance workflows need a consistent way to locate current
repository knowledge without promoting a search index, a caller prompt, or an
LLM response into source authority. The completed knowledge context plan
defines the projection boundary, while VDD, Quick Dev, and Bootstrap Review
need a narrow repository-local consumption contract.

## Decision

- Repository source and Accepted ADRs remain fact authority. Knowledge
  projections and indexes are `derived_cache` only.
- A deterministic Locator returns source locations, hashes, provenance,
  ranking evidence, and confidence status. It does not return synthesized fact
  answers and callers must reread and hash-verify recommended sources.
- Trusted workflow adapters own the domain, path, snapshot, budget, and
  confidence envelope. A caller LLM may provide untrusted query intent but
  cannot widen that envelope.
- VDD records accepted or rejected consumption decisions after reread. A
  rejected candidate cannot satisfy a required knowledge module; an uncovered
  required module blocks plan readiness.
- Quick Dev consumes only VDD-frozen accepted decisions. Bootstrap Review may
  locate context before prepare, then freezes accepted context in its Artifact
  View. Neither may expand context after its respective freeze point.
- Locator ambiguity fallback is disabled by default. When an approved policy
  enables it, Python code delegates only through
  `scripts/sc/_llm_backend.py::run_llm_exec`.
- Repository-fact maintenance pins local `refs/heads/main`, performs no
  implicit fetch, checkout, merge, or branch mutation, and records only
  derived artifacts and append-only maintenance evidence.

## Relationships

This ADR **Extends ADR-0044** for repository-local deterministic knowledge
consumption.

This ADR **Complements ADR-0037, ADR-0041, and ADR-0043**. ADR-0037 remains
the shared LLM/Codex entrypoint authority. ADR-0041 remains the Bootstrap
Review control-plane authority. ADR-0043 remains the VDD clarification and
recovery authority.

This ADR **does not supersede** ADR-0037, ADR-0041, ADR-0043, or ADR-0044.

## Consequences

- Consumers share one deterministic location-only retrieval core and stable
  contracts instead of independently searching or synthesizing answers.
- Missing, stale, low-confidence, out-of-policy, or hash-drifted results fail
  closed according to the trusted consumer policy.
- This decision does not authorize Phase routes, Hosted E2 dispatch changes,
  live metadata access, deployment, acceptance, handoff, release, or commit.

## References

- `docs/adr/ADR-0044-knowledge-projection-authority-e2-hosted-context-envelope.md`
- `docs/adr/ADR-0037-phase-shared-llm-codex-entrypoints.md`
- `docs/adr/ADR-0041-bootstrap-review-execution-control-plane-ownership.md`
- `docs/adr/ADR-0043-vdd-solo-maintainer-clarification-recovery.md`
- `execution-plans/2026-07-26-knowledge-locator-workflow-integration/`
