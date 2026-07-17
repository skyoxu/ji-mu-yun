# Validators, Fixtures, And Control Gates

## Composite Entry

`tools/validate_all.py` is the only composite entry. `plan-repair-verified` may pass while the plan is blocked, but it authorizes no readiness or implementation state. Every predicate blocked by the Round 3 disposition returns nonzero with machine status `blocked`.

## Required Checks

1. Required books and unique ownership.
2. Durable closed-set authority manifest, clarification projection, and fully bound Round 3 blocking disposition; no required clean-checkout authority may resolve under ignored `logs/**`.
3. UTF-8 JSON parsing and strict validation against the declared implementation-contract and result-envelope schemas. Unsupported schema keywords fail closed.
4. Markdown local-link closure.
4. Requirement uniqueness, quality, owner, phase, acceptance, source, status, and evidence intent.
5. Exact agreement among requirement registry, 97 ledger, 98 audit, and 99 coverage.
6. Explicit `ADDED`, `MODIFIED`, `REMOVED`, and `RENAMED` delta semantics.
7. Implementation-contract vocabulary, concrete authority-book hashes, slice dependency graph, command IDs, write/read/dependency sets, and authority policies.
8. Command `shell=false`, environment allowlist, typed placeholders, resolved root containment including existing reparse points, and raw-shell rejection.
9. Every slice GREEN command has an exact predicate/slice binding and its composite route checks slice-owned outputs or evidence.
10. Source section IDs and selectors are derived from the hash-bound source structure and must match the coverage machine owner exactly.
11. The union of all slice requirement IDs equals the complete active requirement registry.
12. Shadow slices compare protected-tree hashes and file counts against an independent pre-backfill baseline.
13. Every slice consumes explicit run/RED/GREEN/REFACTOR paths and verifies current hashes, observed exits, strict time/order, predecessor hashes, and recovery lineage; S6 consumes candidate only, while S7 cross-binds candidate, trusted review profile, preflight evidence, final result, and dispositions.
14. Every active requirement maps to one executable acceptance contract whose expected failure IDs equal the referenced negative fixtures' actual stable rules.
15. Validation snapshots the plan, source, and validator before and after all checks; drift forces a non-authorizing failure envelope with distinct candidate/current hashes.
16. Persisted Capsule schemas, predecessor hashes, context hashes, path containment, and non-authorizing predicate boundaries.
17. Attempt request/response/diff/decision bindings, sensitive-content exclusions, monotonic lineage, decision-last finalization, event chain, and one accepted lineage per represented stage.
9. Predicate-to-authority exactness and release exclusion.
10. Shadow backfill exact population, order, additive-only policy, and non-authoritative status.
11. Recovery initial/stale/successor state rules and append-only lineage.
12. P0/P1 closure, P2 disposition, high-risk deferral rejection, and expiry blocking.
13. Positive, negative, boundary, stale, and mutation fixtures with expected stable rule IDs.
14. Validator unit tests executed, not inferred from source markers.

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

## Fixture Contract

[`fixtures/fixture-cases.v1.json`](fixtures/fixture-cases.v1.json) owns deliberate counterexamples. Each case applies one bounded mutation to the valid self-hosted contract and names exactly one expected failure rule. A case that fails for another rule is invalid.

[`fixtures/capsule-attempt-cases.v1.json`](fixtures/capsule-attempt-cases.v1.json) owns protocol counterexamples for stale context, S2 predicate escalation, path escape, stale request binding, raw response persistence, forbidden diff, stale decision hashes, adapter authority escalation, invalid next state, missing decision, duplicate accepted stage, and stale event lineage. [`tools/protocol_guards.py`](tools/protocol_guards.py) validates both the fixture bundle and persisted run directories.

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
- high-risk P2 deferral;
- expired P2 deferral;
- predicate authority escalation.

## RED Before Implementation

Before a slice can become ready, run at least one declared invalid fixture and observe its exact stable rule ID. A written test or a clean plan validator alone is insufficient. Evidence belongs under `logs/tdd-adapter/**` or `logs/vdd-plan-validation/**`, not in this directory.

## Bootstrap Separation

The plan-local validator proves deterministic plan/slice/implementation predicates. Bootstrap produces supplemental semantic-review evidence through its existing scope, context-class, preflight, and required-check contracts. Neither substitutes for the other, and Bootstrap does not become release authority.
