---
name: vdd-conformance-exact-cover
description: Validate a VDD-frozen Canonical Spec Package against an execution-plan requirements mapping without changing lifecycle or target plan contents.
---

# VDD Conformance Exact-Cover

Accept only a current VDD `vdd-source-freeze-manifest.v1`, its selected Canonical
Spec Package, and a read-only requirements mapping. Revalidate the VDD-owned
manifest and selection bindings before exact-cover. Deterministic schema, hash,
role, path, ID, set, mapping, and disposition failures return a typed blocked
result. Only a source-bound, structurally complete semantic ambiguity may be
represented as a non-authorizing `bootstrap-upstream-plan` handoff.

Run `scripts/validate_conformance.py` with explicit `--repository-root`,
`--manifest`, and `--mapping` paths. Results, diagnostics, checkpoints, and
receipts always contain `authorizes: []`; this Skill never changes the target,
lifecycle state, review state, acceptance state, or authorization state.
