# K13 Protected Runtime Write-Set Preflight

Status: prepared, not authorized.

Authority: ADR-0044 and ADR-0046. This write set is intentionally separate
from K12 because it changes runtime secret provisioning and dependency
registration. It grants no E2 release or bulk route migration.

## Requested Production Paths

- `PhaseA.Platform/Configuration/PhaseAPlatformOptions.cs`
- `PhaseA.Platform/Configuration/PhaseAPlatformOptionsLoader.cs`
- `PhaseA.Platform/Program.cs`
- `runtime/phase-a/start-phasea.ps1`
- `PhaseA.Platform/Data/HostedContextManifestIssuer.cs`
- `PhaseA.Platform/Data/HostedContextManifestSignatureService.cs`
- `PhaseA.Platform/Data/HostedContextManifestValidator.cs`

## Secret And Registration Contract

- The only accepted source is a dedicated Hosted Context key ring supplied by
  the host environment. The key ring has an active key id and retained
  verification keys for rotation.
- Ticket signing and web-preview signing secrets are prohibited as inputs or
  fallbacks. A missing, malformed, duplicate, or empty key ring fails closed.
- `Program.cs` may register only the server-owned issuer and validator. It may
  not expose a Browser/API endpoint that lets a child select the key, nonce,
  signature, account, project, operation, or gate mode.
- `start-phasea.ps1` may resolve and pass the dedicated environment values but
  may not write key material to the repository, logs, metadata DB, or Hosted
  workspace. It must not generate an implicit replacement key.

## Explicit Exclusions

- No live metadata DB or Hosted workspace mutation.
- No `PhaseA.Platform/Browser/**`, `/ui-v2`, Caddy, public listener, or
  deployment URL change.
- No migration of the 26 current reachable Hosted callsites in this change.
- No `e2-release-evidence.v1.json` creation and no E2 declaration.

## Required Validation

- Configuration parser unit tests cover missing, malformed, duplicate, active,
  and retained key cases without persisting key material.
- Startup-script source tests prove host resolution and child-process
  propagation, and prove there is no fallback to ticket or web-preview keys.
- Issuer/validator round-trip, tampered signature, key rotation, expiry, and
  concurrent nonce-consumption tests pass.
- Rebuild inventories and ledger, run `tools/check_e2_readiness.py`, targeted
  shared-entrypoint tests, whole-directory validation, and `git diff --check`.

## Follow-On Gate

After this write set validates, a separately frozen per-caller write set is
required for each `legacy -> observe -> enforce` transition. A first enforce
candidate must be read-only and prove browser-safe errors and rollback before
any mutation-capable route is considered.
