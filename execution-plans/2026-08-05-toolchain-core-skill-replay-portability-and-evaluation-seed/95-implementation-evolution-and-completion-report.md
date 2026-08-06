# Implementation Evolution And Completion Report

Plan: `toolchain-core-skill-replay-portability-and-evaluation-seed`  
Authority: append-only continuity report; `authorizes=[]`

## Initial VDD Entry - 2026-08-05

- Result: created the only TC-D1 self-hosted execution-plan directory
  authorized by `docs/know.md`.
- Baseline: `main@8c47a52fc8f241f76da9ccb5d936b0fafe807f0f`.
- Scope: portable Skill-package validator capability, byte-preserving 8-01
  compatibility replay, three non-baseline evaluation seed candidates, a
  stable-versus-candidate matrix and one downstream consumer replay.
- Boundary: TC-E0 and TC-D2 through TC-D6 remain independent directories.
- Historical disposition: the 8-01 directory remains byte-preserving and no
  historical lifecycle state is changed.
- Knowledge status: blocked before plan-ready because the published Catalog is
  stale and the new target does not yet exist on pinned main for a separately
  confirmed publication request.
- Lifecycle: `draft`; implementation is not authorized.

## Plan-Ready Publication - 2026-08-05

- Locator result: matched the published source snapshot and returned current
  repository rules, historical workflow and Toolchain consumer contracts.
- Adapter decisions: accepted `AGENTS.md`, the 8-01 plan index and ADR-0053 for
  their named required modules; the mutable VDD and Refactor Acceptance Skill
  candidates were rejected as insufficiently specific and remain outside the
  frozen VDD read set.
- Freeze: `knowledge-context.v1.json` and
  `knowledge-context.freeze.v1.json` bind the exact accepted source and read-set
  hashes and carry `authorizes=[]`.
- Direct authority: `docs/know.md` remains a mandatory source read outside the
  derived Catalog because it is not registered as a Catalog module.
- Lifecycle: VDD published only `plan-ready`; implementation, acceptance,
  release and archive remain unauthorized.

## Knowledge Freeze Supersession - 2026-08-05

- Finding: the first ready context accepted the VDD and Refactor Acceptance
  Skill files even though `RMAP-S0` and `RMAP-S3` declare them in the candidate
  write set. A later slice would therefore reproduce the known
  `self-hosted-knowledge-read-set-collision` failure family.
- Disposition: used the VDD-owned append-only supersession command and bound the
  exact outgoing context hash plus the reason. The original context and receipt
  remain in their history directories.
- Current accepted sources: `AGENTS.md`, the immutable 8-01 plan index, and
  ADR-0053. Current Skill bytes remain directly frozen in
  `authority-manifest.v1.json` and candidate identity, not in the mutable
  knowledge read set.
- Result: knowledge preflight remains ready and non-authorizing; lifecycle
  remains `plan-ready`.

## Round 1 Bootstrap Repair - 2026-08-05

- Review: `tc-d1-upstream-plan-r1b-20260805` finalized `blocked` with five
  confirmed P1 findings. The two findings about omitted consumer tests share
  one repair and are tracked as one repair batch.
- Lifecycle repair: plan validation now has an explicit
  `--implementation-state` mode for the Quick Dev terminal predicate; normal
  VDD validation remains `plan-ready` only.
- Consumer coverage repair: terminal validation runs the declared VDD Skill
  tests and Refactor Acceptance replay-targeted tests before publishing
  implementation-complete.
- Historical protection repair: terminal validation compares the complete
  current 8-01 file set and bytes against the frozen baseline commit, including
  unexpected candidate files.
- Authority repair: the two intentionally mutable Skill sources are declared
  explicitly, and terminal output records their current hashes while immutable
  authority sources remain exact-hash checked.
- Validation: current `plan-ready` validator and plan-local unit tests pass;
  terminal implementation validation remains intentionally RED until the
  four implementation slices produce their declared artifacts.

## Round 2 Bootstrap Repair - 2026-08-05

- Review: `tc-d1-upstream-plan-r2b-20260805` finalized `blocked` with six
  independently confirmed P1 findings across four repair surfaces.
- Plan-time historical protection: `validate_plan.py` now compares the current
  8-01 candidate file set and bytes with the frozen baseline in addition to
  checking the current `main` tree identity.
- Historical replay contract: RMAP-S1 now requires structured bindings for the
  frozen historical validator, the recorded historical command evidence, and
  a hash-bound passing receipt from the current repository wrapper.
- Evaluation seed contract: every RMAP-S2 seed now requires nonempty,
  repository-relative, SHA-256-bound native evidence and must include its
  corresponding historical repair closure.
- Replay matrix contract: RMAP-S2 now requires exactly one positive, negative,
  historical compatibility, dirty baseline, knowledge read-set and closed
  policy case; every case names a validation surface and expected observation.
- Regression coverage: eleven plan-local tests pass, including negative cases
  for historical worktree drift, weak replay records, empty native evidence,
  incomplete matrices and malformed matrix categories.
- Lifecycle: plan validation remains `plan-ready`; terminal implementation
  validation remains intentionally RED because RMAP-S0 through RMAP-S3 have
  not yet produced their implementation artifacts.

## Round 3 Bootstrap Repair - 2026-08-05

- Review: `tc-d1-upstream-plan-r3b-20260805` finalized `blocked` at the
  three-round hard limit with eight independently confirmed P1 findings across
  four repair surfaces.
- Executed historical replay: RMAP-S1 now freezes the exact repository wrapper
  command, target Skill package, package-manifest algorithm, capability file,
  resolved validator identity and detached positive/negative probe outcomes.
  Terminal validation executes that command and requires its stdout JSON to
  equal the saved non-authorizing receipt.
- Executed evaluation matrix: every matrix case now has a unique ID and every
  replay result binds the same category, validation surface and expected
  observation plus native evidence. Terminal validation executes the matrix
  command and requires observed results to equal expected observations and the
  stdout JSON to equal the saved receipt.
- Lifecycle authority: implementation-authorized and implementation-complete
  validation now enforce exact state owner, authorizes and does-not-authorize
  fields, preventing Acceptance or release authority from entering the Quick
  Dev terminal closure.
- Core Skill routing: implementation completion now requires both VDD and
  Refactor Acceptance Skill instructions to contain the fixed repository-owned
  package-validation section and target-specific command. Hash presence alone
  is no longer sufficient.
- Regression coverage: eighteen plan-local tests pass, including wrong target,
  incomplete command, unexecuted matrix, observation mismatch, receipt/stdout
  mismatch, missing Skill routes and lifecycle overclaim cases.
- Lifecycle: the plan remains `plan-ready`; implementation validation remains
  intentionally RED until the four implementation slices produce and execute
  their declared artifacts. Full semantic Round 4 is prohibited.

## Maintainer Manual Disposition And Implementation Authorization - 2026-08-05

- Decision: the maintainer accepted
  `logs/r/tcd1r3-manual-pause-repair-evidence.json` after the three-round
  `bootstrap-upstream-plan` lineage entered manual pause.
- Binding: `plan-state.v1.json` records the accepted evidence path and SHA-256;
  the blocked Round 3 review and its validation envelope remain unchanged.
- Lifecycle: advanced from `plan-ready` to `implementation-authorized` under
  maintainer ownership. This authorizes starting RMAP-S0 only; it does not
  authorize implementation-complete, Acceptance, release or archive.
- Resume: no slice has started or completed. The next action is the controlled
  RMAP-S0 RED/GREEN/refactor sequence through the plan-owned Quick Dev route.
