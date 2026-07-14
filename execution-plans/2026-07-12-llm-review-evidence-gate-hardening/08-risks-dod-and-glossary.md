# 风险、Definition of Done 与术语

## 1. 主要风险

| 风险 | 失败模式 | 缓解与止损 |
| --- | --- | --- |
| prompt 规则被忽略 | schema 合法但事实错误 | 当前 artifact hash、三联证明、独立 verifier、人工标注 corpus |
| 过度降噪导致漏报 | seeded defect 未被发现 | recall 与 precision 联合门槛；不得用 finding 数量作 KPI |
| BMAD/GDS 升级回归 | stock 强制 finding 再次成为 authority | 不改安装文件；team override；仓库 wrapper；升级测试 |
| endless loop | 新标题重复旧误报 | fingerprint disposition memory；一次 discovery/verification；P2 不循环 |
| 文档审查变成写作建议 | 没有 consumer bad outcome | document adapter 强制 authority/consumer/validator 与三联证明 |
| 两类 Codex 规则漂移 | 平台与前台严重等级不一致 | 共享 schema/standard；仅 adapter 上下文不同 |
| 项目间泄露 | finding memory 跨账户读取 | account/project/workspace key、隔离测试、redaction |
| 与进行中重构冲突 | 修改共享入口或旧计划 | R0 handoff gate；未完成前禁止运行时接入 |
| 中途切换三层审查 | 同一 7 月 7 日 review run 混用两套规则 | in-flight route 保持不变；handoff 后按 route version 切换；历史 finding 不重分类 |
| Bootstrap 冒充正式 authority | supplemental 结果被当作 BH-HANDOFF、repair 或完成证据 | sidecar 标记 bootstrap；不接正式 pipeline；operator 手工选择是否反馈上游 |
| Bootstrap 修改目标 | review 工具越界写 7-07/7-11 | prepare/gate/finalize target-read-only 测试；输出目录不得位于 scope 内 |
| 以降 reasoning 换取漏读 | medium role 被错误解释为允许 sampling | completeness profile 固定 all/no-sampling/context-closure；prompt、manifest、gate 一致绑定 |
| gate 重跑丢失 verifier | 恢复操作覆盖独立决策 | CLI 写前检查非空 decisions，拒绝重跑并保持文件 hash |
| dedup 错并或严重等级降级 | 同证据行的不同失败链互相吞并，或 P2 抢先吞掉同 fingerprint P1/P0 | fingerprint 必须包含规范化 failure tuple 与 dimension；仅完整 fingerprint 相同才分组并确定性保留最高 severity |
| 完整 Review 成本失控 | 每修一条 finding 就重跑三层 reviewer | 首轮汇总、批量修复、targeted deterministic checks、默认两轮/硬上限三轮 |
| 受审内容劫持 reviewer | Markdown/代码注释要求改角色、scope 或强制 APPROVE | 所有 artifact 视为 untrusted data；profile-bound prompt injection boundary |
| 三角色同质化 | prompt 只有 reviewer 名称，三个进程重复同一检查 | profile-bound role rubric 与误报清单直接投影到各 prompt |
| authority 未冻结 | reviewer 运行中规则或 artifact 改变导致 run stale | preflight 后 authorize-launch 冻结并在 validate/gate/finalize 重验 |
| 重复语义审查 | Quick Dev/BMAD/GDS 与 Bootstrap 同时找问题 | 每 change cycle 单一 Bootstrap semantic authority，其他 workflow 只做实现与确定性检查 |
| 长进程重复启动或身份伪造 | 超时后重复启动，或用不存在/无关 PID 制造 completed reviewer evidence | acquire 校验 live PID 并捕获 OS process identity；release 强制原 PID，live 时重验 identity，已正常退出时仅允许原 PID 收口 |
| 成本不可见 | 73 artifacts × 三个 high reviewer 在未确认时启动 | prepare 计算 artifact/bytes/reasoning work，high-cost authorize 需要显式确认 |

## 2. Stop Conditions

- 两个上游重构无可验证完成证据时阻止 R1–R6，但不阻止 R0 Bootstrap Review；
- 需要修改 Protected Phase Paths 但尚未获得批准；
- schema 无法表达 P0–P2 三联证明；
- shadow 显示 blocker precision 或 seeded-defect recall 不达标；
- evidence 隔离或 secret redaction 失败；
- gateway 可以被某个生产入口绕过。
- 当前 7 月 7 日审查尚未完成或缺少 route handoff evidence。
- required deterministic preflight 失败或证据不可追溯时，停止在 reviewer 启动前。
- 同一变更达到三轮完整语义 Review 仍未闭合时，停止自动循环并进入 manual pause。
- `authorize-launch` 缺失或失效、同 operation 存在 live lease、high-cost 未确认时，停止 reviewer 启动。

## 3. Global Definition of Done

- 长期 standard、schema、validator、fixtures 已落地并有 owner；
- P0–P2 三联证明全部机器强制；
- 零 finding 合法，failed layer 不会误报 clean；
- review profile/revision 可机读且由 gateway 派生 required layer；required/completed/failed/skipped 集合满足互斥/完备不变量；
- code/document/plan adapters 使用同一严重等级与不同上下文要求；
- BMAD/GDS 安装文件未被修改，升级回归通过；
- Blind/Edge/Acceptance 三个 reviewer 均只能产生带 provenance 的 candidate；
- 平台开发与前台触发 Codex 均不可绕过 gateway；
- dedup、refuted/rejected memory 与 bounded lifecycle 生效；
- shadow 指标和人工标注支持进入 blocking；
- AGENTS/README/standards 只在对应能力真实落地时同步；
- tests、smoke 和 evidence 位于既有 owner 路径，失败证据未被覆盖。
- Bootstrap CLI 可独立运行且没有模型调用、目标写入或正式 pipeline 副作用；外层隔离编排必须由用户显式授权。
- 每个 profile 的 role rubric、误报抑制、untrusted-content、deterministic preflight 和 bounded review-cycle 均被 manifest/hash/test 绑定。

## 4. 术语

- candidate：reviewer 原始候选，不具有阻断权。
- fact gate：确定性检查位置、失败链、上下文和等级证据。
- 三联证明：精确证据与行号、失败场景、防护缺口。
- authority graph：文档条款到 owner、consumer、validator 的关系。
- fingerprint：基于证据和失败链的稳定去重身份。
- disposition memory：rejected/refuted 等最终处置的持久记录。
- sourceReviewers：产生或合并到同一 candidate/finding 的 reviewer role 集合。
- reviewProfile/policyRevision：gateway execution context 为当前 route/scope 分配的可信 review policy 稳定标识和不可变 revision；用于派生 required reviewer layers，不能由 result producer 选择另一个较窄但可信的 profile。
- requiredLayers/completedLayers：可信 profile/revision 派生出的必须运行集合，以及实际成功完成的 reviewer role 集合；与 failed/skipped 共同决定 clean/incomplete，不能只看 findings 数量。
- unverifiedClass/unverifiedDisposition：独立 verifier/gateway 为 unverified P0/P1 写入的机器分类与处置；security/data_loss 对应 blocking，other 对应 manual_pause；前者只能 blocked，后者只能 incomplete，不能混入同一 result。
- clean：scope 内零合格 finding 且所有必要 reviewer layer 完成。
- incomplete：必要 layer、validator 或 evidence 不完整，不能宣告 clean。
- advisory：通过门禁但不自动阻断/循环的 P2。
- plan-ready：计划可实施，不代表代码或产品能力完成。
- bootstrap review：handoff 前可用的 plan-local、只读、用户手工 reviewer 编排与事实门禁；输出是 supplemental evidence，不是生产 gateway 或上游完成 authority。
- review object profile：按计划 authority、实施闭合、Skill/路由、聚焦变更选择的可信 profile；改变 reasoning/depth 但不允许改变 all-artifact、no-sampling 和 context-closure 完整性合同。
- deterministic preflight：在任何语义 reviewer 启动前执行的 build/test/schema/link/validator/smoke 等机器检查；失败即停止，但不能替代最终完整语义 Review。
- full-review cycle：三层 reviewer、gate 和所需 verifier 组成的一次完整语义轮次；默认两轮，第三轮只处理新 P0/P1 或 authority/context graph 改变，之后 manual pause。
