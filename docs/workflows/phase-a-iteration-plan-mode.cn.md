# Phase A 迭代计划模式设计

## 1. 目标

把当前 Phase A 里的“快速修复 / 正式反馈”二分法，调整为更工程化的“迭代计划模式”。

核心思想：

- 持久保存的是计划、进度、当前目标和历史结果。
- 真正调用 Codex 的执行单元保持短生命周期。
- 每次只完成一个小目标，然后回填状态，再决定是否继续下一个小目标。

这个模式借鉴 Chapter 6 的分步、可恢复、先读已有证据再继续的思路，但不引入任务三元组、6.7/6.8 评审管线、交付级验收等重机制。

## 2. 为什么替代当前模式

当前模式的问题不是按钮文案，而是执行语义过粗：

- “快速修复”隐含一次性完成一个小修，但用户实际很容易提交一个多子系统闭环需求。
- “正式反馈”隐含一次性完成一轮较大改动，但真实需求仍然需要拆解和阶段确认。
- 依赖固定超时值去区分任务类型，本质是在赌一次 prompt 能否跑完。
- 一旦进程卡死，前端看到的是长时间无反馈，恢复和解释成本都高。

迭代计划模式把“单次执行能力”与“整体需求推进状态”拆开，避免把一个复杂需求误建模为一个长运行进程。

## 3. 设计原则

- 计划持久，进程短命。
- 一次 run 只做一个小目标。
- 每个小目标都要有明确完成定义。
- 每轮结束后都要回写整体进度和下一目标建议。
- 默认由用户决定是否继续下一目标。
- 后续可选开启自动连续推进，但不是 Phase A 首版必需。
- 恢复优先读已有状态，不重复生成计划，不重复执行已完成目标。

## 4. 最小术语

### 4.1 Iteration Session

一次围绕某个项目和某条用户需求建立的“迭代会话”。

它是持久对象，不是常驻进程。

### 4.2 Iteration Goal

会话里的一个小目标。

要求：

- 范围小
- 完成条件明确
- 尽量可验证
- 能独立向前推进整体目标

### 4.3 Iteration Run

执行某一个小目标的一次实际后台 run。

它沿用现有 run 体系，但 run type 不再直接表达“快速修复/正式反馈”，而是表达“计划生成”或“目标执行”。

## 5. 推荐状态模型

### 5.1 Session 总状态

- `planning`
- `ready`
- `running`
- `paused_for_review`
- `completed`
- `failed`
- `cancelled`

解释：

- `planning`：正在拆解需求
- `ready`：计划已生成，等待执行
- `running`：当前有目标执行中
- `paused_for_review`：某一目标执行完成，等待用户决定是否继续
- `completed`：全部目标完成
- `failed`：计划生成失败，或目标失败且无法自动继续
- `cancelled`：管理员或用户明确终止本次会话

### 5.2 Goal 状态

- `pending`
- `running`
- `succeeded`
- `failed`
- `blocked`
- `skipped`

解释：

- `pending`：尚未执行
- `running`：当前正在执行
- `succeeded`：已完成
- `failed`：执行失败
- `blocked`：依赖不满足，需人工处理
- `skipped`：确认不需要继续做

## 6. 建议的数据模型

Phase A 不需要上来就做很重的关系模型，先做三张核心表即可。

### 6.1 `project_iteration_sessions`

字段建议：

- `id`
- `project_id`
- `created_by_account_id`
- `source_kind`
- `source_message`
- `overall_goal`
- `status`
- `current_goal_index`
- `plan_summary_json`
- `latest_summary`
- `created_utc`
- `updated_utc`
- `completed_utc`

说明：

- `source_kind` 可先支持 `manual_feedback`、`continue_suggestion`
- `plan_summary_json` 存轻量计划结构快照

### 6.2 `project_iteration_goals`

字段建议：

- `id`
- `session_id`
- `goal_index`
- `title`
- `description`
- `acceptance_hint`
- `status`
- `result_summary`
- `created_utc`
- `updated_utc`
- `completed_utc`

说明：

- `acceptance_hint` 只保存轻量完成标准，不做 Chapter 6 式重验收

### 6.3 `project_iteration_goal_runs`

字段建议：

- `id`
- `session_id`
- `goal_id`
- `run_id`
- `run_type`
- `created_utc`

说明：

- 用于把既有 `runs` 记录和新目标绑定起来

## 7. 建议的 run type

保留现有 `runs` 表，新增两个轻量 run type：

- `prototype-iteration-plan`
- `prototype-iteration-goal`

含义：

- `prototype-iteration-plan`：根据用户需求生成小目标列表
- `prototype-iteration-goal`：执行某一个具体小目标

这样可以逐步替代：

- `prototype-quick-fix`
- `prototype-feedback-iteration`

但 Phase A 迁移期可以先并存。

## 8. 基本流程

### 8.1 生成计划

触发方式：

- 用户在自由对话或“提交反馈”区输入较大的改动目标
- 点击“生成迭代计划”

后端动作：

1. 创建 session
2. 启动 `prototype-iteration-plan`
3. 调用 Codex 生成 3 到 7 个小目标
4. 保存 goals
5. 回写 session 状态为 `ready`

前端展示：

- 总目标
- 小目标列表
- 当前推荐先执行的目标

### 8.2 执行下一目标

`??????` ??????????? Phase A Prototype ????????????????`execute-next-goal`???? `prototype` ? `iteration-plan` ???`needs-fix` ????????????????????

触发方式：

- 用户点击“执行下一目标”

后端动作：

1. 检查 session 状态必须是 `ready` 或 `paused_for_review`
2. 取最前面的 `pending` goal
3. 创建 `prototype-iteration-goal` run
4. 调用 Codex 只处理该 goal
5. 回写 goal 状态与总结
6. 刷新 session 状态

若还有未完成目标：

- session -> `paused_for_review`

若全部完成：

- session -> `completed`


???????????????? `README.md`?`meta/routes/prototype/latest.json` ? `meta/routes/iteration-plan/latest.json`??? prototype route state ????????iteration-plan route state ??????????? prototype route state????? Codex?????? goal ? session ??? `needs_fix`???????? prototype ???

???????????? `meta/routes/execute-next-goal/step-XX/latest.json`?`needs-fix` ????????????? step ? `meta/routes/needs-fix/step-XX/latest.json`?????????? `meta/routes/execute-next-goal/step-XX/latest.json`????????????? `meta/routes/prototype/latest.json`??????? needs-fix ??? step ?????????????? prototype ?????
### 8.3 用户判断是否继续

默认设计：

- 每完成一个 goal，就停下来
- 显示：
  - 本轮完成了什么
  - 当前整体进度
  - 下一目标是什么
  - 是否建议继续

用户可选：

- `继续下一个目标`
- `暂不继续`
- `放弃本次计划`

## 9. 计划拆解要求

计划生成器不需要像 Chapter 6 一样生成重型任务，只需要满足以下约束：

- 每个目标必须有明确单句标题
- 每个目标必须只推进一个主要结果
- 每个目标必须尽量控制在单次 Codex run 可处理范围内
- 每个目标必须写一个轻量完成判断
- 目标顺序必须反映依赖关系

建议每次最多生成：

- 3 到 7 个目标

不建议：

- 超过 10 个
- 一个目标内同时要求 UI、逻辑、资源、验证全部大改

## 10. 与现有界面的关系

### 10.1 替换方向

当前两个动作：

- `快速修复`
- `提交反馈并继续优化原型`

建议逐步替换为：

- `生成迭代计划`
- `执行下一目标`
- `继续下一个目标`

### 10.2 过渡期兼容

Phase A 可以暂时保留旧按钮，但做语义收敛：

- 旧“快速修复”
  - 只接受非常小的单点需求
  - 或内部重定向为“生成单目标计划”
- 旧“提交反馈并继续优化原型”
  - 内部改为“生成迭代计划”

## 11. 恢复策略

这是从 Chapter 6 借鉴但做轻量化的重点。

### 11.1 恢复原则

- 先读 session 和 goal 状态
- 不重复生成已有计划
- 不重复执行已 `succeeded` 的 goal
- 若某个 run 卡死，只把当前 goal 标成 `failed` 或 `blocked`
- 不影响整个 session 的历史记录

### 11.2 页面刷新后的表现

页面刷新时应看到：

- 当前是否存在活动 session
- 计划列表
- 当前执行到第几个目标
- 上一个目标结果
- 下一目标建议

## 12. 为什么不建议“持久进程式 run”

不建议让一个后台 run 持续穿过多个小目标，原因：

- 更难恢复
- 更难归因失败位置
- 更难安全回收
- 更难防僵尸进程
- 前端难以给出可信进度

所以推荐模式是：

- 持久的是 session
- 短命的是单目标 run

## 13. Phase A 最小落地范围

首版只做以下能力：

1. 针对当前项目创建一个迭代 session
2. 生成 3 到 7 个小目标
3. 展示计划与当前进度
4. 执行下一目标
5. 每目标完成后停下
6. 用户决定是否继续
7. 记录每个 goal 的结果摘要和关联 run

首版不做：

- 自动连续执行全部目标
- 复杂依赖图
- 并行目标
- Chapter 6 级别的 review / acceptance / task refs
- 多计划合并

## 14. 对当前问题的直接帮助

这个模式能直接解决当前 quick-fix / formal-feedback 的几个问题：

- 不再用固定长短超时去猜需求规模
- 不再把“多闭环需求”误当成一次小修
- 不再要求一个 run 完成整个需求
- 即使中断，也只损失一个目标，不丢整轮上下文
- 用户更容易理解系统当前做到了哪一步

## 15. 推荐实施顺序

### 15.1 第一步

先新增持久计划数据模型与只读展示。

### 15.2 第二步

把“提交反馈并继续优化原型”改为“生成迭代计划”。

### 15.3 第三步

新增“执行下一目标”按钮和单目标 run。

### 15.4 第四步

把“同意继续优化”改成“继续下一个目标”。

### 15.5 第五步

逐步弱化旧的 quick-fix / formal-feedback 路由。

## 16. 一句话总结

Phase A 更适合做“持久计划 + 单目标短 run + 人工决定是否继续”的轻量迭代工作流，而不是继续在“快速修复 300 秒”与“正式反馈 30 分钟”之间做按钮级二选一。
