# Current-Reality Architecture Review - Round 3

## Review Basis

- Frozen artifact: `ARCHITECTURE-SPINE.md` (updated 2026-08-16)
- Lens: current repository ownership, selected Canonical Spec Package, execution-plan contract, and Acceptance implementation
- Scope: default `deterministic_only` route and the explicit Bootstrap-request boundary
- Mechanical baseline: `lint_spine.py` passed with `total_findings: 0`

## Verdict

**NEEDS FIXES: 4 P1 findings.** The Spine is internally coherent, and its lifecycle ownership is compatible with the repository model. The new default-route decision is not yet a consumable repository contract: the selected Spec still says the opposite, the current route code still auto-escalates, explicit actor admission is not represented, and the deterministic evidence handoff cannot currently reach the route decision.

## Findings

### P1-1 - Spine and selected Canonical Spec Package have contradictory route authority

**Evidence:** `ARCHITECTURE-SPINE.md:137-159`; `_bmad-output/specs/spec-acceptance-review-bootstrap-efficiency/SPEC.md:43-44,71-73,104`; `execution-plans/2026-08-15-acceptance-review-bootstrap-efficiency/requirements-and-acceptance.md:74-78`; `execution-plans/2026-08-15-acceptance-review-bootstrap-efficiency/00-index.md:39-47`.

AD-12/AD-15 make `deterministic_only` unconditional after required checks and permit Bootstrap only from an explicit user or maintainer request. The selected Canonical Spec and plan still require registered risk/control-plane triggers to upgrade to Bootstrap or `manual_pause`, and state that this plan's own acceptance is Bootstrap-triggered. Because the Spine lists this package as its source and the package is the selected normative authority, downstream consumers cannot determine one legal route.

**Required closure:** perform the controlled VDD/spec repair and publish a successor Canonical Spec Package with the new route semantics; update the selection/current pointer and plan projection together. Keep the old package as immutable history. Do not implement against both authorities.

### P1-2 - Current Acceptance implementation still performs the forbidden automatic escalation

**Evidence:** `.agents/skills/run-refactor-implementation-acceptance/scripts/semantic_import.py:27-48`; `.agents/skills/run-refactor-implementation-acceptance/scripts/review_requirement.py:103-159`; `.agents/skills/run-refactor-implementation-acceptance/policies/semantic-review-trigger-policy.v1.json:5-17,43-52`.

`project_route()` upgrades any non-empty trigger list from `deterministic_only` to `full_implementation_conformance`. `decide_review_requirement()` classifies `.agents/skills/**` changes, protected paths, unknown paths, and incomplete evidence as Bootstrap requirements. The policy therefore auto-escalates the exact control-plane changes covered by this Spine, contrary to AD-12 and AD-15. The Spine is not implementation-ready until the successor requirements are implemented and their route tests prove zero Bootstrap launches for the default path.

**Required closure:** after the VDD repair, make the route decision consume only an explicit, identity-bound request for optional Bootstrap evidence; deterministic failure remains non-authorizing and must not synthesize a Bootstrap request. Re-run the narrow route/terminal checks and issue a new Quick Dev implementation receipt.

### P1-3 - “Explicit user or maintainer request” has no enforceable actor/publisher contract

**Evidence:** `ARCHITECTURE-SPINE.md:141,153,159`; `.agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py:601-638`; `.agents/skills/run-refactor-implementation-acceptance/scripts/review_requirement.py:103-131`.

The Spine requires an explicit request but does not define its publisher, authenticated actor class, durable request identity, or proof of explicit submission. The current decision input exposes only `maintainer_intent` / `maintainerIntent` with `default|request`; there is no user actor or owner-issued request artifact. An automated caller could therefore synthesize the same value and launch Bootstrap, while a genuine user request cannot be represented distinctly.

**Required closure:** define one owner-scoped request schema and admission boundary with actor class (`user` or `maintainer`), authenticated publisher, immutable request identity, requested route/profile, and current baseline/candidate/closure/check/policy/spec bindings. Acceptance must reject requests outside that boundary; the request remains `authorizes=[]`.

### P1-4 - Deterministic evidence cannot currently satisfy the Spine’s default-route precondition

**Evidence:** `.agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py:583-598`; `.agents/skills/run-refactor-implementation-acceptance/scripts/review_requirement.py:112-137`.

`collect_evidence_command()` publishes `acceptance-evidence-record.v1` without a `status` field, while `decide_review_requirement()` requires `deterministicEvidence.status == "passed"`. A valid collected evidence record is consequently classified as `deterministic_evidence_incomplete`, which blocks the decision before AD-12’s default `deterministic_only` route can be selected. This is a deterministic pipeline contract gap, not a semantic review result.

**Required closure:** close the evidence-record contract so the controlled command receipt (or a validated projection of it) carries and binds `passed|failed`; ensure `collect-evidence -> route decision -> finalization` replays the same identity. Add a deterministic success and failure test proving neither path starts Bootstrap implicitly.

## Confirmed Coherence

- AD-1 preserves the repository’s decentralized lifecycle ownership: VDD, maintainer, Quick Dev, and Acceptance remain distinct publishers.
- AD-2, AD-3, AD-5, AD-9, AD-14, and AD-15 consistently make content identity and current machine evidence authoritative; Bootstrap remains non-authorizing execution evidence.
- The Artifact DAG plus event-sourced Bootstrap execution boundary matches the current repository’s owner-local scripts and does not require a central registry or Phase/user-sandbox dependency.

## Review Disposition

Do not modify this Spine to hide the findings. Complete the controlled VDD/spec repair, then implement the narrow Acceptance route/evidence/request changes and refresh the selection and identity-bound implementation/acceptance evidence.
