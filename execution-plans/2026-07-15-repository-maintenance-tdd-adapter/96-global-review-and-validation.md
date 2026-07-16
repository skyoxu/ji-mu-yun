# Global Review And Validation

## Review Scope

A complete plan review reads every Markdown file, root contract instance, `schemas/**`, `fixtures/**`, `tools/**`, `agentbuild.txt`, the closed clarification state, repository rules, VDD strict standard, stock Quick Dev implementation/review/present steps, and the 7-12 Bootstrap authority used by this plan.

Sampling is not allowed.

## Deterministic Preflight

Before semantic review:

1. run `tools/validate_all.py --predicate plan-repair-verified` and confirm that `--predicate plan-ready` returns `blocked`;
2. run every test under `tools/tests/`;
3. run the VDD Skill contract validator and tests;
4. run the 7-12 Whole-directory validator and Bootstrap regression suite when reviewing integration claims;
5. verify Git status and current source/validator hashes;
6. confirm no old plan or historical evidence changed during plan creation.

A deterministic failure stops semantic review.

## Semantic Review Contract

- Bootstrap is the only semantic finding authority for the change cycle.
- Blind Hunter, Edge Case Hunter, and Acceptance Auditor remain isolated candidate producers.
- Zero candidates is valid.
- P0/P1 requires the current independent-verifier path.
- P2 must be fixed or validly deferred; high-risk P2 is non-deferrable.
- The parent session never edits reviewer or verifier decisions.
- The result is supplemental and cannot become BH-HANDOFF or release authority.

## Plan-Repair-Verified Predicate

`plan-repair-verified` requires all deterministic plan checks, durable clean-checkout authority projections, exact machine ownership, and current hashes. It authorizes only `plan-repair-verified` and explicitly excludes plan-ready, slice-ready, Bootstrap review, implementation acceptance, handoff, and release.

## Plan-Ready Predicate

Plan-ready requires:

- all deterministic checks pass;
- every required fixture demonstrates the expected rule;
- source/requirement/owner/phase/acceptance coverage is exact;
- no open blocker exists;
- plan status is `draft` or `plan-ready` and the result authorizes only transition to or confirmation of `plan-ready`;
- `does_not_authorize` includes slice, implementation candidate, implementation acceptance, protected handoff, and release.

The current Round 3 blocking projection violates the no-open-blocker condition by design, so `plan-ready` must return machine status `blocked` and nonzero exit until an external policy decision supersedes it.

## Implementation Review Predicate

Future `implementation-accepted` requires:

- a current candidate envelope;
- fresh targeted/full deterministic checks;
- finalized Bootstrap result bound to the same candidate and authority;
- no open accepted P0/P1;
- every accepted P2 fixed or validly deferred;
- no high-risk or expired P2 deferral;
- exact authority exclusion for handoff and release.

## Bounded Review Cycle

Use one complete review, batch repair, then one final complete review. A third review is allowed only for a new P0/P1 or changed authority/context graph. P2-only repair uses targeted deterministic validation and does not trigger another full semantic review.

The finalized `repo-maint-tdd-final-20260716-0129` Bootstrap run confirmed five P1 findings and blocked implementation. Their batch repair uses the preserved VDD baseline and targeted counterexamples first. A new complete semantic review may start only after the repaired candidate receives fresh deterministic `plan-ready` evidence.

Round 2 `repo-maint-tdd-final-r2-20260716-024940` confirmed three new P1 findings covering controlled test temp, all-slice exit-proof reachability, and exact source-location validation. They are repaired as one deterministic VDD batch. Because Round 2 introduced new P1 findings, policy permits one Round 3 review; Round 3 is the hard-limit final semantic round and any remaining blocker enters manual pause.

Round 3 `repo-maint-tdd-final-r3-20260716-110837` confirmed eight P1 findings. Their deterministic repair is allowed, but the review cycle remains at `manual_pause`: no Round 4 is authorized, and a passing plan-local validator cannot change the finalized Bootstrap dispositions or claim semantic closure.

## Completion Claim

The final reporter reads the complete result envelope and names commands, exit codes, test counts, evidence paths, current hashes, residual gaps, and changed files. A clean process exit without a valid current envelope is not a pass.
