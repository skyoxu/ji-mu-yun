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
| Candidate diff, test patch, or accepted-attempt fold incomplete | candidate evidence validator and evidence maintainer |
| S7 references a stale or superseded S6 candidate | acceptance predecessor contract |
| S0-S6 lineage omits a slice or breaks predecessor/event hashes | candidate lineage contract |
| Protected handoff or release lacks custody outside the workflow identity | protected-verifier identity boundary |
| Runtime P2 or verifier source evidence is missing/stale | Bootstrap acceptance evidence contract |
| Target plan audit is missing, late, or finds an unresolved defect | target-plan lifecycle contract, then VDD repair |
| 95 report index is missing, stale, duplicate, escaping, or bypassed by a repository-wide scan | non-authoritative index contract, then target-directory-only recovery |
| Target `95-*.md` is missing, ambiguous, hash-authoritative, or rewritten | target report ownership and append-only boundary |
| Overall result is requested before the current terminal predicate passes | terminal reporter; no write is allowed |

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

A target-plan repair is relevant drift by definition. It invalidates every pre-repair freeze and TDD stage observation. After the target validator passes and the change entry is appended, recovery creates or refreezes a successor identity before RED; it never patches an existing Capsule, baseline, or result envelope to point at the repaired plan.

Within one run, Capsule and attempt bytes are also immutable. Capsule revisions link by predecessor Capsule hash. `ATTEMPT-001`, `ATTEMPT-002`, and later IDs are monotonic; each request and decision names the previous attempt, and each decision binds the previous decision hash. The decision is written last. A crash before that write leaves an `incomplete` attempt that cannot satisfy a stage predicate.

Retry creates a new attempt directory and new event records instead of repairing old bytes. Only one lineage may be accepted for a represented RED, GREEN, or REFACTOR stage. Later rejected or superseding attempts remain visible, and recovery consumes the newest deterministic blocker plus the complete hash chain rather than backend prose or a mutable summary ledger.

## P2 Re-Entry

A P2 disposition is valid only when:

- fixed evidence is current; or
- deferral includes owner, non-impact proof, expiry or recheck trigger, and exact closure test.

Security, data-loss, authority-bypass, evidence-integrity, irreversible-mutation, or release-bypass P2 findings are high-risk and non-deferrable. An expired deferral automatically moves acceptance to blocked until a new valid disposition exists.

Deferred P2 evidence is not closure evidence. It must bind an owner authority chained to the profile root, non-impact evidence, a root-authorized immutable command descriptor, current recheck evidence, expiry, and recheck trigger. When a disposition changes to fixed or refuted, a runner-produced process result derived from the hash-chained event log and actual stdout/stderr bytes becomes mandatory. Failed commands preserve their event and never emit a success result. The repository Bootstrap schema and producer own these fields; this plan only consumes them.

## Stop-Loss

- Three failed repair attempts at the same earliest layer require scope reduction or manual pause.
- Three advisory confidence-improvement rounds are the maximum; confidence never changes authority.
- Bootstrap full semantic review follows its own two-round default and three-round hard limit.
- Historical evidence is never rewritten to make a later run pass.
- Capsule overwrite, attempt-ID reuse, raw sensitive-content persistence, or transition authority in `adapter-decision` stops the run.
- A stale or ambiguous index, recursive execution-plans scan, missing or ambiguous target `95-*.md`, failed target validator, reuse of a pre-repair identity, or attempted completion entry before terminal PASS stops the run without modifying the report.

The current stop-loss owner is [`schemas/review-blocking-state.v1.json`](schemas/review-blocking-state.v1.json). It remains immutable. [`schemas/review-policy-reentry.v1.json`](schemas/review-policy-reentry.v1.json) is the only successor selector: pending states authorize nothing; `reentry_authorized` requires a schema-valid repository Bootstrap successor decision, a current authorization-event hash, distinct change/policy/authority/review/input lineage, and a clean v2 envelope that exactly matches a fresh repository producer recomputation.

That successor selector authorizes only `manual-pause-reentry`, which the composite validator consumes independently. `RMAP-BLOCK-PROTECTED-VERIFIER-IDENTITY` remains open only for protected handoff and release. Clearing it requires either independent verifier/evidence custody or a trusted signed envelope binding candidate, source, validator, policy, and verifier identity. Ordinary plan-ready recovery does not require that external identity. Recovery remains append-only and never rewrites the historical blocker or old diagnostic output.

Deterministic repair may produce new plan-local validation evidence and a corrected candidate, but it cannot mutate the Round 3 disposition. After repair, semantic re-entry begins only through a separately recorded durable policy decision and a new authority cycle; it must not be represented as Round 4 of the existing `changeId` policy cycle.

## Confirmed P1 Repair Lineage

The repair baseline is `logs/vdd-plan-repair/repository-maintenance-tdd-adapter/20260716-p1-repair-baseline/baseline-manifest.json`. It preserves Bootstrap findings `BSR-06FAE36E33FCD8DF`, `BSR-074B1DAA968AF43B`, `BSR-592AAB6881E55672`, `BSR-83E672E6803298AD`, and `BSR-9CAF6A01EDF7AAA7`. Closure requires the matching schema, authority-hash, typed-path, nested-glob, and S0-exit fixtures plus a fresh composite result; this section is not closure evidence by itself.

Round 2 repair uses `logs/vdd-plan-repair/repository-maintenance-tdd-adapter/20260716-p1-r2-repair-baseline/baseline-manifest.json` and preserves `BSR-813CC04B3E5C6009`, `BSR-BA46227BDFEF4DA7`, and `BSR-C69B8ECB622B98EA`. Closure requires a controlled-temp test, all-slice exit-proof counterexamples, exact source-location counterexamples, and a new candidate envelope. Round 1 and Round 2 evidence remain immutable predecessors.

Round 3 repair uses `logs/vdd-plan-repair/repository-maintenance-tdd-adapter/20260716-p1-r3-repair-baseline/baseline-manifest.json` and preserves all eight finalized Round 3 P1 dispositions. The repair covers slice requirement union, restricted-token junction testing, S0 ownership RED, independent shadow-byte baselines, and current S6/S7 evidence binding. Because the semantic review hard limit is exhausted, deterministic closure retains `manual_pause` and cannot claim the Bootstrap blockers closed.

The follow-up control-chain repair baseline is `logs/vdd-plan-repair/repository-maintenance-tdd-adapter/20260716-222-repair-baseline/baseline-manifest.json`. It preserves the pre-repair target hash and the local false-positive `plan-ready` PASS. Its candidate may prove only `plan-repair-verified`; it cannot rewrite any prior disposition.

The 1200 repair baseline is `logs/vdd-plan-repair/repository-maintenance-tdd-adapter/20260717-1200-repair-baseline/baseline-manifest.json`. It preserves the 66-file pre-repair inventory, the old 51-test self-consistent PASS, the expected manual-pause block, and the missing successor, cross-slice lineage, supersession, runtime P2, Windows containment, and compatibility-classification controls. New evidence supersedes none of the historical review dispositions.

The 1300 repair baseline is `logs/vdd-plan-validation/repository-maintenance-tdd-adapter/20260717-1300-repair/baseline-manifest.json`. It preserves the 55-test green result that still accepted an empty policy decision and five-field envelope, plus all six 1300 findings. This repair changes the oracle and producer contracts; it does not rewrite earlier validation or review evidence.
