# 7-15 需求目录实施演化与完成报告

状态：第一部分已建立并记录至 2026-07-22；第二部分待实现完成后填写。

目标目录：`execution-plans/2026-07-15-repository-maintenance-tdd-adapter/`

## 1. 文档目的与维护规则

本文档承担两个用途：

1. 在实现完成前，持续记录需求目录因审核、验证、实际实施和恢复工作而发生的修改与优化，为后续迭代 VDD Skill 提供可复用输入。
2. 在实现完成后，记录整个 7-15 需求的实现结果、验证结果、遗留问题和最终结论。

第一部分是追加式演化记录。新发现不得通过改写旧失败证据来制造连续性；应新增事件、修复基线或旁路证据，并说明旧结论为何失效。第二部分只有在当前候选、S7 接受证据和最终结果信封同时满足时才能填写。

本文档是说明性报告，不是机器谓词、接受信封或授权制品。它不授权 `plan-ready`、`slice-ready`、`bootstrap-review`、`implementation-accepted`、受保护交接、发布、提交或完成。

## 2. 证据边界与记录方法

### 2.1 主要证据源

本记录优先使用以下仓库内持久证据：

- `logs/vdd-clarifications/2026-07-15-repository-maintenance-tdd-adapter-f6d1143a/**`
- `logs/vdd-plan-validation/repository-maintenance-tdd-adapter/**`
- `logs/vdd-plan-repair/repository-maintenance-tdd-adapter/**`
- `logs/tdd-adapter/repository-maintenance-tdd-adapter/RMAP-S0/**` 至 `RMAP-S7/**`
- `logs/ci/2026-07-22/**`
- `logs/design-reviews/**`
- `decision-logs/2026-07-21-rmap-vdd-creation-risk-log.md`
- `decision-logs/2026-07-21-rmap-replay-bootstrap-baseline.md`
- 当前需求目录内的 Markdown、machine contract、schema、fixture、guard 和测试。

外部反馈文件曾以 `C:/log/222.txt`、`444.txt`、`555.txt`、`999.txt`、`1200.txt`、`1300.txt`、`1400.txt`、`1600.txt` 等身份触发修复，但本文只引用已经复制到 `C:\jimuyun` 内的基线、澄清状态和验证结果，不把外部路径本身当作可恢复权威。

### 2.2 不作为完成权威的材料

- `logs/agent-worktrees/**` 只可用于诊断和差分重建，不能被追认为历史阶段当时实际消费的字节。
- 助手摘要、对话记忆和“曾经运行成功”的文字陈述不能替代当前 hash-bound 结果。
- 旧候选的 `pass` 只对其绑定的候选哈希、验证器版本和谓词有效；后续 contract、validator、authority 或候选变化会使它失效。
- `plan-ready` 仅证明当前计划在其威胁模型内可实施，不等于实现完成。
- Bootstrap Review 的结构验证通过不等于评审结论通过；`blocked/manual-pause` 不能被本地验证器重写。

### 2.3 状态词

- **已采纳并验证**：存在正常写入授权、修复结果和当前轮可复核验证。
- **修复已验证但仍阻断**：确定性修复通过，但更高谓词仍被人工暂停或外部授权阻断。
- **基线或 RED 已记录**：问题已被持久化，但没有同一修复 ID 下的独立闭环证据。
- **提案已批量修复**：设计提案及其反例验证通过，但尚不能视为目标实现完成。
- **仅草案**：澄清状态为 `draft_only`，不能当作已采纳需求。
- **历史通过，现已失效**：旧结果曾通过，但其候选、验证器或权威已发生变化。

## 第一部分：实施完成前的需求目录修改与优化记录

## 3. 总体演化概览

| 阶段 | 日期 | 核心变化 | 结果边界 |
| --- | --- | --- | --- |
| 初始创建 | 2026-07-15 | 从意图生成完整 VDD 目录、机器契约、fixture 和 11 项验证 | 当时 `plan-ready`，只证明初版静态自洽 |
| 三轮 P1 加固 | 2026-07-15 至 2026-07-16 | 权威、路径、退出证据、需求覆盖、shadow、review evidence 等控制面补强 | 确定性修复通过；第三轮进入 `manual_pause_after_round_3` |
| 执行协议补全 | 2026-07-16 至 2026-07-17 | 完整谓词控制链、Capsule、attempt ledger、候选 diff、跨切片 lineage | 计划验证从 11 项增长到 59 项，旧结果逐轮失效 |
| 信任与证明边界 | 2026-07-17 至 2026-07-19 | 七维 artifact proof、外部信任根、P2 typed evidence、威胁模型 | 防止计划内自证和同步刷新绕过 |
| 实施反馈与恢复 | 2026-07-19 至 2026-07-22 | 阶段证据投影、bootstrap baseline、多基线回放、S6 恢复模型 | S0-S5 有历史实施记录；S6/S7 当前完成性仍未建立 |
| 报告机制 | 2026-07-22 | 新增本文档，固化演化日志与最终报告入口 | 不改变任何机器谓词或完成状态 |

## 4. 逐轮演化台账

### EV-001：初始 VDD 创建与首个 plan-ready

**时间**：2026-07-15
**状态**：历史通过，现已被后续契约演化取代。

创建澄清经历 6 轮，最终置信度为 96，随后生成 7-15 完整目录。初版已经具备需求注册表、source coverage、spec delta、authority predicate、command registry、implementation contract、shadow 规则、fixture 和单元测试。

初版验证包含：

- `shell-true` 负例按 `RMAP-CMD-SHELL` 失败；
- `20260715-plan-ready-final/plan-ready.json` 对候选 `sha256:f1d6cde...` 返回 `pass`；
- 共运行 11 项单元测试；
- 结果明确排除 `slice-ready`、Bootstrap Review、实现接受、交接和发布。

**后续暴露的问题**：初版验证器只证明当时已经编码的规则，尚未覆盖真实执行中的 runtime authority、跨阶段退出证明、attempt lifecycle、候选累计 diff、多基线回放、外部信任根等问题。因此“初版 plan-ready”不是原始设计完全正确的证明。

**主要证据**：

- `logs/vdd-clarifications/2026-07-15-repository-maintenance-tdd-adapter-f6d1143a/clarification-20260715T094322Z/state.json`
- `logs/vdd-plan-validation/repository-maintenance-tdd-adapter/20260715-red-001/shell-true.json`
- `logs/vdd-plan-validation/repository-maintenance-tdd-adapter/20260715-plan-ready-final/plan-ready.json`

**给 VDD Skill 的教训**：创建期验证必须包含一次从干净、隔离环境执行的最小端到端切片演练；仅检查目录结构、字段和静态 fixture，不足以证明计划可实施。

### EV-002：P1 第一轮修复

**时间**：2026-07-15 至 2026-07-16
**状态**：已采纳并验证，后续结果因继续修订而失效。

第一轮 Bootstrap P1 反馈形成 10 个观察到的 RED 断言，其中归并为 5 类修复：

1. authority hash 必须绑定运行时实际字节，不能使用占位身份；
2. typed plan path 必须被约束在目录边界内；
3. S0 退出必须消费真实 TDD exit proof；
4. write set 与 forbidden set 的嵌套重叠必须 fail closed；
5. implementation contract schema 必须拒绝缺失 `plan_id` 等结构缺口。

修复落在 `implementation-contract.v1.json`、contract/authority/slice guards、schema、fixture 和测试中。修复后 19 项测试通过，`plan-ready` 在该候选上通过。

**主要证据**：

- `logs/vdd-plan-repair/repository-maintenance-tdd-adapter/20260716-p1-repair-baseline/red-tests-clean.txt`
- `logs/vdd-plan-repair/repository-maintenance-tdd-adapter/20260716-p1-repair-closure/closure-manifest.json`
- `logs/vdd-plan-validation/repository-maintenance-tdd-adapter/20260716-p1-repair-final/plan-ready.json`

**给 VDD Skill 的教训**：创建期应强制执行 runtime-bound authority、路径 containment、write/forbidden overlap、schema mutation 和每切片退出证明检查，而不是等审核发现。

### EV-003：P1 第二轮修复

**时间**：2026-07-16
**状态**：已采纳并验证，等待第三轮语义审核。

第二轮新增 3 类问题：

1. Windows 默认临时目录不可访问时，受控测试不能依赖环境偶然可用；
2. TDD exit proof 不应只验证 S0，必须覆盖后续 S1、S2 及所有切片；
3. source coverage 必须验证精确位置，不能只看需求 ID 是否出现。

修复增加受控临时目录和 junction 测试、全切片 exit proof 校验、source location drift 负例。22 项测试通过，S1/S2 在实现前仍能按预期 fail closed。

**主要证据**：

- `logs/vdd-plan-repair/repository-maintenance-tdd-adapter/20260716-p1-r2-repair-baseline/red-tests.txt`
- `logs/vdd-plan-repair/repository-maintenance-tdd-adapter/20260716-p1-r2-repair-closure/closure-manifest.json`
- `logs/vdd-plan-validation/repository-maintenance-tdd-adapter/20260716-p1-r2-repair-final/plan-ready.json`

**给 VDD Skill 的教训**：Windows temp、junction、reparse point、路径大小写和不可访问目录属于创建期平台矩阵，不应作为实现期临时补丁。

### EV-004：P1 第三轮修复与人工暂停

**时间**：2026-07-16
**状态**：修复已验证但仍阻断。

第三轮确认 8 类 P1 问题，主要覆盖：

- active slice 的 requirement coverage；
- junction containment 及复合验证环境；
- duplicate ownership；
- S6/S7 review evidence 与候选字节的显式绑定；
- shadow protected tree drift；
- P0/P1 未关闭与 P2 disposition 的权限边界；
- 缺失显式实现证据时的 fail-closed 行为。

修复后 25 项计划测试通过，且新增缺失 requirement、重复 ownership、shadow drift、缺失 review evidence 等负例。第三轮同时触发审核硬上限：`manual_pause_after_round_3` 生效，Round 4 未获授权。本地验证器只能证明确定性修复，不能宣布语义闭环。

**主要证据**：

- `logs/vdd-plan-repair/repository-maintenance-tdd-adapter/20260716-p1-r3-repair-closure/closure-manifest.json`
- `logs/vdd-plan-validation/repository-maintenance-tdd-adapter/20260716-p1-r3-repair-final/plan-ready.json`
- `schemas/review-blocking-state.v1.json`

**给 VDD Skill 的教训**：审核轮次状态必须与计划验证状态分离。确定性修复通过不能清除外部审核的人工暂停，也不能自动生成下一轮授权。

### EV-005：222 控制链整体修复与批量 review patch

**时间**：2026-07-16
**状态**：修复已验证但仍阻断。

该轮把前面分散的问题收束为完整控制链，新增或强化 9 类 mutation case：

- acceptance contract 缺失；
- authority manifest 缺少 `AGENTS.md`；
- candidate identity 不完整；
- clarification projection 指向日志路径；
- 人工暂停被清除或伪造 Round 4；
- RED stage 与 exit expectation 冲突；
- requirement quality 已过期；
- slice phase 与状态不一致。

随后一次完整 review patch 又批量处理 16 个发现族，包括 TOCTOU、scoped candidate identity、stage order、recovery lineage、candidate run artifact、trusted projection、command protocol、manual-pause projection、authority inventory、acceptance fixture binding、result schema 和 clean-checkout execution。两个超出边界的建议被拒绝：不重复处理 schema 已先行拒绝的畸形输入，也不在计划修复谓词内提前执行 S1/S2 产品语义。

本轮广泛修改了 00-08、96-99、implementation contract、authority/acceptance/clarification/review schema、guards、fixtures 和 tests。33 项确定性测试通过，但 `plan-ready` 继续被 `RMAP-REVIEW-MANUAL-PAUSE` 阻断。

**主要证据**：

- `logs/vdd-plan-repair/repository-maintenance-tdd-adapter/20260716-222-repair-closure/closure-manifest.json`
- `logs/vdd-plan-repair/repository-maintenance-tdd-adapter/20260716-222-repair-review-patch-closure/closure-manifest.json`
- `logs/vdd-plan-validation/repository-maintenance-tdd-adapter/20260716-222-repair-final-2/plan-repair-verified.json`

**给 VDD Skill 的教训**：VDD 创建器需要直接生成谓词权限格、候选身份、暂停/重入状态机和 clarification projection，而不是让各文件分别描述后再依赖人工对齐。

### EV-006：444 Capsule 与 attempt ledger 协议补全

**时间**：2026-07-17
**状态**：修复已验证但仍阻断。

实际准备运行 Adapter 时发现，初版对“上下文”和“重试”的描述不足以支撑恢复。该轮增加 RMAP-025/RMAP-026，并明确：

- 每次 backend invocation 使用不可变 Capsule revision；
- Capsule 之间通过 predecessor hash 串联，不能覆盖同一个文件；
- artifact ref 必须有 typed root，并与 context manifest 的去重并集完全一致；
- backend request/response 只持久化最小化、规范化 envelope 和原始字节哈希；
- adapter decision 本身不授权状态推进；
- attempt sequence 单调，decision 最后原子写入；
- partial attempt fail closed；
- 每个阶段只能有一条被接受的 attempt lineage。

增加的反例包括 stale Capsule context hash 和缺失 adapter decision。43 项测试通过，clean snapshot 投影通过，但普通 clean checkout 仍依赖上游权威字节落入其所属变更。

**主要证据**：

- `logs/vdd-plan-repair/repository-maintenance-tdd-adapter/20260717-444-capsule-ledger-baseline/repair-result.json`
- `logs/vdd-plan-validation/repository-maintenance-tdd-adapter/20260717-444-capsule-ledger-repair/plan-repair-verified.json`

**给 VDD Skill 的教训**：凡是计划要求重试、恢复或跨会话执行，就应在创建阶段定义不可变上下文 revision、attempt event chain、partial-write 行为和敏感信息持久化策略。

### EV-007：555 执行闭包与真实字节绑定

**时间**：2026-07-17
**状态**：修复已验证但仍阻断。

444 建立了 Capsule 和 ledger 形状，但仍可能只验证自报字段。555 进一步要求：

- typed Capsule ref 在 prepare、resume、S2 exit、S6 candidate validation 时解析并重算实际字节；
- S2/S6 退出必须具有严格的 RED、GREEN、REFACTOR accepted prefix；
- stage result、attempt decision、context manifest、Capsule hash 双向绑定；
- accepted、rejected、incomplete、superseded 事件遵守明确状态机；
- diff 从 baseline 和当前 worktree 独立重算；
- candidate 绑定 ledger manifest、原始 `run-events.jsonl` 哈希和最终 canonical event hash；
- S7 消费 repository-owned Bootstrap 生成的 finalized-run validation envelope。

计划测试增长到 48 项，Bootstrap Skill 测试为 87 项，whole-directory 和 Skill package 校验通过。由于该轮开始消费外部 Bootstrap producer，需求目录与 Bootstrap Skill 的 producer/consumer 契约产生明确耦合，但审核权仍归 Bootstrap，不归 Adapter。

**主要证据**：

- `logs/vdd-plan-repair/repository-maintenance-tdd-adapter/20260717-555-closure-baseline/baseline-manifest.json`
- `logs/vdd-plan-repair/repository-maintenance-tdd-adapter/20260717-555-closure-repair/verification-summary.json`

**给 VDD Skill 的教训**：创建期必须绘制所有外部 producer/consumer 边界。引用外部评审信封时，应先确认谁生产、谁验证、谁授权以及兼容版本，而不是在实现后补齐。

### EV-008：999 累积 candidate diff 与跨切片 lineage

**时间**：2026-07-17
**状态**：修复已验证但仍阻断。

早期实现只比较最终 attempt 或路径集合，无法证明重复修改、add-then-delete、untracked、binary 和跨切片累积效果。该轮改为：

- 从冻结 baseline 独立构建 versioned candidate diff manifest；
- 按路径折叠所有 accepted RED/GREEN/REFACTOR effect；
- 折叠结果必须与 tracked plus untracked Git 候选完全一致；
- rename 固定表示为 delete plus add，不依赖启发式检测；
- test patch 使用同一累计 manifest，并覆盖 CRLF、binary、delete 和 untracked tests；
- S6 与 S7 使用独立 run ID，S7 通过显式 `candidate_result_ref` 绑定 S6；
- 移除容易因无关提交过期的“当前 HEAD”文字断言。

51 项测试、11 个 mutation fixture、AST/JSON sweep、Windows untracked patch probe 和 `git diff --check` 通过。人工暂停仍保留。

**主要证据**：

- `logs/vdd-plan-repair/repository-maintenance-tdd-adapter/20260717-999-diff-lineage-baseline/baseline-manifest.json`
- `logs/vdd-plan-repair/repository-maintenance-tdd-adapter/20260717-999-diff-lineage-repair/verification-summary.json`

**给 VDD Skill 的教训**：多切片计划在创建时就要定义 baseline、effect fold、同路径连续变更和最终 Git 候选的等价关系。只记录“改了哪些文件”不足以支撑恢复。

### EV-009：1200 重入、supersession 与兼容输入修复

**时间**：2026-07-17
**状态**：修复已验证但仍阻断。

1200 基线保留 6 类缺口：

1. manual-pause successor contract 缺失；
2. cross-slice candidate lineage 缺失；
3. candidate supersession 可自我声明；
4. runtime P2 source evidence 未被消费；
5. 缺少真实 Git for Windows containment 集成；
6. 7-12 compatibility input 被错误提升为 policy authority。

修复后验证器增加 `RMAP-DOC-CURRENT-STATE`、protocol fixture、真实 Git/reparse 边界、successor/supersession 和 runtime evidence 校验。55 项测试通过，`plan-repair-verified` 为 pass，但 `plan-ready` 仍按预期被人工暂停阻断。

**主要证据**：

- `logs/vdd-plan-repair/repository-maintenance-tdd-adapter/20260717-1200-repair-baseline/baseline-manifest.json`
- `logs/vdd-plan-validation/repository-maintenance-tdd-adapter/20260717-1200-repair/closure-plan-repair-verified.json`
- `logs/vdd-plan-validation/repository-maintenance-tdd-adapter/20260717-1200-repair/closure-plan-ready.json`

**给 VDD Skill 的教训**：兼容性输入与当前权威必须显式分层；supersession 状态必须由外部 lineage/recovery evidence 推导，不能由候选自报。

### EV-010：1300 七维 artifact proof 模板

**时间**：2026-07-17
**状态**：修复已验证但仍阻断。

1300 基线说明，55 项测试仍接受空 policy decision 和字段不足的 finalized envelope。该轮保留并修复 6 类问题：

- re-entry pseudo evidence；
- slice effect 自我断言；
- baseline 引用未来路径；
- lineage 字段碰撞；
- P2 verifier 的传递绑定不足；
- capability lifecycle 不完整。

为 12 类关键制品建立统一的七维证明：

1. schema/producer authority；
2. immutable identity；
3. source-of-truth derivation；
4. independent recomputation；
5. staleness propagation；
6. recovery/supersession；
7. consumer/authorization boundary。

artifact proof validation 的 12 项证明和七个维度均通过，计划测试增长到 59 项。该证明本身 `authorizes: []`，只供具体谓词消费。

**主要证据**：

- `logs/vdd-plan-validation/repository-maintenance-tdd-adapter/20260717-1300-repair/baseline-manifest.json`
- `logs/vdd-plan-validation/repository-maintenance-tdd-adapter/20260717-1300-repair/artifact-proof-validation.json`
- `logs/vdd-plan-validation/repository-maintenance-tdd-adapter/20260717-1300-repair/closure-plan-repair-verified.json`

**给 VDD Skill 的教训**：高保证、自托管或会生成授权证据的计划，应在创建时使用统一 artifact proof 模板；普通低风险计划不应无条件继承全部七维成本。

### EV-011：1400 独立性与 typed evidence 再加固

**时间**：2026-07-17
**状态**：修复边界已确认；该修复 ID 下没有单独的完整闭环信封，后续由 1500 及以后证据继续收口。

1400 确认 4 个 P0 问题：

- S7 与 Bootstrap v2 envelope 不兼容；
- successor authorization 仍可能是 pseudo evidence；
- P2 evidence 未完全类型化；
- artifact proof 的“独立重算”实际仍由计划内对象自证。

确认的方向是：Bootstrap 拥有 successor authorization 和 typed P2 语义；artifact contract 与 validator 自身不授权；所有 review-added artifact 使用七维 proof；确定性修复后只能进入一个新的独立语义周期，不能伪装成 Round 4。

**主要证据**：

- `logs/vdd-plan-validation/repository-maintenance-tdd-adapter/20260717-1400-repair/baseline-manifest.json`
- `logs/vdd-clarifications/2026-07-15-repository-maintenance-tdd-adapter-f6d1143a/clarification-20260717T134500Z/state.json`

**给 VDD Skill 的教训**：生成证明的验证器不能同时成为证明的最终信任根。创建器应检查“谁验证验证器”和 null-predecessor 信任链。

### EV-012：1500 profile-bound 信任根与 bounded successor cycle

**时间**：2026-07-18
**状态**：已采纳并验证。

为消除计划内自签和伪 successor，新增或明确：

- review profile 绑定的 Bootstrap authority-root registry 是唯一允许的 null-predecessor root；
- P2 command 绑定 executable、argv、cwd、runner、policy hash；
- process success 从 append-only execution events 重算；
- Round 3 历史证据保持不可变，只更新 successor selector；
- 只允许一个有界 successor closure cycle；
- 未取得认证 GitHub API 证据时，GitHub CI 必须标记为 unconfirmed，不能用本地测试冒充。

过程中曾出现一次 60 项测试中的失败，随后修复 Capsule ref mismatch 和未捕获 bootstrap failure；最终 61 项测试及 `plan-ready-pass.json` 通过。

**主要证据**：

- `logs/vdd-plan-repair/repository-maintenance-tdd-adapter/20260718-1500-trust-root-repair/partial-finding-repair.json`
- `logs/vdd-plan-repair/repository-maintenance-tdd-adapter/20260718-1500-trust-root-repair/plan-repair-verified-pass.json`
- `logs/vdd-plan-repair/repository-maintenance-tdd-adapter/20260718-1500-trust-root-repair/plan-ready-pass.json`

**给 VDD Skill 的教训**：外部 CI、签名、review root 和本地确定性验证必须分开建模；不可用证据的正确状态是 unconfirmed，而不是推断 pass。

### EV-013：1600 artifact proof oracle 反例修复

**时间**：2026-07-18
**状态**：基线或 RED 已记录；此前 1500 的 plan-ready 被明确标记为 stale。

1600 通过 7 个反例证明，当时的 proof oracle 仍未拒绝：

- forged producer；
- self-refreshed identity；
- unrelated derivation source；
- unknown rule；
- empty invalidation；
- missing predecessor lineage；
- empty consumer。

基线明确把 1500 的 `plan-ready-pass.json` 标记为 `stale-after-artifact-proof-oracle-repair`。这说明“上一轮通过”不能跨 validator 语义升级继承。

**主要证据**：

- `logs/vdd-plan-repair/repository-maintenance-tdd-adapter/20260718-1600-artifact-proof-closure/baseline.json`
- `logs/vdd-clarifications/2026-07-15-repository-maintenance-tdd-adapter-f6d1143a/clarification-20260718T160000Z/state.json`，该轮后来被 supersede。

**给 VDD Skill 的教训**：每次 validator 或 oracle 语义变化，都必须自动使旧 pass 结果失效，并要求新候选重新验证。

### EV-014：1700 外部信任根与 predecessor lineage

**时间**：2026-07-18
**状态**：正常修复授权已记录；基线保存 RED，未找到同名独立闭环文件。

1700 继续证明计划本地 registry 可以通过同步刷新 manifest/proof 来提升权限，并且 predecessor 断裂、错误或过期的 lineage 没有被拒绝。修复方向是把 authority identity 终止到 plan 外、profile-bound 的 Bootstrap root，并要求完整 predecessor chain。

**主要证据**：

- `logs/vdd-plan-repair/repository-maintenance-tdd-adapter/20260718-1700-external-trust-root/baseline.json`
- `logs/vdd-clarifications/2026-07-15-repository-maintenance-tdd-adapter-f6d1143a/clarification-20260718T170000Z/state.json`
- `.agents/skills/run-phase-bootstrap-review/references/authority-roots.v1.json`

**给 VDD Skill 的教训**：计划内 registry 只能投影权限，不能创造自己的最高权限；自刷新后的内容寻址并不等于独立信任。

### EV-015：plan-ready 威胁模型与七维适用规则

**时间**：2026-07-19
**状态**：已采纳。

后续澄清把先前不断扩张的安全目标收敛到明确边界：

- `plan-ready` 保护 workflow integrity，拒绝 forged、stale、self-validating 和 over-authorizing evidence；
- 网络攻击、host operations compromise 和恶意 Administrator 不属于 plan-ready 威胁模型；
- 外部独立身份只保留给 protected handoff 和 release；
- 形式化授权制品必须有机器可检查的七维结论；
- 只有 artifact type 明确允许且 reason code 可验证时，某维度才能为 N/A。

这次优化避免把“无法抵抗完全受控主机”错误设为普通计划可实施性的前置条件。

**主要证据**：

- `logs/vdd-clarifications/2026-07-15-repository-maintenance-tdd-adapter-f6d1143a/clarification-20260719T053528Z/state.json`
- `logs/vdd-clarifications/2026-07-15-repository-maintenance-tdd-adapter-f6d1143a/clarification-20260719T100233Z/state.json`
- 当前 `00-index.md` 的 protected-state blocker 和 validation 说明。

**给 VDD Skill 的教训**：创建期必须先选择 assurance profile 和 threat model。没有这一层，验证器会无限吸收超出目标的安全要求。

### EV-016：阶段证据投影与未采纳的 S0 草案

**时间**：2026-07-19 至 2026-07-20
**状态**：阶段投影已实施；同日 S0 repair 澄清仅为 `draft_only`，不可当作已采纳方案。

实际实施发现旧 stage result 不满足新的 candidate lineage consumer。为 S0-S5 增加 stage evidence projection schema、builder、guard 和测试，把既有 RED/GREEN/REFACTOR 结果投影为可验证的阶段证据，并保存修复前基线。

同时，`repair-20260719T143500Z` 提出了限制 S0 projection producer 输出、保留失败尝试并重新运行 RED 的方案，但其 5 个问题均保持 open，写入处置为 `draft_only`。因此本文只记录它是未采纳尝试，不用它证明 S0 完成。

**主要证据**：

- `logs/vdd-plan-repair/repository-maintenance-tdd-adapter/20260720-stage-evidence-projection-baseline/baseline-manifest.json`
- `schemas/stage-evidence-projection.v1.schema.json`
- `tools/stage_projection_builder.py`
- `tools/tests/test_stage_projection_guards.py`
- `logs/vdd-clarifications/2026-07-15-repository-maintenance-tdd-adapter-f6d1143a/repair-20260719T143500Z/state.json`

**给 VDD Skill 的教训**：证据格式升级必须在计划里包含迁移策略。对已执行切片进行 post-hoc projection 时，投影只能转写已有事实，不能发明缺失生命周期。

### EV-017：S0-S5 实施反馈与共享 schema 归属调整

**时间**：2026-07-19 至 2026-07-21
**状态**：实现反馈已持久化；当前目录反映了归属调整，但最终实现尚未接受。

S0-S5 在多个运行目录中形成 RED/GREEN/REFACTOR 与 recovery state。S1 实施还把共享 Adapter protocol schema 的所有权从计划本地副本迁移到 `.agents/skills/quick-dev-tdd-adapter/schemas/**`。当前目录删除重复 schema，并从 `00-index.md` 和 guards 引用 Skill-owned contract，以减少未来需求目录复制和漂移。

该调整说明原始计划把“本计划的 self-hosted instance”和“所有未来计划共用的 protocol schema”放在了同一目录，所有权边界不够清晰。迁移后，本目录保留自己的 implementation instance、candidate/lineage/replay 等计划专属 schema，共享 runtime protocol 归 quick-dev TDD Adapter Skill 所有。

**主要证据**：

- `logs/tdd-adapter/repository-maintenance-tdd-adapter/RMAP-S0/**` 至 `RMAP-S5/**`
- 当前 `00-index.md` 的 Machine Owners；
- 当前工作树中删除的计划本地 `adapter-decision`、`backend-request`、`slice-capsule` 等重复 schema；
- `.agents/skills/quick-dev-tdd-adapter/schemas/**`。

**给 VDD Skill 的教训**：创建时区分“plan-owned instance”和“shared protocol owner”。共享 schema 不应复制到每个需求目录，否则实现一开始就会发生迁移。

### EV-018：S6 回放失败与 replay bootstrap baseline

**时间**：2026-07-21
**状态**：问题和决策已持久化；不等于 S6 完成。

S6 回放检查暴露 4 个创建期问题：

1. 计划要求从 Git `HEAD` 回放 S0-S6，但 S1 以后需要的 Adapter runtime asset 不在该基线内；
2. S0 RED 预期只有 ownership failure，却同时校验由 S0 GREEN 才产生的 authority/source bytes；
3. 当前 scoped Git diff 必须等于累计 slice-effect fold，但旧阶段投影没有覆盖所有实际 worktree change；
4. 相邻切片使用不同 frozen baseline，而原 lineage model 假设单一全局 baseline。

因此增加 replay bootstrap baseline 决策：允许在隔离 worktree 中，从 hash-bound、独立授权的 source-derived baseline 初始化运行；该 baseline 不属于任何切片，不进入 candidate diff，也不授权任何完成谓词。

**主要证据**：

- `logs/tdd-adapter/repository-maintenance-tdd-adapter/RMAP-S6/RUN-20260721T081500Z/candidate-lineage-mismatch.v1.json`
- `logs/tdd-adapter/repository-maintenance-tdd-adapter/RMAP-S6/RUN-20260721T081500Z/candidate-replay-scope.v1.json`
- `decision-logs/2026-07-21-rmap-vdd-creation-risk-log.md`
- `decision-logs/2026-07-21-rmap-replay-bootstrap-baseline.md`
- `schemas/replay-baseline-manifest.v1.schema.json`
- `tools/replay_baseline_guards.py`

**给 VDD Skill 的教训**：在生成“可回放”计划前，必须审计 Git tracked/untracked、runtime prerequisites、RED 前置依赖和相邻切片 baseline。RED 依赖 GREEN 写入属于创建期硬错误。

### EV-019：S6 恢复模型重构、目录优化与三轮提案修复

**时间**：2026-07-22
**状态**：目录确定性回归通过；提案审核为 `blocked/manual-pause`；目标实现仍未由此完成。

为避免继续生成 `rmap-b` 至 `rmap-e` 诊断副本并循环，恢复策略综合 5 种分析：authority trace、历史证据盘点、隔离 worktree 差分重建、counterexample/mutation、时间与控制面状态机。结论是：

- archive copy 只能诊断，不能被恢复时追认为历史前后快照；
- legacy exact revalidation 必须依赖历史运行当时已经提交的 before/after closure 和 event-bound lifecycle；
- 缺失历史生命周期时只能 whole-slice replay，且 replay 必须有 root-authorized source-derived predecessor baseline 和 replay decision；
- baseline bridge 只能证明相邻 identity 连续，不能创造缺失生命周期；
- S6 candidate qualification 与 Bootstrap process launch 分离；
- S6 只产生可送审候选，S7 才能消费 finalized envelope 并授权实现接受；
- trust-root generation 发布必须通过 crash-consistent lease journal 和原子 generation pointer；
- 无法精确重验且没有合法 replay baseline 时必须停止，不能合成证据。

目录层面的优化包括：

- 新增 `candidate-baseline-bridge.v1.schema.json`、`replay-baseline-manifest.v1.schema.json` 和 `stage-evidence-projection.v1.schema.json`；
- 新增 `candidate_builder.py`、`candidate_lineage_builder.py`、`replay_baseline_guards.py` 和 `stage_projection_builder.py`；
- 增加对应 candidate baseline bridge 与 stage projection 测试；
- 更新 `00-index.md`、02、03、04、implementation contract、authority/proof registry、fixture 和 guards；
- 新增 `schemas/reentry-successor-20260722/**`，在不改写旧 Round 3 的前提下投影新的重入身份；
- 把共享 protocol schema 的读取切换到 quick-dev TDD Adapter Skill owner。

第三轮提案审核最终为 `blocked/manual-pause`，确认 6 个 finding 和 1 个 deferred finding。随后一次性批量修复全部 7 项，增加 29 个精确 clause mutation case。结构、authority、cases 验证通过，当前 7-15 `plan-ready` regression 运行 93 项测试且无 diagnostics。

这些结果只证明优化后的提案和当前计划目录具备确定性自洽性。三轮硬上限已到，未启动 Round 4；它们不授权 S6、S7、实现接受或完成。另一个 replay Bootstrap 尝试只完成 preflight，reviewer 状态仍含 pending/failed，没有形成可用于 S7 的 finalized acceptance envelope。

**主要证据**：

- `logs/design-reviews/2026-07-22-rmap-s6-recovery-proposal.md`
- `logs/design-reviews/2026-07-22-rmap-s6-recovery-batch-repair-evidence.v1.json`
- `logs/design-reviews/2026-07-22-rmap-s6-recovery-repair-cases.v1.json`
- `logs/ci/2026-07-22/rs6p4/validation-envelope.json`
- `logs/design-reviews/2026-07-22-rmap-s6-recovery-plan-ready-regression.json`
- `logs/ci/2026-07-22/review-gateway-bootstrap-repo-maint-tdd-replay-r1-20260722/**`

**给 VDD Skill 的教训**：恢复模型必须在创建阶段设计，不能等协议升级后尝试把旧日志“补成”新证据；Review 应验证设计，不应充当无限循环的需求发现引擎。

### EV-020：建立实施演化与完成报告入口

**时间**：2026-07-22
**状态**：已采纳。

新增本文档，原因是现有 `96-global-review-and-validation.md` 只规定最终 reporter 必须报告命令、退出码、测试数、证据路径、当前哈希、遗留缺口和变更文件，没有保存整个需求目录在实施前后的演化历史。

本次写入只新增说明性文档，不修改 `00-index.md`、machine contract、schema、authority projection 或历史 evidence，避免仅为导航而使当前候选哈希和证明链产生额外迁移。后续实现前的需求优化应追加新的 `EV-NNN` 条目。

**主要证据**：

- `logs/vdd-clarifications/2026-07-15-repository-maintenance-tdd-adapter-f6d1143a/clarification-20260722T044421Z/state.json`
- 本文档。

## 5. 跨轮根因归纳

### 5.1 原始文档不是整体错误，但可实施性定义过窄

初版已经正确表达了核心产品方向：stateless Adapter、observed RED、受限 GREEN/REFACTOR、不可变证据、Bootstrap-only review authority 和 S7 acceptance。但它把“计划结构和静态契约自洽”近似成了“完整可实施”，没有在创建期证明干净回放、跨切片 lineage、旧证据升级和外部信任链。

因此后续多数问题不是产品目标反复变化，而是原来未被机器化表达的执行、恢复和授权边界逐层显现。

### 5.2 验证器与需求同时演化，导致每次 pass 只能局部成立

测试数从 11、19、22、25、33、43、48、51、55、59、61 增长到 93。每次增加 rule、fixture 或 oracle 后，旧 `pass` 都可能失效。这是正确的 freshness 行为，但也说明初次 `plan-ready` 前没有完成足够的验证器覆盖设计。

### 5.3 历史证据格式升级缺少预先设计的兼容策略

S0-S5 执行期间，Capsule、attempt ledger、stage projection、candidate diff 和 lineage contract 持续增强。旧运行并非一定“行为没发生”，但缺少新 consumer 所要求的历史生命周期和身份，不能自动继承完成状态。后续被迫在 exact revalidation、whole-slice replay 和 fail-closed stop 之间重新决策。

### 5.4 review、计划修复、候选构建和实现接受曾发生职责混淆

部分轮次把 Bootstrap Review 当作计划设计发现器或实现继续条件，导致 manual pause 与 S6 candidate construction 互相缠绕。优化后的职责是：

- VDD/plan validator：证明计划和确定性契约；
- TDD Adapter：执行切片并形成候选；
- Bootstrap control plane：决定是否启动独立语义审核；
- S7：消费绑定候选的 finalized envelope 并决定实现接受。

### 5.5 自托管证明链造成复杂度快速增长

7-15 不只是普通功能计划，它同时设计执行协议、证据格式、验证器、评审输入和恢复模型。验证器又验证自己的授权输入，因此必须引入 external trust root、七维 artifact proof、successor policy 和 crash-safe publication。该复杂度对本需求有原因，但不应无差别复制到普通 VDD 目录。

## 6. 对 VDD Skill 的迭代建议

### 6.1 创建期必须新增的硬门

1. **Repository baseline audit**：列出 scoped tracked、untracked、ignored runtime asset、必要工具和来源身份。
2. **Clean replay probe**：在隔离目录从声明基线至少运行一个代表性 RED 到 exit 的 dry run。
3. **RED prerequisite audit**：拒绝依赖同切片 GREEN 或未来切片写入的 RED/hash check。
4. **Predicate permission lattice**：为每个谓词固定 `authorizes`、`does_not_authorize`、owner、consumer 和 predecessor。
5. **Evidence lifecycle contract**：涉及恢复时，预先定义 Capsule revision、attempt event、partial write、accepted prefix 和 terminal identity。
6. **Cross-slice lineage**：明确单基线还是多基线、同路径连续 transition、baseline bridge 和最终 Git diff 等价。
7. **External dependency map**：为 review、CI、签名、runtime producer 建立 authority/compatibility/diagnostic 三分法。
8. **Platform matrix**：Windows temp、junction、reparse、case identity、CRLF、binary、untracked 和 path containment 必须有 fixture。
9. **Evidence migration policy**：新 schema 上线时，预先规定 legacy exact revalidation、whole replay 或 stop，禁止 post-hoc fabrication。
10. **Freshness invalidation**：validator、authority、candidate 或 closure definition 变化时，自动废止旧 pass。
11. **Review budget**：审核发现应批量修复；三轮硬上限与 successor policy 在创建期固定，禁止逐 finding 启动 review。
12. **Evolution report**：高风险目录创建时自动生成本类日志文档，实施过程只追加，不依赖对话记忆。

### 6.2 应加入的复杂度控制

VDD Skill 不应把 7-15 的全部控制面复制给所有需求。建议按风险选择 profile：

- **standard**：普通单仓功能，使用基础 requirement、acceptance、test 和 rollback 证据；
- **recovery-aware**：跨会话、可重试或多切片任务，增加 Capsule、attempt lineage 和 baseline migration；
- **high-assurance/self-hosted**：会生成授权证据、验证器或 review control plane 的任务，才要求七维 artifact proof、外部信任根和 successor policy。

创建器应给每个新增 schema、guard 和 proof 一个明确 consumer。没有实际 consumer 或不能改变任何谓词结果的制品，应拒绝加入，避免把“更多证据”误认为“更安全”。

### 6.3 应加入的停止与升级条件

- 同一根因连续两轮只产生更细字段时，应暂停并重新检查整体执行模型。
- 如果修复需要追认历史中不存在的时间身份，应停止，不得继续生成 archive 或 projection。
- 如果一个计划同时修改业务实现、执行协议和 review policy，应拆分 ownership，或明确一个有界 migration gate。
- 如果计划实施超过预设时间且主要工作变成修计划本身，应触发 correct-course，而不是继续按原切片计数。
- 完成状态只由当前 acceptance envelope 推导，不能从“之前已经完成过”或助手总结继承。

## 7. 已知记录限制

1. 当前工作树包含大量未提交且互相叠加的用户与实现改动，不能用 Git commit history 单独恢复每一轮文件差异。各轮 `baseline-manifest.json` 和 `closure-manifest.json` 是文件级精确清单的首选来源。
2. 部分 1400、1600、1700 修复只有基线、澄清状态或后继闭环，没有同名最终 closure 文件。本文按证据强度标为“基线/方向已记录”，没有补写不存在的成功结论。
3. `repair-20260719T143500Z` 为 `draft_only`，不能转化为已采纳 S0 修复。
4. S0-S5 的历史运行和 stage projection 证明有实施事实，但不自动满足后来升级的完整协议。
5. S6 的旧 candidate-result `pass` 绑定旧候选和旧 consumer；S7 当前没有可用于本报告第二部分的有效最终接受结论。
6. 2026-07-22 的 S6 recovery proposal 在三轮后仍为 `blocked/manual-pause`；批量修复和 93 项计划测试不改变该审核事实。

## 8. 当前重新实施记录

### IR-001：重新实施基线与 S0

**时间**：2026-07-22
**状态**：进行中；仅 S0 已由当前候选重新验证通过。

- 实施前基线提交：`aa1afef feat: establish RMAP TDD adapter baseline`。
- 当前候选：`sha256:06192a01fe0110936864da6f4be0fd0e3d0718c64474051f52e667ca9ab5e92c`。
- S0 运行：`rmap-s0-replay-20260722T084218Z-7d340688a7d7`。
- S0 RED：`rmap-observe-ownership-red` 返回 `1`，观察到声明的 duplicate-ownership 负例。
- S0 GREEN：`rmap-s0-preflight` 返回 `0`。
- S0 REFACTOR：`rmap-validator-tests` 与 `rmap-s0-preflight` 均返回 `0`。
- S0 `slice-ready`：通过；最终 validator 运行 94 项测试且无诊断。

证据根：`logs/tdd-adapter/repository-maintenance-tdd-adapter/RMAP-S0/rmap-s0-replay-20260722T084218Z-7d340688a7d7/`。

### IR-002：S2 RED 合同修复与重新实施基线刷新

**时间**：2026-07-22
**状态**：已验证；重新实施尚未完成。

- 缺陷：S2 的 RED 与 GREEN 同时声明 `rmap-adapter-tests`。该命令在已实现状态返回 `0`，没有受控负例，因此无法在不篡改测试或实现的前提下观察声明的 RED。
- 修复：新增 shell-free 的 `rmap-observe-adapter-red`。它通过既有适配器状态机在 GREEN 之前请求 RED，稳定输出 `RMAP-TDD-RED-NOT-OBSERVED` 并以 `1` 退出；S2 GREEN/REFACTOR 仍使用 `rmap-adapter-tests`。
- 覆盖：新增探针自身测试和独立的 S2 命令差异合同测试；为保持结构上限，将该合同测试置于独立文件，`test_plan_validator.py` 保持 400 行以内。
- 派生物：已运行 `tools/refresh_projections.py`，使 authority、spec delta 和 artifact closure 投影重新绑定当前文件身份。
- 验证：完整计划测试 `95` 项通过（`179.265s`）；`plan-repair-verified` 通过（`189.199s`）；`plan-ready` 通过（`180.952s`）。
- 当前候选：`sha256:688a991e253d928dc8c332fea4b1643e8aacdd3281732103bba8737ba4cd5dfc`。
- 影响：IR-001 中基于旧候选 `sha256:06192a...` 的 S0 运行，以及修复前 S1 重放，只保留为历史事实，不能作为当前重新实施的 `slice-ready` 证据。修复提交后必须从 S0 开始重新执行。

### IR-003：验证器运行预算修复

**时间**：2026-07-22
**状态**：已验证；重新实施尚未完成。

- 缺陷：`rmap-validator-tests` 注册的 `timeout_seconds` 为 `120`，而当前完整计划测试在本机连续三次的实际运行时间为约 `180` 至 `189` 秒。S0 的 REFACTOR 依赖该命令，保留 120 秒会必然产生外部超时，无法形成有效 REFACTOR。
- 修复：将 `rmap-validator-tests` 的注册预算调整为 `300` 秒；命令、测试选择器和任何授权谓词均未改变。
- 派生物与验证：已刷新投影；`plan-ready` 通过，95 项测试在 `179.919s` 内通过。
- 当前候选：`sha256:70e719f2fc7d768b2cb30602c7ee3c0ecc4c76292b224b2c3aeb08c674b6a212`。
- 影响：IR-002 后的候选再次变化；必须在该候选对应的干净 Git 基线上开始 S0，不能混用此前的 S0/S1 证据。

## 第二部分：实现完成后的整体报告

状态：**待填写**。

现有 [96-global-review-and-validation.md](96-global-review-and-validation.md) 只定义最终报告的最低字段，没有提供完整的实施后报告，因此本部分保留。

### 填写前置条件

只有同时满足以下条件后才能填写：

1. S0-S7 的当前状态均由当前 contract 和 validator 可复核；
2. S6 当前候选绑定完整 S0-S6 lineage，且不是旧候选的无依据继承；
3. Bootstrap implementation-conformance review 具有当前、完整、hash-bound finalized envelope；
4. S7 的 `implementation-accepted` 谓词通过；
5. 受保护交接和发布若仍阻断，必须明确列为 residual gap，不能隐藏在“实现完成”中；
6. 最终报告引用的命令、退出码、测试数、证据路径和哈希均为当前结果。

### 最终报告必须包含

- 实现范围与非目标；
- S0-S7 最终状态表；
- 最终候选身份、baseline 和 lineage；
- 实际变更文件及 ownership；
- 执行过的命令、退出码和测试数；
- RED/GREEN/REFACTOR、候选审核和 S7 接受证据；
- 兼容性、迁移和恢复结果；
- 未解决问题、受保护交接和发布状态；
- 与原始需求相比的最终偏差；
- 是否完成的明确结论及其授权边界。

在这些条件满足前，本部分不得根据旧 `pass`、提案验证、计划可实施性或助手陈述预填“完成”结论。
