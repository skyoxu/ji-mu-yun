# Default Route Good-Spine Review

## Review Basis

- Frozen artifact: `ARCHITECTURE-SPINE.md`
- Lens: `bmad-architecture` good-spine checklist
- Scope: the default `deterministic_only` route and the explicit Bootstrap-request boundary only.
- Mechanical baseline: `lint_spine.py` passed with zero findings.

## Verdict

**NEEDS FIXES: 2 P1.** AD-12 through AD-15 form a coherent owner-safe design once selected: required-check failure is terminal and non-authorizing, default success has a deterministic Acceptance finalization path, and Bootstrap evidence cannot publish lifecycle state. The declared input authority and the request-admission boundary must be closed before independent consumers can converge on whether Bootstrap may launch.

## Findings

### P1-1 - The spine contradicts the Canonical Spec Package that it declares as a source

**Evidence:** `ARCHITECTURE-SPINE.md:10-16,141,159`; `_bmad-output/specs/spec-acceptance-review-bootstrap-efficiency/SPEC.md:43-44,71-73,104`; `authority-and-lifecycle.md:27-29,89`.

AD-12 and AD-15 correctly prohibit automatic escalation from `acceptance_mode`, unattended status, control-plane scope, lifecycle changes, risk wording, or registered triggers. The current declared Canonical Spec Package still mandates the opposite: registered triggers, including lifecycle/authority control changes, must upgrade the route to full Bootstrap review or manual pause, and the supervised deterministic path consumes a maintainer semantic-review decision. A downstream builder can therefore comply with a stated source or with AD-12, but not both.

**Required closure:** Use the controlled VDD/spec repair to publish a successor Canonical Spec Package whose route matrix and acceptance evidence requirements exactly match AD-12/AD-15. Keep the prior package as provenance only, then update the Spine source/selection binding to that successor. Do not implement the new route against two normative authorities.

### P1-2 - “Explicit user or maintainer request” is not yet an enforceable admission boundary

**Evidence:** `ARCHITECTURE-SPINE.md:141,153,159`.

The request is identity-bound to current evidence and cannot authorize acceptance, which protects lifecycle ownership. However, the spine never fixes who publishes the request artifact, how the requested actor is authenticated/recorded, or how Acceptance distinguishes an explicit request from an internally synthesized one. The phrase `schema-valid owner artifact` is ambiguous: an implementation could let an arbitrary caller, route policy code, or automated risk signal mint an apparently valid request and thereby launch Bootstrap, contrary to the rule that default acceptance must not auto-escalate.

**Required closure:** Define a single request-admission contract: the authorized publisher/storage boundary, authenticated actor class (`user` or `maintainer`), immutable request identity, and the evidence that the request was explicitly submitted. Acceptance must reject requests outside that boundary and bind the accepted request identity into the selected route. This remains an evidence preference with `authorizes=[]`; it must not grant lifecycle authority.

## Confirmed Coherence

- AD-12 makes `deterministic_only` the only default after current required checks pass; deterministic failure starts zero Bootstrap work.
- AD-14 makes deterministic finalization exact-match the candidate, closure, required checks, route, policy, and authority/spec-selection identities, so default acceptance does not depend on Bootstrap output.
- AD-1, AD-12, AD-14, and AD-15 consistently reserve `acceptance-passed` to Acceptance and make Bootstrap evidence non-authorizing.
- Explicit Bootstrap work is correctly modelled as an optional semantic filter, not an ownership transfer or a shared mutable workflow state.
