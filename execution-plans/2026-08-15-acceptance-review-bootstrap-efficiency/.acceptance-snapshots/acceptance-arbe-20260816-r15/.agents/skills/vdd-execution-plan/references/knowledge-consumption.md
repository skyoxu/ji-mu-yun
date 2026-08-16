# Knowledge Consumption

After mandatory authority reads and before freezing plan sources, VDD performs
this required sequence:

1. Read `knowledge/policies/consumer-policies.v2.json` and
   `knowledge/catalogs/repository-knowledge-catalog.v2.json`.
2. Build a Locator request with `consumer: "vdd"` and copy `ref` and `commit`
   exactly from the catalog `source_snapshot`; do not substitute `HEAD`.
3. Send that request as JSON stdin to `scripts/python/knowledge_locator.py`.
   The canonical CLI verifies `knowledge/indexes/current.json`, its immutable
   generation manifest, the formal Catalog/policy/projection hashes, and the
   current main source snapshot before returning candidates. Never use
   `--allow-unpublished-inputs` from this Skill.
4. `catalog_stale` is non-blocking: record `knowledge_freshness: degraded` and
   continue only with the current hash-verified Locator read-set. On every other
   `blocked` result, or `insufficient_match` for a required module, stop before
   publishing `plan-ready`. Invalid publication, unsafe paths, and read-set
   path/module mismatch remain fail-closed. A hash-only drift of the already
   selected read-set is automatically rehashed into a `source_refresh` context;
   it must preserve the catalog-selected path and resource set exactly.
5. Reread every recommended source at the bound source snapshot and verify its
   bytes against the candidate `source_sha256`. If only current worktree bytes
   differ, refresh those exact selected paths into `source_refresh`; otherwise
   keep the snapshot binding. Record an adapter-owned accepted or rejected
   decision for each candidate.
6. Run `scripts/prepare_knowledge_context.py`, which performs the same
   preflight before writing the context. Pass exactly one repository-relative
   `--target-plan execution-plans/<plan>`; output outside that directory is a
   CLI error. Its nonzero exit blocks `plan-ready`.
   The emitted input contains the `locator_request`, `locator_result`, required
   modules, and decisions. An accepted decision must name a path/hash returned
   by that Locator result. The command exclusively creates both
   `knowledge-context.v1.json` and `knowledge-context.freeze.v1.json`; the
   receipt binds the exact context bytes, canonical context, accepted
   decisions, snapshot, source snapshot, and policy revision.

Required knowledge modules must have an accepted decision. An insufficient
optional module remains explicit and non-authorizing. VDD still reads user
input, repository rules, lifecycle authority, and direct source evidence; the
knowledge projection never replaces them.
