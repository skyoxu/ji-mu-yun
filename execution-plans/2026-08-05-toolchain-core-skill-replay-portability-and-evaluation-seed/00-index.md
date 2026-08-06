# Toolchain Core Skill Replay Portability And Evaluation Seed

- Status: `implementation-authorized`
- Profile: `self-hosted`
- Profile reason: this plan changes a shared Toolchain validator capability and the VDD and Refactor Acceptance contracts that consume it.
- Plan ID: `toolchain-core-skill-replay-portability-and-evaluation-seed`
- Source brief ID: `TC-D1`
- Git baseline: `8c47a52fc8f241f76da9ccb5d936b0fafe807f0f`
- Baseline tree: `6963a7c3ef477ddabd0acd9459d268a8f2ceb982`
- Current step: begin `RMAP-S0` through the plan-owned Quick Dev TDD route; no slice has started yet.
- Recovery command: `py -3 -B execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/tools/validate_plan.py --implementation-state`

## Outcome

Replace future machine-specific Skill-package validation calls with one
repository-owned replay entrypoint. The entrypoint resolves an installed
validator through a bounded capability contract, proves compatibility with
detached positive and negative probes, records the resolved path, version and
content identity, and fails closed on missing, substituted, drifted or
incompatible capability.

Preserve the 2026-08-01 Refactor Acceptance plan byte-for-byte. Add a separate
compatibility replay record for its machine-bound terminal step, then convert
its three repaired failure families into explicitly non-authorizing evaluation
seed candidates. Re-run the workflow-model-routing terminal consumer as a
higher-level replay without claiming universal Skill quality.

## Scope

- One shared Toolchain Skill-package validation/replay CLI under `scripts/sc/`.
- A bounded capability descriptor and machine-readable replay receipt consumed
  by current terminal validators.
- Detached positive, negative, missing, substitution, drift and compatibility
  fixtures and tests.
- One append-only compatibility replay record for the historical 8-01 command.
- One evaluation-seed manifest and one stable-versus-candidate replay matrix.
- Minimal VDD and Refactor Acceptance instructions needed to consume the new
  repository-owned entrypoint.
- One current downstream replay of the workflow-model-routing control plane.

Out of scope: Phase service, hosted runtime, browser/API, workspaces, accounts,
sandbox behavior, TC-E0 implementation, quality-baseline publication, review
topology experiments, context-loading experiments, Miner/Memory, Skill version
promotion, autonomous Skill modification and RL.

## Authority

Authority order is `AGENTS.md`, Accepted ADRs, the current four core Toolchain
Skill contracts, `docs/know.md`, the frozen knowledge context, this directory's
machine artifacts, then explanatory prose. `docs/know.md` is a source brief and
grants no lifecycle authority. The 8-01 plan remains historical producer-owned
evidence; TC-D1 may only add separately owned append-only evidence.

## Lifecycle

The lifecycle is `draft -> plan-ready -> implementation-authorized ->
implementation-complete -> acceptance-passed -> archived`. VDD owns only
`draft` and `plan-ready`. The maintainer accepted the deterministic Round 3
repair evidence and published `implementation-authorized`; no implementation
slice has started. Quick Dev may later publish only `implementation-complete`
after the current terminal full validation passes. Refactor Acceptance
separately owns `acceptance-passed`.

## Implementation Order

`RMAP-S0 -> RMAP-S1 -> RMAP-S2 -> RMAP-S3`

- `RMAP-S0`: repository-owned validator capability and detached probes.
- `RMAP-S1`: byte-preserving historical compatibility replay.
- `RMAP-S2`: non-authorizing evaluation seeds and stable/candidate matrix.
- `RMAP-S3`: consumer integration, downstream replay and terminal closure.

Each slice declares one controlled RED or legacy-regression path, GREEN and
refactor commands, downstream dependents and recovery. Only `RMAP-S3` may
publish `implementation-complete`, and only after the terminal validator runs
all current commands.

## First-Class Directory Boundary

TC-D1 is the only directory created by this invocation. It cannot absorb,
publish, repair or implement TC-E0 (`2026-07-31-toolchain-workflow-evidence-
catalog-v1`) or TC-D2 through TC-D6. Those remain independent first-class
directories with their own baseline, knowledge context, lifecycle and
acceptance. TC-D1 seeds are inputs to a future TC-D2 plan; they are not a
quality baseline.

## Historical Evidence Preservation

No byte or lifecycle state under
`execution-plans/2026-08-01-refactor-acceptance-toolchain-compact-vdd/` may be
rewritten or auto-migrated. The absolute validator path in its terminal
validator remains historical evidence of the original machine. TC-D1 records
that limitation and a current compatibility replay in new artifacts whose
authority is local to TC-D1 and whose `authorizes` field is empty.

## Skill Delta Plus Evaluation Delta

The shared replay entrypoint is the Skill delta. Detached capability probes,
the historical compatibility record, the three seed candidates, the
stable-versus-candidate matrix and the downstream consumer replay are the
corresponding Evaluation delta. A future implementation change is incomplete
if it changes the replay behavior without updating or proving coverage by this
evaluation set.

## No Autonomous SkillOS Or RL

TC-D1 does not generate questions, modify Skills, promote candidates, update a
quality baseline, approve its own result or implement learned ranking or RL.
All evaluation outputs are non-authorizing. Any admission into a future Anchor,
Frontier, Challenge or Holdout set requires TC-D2 and maintainer disposition.

## Knowledge Gate

VDD consumed the current published generation whose source snapshot is
`fda1b959c205bc202528919d5b2496de52ecbf57`; current `main@8c47a52f` contains
only the corresponding derived publication delta after that source snapshot.
Locator selected repository rules, the historical 8-01 workflow, and ADR-0053
as the stable Refactor Acceptance consumer authority. The first ready context
that accepted mutable VDD and Acceptance Skill files was superseded through the
append-only VDD recovery path to avoid a self-hosted read-set collision. VDD
reread and hash-verified every current accepted source and created
`knowledge-context.v1.json` plus
`knowledge-context.freeze.v1.json`. The source brief `docs/know.md` remains a
direct VDD authority read because it is not a registered Catalog module. The
superseded context and receipt remain under their history directories.

## Validation

- Draft structure: `py -3 -B execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/tools/validate_plan.py --allow-draft`
- Plan-ready predicate: `py -3 -B execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/tools/validate_plan.py`
- Current implementation-authorized predicate: `py -3 -B execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/tools/validate_plan.py --implementation-state`
- Future terminal implementation predicate: `py -3 -B execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/tools/validate_implementation.py`
