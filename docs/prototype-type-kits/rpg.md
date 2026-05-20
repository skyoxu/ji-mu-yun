# RPG Prototype Type Kit

## Router Binding

- Default repo-local implementation skill: `.agents/skills/prototype-rpg-godot-zh/SKILL.md`
- Default contract reference: `.agents/skills/prototype-rpg-godot-zh/references/rpg-prototype-contract.md`
- Default template manifest: `docs/prototype-type-kits/default-rpg-template.manifest.json`
- The top-level prototype router must attach this metadata when `game_type` is `rpg`.
- Store these paths as repo-relative metadata only. Do not hardcode absolute paths or assume the Godot project sits directly under the repo root.

## 用途

本文件用于 RPG 类型的 prototype lane。它不是完整 GDD，也不处理数值平衡、长期成长、装备经济、任务系统或边界情况。它只定义 1-2 个场景内可以完成的最小核心游玩闭环，让玩家能从地图移动进入战斗，并在胜利或失败后得到明确反馈。

## 参考项目依据

本版 RPG kit 吸收了 `C:/buildgame/nightday/godotgame` 中 `He-is-Coming` prototype 的实践结果：

- 地图与战斗拆成 `MapScene` / `BattleScene` 两个主场景根，但仍由一个 prototype loop 统一调度。
- 地图上有网格移动、遇敌进度、宝箱奖励和障碍物，但不扩展到完整大地图。
- 战斗可以是回合推进感的自动战斗，不必一定要从第一版就做指令按钮。
- 战后肉鸽三选一奖励可作为 RPG prototype 的可选增强，用于验证流派感，但不要扩展成完整成长系统。
- UI 需要明确告诉玩家当前场景、HP、遇敌或战斗状态、战斗日志和奖励/结算结果。

## 适用范围

- 游戏类型：`rpg`
- Prototype 目标：验证探索 -> 遇敌 -> 战斗 -> 结算/回到地图的核心体验是否成立
- 推荐场景数量：2 个
- 推荐实现粒度：可玩优先，表现和数值从简


## ???????

RPG ???????????????????????????????? type kit?

### ????

- `MapScene`????????????????????/????????????????
- `BattleScene`??????????/???????????????????????????
- `DefaultRpgPrototype` ???????????????????????????????????????

### ??????

??????RPG ?????????????????????? repo-relative??????? slug ???/???

- ?????`Game.Godot/Prototypes/DefaultRpgTemplate/Assets/Map/`
- ?????`Game.Godot/Prototypes/DefaultRpgTemplate/Assets/Player/`
- ?????`Game.Godot/Prototypes/DefaultRpgTemplate/Assets/Enemy/`

### ????

- `prototype` ??? RPG ?????????????
- `iteration-plan` ????????????/UI ?????? step?
- `execute-next-goal` ????? step????? README ? route state ????? RPG ????
- `needs-fix` ???? step?????? step ?????

### ??????

- `MapScene` ??????????????
- `BattleScene` ???????????????? UI ???
- ?????????????/?????????????????
- ???????????????????? + ??????????????????????

## Gameplay Flow / GDD Route

### 默认最小游玩动线

1. 玩家进入地图场景。
2. 玩家使用 WASD 在地图上上下左右移动。
3. 地图中至少存在一种战斗触发方式：随机遇怪、地图撞怪，或二者都支持。
4. 触发战斗后，游戏切换到 RPG 战斗场景。
5. 战斗可采用回合制指令或回合推进感的自动战斗。
6. 玩家行动会降低怪物 HP；怪物行动会降低玩家 HP。
7. 怪物 HP 降至 0 时，触发胜利结算。
8. 胜利后可回到地图，也可在结算后结束 prototype，由本次目标决定。
9. 玩家 HP 降至 0 时，触发 Game Over 或 Retry。
10. 如果加入肉鸽奖励，奖励应放在战后或宝箱触发后，不要阻塞最小战斗闭环。

### 最小闭环判定

`进入地图 -> 移动 -> 遇敌 -> 进入战斗 -> 攻击/自动行动 -> HP 变化 -> 胜利或失败 -> 结算反馈`

### 推荐默认假设

- 遇敌方式：地图撞怪更直观；随机遇怪更接近传统 RPG。如果时间允许，二者都可支持。
- 战斗方式：默认回合制指令；如果想验证被动流派或肉鸽构筑，可用自动战斗。
- 地图规模：一个小房间、一条短路径或 12x12 网格即可。
- 怪物数量：最小版 1 个；增强版可用小怪 -> 精英 -> boss 短流程。
- 属性：最小版只需 HP / Attack；增强版可加 Defense / Crit / Passive。

## Prototype Scene UI

### Map Scene UI

- Player HP：显示玩家当前 HP。
- Input Hint：显示 `WASD Move` 或中文操作提示。
- Quest / Goal Hint：显示极简目标，如「找到敌人」或「击败 boss」。
- Encounter Hint / Progress：显示遇敌状态、遇敌概率或接近敌人提示。
- Optional Reward Hint：如果有肉鸽奖励或宝箱，显示奖励触发信息。
- Optional Debug Text：可显示坐标、当前格子、遇敌状态，只用于 prototype 调试。

### Battle Scene UI

- Player HP / Enemy HP：必须可见。
- Actor Presentation：至少有玩家和敌人的代替形象或 sprite。
- Command Panel：如果是指令战斗，至少包含 `Attack`。
- Auto Battle State：如果是自动战斗，显示当前回合、战斗演算状态和关键被动触发。
- Battle Log：显示最近行动反馈。
- Result Panel：显示 Victory / Defeat / Game Over。
- Continue / Retry / End Prototype：结算后至少有一个明确下一步操作。

## 两轮确认问题

### Round 1：Gameplay Flow / GDD Route

1. 使用随机遇怪、地图撞怪，还是二者都支持？
2. 战斗是回合制指令，还是即时碰撞/自动战斗？
3. 胜利后回到地图，还是进入结算后结束 prototype？
4. 玩家失败后是直接 Game Over、Retry 当前战斗，还是回到地图？
5. 是否需要战后奖励或肉鸽三选一来验证流派感？

### Round 2：Prototype Scene UI

1. 战斗场景需要哪些 UI：HP、指令按钮、战斗日志、技能栏？
2. 地图场景需要哪些 UI：HP、任务提示、小地图、遇怪提示？
3. 失败后是直接 Game Over，还是允许 Retry？
4. 结算 UI 需要哪些按钮：Continue、Retry、Back to Map、End Prototype？
5. 是否需要保留调试 UI 帮助快速验证 prototype？

## TDD Consumption Contract

Prototype TDD 应优先消费 `docs/prototypes/<slug>.prototype.json`，其次才从 Markdown 中回退解析。

- 必须读取 `prototype_core.game_feature`、`prototype_core.core_gameplay_loop`、`prototype_core.win_fail_conditions`。
- 必须读取 `prototype_type_kit.gameplay_flow` 和 `prototype_type_kit.prototype_scene_ui`。
- 生成/验证的场景应至少对应 Map Scene 和 Battle Scene 中的必要元素。
- 不得把本 kit 解释为正式 Chapter6 证据或完整 GDD 需求。

## 不进入本 Prototype Kit 的内容

- 等级成长曲线
- 经验值和升级公式
- 装备、背包、商店
- 多角色队伍
- 多怪物编队
- 技能树
- 任务系统
- 长期存档
- 完整剧情演出
- 完整美术 UI 规范
- 边界条件和异常输入处理
