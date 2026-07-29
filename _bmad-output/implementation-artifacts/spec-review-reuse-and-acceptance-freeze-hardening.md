---
title: 'Harden Review Reuse And Acceptance Candidate Custody'
type: 'refactor'
created: '2026-07-28'
status: 'done'
review_loop_iteration: 0
baseline_commit: '29a95dbbda6fff8ba17fe45e387e8df1c48fbff9'
context:
  - '{project-root}/docs/adr/ADR-0049-bootstrap-controller-owned-coverage-and-attempt-retry.md'
---

<frozen-after-approval reason="human-owned intent - do not modify unless human renegotiates">

## Intent

**Problem:** Ordinary review reuse currently identifies a dirty checkout by `HEAD` and `git status --short`, so changed bytes at the same dirty paths can be mistaken for the same input. Refactor implementation acceptance validates manifest JSON hashes but does not verify that declared candidate hashes match immutable candidate bytes.

**Approach:** Introduce a versioned, fail-closed Git content fingerprint shared by review workflows; separate deterministic reuse from LLM-result reuse and bind the latter to resolved runtime and prompt inputs. Record cost-shaping metrics without changing review policy, and verify acceptance manifests against Git objects or an explicit plan-local frozen snapshot.

## Boundaries & Constraints

**Always:** Preserve legacy artifact readability; treat legacy fingerprints as non-reusable when compared with a current versioned fingerprint; keep generated evidence non-authorizing; use raw byte SHA-256; preserve `docs/know6.txt`; cite Accepted ADR-0049 in the implementation; test dirty tracked, staged, and untracked changes plus stale manifest bytes.

**Ask First:** Any change to reviewer count, default prompt limit, default external-agent-prompt loading, Bootstrap roles, Phase production code, live runtime state, metadata DB, or hosted workspace data.

**Never:** Reuse an LLM result solely from `HEAD/status`; read live workspace bytes as a substitute for a declared frozen acceptance snapshot; create a second review-packet authority; invoke an LLM during verification.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| Identical review input | Same versioned Git byte identity, normalized command, backend/model/config, prompt sources, and acceptance context | Eligible clean LLM result may be reused; metrics identify the reused result | Missing identity disables LLM reuse |
| Dirty bytes change | Same `HEAD` and status paths, different tracked, index, or untracked bytes | Snapshot comparison is false and stale full-result reuse is rejected | Incomplete Git hashing fails closed |
| Commit candidate | Manifest paths and hashes bound to an immutable Git revision | `prepare-run` verifies every present candidate blob before publishing | Missing blob or hash mismatch raises `InputError` |
| Dirty candidate | Manifest points to a plan-local frozen snapshot | `prepare-run` verifies snapshot bytes, never the live repository workspace | Missing/escaped snapshot or stale bytes raises `InputError` |

</frozen-after-approval>

## Code Map

- `scripts/sc/_git_snapshot.py` -- shared versioned worktree byte identity and comparison.
- `scripts/sc/run_review_pipeline.py` -- reuse decisions, LLM input identity, and pipeline metrics.
- `scripts/sc/llm_review_needs_fix_fast.py` -- deterministic reuse consumer of the shared fingerprint.
- `scripts/sc/_llm_review_engine.py` -- observed prompt and runtime metrics.
- `scripts/sc/_repair_guidance.py` -- persisted execution-context fingerprint and metrics.
- `.agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_core.py` -- immutable manifest byte verification.
- `.agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py` -- `prepare-run` enforcement.

## Tasks & Acceptance

**Execution:**
- [x] `scripts/sc/_git_snapshot.py` and review callers -- hash tracked worktree diff, index diff, and untracked file content; replace duplicated `HEAD/status` equality.
- [x] `scripts/sc/run_review_pipeline.py` and LLM helpers -- require complete LLM input identity for full-result reuse while retaining independently safe deterministic reuse.
- [x] `scripts/sc/_llm_review_engine.py`, schemas, and sidecars -- publish prompt size/hash, invocation duration, backend/model/reasoning, truncation, and reuse metrics without changing defaults.
- [x] `.agents/skills/run-refactor-implementation-acceptance/**` -- verify manifest entries from Git revisions or a target-root-contained frozen snapshot and add positive/negative tests.

**Acceptance Criteria:**
- Given identical status lines but changed dirty bytes, when review reuse is evaluated, then full-result reuse is rejected.
- Given a legacy run and a current versioned fingerprint, when reuse is evaluated, then the legacy run is not an exact snapshot match.
- Given deterministic evidence with a safe documented delta, when LLM identity does not match, then only eligible deterministic work is reused and LLM review is not reused.
- Given an acceptance manifest whose JSON hash is current but whose declared file hash is stale, when `prepare-run` executes, then it fails before publishing output.
- Given a prompts-only review, when the run completes, then metrics are emitted without an LLM invocation.

### Review Findings

- [x] [Review][Patch] Reject deterministic and acceptance reuse from snapshot-drift runs [scripts/sc/run_review_pipeline.py:1339]
- [x] [Review][Patch] Run the final snapshot guard on every success exit and after post-hook work [scripts/sc/_pipeline_session.py:448]
- [x] [Review][Patch] Distinguish a missing Git path from object lookup failure [acceptance_core.py:109]
- [x] [Review][Patch] Disable Git replacement objects during immutable custody verification [acceptance_core.py:59]
- [x] [Review][Patch] Reject snapshot junctions, reparse paths, and shared hardlinks [acceptance_core.py:199]
- [x] [Review][Patch] Fail closed when tracked files use assume-unchanged or skip-worktree flags [scripts/sc/_git_snapshot.py:102]
- [x] [Review][Patch] Treat malformed historical LLM result codes as a non-reusable candidate [scripts/sc/run_review_pipeline.py:500]

## Spec Change Log

- 2026-07-28: Implemented versioned Git content identity, fail-closed LLM reuse identity, review metrics, and immutable acceptance candidate custody. Added compatibility and regression coverage without changing reviewer policy defaults.
- 2026-07-29: Closed adversarial-review findings by validating canonical LLM identities, binding runtime implementations, invalidating inherited steps across snapshots, restricting deterministic reuse to successful command-equivalent evidence, persisting resolved commit custody, and proving deletion/rename tombstones. Retained fail-closed snapshot drift detection; did not expand locking or hash every clean tracked file for the single-maintainer workflow.
- 2026-07-29: Closed completeness-review findings by rejecting drifted source runs, centralizing final snapshot validation across full reuse and post-hook exits, disabling Git replacement objects, distinguishing missing paths from Git failures, rejecting reparse/shared-link snapshots, detecting special index flags, and treating malformed historical result codes as non-reusable.

## Design Notes

The content fingerprint is evidence, not repository authority. Its schema version and completeness flag are part of equality. The LLM cache key records only hashes and non-secret runtime descriptors; it must not persist prompt bodies, credentials, or secret configuration bytes. Acceptance dirty-worktree mode consumes an explicit frozen snapshot beneath the declared target root, while commit mode reads immutable Git blobs.

## Verification

**Commands:**
- `py -3 -m unittest discover -s .agents/skills/run-refactor-implementation-acceptance/tests -p "test_*.py"` -- 123 tests pass, including immutable Git lookup, hardlink rejection, and frozen-snapshot custody cases.
- `py -3 -m unittest scripts.sc.tests.test_git_snapshot scripts.sc.tests.test_change_scope scripts.sc.tests.test_run_review_pipeline_preflight scripts.sc.tests.test_pipeline_sidecar_protocol scripts.sc.tests.test_run_review_pipeline_marathon scripts.sc.tests.test_llm_review_needs_fix_fast scripts.sc.tests.test_llm_review_runtime_budget scripts.sc.tests.test_repair_guidance` -- 113 tests pass.
- `py -3 -m unittest discover -s scripts/sc/tests -p "test_*review*.py"` -- 162 tests pass in one stable full run.
- `py -3 -m py_compile ...` for all changed review and acceptance Python modules -- pass.
- UTF-8 JSON parsing for all three changed schemas -- pass.
- `git diff --check -- .agents/skills/run-refactor-implementation-acceptance scripts/sc _bmad-output/implementation-artifacts/spec-review-reuse-and-acceptance-freeze-hardening.md` -- pass.

## Suggested Review Order

**Review reuse authority**

- Start with the controller that partitions deterministic and LLM-result reuse.
  [`run_review_pipeline.py:1979`](../../scripts/sc/run_review_pipeline.py#L1979)

- Versioned byte identity fails closed across dirty, staged, and untracked inputs.
  [`_git_snapshot.py:102`](../../scripts/sc/_git_snapshot.py#L102)

- Canonical validation prevents forged or partial LLM identities authorizing reuse.
  [`_llm_review_identity.py:104`](../../scripts/sc/_llm_review_identity.py#L104)

- Needs Fix Fast reuses only command-equivalent successful deterministic evidence.
  [`llm_review_needs_fix_fast.py:747`](../../scripts/sc/llm_review_needs_fix_fast.py#L747)

**Runtime and evidence contracts**

- Runtime descriptors bind model, executable, backend, endpoint, and implementation bytes.
  [`_llm_review_engine.py:103`](../../scripts/sc/_llm_review_engine.py#L103)

- Strict metrics schema blocks missing fields and accidental prompt-body persistence.
  [`sc-review-pipeline-summary.schema.json:144`](../../scripts/sc/schemas/sc-review-pipeline-summary.schema.json#L144)

**Acceptance candidate custody**

- Immutable Git blobs or contained snapshots prove every manifest transition.
  [`acceptance_core.py:141`](../../.agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_core.py#L141)

- Prepare-run publishes resolved revision and snapshot receipt custody.
  [`acceptance_cli.py:59`](../../.agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py#L59)

**Regression coverage**

- Snapshot tests demonstrate same-status byte changes cannot compare equal.
  [`test_git_snapshot.py:40`](../../scripts/sc/tests/test_git_snapshot.py#L40)

- Acceptance tests cover stale bytes, containment, deletion, rename, and NUL rejection.
  [`test_run_input.py:247`](../../.agents/skills/run-refactor-implementation-acceptance/tests/test_run_input.py#L247)
