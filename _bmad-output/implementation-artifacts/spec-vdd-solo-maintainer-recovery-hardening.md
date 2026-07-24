---
title: 'VDD Solo-Maintainer Recovery Hardening'
type: 'refactor'
created: '2026-07-24'
status: 'done'
review_loop_iteration: 0
baseline_commit: '00c2cf7fd03fa9111cfe332281efcf580f51ec7d'
context:
  - 'AGENTS.md'
  - 'execution-plans/2026-07-24-vdd-solo-maintainer-recovery-hardening-requirements.md'
---

<frozen-after-approval reason="human-owned intent - do not modify unless human renegotiates">

## Intent

**Problem:** The simplified VDD package is correctly optimized for one trusted maintainer, but it lacks explicit direct-requirements routing and a few bounded recovery protections for optional clarification state.

**Approach:** Add six lightweight capabilities: deterministic input routing, typed CQ dependencies, explicit invalidate/reopen, hash-bound legacy inspection, sanitized quarantine, and Windows CI coverage. Keep the existing single-file atomic state model and reject all remote-branch proof-system machinery.

## Boundaries & Constraints

**Always:** Preserve the solo-maintainer threat model, existing lifecycle ownership, project/evidence-root containment, UTF-8 and atomic writes, read-only legacy bytes, and generic package behavior without dated plan dependencies. Stabilize targeted tests before final package validation and full VDD test discovery.

**Ask First:** Any need to change Quick Dev, Bootstrap Review, acceptance/archive routing, lifecycle ownership, protected runtime paths, or historical 7-15 evidence; any design that cannot quarantine safely without mutating a legacy file.

**Never:** Add event/hash chains, snapshots/reducers, registries, cross-process locks, signatures, trusted approvals, generation/pointer promotion, source-proof closure, mandatory question counts, confidence gates, or implicit VDD directory creation from one requirements file.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Direct route | One explicit requirements Markdown | Direct implementation; no VDD directory | Route mutation fails package validation |
| CQ graph | Current state with typed decisions | Valid kinds and acyclic dependencies persist | Unknown kind, self/missing/duplicate/cyclic dependency fails |
| Drift recovery | Existing run with changed hashes | Byte-preserving `stale`, then explicit invalidate/reopen | Invalid transition or hash fails without mutation |
| Legacy read | v1/v2 file plus exact SHA-256 | Minimal metadata, unchanged bytes | Hash mismatch, sensitive content, or mutation attempt fails closed |
| Sensitive input | Current run plus credential-shaped payload | Sanitized terminal quarantine with digest only | No original key/value is echoed or persisted |

</frozen-after-approval>

## Code Map

- `AGENTS.md` -- repository-level direct requirements versus full VDD directory routing.
- `.agents/skills/vdd-execution-plan/SKILL.md` and `agents/openai.yaml` -- human-facing invocation boundary.
- `.agents/skills/vdd-execution-plan/references/*.md` -- recovery and clarification semantics.
- `.agents/skills/vdd-execution-plan/scripts/clarification_state.py` -- optional state schema, transitions, legacy inspection, and quarantine.
- `.agents/skills/vdd-execution-plan/scripts/skill-contract.json` -- deterministic route contract and required package files.
- `.agents/skills/vdd-execution-plan/scripts/validate_skill_contract.py` -- route and package validation.
- `.agents/skills/vdd-execution-plan/scripts/tests/*.py` -- state, mutation, compatibility, and negative architecture coverage.
- `.agents/skills/vdd-execution-plan/scripts/fixtures/*.json` -- minimal detached current/legacy fixtures only.
- `.github/workflows/ci-windows.yml` -- VDD hard-gate commands after Python setup.

## Tasks & Acceptance

**Execution:**
- [x] `AGENTS.md`, VDD `SKILL.md`, `openai.yaml`, references, and `skill-contract.json` -- codify the three route outcomes and bounded recovery policy.
- [x] `clarification_state.py` -- introduce current v3 typed CQ validation, stale/invalidate/reopen transitions, digest-bound legacy inspection, and sanitized terminal quarantine while retaining atomic single-writer storage.
- [x] VDD fixtures and tests -- replace inactive strict fixtures; cover route mutations, CQ graph failures, byte-preserving legacy reads, transition boundaries, quarantine, and absence of excluded architecture.
- [x] `validate_skill_contract.py` and `.github/workflows/ci-windows.yml` -- validate routing and run package/tests as Windows hard gates.

**Acceptance Criteria:**
- Given one requirements file, explicit directory create, or explicit directory repair, the package resolves respectively to direct implementation, VDD create, or VDD repair without implicit escalation.
- Given any current or legacy state operation, only a valid contained current state can mutate, and no sensitive value is exposed.
- Given the completed patch, no excluded proof-system entrypoint or field exists and all declared verification commands pass.

## Spec Change Log

## Design Notes

Use one current v3 state file. Reopen replaces stale hashes and clears decisions; it does not append history. Quarantine is the only terminal safety envelope and stores only a rule ID, input digest, and time. Legacy v1/v2 has one inspection command and no migration command.

## Verification

**Commands:**
- `py -3 -B .agents/skills/vdd-execution-plan/scripts/validate_skill_contract.py --skill-root .agents/skills/vdd-execution-plan` -- expected: `ok: true`.
- `py -3 -B -m unittest discover -s .agents/skills/vdd-execution-plan/scripts/tests -p "test_*.py" -v` -- expected: all VDD tests pass.
- `git diff --check` -- expected: no whitespace errors.

## Suggested Review Order

**Routing Boundary**

- Start with the explicit direct, create, and repair invocation boundary.
  [`SKILL.md:12`](../../.agents/skills/vdd-execution-plan/SKILL.md#L12)

- See where repository routing prevents implicit VDD expansion.
  [`AGENTS.md:85`](../../AGENTS.md#L85)

- Verify the machine contract rejects route drift.
  [`validate_skill_contract.py:123`](../../.agents/skills/vdd-execution-plan/scripts/validate_skill_contract.py#L123)

**State And Recovery**

- Review the v3 and quarantine schema boundary first.
  [`clarification_state.py:18`](../../.agents/skills/vdd-execution-plan/scripts/clarification_state.py#L18)

- Trace typed CQ validation and iterative dependency handling.
  [`clarification_state.py:139`](../../.agents/skills/vdd-execution-plan/scripts/clarification_state.py#L139)

- Check canonical path binding before every current-state mutation.
  [`clarification_state.py:299`](../../.agents/skills/vdd-execution-plan/scripts/clarification_state.py#L299)

- Inspect sensitive detection, duplicate-key handling, and terminal quarantine.
  [`clarification_state.py:325`](../../.agents/skills/vdd-execution-plan/scripts/clarification_state.py#L325)

- Follow stale identity handling and explicit recovery transitions.
  [`clarification_state.py:355`](../../.agents/skills/vdd-execution-plan/scripts/clarification_state.py#L355)

- Confirm legacy inspection binds one byte snapshot to its digest.
  [`clarification_state.py:524`](../../.agents/skills/vdd-execution-plan/scripts/clarification_state.py#L524)

**Verification And CI**

- Exercise deep graphs and other state transition boundaries.
  [`test_clarification_state_concurrency.py:135`](../../.agents/skills/vdd-execution-plan/scripts/tests/test_clarification_state_concurrency.py#L135)

- Verify duplicate keys cannot conceal credential material.
  [`test_clarification_state_concurrency.py:367`](../../.agents/skills/vdd-execution-plan/scripts/tests/test_clarification_state_concurrency.py#L367)

- Confirm exclusions apply across package machine sources.
  [`test_validate_skill_contract.py:177`](../../.agents/skills/vdd-execution-plan/scripts/tests/test_validate_skill_contract.py#L177)

- End with the Windows hard gate and explicit failure propagation.
  [`ci-windows.yml:64`](../../.github/workflows/ci-windows.yml#L64)
