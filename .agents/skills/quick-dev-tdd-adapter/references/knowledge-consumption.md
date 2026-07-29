# Verify-Bound Knowledge Consumption

Quick Dev consumes the VDD-frozen accepted knowledge decisions and their source
hashes. It does not issue a new Locator request, add a candidate, reclassify a
decision, widen a path policy, or add a satisfied module. Any mismatch routes
to VDD repair before RED.

`route_plan_directory.py` must validate the current publication generation,
Catalog/policy/projection bindings, frozen request/result hashes, every
adapter-owned decision, and every candidate read-set source hash. The Quick Dev
package contains no Locator or subprocess query path. The staging-only
`--allow-unpublished-inputs` option is forbidden here.

The same pre-RED check requires `knowledge-context.freeze.v1.json` beside the
context and compares its exact-byte hash, canonical hash, accepted decisions,
snapshot, source snapshot, and policy revision. A missing or mismatched receipt
routes to VDD repair.
