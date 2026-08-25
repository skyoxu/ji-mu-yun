# Explicit Open Questions

The adopted architecture spine resolves authority and identity foundations; it does not silently select the operational policies below. These decisions remain unresolved and must not be inferred by this spec.

## Architecture-Resolved Foundations

- Artifact authority, coherent evidence snapshots, exact-cover path grammar and NN+1 promotion ownership are adopted through AD-13..AD-17.
- Pre-execution and post-execution failure-ID byte representation is adopted through AD-16: NFC-normalized RFC 8785/JCS inputs, raw output-byte hashes and immutable comparator specification identity. This fixes identity construction, not comparator meaning.
- Semantic-change reuse may retain identity-valid observations only while coverage is recomputed from a closed snapshot (AD-9 and AD-14); the detailed reuse decision matrix remains Deferred.
- Frozen predecessor judge, fixture and oracle identities are mandatory for promotion (AD-8 and AD-17); retention, revocation and upgrade operations remain Deferred.

## Still Deferred

1. What comparator types and output normalization rules govern case-matrix assertions and the selected `comparator_spec_identity`?
2. What is the predecessor/frozen judge lifecycle, retention, revocation and upgrade policy?
3. What is the minimum runnable rollback probe interface?
4. What independent evidence proves an unexpected green is an existing behavior rather than a missing RED?
5. What deterministic fingerprint repetition threshold triggers stop-loss for each execution Profile?
6. How are schema versions and hash algorithms selected and kept compatible across platforms?
7. How is the detailed partial-observation reuse matrix represented when requirements, acceptance or plan semantics change beyond mandatory coverage recomputation?
