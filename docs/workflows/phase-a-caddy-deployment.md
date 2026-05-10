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

## Windows Service Shape

Publish:

```powershell
dotnet publish PhaseA.Platform\PhaseA.Platform.csproj -c Release -o C:\phase-a\app
```

Service command:

```powershell
C:\phase-a\app\PhaseA.Platform.exe
```

Use Windows Service, NSSM, or the host process supervisor. The process must inherit the required environment variables above.

## Deployment Checks

Run before public exposure:

```powershell
& "C:\Program Files\dotnet\dotnet.exe" test Game.sln
py -3 scripts/python/dev_cli.py run-local-hard-checks-preflight --delivery-profile fast-ship
py -3 scripts/python/dev_cli.py phase-a-runtime-smoke --dotnet "C:\Program Files\dotnet\dotnet.exe"
```

`phase-a-runtime-smoke` starts `PhaseA.Platform` with a temporary SQLite database and workspace under `logs/ci/<date>/phase-a-runtime-smoke/<run_id>/`. It verifies `/healthz`, auth rejection, authenticated project creation, browser Git URL rejection, and the default two-project quota.

Manual checks:

- `curl http://127.0.0.1:8080/healthz` returns `ok`.
- Public `https://your-domain.example/healthz` returns `ok`.
- Public project, run, artifact, and LLM endpoints return `401` without auth.
- Authenticated artifact reads do not expose raw filesystem paths.
- Caddy owns certificate issuance and renewal.
