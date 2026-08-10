# Phase A Host Runtime Guide

This file scopes work inside `runtime/phase-a/**`. It owns host-process startup,
health recovery, watchdog behavior, and Caddy configuration. Application code
belongs to `../../PhaseA.Platform/AGENTS.md`; Hosted game-project execution
context belongs to project workspaces and route contracts.

## Files

- `start-phasea.ps1`: canonical configuration resolution, external build, and
  application-process startup.
- `ensure-phasea.ps1`: one-shot local-first recovery and health evidence.
- `watch-phasea.ps1`: periodic recovery supervisor.
- `Caddyfile`: public listener and reverse proxy to the local application.

## Protected Boundary

Ask before changing any file in this directory. Changes can affect the live
service, public reachability, secret propagation, or recovery behavior.

Never:

- start the live service with ordinary `dotnet run`;
- write real token or signing material into repository files or logs;
- edit the live SQLite database;
- use a public-proxy symptom to skip the local application health check;
- rewrite historical runtime evidence.

## Recovery Order

1. Check `http://127.0.0.1:18080/healthz`.
2. If unhealthy, run `ensure-phasea.ps1`.
3. Recheck local health and inspect additive evidence under
   `../../logs/phase-a-innernet/runtime/`.
4. Only after local health passes, inspect Caddy and public `:8080` health.
5. Do not claim public HTTPS closure until the HTTPS smoke passes without the
   HTTP allowance.

## Configuration Rules

- `start-phasea.ps1` is the canonical live runtime configuration source.
- Stable non-secret defaults may be documented in `README.md` here.
- Secrets and dynamic command paths come from the host environment or secret
  store and are passed to the child without being logged.
- The Hosted Context signing key ring is distinct from ticket and web-preview
  signing secrets. Partial or malformed key-ring configuration fails closed.
- Build outputs stay outside the repository source tree.
- Caddy listens on `0.0.0.0:8080` and proxies to `127.0.0.1:18080` unless an
  approved deployment decision changes the contract.

## Validation

After an authorized change, validate in this order:

Run these commands from the repository root.

```powershell
powershell -ExecutionPolicy Bypass -File runtime/phase-a/ensure-phasea.ps1
py -3 scripts/python/phase_a_ops_check.py
py -3 scripts/python/phase_b_account_smoke.py --base-url http://127.0.0.1:18080
py -3 scripts/python/phase_a_public_smoke.py --base-url http://47.86.160.138:8080 --allow-http
```

Run the HTTPS smoke separately when claiming HTTPS reachability. Record all
runtime and recovery evidence under `logs/` without replacing older failures.

## Documentation Boundary

- This directory explains the host runtime, not Phase API implementation.
- Root `AGENTS.md` retains cross-tree protection, compatibility, and shared
  LLM/Codex rules.
- `../../PhaseA.Platform/README.md` explains the application process.
- Hosted project `AGENTS.md` and `README.md` are generated from the dedicated
  workspace templates and must not expose host configuration or secrets.
