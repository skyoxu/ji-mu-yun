# Adversarial Divergence Review

## Verdict

**CHANGES REQUIRED.** The spine resolves the four stated P1 directions, but five architecture-level contracts still permit independently conforming VDD and exact-cover implementations to produce incompatible bytes, identities, policy decisions, or recovery state. These are not implementation-detail preferences because each can change a deterministic pass/fail or authority result.

## Review Method

For each finding, this review constructs two downstream implementations that follow every applicable AD literally, then tests whether their artifacts remain interoperable. Only important cross-implementation divergence is reported.

## P1-1 - `repository-canonical-json.v1` does not determine one byte sequence

**Affected:** AD-2, AD-3, AD-5, AD-6

**Implementation A:** Uses Python-style JSON with literal UTF-8 for non-ASCII characters, escapes only required control characters, and sorts keys by Unicode scalar/code-point order.

**Implementation B:** Emits every non-ASCII character as `\uXXXX` (including surrogate pairs for non-BMP characters), optionally escapes `/`, and sorts the decoded keys before serialization.

Both implementations satisfy the current words: UTF-8 output, recursively sorted keys, compact separators, preserved strings without Unicode normalization, and the narrow JSON value set. Nevertheless, they hash different bytes for the same value. The declaration that golden vectors are normative does not close the contract until the exact vectors and the serializer behavior they prove are owned and versioned.

**Required closure:** Define the exact string escaping algorithm, permitted Unicode scalar domain/surrogate rejection, object-key comparator, integer lexical form and range, and whether `/` may be escaped. Either name a single repository serializer implementation as the normative byte producer plus frozen cross-language vectors, or state a complete byte-level algorithm. Independent recomputation must reject non-canonical alternate spellings rather than merely parse them to the same value.

## P1-2 - Fingerprint payloads list meanings but not a canonical schema

**Affected:** AD-3, AD-6

**Implementation A:** Hashes `ordered_authoritative_companion_identities` as an array of `{path, role, sha256}` objects and represents shard ranges as `{start_byte, end_byte, start_line, end_line}`.

**Implementation B:** Hashes companion identities as ordered manifest-entry hashes and ranges as half-open two-integer arrays plus a separate line-count field.

Both bind every fact required by AD-6, use the AD-3 domain envelope, and preserve order, but their `run_aggregate_fingerprint.v1` and `shard_reuse_fingerprint.v1` never match. Similar ambiguity remains for validator identity, prompt schema/version identity, policy identity, shard identity, and the comparator used for “ordered” companion/source collections.

**Required closure:** Put each fingerprint behind an owned versioned schema or an explicit field-by-field projection table containing exact field names, value types, null/absence rules, collection ordering keys, range coordinate system, and nested identity representation. Golden vectors must include the complete envelope bytes and expected digest for both fingerprint kinds.

## P1-3 - Canonical Spec Package conformance lacks one physical package contract

**Affected:** AD-1, AD-4, AD-5

**Implementation A:** Treats YAML frontmatter in `SPEC.md` as the package descriptor, reads `schema_version`, `sources`, and `companions` there, and derives roles from frontmatter plus companion metadata.

**Implementation B:** Requires a root package-manifest sidecar carrying the schema/version and typed role graph, treats `SPEC.md` frontmatter as descriptive, and hashes the sidecar as part of the package.

Both can claim one `SPEC.md` root, a schema/version marker, typed complete roles, contained paths, parseable metadata, and deterministic VDD manifest construction. A package accepted by one is rejected by the other, and their manifest source-entry universes differ.

**Required closure:** Assign `canonical-spec-package.v1` a single machine-readable descriptor location and schema owner. Specify root discovery, path resolution base, allowed multiplicity, role encoding, relationship encoding, inclusion/exclusion of descriptor and architecture companions in the directory/source manifest, unknown-field/version behavior, and the exact transition for adopting this spine during `bmad-spec refresh`. Producer provenance should remain non-authorizing as AD-1 intends.

## P1-4 - Runtime-policy validity is defined, but selection authority is not

**Affected:** AD-6, AD-7, AD-9

**Implementation A:** Lets the exact-cover caller supply any schema-valid profile; it chooses very high retry ceilings and permissive shard/presentation limits.

**Implementation B:** Accepts only a repository-pinned current profile selected by VDD source freeze; caller input can reference but cannot replace it.

Both canonicalize the profile, bind its hash into fingerprints, and report it in receipts. Their runs are intentionally hash-distinct, but the first implementation allows an untrusted caller to choose the operational policy that controls cost, stop-loss, quarantine, and evidence shape. AD-9's authorization preflight says it binds “policy” but does not identify the expected policy authority, so it cannot distinguish an approved profile from an arbitrary valid one.

**Required closure:** Name the policy owner and selection point, define the approved-profile registry/current-profile binding, state whether VDD freezes the selected policy identity into the run/source manifest, and require exact-cover plus authorization preflight to compare against that authoritative identity. Define override authority and evidence explicitly; schema validity alone must not grant policy-selection authority.

## P1-5 - Recovery has no deterministic checkpoint ordering or state-transition contract

**Affected:** AD-6, AD-7, AD-9, Consistency Conventions / Recovery

**Implementation A:** Selects the newest valid checkpoint by wall-clock `created_at`; after a retrying worker writes later evidence, it resumes that worker's shard state.

**Implementation B:** Selects by predecessor lineage and monotonically increasing stage/attempt sequence; it ignores the later timestamp when it belongs to an abandoned fork.

Both consume a “newest valid checkpoint and live blocker,” invalidate identity drift, preserve target bytes, and use hash-bound artifacts. Under concurrent, retried, or clock-skewed runs they resume different shard sets, counters, blockers, and next legal actions. The spine also does not say which outcome/stage transitions are legal or how terminal `blocked`, `conformant`, and semantic-handoff states interact with later checkpoints.

**Required closure:** Define a versioned run/checkpoint state machine with terminal states, legal transitions, monotonic sequence/attempt identity, predecessor rules, fork handling, atomic publish semantics, and a deterministic checkpoint-selection tuple. A live blocker must be scoped and ordered against the same run identity; timestamps and filesystem modification order must not be authority.

## Exit Condition

Finalize can pass this lens when the spine closes the five contracts above directly or defers them to named, single-owner versioned schemas whose required fields and selection authority are fixed in the spine. Merely adding future fixtures without fixing the normative algorithm/owner would leave both adversarial implementations conformant.
