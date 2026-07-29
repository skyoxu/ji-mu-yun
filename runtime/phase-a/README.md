# Phase A Host Runtime

`runtime/phase-a` is the stable host-operations entry for the Phase A service.
It starts the ASP.NET application from an external build root, keeps it healthy,
and exposes it through Caddy. It does not define Hosted game-project workflow
context.

## Stable Endpoints

- Local application: `http://127.0.0.1:18080`
- Canonical configured public base: `https://47.86.160.138:8080`
- Current direct public health probe: `http://47.86.160.138:8080/healthz`

The configured HTTPS base and current direct HTTP listener are distinct facts.
Do not claim HTTPS reachability until the HTTPS smoke passes without
`--allow-http`.

## Start And Recover

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File runtime/phase-a/ensure-phasea.ps1
```

Long-running supervision:

```powershell
powershell -ExecutionPolicy Bypass -File runtime/phase-a/watch-phasea.ps1
```

Run Caddy with the canonical configuration when it is not host-managed:

```powershell
caddy run --config runtime/phase-a/Caddyfile
```

Recovery always checks local application health before Caddy or public health.
The live process must be started through `start-phasea.ps1`, not ordinary
`dotnet run`.

## Files

| File | Responsibility |
| --- | --- |
| `start-phasea.ps1` | Resolve config/secrets, build outside the repo, and start the app |
| `ensure-phasea.ps1` | Check local/public health and perform one-shot recovery |
| `watch-phasea.ps1` | Invoke recovery periodically and maintain watchdog evidence |
| `Caddyfile` | Listen on `:8080` and proxy to the local app |

## Stable Non-Secret Defaults

`start-phasea.ps1` remains the complete source of truth. Recovery-grade values
currently include:

```text
APP_BIND_URL=http://127.0.0.1:18080
ASPNETCORE_URLS=http://127.0.0.1:18080
HTTPS_TERMINATION=caddy
PUBLIC_BASE_URL=https://47.86.160.138:8080
HOSTED_WORKSPACE_ROOT=C:\jimuyun\logs\phase-a-innernet\workspaces
HOSTED_PROJECT_LIMIT=2
PHASEA_MAX_CONCURRENT_CHATS=8
PHASEA_MAX_CONCURRENT_CHATS_PER_ACCOUNT=1
PHASEA_MAX_CONCURRENT_GDD_QUESTION_FORMS=4
PHASEA_MAX_CONCURRENT_GDD_QUESTION_FORMS_PER_ACCOUNT=1
PHASEA_MAX_CONCURRENT_PROJECT_CREATIONS=3
PHASEA_MAX_CONCURRENT_PROJECT_CREATIONS_PER_ACCOUNT=1
PHASEA_MAX_CONCURRENT_OTHER_RUNS=3
PHASEA_MAX_CONCURRENT_PROTOTYPE_CREATIONS=2
PHASEA_MAX_CONCURRENT_WEB_PREVIEWS=3
PHASEA_MAX_CONCURRENT_WEB_PREVIEWS_PER_ACCOUNT=1
PHASEA_GODOT3_WEB_PREVIEW_EXPORT_TIMEOUT_SECONDS=180
PHASEA_GODOT3_WEB_PREVIEW_EXPORT_INACTIVITY_TIMEOUT_SECONDS=45
PHASEA_MAX_CONCURRENT_ASSET_GENERATIONS_PER_ACCOUNT=1
PHASEA_METADATA_DB_PATH=C:\jimuyun\logs\phase-a-innernet\data\phase-a-platform.sqlite3
PHASEA_REPOSITORY_ROOT=C:\jimuyun
GODOT_BIN=C:\Godot\4.5.1-mono\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64_console.exe
PHASEA_GODOT3_BIN=C:\Godot\3.6.2\Godot_v3.6.2-stable_win64.exe
DOTNET_ROOT=C:\jimuyun\.dotnet
```

The script also resolves dynamic or secret-backed values including the Codex
command, ripgrep directory, admin token hash, ticket/web-preview signing
secrets, Hosted Context signing key ring, and optional provider integration.
Document names and sources only; never persist real values.

## Build And Evidence

- Stable external build root:
  `C:\Users\Administrator\.codex\memories\phasea-runtime-build`
- Runtime recovery/watchdog evidence:
  `logs/phase-a-innernet/runtime/`
- Watchdog PID: `logs/phase-a-innernet/phasea-watchdog.pid`
- Watchdog log: `logs/phase-a-innernet/runtime/phasea-watchdog.log`

Live metadata and workspaces are protected state. Do not edit them manually.

## Checks

```powershell
py -3 scripts/python/phase_a_ops_check.py
py -3 scripts/python/phase_b_account_smoke.py --base-url http://127.0.0.1:18080
py -3 scripts/python/phase_a_public_smoke.py --base-url http://47.86.160.138:8080 --allow-http
py -3 scripts/python/phase_a_public_smoke.py --base-url https://47.86.160.138:8080
```

See `AGENTS.md` here for change protection and recovery order, and
`../../PhaseA.Platform/README.md` for the application runtime model.
