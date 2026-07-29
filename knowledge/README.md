# Repository Knowledge Base

The repository knowledge base is a derived, main-pinned location service. It
does not replace repository source, Accepted ADRs, runtime facts, or current
acceptance evidence. ADR-0044 and ADR-0048 govern this boundary.

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
  contract, authority manifest, plan state, knowledge context, and command
  registry files. Fixtures, tools, tests, and implementation reports do not
  become global semantic modules.
- `docs/migration/**` is hard-excluded from snapshots, catalogs, semantic
  retrieval, and targeted maintenance.

## Build And Verify

```powershell
py -3 -B scripts/python/build_knowledge_catalog.py --repository-root .
py -3 -B scripts/python/build_knowledge_catalog.py --repository-root . --check
```

The builder reads source bytes with `git show` from the pinned local main ref.
It never promotes dirty-worktree bytes as repository facts.
