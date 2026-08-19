# ADR-0050: Knowledge Publication LKG Recovery And Generation Retention

- Status: Accepted
- Date: 2026-07-29

## Context

The repository knowledge publication gate creates hash-bound immutable
generations and advances `current.json` and `last-known-good.json` only after
the full query gate passes. Publication failure preserves LKG, but operators
also need an explicit way to recover damaged formal layer files from that LKG.

Immutable generations are retained in the repository and currently consume
about 1.7 MB each. Unbounded retention is unnecessary, while implicit cleanup
inside publication would couple recovery data loss to the release path.

## Decision

- `scripts/python/publish_knowledge_catalog.py --restore-lkg` is the only
  formal LKG recovery entrypoint.
- Recovery acquires the publication single-writer lock, verifies the LKG
  pointer, immutable generation identity, every bundled artifact hash, source
  snapshot, policy, query report, and current local `refs/heads/main` before
  changing formal files.
- The LKG source commit may precede current main only when it remains an
  ancestor and every indexed source plus bundled publication input still
  byte-matches current main. The commit that records a generation therefore
  does not immediately invalidate that generation.
- Recovery restores exactly the source snapshot, v2 Catalog, consumer
  projections, and v1 compatibility Catalog. It then verifies the current
  publication, replays the Locator query gate, and runs a canonical Locator
  smoke without unpublished-input bypass.
- A stale LKG is not promoted over a newer main. Any failed post-restore check
  rolls the four layers and current pointer back, attempts every rollback
  target, and verifies their prior bytes before releasing the lock. Main is
  rechecked immediately before activation and after all validation.
- Publication activates the four formal layers, current pointer, LKG pointer,
  and success evidence as one rollback domain. A failed activation preserves
  its immutable generation but restores and verifies all prior formal bytes.
  The current pointer is written last as the logical activation marker.
- Publication requires its builder, evaluator, Locator, core, and publication
  scripts to byte-match pinned main before staging, so a dirty control plane
  cannot create a generation that main cannot reproduce.
- A stale publication lock binds PID and process creation identity. Serialized
  acquisition may recover a definitely dead or reused owner and, after a grace
  period of 60 seconds, an incomplete malformed lock. A live or indeterminate
  owner remains a lock conflict.
- Generation pruning is owned by the independent explicit
  `scripts/python/prune_knowledge_generations.py --prune` command. Publication
  and recovery never invoke pruning.
- `current`, LKG, and the five most recently added-to-main valid successful
  generations are protected. Success requires the complete publication
  manifest, artifact, layer, policy, source-snapshot, and query-report checks;
  mtime is never ordering authority. Invalid, uncommitted, or unrecognized
  generation directories are reported and never deleted.
- Pruning reads only the canonical retention policy at current main. Before
  deletion it persists an operation intent and a per-generation authorization;
  each target is atomically isolated from generation authority before recursive
  cleanup. Per-target evidence and partial failure evidence distinguish removed,
  remaining, and cleanup-failed generation sets.
- Failed publication and recovery evidence remains append-only under
  `logs/knowledge-context/` and is outside generation-pruning scope.

## Relationships

This ADR **extends ADR-0048** and **complements ADR-0044**. It changes neither
repository source authority nor the consumer-owned context freeze points.

This ADR **does not supersede** ADR-0044 or ADR-0048.

## Consequences

- Operators have a deterministic recovery command for damaged derived files
  without accepting stale repository facts.
- Storage cleanup remains reviewable, separately invoked, and protected by the
  same single-writer boundary as publication.
- The retained-generation threshold is an explicit versioned policy and can be
  changed only with a corresponding policy and ADR update.
- Historical failure evidence and non-candidate generations are never removed
  as a side effect of publication or recovery.

## References

- `docs/adr/ADR-0044-knowledge-projection-authority-e2-hosted-context-envelope.md`
- `docs/adr/ADR-0048-repository-knowledge-locator-workflow-consumption.md`
- `knowledge/policies/generation-retention.v1.json`
- `knowledge/README.md`
