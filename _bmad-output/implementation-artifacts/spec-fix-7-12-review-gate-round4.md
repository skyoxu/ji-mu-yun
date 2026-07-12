---
title: 'Fix 7-12 review evidence gate Round 4 findings'
type: 'bugfix'
created: '2026-07-12'
status: 'done'
review_loop_iteration: 0
baseline_commit: 'f58c1d2819ca4cffeb5ad02bdf06fd5a0718990b'
context:
  - 'execution-plans/2026-07-12-llm-review-evidence-gate-hardening/96-global-review-and-validation.md'
---

<frozen-after-approval reason="human-owned intent - do not modify unless human renegotiates">

## Intent

**Problem:** Round 4 Whole-directory review confirmed four P1 contract gaps: fixture validity conflates schema and gateway semantics, result producers can self-narrow required reviewer layers, unverified P1 disposition is ambiguous, and the missing-consumer fixture can pass for the wrong reason.

**Approach:** Harden the plan-local contracts and validator so each gap has a deterministic counterexample, then close the findings in the 96 ledger only after the full directory validator passes.

## Boundaries & Constraints

**Always:** Keep all changes inside `execution-plans/2026-07-12-llm-review-evidence-gate-hardening/`; preserve stable RFG vocabulary; make fixture failure reasons deterministic; retain the rule that plan-ready does not mean code-complete.

**Ask First:** Any change to AGENTS.md, README.md, installer-managed BMAD/GDS files, runtime code, or either upstream 7-07/7-11 refactor directory.

**Never:** Rewrite historical evidence, weaken the P0-P2 proof triplet, treat self-reported layer sets as policy authority, or claim runtime implementation is complete.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Fixture validation | Schema-valid instance violates gateway semantics | Schema and composite expectations remain distinguishable | Validator reports the failed validation stage |
| Layer policy | Producer submits fewer required layers than the trusted profile | Result is rejected | Stable policy-mismatch error |
| Unverified P1 | Same finding is submitted with conflicting result disposition | Only policy-authorized disposition is accepted | Stable disposition error |
| Missing consumer | Consumer requirement is removed while confidence remains otherwise valid | Negative fixture still fails specifically for consumer | Expected reason mismatch fails the suite |

</frozen-after-approval>

## Code Map

- `schemas/review-finding.v1.schema.json` -- finding classification and document authority fields.
- `schemas/review-result.v1.schema.json` -- result status, reviewer layers, and policy authority fields.
- `schemas/review-validation-fixtures.v1.json` -- positive and negative contract examples.
- `tools/validate_whole_directory.py` -- schema subset and gateway semantic validator.
- `02-finding-contract-and-severity.md` -- normative result and layer contract.
- `04-gateway-dedup-verification-and-memory.md` -- trusted policy and verifier disposition rules.
- `96-global-review-and-validation.md` -- mechanical checks and historical finding ledger.

## Tasks & Acceptance

**Execution:**
- [x] Separate schema validity from composite gateway validity in fixture metadata and validation output.
- [x] Add trusted review-profile authority and reject producer-narrowed required layers.
- [x] Add a machine-readable unverified disposition classification and bind it to result status.
- [x] Isolate the missing-consumer negative fixture and assert its expected failure reason.
- [x] Record RFG-REV-4-P1-01 through 04 as Closed with owner and acceptance references.

**Acceptance Criteria:**
- Given a schema-valid but gateway-invalid fixture, when validation runs, then both stages are evaluated without contradictory expectations.
- Given required layers that differ from the trusted policy profile, when validation runs, then the result is rejected.
- Given a blocking unverified P1, when it is labeled incomplete, then the result is rejected; nonblocking unverified cannot be labeled blocked.
- Given the consumer requirement is removed, when the targeted mutation runs, then the missing-consumer fixture no longer fails for an unrelated confidence threshold and the suite detects the regression.
- Given all fixes are present, when the Whole-directory validator runs, then it passes with no Open P0-P2 and does not claim code completion.

## Spec Change Log

## Verification

**Commands:**
- `py -3 execution-plans/2026-07-12-llm-review-evidence-gate-hardening/tools/validate_whole_directory.py` -- expected: Whole-directory PASS.

## Suggested Review Order

**Normative contract**

- Start with the gateway-assigned policy and unverified disposition invariants.
  [02-finding-contract-and-severity.md:46](../../execution-plans/2026-07-12-llm-review-evidence-gate-hardening/02-finding-contract-and-severity.md#L46)

- Confirm policy assignment is external to producer-controlled result fields.
  [04-gateway-dedup-verification-and-memory.md:29](../../execution-plans/2026-07-12-llm-review-evidence-gate-hardening/04-gateway-dedup-verification-and-memory.md#L29)

**Machine enforcement**

- Review gateway-owned class/disposition constraints for unverified findings.
  [review-finding.v1.schema.json:71](../../execution-plans/2026-07-12-llm-review-evidence-gate-hardening/schemas/review-finding.v1.schema.json#L71)

- Review blocked-result exclusion of manual-pause findings.
  [review-result.v1.schema.json:135](../../execution-plans/2026-07-12-llm-review-evidence-gate-hardening/schemas/review-result.v1.schema.json#L135)

- Trace trusted assignment, layer derivation, and aggregate status checks.
  [validate_whole_directory.py:279](../../execution-plans/2026-07-12-llm-review-evidence-gate-hardening/tools/validate_whole_directory.py#L279)

**Counterexamples and closure**

- Inspect external policy assignments and staged fixture validity metadata.
  [review-validation-fixtures.v1.json:3](../../execution-plans/2026-07-12-llm-review-evidence-gate-hardening/schemas/review-validation-fixtures.v1.json#L3)

- Verify mixed blocker/manual-pause and trusted-profile substitution regressions.
  [review-validation-fixtures.v1.json:721](../../execution-plans/2026-07-12-llm-review-evidence-gate-hardening/schemas/review-validation-fixtures.v1.json#L721)

- Finish at the stable Round 4 finding ledger and plan-ready statement.
  [96-global-review-and-validation.md:73](../../execution-plans/2026-07-12-llm-review-evidence-gate-hardening/96-global-review-and-validation.md#L73)
