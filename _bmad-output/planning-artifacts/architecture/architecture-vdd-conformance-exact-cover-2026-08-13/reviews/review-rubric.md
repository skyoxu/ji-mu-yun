# Architecture Reviewer Gate - Rubric Walker

## Verdict

**HIGH findings remain.** The spine has the right ownership model and covers all seven capabilities at the mapping level, but four feature-owned divergence points are still under-specified or contradictory. Two conforming producer/consumer implementations could compute different identities, accept different runtime policies, or route ambiguity differently.

## Review Basis

- `ARCHITECTURE-SPINE.md`, read in full.
- `bmad-architecture/references/reviewer-gate.md`, read in full.
- Canonical SPEC kernel, authority/data, execution/recovery, execution policy, and acceptance contract, read through every reported `Partial` continuation to `Complete`.
- Brownfield contracts checked: repository canonical JSON rules in `docs/skill-input-consumption-contract.md`, the deterministic output/token convention in `docs/model-visible-tool-round-contract.md`, and the current Strict VDD ownership/lifecycle standard.

## Important Findings

### HIGH-1 - `repository-canonical-json.v1` is not yet a byte-complete serialization contract

**Location:** AD-2, AD-3, AD-4; golden-vector paragraph.

**Why it matters:** AD-2 fixes encoding, broad key sorting, separators, value types, and normalization policy, but it does not specify the object-key comparator, JSON string escaping, integer lexical form/range, or parser treatment of invalid Unicode scalar data. For example, a Python-style Unicode-code-point key sort and an RFC-8785/ECMAScript-style UTF-16 sort diverge for some non-BMP/BMP key pairs; serializers may also emit a literal non-ASCII character or a `\uXXXX` escape while satisfying the current prose. Golden vectors detect one implementation's divergence but do not define which bytes are authoritative when the algorithm is incomplete.

**Checklist impact:** Every Rule must be enforceable and shared identity rules must prevent producer/consumer divergence.

**Recommended disposition:** **Autofix in the spine.** Either normatively bind the already verified repository serializer with its exact implementation semantics/version, or define: unsigned UTF-8-byte key ordering (or another single comparator), required string escaping including surrogate rejection, canonical integer grammar/range, and exact parser constraints. Keep golden vectors as verification, not as a substitute for the algorithm.

### HIGH-2 - The SPEC's shard identity contradicts AD-2/AD-3 and has no reconciliation disposition

**Location:** AD-2, AD-3, Consistency Conventions `Hash values`, SPEC Reconciliation.

**Why it matters:** AD-3 says every hash input is the canonical JSON domain envelope and the consistency table says hash values carry a `sha256:` prefix. The normative execution policy instead defines `shard identity` as SHA-256 over a newline-delimited `vcec-shard-v1` byte payload and returns 64 lowercase hex without a prefix. The reconciliation table amends generic hash/fingerprint references but never ratifies, amends, or explicitly exempts this exact shard-ID rule. Implementers can reasonably choose either authority and produce incompatible shard reuse keys and fixtures.

**Checklist impact:** No feature-owned dimension may be left silently conflicting; ratification must not contradict brownfield/SPEC inputs.

**Recommended disposition:** **Autofix in the spine.** Explicitly choose one: ratify shard identity as the sole versioned non-JSON domain-hash exception, including its unprefixed representation; or amend it to an AD-3 typed envelope and require the subsequent `bmad-spec refresh` to replace its existing payload and fixtures.

### HIGH-3 - Runtime-policy ownership is decided, but policy selection authority is not

**Location:** AD-6, AD-7, dependency diagram, Deferred.

**Why it matters:** A profile hash prevents unnoticed changes, but AD-7 allows any schema-valid finite positive values and does not state who owns the approved profile registry, who selects the profile for a run, or how VDD and exact-cover prove the same approved policy identity. A caller could select `1`-byte shards or extreme retry maxima and still satisfy the Rule, while the original SPEC treats its v1 policy as fixed authority. This is an operational/safety envelope owned by the feature, not mere tuning.

**Checklist impact:** Operational dimensions must be decided or explicitly deferred without leaving two units free to diverge.

**Recommended disposition:** **Autofix in the spine.** Assign one repository owner for a versioned allowlisted policy registry; require VDD to freeze an approved policy ID/hash into the run/source-freeze input and exact-cover to independently resolve/re-hash it; reject caller-only, unknown, or unapproved profiles. Numeric values may remain deferred, but selection and successor authority cannot.

### HIGH-4 - CAP-3's semantic escalation and repair handoff are mapped but not architecturally specified

**Location:** AD-9 and `CAP-3 ambiguity isolation` capability map.

**Why it matters:** AD-9 establishes read-only authority and generic recovery, but it does not make the SPEC's decisive route executable: deterministic structure/binding/mapping checks must close first; only genuine requirement ambiguity can produce `bootstrap-upstream-plan`; launch needs explicit authorization; pre-implementation review identity must stay distinct from post-implementation assurance; and the result must become a current hash-bound `vdd-repair-input.v1` consumed only by explicit VDD repair. Without those predicates and ownership edges, two adapters can disagree about when Bootstrap is allowed or use diagnostics/checkpoints directly as repair authority.

**Checklist impact:** CAP coverage must be substantive, not only a row in the capability map; the Rule must prevent the stated lifecycle divergence.

**Recommended disposition:** **Autofix in the spine.** Add the eligibility predicates and typed handoff/re-entry chain to AD-9 (or a dedicated AD), including explicit authorization, separate lifecycle identities, repair-input schema/hash binding, and mandatory exact-cover rerun after VDD creates a new requirements identity.

## Checklist Tail

- **Capabilities:** CAP-1 through CAP-7 are all named and assigned, but CAP-3 is not yet closed by an enforceable Rule as described above.
- **Dependency direction:** The inward canonical core, VDD producer/lifecycle owner, read-only exact-cover consumer, and existing authorization owner are consistent with the brownfield Strict VDD control model.
- **Deferred dimensions:** Deployment topology, filenames, concrete thresholds, and performance tuning are acceptable deferrals once runtime-policy selection authority is fixed. No separate infra/provider/database decision is needed for this offline toolchain feature.
- **Current technology:** No problematic external stack or unpinned library is selected. Reusing the repository's canonical JSON family is directionally current, but its exact bytes still need the HIGH-1 closure.
- **No additional medium/low findings reported.**
