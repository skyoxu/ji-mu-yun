# Testing, Observability, And Evidence

## Test Layers

1. Contract schema and vocabulary tests.
2. Command registry and typed-placeholder tests, including relative-root escape and absolute Windows path rejection.
3. Plan predicate and authority-set tests.
4. RED/GREEN/REFACTOR state-transition tests.
5. Git index, write-set, execution-read-set, dependency-closure, and unrelated-drift tests, including nested and case-insensitive glob intersection.
6. Recovery, stale, successor, and lineage tests.
7. P0/P1/P2 disposition and expiry tests.
8. Shadow backfill tests for 7-12, 7-07, and 7-11.
9. Bootstrap extension-point integration tests.
10. Supportive, neutral, and competing Skill behavior scenarios.
11. Declared JSON Schema required-field and unsupported-keyword failures.
12. Concrete authority-book hash freshness and RMAP-S0 predicate-proof reachability.
13. Controlled repository-local temporary workspace when host `%TEMP%` is unavailable.
14. Exact predicate/slice proof reachability for every S0-S7 GREEN command.
15. Source section identity and line/question selector drift with unchanged coverage union.
16. Active requirement removed from every slice while remaining in the registry.
17. Restricted-token junction creation without nested writable-directory assumptions.
18. S0 ownership duplicate as the behavior-specific observed RED.
19. Protected-tree hash and count drift for all three shadow plans.
20. Positive and negative candidate/review/preflight/disposition identity binding.
21. Manual-pause projection, Round 4 rejection, and blocked predicate result status.
22. Clean-checkout validation without clarification or repair logs.
23. Executable acceptance registry, derived requirement quality, and exact earliest-phase mapping.
24. Command descriptor versus RED/GREEN/REFACTOR invocation expectation separation.

## Required Adapter Fixtures

- compliant RED -> GREEN -> REFACTOR;
- implementation before RED;
- RED passes immediately;
- RED is a compile or harness error;
- stale RED reused by GREEN;
- write outside allowlist;
- Git index drift;
- execution read-set or dependency-closure drift;
- unrelated worktree drift;
- command uses shell or unapproved environment;
- untyped placeholder;
- backend claims review, done, or commit;
- high-risk or expired P2 deferral;
- new successor starts stale;
- Bootstrap starts before deterministic candidate pass.

## Evidence Ownership

Execution plans own contract instances, plan-specific predicates, fixtures, evidence intent, and immutable evidence references. The Skill owns common schemas and executables. Runtime evidence and result envelopes live only under `logs/tdd-adapter/**`.

Minimum run files:

- `prepare-result.json`;
- `baseline-manifest.json`;
- `red-result.json`;
- `green-result.json`;
- `refactor-result.json`;
- `candidate-result.json`;
- `diagnostics.jsonl`;
- `run-events.jsonl`;
- `recovery-state.json`.

Every file binds the same run, plan, contract, slice, source, validator, command registry, and candidate identities. Stage files also record command identity, observed exit, timestamp, and predecessor-stage hash; RED records the declared selector and stable failures. The candidate directory contains hash-bound `changed-files.json` and `test-diff.patch`.

Every slice command receives `--run-dir`, `--red-result`, `--green-result`, and `--refactor-result`; implicit latest selection and repository-wide evidence scans are forbidden. S6 additionally receives `--candidate-result`. Only S7 receives `--bootstrap-run`.

Raw clarification and repair evidence remains under `logs/**`, but clean-checkout authorization consumes only the minimized projections in `schemas/clarification-decisions.v1.json`, `schemas/review-blocking-state.v1.json`, and `schemas/shadow-protected-baseline.v1.json`.

## Candidate Envelope

The candidate result authorizes only `bootstrap-review`. It explicitly excludes `implementation-accepted`, protected handoff, and release. Its worktree identity covers only declared slice write/read/dependency/authority closure through S6, so unrelated unstaged or untracked work does not invalidate it; Git index drift remains blocking.

## Plan Validation Evidence

Plan validation evidence belongs under `logs/vdd-plan-validation/repository-maintenance-tdd-adapter/<run-id>/`. A plan-ready result includes the exact plan candidate, source, validator, and fixture hashes plus rule-level evidence.

## Semantic Review

Bootstrap remains the only semantic finding authority for a change cycle. Quick Dev or another reviewer may not run a competing semantic review. Zero findings is valid. P0/P1 require independent verification under current Bootstrap policy; P2 handling follows this plan's disposition contract.

No reviewer or verifier is launched by plan creation. Such execution requires explicit user authorization at the implementation/review stage.
