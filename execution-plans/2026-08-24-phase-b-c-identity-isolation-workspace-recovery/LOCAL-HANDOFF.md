# Local Handoff: Repair VDD Before Quick Dev

The online delivery is [implementation-repair-input.md](implementation-repair-input.md).
It restores the implementation input, not canonical plan readiness. Read it before any historical next-action pointer. The old plan-state/resume-state, Round-3 mapping, implementation contract and terminal handoff are historical context for this repair, not permission to skip current compilation/probing.

## Local sequence

1. Fetch and check out the repair branch from a clean working tree. Preserve local changes; do not reset them.
2. Read the current VDD Skill repair guidance. Use the original 8-24 target directory and resumable profile, with development governance disabled. No Bootstrap is requested.
3. Compile the repaired input with the canonical process entry below. This can invoke model workers; it was not run online.
4. Inspect compiler exit/result and generated behavior/Acceptance coverage. A nonzero exit or any result other than plan-ready stays VDD repair; stop before Quick Dev.
5. Verify all 53 input cases, 40 PIWR IDs, 18 acceptance IDs, 7 NFRs and 13 Architecture rules remain covered. Every exclusion must cite an actual source non-goal. Do not accept a new blanket not_applicable disposition.
6. Start the locally installed current Quick Dev TDD Skill with the newly compiled 8-24 directory. It must derive current behavior via controlled probes, retaining present behavior as regression and resolving mixed rows into finer obligations.
7. Resolve production protected-path authorization in the local implementation session. This online task explicitly did not authorize or perform those writes.
8. After implementation and current terminal validation, obtain external code/semantic review and run Acceptance. Preserve failed evidence. Do not equate a compiler pass or a test count with product completion.

## Canonical compile command

Run from the repository root in PowerShell. The CLI at the reviewed baseline supports --requirements, repeated --companion, --out-dir, --profile and --result-json; it does not expose a --governance-mode argument. Select governance through the documented environment variable.

```powershell
$planPath = "execution-plans/2026-08-24-phase-b-c-identity-isolation-workspace-recovery"
$specPath = "_bmad-output/specs/spec-phase-b-c-identity-isolation-workspace-recovery"
$architecturePath = "_bmad-output/planning-artifacts/architecture/architecture-phase-b-c-identity-isolation-workspace-recovery-2026-08-23/ARCHITECTURE-SPINE.md"
$evidencePath = "logs/phase-b-c-input-repair/local-" + (Get-Date -Format "yyyyMMddTHHmmss")
$previousGovernance = $env:JIMUYUN_GOVERNANCE_MODE
try {
    $env:JIMUYUN_GOVERNANCE_MODE = "off"
    py -3 scripts/vdd/compile_plan.py `
        --requirements "$planPath/implementation-repair-input.md" `
        --companion "$specPath/SPEC.md" `
        --companion "$architecturePath" `
        --companion "$specPath/identity-and-ownership.md" `
        --companion "$specPath/runner-isolation.md" `
        --companion "$specPath/workspace-recovery-contract.md" `
        --companion "$specPath/api-evolution-and-operations.md" `
        --companion "$specPath/requirements-and-acceptance.md" `
        --out-dir "$planPath" `
        --profile resumable `
        --result-json "$evidencePath/compiler-result.json"
    if ($LASTEXITCODE -ne 0) { throw "VDD repair failed; do not start Quick Dev." }
    $compileResult = Get-Content "$evidencePath/compiler-result.json" -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($compileResult.status -ne "plan-ready") { throw "VDD did not publish plan-ready." }
} finally {
    $env:JIMUYUN_GOVERNANCE_MODE = $previousGovernance
}
```

Do not supply an old worker cache. On the first compile of these changed inputs, do not add --resume-from simply because historical plan-state exists. If this compile actually fails and the current compiler records a resumable failed stage, use its documented --resume-from first-failed-stage with the same current inputs. Do not manufacture completed stages or reuse old RED/terminal receipts.

The full source package is passed explicitly. If the local compiler cannot preserve companion authority or cannot handle this legacy target without rewriting historical evidence, stop as VDD repair with the exact error; do not manually patch the semantic output to green.

## Expected implementation routing

| Observed result | Next action |
| --- | --- |
| Present through the real production entry | Current regression and terminal; no artificial RED |
| Missing behavior with valid executable oracle | Quick Dev owns actual RED, then GREEN and REFACTOR on the same selector |
| Mixed coverage in one case | Split into finer obligations before execution |
| Missing test/host/OS privilege or other unverifiable input | Repair the harness/environment and re-probe; no success or causal RED |
| Targeted checks pass, required terminal category absent | Incomplete; produce the missing actual check |
| Current compiler and implementation evidence complete | External review, then Acceptance on the same current implementation |

The test class/method names in the input are intent, not existing test evidence. The local implementation must materialize them, verify discovery and connect them to production. Existing marker/helper tests remain regressions but cannot substitute the new boundary tests.

## Online validation scope

Online checks cover complete ID mapping, Architecture rule mapping, source/relative-link existence, command argument compatibility and the change boundary. No compiler/model worker, .NET test, Windows permission fixture, production backend, Quick Dev or Acceptance run occurred online. No new lifecycle state or historical evidence was manufactured.
