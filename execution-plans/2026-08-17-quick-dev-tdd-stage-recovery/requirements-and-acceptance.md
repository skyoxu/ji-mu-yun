# Requirements And Acceptance

## S0 - Stage Summaries

The adapter records immutable, hash-bound stage summaries for `prepared`,
`red-observed`, `implementation-needed`, `green-observed`, and
`refactor-verified`. A RED summary records a real nonzero test result on the
current frozen candidate and has no implementation-complete authority.

Acceptance: a RED run persists its summary and routes to `implement`; it does
not run GREEN or refactor in the same invocation.

## S1 - Route And Recovery

Every invocation reads the target plan's current summary before spending work.
GREEN consumes only a matching RED summary; refactor consumes only a matching
GREEN summary. Candidate, contract, validator, or test-selector drift creates
a successor preparation and does not reuse stale stage evidence.

Acceptance: resume after each stage is idempotent; repeated failure fingerprints
stop before duplicate execution.

## S2 - Compatibility And Dogfood

Legacy one-shot lifecycle evidence is read-only continuity data. New
VDD-produced plans declare failure intent only; Quick Dev generates the
shell-free RED command and owns the observed result. The 8-17 coordinator plan
runs through the new staged adapter without VDD-bound RED evidence.

Acceptance: a legacy plan cannot publish new staged evidence, and 8-17 reaches
its current terminal predicate through separate RED, implementation, GREEN,
and refactor actions.
