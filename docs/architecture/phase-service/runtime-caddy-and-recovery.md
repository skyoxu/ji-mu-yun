# Runtime, Caddy, And Recovery Architecture

## Intent

The runtime layer makes the Phase service recoverable on a Windows host without contaminating the repository source tree or hiding live-server failures.

Caddy exposes the public reverse-proxy endpoint. The ASP.NET Core app remains bound to localhost. Recovery starts with the local app because restarting Caddy cannot fix a dead platform process.

The Phase service separates canonical external URL semantics from direct proxy health probing: `PUBLIC_BASE_URL` is the HTTPS external URL required by platform configuration, while `ensure-phasea.ps1` probes the current Caddy listener directly over HTTP for `/healthz`.

In the current IP-only deployment, direct HTTP public smoke can pass while HTTPS public smoke fails because the checked-in Caddy listener is HTTP. Treat that as a TLS/public-smoke closure gap, not permission to downgrade `PUBLIC_BASE_URL` to HTTP.

Use these paired smoke commands when changing public URL behavior:

- Direct HTTP public smoke: `py -3 scripts/python/phase_a_public_smoke.py --base-url http://47.86.160.138:8080 --allow-http`.
- HTTPS public closure smoke: `py -3 scripts/python/phase_a_public_smoke.py --base-url https://47.86.160.138:8080`.

## Boundary

In scope:

- `runtime/phase-a/start-phasea.ps1` as the canonical live-server startup script.
- `runtime/phase-a/ensure-phasea.ps1` as the one-shot health check and recovery script.
- `runtime/phase-a/watch-phasea.ps1` as the watchdog loop.
- `runtime/phase-a/Caddyfile` as the canonical Caddy config.
- Build outputs outside the repository source tree.
- Runtime evidence under `logs/phase-a-innernet/runtime/`.

Out of scope:

- Running the live server with ordinary `dotnet run` against repo-local `obj/bin`.
- Placing runtime configuration under `logs/`.
- Committing live secrets or token hashes.

## Key Decisions

- Local app bind is `http://127.0.0.1:18080`.
- Canonical `PUBLIC_BASE_URL` is `https://47.86.160.138:8080` and must remain HTTPS.
- Direct public health probing currently uses `http://47.86.160.138:8080/healthz` against the Caddy listener.
- Caddy listens on `0.0.0.0:8080` and reverse proxies to the local app.
- The startup script sets both `APP_BIND_URL` and `ASPNETCORE_URLS` to the localhost bind.
- Build output is kept outside the repository source tree to avoid generated files entering compile inputs.
- `logs/**`, `obj/**`, and `bin/**` generated content must stay out of MSBuild default compile inputs.

## Recovery Order

1. Check `http://127.0.0.1:18080/healthz`.
2. If local health is failing, run `runtime/phase-a/ensure-phasea.ps1`.
3. If local health is healthy but public health is failing, inspect or restart Caddy.
4. If the app fails to start, inspect bind-port conflicts and build-path contamination before touching Caddy again.
5. Preserve recovery evidence under `logs/phase-a-innernet/runtime/`.

## Invariants

- The app must be healthy locally before public proxy recovery is considered successful.
- Live secrets must come from host secret store or service environment.
- Runtime evidence is additive; do not rewrite logs to hide failures.
- Important runtime config belongs in stable source paths, not runtime output directories.

## Change Rules

- Runtime script changes require local health validation or a documented validation gap.
- Caddy config changes require local app health and public health checks.
- Bind URL or public URL changes require `phase_a_ops_check.py`, `phase_a_public_smoke.py`, README, AGENTS, runtime doc, and ADR-0039 alignment.
- Secret source changes require security review and must not store real values in docs or scripts.

## Related Code And Scripts

- `runtime/phase-a/start-phasea.ps1`
- `runtime/phase-a/ensure-phasea.ps1`
- `runtime/phase-a/watch-phasea.ps1`
- `runtime/phase-a/Caddyfile`
- `scripts/python/phase_a_ops_check.py`
- `scripts/python/phase_a_runtime_smoke.py`
- `scripts/python/phase_a_public_smoke.py`
- `scripts/python/phase_a_restore_drill.py`
