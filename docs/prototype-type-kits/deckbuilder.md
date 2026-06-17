# Deckbuilder Prototype Type Kit

## Router Binding

- Default repo-local implementation lane: `.agents/skills/prototype-deckbuilder-godot-zh/SKILL.md`
- Contract: `.agents/skills/prototype-deckbuilder-godot-zh/references/deckbuilder-prototype-contract.md`
- Primary genre guide reference: `docs/game-type-guides/card-game.md`
- Default route framework reference: `docs/workflows/game-type-route-framework-guide.md`
- The top-level prototype router attaches this metadata when `game_type` is `deckbuilder`.
- If an upstream taxonomy still says `card-game`, only map it here when the requested goal is a deckbuilder-first-loop prototype, not a collectible card game product.
- Store these paths as repo-relative metadata only. Do not hardcode absolute paths or assume the Godot project sits directly under the repo root.

## 用途

本文件用于卡牌构筑 / Deckbuilder 类型的 prototype lane。它不是完整卡牌产品规范，也不处理完整卡池、收藏经济、赛季系统、天梯匹配、构筑元数据同步或长期数值平衡。它定义一局内最小可玩闭环，但不把所有 deckbuilder 项目固定成“开局抽牌 -> 出牌 -> 奖励 -> 路线选择”的单一脚本。

## 参考项目依据

本版 deckbuilder kit 吸收了 `docs/game-type-guides/card-game.md` 中关于卡牌、牌组、资源、回合结构的通用术语，但首轮验收只保留最小可玩循环，不默认引入收藏、经济、商店、遗物、章节推进或完整地图。

## 适用范围

- 游戏类型：`deckbuilder`
- 兼容分类：`card-game`（仅作为上游分类标签，不作为自动激活全部卡牌系统的理由）
- Prototype 目标：验证一局 deckbuilder first loop 是否成立，例如开局语境、初始牌组可读性、资源与回合规则、出牌结算、牌库循环、战斗结算、奖励/选牌和牌组变化反馈。
- 推荐场景数量：2 个
- 推荐实现粒度：可玩优先，视觉和长期成长从简

## Deckbuilder 路由约束

Deckbuilder 类型项目必须在 prototype、iteration-plan、execute-next-goal 和 needs-fix 四条流水线中继承同一个 type kit。

### 场景职责

- `RunScene`：负责局内上下文、牌组/手牌/弃牌堆/抽牌堆信息、资源与当前目标展示。
- `BattleScene`：负责出牌、资源消耗、敌方压力、结算反馈、回合推进和战斗结果。
- `RewardScene`：负责战后选牌、跳过、抽牌堆/牌组变化反馈。
- `RouteScene`：仅在请求明确需要路线、事件、商店、精英或分支节点时启用；不是 deckbuilder 默认强制项。

### 四条流水线继承规则

- `prototype` 负责创建 deckbuilder 原型切入口、项目级 route state 和首轮可玩场景。
- `iteration-plan` 必须把开局语境、初始牌组可读性、资源与回合规则、出牌结算、战斗结算、奖励和牌组变化拆成可执行 step。
- `execute-next-goal` 必须读取当前 step、项目 README 和 route state，只推进当前 deckbuilder step。
- `needs-fix` 必须只读取当前 step 的 needs-fix 产物；没有 needs-fix 产物时，再读取当前 step 的 execute-next-goal 产物和 prototype 产物。

### Capability-Driven Minimum Acceptance

Deckbuilder prototypes use a first-loop capability profile instead of a fixed card-game script. The profile defines these capabilities:

- `run_context`: 玩家能理解自己在进行一局 run，不是孤立战斗。
- `starter_deck_readability`: 玩家能理解初始牌组与当前工具箱。
- `resource_and_turn_rules`: 资源和回合约束可见且可执行。
- `enemy_intent_or_pressure`: 敌方意图、压力源或倒计时可见。
- `card_play_resolution`: 至少能打出一张牌并看到即时反馈。
- `deck_cycle_and_hand_flow`: 抽牌、弃牌、洗牌或消耗中的至少一个循环可见。
- `combat_resolution`: 战斗可以胜利或失败，并有明确结算状态。
- `reward_or_card_draft`: 胜利后出现选牌或奖励反馈，并能影响后续构筑。
- `deck_mutation_feedback`: 牌组变化、升级、删牌或规则变化可见。
- `map_or_route_choice`: 仅当项目请求路线/节点/事件/商店/精英时启用。
- `final_deckbuilder_first_loop_acceptance`: 首轮闭环从开局到结算都能被验证；只有选择 `map_or_route_choice` 时才要求路线/节点闭环。

#### 默认能力图

| 序号 | id | 模块名 | 默认性 | 设计目的 | 通过标准 |
| --- | --- | --- | --- | --- | --- |
| 1 | `run_context` | 开局目标与路线语境 | Always | 让玩家知道这是一局 run，不是孤立战斗 | 玩家能看到当前角色/阵营、短期目标、失败条件或前进方向 |
| 2 | `starter_deck_readability` | 初始牌组可读性 | Always | 验证玩家能理解自己的初始工具箱 | 手牌、抽牌堆、弃牌堆或牌组列表至少一种可见；卡牌名称、费用、效果可读 |
| 3 | `resource_and_turn_rules` | 费用与回合规则 | Always | 验证出牌约束是否成立 | 能看到能量/费用/行动点/蜡烛等资源；出牌会正确消耗资源并结束回合 |
| 4 | `enemy_intent_or_pressure` | 敌方意图或压力源 | Always | 卡牌构筑战斗必须让玩家有为什么这么打的理由 | 敌人攻击、增益、倒计时、轨道压力或叙事威胁可见 |
| 5 | `card_play_resolution` | 出牌结算反馈 | Always | 验证最小战斗交互手感，避免原型只剩点攻击牌 | 玩家能打出至少一张牌，并看到伤害、防御、召唤、献祭、抽牌等即时反馈 |
| 6 | `deck_cycle_and_hand_flow` | 手牌流转与牌库循环 | Always | 构筑游戏的核心是牌在系统里循环 | 抽牌、弃牌、洗牌或消耗至少一个流程可见且不会卡死 |
| 7 | `combat_resolution` | 战斗胜负结算 | Always | 完成第一场冲突 | 战斗可以胜利或失败，并有明确结算状态 |
| 8 | `reward_or_card_draft` | 战后选牌/奖励 | Always | 从卡牌战斗进入卡牌构筑 | 胜利后出现至少2-3个奖励选择，玩家能选择并影响后续牌组 |
| 9 | `deck_mutation_feedback` | 牌组变化反馈 | Always | 让玩家感到构筑选择真的生效 | 选牌、删牌、升级、获得遗物/神器/图腾后，牌组或规则状态可见变化 |
| 10 | `map_or_route_choice` | 路线选择、事件/商店/精英节点 | Conditional | 验证 run 的下一步选择，而不是把所有 deckbuilder 都强制做成地图游戏 | 玩家能在至少 2 个后续节点/路线/事件中选择，或能明确进入下一节点；若项目不是路线型卡牌构筑，可降级为“继续下一战/下一事件” |
| 11 | `final_deckbuilder_first_loop_acceptance` | 最终验收 | Always | 验证 run loop，而不是单场 demo | 开局 -> 战斗 -> 出牌 -> 结算 -> 奖励/改牌 -> 继续下一战、下一事件或结束 prototype；若选择了 `map_or_route_choice`，则必须额外证明路线/节点选择能回到路线或进入下一节点 |

## Gameplay Flow / GDD Route

### 默认最小游玩动线

1. 玩家进入 run 开局界面。
2. 玩家能看到初始牌组、手牌区、抽牌堆或弃牌堆中的至少一种。
3. 资源与回合规则清晰可见，玩家知道自己每回合能做什么。
4. 玩家打出至少一张牌并看到即时结算。
5. 敌方压力、意图或倒计时对玩家可见。
6. 牌库和手牌发生循环，不能只停留在单次点击反馈。
7. 战斗结束后出现胜负结算。
8. 若项目请求奖励或构筑变化，奖励/选牌/删牌/升级必须能影响后续牌组。
9. 若项目请求路线或节点选择，玩家可以进入下一节点或下一战；否则必须能继续下一战、下一事件或明确结束 prototype。
10. 原型结束时必须能证明首轮闭环已成立。

### 最小闭环判定

`开局语境 -> 牌组可读 -> 资源与回合 -> 出牌结算 -> 敌方压力 -> 牌库循环 -> 胜负结算 -> 奖励/构筑反馈 -> 继续或结束 -> 最终验收`；选择 `map_or_route_choice` 时追加 `路线/节点选择 -> 回到路线或进入下一节点`。

### 推荐默认假设

- 资源：默认使用能量/费用类资源，具体名称由项目表单决定。
- 战斗方式：默认回合制卡牌战斗。
- 地图/路线：默认不强制；只有项目明确要求时才启用。
- 奖励：默认保留战后选牌或奖励反馈。
- 牌组编辑：默认只保留最小的删牌/升级或等价反馈，不扩展完整构筑经济。

## Prototype Scene UI

### Run Scene UI

- Run Context：显示当前 run 的目标、失败条件或前进方向。
- Deck/Hand/Discard：至少一种牌组可读信息必须可见。
- Resource Hint：显示当前回合可用资源。

### Battle Scene UI

- Player/Enemy State：玩家与敌方的关键状态必须可见。
- Card Row：卡牌名称、费用、效果可读。
- Intent / Pressure：敌方意图或压力源可见。
- Resolution Feedback：出牌后有即时反馈。
- Battle Log：显示最近行动反馈。
- Result Panel：显示 Victory / Defeat / End。

### Reward Scene UI

- Reward Choices：至少 2-3 个奖励或选牌项。
- Skip / Accept：玩家能跳过或选择。
- Deck Mutation Preview：选牌后能看见牌组变化。

### Route Scene UI

- Route Choice：只有项目明确请求节点/分支时显示。
- Node Feedback：事件、商店、精英或下一节点的反馈必须明确。

## 两轮确认问题

### Round 1：Gameplay Flow / GDD Route

1. 你要的是纯战斗式 deckbuilder，还是带路线节点的 roguelike deckbuilder？
2. 资源系统用能量、费用、行动点，还是项目自定义资源？
3. 战斗结束后必须给奖励选牌吗，还是只要胜负结算？
4. 是否需要路线、事件、商店或精英节点？

### Round 2：UI / Feedback / Scope

1. 手牌、弃牌堆、抽牌堆、牌组列表里哪些必须可见？
2. 敌方意图需要展示到什么粒度？
3. 牌组变化要展示删除、升级、生成，还是只要奖励反馈？
4. 最小闭环结束后是继续下一战，还是直接结束 prototype？
