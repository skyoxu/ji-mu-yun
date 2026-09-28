# Bounded external-review repair: R3, R4, R8

Base: `9319e4faab2770f3409bb0274fa37bdbe3d79864`.
Branch: `implementation/8-24-identity-isolation-recovery-v2`.
Authority: ADR-0036, ADR-0038, ADR-0061.

## Changes

- R3: validate current route content and persisted prompt binding; reuse the
  frozen-contract consumer to recompute contract and source hashes. Active
  sessions without a current goal and needs-fix sessions without diagnostics
  block continuation. No active session/repair is not applicable.
- R4: require matching workspace isolation registration; apply Administrator
  full-control / Runner modify ACLs to every restored object; reject reparse
  points and child ACL drift before directory switch and before Published.
- R8: require persisted producer binding and behavioral observations. S53
  performs a distinct Windows Runner access-denied probe with a successful
  owned write, and an actual corrupt-snapshot quarantine. The independent
  process reads restored content, quarantine disposition, and probe evidence.
  A rehashed, DB-bound nonbehavioral artifact has a negative regression.
- Existing ordinary restore fixtures now explicitly prepare isolation. New
  missing-descriptor and ACL-drift tests bypass that setup helper deliberately.

## Verification boundary

`validation.json` records executed syntax and production-SQL checks only.
This environment has no Windows runtime or installed .NET SDK. No .NET build,
Windows test pass, Q8 pass, or implementation-complete receipt is claimed.
Historical receipts and predecessor evidence were not rewritten.

## Required Windows follow-up

Use the existing elevated test environment and its provisioned `phase-r-a-p`
Runner credential (the same prerequisite as S54). Missing credentials or a
failed Runner launch must fail; do not skip or replace the probe with flags.

Run from repository root:

```powershell
dotnet test PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj --filter "FullyQualifiedName~RecoveryAuthorityRegressionTests|FullyQualifiedName~RestoreTreeSecurityRegressionTests|FullyQualifiedName~S53BoundaryTests" --logger "trx;LogFileName=repair-boundaries.trx" --results-directory logs/quick-dev/20260928-external-repair-windows
```

Then run the affected restore fixtures and S54:

```powershell
$slices = 4,6,11,13,16,17,19,24,25,27,28,31,32,40,44,46,48,51,52,54,59,62,73
$filter = ($slices | ForEach-Object { "FullyQualifiedName~S${_}BoundaryTests" }) -join '|'
dotnet test PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj --filter $filter --logger "trx;LogFileName=restore-regression.trx" --results-directory logs/quick-dev/20260928-external-repair-windows
```

Retain both failures and successes. Regenerate affected Quick Dev evidence
against the resulting code revision only after these checks pass. S53's
stronger oracle needs successor evidence; old results cannot establish it.
Q8 completion remains pending that execution and evidence review.
