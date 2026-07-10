# Phase A GDD-To-Module Hardening Smoke

Status: Active deterministic smoke
Language: English
Scope: Phase A browser-consumed GDD -> requirement map -> prototype contract -> iteration-plan route hardening.

## Purpose

`scripts/python/phase_a_gdd_to_module_hardening_smoke.py` verifies that the GDD-to-module hardening contracts are present before any expensive project creation or LLM route execution is attempted.

The smoke is intentionally deterministic by default. It checks repository-owned Phase 0 guard artifacts, optional project route-state sidecars, and optional API workflow readback. It does not manually mutate the live metadata DB and it does not rewrite generated failure history.

## Command

```powershell
py -3 scripts/python/phase_a_gdd_to_module_hardening_smoke.py --repository-root C:\jimuyun
```

Optional project readback mode:

```powershell
py -3 scripts/python/phase_a_gdd_to_module_hardening_smoke.py --repository-root C:\jimuyun --project-root <hosted-project-root>
```

Optional API readback mode:

```powershell
py -3 scripts/python/phase_a_gdd_to_module_hardening_smoke.py --repository-root C:\jimuyun --base-url http://127.0.0.1:18080 --project-id <project-id> --admin-token <token>
```

## Evidence

Every run writes `summary.json` under `logs/phase-a-gdd-to-module-hardening/<run-id>/` unless `--out` is supplied. The summary records:

- script name and run ID
- base URL and project ID when API readback is used
- identity class, without token material
- route-state hash checks and source-boundary checks
- failures as stable machine-readable strings

## Phase 0 Baseline Gate

The smoke fails before project/API execution when any required Phase 0 baseline is absent:

- route action descriptor registry and fixture parity baseline
- status vocabulary fixture baseline
- evidence ref kind fixture baseline
- source-boundary contract support
- path/readback and `Cache-Control: no-store` standards
- action exposure classes
- duplicate-run convention
- preflight checklist language
- secret redaction baseline covering token material, provider keys, and raw prompts

## Project Route-State Checks

When `--project-root` is supplied, the smoke verifies:

- `docs/gdd/GDD.md` exists and its normalized hash matches `meta/routes/gdd-document/latest.json.generated_gdd_hash`
- `meta/routes/scene-route/latest.json.source_generated_gdd_hash` matches the generated GDD hash
- `source_scene_route_hash` in requirement map, prototype contract, and skeleton guard matches `confirmed_scene_route_hash`
- prompt-producing route states set `source_boundary_enforced=true`
- source-boundary evidence records `hosted-route-recovery-order.v1`, authority sources, and source hashes
- saved prompt evidence does not include broad raw `docs/game-type-guides` excerpts after contract freeze

## API Readback Checks

When `--base-url` and `--project-id` are supplied, the smoke reads `/api/projects/{projectId}/workflow-recommendation` and verifies descriptor/action readback exists. Auth uses `Authorization: Bearer <token>` when `--admin-token` is supplied. The token is never written to evidence.

## Compatibility

Existing Phase A/B project-creation smokes keep their current gates. This smoke is the dedicated refactor gate for routes that opt into the GDD-to-module hardening contracts.
