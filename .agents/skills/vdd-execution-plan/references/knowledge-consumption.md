# Knowledge Consumption

After mandatory authority reads and before freezing plan sources, VDD performs
this required sequence:

1. Read `knowledge/policies/consumer-policies.v1.json` and
   `knowledge/catalogs/repository-knowledge-catalog.v1.json`.
2. Build a Locator request with `consumer: "vdd"` and copy `ref` and `commit`
   exactly from the catalog `source_snapshot`; do not substitute `HEAD`.
3. Send that request as JSON stdin to `scripts/python/knowledge_locator.py`.
4. On `blocked`, or `insufficient_match` for a required module, stop before
   publishing `plan-ready`.
5. Reread every recommended source at the bound source snapshot and verify its
   bytes against the candidate `source_sha256`. Record an adapter-owned
   accepted or rejected decision for each candidate.
6. Run `scripts/vdd_knowledge_preflight.py`. The input must contain the
   `locator_request`, `locator_result`, required modules, and decisions. An
   accepted decision must name a path/hash returned by that Locator result.

Required knowledge modules must have an accepted decision. An insufficient
optional module remains explicit and non-authorizing. VDD still reads user
input, repository rules, lifecycle authority, and direct source evidence; the
knowledge projection never replaces them.
