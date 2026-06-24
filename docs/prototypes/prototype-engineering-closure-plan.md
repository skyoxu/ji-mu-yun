# Prototype 工程闭环改造核对清单

本文档用于记录即将进行的 prototype 阶段改造工作和完成标准。改造完成后，按本文逐项核对。

## 适用范围

只覆盖 Phase A prototype 阶段：

- 原型骨架创建。
- GDD 到模块 spec 的生成和补全。
- 完成游戏模块。
- 模块反馈修复。
- 轻量原型验收。
- 项目素材库的素材下载、导入、替换和验证。

不覆盖 Chapter 3-7 相关功能。

## 严重程度定义

用于本轮改造后的自检和验收：

- P0：会导致 prototype 主流程不可用、工程无法构建、无法打开项目、白名单下载边界失效，或错误地把失败结果标记为成功。
- P1：会导致机器闭环不可信，例如缺少 evidence、smoke 未运行、自动修复未接入、M1/模块状态不同步、资产替换未验证碰撞。
- P2：不会阻断主流程，但会降低可维护性、可诊断性或前台体验，例如状态文案不统一、证据展示不够清楚、截图检查未覆盖所有模块。

## 文件位置约定

除本文档自身外，本文提到的 `docs/prototype/STRUCTURE.md`、`docs/prototype/MEMORY.md`、`docs/prototype/ASSETS.md`、模块 smoke、Godot scene 和 evidence，默认都位于生成出来的游戏项目工作区内。

Phase A 平台仓的 `docs/prototypes/` 只保存平台侧流程文档、历史记录和改造计划，不直接充当某个用户游戏项目的资产清单或工程记忆。

## 改造目标

把 prototype 阶段升级为可机器闭环的流程：

```text
GDD/spec -> 代码和场景实现 -> build/import/headless/smoke/capture -> evidence -> 自动修复 -> 用户确认模块完成
```

工程系统应能自行判断“当前模块是否达到可运行、可加载、可验证”的事实状态。人类只负责最终试玩体验和主观反馈，不承担工程事实检查。

## 非目标

以下内容不作为本次机器闭环验收条件：

- 画面是否足够好看。
- 手感是否舒服。
- 是否完全像参考游戏。
- 视频是否有演出感。
- 玩家是否觉得好玩。
- 最终美术精修质量。
- 主观 UI/UX 品质评分。

这些可以作为用户反馈或后续人工验收内容，但不能阻塞机器闭环的完成判断。

## GDD 和模块 Spec 输出契约

GDD 创建和补全路由必须产出可被模块执行 route 消费的模块规格，而不是只产出人类可读大纲。

完成标准：

- GDD 必须包含模块列表，每个模块有稳定 `moduleId`，例如 `M1`、`M2`。
- 每个模块必须包含目标、玩家可验证体验、实现范围、输入/操作、场景或 UI 需求、机器验收点。
- 每个模块 spec 必须能独立指导一次模块执行 run。
- 如果 GDD 压缩或扩展模块数量，模块执行页必须以实际 spec 列表为准，不硬编码 M1-M10。
- 补全所有大纲后，必须补全每个模块的具体 spec、轻量 UI/UX 指导和机器验收点。
- 快速补全单个大纲时，只补全当前模块 spec，不重写其他模块。
- 模块 spec 发生变更时，后端模块状态必须保留已完成模块的完成事实，不得重置用户已确认的模块，除非用户明确重新生成项目。

## 必须新增或维护的工程文件

### STRUCTURE.md

每个 prototype 项目需要维护：

```text
docs/prototype/STRUCTURE.md
```

该文件记录真实工程结构，而不是重新描述 GDD。

必须包含：

- Godot 版本和 C#/.NET 版本。
- 主场景路径。
- 当前 prototype 场景路径。
- 每个模块新增或修改的 scene。
- 每个 script 的路径、挂载 node、继承类型。
- input actions。
- collision layers。
- autoload。
- runtime resource paths。
- 当前模块对应的关键文件。

建议最小结构：

```text
# STRUCTURE
- engine: Godot 4.5.1 mono
- dotnet: <version>
- main_scene: res://...
- prototype_scene: res://...
- modules:
  - id: M1
    scenes: [res://...]
    scripts: [res://...]
    tests: [res://...]
- inputs: [move_left, move_right, attack, dodge]
- collision_layers:
  - layer: 1
    name: player
- autoloads: []
- runtime_resources: []
```

完成标准：

- 记录的 scene path 必须存在。
- 记录的 script path 必须存在。
- input action 必须存在于 `project.godot`。
- 主场景必须能加载 prototype scene。
- 模块执行成功后必须更新。

### MEMORY.md

每个 prototype 项目需要维护：

```text
docs/prototype/MEMORY.md
```

该文件只记录工程事实和执行发现，不写主观评价。

必须包含：

- 当前项目维度：2D 或 3D。
- 当前使用的物理方案。
- 已确认的主场景和 prototype 场景。
- 已确认的输入映射。
- 已知 Godot/C# 报错和修复方式。
- 当前模块已完成的真实文件。
- 下一个模块不应覆盖的稳定文件或场景。

建议最小结构：

```text
# MEMORY
- dimension: 2D|3D
- physics: CharacterBody2D|CharacterBody3D|RigidBody...
- stable_scenes: []
- stable_scripts: []
- confirmed_inputs: []
- known_errors:
  - signature: <error text>
    fix: <fix summary>
- module_facts:
  - id: M1
    completed_files: []
    protected_next: []
```

完成标准：

- 每次模块执行成功后追加或更新。
- 自动修复 run 发现新的工程约束时必须写入。
- 后续模块执行 prompt 必须读取。

### ASSETS.md

每个 prototype 项目需要维护：

```text
docs/prototype/ASSETS.md
```

该文件记录资产清单和资产验证状态。

每个资产必须记录：

- asset id。
- 来源：内置、白名单 URL、生成、占位。
- license 或授权说明。
- 原始文件路径。
- Godot `res://` 路径。
- 用途：player、enemy、room、prop、ui、vfx 等。
- 是否已 import。
- 是否已绑定到 scene。
- 是否需要碰撞。
- collision shape 类型和路径。
- 是否通过 asset smoke。
- 最近一次验证时间和验证 run id。

重要规则：

- `ASSETS.md` 不要求在 GDD 创建时完整生成。
- `ASSETS.md` 必须在“项目素材库”的素材下载 run 路由完成后更新。
- 素材下载 run 必须完成素材导入、替换和测试后，才允许把资产标记为 `verified`。
- 用户提交白名单外 URL 时，不得真实下载；只能提取关键词用于白名单内搜索或匹配。

项目素材库 run 的完成标准：

- URL 或关键词已按白名单规则处理。
- 下载文件存在于允许目录。
- Godot import 已执行。
- 替换目标 scene 或 resource 已更新。
- 如果资产参与移动、阻挡、命中、交互或导航，必须存在碰撞验证。
- 替换后运行 asset smoke。
- 通过后更新 `ASSETS.md`。
- 失败时记录失败原因，不得把资产标记为 `verified`。

资产下载安全契约：

- 只允许从配置白名单命中的 HTTPS URL 下载。
- 白名单外 URL 只能提取关键词，不得发起网络下载请求。
- 下载必须设置大小上限、超时上限和允许的文件扩展名。
- 压缩包解压必须防止路径穿越，解压结果不得写出项目允许目录。
- 下载内容不得包含或执行动态代码、脚本、插件或二进制可执行文件。
- 导入前必须先落到隔离目录，完成扩展名、大小、路径和 import 检查后才能进入 `res://` 运行路径。
- 失败资产必须保持 `quarantined` 或 `failed`，不得被 scene/resource 引用。
- 所有下载、隔离、导入和替换结果必须写入 `evidence.json`。

建议最小结构：

```text
# ASSETS
- id: player_model_001
  source: builtin|whitelist_url|generated|placeholder
  license: <license>
  original_path: <path>
  godot_path: res://...
  usage: player|enemy|room|prop|ui|vfx
  imported: true|false
  bound_to_scene: res://...
  requires_collision: true|false
  collision_shape: res://... 或 none
  asset_smoke: passed|failed|skipped
  status: pending|verified|failed|quarantined
  last_verified_at: <iso8601>
  validation_run_id: <run-id>
```

失败处理规则：

- 替换失败时必须回滚到替换前 scene/resource，或把失败资产移动到隔离目录并保持原资产可用。
- 隔离目录必须位于项目允许目录内，例如 `res://_quarantine/` 或工作区证据目录。
- `quarantined` 资产不得被运行时 scene 引用。
- 失败原因必须同时写入 `evidence.json` 和 `ASSETS.md` 对应条目。

## 模块级机器验收

每个模块需要生成或维护机器可运行的 smoke 脚本，例如：

```text
Game.Godot/Tests/Milestones/M1Smoke.cs
Game.Godot/Tests/Milestones/M2Smoke.cs
```

Smoke 只验证工程事实，不验证主观体验。

可验证内容包括：

- 场景能加载。
- Player node 存在。
- Camera 存在并可用。
- input action 存在。
- collision layer 存在。
- 敌人或关键实体能 spawn。
- 攻击、命中、受击、死亡等状态能改变。
- 翻滚、移动、技能等操作会导致可观测状态变化。
- UI 或 HUD 关键节点存在。
- 奖励、升级、结算、存档等数据路径可写可读。
- 房间切换或地城推进后目标 scene 存在。

完成标准：

- 每个已执行模块至少有一个对应 smoke。
- smoke 失败时模块不得标记为机器验收通过。
- smoke 输出必须包含可解析 PASS/FAIL。
- 自动修复循环必须读取 smoke 失败原因。

## Evidence 证据包

每次模块执行、反馈修复或素材替换完成后，需要写入证据文件：

```text
logs/prototype-evidence/<project-id>/<run-id>/evidence.json
```

建议同时保留：

```text
logs/prototype-evidence/<project-id>/<run-id>/godot.log
logs/prototype-evidence/<project-id>/<run-id>/assertions.json
logs/prototype-evidence/<project-id>/<run-id>/frames/
```

`evidence.json` 至少记录：

- `schemaVersion`。
- `projectId`、`runId`、`route`、`moduleId`。
- `startedAt`、`finishedAt`。
- `dotnet build` 结果。
- Godot import 结果。
- Godot headless load 结果。
- 当前模块 smoke 结果。
- asset validation 结果。
- screenshot 或 frame 检查结果。
- 自动修复次数。
- 最终状态。

建议最小 JSON 结构：

```json
{
  "schemaVersion": 1,
  "projectId": "<project-id>",
  "runId": "<run-id>",
  "route": "skeleton-m1|module-execute|feedback-repair|asset-library",
  "moduleId": "M1",
  "status": "passed|failed|needs_user_feedback|timed_out",
  "startedAt": "<iso8601>",
  "finishedAt": "<iso8601>",
  "repairAttempts": 0,
  "checks": {
    "dotnetBuild": { "status": "passed|failed|skipped", "log": "<path>" },
    "godotImport": { "status": "passed|failed|skipped", "log": "<path>" },
    "headlessLoad": { "status": "passed|failed|skipped", "log": "<path>" },
    "milestoneSmoke": { "status": "passed|failed|skipped", "assertions": "<path>" },
    "assetValidation": { "status": "passed|failed|skipped", "assets": [] },
    "frameCheck": { "status": "passed|failed|skipped", "frames": [] }
  },
  "riskItems": [],
  "changedFiles": [],
  "failureSummary": []
}
```

状态规则：

- `passed`：全部必需检查通过。
- `failed`：必需检查失败，且自动修复未达到继续条件。
- `needs_user_feedback`：自动修复达到 3 次或 20 分钟上限，需要用户提交反馈继续修正。
- `timed_out`：run 超时或外部进程超时。
- `skipped` 只能用于当前模块明确不适用的检查，必须写明原因。

截图/帧检查只做机器事实判断：

- 图片不是空白。
- 动态模块的多帧 hash 不完全相同。
- viewport 尺寸正确。
- 没有全黑、全透明或明显错误图。
- Godot log 没有 ERROR。
- ASSERT FAIL 数量为 0。

不要求人类观看视频或截图后判断质量。

## 路由改造要求

### 原型骨架创建路由

原型骨架创建继续保留，但语义是执行 M1。

完成标准：

- 页面展示 M1 的具体内容和玩家应验证的体验点。
- 执行时读取 `GDD.md`、`prototype-v1-plan.md`、M1 spec、`STRUCTURE.md`、`MEMORY.md`、`ASSETS.md`。
- M1 完成后生成或更新 `STRUCTURE.md`。
- M1 完成后生成 `evidence.json`。
- M1 完成后允许打包下载。
- 骨架验收通过后禁止再次创建或删除骨架。
- 如果用户已经通过“完成游戏模块”执行并确认 M1，原型骨架页必须显示 M1 已完成并锁定创建入口。
- 如果用户先通过原型骨架页完成 M1，“完成游戏模块”页面的 M1 必须同步为已执行或可确认状态，不得要求重复执行。

### 完成游戏模块路由

前台仍保持一个模块一个执行按钮，不向用户暴露内部风险任务。

完成标准：

- 默认显示当前 pending/running 模块。
- 只有当前激活模块可以执行、反馈修复、确认完成。
- 执行当前模块时读取当前 M spec 和工程持久文件。
- 模块执行完成后自动运行机器验收。
- 机器验收失败时自动修复，最多 3 次或 20 分钟。
- 超过限制后需要用户使用“提交反馈并修正模块”继续修复。
- 用户可以不下载包就确认完成，但前台应展示打包试玩是建议项。
- 确认完成后解锁下一个模块。

### 模块执行内部流程

每个模块执行 run 必须按以下顺序闭环：

```text
1. 读取 GDD.md
2. 读取 docs/prototype-v1-plan.md
3. 读取当前 m*-spec.md
4. 读取 STRUCTURE.md / MEMORY.md / ASSETS.md
5. 识别内部风险项
6. 实现当前模块
7. 更新或生成 smoke 脚本
8. dotnet build
9. godot --headless --import
10. godot --headless --quit 或等价轻量启动
11. 运行当前模块 smoke
12. 必要时做截图/帧机器检查
13. 写 evidence.json
14. 更新 STRUCTURE.md / MEMORY.md / ASSETS.md
15. 失败则进入自动修复循环
```

轻量验收命令基线：

- C# 编译：`dotnet build`。
- 核心测试：存在相关测试时运行 `dotnet test` 或等价目标测试。
- Godot 导入：`Godot --headless --path <project> --import --quit` 或当前 Godot 版本等价命令。
- Godot 轻量启动：`Godot --headless --path <project> --quit-after 2` 或当前 Godot 版本等价命令。
- 模块 smoke：运行当前模块专用 smoke，并生成可解析 assertions。

如果项目模板、Godot 版本或运行环境不支持某条命令，必须在 `evidence.json` 中把该项标记为 `skipped` 并写明替代检查，不能静默跳过。

### 内部风险预检

风险预检是后台能力，不改变前台流程。

需要识别的风险包括：

- 程序地城或随机房间。
- 动画状态切换。
- 复杂相机。
- 复杂物理。
- 动态导航。
- 运行时几何。
- shader 或后处理。
- 资产替换影响碰撞、阻挡、命中或导航。

完成标准：

- 风险项写入 `evidence.json`。
- 高风险项至少有一个最小验证或 smoke 断言。
- 风险验证失败时不得继续宣称模块完成。
- 风险预检不在前台拆成多个用户任务。

### 项目素材库路由

项目素材库 run 是 `ASSETS.md` 的主要更新入口。

完成标准：

- 支持用户输入关键词或 URL。
- URL 只在白名单命中时允许真实下载。
- 非白名单 URL 只能提取关键词，不能下载。
- 下载必须遵守资产下载安全契约。
- 下载后执行 Godot import。
- 根据替换目标更新 scene/resource。
- 需要碰撞的资产必须补齐 collision shape 或碰撞绑定。
- 运行 asset smoke。
- 通过后更新 `ASSETS.md`。
- 失败时 `evidence.json` 记录失败原因，`ASSETS.md` 不标记 `verified`。

## 路由状态契约

后台 route 对前台至少暴露以下状态，避免页面只能靠日志猜测：

- `not_started`：模块未激活。
- `active`：模块已激活但未执行。
- `running`：模块执行中。
- `validating`：实现完成，正在机器验收。
- `auto_repairing`：机器验收失败，正在自动修复。
- `needs_user_feedback`：自动修复达到上限，需要用户提交反馈继续。
- `passed`：机器验收通过，可由用户确认完成。
- `completed`：用户已确认完成，下一模块已解锁。
- `failed`：不可自动恢复的失败，需要展示失败原因。

完成标准：

- 前台模块状态、进度条颜色、按钮 enabled/disabled 必须只从该状态契约派生。
- 每个状态必须能关联到最近一次 `evidence.json` 或明确说明尚无 evidence。
- 刷新页面后必须从后端项目状态和最新 evidence 恢复当前模块，不依赖浏览器临时记忆。

## 运行互斥和幂等契约

Prototype 阶段所有会写入游戏项目工作区的 run 都必须按项目互斥，避免并发写同一个 Godot 项目导致状态、资源或 evidence 损坏。

受互斥保护的 run 至少包括：

- 原型骨架/M1 执行。
- 当前模块执行。
- 提交反馈并修正模块。
- 项目素材库下载、导入、替换。
- 打包下载项目中会触发构建产物写入的步骤。

完成标准：

- 同一项目同一时间最多只有一个写入型 prototype run。
- 用户重复点击同一按钮时，应返回已有 run 状态或被前台禁用，不得启动第二个写入 run。
- run id 必须稳定写入后端状态和 `evidence.json`。
- run 失败、超时或服务重启后，不得让模块永久停留在 `running`、`validating` 或 `auto_repairing`。
- 服务恢复时必须能根据后端状态和最新 evidence 把卡住的 run 标记为 `timed_out` 或 `failed`，并允许用户继续反馈修复或重新执行当前模块。
- 打包下载不得改变模块完成状态；它只能读取最新通过验收的项目状态并生成包。

## 前台展示要求

在“完成游戏模块”页面的当前模块详情中增加折叠区：

```text
自动验收证据
- build: passed/failed
- godot import: passed/failed
- scene load: passed/failed
- milestone smoke: passed/failed
- asset validation: passed/failed
- screenshot/frame check: passed/failed
- latest evidence path
```

前台不增加复杂任务列表。

保留主要按钮：

- 执行当前模块。
- 提交反馈并修正模块。
- 完成当前模块并激活下一模块。
- 打包下载项目。

## 总体验收标准

本轮改造完成后，至少满足以下条件：

- 新项目从 GDD 创建到 M1 执行，可以生成 `STRUCTURE.md`、`MEMORY.md` 和 `evidence.json`。
- GDD 补全后可以产出模块 spec，模块执行 route 能直接读取并执行。
- 完成游戏模块执行任一 M 后，可以生成或更新 smoke 脚本并运行。
- 模块机器验收失败时会自动修复，不需要用户先手动触发 needs fix。
- 自动修复超过 3 次或 20 分钟后才交还用户反馈入口。
- 项目素材库下载、替换、验证成功后会更新 `ASSETS.md`。
- `ASSETS.md` 中 `verified` 资产必须有 import、绑定、碰撞或 smoke 证据。
- 前台能展示最新模块自动验收证据。
- 不要求用户观看视频或截图后才能确认模块完成。

## 建议实施顺序

1. 新增 `STRUCTURE.md`、`MEMORY.md`、`ASSETS.md` 的生成和读取约定。
2. 给模块执行 run 增加 `evidence.json`。
3. 给 M1/Mn 增加 smoke 脚本生成和运行。
4. 将 smoke/evidence 接入自动修复循环。
5. 将前台模块详情接入自动验收证据展示。
6. 改造项目素材库 run，完成下载、导入、替换、验证后更新 `ASSETS.md`。
7. 增加截图/帧机器检查作为可选证据层。

## 回归测试要求

改造完成后至少增加或更新以下自动化覆盖：

- GDD/spec 补全后可以生成模块 spec，并被模块执行 route 读取。
- M1 通过原型骨架页或完成游戏模块页任一入口完成后，另一个入口状态同步。
- 原型骨架 route 执行 M1 后写入 `STRUCTURE.md`、`MEMORY.md` 和 `evidence.json`。
- 模块执行 route 在 smoke 失败时进入自动修复循环，并在 3 次或 20 分钟后进入 `needs_user_feedback`。
- feedback repair route 完成后再次运行轻量验收，并写入新的 `evidence.json`。
- 资产库 route 对白名单外 URL 不下载，只提取关键词。
- 资产库 route 对下载大小、超时、扩展名、压缩包路径穿越和动态代码文件有拦截测试。
- 资产替换失败时回滚或隔离，`ASSETS.md` 不会标记 `verified`。
- 同一项目重复点击执行、反馈修复或素材替换时不会启动并发写入 run。
- 服务重启或 run 超时后，前台不会永久显示执行中状态。
- 前台刷新后能恢复当前项目和当前模块状态。
- 前台不会展示内部实现名、开发工具名或复杂内部风险任务。

## 核对清单

- [ ] `STRUCTURE.md` 已生成并被模块执行读取。
- [ ] `MEMORY.md` 已生成并被模块执行读取。
- [ ] `ASSETS.md` 已生成，且素材库 run 成功后会更新。
- [ ] GDD 补全后已生成可执行模块 spec。
- [ ] 原型骨架创建按 M1 执行。
- [ ] 原型骨架页和完成游戏模块页的 M1 状态已同步。
- [ ] 每个模块执行后有 `evidence.json`。
- [ ] 每个模块至少有 smoke 验证。
- [ ] 机器验收失败会自动修复。
- [ ] 自动修复有 3 次或 20 分钟上限。
- [ ] 前台展示自动验收证据。
- [ ] 用户不需要下载或人工看图才能确认模块完成。
- [ ] 素材替换后执行 import、绑定、碰撞或 smoke 验证。
- [ ] 素材替换失败会回滚或隔离，不会破坏当前可运行项目。
- [ ] `ASSETS.md` 不会把失败资产标记为 `verified`。
- [ ] `evidence.json` 使用稳定 schema，并能被前台读取。
- [ ] 前台状态从后端状态和最新 evidence 恢复，不依赖浏览器临时记忆。
- [ ] 同一项目写入型 run 已按项目互斥，重复点击不会并发写入。
- [ ] 服务重启或 run 超时后，卡住状态会恢复为 `timed_out` 或 `failed`。
- [ ] 白名单外 URL 不会触发真实下载。
- [ ] 资产下载已限制 HTTPS、大小、超时、扩展名、解压路径和动态代码文件。
- [ ] 新增或更新了 route、自动修复、资产替换和前台恢复相关测试。
