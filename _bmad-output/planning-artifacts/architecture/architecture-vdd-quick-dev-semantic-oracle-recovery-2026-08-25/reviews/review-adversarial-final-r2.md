# Adversarial Review - Final R2 Architecture Spine

**Target:** `ARCHITECTURE-SPINE.md`  
**Lens:** independent downstream implementations that obey every AD yet must converge  
**Verdict:** **REJECT - one convergence blocker remains**

The update resolves the prior H1. AD-6 now limits an identity mismatch to
admissibility of the old observation edge, AD-10 and AD-13 require the
recovery artifact to copy its `referenced_observation` quartet exactly, and
only an executor/judge evaluation may create a new `invalid-run` observation.
There is no longer a competing Quick Dev recovery-result authority.

AD-16 also now enumerates every stated runtime failure family and assigns the
normal execution cases a single legal tuple. Its failure-ID rule is still not
implementable for the pre-execution classifications it includes.

## Finding

### M1 - The total `failure_id` rule has no valid inputs or writer for pre-execution rejection

**References:** AD-2 (lines 60-64), AD-4 (lines 72-76), AD-6 (lines 84-88),
AD-7 (lines 90-94), AD-16 (lines 163-167).

AD-16 classifies VDD rejection as
`planned-only/blocked/semantic-contract-gap` and descriptor binding rejection
as `invalid-run/fail/target-binding-failure`, while requiring every classified
condition to carry a `failure_id` made from taxonomy version, family,
descriptor, target, fixture, oracle, case cell, and a normalized receipt
fingerprint.

For a semantic-contract-gap, VDD has deliberately not emitted a descriptor,
target, fixture, receipt, hash, or observed result (AD-2). For a descriptor
binding rejection, execution may similarly have no receipt and no executed
case cell. AD-4 assigns process receipts and result derivation solely to the
executor/judge, but no executor invocation is available for the VDD rejection;
AD-7 also defines no rejection artifact or writer for either pre-execution
result.

Consequently two compliant implementations can choose different missing-field
sentinels, synthesize a receipt, omit the ID despite AD-16, or decline to emit
the result. This changes stop-loss grouping and recovery fingerprints, and
violates the claimed total mapping.

**Required convergence rule:** split the failure-ID input grammar by artifact
class and name the writer. At minimum, define a VDD-owned preflight/rejection
artifact (or explicitly declare that this is a VDD validation diagnostic and
not a result quartet), and specify exact canonical sentinel values or a
separate pre-execution fingerprint for absent descriptor/receipt/case fields.
For descriptor-binding rejection, bind the descriptor identity and define the
absence representation for the receipt/case-cell fields. The taxonomy must
state which authority writes each resulting quartet and ID. Until then those
families cannot enter a coverage snapshot.

## Resolved Findings

| Prior finding | Result | Evidence |
| --- | --- | --- |
| H1 recovery quartet versus current blocker | Resolved | AD-6 makes mismatches invalidate the old coverage edge, while AD-10 and AD-13 preserve an exact executor/judge quartet and use Quick Dev `projection_status` separately. |
| M1 runtime-family tuple mapping | Partially resolved | AD-16 has a closed family set and prescribed tuples for stated conditions; its common receipt-based ID grammar remains undefined for pre-execution classes. |

## Gate Result

Do not restore `status: final` yet. Resolve M1 and rerun the reviewer gate.
