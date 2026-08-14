# 输入对账：know27.txt

## 结论

当前 PRD 与 addendum 已吸收 `know27.txt` 的主要修正：Acceptance 拥有范围和路由、Bootstrap Complete Review 保持三角色、required checks 来自合同投影、normative authority 使用完整文件或控制器拥有的 hash-bound projection、implementation-complete 位于 Acceptance 之前，以及 segment/lease/executable identity 的 bounded hardening。未发现会推翻产品方向的遗漏。

仍有 3 个重要差距需要在定稿前处理。

## 重要差距

### 1. Bootstrap deterministic preflight 的执行责任没有在功能需求中完全闭合

`know27.txt` 明确要求 Bootstrap implementation conformance 继续执行由 Acceptance/implementation contract 投影的 plan-mandated deterministic checks，而不是只消费已有结论。PRD 的产品原则第 5 条表达了“Bootstrap 只执行投影出的 required checks”，但 FR-5 的主体仅要求 Acceptance 取得 required-check set，FR-8/FR-19 更接近让 Bootstrap 消费或验证已有 evidence。

这留下两种实现解释：Bootstrap 独立重放 required checks，或仅信任 Acceptance 的 replay receipt。后者可能弱化现有 implementation-conformance preflight。建议在 FR-5 或 FR-7 中明确：进入 `full_implementation_conformance` 时，Bootstrap 必须按既有 profile 对同一 frozen candidate/closure 重放或按正式复用合同验证每个 plan-mandated check，且不得仅接受未重放、未验证的上游状态声明。

### 2. 成本决策可能被解释为绕过 typed risk policy

FR-18 写明高成本时 Acceptance 可“改走 deterministic-only”。`know27.txt` 的核心约束是 Bootstrap 是否必需由 Acceptance 的 typed scope/risk policy 决定；成本治理可以促使重建并重新验证 closure、暂停或要求授权，但不能把一个 policy-required 的 full implementation conformance 降级为 deterministic-only。

建议收紧 FR-18：成本结果只能在 typed policy 允许的 route 集合内选择；若 policy 已要求 Bootstrap，高成本只能触发 closure rebuild/revalidation、manual pause 或显式 policy-authorized override，不能单独成为降级依据。

### 3. `75%` closure 缩减尚未决，却已成为硬成功门槛

`know27.txt` 只要求 compact closure “显著小于 whole plan”，并把 `80–200 KB` 明确作为示例而非规范阈值。PRD 的 SM-2 已规定至少减少 75%，但开放问题第 2 项仍在询问是否采用 75% 或动态 workload policy。

这既超出了源输入已确定的决策，也造成文档内部冲突。建议在该开放问题解决前，将 SM-2 的 75% 标为 `[ASSUMPTION]` 或改为“达到经 Architecture/Policy ratify 的版本化缩减阈值”；定稿时只保留一个 authority。

## 无需补充的已吸收事项

- Complete Review 仍为 Blind Hunter、Edge Case Hunter、Acceptance Auditor 三角色。
- deterministic failure 为 typed repair，且 reviewer call 为零。
- implementation-complete 是 Quick Dev/VDD 输出和 Acceptance 入口，不由 Bootstrap 产生。
- 小型 authority 整文件读取，大型 authority 使用 controller-owned hash-bound Range Projection。
- segment-only snapshot、canonical payload identity、绝对 snapshot path、executable identity 自动继承、lease reconciliation 和 bounded retry 均已覆盖。
- 8-13 规模回归已包含越界读取、遗留 lease、人工 executable 重填、mismatch 有界终止和三角色完整 coverage 等关键成功条件。
