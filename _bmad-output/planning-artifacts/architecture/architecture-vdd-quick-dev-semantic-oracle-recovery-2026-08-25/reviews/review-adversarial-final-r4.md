# Adversarial Review - Final R4 Architecture Spine

**Target:** `ARCHITECTURE-SPINE.md`  
**Scope:** AD-16 pre-execution diagnostic authority and predicate encoding  
**Verdict:** **REJECT - 1 convergence blocker**

The authority split now closes the prior trust-boundary conflict: VDD emits a
hash-free semantic rejection and Quick Dev alone derives the classified
pre-execution diagnostic and `failure_id`. The predicate grammar also fixes
schema, types, key ordering, field ordering, absent values, and UTF-8
transport. One byte-level ambiguity remains.

## Finding

### H1 - "compact JSON" is not a canonical JSON byte encoding

**Reference:** AD-16 line 167.

The SHA-256 input is said to be compact JSON with UTF-8, but JSON permits
multiple byte encodings for the same parsed string and the rule does not select
one. For example, one conforming serializer can emit `"a"` and another
`"\\u0061"`; both use compact separators, UTF-8 without a BOM/trailing
newline, satisfy the stated type constraints, and parse to the same predicate.
Similarly, the rule does not select a Unicode normalization form before
encoding.

Quick Dev implementations can therefore consume the same rejection source,
derive distinct predicate bytes, and emit different `failure_id` values.

**Required convergence rule:** name a canonical JSON serialization profile
(for example RFC 8785/JCS) and a Unicode normalization form, or state an
equivalent explicit escaping and normalization algorithm. SHA-256 must consume
those exact normalized bytes.

## Gate Result

Do not restore `status: final` until H1 is resolved and the gate is rerun.
