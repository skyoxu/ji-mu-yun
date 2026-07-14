---
title: 'Harden Bootstrap finding deduplication and process lease identity'
type: 'bugfix'
created: '2026-07-14'
status: 'done'
review_loop_iteration: 0
baseline_commit: 'fdc5ef47584d0ccdd7696bd8ac600b8b15df7b83'
context:
  - 'execution-plans/2026-07-12-llm-review-evidence-gate-hardening/04-gateway-dedup-verification-and-memory.md'
  - 'execution-plans/2026-07-12-llm-review-evidence-gate-hardening/06-testing-observability-and-rollout.md'
  - 'execution-plans/2026-07-12-llm-review-evidence-gate-hardening/09-bootstrap-review-operator-guide.md'
  - 'docs/adr/ADR-0038-phase-evidence-sidecars-readback.md'
---

<frozen-after-approval reason="human-owned intent; do not modify unless human renegotiates">

## Intent

**Problem:** Bootstrap review currently merges distinct failure modes when they cite the same evidence span, and its process-lease protocol can accept a fabricated reviewer identity created with a dead or unrelated PID. Both defects can suppress real findings or manufacture review-execution evidence.

**Approach:** Make deduplication identity include the normalized failure tuple and finding dimension, and bind every process lease to a live process identity captured at acquisition and checked on release whenever the PID is still live.

## Boundaries & Constraints

**Always:** Preserve stable finding IDs for semantically identical candidates; retain the highest severity only within a true duplicate group; fail closed when a process is not live or its identity cannot be captured; require the acquiring PID on release; preserve release of a normally exited child by its original PID; keep Windows process checks read-only and never call `os.kill(pid, 0)` on Windows; preserve append-only historical review evidence in accordance with ADR-0038.

**Ask First:** Any schema version bump, compatibility break for already-finalized review runs, change to reviewer model/routing policy, or modification outside the 7-12 review authority and its implementation spec.

**Never:** Merge candidates merely because their line evidence matches; accept a nonexistent PID at acquisition; allow release without a PID or by a different PID; kill or signal a Codex/reviewer process during liveness checks; rerun a full three-layer review between individual fixes.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| True duplicate | Same evidence, normalized failure tuple, and dimension from multiple reviewers | One finding, all source reviewers, highest proposed severity | Lower-ranked candidates are recorded as duplicates |
| Distinct failure | Same evidence but different trigger/state/outcome or dimension | Independent stable findings | No duplicate rejection |
| Valid lease | Live child PID at acquire; same PID releases after normal exit | Acquired identity is persisted; completed release succeeds | N/A |
| Forged lease | Dead PID, omitted release PID, wrong PID, or live reused PID with different identity | Lease is not acquired or completed | CLI fails closed without writing false completion evidence |

</frozen-after-approval>

## Code Map

- `execution-plans/2026-07-12-llm-review-evidence-gate-hardening/tools/run_bootstrap_review.py` -- finding fingerprinting, process identity, lease acquisition/release, and gate consumption.
- `execution-plans/2026-07-12-llm-review-evidence-gate-hardening/schemas/bootstrap-process-leases.v1.schema.json` -- persisted lease identity contract.
- `execution-plans/2026-07-12-llm-review-evidence-gate-hardening/tools/tests/test_run_bootstrap_review.py` -- deterministic regression coverage.
- `execution-plans/2026-07-12-llm-review-evidence-gate-hardening/{04,06,09,96}-*.md` -- dedup, testing/operator rules, and finding closure ledger.

## Tasks & Acceptance

**Execution:**
- [x] `tools/run_bootstrap_review.py` -- normalize failure identity in fingerprints and capture/check live process identity in leases.
- [x] `schemas/bootstrap-process-leases.v1.schema.json` -- require the captured process identity for every persisted lease.
- [x] `tools/tests/test_run_bootstrap_review.py` -- replace fake-PID happy paths and add dedup and lease forgery regressions.
- [x] Plan authority documents -- align normative rules and close the two confirmed findings without adding unrelated requirements.

**Acceptance Criteria:**
- Given two accepted candidates with identical evidence but different normalized failure tuples or dimensions, when the gateway deduplicates them, then both findings remain.
- Given semantically identical candidates from different reviewers, when the gateway deduplicates them, then one stable finding retains all sources and the highest severity.
- Given a nonexistent PID, when lease acquisition is attempted, then the command fails and no lease is appended.
- Given an acquired lease, when release omits the PID or supplies a different PID, then completion fails without mutating the lease.
- Given a live PID whose current identity differs from the captured identity, when release is attempted, then completion fails.
- Given a child that was live at acquisition and exited normally, when the controller releases with its original PID, then completion succeeds.

## Spec Change Log

## Design Notes

Process identity is an OS-derived creation identity, not merely the numeric PID. On Windows it should be read with query-only process APIs and persisted with the lease. Release rechecks it when that PID is alive; if the original process has exited, exact PID ownership plus the acquisition-time identity permits normal controller completion.

## Verification

**Commands:**
- `py -3 -m unittest execution-plans/2026-07-12-llm-review-evidence-gate-hardening/tools/tests/test_run_bootstrap_review.py` -- all Bootstrap CLI regressions pass.
- `py -3 execution-plans/2026-07-12-llm-review-evidence-gate-hardening/tools/validate_whole_directory.py` -- 7-12 authority remains internally consistent.
- `py -3 C:/Users/Administrator/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/vdd-execution-plan` -- VDD Skill quick validation passes.
- `git diff --check` -- no whitespace errors.

## Suggested Review Order

**Lease identity and finding deduplication**

- Start with the two evidence-integrity boundaries and their fail-closed behavior.
  [`run_bootstrap_review.py:539`](../../execution-plans/2026-07-12-llm-review-evidence-gate-hardening/tools/run_bootstrap_review.py#L539)

- Review acquisition/release ownership and completed-layer enforcement together.
  [`run_bootstrap_review.py:1358`](../../execution-plans/2026-07-12-llm-review-evidence-gate-hardening/tools/run_bootstrap_review.py#L1358)

- Confirm distinct failure tuples and dimensions produce distinct stable findings.
  [`run_bootstrap_review.py:1659`](../../execution-plans/2026-07-12-llm-review-evidence-gate-hardening/tools/run_bootstrap_review.py#L1659)

**VDD structured validation**

- Confirm malformed non-object fixtures return machine-readable findings instead of exceptions.
  [`validate_skill_contract.py:42`](../../.agents/skills/vdd-execution-plan/scripts/validate_skill_contract.py#L42)

**Contracts and regressions**

- Check persisted lease identity is mandatory at the schema boundary.
  [`bootstrap-process-leases.v1.schema.json:17`](../../execution-plans/2026-07-12-llm-review-evidence-gate-hardening/schemas/bootstrap-process-leases.v1.schema.json#L17)

- Read the Bootstrap counterexamples for dedup, pending layers, and forged leases.
  [`test_run_bootstrap_review.py:680`](../../execution-plans/2026-07-12-llm-review-evidence-gate-hardening/tools/tests/test_run_bootstrap_review.py#L680)

- Read the VDD null/array fixture regression.
  [`test_validate_skill_contract.py:77`](../../.agents/skills/vdd-execution-plan/scripts/tests/test_validate_skill_contract.py#L77)

- Finish with the closed finding ledger and Round 2 outcome.
  [`96-global-review-and-validation.md:98`](../../execution-plans/2026-07-12-llm-review-evidence-gate-hardening/96-global-review-and-validation.md#L98)
