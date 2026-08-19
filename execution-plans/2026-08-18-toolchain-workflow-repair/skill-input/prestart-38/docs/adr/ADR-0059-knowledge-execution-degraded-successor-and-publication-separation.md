# ADR-0059: Knowledge Execution Degraded Successor And Publication Separation

- Status: Accepted
- Date: 2026-08-18

## Context

Rapid repository evolution makes catalog freshness and selected source bytes
change frequently. A stale derived catalog should not block unrelated machine
execution, while authority drift and publication integrity must remain strict.

## Decision

- A valid published or LKG catalog may replay a frozen selection against current
  selected read-set bytes and produce a validator-owned successor context.
- `knowledgeSelectionHash` excludes source bytes; `knowledgeContextHash` binds
  selection, current selected source hashes, source snapshot, Locator result,
  decisions, and predecessor context; an authority envelope hash binds ADRs,
  repository rules, policies, contracts, registries, and allowed successor
  kinds.
- Stale freshness and query-quality failure may produce degraded execution for
  unrelated targets when selection, authority, required modules, and current
  read-set remain verifiable.
- Publication failures never advance current/LKG and never invalidate a still
  valid LKG for degraded execution consumption.
- Selection, authority, contract, command/test, policy, protected-path, source
  integrity, or Knowledge-system self-change failures remain blocking or require
  semantic review.

## Assurance Profiles

The rapid-evolution profile permits execution against a validator-verified
same-selection successor with degraded freshness when the target is not a
Knowledge-system self-change. It does not permit publication, lifecycle
transition, or authority replacement.

The production/release profile additionally requires current published
Knowledge, successful publication-quality checks, and the applicable semantic
review evidence before release or externally authoritative completion. A
consumer may select the stricter profile without changing the shared LKG or
publication ownership rules.

## Relationships

This decision extends ADR-0048 and ADR-0050 and supersedes only
the stale-stop execution interpretation in ADR-0057. It does not weaken the
publication query gate or LKG integrity checks.

## Acceptance Boundary

This decision supersedes only the stale-stop execution interpretation in
ADR-0057. It does not authorize Knowledge publication, weaken the publication
query gate, or permit a consumer to bypass authority or source integrity checks.
