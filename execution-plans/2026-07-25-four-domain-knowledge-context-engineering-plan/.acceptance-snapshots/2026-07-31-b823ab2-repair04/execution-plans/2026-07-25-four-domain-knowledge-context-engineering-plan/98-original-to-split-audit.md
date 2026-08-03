# Original Requirements To Split Audit

| Original area | Directory artifact | Coverage |
| --- | --- | --- |
| Four dimensions and four domains | `01-scope-authority-and-non-goals.md`, `schemas/knowledge-contract.v1.schema.json` | KC-001..KC-009 |
| E1/E2/E3 boundaries | `02-executable-contracts-and-invariants.md`, `04-behavior-slices-and-implementation-order.md` | KC-006..KC-007, KC-023, KC-035 |
| Snapshot, path, cache and LKG | `schemas/source-snapshot.v1.schema.json`, K3 slice | KC-015..KC-017 |
| Tokenizer, ranking and evaluation | `03-validators-fixtures-and-control-gates.md`, K5 slice | KC-019..KC-022 |
| K0 synthetic environment | K0 slice and `fixtures/` | KC-010..KC-011 |
| Save/retention policy | `02-executable-contracts-and-invariants.md`, K3/K7/K8 | KC-016..KC-017, KC-024..KC-026 |
| Context budget and omission evidence | `schemas/context-assembly.v1.schema.json`, K10 | KC-027 |
| Manifest signature and replay | `schemas/hosted-context-manifest.v1.schema.json`, `fixtures/reference-vectors/jcs-hmac-reference-vector.v1.json`, K10 | KC-028..KC-029 |
| Three caller inventories | `tools/build_hosted_inventory.py`, inventory JSON files, K11 | KC-030..KC-032 |
| Compatibility migration and rollback | K12/K13 slices and gate schema | KC-033..KC-035 |
| Bootstrap entry conditions | `08-bootstrap-review-entry.md` | KC-040 |
| Standardized knowledge consumption | Locator request/result Schemas, interface fixtures, K5 slice | KC-041..KC-046, KC-052 |
| Knowledge-base maintenance Skill | Maintenance request/result Schemas, interface fixtures, K14 slice | KC-047..KC-051 |

No original requirement is intentionally dropped. KC-041..KC-052 trace the maintainer-authorized 2026-07-25 amendment now recorded in the original-requirements file. Implementation details beyond that amendment remain plan-local acceptance mechanics rather than silent product scope.
