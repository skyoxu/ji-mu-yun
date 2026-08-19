# ADR-0057: Explicit Knowledge Publication And Nonrecursive Plan Indexing

- Status: Accepted
- Date: 2026-08-05

## Context

Acceptance treated `catalog_stale` as a route to knowledge maintenance, but the
route did not distinguish a read-side recovery request from authority to
publish all repository knowledge layers. VDD and Acceptance also constrained
outputs only to the broad `execution-plans/` tree rather than one declared
target. Finally, plan catalog modules included authority manifests even though
those manifests can bind plan-local knowledge contexts, creating a conditional
catalog -> authority manifest -> knowledge context -> catalog dependency loop.

## Decision

- Knowledge publication is owned only by `maintain-knowledge-base` and requires
  a separate append-only request with explicit maintainer confirmation.
- The request binds its caller, trigger, one target plan, current local main
  commit, non-automatic status, timestamp, `knowledge-publication` authority,
  and the hash-verified Acceptance maintenance route for stale-triggered work.
  The target must exist at pinned main. `publish_knowledge_catalog.py
  --publish` fails closed without these bindings.
- Acceptance emits a typed, hash-bound, non-authorizing stop route for stale
  catalogs and persists it append-only inside the target plan. It never turns
  that route into publication authority.
- VDD and Acceptance require one explicit target plan and reject knowledge
  outputs outside that exact directory.
- Plan catalog modules index stable semantic plan sources only. Authority
  manifests and knowledge contexts are context-bound lifecycle artifacts and
  are excluded from the global semantic closure.
- The standalone catalog builder is read-only. Only the publication gate may
  activate formal knowledge layers or pointers, and its internal bundle writer
  requires a validated authorization capability.
- Plan requirements, implementation contract, plan state, and command registry
  discovery accepts versioned top-level files and selects the highest numeric
  version. Both requirements-ledger and requirements naming are supported.
- Read-only publication checks and historical generation reads remain
  compatible. Existing generations do not require a retroactive publication
  request field; new authorized publications record its summary and hash.

## Relationships

This ADR extends ADR-0044, ADR-0048, and ADR-0050. It supersedes no ADR.

## Consequences

- A stale catalog creates a visible maintenance boundary instead of an
  automatic global write.
- Publication intent is independently auditable and tied to the repository
  state it authorizes.
- Consumer context preparation cannot mutate sibling execution plans.
- Removing lifecycle artifacts from global plan indexing breaks the recursive
  freshness loop while retaining plan requirements, contracts, state, and
  command discovery.

## References

- `knowledge/README.md`
- `knowledge/contracts/knowledge-publication-request.v1.schema.json`
- `scripts/python/publish_knowledge_catalog.py`
- `.agents/skills/maintain-knowledge-base/SKILL.md`
- `.agents/skills/run-refactor-implementation-acceptance/SKILL.md`
- `.agents/skills/vdd-execution-plan/SKILL.md`
