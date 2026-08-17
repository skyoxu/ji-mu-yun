# Requirements And Acceptance

## S0 - Stage Summaries

The adapter records immutable, hash-bound stage summaries for `prepared`,
`red-observed`, `implementation-needed`, `green-observed`, and
`refactor-verified`. A RED summary records a real nonzero test result on the
current frozen candidate and has no implementation-complete authority. Its
RED-basis identity is the failure intent, test selector, contract, validator,
and pre-implementation candidate.

Acceptance: a RED run persists its summary and routes to `implement`; it does
not run GREEN or refactor in the same invocation.

## S1 - Route And Recovery

Every invocation reads the target plan's current summary before spending work.
GREEN consumes only a matching RED lineage; refactor consumes only a matching
GREEN summary. The declared implementation delta creates an implementation
successor with a new post-implementation candidate, rather than invalidating
the RED basis. Contract, validator, test selector, authority, or undeclared
write-set changes are real drift and create a successor preparation.

Acceptance: resume after each stage is idempotent; repeated failure fingerprints
stop before duplicate execution.

## S2 - Compatibility And Dogfood

Legacy one-shot lifecycle evidence is read-only continuity data. S0/S1 may use
the old adapter only as a one-time migration bridge to install the staged
primitive and route machine. After cutover, S2, 8-17 dogfood, and terminal-full
must use the staged adapter. New VDD-produced plans declare failure intent
only; Quick Dev generates the shell-free RED command and owns the observed
result.

Acceptance: a legacy plan cannot publish new staged evidence, and 8-17 reaches
its current terminal predicate through separate RED, implementation, GREEN,
and refactor actions.
