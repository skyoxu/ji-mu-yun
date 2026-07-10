---
title: "同步 Game Type Guides 并闭合前台 BMAD 可用性"
type: "chore"
created: "2026-07-10"
status: "done"
review_loop_iteration: 1
baseline_commit: "a57640d685e0d3fc4875a42f67a1ba34d62f6555"
context:
  - "{project-root}/AGENTS.md"
  - "{project-root}/docs/standards/phase-service.md"
  - "{project-root}/docs/architecture/ADR_INDEX_PHASE.md"
---

<frozen-after-approval reason="human-owned intent - do not modify unless human renegotiates">

## Intent

**Problem:** `docs/game-type-guides` 的正文已与 GDS v0.6.0 对齐，但来源说明、24/25 数量口径和 Phase A fallback 仍指向旧 `gds-create-gdd`；前台 read-only BMAD 调用还在项目外临时目录执行，不能可靠发现已同步到项目内的 skill。

**Approach:** 将 `gds-gdd/assets` 设为 canonical、保留旧路径兼容回退和本仓 `survivorslike` 扩展，加入防漂移测试；让网页聊天与 Skill Action 在项目仓库根目录以 read-only 模式调用 Codex，并用静态引用审计和针对性测试验证前台 BMAD 链路。

## Boundaries & Constraints

**Always:** 保留 24 个上游指南的原始正文、本仓追加的 Default Prototype Contract/Module Matrix、扩展标签和 `survivorslike`；保持 docs 最高读取优先级；中文文档使用 UTF-8；引用 ADR-0032、ADR-0037、ADR-0038 的既有边界。

**Ask First:** 若需要移除兼容 skill、改变公开 API、修改 live DB/runtime/auth/shared LLM entrypoint，或执行真实计费的线上 BMAD run。

**Never:** 整目录覆盖 `docs/game-type-guides`；删除本仓扩展；把 24 个上游类型误写成 25 个上游类型；仅凭 prompt 含 skill 名就宣称技能已加载；回退当前 Phase A 重构。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Docs catalog present | 25-row repo catalog | Load docs first, including `survivorslike` and expanded tags | No fallback needed |
| Docs partial or missing | Canonical GDS assets present | Merge valid docs rows over 24 canonical rows; use compatibility mirror only after canonical | Missing repository-only extension remains unavailable instead of impersonating another type |
| Frontend skill mode | User selects game-design-master | Codex runs read-only from project repo and can discover seeded `.agents/skills` and refreshed `_bmad` | Preserve normal route failure/status evidence |
| Upstream drift | Canonical guide/CSV changes | Deterministic test reports prefix, tag, contract, mirror, or extension mismatch | Block validation until docs are reconciled |

</frozen-after-approval>

## Code Map

- `docs/game-type-guides/**` -- 24 upstream-derived guides plus one Ji Mu Yun extension and repo-only contracts/tags.
- `PhaseA.Platform/Prototypes/BmadGameTypeDesignCatalog.cs` -- docs/canonical/compatibility fallback order and row-level merge.
- `PhaseA.Platform/Llm/ChatService.cs` -- browser chat BMAD skill-mode working directory.
- `PhaseA.Platform/Skills/SkillActionService.cs` -- standalone frontend Skill Action working directory.
- `PhaseA.Platform/Workspaces/ProjectWorkspaceSeeder.cs` -- refreshes skills and BMAD runtime/config into existing hosted projects.
- `scripts/python/tests/test_game_type_guides_module_matrix.py` -- repo drift, guide-contract, generator, and installed-skill gate.
- `PhaseA.Platform.Tests/**` -- frontend prompt, workspace, catalog fallback, and route regression coverage.

## Tasks & Acceptance

**Execution:**
- [x] Update guide-source/count documentation and register `survivorslike` as the sole repository extension.
- [x] Change catalog fallback to docs -> `gds-gdd/assets` -> `gds-create-gdd` compatibility mirror, including partial-catalog row fallback.
- [x] Repair and extend guide drift tests for upstream prefix parity, required repo contracts, tag supersets, mirror parity, unique 25-type registry, scene/module tables, and generator invariants.
- [x] Run browser chat and Skill Action read-only Codex calls from the seeded project repository and assert skill plus `_bmad` visibility.
- [x] Audit all Phase A BMAD/GDS skill references against `.agents/skills`, then run targeted frontend/GDD/prototype tests and BMAD status checks.

**Acceptance Criteria:**
- Given the current stable GDS install, when guide drift tests run, then 24 upstream guides match canonical prefixes, one `survivorslike` extension is explicit, all 25 unique effective guides have valid repo contracts, and docs tags are supersets.
- Given docs guides are partial or unavailable, when the design catalog loads, then valid docs rows override canonical rows, canonical fills missing rows, the compatibility mirror remains a final fallback, and a missing `survivorslike` extension does not masquerade as `survival`.
- Given a browser user selects 游戏策划大师, when chat or Skill Action invokes Codex, then the request workspace is the project repo, the alias skill and required `_bmad` activation files exist there, and execution remains read-only.
- Given all explicit Phase A skill names and GDS asset directories, when the readiness audit runs, then every production reference resolves to an installed skill and targeted tests pass.

## Spec Change Log

- Review iteration 1: restored UTF-8 Chinese content after Windows command transport replaced non-ASCII text; expanded partial-catalog, repository-extension, existing-workspace `_bmad`, table-schema, unique-id, and generator acceptance based on blind-review findings. KEEP: canonical GDS source, compatibility alias, project-root read-only execution, and append-only readiness evidence.
- Review iteration 1 edge closure: merged partial CSV fields safely, rejected duplicate ids and escaping fragment paths, refreshed only required `_bmad` activation files, pruned the eight explicitly retired managed skills while preserving unknown project skills, and made Chapter 2 fail closed on a damaged catalog.
- Review iteration 1 final closure: rejected missing/unreadable/reparse-point guide fragments and malformed CSV rows, preserved existing project GDS config while filling it only when absent, and made the checked-in Chapter 2 skill byte-identical to generator output.
- Review iteration 1 final edge closure: restored generated Chapter 2 read-only JSON/gameplay-fit/Chinese-encoding rules, required the complete catalog header and non-empty fragment field, and validated CSV plus guide paths from the trusted repository root across reparse components.
- Review iteration 1 empty-guide closure: repository rows whose guide normalizes to empty are discarded so unavailable extensions cannot appear ready without prompt context.

## Design Notes

The frontend keeps the compatibility name `bmad-agent-game-designer` because it is part of current browser/API behavior. That alias delegates to canonical `gds-agent-game-designer`; changing the public action now would add migration risk without improving capability.

## Verification

**Commands:**
- `py -3 -m unittest scripts.python.tests.test_game_type_guides_module_matrix scripts.sc.tests.test_llm_backend` -- expected: guide, mirror, count, skill-reference, generator, and LLM backend checks pass.
- `dotnet test PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj --filter "<targeted classes>"` -- expected: frontend, workspace seeding, catalog, GDD, and route BMAD integration passes.
- `npx -y bmad-method@6.10.0 status` -- expected: BMAD Core/BMM 6.10.0 and GDS v0.6.0 are up to date.
- `py -3 logs/bmad-upgrade/2026-07-10/audit_upgrade.py` -- expected: functional/version checks pass; the historical frozen-snapshot checks remain explicitly superseded by this authorized follow-up and are not rewritten.

## Suggested Review Order

**Catalog authority and safety**

- Merge docs over canonical assets while failing closed on malformed or unsafe rows.
  [`BmadGameTypeDesignCatalog.cs:60`](../../PhaseA.Platform/Prototypes/BmadGameTypeDesignCatalog.cs#L60)

- Validate trusted-root fragments, missing content, duplicate ids, and reparse boundaries.
  [`BmadGameTypeDesignCatalog.cs:127`](../../PhaseA.Platform/Prototypes/BmadGameTypeDesignCatalog.cs#L127)

**Frontend skill discovery**

- Run browser chat from the seeded project root so Codex discovers repository skills.
  [`ChatService.cs:216`](../../PhaseA.Platform/Llm/ChatService.cs#L216)

- Apply the same read-only project-root behavior to standalone Skill Action.
  [`SkillActionService.cs:145`](../../PhaseA.Platform/Skills/SkillActionService.cs#L145)

- Refresh activation scripts, preserve project config, and prune only retired managed skills.
  [`ProjectWorkspaceSeeder.cs:31`](../../PhaseA.Platform/Workspaces/ProjectWorkspaceSeeder.cs#L31)

**Guide and workflow contract**

- Establish the 24-upstream-plus-one-extension source and count contract.
  [`README.md:3`](../../docs/game-type-guides/README.md#L3)

- Keep the Ji Mu Yun extension fully contract- and matrix-backed.
  [`survivorslike.md:15`](../../docs/game-type-guides/survivorslike.md#L15)

- Preserve read-only JSON classification and Chinese UTF-8 interaction on regeneration.
  [`SKILL.md:63`](../../.agents/skills/workflow-chapter2-repository-bootstrap/SKILL.md#L63)

**Regression evidence**

- Gate all 25 guides, source mirrors, schema tables, generator parity, and skill references.
  [`test_game_type_guides_module_matrix.py:40`](../../scripts/python/tests/test_game_type_guides_module_matrix.py#L40)

- Exercise partial catalogs and canonical fallback at the runtime boundary.
  [`GameTypeTemplateCatalogTests.cs:568`](../../PhaseA.Platform.Tests/Prototypes/GameTypeTemplateCatalogTests.cs#L568)

- Prove existing workspaces expose the alias and required BMAD activation files.
  [`SkillActionServiceTests.cs:48`](../../PhaseA.Platform.Tests/Skills/SkillActionServiceTests.cs#L48)

- Review the source/test-ready conclusion and explicit live-runtime exclusions.
  [`frontend-bmad-readiness.md:1`](../../logs/bmad-upgrade/2026-07-10/frontend-bmad-readiness.md#L1)
