# Source Coverage

## Normative source set

- `execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan.md`
- `docs/adr/ADR-0044-knowledge-projection-authority-e2-hosted-context-envelope.md`
- `docs/adr/ADR-0033-phase-metadata-sqlite-local-disk.md`
- `docs/adr/ADR-0035-phase-controlled-runner-workspace-execution.md`
- `docs/adr/ADR-0037-phase-shared-llm-codex-entrypoints.md`
- `docs/adr/ADR-0038-phase-evidence-sidecars-readback.md`
- `docs/architecture/phase-service/prototype-routes-and-recovery.md`
- `docs/architecture/phase-service/llm-codex-execution.md`
- `docs/standards/phase-service.md`
- `AGENTS.md`

## Current source anchors

| Contract fact | Source |
| --- | --- |
| Eight-source Hosted recovery order | `PhaseA.Platform/Workflow/HostedRouteRecoveryContract.cs` |
| Seeder managed paths and exclusions | `PhaseA.Platform/Workspaces/ProjectWorkspaceSeeder.cs` |
| Shared structured LLM entrypoint | `PhaseA.Platform/Llm/LlmRouteEngine.cs` |
| Shared executable Codex entrypoint | `PhaseA.Platform/Runs/CodexHostedProcessCommandFactory.cs` |
| Shared Python backend | `scripts/sc/_llm_backend.py` |
| Prompt evidence DB binding | `PhaseA.Platform/Data/SqliteMetadataSchema.cs` and `docs/standards/phase-service.md` |
| Paused BH-HANDOFF dependency | `execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan.md` |
| Knowledge maintenance and consumption authority | ADR-0044 section 6 and original-requirements amendment section 20 |
| Repository fact baseline | Pinned local committed `refs/heads/main`; no implicit fetch and no dirty-worktree fact authority |
| Future maintenance Skill package | `.agents/skills/maintain-knowledge-base/SKILL.md` after separate K14 authorization |
| Future first consumption adapter | One CLI over the canonical Locator core; later Skill/Tool/MCP/Phase adapters reuse the same contracts |

The inventory generator records the current file-state snapshot and callsite fingerprints. It is the source for caller membership, not the hand-written observation that the repository once had nine calls.
