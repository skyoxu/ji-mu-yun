# Strict VDD Standard

## Contents

1. Definition
2. Lifecycle and failure routing
3. Authority, intent kernels, and executable contracts
4. Specification deltas and drift control
5. Validator control and result envelope
6. Behavior slices and implementation phases
7. Counterexamples, diagnostics, repair, and re-entry
8. Evidence, freshness, and authority levels
9. LLM review gates
10. BMad interoperability
11. Directory and ledger contract
12. Anti-patterns
13. Assessment rubric

## 1. Definition

Verification-Driven Development places executable verification in the control position of development. A plan is VDD only when validation results can prevent task activation, mutation, phase exit, acceptance, or release.

Testing sections, acceptance prose, large matrices, or many schemas are insufficient by themselves. The critical property is control authority:

```text
no valid evidence -> no authorized transition
```

The plan must distinguish:

- intent correctness;
- contract validity;
- validator validity;
- behavior-slice readiness;
- implementation acceptance;
- release or handoff authority.

## 2. Lifecycle and failure routing

Canonical lifecycle:

```text
Intent
  -> executable invariant/contract
  -> acceptance examples and counterexamples
  -> validator/harness initially proves the missing behavior
  -> smallest vertical behavior slice
  -> implementation
  -> validation and evidence capture
  -> diagnosis
  -> repair
  -> hash-bound revalidation
```

The loop does not always return to validation design:

| Diagnosis | Return to |
| --- | --- |
| intent or authority is wrong | intent/authority |
| contract cannot express the required behavior | executable contract |
| oracle is false, incomplete, or self-invalidating | validator/fixtures |
| slice cannot deliver independently | behavior decomposition |
| implementation violates a valid contract | implementation |
| evidence is stale, conflicting, or from another candidate | evidence/re-entry gate |

Repairs must not rewrite prior failures. Start a new run when target hashes change and bind it to the predecessor run and affected finding/rule IDs.

## 3. Authority, intent kernels, and executable contracts

Start from one approved intent kernel. When no durable kernel exists, define:

- why the change exists;
- capabilities, each with stable ID, intent, and success signal;
- constraints that rule out real design choices;
- explicit non-goals;
- a concrete overall success signal;
- assumptions and open questions that remain non-authoritative until resolved.

If a BMad `SPEC.md` package exists, inherit its `CAP-N` identities, `companions`, and append-only `.memlog.md` instead of creating competing IDs or rewriting its decisions. Bind the exact source and companion hashes used by the plan.

Every normative requirement needs:

- stable ID;
- approved source;
- accountable owner;
- first required phase;
- affected consumers/routes;
- executable acceptance ID;
- failure severity/family;
- evidence intent;
- status and deferral/recheck contract.

Contracts must be machine-readable where a machine consumes them. Prose owns rationale; schemas/registries own fields, enums, predicates, and state transitions.

Avoid duplicate authority. A plan references durable standards and ADRs rather than copying thresholds or security policy.

Deferral is not verification. An allowed deferral retains its status and must include owner, affected scope, severity, non-impact proof, expiry/recheck trigger, and exact closure test.

## 4. Specification deltas and drift control

Represent changes to an existing behavior contract with explicit delta operations:

- `ADDED` - new requirement or capability with a new stable ID;
- `MODIFIED` - complete replacement contract while retaining the stable ID and previous revision reference;
- `REMOVED` - behavior removed with reason, migration/consumer impact, and a counterexample proving the old path is no longer authorized;
- `RENAMED` - name-only change with old/new names and unchanged stable identity.

A partial `MODIFIED` block is invalid because archive/merge would lose omitted behavior. A plan that changes an existing requirement but labels it `ADDED` creates conflicting authority and must fail.

Bind every delta to:

- prior source/spec revision and hash;
- current proposed contract hash;
- affected consumers, acceptance IDs, validators, fixtures, and slices;
- compatibility/migration decision;
- revalidation command and expected rule IDs.

Create a requirement-quality checklist separate from implementation tests. It checks that every requirement is one observable behavior, uses an intentional normative strength, has executable acceptance, covers important negative/boundary cases, avoids implementation leakage, and maps to exactly one current delta/owner. A checked checklist is evidence only when generated or verified against the current contract hash.

Any source, companion, inherited architecture rule, validator, fixture, or candidate change invalidates evidence bound to the previous hash. Recompute generated views and rerun cross-artifact consistency analysis before implementation authorization.

## 5. Validator control and result envelope

### Composite entry

Provide one documented entry that runs every required readiness check. The command must produce:

- nonzero exit for command/validation failure;
- machine-readable overall status;
- stable failed rule IDs;
- evidence/candidate hashes;
- explicit skipped checks and authorized non-applicability;
- a statement of what the result does and does not authorize.

If a command intentionally returns zero for `blocked`, `incomplete`, or `awaiting_verification`, every caller must be tested to consume the machine status rather than exit code alone.

### Validation result envelope

Every authorizing composite result should use a versioned machine envelope with at least:

```json
{
  "schema_version": "vdd.validation-result.v1",
  "run_id": "...",
  "predicate": "plan_ready",
  "status": "pass|fail|blocked|incomplete",
  "candidate_hash": "sha256:...",
  "current_candidate_hash": "sha256:...",
  "source_hash": "sha256:...",
  "validator_version": "...",
  "authorizes": ["plan-ready"],
  "does_not_authorize": ["phase-authorized", "implementation-accepted", "release-ready"],
  "checks": [
    {"rule_id": "VDD-...", "status": "pass|fail|skip", "evidence": ["..."]}
  ],
  "diagnostics": [],
  "generated_at": "..."
}
```

A `pass` is invalid when candidate and current candidate hashes differ, any required check is missing/non-pass, authorization is unnamed, or higher authority is unbounded. A fresh process exit without a valid envelope is a command result, not a readiness result.

### Validator location and identity

- Keep validator source and tests in version-controlled source directories.
- Do not use `logs/` as the only copy of an authorizing executable.
- Bind result evidence to validator/rule version.
- Prevent a task from weakening the validator that authorizes that same task when the gate protects security, release, or irreversible mutation.
- Use an independent protected verifier when repository-local self-validation is insufficient.

### Structural and semantic checks

Validate at least:

- required files and unique owner books;
- UTF-8, links, JSON parseability, and full supported schema validity;
- requirement ID sequence/uniqueness and exact source coverage;
- owner, phase, acceptance, status, and evidence references;
- state-machine transition ownership and predecessors;
- open findings/blockers and deferral expiry;
- generated view freshness;
- current candidate/source/validator hashes;
- documentation synchronization and future/current claims.

Do not accept source-marker checks as proof that tests pass. Execute the tests through the composite entry.

### Counterexample protection

For each important rule, include:

- valid fixture;
- invalid fixture targeting only that rule;
- boundary fixture;
- stale/hash-mismatch fixture;
- mutation that removes or weakens the rule;
- expected stable failure ID.

Negative fixtures must assert the intended error so an unrelated constraint cannot keep them falsely green.

## 6. Behavior slices and implementation phases

Each slice should deliver one observable behavior or one enforcement boundary. Record:

- intent and requirement IDs;
- contracts consumed/produced;
- preconditions and predecessor evidence;
- production files/consumers expected to change;
- tests first, including negative cases;
- evidence path and candidate hash;
- rollback/recovery;
- exit predicate and next allowed transition.

Before implementation, prove the slice's validator is red-capable: run one invalid or mutation fixture and observe the expected stable rule ID for the missing behavior. A test merely written but never executed does not satisfy this gate.

Cross-cutting irreversible decisions, shared contracts, validator baselines, and diagnostic vocabulary precede feature implementation. Do not postpone foundational control gates to a final consolidation phase.

Only one phase should own a transition. Phase exit evidence must be durable, append-only/run-scoped, and bound to the exact candidate and predecessor state.

## 7. Counterexamples, diagnostics, repair, and re-entry

### Repair baseline and candidate application

Before repairing an existing directory:

1. inventory every target artifact and canonical role;
2. record a baseline manifest containing relative paths, content hashes, source/validator versions, and current status;
3. run current validators read-only and preserve baseline failures;
4. define the proposed spec deltas and affected evidence;
5. apply repairs to a new candidate state;
6. rerun the same applicable validators plus new regression counterexamples.

If any target or authority input changes after baseline capture, mark the candidate/evidence stale and create a new baseline or run. Do not overwrite failed history. `draft`, `blocked`, and `quarantined` are valid safe outcomes when the candidate cannot be authorized.

Diagnostics are control data, not log prose. A diagnostic record should include:

- diagnostic/rule ID;
- requirement and acceptance IDs;
- failure family and severity;
- candidate/source/validator hashes;
- triggering input and required state;
- observed bad outcome;
- guard analysis;
- account/project/task/run scope where relevant;
- repair owner and remediation ID;
- rerun command and expected rule set;
- predecessor run and superseded finding IDs;
- current status and next allowed transition.

Repair must consume the newest authoritative blocker, not an old assistant summary. It must preserve failed evidence, apply to a new candidate, and rerun the same applicable validators plus regression counterexamples.

Rollback/quarantine belongs in the contract when failed mutation could corrupt active state. A failed acceptance must never be reported as mutation success.

## 8. Evidence, freshness, and authority levels

Bind evidence to:

- exact candidate/source hashes;
- Git tree/commit where applicable;
- contract/schema/validator versions;
- input manifest and scope;
- run ID and timestamps;
- predecessor exit result;
- reviewer/verifier identity or process attestation when authoritative.

Separate these authority levels:

- plan-readiness: documents and machine contracts are internally implementable;
- phase authorization: predecessor and route-specific gates permit work to start;
- implementation acceptance: actual behavior passes tests/smoke/runtime evidence;
- protected handoff/release: independent authority permits downstream or production transition.

Never infer a higher level from a lower one.

Before any success claim, identify the full proof command, run it against the current candidate, read the complete result/exit/failure counts, and cite the resulting evidence. Old output, an earlier candidate, a partial test target, or a successful command invocation cannot support the claim.

## 9. LLM review gates

LLM reviewers are untrusted candidate producers unless an accepted policy explicitly says otherwise.

Requirements:

- zero findings is valid;
- no minimum finding quota;
- exact current-revision evidence and line range;
- concrete `trigger -> required state -> bad outcome`;
- named existing guard gap;
- complete context closure mapped to concrete artifacts;
- accountable authority, consumer, and executable validator reference;
- deterministic gateway rejection of incomplete candidates;
- independent verification for blockers;
- bounded review/repair lifecycle.

Dedup must not collapse distinct failures merely because they quote the same lines. Fingerprint/evidence-root identity includes:

- route/version;
- artifact and exact evidence hash;
- line range;
- normalized failure tuple;
- finding family/dimension;
- authority revision.

When model, reasoning, tool access, or session separation affects authority, record verifiable execution/process evidence. A prompt saying which model to use is not proof that it was used.

`readArtifacts` is an attestation unless tool traces prove reads. Do not describe self-reported coverage as mechanical proof.

## 10. BMad interoperability

BMad artifacts are optional first-party inputs, not runtime dependencies. When present, map them without duplicating authority:

| BMad artifact | VDD role | Required treatment |
| --- | --- | --- |
| `SPEC.md` + companions | intent/capability contract | inherit stable `CAP-N`; bind source and companion hashes |
| `.memlog.md` | append-only decision lineage | consume newest live decision; retain superseded history |
| `ARCHITECTURE-SPINE.md` | inherited invariants | cite stable `AD-n`; never weaken locally |
| FR/NFR/UX-DR coverage | requirement sources | map to stable requirement/acceptance IDs and revalidate coverage |
| epics/stories | behavior-slice candidates | require independent completion and no forward dependency |
| story `baseline_commit` | candidate baseline input | combine with plan/source/validator hashes |
| BMad status/checklist | candidate state | never treat as VDD authorization without executable result |
| Dev Auto triage log | diagnosis input | map intent gap/spec defect/patch/defer to VDD failure families |

BMad user-value epics and VDD control-plane prerequisites are distinct. Shared contracts, validator baselines, diagnostic vocabularies, and irreversible decisions may precede feature stories as phase gates; do not disguise them as user-value epics.

Use BMad's root-cause routing and bounded re-derivation patterns, but replace self-reviewed readiness with the composite validator, hash-bound evidence, and protected verifier where required. Never inherit a fixed finding quota from an adversarial reviewer.

## 11. Directory and ledger contract

Preferred ownership map for a new split directory:

| Artifact | Owner responsibility |
| --- | --- |
| `00-index.md` | status, routing, authority, commands, phase order |
| `01` | intent, current state, authority, non-goals |
| `02` | executable contracts, invariants, state vocabularies |
| `03` | validators, fixtures, mutation rules, gate predicates |
| `04` | behavior slices and dependency order |
| `05` | diagnostics, repair, rollback, re-entry |
| `06` | testing, evidence, observability, rollout |
| `07` | implementation phases and exits |
| `08` | risks, stop conditions, DoD, glossary |
| `96` | global review and validation standard |
| `97` | stable requirement ledger |
| `98` | source-to-split semantic audit |
| `99` | exact owner/phase/source coverage |
| `schemas/` | machine contracts |
| `fixtures/` | positive/negative/mutation inputs |
| `tools/` | version-controlled composite validator |
| `tools/tests/` | validator and control-state tests |

The source coverage map and requirement ledger must agree exactly. Generated Markdown views must derive from machine owners and must not become independent authority.

## 12. Anti-patterns

Reject these patterns:

- “Tests will be added during implementation.”
- Validator exists only as prose or a command under ignored logs.
- Validator counts keywords instead of parsing contracts.
- Plan validator PASS is called code-complete.
- Matrix generation success authorizes the next phase without a separate current result.
- Reviewer output directly blocks work without a deterministic gateway.
- Fixed minimum finding counts.
- Required context classes exist only as prompt text.
- Failure tuple, guard, authority, consumer, or validator references are checked only for non-empty strings.
- Dedup omits failure identity and merges different bugs on the same lines.
- Full test suite is represented by checking that test function names exist.
- Existing evidence is overwritten during repair.
- Same run is mutated after verification instead of starting a new hash-bound run.
- New run lacks predecessor/supersession/closure lineage.
- Local plan validator substitutes for a protected handoff/release verifier.
- Recovery proceeds from assistant prose instead of current acceptance/diagnostic authority.
- Future capabilities are documented as active before exit evidence exists.
- BMad `ready-for-dev`, `review`, or `done` state is treated as executable VDD authorization.
- An existing requirement is changed without an explicit delta and prior revision/hash.
- Repair begins without a baseline manifest or reuses evidence after target hashes change.
- A success claim cites an old, partial, or unparsed validation run.
- Skill package fixtures are described as proof of fresh-context Agent compliance.

## 13. Assessment rubric

Classify separately:

### VDD-oriented

The plan mentions contracts, validators, gates, diagnostics, and repair but control is partly prose or self-reported.

### Plan-level VDD qualified

The composite plan validator, machine contracts, fixtures, mutation tests, source coverage, and fail-closed readiness status are executable and pass. This still does not prove implementation.

### Implementation VDD qualified

Behavior slices are implemented under the gates, actual tests/smoke/runtime evidence pass, failures enter structured repair/re-entry, and phase transitions are machine-authorized.

### Protected production VDD qualified

Independent/protected verification, execution identity, non-bypassable entrypoints, release/handoff authority, rollback, and evidence custody are operational and tested.

Report the achieved level and every missing higher-level condition. Never compress these levels into one PASS.
