# 原型：<slug>

- 状态：active | promoted | archived | discarded
- 负责人：<name or agent>
- 日期：<YYYY-MM-DD>
- 关联正式任务 id：none yet | <id list>

## 假设
- <你想验证什么>

## 核心玩家幻想
- <玩家在第一分钟内应该感受到什么，或看懂什么>

## 最小可玩循环
- <玩家必须能够完整走通的最小闭环>

## 游戏特色
- <这个 prototype 最有辨识度的玩法特色>

## 核心游戏循环
- <重复发生的核心游戏循环>

## 胜利 / 失败条件
- <玩家如何获胜，如何失败>

## 游戏类型细节
- Game Type: <docs/game-type-guides 中的 canonical id，例如 rpg>
- Guide Path: docs/game-type-guides/<game-type>.md
- <Step07-lite 原型 1>：<玩家对该小节的回答>
- <Step07-lite 原型 2>：<玩家对该小节的回答>
- <Step07-lite 原型 3>：<玩家对该小节的回答>

## 实现 Skill
- Name: <仓内 prototype skill 名称，例如 prototype-rpg-godot-zh>
- Path: .agents/skills/<skill-name>/SKILL.md
- Contract Path: .agents/skills/<skill-name>/references/<contract-file>.md

## 原型类型模板
- Game Type: <docs/prototype-type-kits 中的 canonical id，例如 rpg>
- Kit Path: docs/prototype-type-kits/<game-type>.md
- Manifest Path: docs/prototype-type-kits/default-rpg-template.manifest.json

### Gameplay Flow / GDD Route
- 使用随机遇怪、地图撞怪，还是二者都支持？ <player answer>
- 战斗是回合制指令，还是即时碰撞/自动战斗？ <player answer>
- 胜利后回到地图，还是进入结算后结束 prototype？ <player answer>

### Prototype Scene UI
- 战斗场景需要哪些 UI：HP、指令按钮、战斗日志、技能栏？ <player answer>
- 地图场景需要哪些 UI：HP、任务提示、小地图、遇怪提示？ <player answer>
- 失败后是直接 Game Over，还是允许 Retry？ <player answer>


## 原型组件映射
- 风格：使用 Godot 节点/场景组件，不使用 ECS。
- 根节点：PrototypeRoot / <SlugPascalCase>Prototype 只负责编排生命周期、输入、场景切换和状态交接。
- 状态/数据：<SlugPascalCase>State 或 Scripts/Data/* 保存临时状态和调参数据。
- 玩法系统：Scripts/Systems/* 保存玩法计算，例如战斗、奖励、遭遇、移动或谜题规则。
- 视图组件：
  - HudView：<HUD / 状态反馈槽位>
  - MapView：<地图 / 场景 / 世界表现槽位>
  - BattleView：<战斗 / 挑战表现槽位>
  - RewardView：<奖励 / 结算选择槽位>
  - ActorView：<玩家 / 敌人 / NPC 表现槽位>
  - LogView：<战斗日志 / 任务日志 / 状态文字槽位>
- 绑定规则：优先使用 exported NodePath 字段或集中绑定方法，避免在多个玩法方法中重复长 GetNode 路径。
- 通信规则：同一 prototype 内优先直接调用、Godot signal 或 C# event；EventBus 只保留给全局通知或未来 promote 候选。

## 范围
- In:
  - <包含内容>
- Out:
  - <排除内容>

## 成功标准
- <可观察的成功判断 1>
- <可观察的成功判断 2>

## Promote 信号
- <什么证据说明它值得进入正式任务>

## Archive 信号
- <什么证据说明它有信号，但暂时不适合正式交付>

## Discard 信号
- <什么证据说明它应该停在 prototype 阶段>

## 证据
- Code paths:
  - <path>
- Logs / media / notes:
  - <path or note>

## 结论
- discard | archive | promote

## 下一步
- <如果 promote，下一步进入什么正式任务 / overlay / test>
