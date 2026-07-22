# Global Review And Validation

## Review Scope

A complete plan review reads every Markdown file, root contract instance, `schemas/**`, both fixture registries, `tools/**` including `protocol_guards.py`, `agentbuild.txt`, all projected closed clarification runs, repository rules, VDD strict standard, stock Quick Dev implementation/review/present steps, and the current 7-12 Bootstrap profile authority used by this plan.

Sampling is not allowed.

## Deterministic Preflight

Before semantic review:

1. run `tools/validate_all.py --predicate plan-repair-verified` and `--predicate plan-ready`; both must pass under workflow-integrity assurance, while neither may authorize protected handoff or release;
2. run every test under `tools/tests/`;
3. run the VDD Skill contract validator and tests;
4. run the 7-12 Whole-directory validator and Bootstrap regression suite when reviewing integration claims;
5. verify Git status and current source/validator hashes;
6. confirm no old plan or historical evidence changed during plan creation.
7. observe at least one Capsule and one attempt-ledger counterexample with the expected stable rule ID.
8. observe candidate omission, fabricated slice projection, missing cross-slice lineage, test-patch mismatch, authoritative S7 supersession, runtime P2/verifier source, partial re-entry evidence, and artifact-proof counterexamples with their stable rule IDs;
9. apply the seven-dimensional proof contract to every formal artifact added for a prior finding; require explicit executable `PASS` or type-authorized reasoned `N/A`, reject missing verdicts, unauthorized N/A, fake PASS rules, forged producer, self-refreshed identity, unrelated derivation, unknown rule, empty invalidation, broken lineage, and incomplete consumer permission, and prove static contracts have zero runtime authority;
10. execute the disposable Git for Windows add/modify/delete/binary-patch test and junction containment test.
11. observe all three target-plan lifecycle counterexamples, verify the exact non-authoritative index entry and exactly one `95-*.md`, and prove that both index and report are absent from authority and candidate hash scopes.

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
- plan status is `draft` or `plan-ready`, no workflow-integrity blocker is open, and the result authorizes only transition to or confirmation of `plan-ready`;
- `does_not_authorize` includes slice, implementation candidate, implementation acceptance, protected handoff, and release.

The historical Round 3 blocker remains immutable. The current versioned re-entry selector validates a distinct profile-root-authorized policy decision and independently recomputed clean semantic closure envelope, but authorizes only `manual-pause-reentry`. The composite validator may then authorize `plan-ready` under workflow-integrity assurance. Protected handoff and release remain separately gated by independent verifier identity or trusted signed-envelope evidence.

## Implementation Review Predicate

Future `implementation-accepted` requires:

- a current candidate envelope;
- fresh targeted/full deterministic checks;
- finalized Bootstrap result bound to the same candidate and authority;
- no open accepted P0/P1;
- every accepted P2 fixed or validly deferred;
- no high-risk or expired P2 deferral;
- exact authority exclusion for handoff and release.
- a candidate-bound final context/Capsule, immutable S0-S6 lineage, and authoritative non-supersession proof;
- runtime Bootstrap P2 dispositions and verifier output schema-valid and directly hash-bound by the v2 finalized envelope;
- every review-added artifact covered by the independent required inventory, static contract proof, runtime artifact type proof, current authority hash, registered validator/negative test, consumer registry, and exact predicate permission lattice.
- target-plan audit and any VDD repair completed before implementation identity freeze, with the target validator passing and all affected identities refrozen.

## Bounded Review Cycle

Use one complete review, batch repair, then one final complete review. A third review is allowed only for a new P0/P1 or changed authority/context graph. P2-only repair uses targeted deterministic validation and does not trigger another full semantic review.

The finalized Round 3 Bootstrap run remains immutable under `manual_pause_after_round_3`; it was not edited or relabelled as Round 4. `review-policy-reentry.v1` now binds a schema-valid successor policy decision whose authority source terminates at the exact profile-bound root, a hash-bound authorization event, distinct change/policy/authority/review/input lineage, and a clean envelope reproduced by the repository Bootstrap v2 validator. The bounded successor cycle authorizes only plan re-entry, not implementation or release.

GitHub CI for the repair revision is unconfirmed unless authenticated current-run evidence is available. Fresh local deterministic evidence may prove plan repair and closure predicates, but it must not be reported as GitHub Actions PASS.

Round 2 `repo-maint-tdd-final-r2-20260716-024940` confirmed three new P1 findings covering controlled test temp, all-slice exit-proof reachability, and exact source-location validation. They are repaired as one deterministic VDD batch. Because Round 2 introduced new P1 findings, policy permits one Round 3 review; Round 3 is the hard-limit final semantic round and any remaining blocker enters manual pause.

Round 3 `repo-maint-tdd-final-r3-20260716-110837` confirmed eight P1 findings. Their deterministic repair is allowed, but the review cycle remains at `manual_pause`: no Round 4 is authorized, and a passing plan-local validator cannot change the finalized Bootstrap dispositions or claim semantic closure.

## Completion Claim

The final reporter resolves the report from the validated non-authoritative index entry, reads the complete terminal result envelope, and names commands, exit codes, test counts, evidence paths, current hashes, residual gaps, and changed files. Only then may it append the overall result to the target plan's unique `95-*.md`. A clean process exit, partial-slice result, assistant summary, index entry, or report entry without a valid current terminal envelope is not a pass and authorizes nothing.
