# Scope, Authority And Non-Goals

## Original requirements

The single-file input is `execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan.md`. Its role is original-requirements input. The machine contracts in this directory make the requirements observable; they do not silently change the source intent.

The historical `docs/know1.txt` through `docs/know5.txt` files are source lineage only. They are not current authority and are not copied into a runtime prompt.

## Accepted decision

`docs/adr/ADR-0044-knowledge-projection-authority-e2-hosted-context-envelope.md` is the new Accepted decision for this initiative.

- It extends ADR-0037 and uses its three shared LLM/Codex entrypoints.
- It complements ADR-0038 and aggregates its evidence, redaction, hash and account-scope rules.
- It does not supersede ADR-0037 or ADR-0038.
- It leaves E3 outside scope and does not rely on Proposed ADR-0040 as implementation authority.

## In scope

- Four dimensions: Domain, per-domain Visibility, Lifecycle Instance, Enforcement Level.
- Toolchain, Phase, Workspace and Marketplace domain metadata and dependency closure.
- Repository, template, project and run lifecycle boundaries.
- Deterministic snapshot, tokenizer, ranking, evaluation, budget and omission contracts.
- One canonical deterministic Knowledge Locator core, a CLI-first JSON adapter, precise source-location results, and caller/source hash revalidation.
- One repository-local `maintain-knowledge-base` Skill contract with closed-world `existing-only` and explicit `targeted` modes.
- Local committed `refs/heads/main` authority semantics, provisional target-only worktree handling, no implicit fetch, and append-only maintenance evidence.
- E1 Projection and E2 Context Envelope as plan-local contracts.
- Source-generated caller inventories for Codex, `LlmRouteEngine`, and Python `run_llm_exec`.
- Positive and negative fixtures and a composition validator.
- K0-K14 implementation slices, acceptance refs, and recovery evidence rules.

## Out of scope

- Any Phase production code, runtime, Caddy, live DB or live Hosted workspace change before the relevant gate.
- E3 filesystem/process/network/secret isolation.
- Replacement of existing route recovery, prompt scan, DB evidence, or readback contracts.
- A second LLM provider or subprocess architecture.
- Formal Bootstrap Review execution during plan construction.
- A generated fact-answer service, default LLM/embedding retrieval, or caller-LLM ownership of trusted query fields.
- Source or consumer-object mutation by the maintenance Skill.
- Production Phase API, Browser, MCP, or Hosted route exposure of the Locator before the K11-K13 protected gate.

## Protected-path rule

K0-K10 are plan-local, offline, or synthetic only. K5 specifies the Locator core and first adapter without authorizing production integration. K11-K13 may generate read-only inventory, but production integration is blocked until the paused frontend-boundary plan has a successful BH-HANDOFF or a formal merge/supersede decision exists. K14 specifies the repository-local maintenance Skill but retains separate downstream authorization. Every exact write set requires explicit user authorization; the plan never infers it from its own validator.
