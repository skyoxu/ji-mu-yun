# Adversarial Review - Default Deterministic Route

## Review Basis

- Frozen artifact: `ARCHITECTURE-SPINE.md`
- Lens: AD-12, AD-14, and AD-15 only
- Scope: default `deterministic_only` routing and explicit Bootstrap request admission
- Review style: important compatibility findings only

## Verdict

**NEEDS FIXES: 2 P1.** The revised spine is internally coherent about lifecycle ownership and makes the default path independent of Bootstrap. It is not yet a closed producer/consumer contract because its declared Canonical Spec Package still describes the former automatic-escalation matrix, and the explicit request boundary is not machine-enforceable.

## Findings

### P1-1 - Declared Canonical Spec Package still contradicts AD-12/AD-15

**Evidence:** `ARCHITECTURE-SPINE.md:10-16,141,159`; `_bmad-output/specs/spec-acceptance-review-bootstrap-efficiency/SPEC.md` route constraints and success criteria; `authority-and-lifecycle.md` route matrix.

AD-12/AD-15 make `deterministic_only` the unconditional default after required checks and prohibit escalation from mode, unattended status, control-plane scope, risk hints, lifecycle changes, or registered triggers. The selected Canonical Spec Package still requires the old supervised/unattended matrix and automatic registered-trigger upgrades. A downstream producer or Acceptance consumer can therefore satisfy one declared authority only by violating the other.

**Required closure:** Publish a successor Canonical Spec Package through the controlled VDD/spec repair, with the new route and evidence semantics. Update the Architecture source/selection binding to that successor and retain the prior package as immutable provenance. Do not implement against both matrices.

### P1-2 - Explicit Bootstrap request has no enforceable publisher/authentication boundary

**Evidence:** `ARCHITECTURE-SPINE.md:141,153,159`.

The spine requires a "schema-valid owner artifact" and says a user or maintainer may explicitly request Bootstrap, but it does not define the owner/storage boundary, authenticated actor class, or evidence that the artifact was actually submitted by that actor. An automated route policy, risk detector, or arbitrary caller could mint the same shape and cause Bootstrap to launch, contradicting the rule that default Acceptance never auto-escalates.

**Required closure:** Define one request-admission contract: Acceptance-owned request artifact and storage boundary, authenticated `user`/`maintainer` actor identity, immutable request identity, explicit-submission evidence, requested route/profile, and exact current input bindings. Acceptance must reject synthesized or unauthenticated requests and bind the accepted request identity into the selected route. The request remains non-authorizing (`authorizes=[]`).

## Confirmed Non-findings

- AD-12, AD-14, and AD-15 consistently reserve `acceptance-passed` to Acceptance and keep Bootstrap evidence non-authorizing.
- Candidate mutation staling the explicit request and all downstream artifacts is specified.
- Deterministic failure launching zero Bootstrap work is compatible with the default route and does not require rerunning historical Bootstrap evidence.
