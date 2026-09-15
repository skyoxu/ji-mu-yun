# 8-24 direct Quick Dev handoff

The maintainer requested direct repair and no further VDD run. Target branch:
`implementation/8-24-identity-isolation-recovery-v2`.

## Restore the verified prepared input

The complete verified plan is now preserved in
`rebuild-inputs/prepared-inputs.tar.xz`, including its file hashes and retired
projection list. The existing preparation command restores those exact bytes
and reruns the native checks; it does not regenerate them through VDD.
Until restoration passes, root-level machine JSON remains the historical
baseline and must not be used to start implementation.

From a clean synchronized repository worktree, run in PowerShell:

```powershell
py -3 execution-plans/2026-08-24-phase-b-c-identity-isolation-workspace-recovery/tools/rebuild_current_input.py
if ($LASTEXITCODE -ne 0) { throw "Input repair validation failed; stop here." }
```

This is not VDD: no compiler, model, Bootstrap, live backend or Phase test is
invoked. It first runs the tool guard regressions, preserves original product
IDs, assembles 73 slices / 351 obligations, checks native semantic/routing and
CER descriptor contracts, and runs public Q1 for every slice. It creates no
Phase production code or target tests. It stops on failure. Evidence is appended
under `logs/phase-b-c-input-repair/local-rebuild/`.

The prepared-archive route does not require the old Git baseline object.
The reconstruction fallback remains available only when the archive is absent.
Existing local plan changes are preserved by refusing to overwrite them.
A materialization marker allows identical prepared inputs to be reverified;
changed prepared inputs are never silently overwritten.

The assembly generates normal tracked plan changes. Commit them after the
checks pass and before starting implementation, so the candidate identity is
stable. Do not rerun this preparation after Phase implementation starts.
The complete archive restoration path has been exercised online with 29 guard
tests and all 73 public Q1 preflights. The local command rechecks these against
your checkout and environment; it does not reuse historical runtime proof.

## Current input and order

The 73 product slices retain 347 original product obligations and their assertion
identities, plus four source-grounded cases. Fourteen instruction/non-goal rows
move to explicit dispositions; S70 setup is retained inside S69.
Use `implementation-order.v1.json` and `implementation-case-map.v1.json`
after assembly. First slice: **S12**. Preserve IDs rather than renumbering.

Historical compiler, alignment, feasibility, source-freeze and lifecycle files
remain historical. They do not prove this maintainer-authored revision.
Assembly does not manufacture plan-ready, implementation-complete or
acceptance-passed.

## Q2 authoring and execution

Read the current Quick Dev Skill execution guide and selected agent-context.
Use `standard`, governance off. In a fresh explicitly named run under
`logs/phase-b-c-implementation/`, author the declared Python wrapper, C# boundary
test and helper. Follow current author-red / run-probe routing.

Each obligation maps to a distinct pytest node and .NET FullyQualifiedName.
Mark every bound assertion with `pytest.mark.cer_assertion`. Invoke the real
.NET test using literal `subprocess.run` argv with explicit `shell=False`,
`dotnet test PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj`, exact
`--filter FullyQualifiedName=<mapped case>`, and `--logger trx`.
The frozen Fact/Theory source calls a declared production owner or a real
`WebApplicationFactory<Program>` host plus client. The test project references
the production project. Static admission is not execution or semantic proof.

Parse fresh invocation-specific TRX, verify exact method and all parameter cases,
and assert the real product observation. Build/discovery/setup/timeout/privilege
failures are harness errors, never product AssertionError/RED. Reject missing,
stale, skipped and inconclusive results. A nonzero exit alone is not causal RED.
Emit the planned FAILURE ID only from its actual bound product assertion.

Freeze wrappers, C# cases, helpers, fixtures and selectors before formal RED.
Declare every execution dependency before freezing; GREEN/REFACTOR cannot change
the plan or tests. Preserve correct production when repairing test inputs.

| Actual observation | Required path |
| --- | --- |
| Present | Regression and terminal; no artificial RED |
| Missing | Causal RED, bounded GREEN, same-selector REFACTOR and terminal |
| Mixed | Preserve present regression and implement the missing subset |
| Unverifiable | Repair the harness/environment; no pass or production authorization |
| Dependency changed | Re-probe affected slices and downstream consumers |

Use real restricted Windows identities, ACL denial, Job Object lifetime,
SQLite restart, authenticated operations and retained Snapshot content.
Use disposable roots and harmless workloads to isolate unrelated model behavior.

## Terminal boundary

A18 uses an independent-process reader authored in the test helper; it reads
explicit current isolation, permissions, round-trip, fault, migration and
redaction artifacts. It is not a generic evaluation system.

After targeted stabilization, execute the full PhaseA.Platform.Tests project.
Required terminal evidence also covers real Windows OS boundaries, restart/fault
recovery, authenticated Snapshot/Restore/readback/controlled Run, legacy-data
upgrade/reuse and independent A18 verification. Bind current predecessors to
Q7/Q8. Counts alone cannot close the plan; Acceptance remains the separate final
consumer. No live workspace, runtime/Caddy, shared Skill or historical evidence
changes are authorized for the subsequent Phase implementation.
