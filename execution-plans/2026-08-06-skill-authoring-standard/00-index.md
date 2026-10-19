# Skill Authoring Standard: Current Package A Repair

Current state: **requirements refreshed; canonical compilation blocked**.
This is not `plan-ready`, `implementation-complete` or `acceptance-passed`.
Updated: 2026-10-19. Main baseline:
`f7ac19dbc1dde82e73f91854b5dc0c157c78703a`.
Work branch: `fix/08-06-skill-authoring-plan-refresh`.

The 2026-10-19 compiler maintenance repair fixes grouped/cache execution-hint
projection and retains strict validation of the returned candidate. It also
keeps existing workflow controls in V3 authoring context instead of extracting
them as new Package A implementation features. All 25 product intent rows are
unchanged. See
[the V3 repair note](repair/2026-10-19-v3-projection.md). The latest reported
local compile stopped in V3 execution-contract validation. Because the source
role and V1 transport changed, current source-bound V1/V3 and downstream checks
must revalidate before Quick Dev; do not force the old V1/V3 output into reuse. The environment failure described
below remains the historical result of the 2026-10-18 online invocation.
No successful semantic publication is asserted by the maintenance tests.

## Current entry

1. Read [requirements.md](requirements.md): the complete, scoped Package A input.
2. Read [LOCAL-HANDOFF.md](LOCAL-HANDOFF.md): local compilation, the readiness
   gate and the current Quick Dev route.
3. Read [the reconciliation](repair/2026-10-18/reconciliation.md) for old-to-new
   coverage, preserved exclusions and why the old route cannot be reused.
4. Read [verification](repair/2026-10-18/verification.md) for checks actually
   performed and what remains unverified.

The user authorized repair of this existing directory, not implementation of
Package A production code. No standard/validator or Skill has been implemented
by this repair. Implementation remains the subsequent local Quick Dev task.

## Scope

Package A defines the standard, a deterministic **static package** validator,
reference fixtures and Package B migration guidance. Its 25 authoring intents
cover all 12 original SAS requirements. Four suggested implementation groups
organize the work; canonical compilation determines actual slice IDs and exact
behavior/Acceptance partitioning.

The completed 8-05 toolchain and 8-24 Phase capabilities are the baseline.
Their Runner, authorization, recovery, current CER probe and evidence mechanisms
are not new work in 8-06. Package B, BMAD/VDD knowledge queries, 7-31, S1/S2/S3,
internal review activation and app-server/SDK changes remain separate.

The VDD profile is `self-hosted`; development governance is off. No new Bootstrap
review, frozen knowledge receipt, Skill-input attestation or 95 report is needed.
External review does not require enabling the internal review Skill.

## Publication boundary

Current VDD only permits `scripts/vdd/compile_plan.py` to publish canonical
artifacts and `plan-ready`. The real public compiler was invoked and stopped
because `codex` is unavailable. No model API backend is configured either.
No worker fixtures, synthetic pass receipts or hand-authored semantic bundle
were substituted.

The output location is `current-plan/`, inside this same requirement directory.
This isolates the current-format publication from the incompatible historical
v1 contracts; it is not another requirement package or a new review lineage.
Until successful compilation, that directory has no consumable current plan.
The local start command must use `current-plan/` **after** publication, never the
historical root `implementation-contract.v1.json`.

## Historical records

All pre-refresh files except this navigation index are preserved byte for byte.
The original index is also preserved as
[00-index.before-refresh.md](repair/2026-10-18/00-index.before-refresh.md).
The root v1 requirements, implementation contract, command registry, plan/resume
states, 95 report, tools, frozen inputs and review/repair results describe their
original run only. Their `plan-ready`, authorization or blocked Bootstrap
wording does not describe this repair. Do not run their old plan-local combined
writers or import their evidence into the new Quick Dev run.

The later successful compiler output and its exact source identity become the
current machine-consumable input. A local maintainer/agent should then update
this navigation status with that real result without rewriting old evidence.
