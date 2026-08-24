# Implementation Evolution And Completion Report

Plan: `refactor-acceptance-toolchain-compact-vdd`
Authority: append-only continuity report; `authorizes=[]`

## Initial Entry - 2026-08-01

- Result: self-hosted plan source created after Acceptance prerequisite audit.
- Trigger: the workflow model routing target cannot enter Acceptance because a
  compact VDD prerequisite projection and complete toolchain policy are absent.
- Current candidate: mixed toolchain/Phase; the existing Phase policy covers
  the shared backend but leaves the repository workflow partition unreviewed.
- Dirty dependencies: current Acceptance changes are frozen by path and hash;
  only declared overlap may incorporate those bytes.
- Lifecycle: `plan-ready` only.

## Implementation Authorization - 2026-08-01

- Authority: the maintainer agreed to the proposed self-hosted Acceptance
  extension after the prerequisite audit failed closed.
- Lifecycle: `implementation-authorized`.
- Boundaries: no original target Acceptance run starts until this plan's
  terminal predicate passes; no state beyond implementation is authorized.

## RA-TC-S0 - Toolchain Domain Policy

- RED: `tests/test_toolchain_domain.py` was absent.
- GREEN: 5 toolchain-domain tests, 53 existing run-input tests, and the schema
  suite passed.
- Result: `resolve-code-review-policy` supports a closed toolchain policy,
  records shared Phase entrypoints as cross-domain dependencies, rejects
  uncovered paths, and preserves the Phase-only compatibility entrypoint.

## RA-TC-S1 - Compact VDD Prerequisite Projection

- RED: `tests/test_compact_vdd_projection.py` was absent.
- First GREEN attempt: exposed a Windows 8.3 versus expanded temp-path custody
  comparison and a fixture newline-normalization error.
- Repair: custody retains absolute lexical spelling after rejecting every link
  and reparse component; the fixture restores exact Git blob bytes.
- GREEN: 3 projector tests and all 53 existing run-input tests passed.
- Result: explicit changed paths produce complete baseline/candidate manifests,
  deletion tombstones, a frozen snapshot, run request, action DAG, command
  registry, policy copy, knowledge binding, and a non-authorizing bundle.

## RA-TC-S2 - Migration And Terminal Replay

- GREEN: package tests passed 7 tests, CLI package closure passed, Skill
  Creator quick validation passed, and `git diff --check` reported no errors.
- Accepted decision: ADR-0053 records toolchain policy coverage, explicit
  cross-domain dependencies, and compact prerequisite projection.
- Terminal command:
  `py -3 execution-plans/2026-08-01-refactor-acceptance-toolchain-compact-vdd/tools/validate_implementation.py`.
- Terminal result: PASS in 175.8 seconds. All 6 registered commands returned
  zero, including the full Acceptance suite and the original workflow model
  routing terminal replay.
- Lifecycle: `implementation-complete`.
- Authority: does not authorize target Acceptance, release, or archive.

## Repair Round 1 - Dirty Baseline Overlay Custody

- Finding: a real compact-VDD consumer includes a file that was dirty before
  the candidate; using HEAD alone would absorb prior maintainer bytes.
- Repair: `baselineOverlaySources` now replaces only explicitly declared blobs
  in a temporary Git index and publishes an immutable synthetic baseline
  commit without moving refs or changing the worktree.
- GREEN: 4 projection tests and all 53 existing run-input tests passed.
- Terminal replay: all 6 registered commands passed in 186.4 seconds; plan
  validation and `git diff --check` also passed.
- Closure: `repair/round-1/repair-closure.json` binds the repair plan,
  repaired source and test bytes, terminal validator, and validation results.
- Lifecycle remains `implementation-complete`; `authorizes=[]` for this repair.

## Repair Round 2 - Self-hosted Locator Candidate Bound

- Finding: the Acceptance knowledge adapter could not bind the canonical
  Locator candidate limit, so changed governance sources in rejected read sets
  blocked every self-hosted context.
- Repair: `--max-candidates` now accepts only 1 through 12, is hash-bound in the
  locator request, and is passed to the canonical Locator CLI.
- GREEN: all 5 knowledge-context tests passed, including request/CLI binding
  and invalid-bound rejection.
- Terminal replay: all 6 registered commands passed in 189.9 seconds.
- Closure: `repair/round-2/repair-closure.json` binds source, test, repair plan,
  terminal validator, and results with `authorizes=[]`.
- Lifecycle remains `implementation-complete`.

## Repair Round 3 - Architecture Index Policy Coverage

- Finding: real policy resolution rejected `docs/architecture/ADR_INDEX_PHASE.md`
  because only `docs/architecture/phase-service/` was covered.
- Repair: the closed prefix now covers `docs/architecture/`, with a refreshed
  canonical policy revision and an ADR-index positive fixture.
- GREEN: all 5 toolchain-domain tests passed; the unsupported Godot path still
  fails closed.
- Terminal replay: all 6 registered commands passed in 190.1 seconds.
- Closure: `repair/round-3/repair-closure.json` binds the policy, test, repair
  plan, terminal validator, and results with `authorizes=[]`.
- Lifecycle remains `implementation-complete`.
