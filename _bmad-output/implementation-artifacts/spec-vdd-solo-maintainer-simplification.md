---
title: 'VDD Solo-Maintainer Simplification'
type: 'refactor'
created: '2026-07-24'
status: 'done'
review_loop_iteration: 0
baseline_commit: 'f2694e9cd154831633cb4e3d088d75b031a550c1'
context:
  - 'execution-plans/2026-07-24-vdd-solo-maintainer-simplification-requirements.md'
  - 'AGENTS.md'
---

<frozen-after-approval reason="human-owned intent - do not modify unless human renegotiates">

## Intent

**Problem:** `vdd-execution-plan` currently treats a trusted single-maintainer repository as a multi-writer adversarial evidence system. The resulting mandatory five-question gate, custom proof artifacts, global replay, Bootstrap rounds, and distributed recovery machinery make plan control exceed ordinary implementation work.

**Approach:** Rebuild the Skill around three explicit profiles: a lightweight `standard` default, a small `resumable` extension, and a narrowly scoped `self-hosted` extension. Retain truthful tests, current Git identity, lifecycle separation, protected-path approval, and historical evidence while removing controls without a real single-maintainer consumer.

## Boundaries & Constraints

**Always:** Implement every `VDD-SOLO-*` and `AC-*` item in `execution-plans/2026-07-24-vdd-solo-maintainer-simplification-requirements.md`. Preserve the canonical lifecycle `draft -> plan-ready -> implementation-authorized -> implementation-complete -> acceptance-passed -> archived`; maintain the ownership boundary that Quick Dev can publish only `implementation-complete`. Retain UTF-8, path containment, sensitive-data minimization, protected-path approval, current test evidence, Git-based candidate identity, and additive historical records. The generic package must not read mutable live plan directories or encode concrete plan identities. Run the package validator and the complete VDD unit suite.

**Ask First:** Changes outside `.agents/skills/vdd-execution-plan/**`, including Quick Dev, Bootstrap Review, acceptance/archive Skills, the 7-15 historical plan, or live runtime state. Any product-security weakening or destructive history rewrite.

**Never:** Recreate 7-15 evidence, fabricate historical RED/attempt events, make plan readiness imply acceptance, turn Bootstrap into lifecycle authority, or retain duplicate custom schemas, ledgers, trust roots, signatures, distributed locks, or filesystem edge fixtures by default merely to preserve the former strict model.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| Standard clear request | Explicit write authorization, existing repository tests | One compact plan plus lifecycle marker; no filler questions, custom validator, 95 report, or Bootstrap prerequisite | Material ambiguity alone opens a targeted question/blocker |
| Resumable/self-hosted work | Cross-session or workflow-control change | Adds only compact resume/freshness state, declared dependents, and indexed append-only 95 report | Missing required profile artifact fails its deterministic profile check |
| Local repair | Slice-local source, fixture, or command change | Invalidates the slice and declared downstream consumers; targeted checks stabilize first | Shared lifecycle/validator/baseline change requires one terminal full replay |
| Legacy history | Existing behavior without historical RED | Records legacy/regression path without inventing prior events | Historical evidence remains non-current and byte-preserved |
| Authorization/review | Explicit maintainer approval; optional Bootstrap evidence | Static Skill lifecycle permits implementation only; review remains supplemental and batch-handled | Invalid state jump, Quick Dev acceptance claim, or old emitted state name is rejected |

</frozen-after-approval>

## Code Map

- `.agents/skills/vdd-execution-plan/SKILL.md` -- operator workflow, profile selection, compact plan shape, clarification, recovery, and completion guidance.
- `.agents/skills/vdd-execution-plan/references/clarification-gate.md` -- material-question-only and initial-authority policy.
- `.agents/skills/vdd-execution-plan/references/lifecycle-state-contract.md` -- static lifecycle owner and compatibility policy.
- `.agents/skills/vdd-execution-plan/references/solo-maintainer-vdd-standard.md` -- single-maintainer verification, freshness, review, and profile rules.
- `.agents/skills/vdd-execution-plan/scripts/clarification_state.py` -- optional single-writer resumable clarification state.
- `.agents/skills/vdd-execution-plan/scripts/skill-contract.json` and `scripts/validate_skill_contract.py` -- profile, fixture, and package-contract validation.
- `.agents/skills/vdd-execution-plan/scripts/fixtures/**` and `scripts/tests/**` -- profile, authorization, freshness, legacy, and competing-pressure regression coverage.
- `.agents/skills/vdd-execution-plan/agents/openai.yaml` -- routing metadata aligned with the simplified workflow.

## Tasks & Acceptance

**Execution:**
- [x] `SKILL.md` and all three reference contracts -- replace strict default gates with `standard`, `resumable`, and `self-hosted` rules; make zero material questions and initial explicit authorization valid; retain only material blocker handling.
- [x] `scripts/clarification_state.py`, contract, and fixtures -- make persistence optional, remove default registry/lock/attestation requirements, preserve safe atomic single-writer updates and legacy readable state.
- [x] `references/lifecycle-state-contract.md`, package validator, and tests -- publish one Skill-owned transition contract; allow explicit maintainer implementation authorization; reject escalation, legacy emission, and Quick Dev acceptance authority.
- [x] `scripts/skill-contract.json`, `validate_skill_contract.py`, fixtures, and tests -- implement deterministic profile validation, profile-specific artifacts and 95 rules, detached index checks, no-live-plan/no-hardcoding guards, and profile-driven plan shape.
- [x] freshness/replay policy, fixtures, and tests -- bind only normative inputs, exclude 95/log prose, invalidate slice plus declared downstream only, require terminal replay only for shared changes, and preserve historical-only or regression migration paths.
- [x] review and recovery policy, fixtures, and tests -- make Bootstrap optional/supplemental, batch requested findings before later review, prevent P2-only automatic loops, and make edge/recovery machinery conditional on actual semantics.
- [x] `agents/openai.yaml` -- regenerate or update routing metadata for the new profile-first workflow.

**Acceptance Criteria:**
- Given a clear authorized ordinary request, when VDD creates a plan, then the standard fixture proves no filler question, second approval, custom validator/schema, 95 report, or Bootstrap gate is required.
- Given resumable or self-hosted work, when its contract is validated, then only its required compact recovery and indexed non-authorizing 95 report are required.
- Given a local change or a shared control change, when freshness is evaluated, then only the declared dependent closure is stale for the former and one terminal replay is required for the latter.
- Given explicit maintainer approval or requested Bootstrap evidence, when lifecycle is evaluated, then only `implementation-authorized` is granted by the former and the latter remains supplemental.
- Given legacy evidence, old state names, an invalid lifecycle jump, or a Quick Dev acceptance claim, when validation runs, then the correct compatibility path is retained or the invalid action is rejected without fabricated history.
- Given the package source and detached fixtures, when complete validation runs, then no mutable live execution-plan read or concrete dated plan identity is present, while the repository-level 95 index validator remains separately owned.

## Spec Change Log

## Design Notes

The implementation must replace the strict default rather than layering a permissive branch around it. A profile contract owns whether an artifact exists and whether it can affect a decision; this prevents a `standard` plan from inheriting self-hosted proof requirements while keeping self-hosted protocol checks available where an actual consumer exists.

## Verification

**Commands:**
- `py -3 .agents/skills/vdd-execution-plan/scripts/validate_skill_contract.py --skill-root .agents/skills/vdd-execution-plan` -- expected: package contract and all detached fixtures pass.
- `py -3 -m unittest discover -s scripts/tests -p "test_*.py" -v` from `.agents/skills/vdd-execution-plan` -- expected: complete profile, clarification, lifecycle, freshness, compatibility, and no-hardcoding suite passes.

## Suggested Review Order

**Profile Workflow**

- Start with the profile-first route and its intentionally small standard default.
  [`SKILL.md:12`](../../.agents/skills/vdd-execution-plan/SKILL.md#L12)

- Confirm candidate identity, optional review, conditional 95, and terminal validation remain distinct.
  [`SKILL.md:42`](../../.agents/skills/vdd-execution-plan/SKILL.md#L42)

**Lifecycle And Freshness**

- Inspect the static owner contract before reviewing its deterministic enforcement.
  [`lifecycle-state-contract.md:1`](../../.agents/skills/vdd-execution-plan/references/lifecycle-state-contract.md#L1)

- Review the targeted-first replay rule and removal of default proof-system controls.
  [`solo-maintainer-vdd-standard.md:13`](../../.agents/skills/vdd-execution-plan/references/solo-maintainer-vdd-standard.md#L13)

- Verify lifecycle endpoints, compatibility, profile completeness, and generic-source guards.
  [`validate_skill_contract.py:32`](../../.agents/skills/vdd-execution-plan/scripts/validate_skill_contract.py#L32)

**Optional Resume State**

- Check resumed-state containment and stale-input handling before persistence occurs.
  [`clarification_state.py:119`](../../.agents/skills/vdd-execution-plan/scripts/clarification_state.py#L119)

- Check material-only blocking and value-level secret minimization in the focused tests.
  [`test_clarification_state_concurrency.py:19`](../../.agents/skills/vdd-execution-plan/scripts/tests/test_clarification_state_concurrency.py#L19)

**Regression Fixtures**

- Confirm negative mutations cover lifecycle jumps, omitted profile controls, and plan hardcoding.
  [`test_validate_skill_contract.py:19`](../../.agents/skills/vdd-execution-plan/scripts/tests/test_validate_skill_contract.py#L19)
