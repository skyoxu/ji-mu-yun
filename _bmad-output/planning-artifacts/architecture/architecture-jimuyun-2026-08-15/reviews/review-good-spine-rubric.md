# Good-Spine Rubric Review

## Review Basis

- Frozen artifact: `ARCHITECTURE-SPINE.md`
- Frozen SHA-256: `fabc669a030080efb3f740a5a8093b5fa433c974541ef52dcfd2a61ca1b4d291`
- Lens: `bmad-architecture` good-spine checklist
- Scope: only P0/P1/P2 issues that materially permit downstream divergence

## Verdict

**NEEDS FIXES: 3 P1 and 1 P2.** The spine covers the Canonical Spec capabilities, preserves lifecycle ownership, and establishes a coherent repository-local operational envelope. Four remaining rules are not precise enough for independent implementations to converge.

## Findings

### P1-1 - Canonical JSON string escaping is named but not fully specified

**Evidence:** `ARCHITECTURE-SPINE.md:78-80`

AD-5 fixes the hash envelope and most canonical JSON rules, but the phrase `fixed control-character escapes` does not define the actual byte mapping. Independent implementations can still disagree on short escapes versus `\u00xx`, hexadecimal letter case, escaping `/`, and the required forms for quote and backslash. Because these bytes feed every current content identity, both implementations can satisfy the written rule yet compute different hashes.

**Required closure:** Freeze the exact string-escape table, including quote, backslash, slash behavior, the five short control escapes, the remaining U+0000-U+001F encoding, and hexadecimal case. Add corresponding golden and mutation vectors. This is an Architecture invariant, not an implementation preference.

### P1-2 - Policy ownership and `current` selection are incomplete for Acceptance route/cost decisions

**Evidence:** `ARCHITECTURE-SPINE.md:60`, `ARCHITECTURE-SPINE.md:110`, `ARCHITECTURE-SPINE.md:140`, `ARCHITECTURE-SPINE.md:146`

AD-2 says `current` is owner-scoped, AD-10 refers to a current published runtime policy, and AD-12/AD-13 depend on an authority/risk policy and policy identity. The spine does not identify the publisher and current-selection authority for the Acceptance route/cost policy, nor state whether it is the same artifact family as the Bootstrap runtime policy. Acceptance route calculation, Bootstrap launch validation, and test fixtures can therefore select different policy universes while each claims to use the current policy.

**Required closure:** Separate the policy families, name each owner and owner-local current-selection artifact, and require route, cost, launch, retry, and reuse consumers to bind and validate the applicable complete policy identity. If Acceptance owns route/cost policy publication, state it; if another maintainer-scoped owner does, state that instead.

### P1-3 - The initial no-progress window has no deterministic event anchor

**Evidence:** `ARCHITECTURE-SPINE.md:110`

The conjunctive lease requires `effective_progress_window_not_expired`, and only a validated Effective Progress Event refreshes that window. The rule does not define the initial timestamp/deadline before the first Effective Progress Event. Implementations can anchor it at reservation, attempt start, process observation, first heartbeat, or treat it as absent; those choices produce immediate stale classification, extra runtime, or an unbounded initial attempt.

**Required closure:** Define the immutable event that initializes the first no-progress deadline, preferably the accepted `attempt-started` event, and state that later extension occurs only through validated Effective Progress Events. Bind the selected policy identity and derived deadline to the attempt/event fold.

### P2-1 - Range Projection cannot prove it was eligible under a specific model-visible budget policy

**Evidence:** `ARCHITECTURE-SPINE.md:92`

AD-7 permits Range Projection only for over-budget authority and leaves thresholds in runtime policy, but the required projection binding omits that policy or model-visible contract identity. A projection minted under one threshold can be reused after policy change without proving that range projection remains allowed.

**Required closure:** Bind the exact model-visible budget/output-contract policy identity and the full-source size used for the eligibility decision into the Range Projection or its mandatory parent decision artifact. Validation must reject stale eligibility evidence after policy mutation.

## Checklist Result

| Good-spine criterion | Result | Notes |
| --- | --- | --- |
| Fixes real divergence points | Partial | Four protocol/policy timing details remain divergent. |
| Every Rule is enforceable | Partial | AD-5 escape bytes, AD-10 initial deadline, and policy selection are underspecified. |
| Deferred is safe | Pass | Deferred numeric thresholds and later adopters do not weaken current authority when policy identity is closed. |
| Named technology is current | Pass | No external version-sensitive technology is bound. |
| Ratifies brownfield boundaries | Pass | Repository-local Skills and shared primitive retain decentralized ownership. |
| Covers driving Spec capabilities | Pass | CAP-1 through CAP-10 are mapped; lifecycle, closure, required checks, routing, review, recovery, and final import are represented. |
| Operational/environmental dimension | Pass | Repository-local operation is fixed and Phase/user-sandbox/provider topology is explicitly out of scope. |

## Positive Confirmations

- Lifecycle ownership is unambiguous: VDD, maintainer, Quick Dev, and Acceptance retain distinct publication authority; Bootstrap remains non-authorizing.
- Changed-set, Consumer Closure, required checks, typed routing, three-role Complete Review, and Acceptance import preserve the Canonical Spec semantics.
- Event sourcing is correctly limited to Bootstrap execution history; artifact content identity remains primary truth.
- The shared canonical primitive is repository-neutral and does not become a central evidence registry or lifecycle owner.
