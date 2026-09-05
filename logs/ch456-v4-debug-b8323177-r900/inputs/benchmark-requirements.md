# FR-301
An idempotency reservation ledger must be implemented as one bounded stateful slice.

Production owner: `benchmarks/ch456-live-blind/idempotency-ledger-v1/src/idempotency_ledger.py`.
The RED author must create `benchmarks/ch456-live-blind/idempotency-ledger-v1/tests/test_idempotency_ledger.py` and may use the existing fixture `benchmarks/ch456-live-blind/idempotency-ledger-v1/tests/cases.json`.
The production implementation may modify only the production owner above.
The validation command is `py -3 -m pytest benchmarks/ch456-live-blind/idempotency-ledger-v1/tests/test_idempotency_ledger.py -q -p no:cacheprovider`.
The RED test must call the real production owner and, whenever a declared Acceptance assertion fails, emit the matching VDD failure intent as `FAILURE_ID:<failure_id>` before the assertion fails.

The ledger has three independently observable required behaviors, all of which must be exercised by the same selector family:

1. Claiming a key that is already active at `now < expires_at` returns `duplicate` rather than `accepted`.
2. Claiming with `ttl_seconds <= 0` returns `invalid-ttl` and must not create an active reservation.
3. Releasing a key that is not active returns `not-found` rather than reporting a successful release.

The existing skeleton intentionally returns success for every operation, so all three forbidden behaviors are observable before implementation.  A legal GREEN must change production only; GREEN and REFACTOR must preserve the RED selector, fixture and assertions.
