# Validators, Fixtures, And Control Gates

## Composite Entry

`tools/validate_all.py` is the only composite entry. `plan-repair-verified` may pass while the plan is blocked, but it authorizes no readiness or implementation state. Every predicate blocked by the Round 3 disposition returns nonzero with machine status `blocked`.

## Required Checks

1. Required books and unique ownership.
2. Durable closed-set authority manifest, clarification projection, immutable Round 3 blocker, and successor re-entry selector; no required clean-checkout authority may resolve under ignored `logs/**`.
3. UTF-8 JSON parsing and strict validation against declared schemas; unsupported schema keywords fail closed.
4. Markdown local-link closure.
5. Requirement uniqueness, quality, owner, phase, acceptance, source, status, and evidence intent.
6. Exact agreement among requirement registry, 97 ledger, 98 audit, and 99 coverage.
7. Explicit `ADDED`, `MODIFIED`, `REMOVED`, and `RENAMED` delta semantics.
8. Implementation-contract vocabulary, concrete authority-book hashes, slice dependency graph, command IDs, write/read/dependency sets, and authority policies.
9. Command `shell=false`, environment allowlist, typed placeholders, resolved root containment including reparse points, and raw-shell rejection.
10. Every slice GREEN command has an exact predicate/slice binding and its composite route checks slice-owned outputs or evidence.
11. Source section IDs and selectors are derived from the hash-bound source structure and must match the coverage machine owner exactly.
12. The union of all slice requirement IDs equals the complete active requirement registry.
13. Shadow slices compare protected-tree hashes and file counts against an independent pre-backfill baseline.
14. Every slice consumes explicit stage evidence; S6 folds immutable S0-S6 run artifacts and proves exact Git/candidate/lineage equality plus reproducible patch bytes.
15. S7 derives active-candidate status from recovery/events/successor evidence and consumes finalized Bootstrap artifacts plus runtime P2/verifier source evidence when applicable.
16. Every active requirement maps to one executable acceptance contract whose expected failure IDs equal the referenced negative fixtures' actual stable rules.
17. Validation snapshots plan, source, and validator before and after all checks; drift forces a non-authorizing failure envelope.
18. Persisted Capsule schemas, predecessor hashes, context hashes, containment, and non-authorizing predicate boundaries.
19. Attempt request/response/diff/decision bindings, sensitive-content exclusions, monotonic lineage, decision-last finalization, and one accepted lineage per represented stage.
20. Predicate-to-authority exactness and release exclusion.
21. Shadow backfill exact population, order, additive-only policy, and non-authoritative status.
22. Recovery initial/stale/successor rules, append-only lineage, and successor-policy re-entry exactness.
23. P0/P1 closure, runtime P2 disposition, high-risk deferral rejection, and expiry blocking.
24. Seven-dimensional artifact proof closure from an independent required inventory, with static contract zero-authority, separate runtime type proof, current authority hashes, registered consumer/rule/negative-test mappings, and exact predicate permissions.
25. Full protocol-bundle recomputation rejects fabricated slice effects, omitted accepted attempts, self-asserted final events, and effects not derived from real diffs.
26. The global baseline rejects predicted future paths while a first accepted add is valid and becomes part of the derived cross-slice state.
27. Cross-slice effect hashes are separate from same-slice recovery/supersession lineage.
28. Re-entry rejects empty policy decisions, partial saved envelopes, stale authorization events, and any saved envelope that differs from a fresh Bootstrap producer result.
24. Positive, negative, boundary, stale, mutation, real Git for Windows, and junction containment tests.
25. Validator unit tests executed, not inferred from source markers.

## Stable Rule Families

| Family | Purpose |
| --- | --- |
| `RMAP-STRUCT-*` | Required files, links, UTF-8, and JSON shape |
| `RMAP-REQ-*` | Requirement identity, quality, owner, acceptance, and coverage |
| `RMAP-CMD-*` | Command registry, shell, env, argv, and placeholders |
| `RMAP-PATH-*` | Write set, read set, dependency closure, containment, and overlap |
| `RMAP-HASH-*` | Source, candidate, contract, validator, and evidence freshness |
| `RMAP-TDD-*` | RED, GREEN, REFACTOR, and candidate transitions |
| `RMAP-RECOVERY-*` | Stale, successor, lineage, and resumability |
| `RMAP-REVIEW-*` | Bootstrap boundary and P0/P1/P2 dispositions |
| `RMAP-AUTH-*` | Predicate and release-authority separation |
| `RMAP-OWNERSHIP-*` | Durable owner uniqueness and ADR identifier collision |

## Fixture Contract

[`fixtures/fixture-cases.v1.json`](fixtures/fixture-cases.v1.json) owns deliberate counterexamples. Each case applies one bounded mutation to the valid self-hosted contract and names exactly one expected failure rule. A case that fails for another rule is invalid.

[`fixtures/capsule-attempt-cases.v1.json`](fixtures/capsule-attempt-cases.v1.json) owns protocol counterexamples for stale context, S2 predicate escalation, path escape, stale request binding, raw response persistence, forbidden diff, stale decision hashes, adapter authority escalation, invalid next state, missing decision, duplicate accepted stage, and stale event lineage. [`tools/protocol_guards.py`](tools/protocol_guards.py) validates both the fixture bundle and persisted run directories.

The valid protocol fixture materializes three immutable Capsule revisions and three accepted attempts in exact RED, GREEN, REFACTOR order. Its virtual artifact store supplies actual bytes, baseline snapshots, per-attempt result snapshots, stage results, event-log bytes, and ledger manifest bytes; fixture hashes are recomputed before each bounded mutation.

The minimum cases are:

- valid contract;
- `shell=true`;
- non-allowlisted environment key;
- untyped interpolation;
- raw command field;
- schema-required field removal;
- typed `repo_path` or `plan_path` escape;
- inaccessible host default temp while the repository evidence temp remains writable;
- S1 or later GREEN command replaced with a generic plan validator;
- source section ID or line/question selector drift with unchanged requirement union;
- active requirement removed from every slice;
- duplicate ownership path;
- protected shadow tree or target path drift;
- stale candidate, mismatched Bootstrap identity, missing required check, open P0/P1, or undisposed P2;
- symbolic or stale authority-book hash;
- stale source hash;
- exact and nested/case-insensitive write/forbidden overlap;
- S0 GREEN/exit proof mismatch;
- missing slice dependency;
- backend commit/review authority;
- authoritative old-plan shadow result;
- successor starting as stale;
- high-risk or expired runtime P2 disposition;
- predicate authority escalation.
- ADR-0041 identifier collision;
- stale Capsule artifact bytes, omitted/extra/duplicate manifest refs, ambiguous typed root, or raw blocker payload;
- incomplete or reordered accepted stage set and stale stage-result binding;
- missing lifecycle event or stale event artifact bytes;
- response/diff file mismatch, unapproved command, self-labelled forbidden path, or stale before/after hash;
- stale attempt-ledger root or stale finalized Bootstrap profile envelope.
- candidate changed-file omission, extra path, missing deletion, stale after hash, role drift, or untracked omission;
- candidate accepted-attempt fold mismatch;
- empty or non-reproducible test patch when test changes exist;
- missing S0-S6 lineage slice or stale lineage hash;
- stale S7 candidate-result reference or authoritative supersession proof;
- stale blocker hash or pending re-entry artifact that gains authority;
- empty successor policy, five-field synthetic finalized envelope, self-declared independence, or mismatched change/input lineage;
- fabricated slice effect with valid but unrelated ledger/event hashes, omitted accepted attempt, self-asserted final event, or effect not derived from diff manifests;
- future path predeclared with a null baseline hash, cross-slice use of recovery predecessor fields, or broken previous-slice effect hash;
- empty/malformed verifier evidence, stale P2 transitive evidence, or missing direct finalized-envelope hashes;
- manual capability Boolean that conflicts with current predicate evidence;
- missing or self-inconsistent seven-dimensional artifact proof, inventory omission, static-contract authority escalation, unregistered consumer/rule, or runtime predicate permission mismatch.
- real Git for Windows add/modify/delete/binary-patch behavior and junction escape.

## RED Before Implementation

Before a slice can become ready, run at least one declared invalid fixture and observe its exact stable rule ID. A written test or a clean plan validator alone is insufficient. Evidence belongs under `logs/tdd-adapter/**` or `logs/vdd-plan-validation/**`, not in this directory.

## Bootstrap Separation

The plan-local validator proves deterministic plan/slice/implementation predicates. Bootstrap produces supplemental semantic-review evidence through its existing scope, context-class, preflight, and required-check contracts. Neither substitutes for the other, and Bootstrap does not become release authority.
