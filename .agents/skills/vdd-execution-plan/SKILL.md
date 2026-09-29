---
name: vdd-execution-plan
description: Create or repair a complete verification-driven execution-plan directory when the user explicitly requests that outcome. Do not use for direct implementation of one standalone requirements Markdown file.
---

# VDD Execution Plan

Create plans that make observable behavior and current validation decide completion. This repository is maintained by one trusted person and an AI assistant: do not add multi-writer, signer, reviewer-identity, or adversarial-custody controls unless a separate requirement explicitly needs them.

Select the operation before loading detailed guidance. For create or repair, read [the planning guide](references/planning-operation.md), [the solo-maintainer standard](references/solo-maintainer-vdd-standard.md), [clarification rules](references/clarification-gate.md), and [lifecycle rules](references/lifecycle-state-contract.md). In the standard, read Governance Activation and Required Controls for both modes, Freshness And Repair when repairing, and Optional Controls only when that control is selected. For Skill maintenance, inspect the affected operation's references and run the package checks below; do not start a plan compiler merely to edit this Skill.

| Operation | Additional reading |
| --- | --- |
| Create a complete directory | Planning guide and common rules below |
| Repair or resume compilation | Planning guide; preserve the original target and inspect the first failed stage |
| Governance enabled | [Governance operations](references/governance-operation.md), including knowledge and Skill-input gates, before publication |
| Governance disabled | Current sources and planning rules; do not load governance procedures |

## Phase Service State And Governance Mode

Resolve governance from `PHASEA_SERVICE_STATE=development|test|production`;
an unset state is `development`. `auto` disables governance in development
and enables it in test and production. An explicit `--governance-mode
on|off|auto` overrides `JIMUYUN_GOVERNANCE_MODE`, which overrides the phase
state.

With governance disabled, do not create frozen knowledge or Skill-input
attestations, source-freeze/conformance, external review, candidate binding,
maintainer authorization, review lineage, custody, signature, or `95-*.md`
governance artifacts. Inspect the current repository sources directly and keep
the plan compact. This never removes behavior/acceptance coverage, dependency-
scoped implementation slices, one failure intent per active behavior, runnable
targeted commands, RED ownership by Quick Dev, declared write boundaries, or
the terminal full validation command.

## Route Input Before Profile

One standalone requirements Markdown file routes to direct implementation and creates no VDD directory, lifecycle bundle, 95 report, or Bootstrap run. Only an explicit request to create a complete execution-plan directory routes to VDD `create`; only an explicit request to repair a complete existing directory routes to VDD `repair`. Never infer either VDD route from file contents or growing task complexity.

## Canonical Compiler Entry

For VDD `create` and `repair`, `scripts/vdd/compile_plan.py` is the only public plan compiler entry. Invoke it as a process from the repository root; callers must not import the internal semantic compiler modules directly or hand-author `plan-ready`. The CLI installs the complete repository-owned semantic patch stack and alone may publish current canonical plan artifacts, preserving the repository/plan authority boundary accepted in [ADR-0041](../../../docs/adr/ADR-0041-bootstrap-review-execution-control-plane-ownership.md).

Use the selected profile with the canonical entry:

```text
py -3 scripts/vdd/compile_plan.py --requirements <requirements.md> --out-dir <execution-plans/plan> --profile <standard|resumable|self-hosted>
```

For an existing failed compiler directory, add `--resume-from first-failed-stage`. A nonzero exit or any status other than `plan-ready` remains a VDD repair result; no caller may promote it. `--recommendation-only` performs no plan publication and never represents readiness.

For an already reviewed plan whose only defect is the Quick Dev execution
handoff, use `--repair-quick-dev-handoff-from <predecessor-dir>` with the
unchanged requirements and a distinct empty successor `--out-dir` inside the
same repair scope. The predecessor profile is retained. This mode preserves
semantic scope and records V1/V4 reuse; it performs no model calls. Read
[the planning guide](references/planning-operation.md) for its exact limits.

For real-worker quality evaluation, `scripts/vdd/evaluate_real_semantic_quality.py`
supervises the compiler with `--compile-timeout-seconds` (default 3600), distinct
from the optional `--repair-timeout-seconds` override. It prints the progress
path at launch and retains the run directory. Inspect
`plan/.compiler-work/compiler-progress.jsonl` for stage/worker start and return
events; an unmatched start locates the last observed wait, not its cause.
Timeout produces `compile-timeout`, never acceptance evidence. Windows process
cleanup targets only the owned PID tree; inspect `cleanup_error` if termination
fails. Existing caches and worker outputs remain available for offline diagnosis.

## Choose The Profile First

Choose the least complex profile that serves a real consumer. Record the selected profile and reason in the plan.

| Profile | Use when | Required additions |
| --- | --- | --- |
| `standard` | Ordinary feature, fix, documentation change, or bounded refactor | One compact plan document, lifecycle state, Git baseline/current scope, implementation slice(s), declared failure intent and acceptance targets, targeted commands, and one terminal full validation command. |
| `resumable` | Work crosses sessions, has dependent slices, or can leave partial state | `standard` plus compact resume state, dependency-scoped slice status, recovery instructions, and an indexed append-only `95-*.md` report. |
| `self-hosted` | The work changes VDD, Quick Dev, acceptance/review routing, or a controlling validator | `resumable` plus only the protocol fixtures and migration checks consumed by the changed workflow. Stabilize the changed layer with targeted checks before one end-to-end replay. |

Do not create fixed `00-08`/`96-99` books, custom schemas, a custom validator, mutation fixtures, a 95 report, Bootstrap Review, trust roots, attempt ledgers, or effect-fold records for a `standard` plan unless a concrete consumer cannot use an existing repository command or contract. One owner artifact may map requirements, sources, acceptance, and coverage.

## Clarify Only Material Boundaries

Inspect repository authority, current state, relevant callers, protected paths, and existing tests before asking. Ask only when an answer changes scope, compatibility, destructive behavior, protected-path approval, or acceptance. Zero questions is valid.

An initial explicit write authorization is enough to begin writing when no material blocker remains. Persist a minimized clarification/resume record only when an unresolved decision must survive a session boundary; do not create an active-run registry, cross-process lock, or identity attestation by default. `clarification_state.py` is an optional single-writer resume helper, not a default plan artifact. Its current state uses typed, acyclic CQ dependencies and explicit invalidate/reopen; legacy state is hash-bound and read-only, and sensitive current state terminates in a sanitized quarantine envelope.

## Lifecycle And Implementation

Use the static transition contract in [references/lifecycle-state-contract.json](references/lifecycle-state-contract.json):

`draft -> plan-ready -> implementation-authorized -> implementation-complete -> acceptance-passed -> archived`

VDD owns `draft` and `plan-ready`. With governance enabled, the maintainer
may explicitly publish `implementation-authorized` without Bootstrap evidence;
Bootstrap Review is optional supplemental evidence and never publishes a
lifecycle state. With governance disabled, `plan-ready` routes directly to
Quick Dev and no authorization receipt is created. Quick Dev may publish only
`implementation-complete`; acceptance and archive are separately owned. New
plans emit no old state names; repair plans may read them only through the
documented compatibility adapter.

For each slice, name its intended behavior, failure intent (the test selector and
expected observable failure before the change), GREEN/acceptance target,
declared downstream dependents, and recovery action. VDD owns none of the RED
execution: it must not emit a RED command descriptor, mode, run ID, receipt,
hash, predecessor, or imported historical evidence. Quick Dev resolves the
declared selector after freezing its current candidate, runs the RED command,
and owns the resulting observation under its current run directory. A VDD plan
that finds the behavior already present removes it from implementation scope and
keeps it only as current regression/terminal coverage; it must not use a
legacy path to manufacture a missing RED. Legacy RED import remains a
read-only compatibility path for already-versioned historical plans, never an
artifact that a newly created or repaired VDD plan may publish.

During repair, first stabilize the smallest affected layer. A slice-local change invalidates that slice and its declared downstream dependents only. A shared lifecycle contract, global validator semantic, baseline identity, or dependency used by every slice requires one terminal full replay after targeted stabilization. Targeted validation never authorizes completion. Before publishing `implementation-complete`, run one current terminal full validation.

## Candidate, Review, And Reports

Use current scoped Git identity for TDD freshness and preserve invalidated evidence as historical. Only when governance is enabled, read [governance operations](references/governance-operation.md) before freezing inputs or preparing review/report artifacts. That guide preserves a stable `lineageFamilyId` derived from the original plan target. A successor does not reset that budget; require a hash-bound `inspect-lineage` projection even when it reports zero rounds and a root-cause callsite inventory before review re-entry.

Bootstrap history indexes, cost-calibration candidates, and synthetic shadow
corpora are non-authorizing operational inputs. VDD may use their cost signal
when presenting an optional review, but it never treats a historical finding,
similar sample, or prior clean run as current plan readiness. Exact finalized-
envelope reuse belongs to the consuming acceptance workflow and requires a
fresh Bootstrap validation plus byte-identical current candidate binding; VDD
does not select or import that envelope.

## Completion

Do not claim completion until the selected profile's required artifacts exist, each active requirement has an observable acceptance path, the declared RED/negative or legacy path is recorded, targeted repairs are stable, and the current terminal full validation passed. `plan-ready`, `implementation-authorized`, `implementation-complete`, `acceptance-passed`, and `archived` remain distinct.
## Repository-Owned Package Validation

Use this repository-owned command for Skill package validation:

```text
py -3 -B scripts/sc/skill_package_replay.py validate-package --target .agents/skills/vdd-execution-plan --capability scripts/sc/config/skill-package-validator-capability.v1.json
```


For Skill maintenance also run `py -3 .agents/skills/vdd-execution-plan/scripts/validate_skill_contract.py --skill-root .agents/skills/vdd-execution-plan` and its unit tests.

An explicit `--runtime-red-intent <failure-intent-id>` on handoff repair binds
a reviewed executable assertion to an expected-red role without changing its
requirement category or existing diagnostic family. This is not automatic
Governance conversion. See the planning guide and ADR-0041; approval decisions
can never become runtime implementation authority through this option.
