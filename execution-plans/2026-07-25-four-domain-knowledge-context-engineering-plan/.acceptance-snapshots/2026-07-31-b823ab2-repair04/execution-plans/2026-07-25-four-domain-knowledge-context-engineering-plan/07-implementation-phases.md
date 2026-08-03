# Implementation Phases

## Phase A: Plan-local foundation (K0-K4)

Create and validate the synthetic environment contract, ADR relationship, Schema, fixtures, deterministic snapshot rules, cache-root checks, and repository catalog. No Phase production code is in the write set.

## Phase B: Deterministic retrieval and E1 (K5-K6)

Freeze the hybrid tokenizer, ranking parameters, glob semantics, evaluation set, and K5 ambiguity delegation through `scripts/sc/_llm_backend.py::run_llm_exec`. Specify one deterministic Knowledge Locator core and CLI-first JSON adapter: caller LLMs provide intent only, trusted adapters own authority/scope/snapshot/budget, and results contain locations plus hashes rather than generated facts. Build only the experimental Phase Projection and its local evidence.

## Phase C: Lifecycle projections and observe-only assembly (K7-K10)

Model actual Seeder behavior, build isolated project/recovery projections, and assemble a synthetic Context Envelope. This phase may validate signatures and contract composition but cannot change Hosted production dispatch.

## Phase D: Protected Hosted integration (K11-K13)

Read-only inventory can be generated before handoff. Any production integration waits for the paused frontend-boundary plan BH-HANDOFF or a formal merge/supersede decision, a new/updated Accepted ADR set, explicit user authorization, and a non-overlapping write set. Migration is server-controlled `legacy -> observe -> enforce`.

## Phase E: Other domains and maintenance (K14)

Complete Toolchain, Workspace shared and Marketplace projections only after E2 prerequisites are independently current. Create the separately authorized repository-local `maintain-knowledge-base` Skill as a thin adapter over K3-K5 deterministic tools. Validate existing-only closed-world refresh, targeted discovery, local-main pinning, provisional worktree content, zero source mutation, append-only logging, incremental/full rebuild, LKG, retention and compatibility. E3 remains a separate Phase C plan.

## Resumption rule

Resume from `resume-state.v1.json`. Re-run the affected slice targeted command, then the terminal whole-directory validator. Never infer state from chat summaries or old inventory bytes.
