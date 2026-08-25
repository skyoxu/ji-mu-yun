# Architecture Spine Rubric Review

Frozen target: `ARCHITECTURE-SPINE.md` dated 2026-08-25.  
Inputs checked: canonical `SPEC.md`, normative `requirements.md` and `open-questions.md`, adopted `addendum.md`, and the installed VDD/Quick Dev skill tree. Mechanical lint passed with zero findings.

## Verdict

**BLOCKED - revise before implementation.** The spine establishes the intended trust-zone direction and disposes of all seven declared open questions, but leaves several implementation-level compatibility decisions unresolved at the feature altitude. In particular, exact result legality, current-artifact resolution, and durable trust-boundary enforcement are not yet independently buildable.

## Findings

### High - AD-6 does not define an executable legal tuple contract

**Evidence:** spine AD-6 (lines 82-86) enumerates states and outcomes but gives only partial pair restrictions; it neither enumerates the FR-13 `failure_family` domain nor defines which `failure_family`/`failure_id` presence and values are legal for each state/outcome pair. AD-12 (lines 136-140) mentions only five of the ten required families. `requirements.md` FR-13 (line 20) makes all ten families normative.

**Divergence:** one executor can serialize `observed-run/pass/expected-red`, another can reject it; similarly, builders can disagree whether `blocked` needs an identity, whether `not-applicable` permits one, and how an invalid artifact retains its original outcome. These choices change completion and recovery behavior.

**Action: autofix.** Add one normative legality table or equivalent schema decision: the complete failure-family enum, per-state/outcome permitted family presence, `failure_id` derivation/format, and an explicit rule for invalidated evidence. Make the coverage gate reject every tuple outside that table.

### High - "current" evidence and append-only publication have no deterministic resolver or concurrency boundary

**Evidence:** AD-5 accepts only "current" observations (lines 76-80); AD-7 requires append-only artifacts (lines 88-92); AD-10 publishes "current live blockers" (lines 124-128). None identifies the authoritative artifact store, run/attempt identity, ordering or supersession rule, atomic publication protocol, or how a coverage result binds the exact input set it evaluated.

**Divergence:** independently built writer/gate/recovery units can select newest-by-clock, newest-by-path, last manifest entry, or a coordinator-provided pointer. Concurrent appenders can produce two candidates that both appear current, and a recovery artifact can refer to a different blocker set than the coverage decision.

**Action: autofix or Deferred.** Bind a single manifest/ledger owner and immutable run/attempt identity; define atomic append plus an explicit current/supersedes selection rule and require coverage/recovery to record the resolved input-manifest identity. If the physical artifact-store protocol is intentionally out of this slice, list it under Deferred and block more than one writer/execution from using the contract until it is chosen.

### High - Trust zones are conceptual only; storage/write authorization and integrity enforcement are silent

**Evidence:** AD-1 says zones may not write another zone's authoritative artifact (lines 52-56), while AD-7 assumes fixed single writers (lines 88-92), but neither rule assigns artifact namespace, credential/capability issuance, filesystem permissions, or verification of writer provenance. `requirements.md` NFR-3 requires that the SUT cannot write or override results, coverage, or completion; FR-17 requires an external consumer to read recovery output.

**Divergence:** a same-host implementation can grant the SUT and judge the same writable directory, while another uses distinct workspaces. Both satisfy the prose direction, but only the latter enforces NFR-3. The external coordinator's read boundary and ability to tamper with artifacts are also unspecified.

**Action: autofix.** Decide the single-node artifact-store boundary: per-zone write paths/capabilities, read-only mounts or equivalent enforcement, provenance verification, and coordinator read-only access. State the failure result when authorization or integrity validation fails (`artifact-integrity` / `invalid-run`).

### Medium - Structural seed and stack misrepresent the brownfield code surface

**Evidence:** the seed names `tools/descriptor_compiler`, `tools/semantic_oracle`, `tools/coverage_gate`, and `acceptance-or-review/` (lines 162-176), while the installed `quick-dev-tdd-adapter/tools/` contains `build_slice_invocation.py`, `run_slice_lifecycle.py`, `stage_artifact_composer.py`, and related current tools, not those three paths; no `acceptance-or-review` skill directory exists. The adopted addendum proposes conditional extraction of `tools/semantic_oracle.py`, rather than asserting it exists. The stack also calls canonical JSON helpers "Existing" without identifying their owning module (lines 153-160).

**Divergence:** implementers can create a parallel tool tree, modify existing lifecycle tools, or treat the new names as already-ratified components. That defeats the spine's stated brownfield ratification requirement.

**Action: autofix.** Replace the seed with the existing entrypoints and name each intended new module as `[ASSUMPTION]`/target state, including its integration point. Name the actual canonical-JSON helper owner, or defer the helper selection until the first schema implementation.

### Medium - Validation ownership for validator/executor/schema changes is asserted but not governed

**Evidence:** AD-4 binds NFR-8 but its rule only assigns receipt/observation writing (lines 70-74); no AD makes positive, negative, and mutation suites mandatory for changes to the semantic validator, executor, or schemas. `requirements.md` NFR-8 (line 40) makes that requirement normative.

**Divergence:** VDD and Quick Dev implementers can both assume the other owns mutation fixtures and the change gate, yielding a compliant-looking artifact pipeline with no required regression suite for the authority components themselves.

**Action: autofix.** Add an AD or extend AD-4/AD-5 to assign suite ownership, required fixture categories, and the gate that rejects a validator/executor/schema change lacking those suites.

## Checklist Coverage

- Real lower-level divergence points: incomplete (findings 1-3 and 5).
- AD enforceability: incomplete (AD-1, AD-5, AD-6, AD-7, AD-10).
- Deferred: all seven supplied spec open questions are explicitly deferred with re-decision conditions (pass).
- Spec capability coverage: CAP-1..CAP-7 map is present, but FR-13 and NFR-8 are not fully operationalized (findings 1 and 5).
- Brownfield ratification: incomplete (finding 4).
- Operational/environmental envelope: not decided or deferred (findings 2 and 3).
- Technology currency: no externally version-pinned technology was introduced; the unverified "Existing" helper claim remains part of finding 4.
