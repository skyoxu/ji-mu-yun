# Adversarial Review - Final R3 Architecture Spine

**Target:** `ARCHITECTURE-SPINE.md`  
**Scope:** AD-16 pre-execution failure classification  
**Verdict:** **REJECT**

`semantic-rejection.v1` and `descriptor-rejection.v1` correctly name a sole
writer, separate the two pre-execution classes from executor/judge execution
results, and prohibit fabricated receipts or case cells. This closes the
missing-artifact and missing-field portion of the prior finding. Two
convergence conflicts remain.

## Findings

### H1 - VDD-generated `failure_id` violates the VDD no-hash boundary

**References:** AD-2 line 64; AD-16 line 167.

AD-2 prohibits VDD from emitting a hash. AD-16 makes VDD the sole writer of
`semantic-rejection.v1` and requires its `failure_id` to be a SHA-256 value.
`failure_id` is explicitly the generated hash, not merely an identity
reference. A conforming implementation therefore cannot both produce the
required semantic rejection artifact and obey the VDD trust boundary.

**Required rule:** either explicitly carve a deterministic semantic-rejection
fingerprint out of AD-2's no-hash rule, with the non-execution scope made
clear, or assign deterministic `failure_id` derivation to a non-VDD authority
and make `semantic-rejection.v1` reference that result. The choice must retain
VDD's prohibition on commands, receipts, and execution facts.

### M1 - `normalized rejection predicate` does not define a deterministic byte representation

**Reference:** AD-16 line 167.

The new ID grammar names `normalized rejection predicate` but never defines
the predicate's fields, ordering, Unicode/number handling, absent-versus-empty
rules, or canonical serialization. Two VDD validators can classify the same
semantic gap while serializing an equivalent predicate differently and derive
different IDs. The literal `absent` rule covers unavailable artifact fields,
but not the predicate itself.

**Required rule:** define a versioned predicate schema and canonical byte
encoding (including field order and normal form), or reference a repository
canonical serialization contract that is binding for this artifact. The
resulting bytes must be the exact SHA-256 input.

## Gate Result

Do not restore `status: final`. Resolve H1 and M1, then rerun the reviewer
gate.
