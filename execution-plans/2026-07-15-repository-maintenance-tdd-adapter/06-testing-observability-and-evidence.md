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
15. Exact cumulative candidate diff equality across Git, immutable S0-S6 lineage fold, and candidate manifest.
16. Binary-safe deterministic test-patch reproduction in a disposable Git for Windows repository, including untracked binary add, modification, and deletion.
17. Explicit S7-to-S6 reference with independent run IDs and recovery/event/successor-derived supersession rejection.
18. Runtime Bootstrap P2 disposition and applicable verifier source binding.
19. Source section identity and line/question selector drift with unchanged coverage union.
20. Active requirement removed from every slice while remaining in the registry.
21. Restricted-token junction creation and evidence-read containment without nested writable-directory assumptions.
22. S0 ownership duplicate as the behavior-specific observed RED.
23. Protected-tree hash and count drift for all three shadow plans.
24. Positive and negative candidate/review/preflight/disposition identity binding.
25. Immutable manual-pause blocker, successor re-entry selection, Round 4 rejection, and blocked predicate status.
26. Clean-checkout validation without clarification or repair logs.
27. Executable acceptance registry, derived requirement quality, and exact earliest-phase mapping.
28. Command descriptor versus RED/GREEN/REFACTOR invocation expectation separation.
29. Immutable Capsule context, predecessor chain, path, and predicate authority.
30. Minimized attempt evidence, request/response/diff/decision binding, partial failure, stage uniqueness, and event lineage.
31. Bootstrap finalized-run envelope success, stale profile/control-plane/validator/artifact rejection, and empty authorization set.

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
- stale Capsule context or predecessor hash;
- raw or sensitive backend request/response persistence;
- missing decision, stale decision binding, forbidden diff, or duplicate accepted stage.

## Evidence Ownership

Execution plans own contract instances, plan-specific predicates, fixtures, evidence intent, and immutable evidence references. The Skill owns common schemas and executables. Runtime evidence and result envelopes live only under `logs/tdd-adapter/**`.

Minimum run files:

- `prepare-result.json`;
- `baseline-manifest.json`;
- `red-result.json`;
- `green-result.json`;
- `refactor-result.json`;
- `candidate-result.json`;
- `candidate-lineage-manifest.json`;
- `candidate-supersession-proof.json` for S7 predecessor consumption;
- `diagnostics.jsonl`;
- `run-events.jsonl`;
- `recovery-state.json`.

Persisted protocol layout:

```text
context/<capsule-id>/context-manifest.v1.json
context/<capsule-id>/slice-capsule.v1.json
candidate-slice-effect.v1.json
baseline-file-manifest.v1.json
baseline/files/<repository-relative-snapshot>
attempts/<attempt-id>/backend-request.v1.json
attempts/<attempt-id>/backend-response.v1.json
attempts/<attempt-id>/diff-manifest.v1.json
attempts/<attempt-id>/adapter-decision.v1.json
attempts/<attempt-id>/result-files/<repository-relative-snapshot>
run-events.jsonl
attempt-ledger-manifest.v1.json
```

Every file binds the same run, plan, contract, slice, source, validator, command registry, and candidate identities. Stage files also bind the accepted attempt decision and Capsule/context identities while recording command identity, observed exit, timestamp, and predecessor-stage hash; RED records the declared selector and stable failures. The S6 candidate directory contains a schema-valid cumulative `changed-files.json`, `candidate-lineage-manifest.json`, reproducible `test-diff.patch`, final context/Capsule, attempt-ledger manifest, raw event-log hash, final canonical event hash, accepted-attempt folds, and accepted decisions. The S7 run contains `candidate-result-ref.json` plus a supersession proof referencing current recovery/events/successors; it never infers activity from its own run ID.

Every slice command receives `--run-dir`, `--red-result`, `--green-result`, and `--refactor-result`; implicit latest selection and repository-wide evidence scans are forbidden. S6 additionally receives `--candidate-result`. Only S7 receives both `--candidate-ref` and `--bootstrap-run`; its `--candidate-result` uses an explicit independent `<candidate-run-id>`.

Raw clarification and repair evidence remains under `logs/**`, but clean-checkout authorization consumes only minimized projections in `schemas/clarification-decisions.v1.json`, immutable `schemas/review-blocking-state.v1.json`, `schemas/review-policy-reentry.v1.json`, and `schemas/shadow-protected-baseline.v1.json`.

## Candidate Envelope

The candidate result authorizes only `bootstrap-review`. It explicitly excludes `implementation-accepted`, protected handoff, and release. It binds its S6 run ID, cumulative candidate diff manifest, test patch, final context-manifest hash, final Capsule hash, attempt-ledger manifest hash, raw `run-events.jsonl` hash, final canonical event hash, accepted-attempt fold, accepted refactor attempt ID, and accepted decision hash. Its worktree identity covers declared write, forbidden, read, dependency, and authority closure through S6; unrelated work outside that closure remains excluded, while Git index or monitored dependency drift blocks.

## Plan Validation Evidence

Plan validation evidence belongs under `logs/vdd-plan-validation/repository-maintenance-tdd-adapter/<run-id>/`. A plan-ready result includes the exact plan candidate, source, validator, and fixture hashes plus rule-level evidence.

## Semantic Review

Bootstrap remains the only semantic finding authority for a change cycle. Quick Dev or another reviewer may not run a competing semantic review. Zero findings is valid. P0/P1 require independent verification under current Bootstrap policy; P2 handling follows this plan's disposition contract.

No reviewer or verifier is launched by plan creation. Such execution requires explicit user authorization at the implementation/review stage.
