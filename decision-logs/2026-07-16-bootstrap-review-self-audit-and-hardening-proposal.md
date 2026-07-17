# Bootstrap Review 自检结论与控制面修复提案

- Title: bootstrap-review-self-audit-and-hardening-proposal
- Date: 2026-07-16
- Status: accepted
- Supersedes: none
- Superseded by: none
- Branch: main
- Git Head: 6adab7f
- Why now: 2026-07-13 至 2026-07-16 已累计产生 45 个真实 Bootstrap Review run；多轮 Review 证明事实门禁能发现高价值问题，但 Windows ACL、受限 token 访问、重复 reviewer、悬空 lease、非终态 run 和失真的成本估算造成了可观的时间与 token 消耗，需要在继续扩大使用范围前先修复控制面。
- Context: 本次只读自检覆盖 `logs/ci/**/review-gateway-bootstrap-*` 下全部真实 run，并以当前 `run-phase-bootstrap-review` Skill、operator guide、profile registry 和 `run_bootstrap_review.py --help` 为运行权威。`logs/ci/2026-07-16/synthetic-rmap-binding-clean/` 仅是合成绑定证据，不计为真实 Review run。
- Decision: 接受并保留三层独立 reviewer、完整 artifact 覆盖、P0/P1 独立 verifier 和三轮硬上限。实施前先接受 Bootstrap Review Execution Control Plane Ownership ADR 并建立 durable standard；随后由仓库自有 Skill 拥有 Codex Exec runner、Artifact View、attempt/event、repair closure 和恢复协议，7-12 目录仅保留迁移期兼容入口，外部全局 Skill 只做 revision-bound 薄路由。本文件直接作为 approved intent source，不再创建新的 VDD execution-plan。
- Consequences: Review 的语义强度不下降；启动前失败会更早、更便宜；历史 run 可以被确定性归类而不改写原始 evidence；后续完整 Review 需要额外的 access proof 和 repair closure，但能显著降低无效 reviewer 消耗。
- Recovery impact: 后续会话应先读取本文件，再读取 `execution-plans/2026-07-12-llm-review-evidence-gate-hardening/09-bootstrap-review-operator-guide.md` 和待新增的 run index/inspect 输出。任何优化都必须新增 sidecar 或新 run，不得重写 45 个历史目录。
- Validation: `py -3 scripts/python/bootstrap_review_self_audit.py --audit-id bootstrap-self-audit-20260716-proposal-r2 --out-dir logs/ci/bootstrap-self-audit/bootstrap-self-audit-20260716-proposal-r2` 已通过；`audit-result.json` 为 `sha256:ccad4469eaf4c39992c63d6493d7726d6729de6bad342fd52764bae426323010`。审计解析了 45 份真实 input、31 份 gate result、26 份 final metrics/dispositions、17 份 process lease 和全部符合声明规则的 token 记录，未修改历史 Review evidence。
- Related ADRs: `docs/adr/ADR-0041-bootstrap-review-execution-control-plane-ownership.md`；该 ADR 明确 durable standard、仓库自有 Skill、7-12 compatibility layer、logs evidence 和外部薄 Skill 的所有权。
- Related execution plans: `execution-plans/2026-07-12-llm-review-evidence-gate-hardening/`; `execution-plans/2026-07-15-repository-maintenance-tdd-adapter/`
- Related task id(s): n/a; Bootstrap Review run 当前不绑定 Taskmaster task id。
- Related run id: 2026-07-13 至 2026-07-16 的 45 个 `review-gateway-bootstrap-*` run；重点包括 `vdd-clarification-quick-20260715-004024`、`repo-maint-tdd-final-20260716-0129`、`repo-maint-tdd-final-r2-20260716-024940`、`repo-maint-tdd-final-r3-20260716-110837`。
- Related latest.json: n/a; Bootstrap Review 当前没有跨 run 的 canonical latest/status pointer，这正是本提案要修复的恢复缺口之一。
- Related pipeline artifacts: `logs/ci/2026-07-13/` 至 `logs/ci/2026-07-16/` 下的 `review-gateway-bootstrap-*`；当前自检 evidence 为 `logs/ci/bootstrap-self-audit/bootstrap-self-audit-20260716-proposal-r2/`；前一版审计 evidence 保留为 superseded sidecar；可提交摘要为 `decision-logs/evidence/2026-07-16-bootstrap-review-self-audit-summary.json`。

## 1. 结论摘要

当前 Bootstrap Review 的主要问题不是事实门禁过严，也不是 reviewer 数量过多。日志证明三层独立审查和独立 verifier 能持续发现真实 P1，并且 Edge Case Hunter 与 Acceptance Auditor 的高推理配置有明确产出。

主要浪费集中在控制面：

1. 父进程能读取 artifact，不代表受限 `codex exec` token 能读取同一 artifact。
2. Artifact 访问和输出写入失败往往发生在 reviewer 已消耗大量 token 之后。
3. 每轮使用临时 PowerShell/Python runner 管理 PID、lease、stdin、retry 和 JSON 写回，恢复形态不统一。
4. 缺少跨 run 的确定性状态索引，无法直接区分 prepared、running、awaiting verification、finalized、abandoned 和 superseded。
5. Round 2/3 只绑定 predecessor lineage，没有强制证明上一轮 accepted finding 已经按当前 hash 完成批量修复和相邻回归验证。
6. 成本估算按单份 artifact 集合计数，不能反映三 reviewer、verifier、retry 和多轮完整读取的实际成本。

因此修复方向应是“更早失败、统一执行、显式恢复、校准成本”，而不是减少 reviewer、抽样材料或降低推理等级。

## 2. 审计范围与方法

### 2.1 纳入范围

- 所有 `logs/ci/**/review-gateway-bootstrap-*/review-input.json`。
- 对应的 `preflight-result.json`、`review-launch-authorization.json`、`process-leases.json`。
- 三个 `reviewer-outputs/*.json`。
- `review-gate-result.json`、`review-candidates.json`、`review-rejections.json`。
- `verifier-output.json`、`review-dispositions.json`、`review-metrics.json`。
- 可读的 probe、reviewer、verifier stderr/stdout 和 token 记录。

### 2.2 排除范围

- `logs/ci/2026-07-16/synthetic-rmap-binding-clean/`：仅用于验证 plan-local evidence binding，不是实际三层 Review。
- `logs/vdd-plan-*`：作为被 Bootstrap run 引用的修复和验证 evidence，不重复计为 Review run。
- 历史日志中的 prompt 文本不作为运行成功证据；以 JSON sidecar、lease、gate/final result 为准。

### 2.3 历史协议分层

- 28 个早期 run 缺少当前完整的 `changeId`、`fullReviewRound`、`executionMode`、cost estimate、preflight、launch authorization 或 process lease 合同。
- 17 个较新 run 使用当前控制协议。
- 早期 run 用于识别演进和失败模式，不应倒推为当前 CLI 的合规失败。

### 2.4 可复现审计合同

审计由版本控制内脚本 `scripts/python/bootstrap_review_self_audit.py` 执行，并生成：

```text
logs/ci/bootstrap-self-audit/<audit-id>/
  audit-input-manifest.json
  per-run-classification.json
  candidate-funnel.json
  token-and-duration-summary.json
  audit-result.json
```

证据绑定：

- 45 个 run 的仓库相对路径。
- 每个关键 sidecar 和 token 记录文件的 SHA-256。
- 分类理由、缺失 sidecar 和不可读输入。
- 统计实现文件及其 SHA-256。
- Git HEAD 和工作区状态。
- Candidate、token、duration、lease 和 run-state 的精确定义。

本提案只声明“基于本机 append-only logs 的 hash-bound 可复算统计”。由于原始 45 个 run 未提交到 Git，GitHub 只能检查可提交摘要、脚本和 hash，不能在没有原始 evidence bundle 的情况下独立复算。若未来需要远端独立复算，必须发布原始 evidence bundle 或提供稳定的受控 artifact locator。

## 3. 全量事实基线

### 3.1 Run 状态

| 指标 | 数量 |
| --- | ---: |
| 真实 Bootstrap run | 45 |
| Finalized | 26 |
| Finalized blocked | 20 |
| Finalized clean | 4 |
| Finalized advisory | 2 |
| Prepared/no gate | 14 |
| Awaiting verification | 3 |
| Incomplete | 2 |
| 输入来自 dirty worktree | 43 |

### 3.2 按审查对象分组

| 审查对象 | Run 数 | Finalized | 非终态 |
| --- | ---: | ---: | ---: |
| 7-07 | 12 | 7 | 5 |
| 7-11 | 4 | 1 | 3 |
| Bootstrap Skill 与控制面 | 17 | 10 | 7 |
| VDD Skill 与 clarification gate | 5 | 5 | 0 |
| Repository Maintenance TDD Adapter | 6 | 3 | 3 |
| Focused refactor spec | 1 | 0 | 1 |

### 3.3 Finding 与事实门禁

Candidate funnel 必须区分全部 run 和 finalized run：

| 指标 | 数量 |
| --- | ---: |
| 全部 45 个 run 的 reviewer submissions | 139 |
| 26 个 finalized run 的 reviewer submissions | 82 |
| Finalized gate 接受的唯一 candidate | 79 |
| Finalized gate rejection | 3 |
| Rejection 原因 `stale_evidence` | 3 |
| Verifier refuted | 6 |
| 最终 confirmed P1 | 62 |
| 最终 advisory P2 | 11 |
| P0 | 0 |
| Unverified | 0 |

Reviewer submissions：

| 角色 | 全部 45 个 run | 仅 26 个 finalized run | 最终 finding source |
| --- | ---: | ---: | ---: |
| Blind Hunter | 32 | 21 | 19 |
| Edge Case Hunter | 71 | 38 | 34 |
| Acceptance Auditor | 36 | 23 | 20 |

机械闭合关系为：`82 finalized submissions = 79 accepted unique + 3 rejected`。`139` 与 `82` 的差异来自 19 个非 finalized run，不是 dedup。一个最终 finding 可以有多个 source reviewer，因此最终 source 数量不要求与最终 finding 总数相等。

### 3.4 时间、token 与日志体积

只有 17 个较新 run 保存了可解析 token 记录，因此 token 数据是下限：

| 类型 | 记录 tokens |
| --- | ---: |
| Primary reviewer | 6,886,050 |
| Retry 标记执行 | 2,995,109 |
| Probe | 1,196,686 |
| Verifier | 603,513 |
| 合计下限 | 11,681,358 |

另有至少 2,379,293 tokens 消耗在最终没有形成 `review-result.v1` 的 run 中。该值与上表按执行类型的分类是交叉维度，不能重复相加。

Process lease：

| 状态 | 数量 |
| --- | ---: |
| Completed | 58 |
| Failed | 13 |
| Stale | 1 |
| 仍显示 acquired | 4 |

其他运行成本：

- 61 个日志文件名包含 `retry`。
- 全部 run 约 75.52 MiB。
- 非 finalized run 约 23.71 MiB。
- 有完整 lease 时间的 finalized Codex run 中位 wall time 约 32 分钟，最大 72.7 分钟。

## 4. 代表性运行分析

### 4.1 Repository Maintenance Round 3

Run：`logs/ci/2026-07-16/review-gateway-bootstrap-repo-maint-tdd-final-r3-20260716-110837/`

- 49 个 artifact，535,333 bytes。
- 8 个 confirmed P1。
- 记录 tokens：705,767。
- 总 wall time：约 51.6 分钟。
- Probe：6.6 分钟。
- 三 reviewer 并行阶段：约 26.7 分钟。
- Gate/切换 verifier：约 2.3 分钟。
- Verifier：15 分钟。
- 没有 reviewer retry、failed lease 或明显空等。

结论：该 run 的慢主要是真实完整读取、高推理和 verifier 成本，不属于明显调度浪费。

### 4.2 Repository Maintenance Round 2

Run：`logs/ci/2026-07-16/review-gateway-bootstrap-repo-maint-tdd-final-r2-20260716-024940/`

首次三个 reviewer 均受到 `.agents/skills/bmad-quick-dev/SKILL.md` 访问问题影响：

- Blind Hunter failed。
- Acceptance Auditor failed。
- Edge Case Hunter lease stale，输出记录必读 artifact 未完成。
- 三个首次尝试合计约 259,249 tokens，之后又运行完整 retry。

该失败在启动 reviewer 前可以通过“受限 token 全 artifact 访问探针”发现，因此属于明确可消除的浪费。

### 4.3 VDD Clarification Round 1

Run：`logs/ci/2026-07-15/review-gateway-bootstrap-vdd-clarification-quick-20260715-004024/`

- 记录 tokens：1,219,615。
- 9 条 reviewer lease，相当于三个角色各经历三轮执行。
- 日志明确记录临时 ACL grant 和 controller-owned lease 语义澄清后的 corrective retry。
- Wall time：约 72.7 分钟。

该 run 说明输出 ACL、输入访问、lease 所有权和 retry 责任如果不由一个仓库自有 runner 统一管理，会把控制面问题放大成完整 reviewer 重跑。

### 4.4 多轮 Review 收敛性

VDD clarification cycle：

- Round 1：2 findings。
- Round 2：9 findings。
- Round 3：9 findings。
- 最终达到三轮硬上限并保持 blocked。

Repository Maintenance final-freeze cycle：

- Round 1：5 P1。
- Round 2：3 P1。
- Round 3：8 P1。
- 最终达到三轮硬上限并进入 manual pause。

结论：predecessor lineage 能防止轮次重置，但不能证明批量修复覆盖了上一轮 finding 的相邻控制面。下一轮启动前需要机器化 repair closure。

## 5. 根因分类

### RC-1：父进程访问能力不等于 reviewer token 访问能力

`prepare` 和 `authorize-launch` 可以由高权限父进程完成 hash 复核，但受限 `codex exec` token 仍可能在真正读取 artifact 时收到 `WinError 5`。

### RC-2：输入 artifact 与输出模板使用不同的 ACL 验证路径

当前 CLI 已考虑 reviewer 输出模板的 Modify 权限，但没有用同一受限 token 对全部输入 artifact 做 launch 前读取验证。

### RC-3：编排逻辑分散在每个 run 的临时脚本中

不同 run 使用不同的 PowerShell/Python helper、PID 文件、`.go` 文件和 retry 命名，导致 lease 释放、超时 reattach、输出原子写入和 fallback 处理不一致。

### RC-4：缺少 run 级终态和跨 run 索引

当前 CLI 能验证单个 sidecar，却不能直接列出一个 change cycle 的全部 run、当前权威 run、废弃 run、悬空 lease 和下一动作。

### RC-5：Round 2/3 缺少 repair closure 强制合同

新 round 要求 predecessor，但不要求机器证明上一轮 finding、修复引用、回归测试、相邻 mutation 与当前 candidate hash 已闭合。

### RC-6：成本估算没有反映多角色完整读取

当前 high-cost 条件使用单份 artifact 数量和单份总 bytes。Round 3 的 49 个 artifact 和 535 KB 没有触发 high-cost，但实际三个 reviewer 加 verifier 消耗约 706K tokens。

### RC-7：Probe 成本不可忽略

26 条 probe lease 合计约 61 个进程分钟，记录 token 约 1.20M。Probe 是必要安全控制，但当前没有受约束的跨 run 短期复用。

## 6. 修复目标

### G-1：更早失败

任何 artifact 访问、输出写入、模型、工具、authority 或 preflight 问题都必须在三个 reviewer 启动前暴露。

### G-2：单一执行协议

Probe、reviewer、verifier 的启动、lease、PID、stdin、fallback、timeout、reattach、输出和 validate-layer 由同一个仓库自有 runner 管理。

### G-3：证据可恢复

任意 run 都能被确定性归类，废弃和 supersede 使用 append-only sidecar，不修改历史 reviewer/verifier 决策。

### G-4：轮次可收敛

Round 2/3 启动前必须证明 predecessor finding 的批量修复和相邻回归覆盖。

### G-5：成本可解释

启动前报告基于有限历史样本校准的 token P50/P90、wall-time P50/P90、verifier likelihood、retry risk、样本量和置信度；该启发式只用于运营告警，不参与语义 authorization。

## 7. 不可削弱项

以下行为不属于允许的优化：

- 不得减少为单 reviewer。
- 不得让三个 discovery reviewer 共享 session 或提前读取彼此 candidate。
- 不得复用 discovery reviewer 作为 verifier。
- 不得降低 profile 规定的 artifact coverage。
- 不得允许 sampling。
- 不得降低 Edge Case Hunter、Acceptance Auditor 或 verifier 的既定 reasoning effort 来换取 green。
- 不得跳过 P0/P1 独立验证。
- 不得引入固定 finding 数量。
- 不得用 Bootstrap final result 替代 BH-HANDOFF 或生产 release authority。
- 不得改写历史 run 以清除 failed、stale、acquired 或 blocked 记录。

## 8. 修复方案

### P1-1：两级 Artifact Access Proof

不得声明运行平台无法证明的“相同 Windows token”。访问证明分两级：

1. Launch 前 identity-equivalent probe：使用相同 sandbox policy、workspace、model route、executable/config 和用户身份类别读取 manifest artifact 并复核 SHA-256。
2. Reviewer 同进程 access handshake：实际 reviewer child 在开始语义推理前调用 deterministic helper，读取本角色全部 Artifact View 项并返回 hash-bound handshake result。

Runner 只有在同一 child 的 handshake 通过后才允许传入语义任务。任一 artifact 缺失、拒绝访问或 hash 不符时，该 child fail closed 且不产生 candidate。

实施前先做 capability probe，确认 Codex CLI 能证明哪些 process/token identity 字段；schema 只能要求可观测、可复核的身份等价条件。

验收：构造父进程可读但 reviewer child 不可读的 fixture，identity-equivalent probe 或同进程 handshake 必须在语义推理前失败，正式 reviewer output 保持 pending，candidate 数量为零。

### P1-2：受控 Artifact View

先对 Codex Exec canary 启用 `artifact-view.v1`，不立即改变 manual 或 specialized-agent 模式：

```text
run-dir/artifact-view/
  manifest.json
  tree/<original-relative-layout>
```

Manifest 至少记录 original repository-relative path、snapshot path、双侧 SHA-256、size、encoding、line count、file type、binary/text、symlink/reparse-point、Windows case-normalized identity、context-class membership、source scope、creation hash 和时间。

控制要求：

- View 位于 run directory，不位于 reviewed scope，并保持原始相对目录结构。
- Reviewer 对 view 只读，对自己的 attempt output temp 只写。
- Reviewer 在一个 run 中不能同时读取 live original 和 snapshot。
- Gateway 把 snapshot evidence 投影回 original path 和 original line range。
- Original 与 snapshot bytes 不同立即失败；live original 后续漂移使 run stale。
- Windows 大小写冲突、junction/reparse escape 和 snapshot path collision 必须拒绝。
- Binary artifact 可以纳入 manifest，但不能生成文本 exact-evidence line range。
- 复制到 `logs/` 的敏感内容必须受 ACL、retention 和 archive contract 约束。

验收：Codex Exec canary 运行期间修改 live artifact，child 只能读取 frozen view；gate 仍必须根据 authority freshness 拒绝把 stale run 当作当前结果。

### P1-3：仓库自有 Layer Runner

新增稳定入口，例如：

```text
run-layer --run-dir <run> --role <role>
```

Runner v1 只服务 `codex-exec`。Manual 和 specialized-agent 继续保留外部执行边界，不能为了统一而变成隐藏 provider 调度。

交换协议：

```text
Codex child
  读取 Artifact View
  完成同进程 access handshake
  最终只输出结构化 candidate response

Runner
  捕获 last message/result file
  schema 与 binding 校验
  原子写入正式 reviewer/verifier output
  执行 validate-layer
```

模型不得直接覆盖正式 reviewer JSON。Runner 必须区分半写文件、child 成功但缺输出、retry attempt、并发写竞争和 stale attempt。

每次执行保存：

```text
process-events.jsonl
attempts/<attempt-id>/
  request.json
  process-result.json
  stdout.log
  stderr.log
  token-usage.json
  candidate-output.json
```

Append-only process events 是执行事实权威；`process-leases.json` 是可再生当前视图，不再作为唯一可变状态权威。Runner 不拥有 finding 接受、severity、gate、done、commit、handoff 或 release authority。

验收：删除所有 run-local helper 后仍能完成 Codex Exec probe、三个 reviewer、verifier 和 finalize；重复 operation 必须稳定拒绝；任何失败 attempt 不得覆盖先前 evidence 或正式 role output。

### P1-4：Run Lifecycle Index 与恢复命令

新增：

```text
list-runs [--change-id <id>]
inspect-run --run-dir <run>
seal-run --run-dir <run> --state abandoned|superseded --reason <code> [--successor <run>]
```

状态必须分维度：

```text
run_execution_state
  prepared | preflight-failed | authorized | layers-running |
  layers-incomplete | awaiting-verification | finalized | abandoned

run_relationship
  active | superseded | replaced-after-probe-failure

change_cycle_state
  review-required | repair-required | next-round-authorized |
  accepted | manual-pause | closed
```

一个 Round 3 run 可以同时是 `run_execution_state=finalized` 和 `change_cycle_state=manual-pause`。全局 index 只是可再生视图，不能成为新的状态权威。

`seal-run` 写一次性 immutable annotation：finalized 不能 seal 为 abandoned；superseded 必须引用 successor；sidecar 禁止覆盖；seal 不得修改 gate、reviewer、verifier、event 或 lease 历史；change-cycle manual pause 不能通过 seal 伪造。

验收：对本次 45 个历史 run 生成只读索引，必须得到 26 finalized、14 prepared/no-gate、3 awaiting-verification、2 incomplete，并显式标出 4 条 acquired lease。

### P1-5：Round 2/3 Repair Closure Gate

Round > 1 时要求 `repair-closure.json`，至少包含：

- predecessor run/input/result hash。
- predecessor finalized disposition 中全部 finding ID；confirmed/advisory/refuted 均不得从 exact set 消失。
- 每项 current disposition；需要修复的 finding 提供 fix refs 和验证命令，refuted finding 提供 no-action authority reference。
- 当前 candidate/source/validator hash。
- finding-family 对应的 closure proof 与相邻回归证据。
- 允许延期的 owner、severity、expiry 与 closure test。
- Git index 和 reviewed write-set drift 结果。

Canonical finding set 必须来自 finalized `review-gate-result.json` 与 `review-dispositions.json` 的联合，不得使用原始 reviewer candidate 或 pre-verifier gate-only state。

分两阶段验证：

- `prepare`：检查 closure schema、predecessor identity、finalized finding exact set、声明 evidence 路径和 proof-family 适配。
- `authorize-launch`：重新检查 evidence hash、candidate/source/validator hash、Git/index、write-set 和 context graph freshness。

Closure proof 按 finding family 选择：code/runtime defect 使用 failing test 或 targeted regression；schema/validator defect 使用 negative fixture 或 mutation；documentation/authority defect 使用 source-to-contract counterexample 或 exact predicate proof；ACL/process defect 使用 restricted-context execution fixture；P2 deferred 使用 owner、non-impact proof、expiry 和 closure test。不得强制所有 finding 伪造 mutation test。

该 gate 只证明 repair evidence 完整，不声称 finding 已被新一轮语义 reviewer 关闭。

验收：遗漏任一 finalized finding、proof family 不匹配、使用 stale candidate 或缺当前 freshness proof 时，Round 2/3 reviewer lease 数量保持为零。

### P2-1：历史校准的成本启发式

成本估算应增加：

- Estimated input range。
- Estimated total token P50/P90。
- Estimated wall-time P50/P90。
- Verifier likelihood band。
- Retry-risk class。
- Basis sample count 和 `confidence=low|medium|high`。
- Profile、reasoning、artifact count、bytes、文本/binary 比例、context-class fanout、round、代码/文档比例和历史 retry rate。

High-cost 不能只看单份 `totalBytes`，但 17 个带 token 记录的样本不足以训练精确预测模型。该启发式只提供运营告警和人工确认依据，不拥有语义 authorization。

验收：以 Round 3 的 49 artifact、535,333 bytes 为 fixture，启发式必须输出明显高成本告警、样本量、P50/P90 区间和置信度；不得要求精确预测不低于单一历史 run 的 705,767 tokens。

### P2-2：严格 Probe Cache

Probe Cache 延后到 runner、attempt/event 和 Artifact View 稳定之后。允许缓存模型/终端健康，不能缓存每轮 artifact access、preflight 或 authority proof。

Cache key：

```text
provider + endpoint/config hash + model + reasoning + sandbox +
Codex executable hash + non-secret credential identity + OS/build +
current user identity + tool-policy hash + network/proxy identity +
runner protocol version
```

要求：

- Success 使用短 TTL，failure 使用更短 TTL。
- Host、CLI、sandbox 或 credential source 变化立即失效。
- Artifact access probe、preflight 和 authority freeze 每个 run 必须新跑。
- 启用跨 run cache 会改变 profile 的 `toolProbeRequired` 语义，必须更新 policy revision 和所有权 ADR，不能只改 runner。

验收：相同 key 在 TTL 内不启动第二个模型健康 probe；任一 key 字段变化必须重新 probe。

### P2-3：误报抑制回归集

先把 6 个 verifier refute 分类为 deterministic gateway rule、role rubric、verifier fixture 或 profile-specific false-positive rule，不能全部直接扩成宽泛 prompt 指令。候选负例包括：

- 允许延期不等于缺少合同。
- Route-local 示例不等于完整 authority。
- Local block 必须与上层 merge/expansion guard 一起判断。
- 高层 reuse 摘要不能脱离完整 reuse predicate。
- 创建新 run 可以是合法恢复路径。
- EvidencePath 不自动意味着必须递归纳入所有引用文件，除非 profile 明确要求。

每个 refuted 负例必须配一个语义相近的 confirmed 正例，证明抑制规则不会吞掉真实 defect。现有 profile 已包含部分延期/阶段误报抑制，新增规则必须证明不是重复或过宽。

验收：负例不能产生 accepted P1；配对正例仍必须被发现，并保持相同 authority/context 读取要求。

### P2-4：日志摘要与保留策略

Finalized 或 sealed run 生成统一 `run-summary.json`，记录：

- 状态和下一动作。
- artifact/cost/profile/round。
- 每个 lease 的状态和耗时。
- token usage。
- retry、stale、ACL 和 drift 信号。
- gate/verifier/final result hash。

Raw stdout/stderr 不能被静默压缩或替换。压缩必须先定义：

```text
archive-manifest.json
  original_path
  original_sha256
  archive_path
  archive_sha256
  codec
  retained_until
```

只有全部消费者支持 archive mapping 后才能迁移；已被 manifest、lease 或 metrics 直接 hash-bound 的文件不能在原路径静默替换。敏感信息应优先在采集时避免写入或写入受控 raw evidence，再生成可公开的脱敏摘要；不得事后改写历史 evidence 来“清理”secret。

验收：索引和恢复命令无需解析 raw stdout/stderr 即可回答当前 run 状态、成本、失败原因和下一动作。

## 9. 实施顺序

### Phase 0：冻结基线

- 使用本提案的五文件审计包冻结 45-run 可复算基线和统计定义。
- 为 ACL failure、stale input、pending layer、failed lease、acquired lease 和 Round 3 manual pause 建立最小样例。
- 冻结当前 Skill、operator guide、profile registry、CLI 和 schema hash。
- 接受 Bootstrap Review Execution Control Plane Ownership ADR，并建立 durable standard。

### Phase 1：Runner 协议与最小实现

- 定义 runner request/response、attempt、process event、candidate output 和 atomic sidecar schema。
- 实施最小 Codex Exec layer runner。
- 明确 child 只返回结构化 candidate，runner 才能写正式 role output。
- 保持 manual/specialized-agent 外部执行边界。

### Phase 2：Artifact View 与实际访问证明

- 实施 Artifact View 和 original-path projection。
- 实施 identity-equivalent launch probe。
- 实施 reviewer 同进程 access handshake。
- 增加 Windows ACL、junction、reparse、case-insensitive collision、binary 和 atomic write 测试。

### Phase 3：生命周期与恢复

- 实施 list/inspect/seal。
- 生成全仓 run index。
- 分离 run execution、run relationship 和 change-cycle state。
- 把 process lease 作为 event-derived view。

### Phase 4：轮次收敛

- 定义 repair-closure schema。
- Round 2/3 在 prepare 和 authorize-launch 两阶段消费 closure。
- 加入 predecessor finding exact-set 和 current hash 验证。

### Phase 5：成本与运营

- 实施带样本量和置信度的成本启发式。
- Runner 稳定后再实施严格 probe cache，并更新 profile policy revision。
- 实施成对 false-positive/confirmed fixtures。
- 实施 run summary、archive manifest 和 retention contract。

### Phase 6：权威同步与独立 Review

- 把 7-12 CLI 收缩为 compatibility adapter，并同步 operator guide、CLI `--help`、profiles、schemas 和 regression tests。
- 更新仓库自有 Skill revision，再更新外部 `run-phase-bootstrap-review` 薄 Skill 的委托 revision。
- 在 `logs/ci` 建立 hash-equal Skill/route review snapshot。
- 使用 `bootstrap-skill-route` 运行一次完整独立 Review。
- 该 Review 结果仍是 supplemental Bootstrap evidence，不替代生产 authority。

## 10. 计划验收指标

实施完成后至少达到：

1. Artifact access handshake 失败时，child 不进入语义阶段，正式 candidate 数量为零。
2. 新 run 不再生成临时 runner、`.go` 或手工 PID 协议文件。
3. 每个 Codex child 都有且只有一个 append-only attempt/event lineage；lease 可从事件重建。
4. Finalized 或 immutable sealed run 不存在未解释的 acquired lease。
5. `list-runs` 能完整复现本次 45-run 基线，并分别输出三类状态维度。
6. Round 2/3 缺 repair closure 时在 prepare 阶段失败；evidence 漂移时在 authorize-launch 阶段失败。
7. 成本启发式能把 Round 3 量级识别为高成本，并输出样本量、P50/P90 和置信度。
8. Probe cache 不跨 provider/config/executable/user/tool-policy/network/runner drift 复用。
9. 六个 refuted 模式均有 paired confirmed fixture。
10. Artifact View 保持 original path、bytes、line 和 context-class 投影一致。
11. 三层 reviewer、完整覆盖、独立 verifier、零 finding 合法和三轮 hard limit 均保持不变。

## 11. 风险与待批准决策

### D-1：Artifact View 是否进入 Codex Exec canary

建议：有条件接受。改为受控 Artifact View，先仅用于 Codex Exec canary；manual 和 specialized-agent 不在第一批强制迁移范围。

风险：mapping、行号、binary、reparse、大小写冲突、敏感内容 ACL 或 retention 错误都会破坏 authority 投影。Gateway 必须强制 original-path projection。

### D-2：是否允许跨 run Probe Cache

建议：原则接受但延期。Runner、attempt/event 和 Artifact View 稳定后再启用，只缓存模型/终端健康，不缓存 artifact、authority 或 preflight 结论，并更新 profile policy revision。

风险：过宽 key 或 TTL 会把 provider/credential 漂移隐藏为旧成功。

### D-3：Layer Runner 的所有权

建议：拒绝原先“仓库 `tools/` 拥有”的宽泛表述。实施前必须接受框架级 ADR，并采用以下所有权：

```text
docs/standards/
  长期语义、权威和生命周期规范

docs/adr/
  Bootstrap Review Execution Control Plane Ownership

仓库自有 Skill/
  runner、schemas、artifact-view、attempt/event、
  repair-closure、inspect/list/seal 通用实现

7-12 execution-plan/
  兼容入口、迁移适配、plan-specific fixture

logs/
  append-only run、attempt、review 和审计 evidence

外部全局 Skill/
  revision-bound 薄路由
```

风险：Runner 不能演化成隐藏 provider scheduler，也不能拥有 reviewer 结论、gate 或 release authority。

### D-4：历史非终态 run 如何归档

建议：接受。新增 immutable annotation 和可再生索引，分离 run execution、run relationship 与 change-cycle state；不修改旧 sidecar，不删除 raw evidence。

风险：如果直接编辑旧 lease 或 gate state，会破坏本提案依赖的历史事实基线。

## 12. 下一步

本提案已由用户接受，并直接作为本轮优化的 approved intent source。下一步先接受框架级 `Bootstrap Review Execution Control Plane Ownership` ADR 和对应 durable standard，再直接更新仓库自有 Skill、外部薄路由和 7-12 compatibility adapter；不创建新的 VDD execution-plan，不向模糊顶层 `tools/` 或历史 run 目录追加权威能力。
