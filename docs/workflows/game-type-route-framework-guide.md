# 游戏类型路由框架指南

本文面向未来维护者和 agent，说明当前 JRPG/RPG 路由为什么这样搭建、入口在哪里、如何运行、测试覆盖什么，以及如何借鉴这套框架为其他游戏类型创建完整的 Phase A 可执行路由。

建议同时读取：

- `docs/workflows/game-type-route-profile-guide.md`
- `docs/prototype-type-kits/rpg.md`
- `.agents/skills/prototype-rpg-godot-zh/SKILL.md`
- `.agents/skills/prototype-rpg-godot-zh/references/rpg-prototype-contract.md`
- `PhaseA.Platform/Runs/GameTypeRouteStrategies.cs`
- `PhaseA.Platform/Runs/JrpgRouteSemantics.cs`
- `PhaseA.Platform/Runs/PrototypeIterationPlanService.cs`
- `PhaseA.Platform.Tests/Runs/PrototypeIterationPlanServiceTests.cs`
- `PhaseA.Platform.Tests/Runs/PrototypeIterationGoalServiceTests.cs`

## 1. 这套框架解决什么问题

早期 RPG 原型路由容易把 RPG 固定理解为“地图 -> 遇敌 -> 战斗 -> 奖励 -> 回地图 -> 最终验收”。这对部分 Dragon Quest 风格原型有效，但对很多 RPG/JRPG 需求过重。例如用户只要求城镇探索、NPC 对话、任务目标更新、地图移动时，不应该自动创建或验收 `BattleScene`。

现在 JRPG 路由改成 capability-driven 框架：

1. 先从可信输入中选择 capability。
2. 用 capability 生成迭代计划 scaffold。
3. 本地 route guard 先检查计划边界。
4. 每个 goal 映射到明确 acceptance contract。
5. 最终验收只验收当前选中的 capability。
6. 模板、metadata、历史 summary、旧 route state 不能强行激活未请求的场景或系统。

未来其他游戏类型应该借鉴这个“能力图 + 可信输入边界 + 本地 guard + 条件验收”的结构，而不是复制 JRPG 的 10 个模块名称。

## 2. 公开入口与内部路由

JRPG 没有新增公开 API。它复用 Phase A 现有入口：

- prototype creation
- iteration-plan creation/evaluation
- execute-next-goal
- needs-fix / quick-fix repair
- final acceptance / package / readback

游戏类型切换发生在平台内部：

- `GameTypeRouteEngine` 和 `GameTypeRouteProfiles` 解析项目属于哪种 executable route profile。
- `PrototypeRouteSkillPolicy` 作为兼容门面，给服务层提供 skill、profile、prompt block。
- `GameTypeRouteStrategies.Resolve(...)` 返回对应的 `IGameTypeRouteStrategy`。
- `RpgGameTypeRouteStrategy` 是当前 JRPG/RPG 的参考实现。

未来新增类型时，不要为每种游戏类型新增公开 API 路由。应继续走同一套 Phase A 原型流水线，由内部 profile/strategy 分派。

## 3. 核心文件职责

| 文件 | 职责 |
| --- | --- |
| `PhaseA.Platform/Runs/GameTypeRouteEngine.cs` | 注册和解析 game-type route profile。 |
| `PhaseA.Platform/Runs/GameTypeRouteStrategies.cs` | 按游戏类型把 goal 映射为 acceptance contract；`RpgGameTypeRouteStrategy` 是 JRPG 参考实现。 |
| `PhaseA.Platform/Runs/JrpgRouteSemantics.cs` | JRPG battle/reward/negation/contract intent 的集中语义判断。 |
| `PhaseA.Platform/Runs/PrototypeIterationPlanService.cs` | JRPG capability 选择、scaffold 生成、LLM refinement 解析、本地计划 guard。 |
| `PhaseA.Platform/Runs/PrototypeGoalAcceptanceValidator.cs` | 执行 strategy 产出的 `PrototypeGoalAcceptanceContract`。 |
| `PhaseA.Platform/Runs/PrototypeRouteStateWriter.cs` | 写入 route state 和 project execution guide，供后续 route 恢复和执行。 |
| `.agents/skills/prototype-rpg-godot-zh/SKILL.md` | JRPG/RPG 可执行实现 skill。 |
| `.agents/skills/prototype-rpg-godot-zh/references/rpg-prototype-contract.md` | JRPG/RPG 实现合同。 |
| `docs/prototype-type-kits/rpg.md` | RPG type kit 与 capability-driven minimum acceptance。 |

### 3.1 复用 JRPG 时的改造对照

创建新游戏类型时，先复制框架关系，不要复制 JRPG 的具体能力名。

| JRPG 参考点 | 新类型应该保留什么 | 新类型必须替换什么 |
| --- | --- | --- |
| `GameTypeRouteProfile` | profile 作为内部路由分派入口，不新增公开 API。 | `GameTypeId`、`ProfileId`、skill、prompt protocol、route ids。 |
| `JrpgRouteSemantics` | 正向语义、否定语义、合同意图提取集中在一个 helper。 | 该类型自己的关键词、否定词、误触发词和合同字段。 |
| `JrpgFirstLoopCapabilities` | capability 以稳定 id、标题、描述、验收模板表达。 | always-on/conditional 能力图和首轮顺序。 |
| `FindRpgPlanContractIssue(...)` | 本地 guard 先于 LLM evaluation，负责硬边界。 | 新类型自己的缺步、宽泛步骤、越界验收、stale state 规则。 |
| `RpgGameTypeRouteStrategy` | strategy 把 goal title 映射到 acceptance contract。 | 新类型自己的 scene、marker、file proof、final acceptance 组合。 |
| `prototype-rpg-godot-zh` skill | skill 约束执行 agent 的可交付边界。 | 新类型 Godot 场景、测试、素材、UI、循环验收合同。 |
| JRPG tests | 测试覆盖 profile、计划、执行、修复、最终验收。 | 新类型正反例、session scoped state、模板污染、conditional acceptance。 |

判断是否可以“照搬”某段 JRPG 逻辑的标准：如果这段逻辑表达的是 Phase A 路由骨架，可以保留；如果它表达的是地图、队伍、战斗、奖励、任务等 JRPG 语义，必须替换。


## 4. Route State 与可信输入边界

常见 route state：

- `meta/routes/prototype/latest.json`
- `meta/routes/iteration-plan/latest.json`
- `meta/routes/execute-next-goal/step-XX/latest.json`
- `meta/routes/needs-fix/step-XX/latest.json`
- `meta/routes/prototype-repair/latest.json`
- `meta/routes/repair-plan/latest.json`

JRPG 当前规则：

- prototype contract 只能通过 `JrpgRouteSemantics.ExtractPrototypeContractIntentText(...)` 提取项目意图。
- iteration-plan state 必须匹配当前 goal 的 `session_id`，才允许读取 `source_message`、`regeneration_guidance`、`selected_capabilities`。
- 缺失或不匹配 `session_id` 的旧 route state 不得影响当前战斗/奖励判断。
- `game_name`、`game_type`、`smoke_scene`、模板说明、历史 prototype summary、analysis summary、field coverage missing reason、旧 goals 文案，都不能强制创建 runtime 场景。

未来任何新类型都必须保留这个边界。不要让模板词、metadata 或旧 state 激活当前请求没有选择的系统。

## 5. JRPG Capability 列表

JRPG 目前是 capability graph，不是固定全量 10 步。

### 5.1 Always-on capability

| Capability | 标准标题 | 目的 | 验收意图 |
| --- | --- | --- | --- |
| `opening_context` | `JRPG First Loop: opening context and player objective` | 让玩家知道控制谁、在哪里、下一目标是什么。 | 可控角色、场景语境、目标清晰。 |
| `field_navigation` | `JRPG First Loop: field navigation and stable control` | 独立验证地图/城镇/field 移动层。 | 入口打开可见地图或场景，移动稳定，地图/玩家素材可见。 |
| `final_first_loop_acceptance` | `JRPG First Loop: final first-loop acceptance` | 对选中 capability 做首轮闭环验收。 | 选中能力端到端可玩，合同字段、素材、Godot 验证、打包准备通过。 |

### 5.2 Conditional capability

| Capability | 标准标题 | 触发条件 | 验收意图 |
| --- | --- | --- | --- |
| `interaction_discovery` | `JRPG First Loop: interaction and discovery beat` | NPC、对话、宝箱、调查、发现、事件。 | 至少一个交互可见、可到达，并改变反馈/目标/理解。 |
| `conflict_entry` | `JRPG First Loop: conflict entry trigger` | 遇敌、敌人、危险、冲突、挑战入口。 | 玩家能触发或到达第一个冲突，触发规则可见或被验证。 |
| `battle_or_challenge_resolution` | `JRPG First Loop: battle or challenge resolution` | 战斗、combat、enemy、monster、boss、fight、challenge resolution。 | 一个冲突或挑战能被解决，有状态、行动反馈和结算。 |
| `party_or_character_state` | `JRPG First Loop: party or character state readability` | HP、属性、装备、队伍、状态、被动。 | 玩家侧角色状态可见、可理解，并与规则一致。 |
| `growth_feedback` | `JRPG First Loop: growth, reward, or consequence feedback` | 奖励、道具、等级、经验、技能、选择、成长、后果反馈。 | 奖励/成长/后果可理解，状态变化可见或可验证。 |
| `return_or_continue_loop` | `JRPG First Loop: return or continue loop` | 结算后继续、回地图、下一可玩状态。 | 原型能进入目标下一状态，输入和视觉不堆叠不失效。 |
| `quest_or_story_progress` | `JRPG First Loop: quest or story progress` | 剧情、任务、城镇事件、NPC 流程、目标完成。 | 剧情/任务/目标状态可见推进，能追溯到请求。 |

## 6. BattleScene 与 Reward 的条件规则

- 表单/合同/当前 capability 没有战斗或冲突语义时，不创建、不要求、不修复 `BattleScene`。
- 当前有效 `selected_capabilities` 包含 `conflict_entry` 或 `battle_or_challenge_resolution` 时，最终验收需要 battle 相关证明。
- 当前有效 `selected_capabilities` 包含 `growth_feedback` 时，最终验收需要 reward/growth/consequence 相关证明。
- `return_or_continue_loop` 本身不等于 reward flow。它只证明能继续或回到下一可玩状态。
- `scene switching`、`asset/UI validation`、`contract alignment` 都不能默认要求 battle/reward；它们只能根据当前可信语义追加对应 marker。

## 7. 迭代计划如何运作

### 7.1 选择 capability

`SelectJrpgFirstLoopCapabilities(...)` 只读取：

- 当前用户 message。
- 当前 regeneration guidance。
- 经 `JrpgRouteSemantics.ExtractPrototypeContractIntentText(...)` 提取的合同意图。

它不读取：

- 历史 prototype summary。
- planning summary。
- draft summary。
- prototype state excerpt。
- field coverage missing reason。
- 完整 contract JSON。
- route profile metadata。

### 7.2 构建 scaffold

`JrpgFirstLoopCapabilities` 定义每个 capability 的：

- `Id`
- `Title`
- `DescriptionTemplate`
- `AcceptanceTemplate`

scaffold 以稳定顺序生成。LLM 可以润色 description 和 acceptance hint，但必须保留标准标题和必要合同词。

### 7.3 本地 guard

`FindRpgPlanContractIssue(...)` 在 LLM evaluation 前运行。它负责拦截：

- 缺少 field navigation。
- 缺少 final first-loop acceptance。
- conflict/battle 只出现一半，没有拆成 entry 与 resolution。
- reward/growth 计划缺少 return-or-continue。
- 第一个 field navigation goal 混入 encounter、battle、reward、scene switching、package readiness 或 final acceptance。
- 合同明确要求的胜负/规则没有被命名。
- stale route state 或 stale selected capabilities。

LLM evaluation 只能在本地 guard 通过后作为二次判断。

## 8. Goal Acceptance 如何运作

`RpgGameTypeRouteStrategy.ResolveRpgRouteGoalTitle(...)` 先处理标准 JRPG 标题：

- opening context -> static objective/start acceptance。
- field navigation -> `MapEntryAcceptance` + `MoveOnMap`。
- conflict entry -> 默认 map entry；只有当前语义需要 battle 时才附加 battle/reward marker。
- battle/challenge resolution -> 只有需要 battle 时才启用 `BattleSceneAcceptance`。
- growth/reward/consequence -> 只有需要 reward 时才启用 `RewardFlowAcceptance`。
- return/continue -> map/continue proof，不默认 reward。
- final acceptance -> 通过 `ResolveFinalRequirements(...)` 条件决定 battle/reward。

`ResolveRpgGoalSemantic(...)` 处理非标准标题和 legacy RPG step 名称，但必须使用同样的语义门禁和 negation 规则。

最终验收的关键函数是 `ResolveFinalRequirements(...)`：

1. 如果当前有效 `selected_capabilities` 非空，以它为权威。
2. battle 只由 `conflict_entry` 或 `battle_or_challenge_resolution` 触发。
3. reward 只由 `growth_feedback` 触发。
4. 如果没有 selected capabilities，才回退到可信语义文本检测。

未来其他类型应该复制这个控制流，而不是复制 JRPG 的关键词。

## 9. 测试说明

这些测试不是只证明 JRPG 可用。它们定义了新增游戏类型必须继承的质量门：路由能被识别、计划不会过度生成、执行验收只检查选中能力、修复不会把旧模板能力重新带回来。


### `PrototypeRouteSkillPolicyTests`

验证 RPG 项目能解析到正确 profile、skill、contract、prompt block 和 route metadata。新增游戏类型时，必须有同类测试，证明项目不会走 generic 7-day route。

### `PrototypeIterationPlanServiceTests`

覆盖：

- 无 combat 语义时不选 battle capability。
- combat 请求会选 conflict/battle/reward/return。
- 历史 prototype summary 不污染选择。
- route profile metadata 不污染选择。
- negated combat/reward 被尊重。
- regeneration guidance 只在当前明确时影响选择。
- LLM 计划不保留 scaffold 标题时失败或回退。
- 本地 route guard 拒绝缺步、宽泛第一步、stale selected capabilities、stale analysis、缺少显式合同规则。
- selected capabilities 必须 session-scoped。

### `PrototypeIterationGoalServiceTests`

覆盖：

- 当前选中 battle capability 时缺失 BattleScene 会报错。
- 无 combat contract 的 final acceptance 不要求 BattleScene。
- template-only BattleScene 文案被忽略。
- 无 `session_id` 的 legacy iteration-plan state 被忽略。
- stale selected capabilities 被忽略。
- prototype metadata 里的 BattleScene/combat/reward 被忽略。
- 非战斗 challenge、failure、scene switching、contract alignment、asset/UI validation、story consequence、return/continue 不误触发 battle/reward。
- reward goal 缺少 reward contract 时有可解释原因。

### Repair / Needs-Fix / E2E

- `PrototypeQuickFixServiceTests` 验证 quick-fix 不会偏离当前 goal。
- `PrototypeNeedsFixRouteServiceTests` 验证 needs-fix 只围绕当前 step 和当前 ledger。
- `PrototypeRepairPlanServiceTests` 验证 repair-plan 不被旧上下文污染。
- `PhaseAPrototypeRouteE2ETests` 验证 hosted prototype route 可跑通。

## 10. 新增其他游戏类型的步骤

### Step 1: 定义 capability graph

先定义最小首轮能力图，区分 always-on 与 conditional capability。不要把该类型所有典型系统都塞进每个原型。

### Step 2: 创建语义 helper

例如 `DeckbuilderRouteSemantics`。应包含：

- 每个 conditional capability 的正向检测。
- negation 检测。
- 关键词 normalization，避免 `itemized` 误触发 item reward、`explore` 误触发 exp。
- 只提取项目合同意图，不读取模板 metadata。

### Step 3: 添加 type kit 和 skill

新增或更新：

- `docs/prototype-type-kits/<type>.md`
- `.agents/skills/prototype-<type>-godot-zh/SKILL.md`
- `.agents/skills/prototype-<type>-godot-zh/references/<type>-prototype-contract.md`

### Step 4: 注册 route profile

在 `GameTypeRouteEngine.cs` 增加 profile，并扩展 resolve 逻辑。profile 应定义：

- `GameTypeId`
- `ProfileId`
- `RouteSetId`
- `PromptProtocolId`
- `RouteSkill`
- planner/evaluator/executor/needs-fix/final acceptance ids

### Step 5: 添加 strategy

新增或注册 `IGameTypeRouteStrategy`，说明：

- 是否需要 model-backed iteration planning。
- 是否使用 specialized planning/evaluation。
- 标准 goal title 如何映射 acceptance contract。
- semantic fallback 如何映射 acceptance contract。
- 哪些 marker 和 acceptance flag 是条件启用。

不要把类型检测散落到 `PrototypeGoalAcceptanceValidator`。

### Step 6: 添加 planning scaffold 和 guard

在 `PrototypeIterationPlanService` 中添加该类型的：

- capability selection。
- scaffold goals。
- model refinement prompt。
- refined plan parser。
- route guard。
- current route-context reader。

### Step 7: 添加测试

最小测试集：

- profile/skill resolution。
- 正向和负向 capability selection。
- metadata 和历史 summary 不污染。
- selected capabilities session-scoped。
- plan guard 拒绝缺失能力和宽泛第一步。
- final acceptance 使用 selected capabilities。
- 每个 capability 映射正确 acceptance markers。
- repair/needs-fix 保持当前 goal。
- 一个 E2E route test。

### Step 8: 验证

```powershell
dotnet test PhaseA.Platform.Tests\PhaseA.Platform.Tests.csproj --filter "FullyQualifiedName~PrototypeRouteSkillPolicyTests|FullyQualifiedName~PrototypeIterationPlanServiceTests|FullyQualifiedName~PrototypeIterationGoalServiceTests|FullyQualifiedName~PrototypeQuickFixServiceTests|FullyQualifiedName~PrototypeNeedsFixRouteServiceTests|FullyQualifiedName~PrototypeRepairPlanServiceTests|FullyQualifiedName~PhaseAPrototypeRouteE2ETests" --logger "console;verbosity=minimal"
dotnet test PhaseA.Platform.Tests\PhaseA.Platform.Tests.csproj --logger "console;verbosity=minimal"
git diff --check
```

### Step 9: 做跨文件一致性审查

新增类型完成后，至少审查这些文件是否说的是同一套规则：

| 审查对象 | 必须一致的内容 |
| --- | --- |
| type kit | capability id、默认/条件能力、最小验收。 |
| skill `SKILL.md` | 执行 agent 的场景、素材、测试和边界规则。 |
| skill contract | 可机器检查或可人工复核的合同字段。 |
| route profile | `GameTypeId`、skill 名、route ids、prompt protocol。 |
| route strategy | goal title 到 acceptance contract 的映射。 |
| iteration plan service | capability selection、scaffold、guard、session scoped route state。 |
| tests | 正例、负例、模板污染、stale state、最终验收。 |
| profile guide / index | 入口文档指向新类型资料，且不保留旧类型固定流程描述。 |

如果这些文件中任意一个仍写着“默认创建某个条件系统”，而 capability graph 说它是 conditional，就应当先修文档或代码再合并。


## 11. 未来类型设计检查表

### 11.1 新类型设计简表

在写代码前，先为新类型填一份简表。它应该能直接转换成 type kit、skill contract、route strategy 和测试用例。

| 字段 | 填写要求 |
| --- | --- |
| `game_type_id` | 稳定小写 id，例如 `deckbuilder`、`slg`、`survivorslike`。 |
| `profile_id` | 带版本的 executable route profile，例如 `godot-deckbuilder-v1`。 |
| 核心首轮承诺 | 一句话说明最小可玩闭环，不包含未请求的可选系统。 |
| Always-on capabilities | 每个原型都必须验收的最小能力。 |
| Conditional capabilities | 只在请求、合同或 current selected capabilities 明确选择时验收的能力。 |
| 可信输入 | 当前用户 message、当前 regeneration guidance、经 helper 提取的合同意图。 |
| 不可信输入 | 模板示例、game name、game type、smoke scene、历史 summary、旧 route state。 |
| 语义否定 | 能取消 conditional capability 的短语，例如“不需要战斗”“无商店”“只做基础移动”。 |
| 第一目标边界 | 第一个 goal 只能证明什么，不能偷做哪些后续能力。 |
| Final acceptance 最小集 | 只选 always-on 时验收什么。 |
| Final acceptance 满能力集 | 所有 conditional capability 都被选择时额外验收什么。 |
| 文件/场景证据 | 每个 acceptance marker 对应哪些 Godot 文件、节点、脚本或测试证明。 |
| 失败时修复边界 | needs-fix / quick-fix 能修什么，不能从旧模板补什么。 |

### 11.2 新类型路由回归防线

新增 route 不应只靠 happy path 通过。至少要有这些反向防线：

| 风险 | 必要测试 |
| --- | --- |
| 识别到新类型后仍走 generic route。 | profile/skill resolution 测试断言 `ProfileId`、`RouteSkill`、prompt block。 |
| 模板示例激活未请求系统。 | metadata、design template、history summary 中放入可选系统词，断言 capability 不被选中。 |
| 否定语义失效。 | 请求写明“不需要 X”，断言 X 的 capability、acceptance marker、repair focus 都不出现。 |
| stale route state 污染当前 session。 | 写入不匹配 `session_id` 的 selected capabilities，断言 final acceptance 忽略它。 |
| LLM refinement 删除 scaffold 合同词。 | 模拟模型返回缺少标准标题或关键验收词，断言回退或失败。 |
| 第一个 goal 过宽。 | 第一目标混入后续系统，断言本地 guard 拒绝。 |
| repair/needs-fix 重新引入旧模板系统。 | 最新 failure 不要求该系统时，断言 quick-fix prompt 和 repair plan 不补它。 |

## 12. 设计评审问题清单

创建新类型前必须回答：

- always-on first-loop capabilities 是什么？
- conditional capabilities 是什么？
- 哪些用户/合同词会选择每个 conditional capability？
- 哪些 negation 会取消它？
- 哪些 route state 字段可信？
- 如何强制 current session？
- 哪些字段禁止创建 runtime obligation？
- final acceptance 在最小能力集下验收什么？
- final acceptance 在全能力集下验收什么？
- stale route state 如何 fail safely？
- 哪些测试证明模板示例不会强制未请求系统？

### 12.1 P0/P1/P2 文档与实现评审口径

| 等级 | 判定标准 | 例子 |
| --- | --- | --- |
| P0 | 会让已识别游戏类型走错公开入口、绕过共享 LLM/Codex 入口、破坏现有 JRPG 路由，或让最终验收系统性误判。 | 新类型没有 profile 测试却被标成 executable route；final acceptance 无条件要求所有 conditional capability。 |
| P1 | 会让未来 agent 按文档实现出错误路由，或让当前能力边界和文档冲突。 | 文档写 BattleScene 默认存在，但代码规定无战斗语义不得创建；skill contract 与 strategy 的 capability id 不一致。 |
| P2 | 不阻断实现，但会降低复用速度、审查效率或排障效率。 | 缺少复制对照表、测试失败解释、常见误触发词、示例 capability graph。 |

评审时先找 P0/P1，再处理 P2。不要因为发现新的 P2 就推翻已通过的 P0/P1 结论；P2 应该聚合处理，避免反复改动同一段路由规则。


## 13. 常见错误

- 复制 JRPG 标题到其他类型，而不是定义新类型自己的能力图。
- 把 genre guide 当成 executable route requirement。
- 让 `game_name`、`game_type`、`smoke_scene` 激活 runtime system。
- capability selection 读取历史 summary。
- route state 不校验 `session_id`。
- final acceptance 永远要求所有能力。
- 第一个 goal 混入多个能力。
- 接受删除 scaffold 关键合同词的 LLM refinement。
- 为修 false positive 而削弱所有验收，而不是收窄可信输入。

## 14. 卡牌构筑类型的参考起点

如果下一个类型是卡牌构筑，建议用 JRPG 框架，但定义独立 capability graph：

| Capability | 是否默认 | 说明 |
| --- | --- | --- |
| `run_start` | Always | 开始一局，显示 deck/hand/discard/draw pile 上下文。 |
| `hand_and_energy_readability` | Always | 手牌、费用/能量、可打出状态、目标/意图清晰。 |
| `turn_resolution` | Always | 打出卡牌、结算效果、敌方或环境响应、结束回合。 |
| `route_choice` | Conditional but common | 战斗后或节点间路线选择。 |
| `event_shop_elite_node` | Conditional but common | 事件、商店、精英节点；请求没有时不要强制。 |
| `deck_reward` | Conditional | 卡牌奖励、跳过/拿取、牌组更新。 |
| `deck_editing` | Conditional | 删除、升级、转换、牌库操作。 |
| `relic_or_modifier` | Conditional | 遗物、被动、局内 modifier。 |
| `final_run_acceptance` | Always | 选中 capability 端到端可玩。 |

卡牌构筑 route 的条件规则可以类比 JRPG 的 BattleScene/Reward：

| 系统 | 何时激活 | 不应由什么激活 |
| --- | --- | --- |
| 路线选择 | 请求、合同或当前 selected capability 明确要求地图、路径、节点选择、分支路线。 | 模板提到 Slay the Spire 或 roguelike deckbuilder。 |
| 事件/商店/精英节点 | 请求、合同或 selected capability 明确要求 event、shop、elite、special node。 | 只要求一场卡牌战斗、手牌/费用验证、基础回合结算。 |
| 卡牌奖励 | 请求、合同或 selected capability 明确要求战后奖励、选牌、跳过、牌组更新。 | 只要求路线选择或商店存在。 |
| 牌组编辑 | 请求、合同或 selected capability 明确要求删除、升级、转换、构筑调整。 | 只因为存在 deck/hand/discard UI。 |
| 遗物/modifier | 请求、合同或 selected capability 明确要求 relic、artifact、passive、modifier。 | 只因为参考游戏有遗物系统。 |


不要因为模板提到杀戮尖塔/怪物火车/邪恶冥刻，就默认要求路线选择、商店、事件、精英、遗物、奖励全部出现。它们应该由当前 request、contract 或 current selected capabilities 激活。

## 15. 未来 agent 交接摘要模板

当一个新类型 route 做完但还没有提交时，交接摘要至少包含：

```text
Game type:
Profile id:
Route skill:
Capability graph:
Always-on:
Conditional:
Trusted inputs:
Ignored inputs:
Final acceptance rule:
Tests run:
Known residual risks:
Files changed:
```

这份摘要的目的不是替代文档，而是让下一位 agent 能快速判断：当前工作是否已经覆盖 profile、strategy、plan、acceptance、repair、tests 和索引入口。

