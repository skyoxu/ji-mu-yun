---
title: 'Phase 0A Clause-Level Acceptance Closure'
type: 'refactor'
created: '2026-07-12'
status: 'done'
review_loop_iteration: 0
baseline_commit: 'f58c1d2819ca4cffeb5ad02bdf06fd5a0718990b'
context:
  - 'C:/jimuyun/AGENTS.md'
  - 'C:/jimuyun/docs/standards/phase-service.md'
  - 'C:/jimuyun/execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/00-index.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 旧 Phase 0 完成声明只证明了部分机器契约和回归；新的条款级验收矩阵与三层审查发现 secret persistence、admin review queue、source-boundary、action descriptor、no-store 和证据映射仍有 P0/P1/P2，不能进入 Phase 0B。

**Approach:** 以 826 条稳定 check ID 的矩阵为追踪入口，先修复 Phase 0A 的真实代码、数据库、API、测试和 append-only 证据，再进行三层对抗复核；只有 unresolved P0/P1/P2 为零时才将 Phase 0A 标为 verified。

## Boundaries & Constraints

**Always:** 保持 API/DB additive compatibility；审计与失败历史 append-only；所有 admin/private readback 默认 no-store；恢复顺序、hash 与 prompt evidence fail closed；LLM/secret 输出在 persistence/export 前 redaction；每项结论绑定 code/test/evidence refs。

**Ask First:** 破坏性 live DB 迁移、修改 runtime/Caddy、改变 token/auth 模型、删除既有审计历史或改变 accepted ADR 决策。

**Never:** 在 finding 未清零时将 Phase 0A 标 verified；用 assistant 文本替代机器证据；原地覆盖 admin decision/history；把宽泛 phase evidence 复用于所有条款；提前进入 Phase 0B。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| admin queue decision | admin + current decision version + valid payload | versioned decision、redacted metadata、sidecar refresh | invalid=400, missing=404, conflict=409 |
| queue regeneration | same key with changed evidence after prior decision | append new row and supersede prior row | preserve prior decision/history |
| source-boundary verification | route state plus recovery/hash/prompt evidence | only complete evidence passes | missing/mismatch produces P0 blocker |
| private admin readback | authorized or unauthorized request | authorized redacted response with no-store | unauthorized stays admin-forbidden |

</frozen-after-approval>

## Code Map

- `PhaseA.Platform/Data/PhaseAMetadataStore.cs` -- queue versioning, filters, decisions, redaction and sidecar refresh.
- `PhaseA.Platform/Data/SqliteMetadataSchema.cs` -- additive supersession columns and indexes.
- `PhaseA.Platform/Program.cs` -- admin queue query/decision API and no-store policy.
- `PhaseA.Platform/Runs/ProjectRouteStateArtifactService.cs` -- source-boundary evidence validation.
- `PhaseA.Platform/Workflow/RouteActionDescriptors.cs` -- account/auth/idempotency action metadata.
- `PhaseA.Platform/Llm/LlmRouteEngine.cs` -- unique, redacted LLM evidence persistence.
- `scripts/python/build_gdd_to_module_acceptance_matrix.py` -- clause-level status derivation.

## Tasks & Acceptance

**Execution:**
- [x] Complete admin queue additive schema, append/supersede behavior, filters, mutation API, decision metadata and sidecar tests.
- [x] Apply no-store and admin authorization checks to all touched private audit/readback endpoints.
- [x] Close secret redaction, shared LLM evidence uniqueness, action descriptor and source-boundary negative paths.
- [x] Replace inferred matrix verification with explicit per-check evidence; mark later phases blocked until predecessor exit.
- [x] Run targeted/full regression, hardening smoke, governance audit and append a new Phase 0A exit review.
- [x] Run Blind Hunter, Edge Case Hunter and Acceptance Auditor; patch every P0/P1/P2 and repeat until clean.

**Acceptance Criteria:**
- Given every Phase 0A exit, local 01-07 acceptance and relevant split-added row, when the matrix is generated, then each has an allowed status and concrete owner/code/test/evidence refs or an auditable gap.
- Given queue regeneration or decision retry, when persistence is inspected, then decisions are idempotent, conflicts are versioned, prior rows remain queryable, and sidecar readback reflects supersession.
- Given secret-bearing text or host paths, when any touched persistence/export/evidence path writes data, then the stored/readback form is redacted.
- Given Phase 0A verification, when all tests/smokes/reviews complete, then the new evidence reports zero unresolved P0/P1/P2 and only then marks the phase verified.

## Spec Change Log

## Design Notes

The acceptance matrix is a traceability projection, not an authority that can manufacture success. Status transitions must be driven by explicit check-ID evidence. Queue supersession uses new rows so regenerated blockers cannot erase earlier human decisions.

## Verification

**Commands:**
- `dotnet test PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj --no-restore --filter <Phase0A targets>` -- all targeted contracts pass.
- `py -3 -m pytest scripts/python/tests/test_build_gdd_to_module_acceptance_matrix.py scripts/sc/tests/test_llm_backend.py` -- matrix and shared Python LLM entrypoint pass.
- `py -3 scripts/python/phase_a_gdd_to_module_hardening_smoke.py --repository-root C:/jimuyun` -- status ok with new append-only evidence.
- Governance audit and three-layer review -- zero unresolved P0/P1/P2.

## Suggested Review Order

**Source-boundary enforcement**

- Start with the route-level fail-closed boundary and evidence construction.
  [`GameDesignDocumentService.cs:1947`](../../PhaseA.Platform/Runs/GameDesignDocumentService.cs#L1947)

- Inspect exact, edited, inserted, deleted, and repeated-token detection.
  [`HostedRouteForbiddenSourceGuard.cs:12`](../../PhaseA.Platform/Workflow/HostedRouteForbiddenSourceGuard.cs#L12)

- Verify every catalog variant participates and partial loads fail closed.
  [`BmadGameTypeDesignCatalog.cs:44`](../../PhaseA.Platform/Prototypes/BmadGameTypeDesignCatalog.cs#L44)

- Confirm requirement-map generation propagates catalog completeness.
  [`GameDesignRequirementMapService.cs:585`](../../PhaseA.Platform/Runs/GameDesignRequirementMapService.cs#L585)

**Readback and persistence authority**

- Check prompt evidence validation against current source hashes and completeness.
  [`ProjectRouteStateArtifactService.cs:1195`](../../PhaseA.Platform/Runs/ProjectRouteStateArtifactService.cs#L1195)

- Review append-only queue supersession and concurrent producer serialization.
  [`PhaseAMetadataStore.cs:1517`](../../PhaseA.Platform/Data/PhaseAMetadataStore.cs#L1517)

- Verify admin decision APIs and private no-store handling.
  [`Program.cs:519`](../../PhaseA.Platform/Program.cs#L519)

- Inspect sidecar authority fields for live, deferred, and superseded states.
  [`ProjectAdminReviewQueueSidecarWriter.cs:8`](../../PhaseA.Platform/Runs/ProjectAdminReviewQueueSidecarWriter.cs#L8)

**Governance and verification**

- Review canonical action semantics, paths, auth, and idempotency metadata.
  [`RouteActionDescriptors.cs:6`](../../PhaseA.Platform/Workflow/RouteActionDescriptors.cs#L6)

- Confirm matrix status transitions require explicit reviewed check-ID evidence.
  [`build_gdd_to_module_acceptance_matrix.py:763`](../../scripts/python/build_gdd_to_module_acceptance_matrix.py#L763)

- Finish with adversarial source-boundary regression coverage.
  [`RouteOperationGovernanceTests.cs:136`](../../PhaseA.Platform.Tests/Workflow/RouteOperationGovernanceTests.cs#L136)
