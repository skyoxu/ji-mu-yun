# Final Rubric Review R2 - Architecture Spine

**Target:** `ARCHITECTURE-SPINE.md` (latest frozen review revision)  
**Lens:** BMad Architecture Reviewer Gate rubric walker, canonical SPEC, and
normative requirements companion  
**Verdict:** **REJECT - one convergence blocker remains**

## Review Scope

This review rechecked AD-1 through AD-17, the legal layered-result
combinations, the Mermaid graphs, and all seven Deferred items. It specifically
tested whether AD-16's RFC 8785/JCS plus Unicode NFC change makes `failure_id`
deterministic for every execution path, as required by FR-13 and NFR-7/NFR-9.

## Convergence Blocker

### H1 - AD-16 canonicalizes only the pre-execution `failure_id` path

**References:** AD-16; FR-4, FR-13; NFR-7, NFR-9; Deferred "Comparator types
and stdout/stderr normalization".

AD-16 fully closes the Quick Dev pre-execution diagnostic path: it fixes the
predicate tree, NFC normalization, permitted values, JCS serialization, UTF-8
bytes, and the SHA-256 input. That is a material improvement.

The executor/judge post-execution path still says only that `failure_id` is
"SHA-256 over taxonomy version, family, descriptor, target, fixture, oracle,
case cell and normalized receipt fingerprint." It does not define the canonical
tree/projection, field ordering, NFC rule, receipt-fingerprint algorithm, or
JCS/byte encoding for those inputs. The Deferred comparator/normalization item
does not repair this: it legitimately defers semantic comparator choices, but
it cannot leave the byte representation of a machine-readable deterministic
failure identity implementation-defined.

Two independent judges can therefore classify the same post-execution timeout
or assertion mismatch to the same family but produce different IDs by choosing
different receipt normalization or concatenation/serialization rules. That
breaks stop-loss fingerprint grouping and recovery routing while each remains
otherwise compliant with the AD text.

**Required convergence rule:** extend AD-16 to prescribe a separate
`postexecution-failure-id-input.v1` JSON value, including exact fields and
receipt-fingerprint projection, and require Unicode NFC, RFC 8785 JCS, UTF-8
without BOM/trailing newline, and SHA-256 over those bytes. Comparator semantics
may remain Deferred, but their selected comparator/normalization specification
must be identity-addressed input to the canonical receipt fingerprint.

## Positive Checks

- **AD-1 through AD-15 and AD-17:** The named writer, immutable boundary, and
  fail-closed rule are present for the relevant trust zones, current snapshot,
  exact-cover path, recovery projection, and NN+1 promotion.
- **Result legality:** AD-6 closes `evidence_state` and
  `verification_outcome` pairs. AD-16 provides an exhaustive family list and
  fixed outcome/family mapping for the listed conditions; the remaining defect
  is deterministic post-execution ID construction, not the state/outcome map.
- **Mermaid:** The trust-boundary flow, NN+1 sequence, and evidence graph agree
  with AD-13 through AD-17: coverage gate owns snapshot and promotion, Quick
  Dev owns blocker/recovery publication, and the coordinator is read-only.
- **Deferred items:** All seven are explicit and carry re-decision conditions.
  They do not reopen artifact ownership, exact cover, completion, recovery, or
  promotion authority. The receipt-normalization portion cannot be deferred
  where it changes the deterministic `failure_id` contract above.

## Gate Result

Do not restore `status: final` yet. Close H1, freeze the resulting revision,
and rerun the complete reviewer set.
