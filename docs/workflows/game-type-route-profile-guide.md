# 游戏类型路由 Profile 接入指南

本文说明后续如何像现有 RPG / Survivors-like 路由一样添加新的游戏类型路由，并让原型创建、迭代计划、执行下一目标、Needs Fix 和最终验收都切到该类型的专属规则。

## 设计原则

- 不为每个游戏类型新增公开 API 路由，继续使用现有 Phase A 原型工作流入口。
- 游戏类型切换由 `GameTypeRouteEngine` 和 `GameTypeRouteStrategies` 在平台内部完成。
- `PrototypeRouteSkillPolicy` 保持为兼容门面，继续给现有服务提供 skill、profile 和 prompt block。
- 只读或 JSON LLM 调用必须继续使用 `ILlmRouteEngine`。
- 可执行 Codex 工作流必须继续使用 `CodexHostedProcessCommandFactory`。
- prompt 传输保持 stdin-first，不要把大 prompt 拼到命令行参数里。

## RPG 现状

新增可执行游戏类型前，先读取 `docs/workflows/game-type-route-framework-guide.md`。该文档以当前 JRPG 路由为参考实现，说明 capability graph、可信输入边界、计划 guard、验收映射和测试矩阵。

RPG 现在由两层提供专属能力：

- `PhaseA.Platform/Runs/GameTypeRouteEngine.cs` 中的 `GameTypeRouteProfiles.Rpg` 负责路由 profile 和 skill 上下文。
- `PhaseA.Platform/Runs/GameTypeRouteStrategies.cs` 中的 `RpgGameTypeRouteStrategy` 负责类型能力、验收映射和兼容旧 RPG 形状。

RPG/JRPG 现在是 capability-driven：默认只保留 opening context、field navigation、final first-loop acceptance；BattleScene、奖励、回地图、任务推进等只在当前请求、合同或 session-scoped selected capabilities 明确选择时进入计划和验收。

## 当前已注册 Route Profiles

当前平台内已经存在的 route profile 不止 RPG：

| Game type | Profile | 状态 | 说明 |
| --- | --- | --- | --- |
| `default` | `godot-playable-default-v1` | Active | 通用原型路由，供未识别类型使用。 |
| `rpg` | `godot-rpg-v1` | Active | 当前 JRPG/RPG 可执行专属路由。 |
| `survivorslike` | `godot-survivorslike-v1` | Active | 当前 Vampire Survivors-like 可执行专属路由。 |
| `deckbuilder` | `godot-deckbuilder-v1` | Active | 当前卡牌构筑 / roguelike deckbuilder 可执行专属路由；路线/节点选择是条件能力。 |

这意味着新增游戏类型的文档不应该假装当前系统只有 RPG。后续维护者必须先区分：

- 已注册的可执行 route profile。
- 仅有文档输入的未来类型。
- 仍然回退到 default 路由的泛型项目。

## 顶层项目工作流路由关系

`ProjectWorkflowRouteService` 是当前普通用户“下一步建议”和项目进度查询的顶层路由。它不会替代 `GameTypeRouteProfile` 或 `IGameTypeRouteStrategy`，但会把项目状态整理成用户可见流程，并决定下一步应该打开哪个页面或 run 入口。

当前顶层进度步骤是：

1. 游戏项目概述
2. 原型骨架创建
3. 骨架验收修复
4. 完成迭代计划
5. UI优化
6. 原型项目验收
7. 项目素材库
8. 打包下载项目

新增可执行游戏类型时，除了接入 profile、strategy、skill 和计划/验收外，还要确认 `ProjectWorkflowRouteService` 的下一步建议是否需要类型差异：

- 非 generic route 在已打包后会额外建议 UI 优化和项目素材库。
- UI 优化是 option，不应卡住原型项目验收或打包下载。
- 素材清单和打包下载属于项目级工作流，不应该写进单个 game-type strategy 的 acceptance contract。
- 聊天里的“下一步建议”只查询顶层项目路由；一次性按钮只打开对应页面，不自动启动 run。

## BMAD/GDS 24 Game-Type Templates

BMAD/GDS game-type templates are design semantics, not Phase A executable routes. The runtime catalog first reads `docs/game-type-guides/game-types.csv` and `docs/game-type-guides/<game-type>.md`; if those extracted docs are missing, it falls back to `.agents/skills/gds-create-gdd/game-types.csv` and matching fragments.

Use boundaries:

- Use them for game-type classification, GDD/free-chat context, iteration-plan semantic hints, and source material for future route profiles.
- Do not turn every GDD section in a template into iteration steps.
- Do not assume all 24 ids have dedicated Godot executable routes just because the taxonomy exists.
- A type becomes a Phase A executable route only after it has `GameTypeRouteProfile`, `IGameTypeRouteStrategy`, skill contract, plan generation/evaluation, execution acceptance, and tests.

Current runtime integration:

- `BmadGameTypeDesignCatalog` loads the 24 design templates read-only.
- RPG/JRPG iteration planning injects the `rpg` guide excerpt as taxonomy and semantic hints.
- RPG/JRPG execution boundaries still come from `prototype-rpg-godot-zh`, `GameTypeRouteProfiles.Rpg`, and `RpgGameTypeRouteStrategy`.
- Survivors-like execution boundaries come from `prototype-survivorslike-godot-zh`, `GameTypeRouteProfiles.SurvivorsLike`, and `SurvivorsLikeGameTypeRouteStrategy`.
- Deckbuilder execution boundaries come from `prototype-deckbuilder-godot-zh`, `GameTypeRouteProfiles.Deckbuilder`, and `DeckbuilderGameTypeRouteStrategy`.
- Generic project-level next-step advice, UI optimization prompts, asset inventory prompts, package/download prompts, and route buttons are produced by `ProjectWorkflowRouteService`, not by the game-type route strategy itself.

When adding a new game type, extract first-loop capability vocabulary from the BMAD/GDS guide first, then decide whether the type deserves a Phase A executable route profile.

## 新增游戏类型步骤
### 1. 新增专属 skill

在 `.agents/skills/` 下新增目录，例如：

```text
.agents/skills/prototype-slg-godot-zh/SKILL.md
.agents/skills/prototype-slg-godot-zh/references/slg-prototype-contract.md
```

`SKILL.md` 需要写清该类型的核心循环、每个迭代 step 的边界、Godot 场景要求、Core 测试要求、素材使用要求和最终验收条件。

### 2. 注册 `GameTypeRouteProfile`

在 `PhaseA.Platform/Runs/GameTypeRouteEngine.cs` 中新增 profile，例如 `GameTypeRouteProfiles.Slg`。需要填写：

- `GameTypeId`，例如 `slg`。
- `ProfileId`，例如 `godot-slg-v1`。
- `RouteSetId`，例如 `slg-prototype-routes-v1`。
- `PromptProtocolId`，例如 `slg-prompt-protocol-v1`。
- `RouteSkill`，指向新 skill 和 contract。
- `PlannerId`、`EvaluatorId`、`ExecutorId`、`NeedsFixId`、`FinalAcceptanceId`。

同时扩展 `GameTypeRouteProfiles.Resolve(project)` 的识别逻辑。这里只判断类型，不要写计划、验收或文件检查规则。

### 3. 新增类型策略

在 `PhaseA.Platform/Runs/GameTypeRouteStrategies.cs` 中新增策略类，例如 `SlgGameTypeRouteStrategy`。策略应该表达：

- 是否需要模型参与迭代计划。
- 是否禁止空目标列表。
- 是否启用专属计划逻辑。
- 是否启用专属计划评估。
- 如何把目标映射到 `PrototypeGoalAcceptanceContract`。

不要把新类型的 `IsXxxProject` 分支写回 `PrototypeGoalAcceptanceValidator`。validator 应继续只执行通用检查和可复用的文件验证。

### 4. 添加专属计划和硬拦截

如果新类型需要像 RPG 一样严格控制 step 顺序，在 `PrototypeIterationPlanService` 中新增该类型的 scaffold builder、LLM refinement prompt、parse/guard 和本地硬拦截方法。

硬拦截应先于 LLM 评估运行，用于阻断顺序错误、缺失核心 step 或过度泛化的计划。

### 5. 添加测试

最少需要覆盖：

- `PrototypeRouteSkillPolicyTests`：新类型能解析到正确 profile、skill、contract 和 prompt block。
- `PrototypeIterationPlanServiceTests`：新类型能生成专属 step 顺序，错误或泛化计划会被拒绝或要求重拆。
- `PrototypeIterationGoalServiceTests`：执行目标时能使用新类型的 acceptance kind。
- `ProjectWorkflowRouteServiceTests`：顶层项目路由能根据项目状态、UI 优化、素材清单、打包下载和试玩反馈给出正确下一步建议。

## 验证命令

```powershell
dotnet test PhaseA.Platform.Tests\PhaseA.Platform.Tests.csproj --filter "FullyQualifiedName~PrototypeRouteSkillPolicyTests|FullyQualifiedName~PrototypeIterationPlanServiceTests|FullyQualifiedName~PrototypeIterationGoalServiceTests|FullyQualifiedName~PrototypeRepairPlanServiceTests|FullyQualifiedName~ProjectWorkflowRouteServiceTests" --no-restore
git diff --check
```

如果影响 live Phase A 服务，使用 `runtime/phase-a/start-phasea.ps1` 重启，不要用 `dotnet run` 直接启动 live 服务。

## 不要做的事

- 不要为每个游戏类型新增公开 API 路由。
- 不要绕过 `PrototypeRouteSkillPolicy` 自己拼 profile prompt。
- 不要绕过 `ILlmRouteEngine` 或 `CodexHostedProcessCommandFactory`。
- 不要让默认 7-day route 偷跑已识别游戏类型的专属项目。
- 不要把类型合同只写在文档里，必须有可测试的策略映射和 acceptance kind。

## 常见文件清单

```text
.agents/skills/prototype-<type>-godot-zh/SKILL.md
.agents/skills/prototype-<type>-godot-zh/references/<type>-prototype-contract.md
docs/prototype-type-kits/<type>.md
PhaseA.Platform/Runs/GameTypeRouteEngine.cs
PhaseA.Platform/Runs/GameTypeRouteStrategies.cs
PhaseA.Platform/Runs/ProjectWorkflowRouteService.cs
PhaseA.Platform/Runs/PrototypeIterationPlanService.cs
PhaseA.Platform.Tests/Runs/PrototypeRouteSkillPolicyTests.cs
PhaseA.Platform.Tests/Runs/PrototypeIterationPlanServiceTests.cs
PhaseA.Platform.Tests/Runs/PrototypeIterationGoalServiceTests.cs
PhaseA.Platform.Tests/Runs/ProjectWorkflowRouteServiceTests.cs
```
