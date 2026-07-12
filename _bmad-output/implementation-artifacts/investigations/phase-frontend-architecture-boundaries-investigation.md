# Investigation: Phase 前台业务架构边界与工程治理现状

## Hand-off Brief

1. **发生了什么。** Phase 前台业务已有清晰的产品壳/工作流内核边界、变更契约和测试证据，但内部代码仍有显著巨石类、双向命名空间依赖和不完整的作业硬隔离。
2. **当前状态。** 调查已结论化；文档治理强，防御、测试和证据体系较成熟，但严格 SRP、单向分层、全局异常可观测性、requestId 闭环和 Phase SemVer 尚未满足。
3. **下一步。** 优先建立 Codex 文件变更 allowlist/diff 闸门和分拆前台/Program/MetadataStore 热点，再补 request correlation 与 Phase 平台版本来源。

## Case Info

| Field | Value |
| --- | --- |
| Ticket | N/A |
| Date opened | 2026-07-11 |
| Status | Concluded |
| System | Windows；Ji Mu Yun Phase A/B 平台；Godot + C# |
| Evidence sources | 仓库文档、源代码、测试、版本信息 |

## Problem Statement

确认用户提出的边界规划、测试止损、防御与日志、可维护性、文档协作和语义化版本规范是否合理，并分析 Phase 系统前台相关业务的当前仓库现状与越界风险。

## Evidence Inventory

| Source | Status | Notes |
| --- | --- | --- |
| `AGENTS.md` | Available | 已提供且将以工作区文件复核 |
| `README.md` | Available | 已完整阅读 |
| Phase 架构与标准文档 | Available | 已读取架构索引、Phase 标准、ADR 与执行规则 |
| `PhaseA.Platform/**` | Available | 已完成全仓静态盘点与代表性调用链抽样 |
| `PhaseA.Platform.Tests/**` | Available | 79 个测试源文件、约 1040 个 Fact/Theory；已核对代表性失败路径 |
| 版本与发布配置 | Available | Phase 平台无独立版本属性、根 CHANGELOG 或现有 git tag |

## Investigation Backlog

| # | Path to Explore | Priority | Status | Notes |
| - | --- | --- | --- | --- |
| 1 | 读取 AGENTS、README 与 Phase 标准 | High | Done | 文档治理强于部分代码落地 |
| 2 | 盘点 Phase 前台业务的分层与依赖方向 | High | Done | 逻辑分区存在，严格单向分层不存在 |
| 3 | 抽样测试、异常、日志与常量治理 | High | Done | 测试丰富；异常与关联标识仍有缺口 |
| 4 | 检查维护性与协作机制 | Medium | Done | 组合良好；巨石类和版本治理是主要缺口 |
| 5 | 形成证据分级结论与改进优先级 | High | Done | 已完成 |

## Timeline of Events

| Time | Event | Source | Confidence |
| --- | --- | --- | --- |
| 2026-07-11 | 用户发起 Phase 前台架构治理调查 | 对话 | Confirmed |

## Confirmed Findings

### Finding 1: 仓库已定义 Phase Service Change Contract

**Evidence:** `AGENTS.md` 的 Phase Service Change Contract、Protected Phase Paths 与 Definition of Done。

**Detail:** 仓库在文档层面对 API、持久化、认证、运行时、前台浏览器调用方、测试和证据有明确变更矩阵与保护边界。

### Finding 2: 前台关键链路存在多个巨石热点

**Evidence:** `PhaseA.Platform/Browser/BrowserUiRenderer.cs:10`、`PhaseA.Platform/Program.cs:33`、`PhaseA.Platform/Data/PhaseAMetadataStore.cs:12`、`PhaseA.Platform/Readback/ProjectWebPreviewService.cs:18`。

**Detail:** BrowserUiRenderer 约 12147 行，Program 约 3322 行，PhaseAMetadataStore 约 5441 行且约 95 个公开方法，ProjectWebPreviewService 约 5983 行。严格“一类一责”不成立。

### Finding 3: 目录分区清晰，但依赖方向没有编译期隔离

**Evidence:** `docs/architecture/phase-service/system-overview.md:38`、`PhaseA.Platform/Data/PhaseAMetadataStore.cs:3`、`PhaseA.Platform/Runs/ProjectWorkflowRouteService.cs:5`。

**Detail:** Data、Projects、Runs、Readback、Llm 等目录与命名空间清晰，但位于单一程序集且存在 Data/Runs、Projects/Prototypes、Runs/Readback 双向依赖。

### Finding 4: 测试和防御路径丰富，但不能证明普遍 test-first

**Evidence:** `docs/testing-framework.md:114`、`scripts/python/run_dotnet.py:163`、`PhaseA.Platform.Tests/Data/SqliteMetadataSchemaTests.cs:793`、commit `b7a3353`、commit `ffc2bb2`。

**Detail:** Phase 测试资产丰富并进入 CI，覆盖认证、路径、取消、恢复和失败优先级；但同提交无法还原书写顺序，且存在实现早于专门测试的历史样本。

### Finding 5: 日志、审计、证据体系存在，但 correlation 契约未闭合

**Evidence:** `docs/standards/phase-service.md:157`、`PhaseA.Platform/Program.cs:191`、`PhaseA.Platform/Program.cs:3167`。

**Detail:** 顶层异常会 LogError 并写 JSONL，run/account/LLM/artifact 证据可追溯；但全局错误与诊断没有实现标准要求的 requestId/correlationId。

### Finding 6: Phase 平台没有独立语义版本

**Evidence:** `README.md:354`、`PhaseA.Platform/PhaseA.Platform.csproj`、`.github/workflows/windows-release-tag.yml:3`。

**Detail:** README 的 v* 标签发布明确属于 Godot 模板；当前仓库无 tag，PhaseA.Platform 无版本属性，也没有根 CHANGELOG/VERSION。

## Deduced Conclusions

### Deduction 1: Codex 越界风险被规约降低，但未被统一硬闸门消除

**Based on:** Findings 1、2、3；`PhaseA.Platform/Runs/PrototypeIterationGoalService.cs:549`、`PhaseA.Platform/Runs/PrototypeQuickFixService.cs:3713`。

**Reasoning:** 作业提示词、恢复权威、保护路径和部分 focused workspace 能降低误改；但大文件、双向依赖、非全路由 focused workspace，以及缺少共享文件差异 allowlist，使越界仍可能发生。

**Conclusion:** 对 Codex 来说是“有软边界和部分硬边界”，不是“默认不可能越界”。

## Hypothesized Paths

### Hypothesis 1: 文档边界清晰，但大型服务类和前台单文件可能让 Codex 在局部修改时跨职责

**Status:** Confirmed

**Theory:** 平台演进速度较快，文档治理可能强于代码内部模块化程度。

**Supporting indicators:** 用户特别询问越界风险；仓库的 Phase 服务范围广且跨浏览器、API、持久化、运行时和生成工作流。

**Would confirm:** 发现高耦合大类、直接跨层访问、重复基础设施逻辑或前台/服务职责混合。

**Would refute:** 依赖方向稳定、薄入口、领域服务边界清楚，且有架构测试约束。

**Resolution:** 多个核心类的文件规模、方法数量和职责抽样确认了该风险；同时文档与部分 focused workspace 说明风险已有治理但未闭环。

## Missing Evidence

| Gap | Impact | How to Obtain |
| --- | --- | --- |
| 同一提交内测试与实现的编辑顺序 | 无法证明普遍 test-first | 需要更细粒度提交或红测运行证据 |
| 所有 Codex 可执行路由的实际文件差异 | 无法证明每条路由都不越界 | 为共享执行入口增加 allowlist/diff 验证并保留证据 |

## Source Code Trace

| Element | Detail |
| --- | --- |
| Error origin | 不适用；这是区域探索 |
| Trigger | 浏览器端项目创建、GDD、聊天、原型、修复和 Web Preview 流程 |
| Condition | 日常 Codex 变更依赖提示词、恢复源、服务边界和部分 focused workspace |
| Related files | `BrowserUiRenderer.cs`、`Program.cs`、`PhaseAMetadataStore.cs`、`Runs/**`、`Readback/**` |

## Conclusion

**Confidence:** High

用户提出的规范方向总体合理，但应避免机械化：接口只用于跨边界/替换点；常量按领域和契约集中而非一个全局桶；DTO 可保持无行为；“先写测试”对 bug 应升级为失败复现优先并保留 red 证据。当前仓库文档、测试、防御和证据治理较强，组合优先也落实良好；严格 SRP、单向分层、全路由 Codex 文件硬边界、异常降级可观测性、request correlation 和 Phase SemVer 尚未达标。

## Recommended Next Steps

### Fix direction

按优先级：统一 Codex 变更 allowlist/diff gate；拆 BrowserUiRenderer、Program、PhaseAMetadataStore；建立依赖方向测试；补 requestId/correlation 和降级 telemetry；建立 Phase 独立 SemVer/version endpoint/changelog。

### Diagnostic

对上述改进分别建立架构测试、契约测试和窄范围迁移计划；不要一次性大重构。

## Reproduction Plan

本调查已通过代表性浏览器请求追踪、静态依赖扫描、测试清单与提交历史完成验证。

## Side Findings

- `Program.cs:2634` 将 `ex.Message` 返回给浏览器，与统一脱敏目标存在潜在漂移。
- 诊断写入失败处的空 catch 有明确“不反向破坏业务”的理由，但缺备用 logger/metric，严格“不吞异常”仍未满足。
