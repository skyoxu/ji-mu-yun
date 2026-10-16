# Local Handoff: Enter Quick Dev Directly

The maintainer explicitly authorized direct online repair of this input and
requested **no further VDD Skill run**. This instruction supersedes the earlier
compiler-first handoff. Source baseline: `9cd87d3ab780f7087b9fd470dc2843968b208eca`.

## Current input and scope

| Item | Current contract |
| --- | --- |
| Consumer | `.agents/skills/quick-dev-tdd-adapter/SKILL.md`, current execution guide |
| Entry | `scripts/quick_dev/run.py`; current semantic bundle, not historical v1 |
| First slice | `S12` (real schema/startup foundation) |
| Remaining order | `implementation-order.v1.json` |
| Product coverage | 351 atomic obligations / Acceptances, 73 stable-ID slices |
| Runtime routing | Real probe decides present, missing or unverifiable |
| Profile | `standard`, development governance off |
| Compiler/model run online | None; input repair and deterministic validation only |
| Target production/tests online | Unchanged; declared new test files are Q2 work |
| Completion | Quick Dev Q7/Q8, then external review and Acceptance |

The semantic bundle plus its synchronized projections are the current input.
Read `input-repair-dispositions.v1.json` for the exact relocation of workflow
instructions and explicit non-goals. No product obligation was dropped.
S70 test preparation is retained in S69. The original IDs of the other product
obligations and assertions are retained; four source-grounded cases are added.

Historical `compiler-state.v1.json`, `plan-state.v1.json`, `resume-state.v1.json`,
`implementation-contract.v1.json`, `command-registry.v1.json`, source freeze,
compiler source index/alignment/feasibility and old terminal/repair directories
remain records of their original run. Do not use their S0 pointer, compiler
hash or completion wording as current authority. The current source manifest
is `input-repair-source-index.v1.json`. No old runtime proof is reusable for
this changed semantic bundle. Do not rewrite the historical records.

## Local start

Synchronize the pushed branch in a clean worktree, preserving any local changes.
Use the current Quick Dev Skill and its execution/recovery guides. From the
repository root, PowerShell:

```powershell
$planPath = "execution-plans/2026-08-24-phase-b-c-identity-isolation-workspace-recovery"
py -3 scripts/quick_dev/run.py --plan $planPath --slice S12 --profile standard
```

Inspect the returned JSON **status**, not only the process exit code:
`preflight-passed` admits test authoring; `environment-blocked` requires fixing
the named environment prerequisite. A preflight pass is not product proof.
The agent then creates a fresh explicitly named run under
`logs/phase-b-c-implementation/` and follows the current Skill's `author-red`
(CER probe authoring), `run-probe`, and observed routing. Do not invoke VDD,
Bootstrap, legacy combined writers or an old plan-local terminal shortcut.

The online checks exercise the native planned preflight for all slices. Local
Windows/.NET, actual permissions, host fixtures and product outcomes still
belong to implementation; no successful runtime disposition is preassigned.

## Q2 test authoring contract

1. Read the selected agent-context and its rows in
   `implementation-case-map.v1.json`. Respect the declared predecessor order.
2. Materialize only that slice's declared pytest file, C# boundary class and
   fixture helper. These paths are deliberately planned, not missing evidence
   to paper over. Do not change production to make test discovery/build pass.
3. The current CER adapter accepts `python -m pytest`. The pytest case must
   call the real .NET boundary test in
   `PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj` and read a fresh TRX
   bound to that invocation. Use a literal `subprocess.run` argv list with
   explicit `shell=False`, `dotnet test` plus the project path, exact
   `--filter FullyQualifiedName=<mapped case>` and `--logger trx`. The frozen
   C# Fact/Theory source must call a real declared production owner, or use
   `WebApplicationFactory<Program>` plus `CreateClient` for the real host.
   The test project must reference the production project. These static
   bindings admit execution; they do not prove the .NET result. Test code
   and helpers use disposable roots/DBs.
4. Discover the exact method and parameter cases. Verify every required case
   executes; reject missing, stale, malformed, skipped, inconclusive or extra
   ambiguous TRX results. Build failure, missing host/privilege, timeout or
   undiscovered cases are harness errors, never product AssertionError/RED.
5. Preserve the original typed SUT failure and expected failure family. Emit
   the mapped `FAILURE-...` only when a real bound product assertion fails.
   `expected-red` in the plan is a conditional intent, not a forced outcome.
6. Mark each pytest case with its exact `cer_assertion` IDs. Shared markers
   cannot cover unexecuted parameter cases. Keep the real production call
   attributable; source-string checks or unconditional markers cannot prove
   runtime behavior. Direction-only duties use meaningful contract/composition
   checks and do not require deployment of an external OIDC provider.
7. Freeze pytest, C# cases, helpers and fixtures before formal RED. Do not
   change them, their selectors or the plan during GREEN/REFACTOR. Any additional
   execution dependency must be declared before that freeze; retain correct
   production when repairing test inputs.

A18 uses a test-owned independent-process reader authored in the slice fixture
helper. It checks the real current isolation, permission, round-trip, fault,
migration and redaction artifacts; it does not read Taskmaster or call a help
command as evidence. Fix missing/broken product evidence at its real producer.
This does not introduce a general evaluation or scoring system.

## Implementation and terminal

| Observed condition | Action |
| --- | --- |
| Present | Regression and terminal; no artificial RED or production change |
| Missing, valid oracle | Formal causal RED, bounded GREEN, same-selector REFACTOR |
| Mixed | Retain present regression and implement only the observed missing subset |
| Harness/environment gap | Repair the identified prerequisite and re-probe; no pass/RED |
| Changed dependency | Revalidate the affected slice and downstream proof |
| Required terminal category absent | Incomplete, even if another suite is green |

Retain narrow production write boundaries and existing protected-path rules.
No live metadata, Hosted workspace, runtime/Caddy, shared Skill, upstream scope
or historical evidence edits are authorized for the subsequent Phase implementation. Do not start
an unrelated governance/reviewer workflow or reopen VDD automatically.

After targeted stabilization, execute the real full project suite and retain
its fresh structured results:

```powershell
dotnet test PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj --logger trx
```

The terminal evidence must also prove non-skipped real Windows OS identity,
ACL and Job Object boundaries; durable restart/fault behavior; authenticated
Snapshot-to-Restore-to-route/readback-to-controlled-Run; old-data upgrade/reuse;
and independent A18 validation. Tie explicit current predecessors to Q7/Q8.
Neither this handoff, the input validator nor a full-suite count can publish
implementation-complete or acceptance-passed. External review follows actual
implementation; Acceptance remains its separate final consumer.
