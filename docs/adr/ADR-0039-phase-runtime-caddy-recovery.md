# ADR-0039: Phase Runtime, Caddy, And Recovery Order

- Status: Accepted
- Date: 2026-06-28

## Context

The live Phase service runs on a Windows host with ASP.NET Core bound locally and Caddy exposing the public reverse proxy. Failed public health can come from the app, Caddy, bind conflicts, build-path contamination, or missing runtime secrets.

Restarting Caddy first can hide the real failure when the app is down.

## Decision

Use explicit runtime scripts and a local-first recovery order.

- `runtime/phase-a/start-phasea.ps1` is the canonical live-server startup script.
- `runtime/phase-a/ensure-phasea.ps1` is the one-shot health check and recovery script.
- `runtime/phase-a/watch-phasea.ps1` is the watchdog loop.
- `runtime/phase-a/Caddyfile` is the canonical Caddy config.
- The app binds to `http://127.0.0.1:18080`.
- `PUBLIC_BASE_URL` is the canonical external HTTPS URL and must stay absolute HTTPS.
- The current direct Caddy health probe uses `http://47.86.160.138:8080/healthz`; do not confuse this probe URL with `PUBLIC_BASE_URL`.
- Public HTTPS reachability is not proven by direct HTTP health. HTTPS public smoke must pass before documentation or release notes claim the public HTTPS endpoint is operational.
- Caddy listens publicly on `0.0.0.0:8080` and proxies to the local app.
- Recovery checks local `/healthz` before public `/healthz`.
- The live server must not use ordinary `dotnet run` against repo-local `obj/bin`.

## Consequences

- Public proxy recovery becomes diagnosable.
- Build output stays outside the repository source tree.
- Runtime evidence is written under `logs/phase-a-innernet/runtime/`.
- Runtime variables documented in AGENTS must stay aligned with `start-phasea.ps1`, which is the operational source of truth.
- Public URL changes must keep `PhaseAPlatformOptionsLoader`, `phase_a_ops_check.py`, `phase_a_public_smoke.py`, AGENTS, runtime docs, and recovery probes semantically aligned.

## References

- `docs/architecture/phase-service/runtime-caddy-and-recovery.md`
- `runtime/phase-a/start-phasea.ps1`
- `runtime/phase-a/ensure-phasea.ps1`
- `runtime/phase-a/watch-phasea.ps1`
- `runtime/phase-a/Caddyfile`
- `scripts/python/phase_a_ops_check.py`
- `scripts/python/phase_a_public_smoke.py`
