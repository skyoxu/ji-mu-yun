# Addendum：VDD 与 Quick Dev 语义验证及独立裁判恢复

本附录承载不属于产品合同正文的实现背景和选项，供架构、实现和测试工作流提取。

## 1. 建议的变更落点

- VDD Skill：`.agents/skills/vdd-execution-plan/SKILL.md` 增加短规则；详细合同放在 `references/semantic-verification-contract.md`。
- VDD 验证：新增 `scripts/validate_semantic_verification.py`，并更新 `scripts/validate_skill_contract.py` 及有效/缺失覆盖/结构假绿/自证 validator fixtures。
- Quick Dev schema：扩展 plan-owned implementation contract 和 slice capsule，新增 semantic observation/coverage schemas。
- Quick Dev 工具：按需调整 `tools/build_slice_invocation.py`、`tools/run_slice_lifecycle.py`、`tools/stage_artifact_composer.py`、`tools/loop_plan_directory.py`；复杂度足够时拆出 `tools/semantic_oracle.py`。

## 2. 冻结与执行边界

candidate freeze 后，描述符固定 `shell=false`、executable、argv、cwd、真实 target、fixture 内容 hash 和 RED oracle/hash。GREEN 与 REFACTOR 只能修改实现，不得替换 RED oracle、fixture 或预期结果。oracle executor 应在独立边界内启动进程并从 exit/stdout/stderr、target identity、fixture identity、执行计数和矩阵结果派生 observation。

## 3. Adapter 选择

- **test-runner adapter**：解析 pytest、unittest、dotnet-test 等测试结果；`0 tests + exit 0` 必须判失败。
- **case-matrix adapter**：逐项运行 positive、negative、mutation、recovery fixture，自行比较实际 exit/output 与预期，不信任 SUT 汇总 pass。

两者都应产出统一的 `semantic-observation.v1`，并由 coverage composer 生成 `acceptance-coverage.v1`。schema 版本、目标身份和 hash 是证据不可变字段。

## 4. N→N+1 dogfood

先用冻结黑盒测试和假绿 fixtures 证明旧 judge 能识别漏洞，再修改 VDD 与 Quick Dev。候选 Quick Dev 作为 SUT 被前代/外部 judge 驱动；通过后才允许登记为下一代执行器。使用 08-05 当前实现的脱离式副本进行 dogfood，禁止修改 08-05 原目录及历史证据。

## 5. 失败家族建议

建议至少保留 `missing-coverage`、`copied-observation`、`target-ignored`、`fixture-not-executed`、`matrix-hardcoded`、`zero-tests`、`root-replaced`、`self-judging-validator`、`rollback-prose-only` 和 `hash-drift` 等稳定标识。最终命名和向后兼容策略属于架构阶段决策。

## 6. 未决机制

本附录不决定 schema 拆分、跨平台 stdout/stderr 规范化、judge 版本保留或 rollback probe 接口；这些问题由 PRD 开放问题转入架构/实现阶段，并需在落地前记录决策和测试证据。

## 7. Chapter 6 实施内核补充

### 7.1 Semantic preflight

`semantic-verification.v1` 新增 `complexity_class`、`verification_lane`、`context_lookup_required`、`context_lookup_reason`、`minimum_red_scope` 和 `upgrade_conditions`。preflight 只做判断，不执行测试；语义不足时输出 `semantic-contract-gap` 与 `repair-vdd`。

### 7.2 运行状态与建议路由

运行状态分为 `planned-only`、`observed-run`、`recovered-run`、`invalid-run`。建议路由可写入独立 `recommendation-only` artifact，字段包括 `recommended_action`、`forbidden_actions`、`reason`、`blocked_by`、`reusable_observations` 和 `invalidated_observations`。调用者在完整执行前读取该 artifact。

### 7.3 失败止损与重放

failure family 至少覆盖 semantic-contract-gap、expected-red、unexpected-green、task-implementation-failure、test-harness-failure、target-binding-failure、repo-noise、timeout-no-observation、repeated-deterministic-failure 和 artifact-integrity。建议以 deterministic fingerprint 记录重复失败；达到阈值后停止原参数重跑。每个 oracle 的复用元数据应绑定变化影响图，fixture/target/command 变化会使 RED/GREEN/REFACTOR 全部失效。

### 7.4 Profile 底线

`fast-ship`、`standard`、`self-hosted` 仅改变 oracle 选择和执行成本。实现层应在 profile 展开后再次强制真实进程、exact cover、非零 case/test、target/fixture 绑定和独立 judge；不能用 profile 绕过门禁。

### 7.5 外层职责

LLM Review、Needs Fix 多 reviewer、commit 前全仓硬检查、Godot/GdUnit/taskmaster/overlay 业务规则和 Chapter 5 批处理均由外层 Acceptance/Review/协调器处理。Quick Dev 只生成 handoff 或 stop 建议，并提供恢复所需的完整 artifact 身份与 live blocker。
