# Adversarial Review R2 - Architecture Spine

**Target:** `ARCHITECTURE-SPINE.md`  
**Lens:** independent downstream implementations that obey every stated AD but still disagree  
**Verdict:** **REJECT - convergence blockers remain**

The revision establishes the correct major trust zones and makes the intended
writers much clearer. It still leaves several cross-boundary meanings open.
Those gaps are significant because they occur at the handoff points where a
coverage decision, recovery consumer, and concurrent resolver must reach the
same answer from the same immutable history.

## Findings

### H1 - Recovery result layers and live blockers have no authoritative source

**References:** AD-3, lines 64-68; AD-4, lines 70-74; AD-6, line 86; AD-7,
line 92; AD-10, line 128.

AD-4 makes executor/judge the only writer that *derives* all four result
fields, including `evidence_state`, while AD-10 makes Quick Dev publish a
recovery artifact containing those same state/outcome/failure layers. AD-6
then says a recovered run becomes `invalid-run` when the current
descriptor/target/fixture/oracle/**live-blocker** identity mismatches. No
artifact type, writer zone, schema owner, or identity rule owns a live blocker,
and no rule states whether Quick Dev is copying executor-derived fields or
deriving a new recovered/invalid state.

Two conforming implementations can therefore disagree:

- Recovery publisher A copies the referenced observation's
  `observed-run/pass` quartet and renders a newly discovered blocker as a
  recommendation only, preserving the executor as the quartet authority.
- Recovery publisher B evaluates the mismatch required by AD-6, emits
  `invalid-run/blocked/<family>/<id>` in its recovery artifact, and treats its
  own projection as the recovery quartet.

Both are Quick Dev-only writers and neither rewrites an observation or
coverage artifact, yet the coordinator receives opposite recovery state. A
second pair can choose distinct "current live blockers" because the artifact
has no owner/index and still satisfy AD-7's listed ownership table.

**Required convergence rule:** introduce a versioned, identity-addressed
`live-blocker` artifact with one named writer and append-only index. State
whether the recovery artifact carries (a) an exact copied observation quartet
plus a separate projection-status quartet owned by Quick Dev, or (b) a new
executor/judge-signed recovery observation. Specify the invalidation
transition, its writer, and the exact blocker identity it consumes. Do not use
one unqualified set of result fields for both sources.

### H2 - The `current` resolver cannot construct a coherent dependency snapshot

**References:** AD-5, line 80; AD-7, line 92; AD-9, line 122; AD-10, line
128.

AD-7 only resolves the newest schema-valid artifact independently in each
owner's index. It does not define a root artifact, monotonic sequence domain,
or a closure rule that requires every inbound identity to be a predecessor of
the selected root. The clause about equal sequence is not actionable because
the specified index entry contains an artifact identity, predecessor identity,
writer zone, and timestamp, but no sequence field.

Consider a concurrent run: the executor publishes observation `O2` for new
descriptor `D2`; coverage `C1` is still the current completion decision for
`D1/O1`; then Quick Dev publishes recovery projection `R2`. One conforming
resolver independently selects newest `D2`, `O2`, and `C1`, since each is
newest in its owner index. Another begins from `C1` and follows its immutable
predecessor closure, selecting `D1/O1`. Both honour append-only writes,
identity-addressed reads, and fail only on the explicitly named equal-sequence
or concurrent-publication case, but they emit materially different recovery
and implementation status.

**Required convergence rule:** define a single snapshot/root selection
algorithm. For example, make `acceptance-coverage.v1` the only completion
snapshot root and require it to enumerate the manifest, semantic-intent,
descriptor, receipt, observation, reuse/invalidation, and blocker identities
that form its closed DAG; recovery must select one such root and may not mix
independently-current leaves. Put a strictly ordered owner-local revision (or
an explicit compare-and-swap predecessor rule) in the index and define
fail-closed behavior for a missing, forked, or unclosed graph.

### H3 - Exact cover does not bind an asserted Acceptance ID to a verified evidence path

**References:** AD-2, line 62; AD-5, line 80; AD-9, line 122.

AD-5 requires each active ID to have an "admissible oracle/observation path"
and each asserted path to resolve to the same manifest, but neither an
admissible path nor its mandatory edge set is specified. `semantic-verification.v1`
contains abstract `case_source_refs`/`case_producer_ref`, but it is not
required to bind Acceptance IDs, the descriptor's selected cases, the executed
matrix result, and the observation assertion into one immutable chain.

Two gate implementations can both satisfy the text:

- Gate A accepts an observation whenever a coverage record locally maps its
  oracle reference to an ID in the active manifest.
- Gate B requires the chain `manifest -> semantic intent/oracle -> descriptor
  -> receipt + observation matrix cell -> asserted Acceptance ID`, with each
  edge carried by identity in the downstream artifact.

For an overlapping oracle or a manifest revision, Gate A can declare exact
cover from a current passing observation whose descriptor never selected the
case for that Acceptance ID; Gate B rejects it. Neither behavior violates the
present definitions of "path", "resolves", or "identity-matched".

**Required convergence rule:** make the admissible-path grammar normative and
require every coverage edge to record the immutable identities and the precise
case/matrix-cell-to-Acceptance-ID relation. Define whether one observed case
may satisfy multiple IDs, and require the coverage gate to reject an edge
missing any link. Make a coverage artifact explicitly bind the exact semantic
intent and descriptor generations used to construct its cover.

### M1 - AD-6 does not close the legal four-field tuple

**References:** AD-6, line 86; AD-12, line 140; conventions, lines 148-150.

The state/outcome pair is closed, but `failure_family` has no declared finite
domain or ownership of its namespace, and "deterministic member" leaves the
`failure_id` derivation function unspecified. Classification is optional
whenever it is "known", which permits different judges to decide at different
points that the same matrix result is known. AD-12 gives four family names but
does not say whether they are exhaustive, what outcomes they permit, or how
they interact with `expected-red`.

Example: a timeout with partial output can be emitted by one judge as
`observed-run/blocked/timeout-no-observation/<id>` and by another as
`observed-run/incomplete/<unset>/<unset>` because the latter considers the
classification not known. Both are legal under AD-6 and non-completing under
AD-12, but recovery fingerprints, stop-loss grouping, and downstream routing
diverge.

**Required convergence rule:** publish an owned, versioned failure taxonomy
and a total mapping from each observation-classification condition to either a
specific `(outcome, family, id)` or the sole permitted unclassified tuple.
Define the canonical ID input and hash/normalization so two judges derive the
same ID.

### M2 - N->N+1 promotion record lacks a named writer and binding to the gate snapshot

**References:** AD-7, line 92; AD-8, lines 98-115.

AD-8 requires a new promotion record only after mandatory suites pass, while
AD-7 assigns no promotion-record writer. The sequence diagram also has the
coverage gate notify the predecessor judge and then the candidate becomes
eligible, but it does not identify the artifact or the identity of the
coverage decision that authorizes promotion.

One implementation can let the predecessor judge append the promotion record
after seeing its own observations; another can let Quick Dev append it after
reading the gate's eligibility message. Both preserve all named writers and
frozen judge bytes, but the first may promote before exact cover and the second
may bind a different current coverage snapshot.

**Required convergence rule:** assign the promotion-record root and sole
writer explicitly (normally the coverage gate, or a dedicated promotion
authority), and require it to cite the frozen judge/fixture/oracle identities
plus one closed acceptance-coverage snapshot. State that no other zone may
materialize promotion from a notification.

## Positive Checks

- The SUT and external coordinator are explicitly denied evidence/completion
  writes (AD-1, AD-4, AD-7).
- Descriptor, receipt, observation, coverage, and recovery have clear primary
  writers in AD-3/4/5/7; the remaining issue is the recovery-derived state and
  live-blocker input, not ordinary artifact ownership.
- NN+1 correctly keeps the candidate in the SUT role and freezes predecessor
  judge bytes and fixtures (AD-8).
- The seven source open questions are all either deferred with a re-decision
  condition or constrained by an AD.

## Gate Result

Do not finalize the spine until H1-H3 are resolved. M1 and M2 should be
resolved in the same update because they affect the requested four-field
contract and NN+1 promotion authority.
