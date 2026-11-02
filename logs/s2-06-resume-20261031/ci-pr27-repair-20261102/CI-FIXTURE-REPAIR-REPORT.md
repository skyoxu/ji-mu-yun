# PR27 CI fixture integration repair

Authority: Accepted ADR-0035 and ADR-0061. Base: `a58e48a11feb2c5c210cc42281e314953818d190`.

## Scope

Seventeen test-only files now explicitly supply single-node test options, initialize the matching node binding, authenticate actual disposable credentials, enter current scopes in the calling execution context, and pass node-backed queues/seeding/Runner dependencies. Negative constructors and production guards remain unchanged. Existing assertion calls are retained; the queue suite adds missing/forged/revoked-context rejection and valid/restored-authority success.

The shared authority fixture no longer calls Linux logical registration on Windows. Owned Windows workspaces use the existing Windows provisioner and explicit registration cleanup. Owned HTTP fixtures register their canonical workspace before host startup. S25 retains owned startup diagnostics, with its synthetic token redacted. These Windows paths compile, but have not run on this Linux machine.

## Original CI evidence

Both reported runs used PR27 head `a58e48a1`, merge `2242c35e8fff6aaca08fa5a7369192d5dff8417c`.

- Run 41466971164 / windows-entry: 205 failed, 81 passed; failures occurred after a successful build.
- Run 41466971115 / quality: 853 failed, 1094 passed. Its other failed job only mirrors quality. The original job log exposes a bounded list of failures. The complete artifact could not be transferred locally (HTTP 403); this repair does not claim all 853 failures have been diagnosed.

## Current Linux verification

The current test project builds successfully. The final affected-scope run executed 189 cases: **184 passed, 5 failed, 0 skipped**. Existing Windows-drive-specific cases and native Windows suites were not selected on Linux; their source assertions are unchanged. No complete VDD, Quick Dev, Acceptance, or CI rerun was performed.

Final TRX SHA-256: `66ec64365892806d16622a174feb4ab81546e6a2119589b280a006c3325e290a`.

The five failures expose production conflicts beyond this fixture/configuration-only change:

| Test / behavior | Actual cause | Production location |
| --- | --- | --- |
| Administrator deleting another account's project | Owner-only project read occurs before service administrator authorization | `ProjectCreationService.cs:259`, `PhaseAMetadataStore.cs:7556` |
| Owner repeating an already confirmed delete | Owner path enumerates administrator-only tombstones | `ProjectCreationService.cs:264` |
| Two ordinary-user queued-preview readback cases | Service requests administrator-only `includeAll: true` | `ProjectWebPreviewService.cs:4088`, `HeavyRunnerQueueService.cs:260` |
| GDD-to-package integration | Package capture passes the workspace root, while current snapshot binding accepts only the registered repository root | `ProjectPackageService.cs:216`, `WorkspaceStorageService.cs:171` |

The last failure surfaces as an empty package filename downstream. Its original run stderr independently confirms `current_workspace_binding_required`; no guard or assertion has been weakened to conceal it. Production repair requires separately agreed boundaries for administrator deletion, owner-only tombstone lookup, owner-scoped queue readback and canonical snapshot capture.

Raw requests, build/test logs, failed results, and provenance are retained in this cloud repair directory. One earlier no-build run was explicitly marked stale and is not used as current-candidate proof. Native Windows execution, the two original S25 Windows health failures, the rest of quality's failures, Q7/Q8 and formal Acceptance remain unverified. This commit is a partial fixture integration repair, not a CI-green or acceptance-passed claim.
