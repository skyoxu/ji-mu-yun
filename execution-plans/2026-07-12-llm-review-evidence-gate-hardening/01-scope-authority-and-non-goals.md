# 范围、权威与非目标

## 1. 问题定义

当前通用 adversarial reviewer 含有“至少找出十个问题”和“零发现可疑”的规则。该激励会把模式匹配、风格偏好和未来假设推入 finding，再由后续 triage 消耗模型、人工和复审轮次。本计划把真实性判断从提示词自律提升为输出层机器门禁。

## 2. 规范层级

实施后的权威顺序：

1. `AGENTS.md` 的安全、变更和路由硬规则；
2. 已接受 ADR 与 `docs/standards/llm-review-findings.md`；
3. review finding/rejection/result JSON Schema；
4. review gateway 确定性规则；
5. 代码、文档、计划和安全 adapter；
6. BMAD/GDS/Codex reviewer prompt。

低层不得降低高层的证据要求。prompt 与 gateway 冲突时，gateway 拒绝输出。

## 3. 覆盖范围

- changed-code review、acceptance review、edge-case review；
- Markdown、JSON Schema、fixture、execution-plan whole-directory review；
- `scripts/sc/run_review_pipeline.py` 与 `agent_to_agent_review.py` 的 finding sidecar；
- 平台开发 Codex 作业前自检和作业后审查；
- 前台用户触发 Codex 的候选 finding、修复建议和阻断决定；
- BMAD/GDS code-review 与 quick-dev 的仓库级适配。

## 4. 非目标

- 不复制或 fork ECC workflow runtime；
- 不修改 BMAD/GDS 安装文件；
- 不把文件长度、函数长度、重复、缺接口、缺注释等 code smell 自动认定为 bug；
- 不要求每次审查必须有 finding；
- 不在本计划中实施 GDD-to-module、React `/ui-v2` 或 Phase boundary 重构；
- 不用 LLM finding 替代编译、测试、schema、link、smoke 或安全扫描；
- 不把计划可实施解释为代码已完成。

## 5. 两类 Codex 的共享与差异

共享核心：同一 finding schema、三联证明、去重指纹、状态机、有限复审、零发现合法。

平台开发 Codex adapter 额外读取 diff、调用关系、测试、ADR、standards 和任务 authority。前台触发 Codex adapter 额外读取账户/项目边界、route recovery authority、当前 acceptance blocker、workspace allowlist 与浏览器安全输出合同。两者不得建立两套互相漂移的严重等级。

## 6. 上游等待门

除本目录纯计划和本目录 plan-local schema/validator 外，实施者必须证明两个上游重构目录都已达到各自完成定义，并记录不可变 commit/evidence 引用。未满足时，禁止把 schema/validator 迁入长期 owner，禁止修改共享 Phase LLM/Codex 入口、现有执行计划或前台 route integration。

## 验收标准

- Given 实施者准备开始 R1–R6，When 检查上游 handoff，Then 两个上游完成证据均存在且可定位，否则 fail closed。
- Given reviewer prompt 与 schema 冲突，When gateway 校验，Then 以 schema/standard 为准并拒绝不合格 finding。
- Given BMAD/GDS 升级，When重新安装技能，Then 本目录规划的标准、custom override、gateway 和回归测试仍由仓库拥有。
