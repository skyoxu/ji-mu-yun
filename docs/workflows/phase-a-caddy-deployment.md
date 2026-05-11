---
Title: Phase A Caddy Deployment
Status: Draft
Updated: 2026-05-11
ADRs: [ADR-0018, ADR-0019, ADR-0025, ADR-0031]
---

# Phase A Caddy Deployment

Phase A runs the ASP.NET Core platform on localhost and exposes it through Caddy HTTPS.

## Required Environment

```powershell
$env:HTTPS_TERMINATION = "caddy"
$env:APP_BIND_URL = "http://127.0.0.1:8080"
$env:PUBLIC_BASE_URL = "https://your-domain.example"
$env:HOSTED_WORKSPACE_ROOT = "C:\workspaces"
$env:PHASEA_METADATA_DB_PATH = "C:\phase-a\phase-a-platform.sqlite3"
$env:PHASEA_REPOSITORY_ROOT = "C:\jimuyun"
$env:PHASEA_ADMIN_TOKEN_HASH = "<manual-admin-token-or-host-secret-ref>"
$env:GODOT_BIN = "C:\Godot\4.5.1-mono\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64_console.exe"
```

Rules:

- `APP_BIND_URL` must stay on `127.0.0.1` or `localhost` when `HTTPS_TERMINATION=caddy`.
- Caddy is the only public listener for Phase A.
- `PUBLIC_BASE_URL` must be HTTPS.
- Do not store upstream provider API keys in Phase A platform configuration or SQLite.
- Browser/API callers must send `Authorization: Bearer <admin-token>` or the configured admin token header.

## Caddyfile

```caddyfile
your-domain.example {
    encode zstd gzip

    reverse_proxy 127.0.0.1:8080

    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        X-Content-Type-Options "nosniff"
        Referrer-Policy "no-referrer"
    }
}
```

## Admin Token

Generate a strong token before first deployment:

```powershell
py -3 scripts/python/dev_cli.py phase-a-generate-admin-token
```

Set the generated value as `PHASEA_ADMIN_TOKEN_HASH` in the host service environment. Phase A currently treats this configured value as the bearer-token verifier, so rotate it by changing the service environment and restarting the process. Do not commit the generated token, and do not put it in Caddyfile or git-tracked docs.

## Operations Preflight

Before publishing or restarting the service, run:

```powershell
py -3 scripts/python/dev_cli.py phase-a-ops-check `
  --repository-root "C:\jimuyun" `
  --workspace-root "C:\workspaces" `
  --metadata-db "C:\phase-a\phase-a-platform.sqlite3" `
  --app-bind-url "http://127.0.0.1:8080" `
  --public-base-url "https://your-domain.example"
```

This validates absolute paths, creates missing deployment directories where safe, checks `py` and `dotnet` on `PATH`, verifies localhost binding behind Caddy, and records evidence under `logs/ci/<date>/phase-a-ops-check/summary.json`. A missing `GODOT_BIN` is a warning until Day 5/GdUnit checks are enabled.

## Windows Service Shape

Publish:

```powershell
dotnet publish PhaseA.Platform\PhaseA.Platform.csproj -c Release -o C:\phase-a\app
```

Service command:

```powershell
C:\phase-a\app\PhaseA.Platform.exe
```

Use Windows Service, NSSM, or the host process supervisor. The process must inherit the required environment variables above. The service account must have read/write access to `PHASEA_METADATA_DB_PATH`, `HOSTED_WORKSPACE_ROOT`, `PHASEA_REPOSITORY_ROOT`, and `logs/`.

## Backup And Restore

Create a backup while the service is stopped or during a quiet maintenance window:

```powershell
py -3 scripts/python/dev_cli.py phase-a-backup `
  --metadata-db "C:\phase-a\phase-a-platform.sqlite3" `
  --workspace-root "C:\workspaces" `
  --out-dir "C:\phase-a\backups"
```

The backup command uses SQLite's backup API for the metadata database and zips the workspace root. Add `--include-logs --logs-root logs` when logs must be retained for incident investigation.

Restore shape:

1. Stop the Phase A service.
2. Copy the backed-up SQLite file to `PHASEA_METADATA_DB_PATH`.
3. Extract the workspace zip back to `HOSTED_WORKSPACE_ROOT`.
4. Confirm permissions for the service account.
5. Start the service and run `phase-a-runtime-smoke`.

Keep at least one off-host copy of the latest SQLite and workspace backup before public launch.

## Deployment Checks

Run before public exposure:

```powershell
& "C:\Program Files\dotnet\dotnet.exe" test Game.sln
py -3 scripts/python/dev_cli.py run-local-hard-checks-preflight --delivery-profile fast-ship
py -3 scripts/python/dev_cli.py phase-a-runtime-smoke --dotnet "C:\Program Files\dotnet\dotnet.exe"
py -3 scripts/python/dev_cli.py phase-a-prototype-e2e --dotnet "C:\Program Files\dotnet\dotnet.exe" --stop-after-day 5
py -3 scripts/python/dev_cli.py phase-a-restore-drill --dotnet "C:\Program Files\dotnet\dotnet.exe"
py -3 scripts/python/dev_cli.py phase-a-token-rotation-drill --dotnet "C:\Program Files\dotnet\dotnet.exe"
py -3 scripts/python/dev_cli.py phase-a-public-smoke --base-url "https://your-domain.example" --admin-token "<admin-token>"
```

`phase-a-runtime-smoke` starts `PhaseA.Platform` with a temporary SQLite database and workspace under `logs/ci/<date>/phase-a-runtime-smoke/<run_id>/`. It verifies `/healthz`, auth rejection, authenticated project creation, browser Git URL rejection, and the default two-project quota.

`phase-a-prototype-e2e` starts `PhaseA.Platform` against a temporary repository copy by default. It creates a project, runs Chapter 2 bootstrap, runs the hosted prototype route through Day 4, creates a prototype scene, runs hosted prototype TDD refactor, and verifies run/artifact readback. With `GODOT_BIN` configured, the same command can run through Day 5 and verify the GdUnit-backed Godot path.

`phase-a-restore-drill` creates a fixture SQLite/workspace pair, backs it up, restores it to a new location, starts `PhaseA.Platform` against the restored files, and verifies project readback through the API.

`phase-a-token-rotation-drill` starts the service with an old token, restarts with a new token, then verifies old-token rejection and new-token acceptance.

Run service-starting drills serially. Parallel `dotnet run` invocations can lock `PhaseA.Platform` build outputs.

`phase-a-public-smoke` verifies the deployed public endpoint through Caddy: `/healthz`, unauthenticated `401`, and authenticated project-list access. Add `--create-project` only when you intentionally want the smoke to consume one project slot on the deployed account. Non-local public endpoints must use HTTPS unless `--allow-http` is passed for a local-only check.

Runtime PATH requirements:

- The service process must be able to launch `py`.
- The service process must be able to launch `dotnet` because prototype TDD invokes `dotnet test`.
- Set `GODOT_BIN` before enabling Day 5 or any GdUnit-backed prototype checks. The expected Phase A value is `C:\Godot\4.5.1-mono\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64_console.exe`.

Manual checks:

- `curl http://127.0.0.1:8080/healthz` returns `ok`.
- Public `https://your-domain.example/healthz` returns `ok`.
- Public project, run, artifact, and LLM endpoints return `401` without auth.
- Authenticated artifact reads do not expose raw filesystem paths.
- Caddy owns certificate issuance and renewal.
