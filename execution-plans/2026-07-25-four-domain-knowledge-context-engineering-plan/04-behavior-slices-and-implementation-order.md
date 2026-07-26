# Behavior Slices And Implementation Order

Each slice names a controlled negative path, a green/acceptance path, dependents, and write policy. A RED result is a declared absence or invalid fixture; it is not fabricated historical evidence.

| Slice | Behavior | RED / controlled negative | GREEN / acceptance | Dependents | Production write policy |
| --- | --- | --- | --- | --- | --- |
| K0 | Synthetic pollution and access baseline | Missing synthetic-only manifest is rejected | Baseline manifest and canary report validate | K1, K2 | Forbidden; no live DB/workspace |
| K1 | ADR-0044 and four-dimensional authority | Missing ADR relationship or E3 claim is rejected | ADR/index and contract references validate | K2 | Plan/docs only |
| K2 | Plan-local Schema and fixture set | Unknown field/revision fixture fails with targeted code | All schemas and positive/negative cases validate | K3, K4 | Plan-local only |
| K3 | Snapshot, Windows path, cache root, lock and LKG | Case collision, reparse escape, cache-under-workspace fail | Same input reproduces snapshot and failed build preserves LKG | K4, K5 | Plan-local only |
| K4 | Repository Source Catalog | Excluded logs/workspace/cache source is returned | Catalog and provenance bind to snapshot | K5, K6 | Plan-local only |
| K5 | Deterministic Knowledge Locator, classification, tokenizer, ranking and evaluation | LLM-owned trusted fields, generated answer, source identity drift, direct provider invocation or unstable ranking fails | Shared request/result contract, JSON CLI adapter, exact location/insufficient-match fixtures and evaluation vectors pass; ambiguity uses `scripts/sc/_llm_backend.py::run_llm_exec` only | K6-K14 | Plan-local only |
| K6 | Experimental Phase E1 Projection | Forbidden/stale/cross-domain result fails | E1 projection meets evaluation thresholds | K7, K8, K9, K10 | Plan-local only |
| K7 | Repository Template Projection | Seeder-derived managed paths missing or cache copied | Template projection matches actual Seeder policy | K8 | Plan/local docs only |
| K8 | Project Instance Projection | Cross-account/project or stale generation fails | Isolated project cache and LKG validate | K9, K10 | Synthetic/plan-local only |
| K9 | Project Recovery Projection | Raw prompt, token, host path, other-account data fails | Sanitized recovery view validates | K10 | Synthetic/plan-local only |
| K10 | Context Assembler and envelope | Required omission, modified payload, stale contract fails | Deterministic assembly, JCS/HMAC vector and contract aggregate validate | K11 | Plan-local/observe-only; no production dispatch |
| K11 | Three caller inventories and direct-call guard | Source drift or unknown reachability blocks inventory | Generator reproduces all three snapshots and violations list | K12 | Read-only inventory allowed; production write waits BH-HANDOFF/merge |
| K12 | Per-route gate migration | Client-selected mode or rollback retaining E2 fails | Legacy -> observe -> read-only enforce path validates | K13 | Production write blocked until gate and user authorization |
| K13 | E2 release readiness | Any stale evidence, bypass, non-enforce route or failed test blocks | Mechanical E2 predicate and revocation behavior validate | K14 | Production write blocked until gate and user authorization |
| K14 | Other domains and `maintain-knowledge-base` Skill | Untargeted discovery, worktree fact promotion, source mutation, implicit fetch, dirty authority, non-append log, or rebuild without LKG fails | Thin Skill adapter, existing-only/targeted modes, incremental/full rebuild, append-only log, retention and old-index compatibility validate | None | Separate authorization after E2 |

## Recovery

If a slice fails, preserve the failed fixture or validation output under `logs/knowledge-context/<date>/<run-id>/` and invalidate only that slice plus declared dependents. This repair changes K5 and therefore invalidates K5-K14 plan evidence until targeted checks and one terminal full replay pass. A shared schema, validator, source snapshot, or lifecycle change always requires a terminal full replay.
