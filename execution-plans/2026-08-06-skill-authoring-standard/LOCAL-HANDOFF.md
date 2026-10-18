# Local Handoff: Package A Repair To Current Quick Dev

This branch repairs requirements only. It cannot honestly be advertised as
ready for immediate Quick Dev execution yet: the temporary workspace lacked
Codex CLI/API credentials for the current VDD compiler's real semantic workers.
The missing step is **one local canonical compile/repair**, not a new round of
requirements design or a Bootstrap review. A successful compile is still
required; its result must not be assumed in advance.

## Inputs and authority

- Repository baseline: `f7ac19dbc1dde82e73f91854b5dc0c157c78703a`.
- Source: `execution-plans/2026-08-06-skill-authoring-standard/requirements.md`.
- Output: `execution-plans/2026-08-06-skill-authoring-standard/current-plan`.
- Compiler: current `.agents/skills/vdd-execution-plan/SKILL.md` and public CLI.
- Consumer: current `.agents/skills/quick-dev-tdd-adapter/SKILL.md`.
- Selected profile: `self-hosted`; development governance off.
- Scope: Package A only; no existing Skill modification, Package B migration,
  model/runtime change or Phase work is authorized by this document.

Use a clean worktree on the pushed branch; preserve unrelated local changes.
Read the repository instructions and this directory's index. If main has moved,
compare changes to the relevant contracts before rebasing or compiling. Do not
make the old 8-05 index's RMAP-S0 pointer into a new dependency: the maintainer
confirmed 8-05 and 8-24 were completed and merged; current code owns behavior.

## 1. Compile locally

The local machine needs its normal authenticated Codex CLI, current model
configuration and the repository's existing Python dependencies. Do not put
credentials or model secrets into the plan. The compiler uses the normal
configured model; this repair does not change model routing or force a model.
From the repository root in PowerShell:

```powershell
$planRoot = "execution-plans/2026-08-06-skill-authoring-standard"
$compiledPlan = "$planRoot/current-plan"
py -3 -B scripts/vdd/compile_plan.py --requirements "$planRoot/requirements.md" --out-dir $compiledPlan --profile self-hosted --resume-from first-failed-stage --result-json logs/08-06-local-plan-repair/compiler-result.json
```

`--resume-from first-failed-stage` is valid for the empty/failed target and retains
any actual compiler work when present. The temporary workspace's failed worker
outputs are not passed as a fixture cache or claimed as a reviewed predecessor.
Do not add `--worker-cache`, import internal compiler functions or fabricate
`plan-ready`. Do not use the execution-only handoff repair mode: the historical
root is not a valid published current semantic predecessor.

Inspect both exit code and result JSON. Continue only on exit 0 and
`status=plan-ready`, with the newly published semantic bundle, source/semantic
checks and slice contexts present. Any `repair-vdd` result remains a VDD issue:
follow the named first failed stage, preserve failure evidence, and repair only
its real cause. Do not change source scope or weaken predicates to make it pass.

The default service state is development. Respect the actual local service
state; do not disable an active production/test gate by copying an environment
override from an example. No governance override is included in the command.

## 2. Enter current Quick Dev

After successful compilation, obtain the first dependency-ready slice from the
published bundle. The authoring groups A1--A4 and historical SAS-S0 IDs are not
substitutes for the compiler's slice IDs. Read the published dependency graph
and the selected `agent-context.json`; start with a zero-dependency slice.

```powershell
py -3 scripts/quick_dev/run.py --plan $compiledPlan --slice <published-slice-id> --profile self-hosted --recommendation-only
py -3 scripts/quick_dev/run.py --plan $compiledPlan --slice <published-slice-id> --profile self-hosted
```

Replace `<published-slice-id>` before running. Q0 is read-only. Q1 must return
`preflight-passed`; `environment-blocked`, legacy routing or `repair-vdd` is not
permission to implement. Follow the current Skill's execution/recovery guides
and create a fresh explicitly named run under `logs/08-06-implementation/`.
No old RED receipt, plan-local terminal predicate or 'latest success' scan is an
execution predecessor.

Q2 authors the declared pytest cases, helpers and fixture data before freezing
real case mappings. Current CER probes decide present/missing/unverifiable:

- Present behavior goes through regression and terminal coverage.
- Missing behavior requires a real assertion-based RED, bounded GREEN and the
  same frozen selector through REFACTOR.
- Missing environment, import/setup errors, unavailable production binding,
  zero cases or ambiguous evidence stop that scope; they are not product RED.

`expected-red` is an intent, not a preassigned runtime result. Tests must invoke
the real production entry and check an independent expected outcome. Never
create an unconditional failing placeholder or write production from Q2 merely
to get a legal-looking receipt. If the current runner cannot materialize a
valid first-use entry for new production, report the exact contract limitation;
do not reintroduce the old file-absence RED.

## 3. Work within declared boundaries and finish

Production writes are limited to the standard/ADR/index, policy/schemas and the
two validator modules listed in requirements.md. Q2 owns the four test modules,
helper and fixture subtree. Existing Skills, Quick Dev/VDD engines, shared LLM
entrypoints, Phase code and historical evidence remain outside the write set.
Production owners and frozen execution snapshots must not overlap.

Use targeted group tests and applicable predecessor regressions while working.
The terminal command executes the four declared Package A pytest modules.
After stable targeted checks, use the actual current Q7/Q8 route for final
coverage and implementation-complete. A pytest pass alone is not that state.
Hand Q8's native result and exact snapshot/source inputs to external review and
run-refactor-implementation-acceptance; only Acceptance owns acceptance-passed.
Do not alter the normative source/fixtures/selector during GREEN to make it pass.

The reference fixture is not an installed Skill. Do not scan all five existing
Skills as a mandatory compliance gate. Package B later migrates their current
contracts without reactivating internal review. BMAD/VDD knowledge-query work
still occurs after Package A and before that migration, per the agreed sequence.
