# Normative Requirements and Acceptance Signals

This companion preserves the complete requirement IDs from the PRD. It is normative, not provenance-only.

## Semantic contract and preflight

- **FR-1:** Define `semantic-verification.v1` with oracle_id, covers_acceptance_ids, oracle_class, test_selector, subject_role, required_case_roles, red_failure_family, expected_failure_ids, green_expected_observations, minimum_executed_cases, independent_judge_required, abstract `case_source_refs` and `case_producer_ref`. VDD does not generate command, receipt or hash.
- **FR-2:** Reject file-existence-only behavior RED, missing exact coverage, matrix without a real case producer, missing positive/negative/mutation fixtures, prose-only rollback and self-judging definitions.
- **FR-10:** Require complexity_class, verification_lane, context_lookup_required, context_lookup_reason, minimum_red_scope and upgrade_conditions. Upgrade for multi-root, cross-module, contract or runtime scope; semantic gaps route to VDD repair; unexpected green becomes regression or requires independent proof of existing behavior.

## Execution, evidence and completion

- **FR-3:** Freeze shell=false, executable, argv, cwd, target, fixture hash and RED oracle/test hash; GREEN/REFACTOR cannot replace the RED basis.
- **FR-4:** Independent executor derives `evidence_state`, `verification_outcome`, process receipt, target/fixture identity, execution count, `failure_family`, `failure_id` and actual matrix results. SUT status/observed_result is never accepted; evidence state and verification outcome are distinct fields.
- **FR-5:** Support test-runner and case-matrix adapters; 0 tests + exit 0 fails; matrix cases execute and compare actual results.
- **FR-6:** `implementation-complete` requires all active IDs covered by current observations, receipts, non-zero execution, unchanged hashes and self-hosted independence.
- **FR-7:** Produce semantic-observation.v1 and acceptance-coverage.v1 with schema, time, hashes, coverage and layered failure evidence.
- **FR-11:** Distinguish `evidence_state` values planned-only, observed-run, recovered-run and invalid-run from independent `verification_outcome`; only valid observed/recovered evidence contributes to completion, and evidence state cannot be inferred from outcome alone.
- **FR-12:** Publish recommendation-only fields: recommended_action, forbidden_actions, reason, blocked_by, reusable_observations and invalidated_observations.
- **FR-13:** Classify semantic-contract-gap, expected-red, unexpected-green, task-implementation-failure, test-harness-failure, target-binding-failure, repo-noise, timeout-no-observation, repeated-deterministic-failure and artifact-integrity as `failure_family` values with deterministic `failure_id` members. `verification_outcome` remains independent: repo noise is not RED; harness failure is not GREEN; timeout is neither pass nor fail; repeated deterministic failure stops blind reruns.
- **FR-14:** Re-run affected oracles for code/test/schema/validator changes; reuse for ordinary non-semantic docs; recompute coverage for requirements/acceptance/plan changes; invalidate RED/GREEN/REFACTOR on fixture/target/command changes. Each oracle publishes reusable, invalidated_by and required_next_action.
- **FR-15:** Profiles fast-ship, standard and self-hosted control cost/scope only; authenticity invariants remain mandatory.
- **FR-17:** Quick Dev publishes an external-coordinator-consumable recovery artifact containing current state, evidence identity, recommendations, reusable/invalidated observations and live blockers. The top-level coordinator is out of scope.

## Self-hosted and boundary

- **FR-8:** N→N+1 uses frozen black-box tests, fixtures and judge hash; candidate is SUT only and becomes next executor only after independent validation.
- **FR-9:** Cover all nine required false-green regression cases and block the known false-green implementation while corrected fixtures pass.
- **FR-16:** Keep Review, commit authority, business repository rules and Chapter 5 batch capabilities outside Quick Dev; route only to handoff or stop.

## Non-functional requirements

- **NFR-1:** Frozen descriptors and fixtures produce comparable target, fixture and oracle hashes and receipts; differences are explicit.
- **NFR-2:** Every observation is traceable by Acceptance ID coverage without chat context or manual logs.
- **NFR-3:** SUT cannot write or override judge results, receipts, coverage or completion state.
- **NFR-4:** Execution is non-shell by default and target/cwd are descriptor-bound.
- **NFR-5:** Old plans remain read-only; new create/repair uses the semantic contract.
- **NFR-6:** Legacy contracts cannot authorize new self-hosted completion.
- **NFR-7:** Failures are stable machine-readable layered identities.
- **NFR-8:** Validator, executor and schema changes have positive, negative and mutation tests.
- **NFR-9:** Preflight, state, recommendation, failure and reuse decisions are deterministic and machine-readable.
- **NFR-10:** Profiles, recovery and stop-loss cannot turn timeout, noise, planned-only or unexpected-green into implicit pass.
- **NFR-11:** Recovery trusts current artifact integrity, target/fixture identity and latest live blocker.

## Success metrics

- **SM-1:** 100% active Acceptance IDs have current observation and receipt at completion; validates FR-6/FR-7.
- **SM-2:** All nine false-green fixtures block the candidate and corrected fixtures pass; validates FR-8/FR-9.
- **SM-3:** 100% of new VDD create/repair uses semantic-verification.v1; validates FR-1/NFR-5.
- **SM-4:** Zero executed tests/cases never reaches implementation-complete; validates FR-4/FR-5.
- **SM-C1:** Do not optimize pass rate by reducing fixtures or weakening failure identities.
- **SM-C2:** Do not optimize latency by weakening independent judging, hash stability or receipt completeness.
- **SM-C3:** Do not optimize reuse rate by hiding semantic changes or fixture drift.

## Layered result contract

- **evidence_state:** evidence lifecycle state: planned-only, observed-run, recovered-run or invalid-run. It answers whether evidence exists and is admissible.
- **verification_outcome:** independent run/oracle disposition: pass, fail, blocked, incomplete or not-applicable. It answers what verification concluded.
- **failure_family:** stable category explaining why verification cannot advance, or why an expected failure occurred.
- **failure_id:** specific deterministic identity within a failure family, suitable for expected-failure matching.

These layers are independent: `evidence_state` is not a verification result; `verification_outcome` is not an evidence lifecycle state; a non-failing outcome may carry no failure identity; a failure family groups IDs; a failure ID never substitutes for either state or outcome.
