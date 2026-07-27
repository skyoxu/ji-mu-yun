---
name: maintain-knowledge-base
description: Refresh or audit the repository knowledge base against the pinned local main branch. Use when maintaining existing knowledge facts, checking a specific execution plan, CLI, skill, tool, MCP, or document directory, detecting stale registered entries, or producing derived index and append-only maintenance evidence.
---

# Maintain Knowledge Base

Use this Skill only for derived knowledge artifacts. Never edit the inspected
source, checkout/fetch/merge Git branches, mutate a live Phase workspace, or
promote dirty-worktree bytes as repository facts.

## Workflow

1. Read `AGENTS.md`, the stable maintenance-compatible contracts under
   `knowledge/contracts/`, and the existing knowledge catalog. The dated
   2026-07-25 schemas are read-only migration inputs, not runtime owners.
2. Pin `refs/heads/main` with `git rev-parse refs/heads/main`. Reject a request
   whose declared `main_commit` differs. Treat catalog `source_snapshot` as
   provenance for the derived index, not as the commit containing the catalog
   itself. Do not fetch or change branches.
3. Use `existing-only` without a target to refresh only catalog entries already
   registered. Do not discover absent files.
4. Use `targeted` only with one explicit repository-relative target. Read main
   blobs as facts; worktree-only target content may be recorded only as a
   `provisional` candidate.
5. Run `scripts/maintain_knowledge.py` with the request, catalog, derived
   output and append-only log root. When it reports a stale catalog snapshot,
   use its `suggested_catalog_source_snapshot` to regenerate the catalog from
   current main facts, then re-read output hashes before claiming a result.
6. Report source locations and hashes, not generated factual answers. Preserve
   failed result sidecars under `logs/knowledge-context/`.

## Command

```powershell
py -3 .agents/skills/maintain-knowledge-base/scripts/maintain_knowledge.py `
  --request request.json --catalog knowledge/catalogs/repository-knowledge-catalog.v1.json `
  --output knowledge/indexes/derived-index.v1.json --repo-root .
```

The request must conform to `knowledge-maintenance-request.v1`. The catalog is
a JSON object with an `entries` array; every entry needs `entry_id` and
`source_path`, and may contain `source_sha256`.

Use `--dry-run` to validate authority and compute the result without writes.
The only normal writes are the derived output and a new append-only result file
under `logs/knowledge-context/`.
