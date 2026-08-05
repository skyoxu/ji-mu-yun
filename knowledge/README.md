# Repository Knowledge Base

The repository knowledge base is a derived, main-pinned location service. It
does not replace repository source, Accepted ADRs, runtime facts, or current
acceptance evidence. ADR-0044, ADR-0048, and ADR-0057 govern this boundary.

## Three Layers

1. `snapshots/repository-source-snapshot.v1.json` records eligible committed
   source bytes, source roles, the pinned `refs/heads/main` commit, and SHA-256.
   This is the integrity layer and is not searched directly.
2. `catalogs/repository-knowledge-catalog.v2.json` contains typed modules,
   headings, relationships, governance component bundles, route bindings, and
   source hashes. This is the semantic discovery layer.
3. `projections/consumer-projections.v1.json` freezes the modules visible to
   each consumer policy. VDD and Bootstrap may query and freeze context; Quick
   Dev has an empty projection and may only reuse VDD-frozen context.

The v1 catalog remains a generated compatibility projection. It is not the
runtime owner for new integrations.

## Publication Envelope

The three runtime layers and the v1 compatibility projection are published as
one logical generation. `indexes/current.json` is the logical commit marker;
`indexes/last-known-good.json` is advanced only after a validated publication.
Each immutable generation binds the source snapshot, both catalogs, consumer
projections, policy, exclusion policy, query suite, and query report by
SHA-256. The Locator verifies the current pointer and these runtime artifact
hashes before reading the Catalog, then re-reads current main source blobs and
verifies every returned read-set hash.

## Indexing Rules

- ADRs are registered globally and grouped into Phase, Godot/workspace,
  Toolchain/governance, and unscoped collections. Accepted ADRs are active,
  Proposed ADRs are conditional, Superseded ADRs are historical, and an
  unmarked ADR is excluded from semantic retrieval.
- Phase service, base, and overlay architecture use collection entry -> module
  -> heading anchors. Encoding fixtures, acceptance fixtures, examples, and
  ordinary checklists remain integrity-only sources.
- Standards are individual modules under the standards collection.
- Governance Skills are component modules binding their Skill entrypoint,
  CLI, orchestrator, route registry or policy, operations, and freeze point.
- Each execution-plan directory contributes one discoverable plan module at
  `00-index.md`. The module binds available requirements, implementation
  contract, plan state, and command registry files. Context-bound lifecycle
  artifacts such as authority manifests and knowledge contexts never enter the
  global semantic source closure; this prevents catalog-to-plan-to-context
  recursion. Fixtures, tools, tests, and implementation reports do not become
  global semantic modules. Versioned top-level plan resources use the highest
  available numeric version and accept both `requirements-ledger.vN.json` and
  `requirements.vN.json`.
- `docs/migration/**` is hard-excluded from snapshots, catalogs, semantic
  retrieval, and targeted maintenance.

## Build And Verify

```powershell
py -3 -B scripts/python/publish_knowledge_catalog.py --check
py -3 -B scripts/python/publish_knowledge_catalog.py --publish --publication-request <request>
py -3 -B scripts/python/publish_knowledge_catalog.py --restore-lkg
```

The publication CLI stages source bytes from the pinned local main ref, checks
schema shape, composition, hashes, contamination, 108 real queries, and every
adapter-owned consumption decision before atomically advancing the four formal
layers, `current`, LKG, and success evidence. Any activation failure restores
and verifies every previous byte while preserving the immutable failed
generation. The builder, evaluator, Locator, and publication control scripts
must themselves byte-match that pinned main, so an uncommitted control-plane
change cannot produce a publishable generation. It never promotes
dirty-worktree bytes as repository facts. This is a local release gate; no CI
workflow file is required.

`build_knowledge_catalog.py` is permanently read-only and reports only whether
the formal layers match a staged build. Formal layer activation is available
only through the authorized publication CLI.

Publication is never a consumer-side recovery side effect. `--publish` requires
an append-only request created by `maintain-knowledge-base`, bound to one target
plan, its hash-verified stale-maintenance route, and the current local main
commit, with explicit maintainer confirmation. The target plan must exist at
pinned main.
Acceptance and VDD stop with typed non-authorizing routes when maintenance is
required; they may write knowledge artifacts only inside their explicit target
execution-plan directory.

`--restore-lkg` is an explicit recovery operation. The generation source commit
must be an ancestor of local `refs/heads/main`; every indexed source and bundled
publication input must still byte-match current main. This permits the commit
that records the immutable generation without accepting later source drift.
Recovery verifies every bundled artifact hash, restores the snapshot, v2
Catalog, projections, and v1 compatibility Catalog, then re-runs publication
verification and the real Locator gate. A failed check or success-evidence
write rolls back and re-verifies every target. Locks bind PID and process
creation identity; a dead, reused, or sufficiently old malformed owner can be
recovered after a 60-second grace period through serialized acquisition and
append-only evidence. Recovery never deletes a generation or historical
evidence.

## Generation Retention

Generation retention is governed by
`policies/generation-retention.v1.json`. Current and LKG generations are always
protected, as are the five most recently added-to-main valid successful
generations. A successful generation must pass the complete publication
manifest, artifact, layer, source snapshot, policy, and query-report checks;
filesystem timestamps are not authority. Invalid, uncommitted, or unrecognized
generation directories are reported and never pruned. Failed publication
reports remain append-only under `logs/knowledge-context/` and are outside
generation pruning scope.

```powershell
py -3 -B scripts/python/prune_knowledge_generations.py --check
py -3 -B scripts/python/prune_knowledge_generations.py --prune
```

The default command is read-only. Deletion requires the independent explicit
`--prune` mode, runs under the publication single-writer lock, and accepts no
alternate policy path. It records an append-only intent before deletion, a
per-generation authorization before each removal, atomically isolates a target
from generation authority before recursive cleanup, and records per-target
deletion evidence plus success or partial-failure sets. Publication and LKG
restoration never invoke it.
