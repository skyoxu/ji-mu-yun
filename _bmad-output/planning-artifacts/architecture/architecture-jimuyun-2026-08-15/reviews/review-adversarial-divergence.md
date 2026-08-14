# Adversarial Divergence Review

Verdict: NEEDS FIXES

Frozen spine SHA-256: `fabc669a030080efb3f740a5a8093b5fa433c974541ef52dcfd2a61ca1b4d291`

## P1 - Current policy selection authority is not closed

AD-10 and AD-12 bind execution and routing to a current policy, but the spine does not identify the owner-scoped policy family, immutable policy artifact identity, or current selection authority. Two compliant builders can select different route/cost/runtime policy revisions for the same frozen inputs and still claim deterministic behavior.

Required fix: define separate owner-scoped route/cost and Bootstrap runtime policy families; each current selection is published only by its policy owner and resolves to an immutable identity-bound policy artifact. Route, cost decision, segment launch, attempt, retry, recovery, and final import bind the resolved policy identity.

## P1 - Attempt deadline initialization is ambiguous

AD-10 defines how heartbeat and Effective Progress refresh separate windows but not the event that initializes them. One controller can start both deadlines at reservation, another at process start, and a third only after first heartbeat/progress.

Required fix: `attempt-started` initializes liveness and Effective Progress/no-progress windows from the bound runtime policy. Reservation has its own launch/terminal grace and cannot create an occupied lease before current process identity is observed.

## P1 - Current pointer mutability wording is contradictory

AD-2 calls a `current` pointer an immutable selection artifact. A content-addressed selection record can be immutable, but the owner-scoped current pointer must be atomically replaceable to select a new record. Treating both as immutable leaves no defined publication transition.

Required fix: immutable content-addressed selection records; an owner-only, schema-valid, atomically replaced current pointer references exactly one selection identity. Pointer replacement changes selection, never artifact truth, and previous selection records remain immutable.

## P2 - Range eligibility policy is not identity-bound

AD-7 delegates the budget threshold to runtime policy but the Range Projection does not bind the policy identity used to decide whole-file versus projection delivery. The same source and range can therefore be admitted under incompatible budget revisions.

Required fix: the authority-delivery decision and Range Projection descriptor bind the selected model-visible budget policy identity. Threshold values remain outside the spine.
