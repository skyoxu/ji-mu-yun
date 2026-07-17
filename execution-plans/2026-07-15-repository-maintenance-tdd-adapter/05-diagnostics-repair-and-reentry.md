# Diagnostics, Repair, And Re-Entry

## Diagnostic Contract

Every failure record contains:

- stable rule and diagnostic IDs;
- plan, contract, slice, run, and predecessor identities;
- source, contract, validator, command-registry, Git index, read-set, dependency, and candidate hashes;
- expected and observed states;
- failure family and severity;
- repair owner and remediation ID;
- rerun command and next allowed state;
- superseded diagnostic and run IDs where applicable.

## Failure Routing

| Failure | Earliest owner |
| --- | --- |
| Wrong goal or ownership | intent, ADR, or standard |
| Missing/ambiguous field | common schema or plan instance |
| False oracle or wrong fixture | validator and fixture |
| Non-independent slice | slice decomposition |
| Expected RED not observed | test or acceptance design |
| Valid RED but wrong implementation | backend candidate |
| Semantic P0/P1 | implementation repair before acceptance |
| Stale hash or concurrent closure drift | run recovery and re-entry |

Never weaken a validator to match a candidate without an explicit contract delta and regression counterexample.

## Recovery State

Run evidence lives at:

`logs/tdd-adapter/<plan-id>/<slice-id>/<run-id>/`

It is append-only and records predecessor/supersession lineage. Resume is allowed only when every bound hash, Git index, execution read set, dependency closure, and current acceptance blocker matches.

On relevant drift:

1. mark the original run `stale`;
2. preserve its evidence unchanged;
3. create a successor with `predecessor_run_id` and `supersedes_run_id`;
4. start the successor at `initialized`, never `stale`;
5. rerun prepare and the required RED gate.

Unrelated worktree changes outside all closures are appended as observations and do not restart the run.

Within one run, Capsule and attempt bytes are also immutable. Capsule revisions link by predecessor Capsule hash. `ATTEMPT-001`, `ATTEMPT-002`, and later IDs are monotonic; each request and decision names the previous attempt, and each decision binds the previous decision hash. The decision is written last. A crash before that write leaves an `incomplete` attempt that cannot satisfy a stage predicate.

Retry creates a new attempt directory and new event records instead of repairing old bytes. Only one lineage may be accepted for a represented RED, GREEN, or REFACTOR stage. Later rejected or superseding attempts remain visible, and recovery consumes the newest deterministic blocker plus the complete hash chain rather than backend prose or a mutable summary ledger.

## P2 Re-Entry

A P2 disposition is valid only when:

- fixed evidence is current; or
- deferral includes owner, non-impact proof, expiry or recheck trigger, and exact closure test.

Security, data-loss, authority-bypass, evidence-integrity, irreversible-mutation, or release-bypass P2 findings are high-risk and non-deferrable. An expired deferral automatically moves acceptance to blocked until a new valid disposition exists.

## Stop-Loss

- Three failed repair attempts at the same earliest layer require scope reduction or manual pause.
- Three advisory confidence-improvement rounds are the maximum; confidence never changes authority.
- Bootstrap full semantic review follows its own two-round default and three-round hard limit.
- Historical evidence is never rewritten to make a later run pass.
- Capsule overwrite, attempt-ID reuse, raw sensitive-content persistence, or transition authority in `adapter-decision` stops the run.

The current stop-loss owner is [`schemas/review-blocking-state.v1.json`](schemas/review-blocking-state.v1.json). It records `manual_pause_after_round_3`, forbids Round 4 under the current policy revision, and requires a new external policy decision for semantic re-entry.

Deterministic repair may produce new plan-local validation evidence and a corrected candidate, but it cannot mutate the Round 3 disposition. After repair, semantic re-entry begins only through a separately recorded durable policy decision and a new authority cycle; it must not be represented as Round 4 of the existing `changeId` policy cycle.

## Confirmed P1 Repair Lineage

The repair baseline is `logs/vdd-plan-repair/repository-maintenance-tdd-adapter/20260716-p1-repair-baseline/baseline-manifest.json`. It preserves Bootstrap findings `BSR-06FAE36E33FCD8DF`, `BSR-074B1DAA968AF43B`, `BSR-592AAB6881E55672`, `BSR-83E672E6803298AD`, and `BSR-9CAF6A01EDF7AAA7`. Closure requires the matching schema, authority-hash, typed-path, nested-glob, and S0-exit fixtures plus a fresh composite result; this section is not closure evidence by itself.

Round 2 repair uses `logs/vdd-plan-repair/repository-maintenance-tdd-adapter/20260716-p1-r2-repair-baseline/baseline-manifest.json` and preserves `BSR-813CC04B3E5C6009`, `BSR-BA46227BDFEF4DA7`, and `BSR-C69B8ECB622B98EA`. Closure requires a controlled-temp test, all-slice exit-proof counterexamples, exact source-location counterexamples, and a new candidate envelope. Round 1 and Round 2 evidence remain immutable predecessors.

Round 3 repair uses `logs/vdd-plan-repair/repository-maintenance-tdd-adapter/20260716-p1-r3-repair-baseline/baseline-manifest.json` and preserves all eight finalized Round 3 P1 dispositions. The repair covers slice requirement union, restricted-token junction testing, S0 ownership RED, independent shadow-byte baselines, and current S6/S7 evidence binding. Because the semantic review hard limit is exhausted, deterministic closure retains `manual_pause` and cannot claim the Bootstrap blockers closed.

The follow-up control-chain repair baseline is `logs/vdd-plan-repair/repository-maintenance-tdd-adapter/20260716-222-repair-baseline/baseline-manifest.json`. It preserves the pre-repair target hash and the local false-positive `plan-ready` PASS. Its candidate may prove only `plan-repair-verified`; it cannot rewrite any prior disposition.
