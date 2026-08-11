---
title: '修复 Skill 输入消费协议的子进程边界与完整交付'
type: 'bugfix'
created: '2026-08-11'
status: 'done'
baseline_commit: 'b064b689222a7eec039f5a7032e7a7f1c3ddbbc4'
review_loop_iteration: 0
context:
  - 'C:/jimuyun/docs/skill-input-consumption-contract.md'
  - 'C:/jimuyun/AGENTS.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 协议的核心门禁已经存在，但语义子进程的 execution identity、只读快照边界和输出脱敏没有被机制化绑定；Markdown 引用闭包可能漏源；Bootstrap Review 与 Refactor Acceptance 只保存 context hash，没有把 context artifact 交给后续权威阶段。现状可能让不完整或不可信的输入通过 ready，且无法证明四个 Skill 真正消费了同一份语义上下文。

**Approach:** 在共享 launcher 中统一构造并验证实际执行身份，使用只读快照和受限能力，校验子进程输出中的 credential-like 值；补全 Markdown 引用解析并对不可解析引用 fail closed；让两个消费者显式传递 context artifact；增加真实 producer/consumer 组合测试。二进制 parser v1 能力与文档保持一致，当前未声明 parser 的 binary 继续 fail closed。

## Boundaries & Constraints

**Always:** 保持现有 receipt、manifest、context、decision Schema 兼容；保持 `authorizes=[]`、日志不得作为恢复源、路径和哈希 fail-closed；不修改 `_llm_backend.py` 的共享入口；测试不得通过禁用 gate 或放宽校验来通过。

**Ask First:** 若实际 Codex CLI 不支持所需的进程级只读/工具限制，暂停并报告可实现的最小替代边界，不擅自改变安全契约。

**Never:** 不把原始快照、日志或 rollout 返回主上下文；不提交 token/secret；不改动 live Phase 状态、数据库、运行时启动配置或历史证据。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|-----------------------------|----------------|
| 实际身份不匹配 | request identity 与实际 backend/model/sandbox 不同 | child 不启动，receipt 不可 ready | 明确 identity binding failure |
| 子进程修改快照 | child 返回前改变 snapshot 文件或 manifest | 结果拒绝，原始绑定保持 candidate | snapshot drift / capability failure |
| 输出含 credential-like 值 | context/rationale/decision 含 Bearer、token、password 等值 | sidecar 不发布，receipt 不可 ready | output redaction failure |
| 引用式 Markdown | `[text][id]` 与 `[id]: path` | 引用文件进入同一 manifest | 无法解析或目标缺失则 fail closed |
| Bootstrap/Acceptance 消费 | ready receipt 含 context artifact | 权威阶段收到并绑定 artifact 路径与 hash | 缺失或漂移阻断 |

</frozen-after-approval>

## Code Map

- `scripts/python/launch_skill_input_consumer.py` -- child request 构造、执行身份绑定、子进程隔离和 typed 输出发布。
- `scripts/python/validate_skill_input_consumption.py` -- sidecar、输出安全、ready 门禁和 artifact 绑定。
- `scripts/python/skill_input_consumption.py` -- source graph 与 Markdown/JSON 引用展开。
- `.agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py` -- review 权威入口的 context artifact 交付。
- `.agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py`、`execution_control.py` -- acceptance run 的 context 交付与持久化。
- `scripts/python/tests/test_skill_input_consumption.py`、`scripts/python/tests/test_skill_contract_composition.py` -- 共享边界及真实组合测试。

## Tasks & Acceptance

**Execution:**
- [x] `scripts/python/launch_skill_input_consumer.py` -- 由 launcher 生成 request 并从实际执行配置计算 identity；拒绝漂移、未授权能力和快照修改 -- 消除自报身份与提示词-only 隔离。
- [x] `scripts/python/validate_skill_input_consumption.py` -- 对 context、decision、rationale 执行输出脱敏检查并绑定 redaction profile -- 防止 typed sidecar 携带 credential-like 值。
- [x] `scripts/python/skill_input_consumption.py` -- 完整解析支持的 Markdown 引用形式并对疑似未解析引用 fail closed -- 保证源闭包。
- [x] `bootstrap_review.py`、`acceptance_cli.py`、`execution_control.py` -- 将 context artifact 路径与 hash 传入各自权威阶段和恢复状态 -- 确保实际消费语义上下文。
- [x] 共享及四个 Skill 测试 -- 增加身份/隔离/输出泄漏/引用闭包和 producer→consumer→ready 的组合测试 -- 覆盖文档验收标准。

**Acceptance Criteria:**
- Given request 使用伪造 identity 或实际配置漂移，when launcher 执行，then 不启动 child 且 receipt 保持非 ready。
- Given child 修改快照或输出 credential-like 值，when publish-ready 验证，then sidecar 被拒绝且不发布 ready。
- Given Markdown 使用受支持的引用式链接，when prepare 展开 source graph，then 所有目标进入 manifest；解析失败时 fail closed。
- Given Bootstrap Review 或 Refactor Acceptance 通过 gate，when 进入权威阶段，then context artifact 路径和 hash 可被读取、校验并绑定到该 run。
- Given 四个 Skill 的真实 producer/consumer 组合测试，when 缺失、陈旧或错误 receipt，then 首个权威动作阻断；ready 场景完整通过。

## Verification

**Commands:**
- `py -3 -m unittest discover -s scripts/python/tests -p "test_skill_input*.py"` -- 共享协议测试全部通过。
- `py -3 -m unittest discover -s .agents/skills/run-phase-bootstrap-review/tests -p "test*.py"` -- Bootstrap 入口和组合测试通过。
- `py -3 -m unittest discover -s .agents/skills/run-refactor-implementation-acceptance/tests -p "test*.py"` -- Acceptance 入口和恢复绑定测试通过。
- `py -3 -m unittest discover -s .agents/skills/quick-dev-tdd-adapter/tools/tests -p "test*.py"` -- Quick Dev 入口回归通过。
- `py -3 -m unittest discover -s .agents/skills/vdd-execution-plan/scripts/tests -p "test*.py"` -- VDD 入口回归通过。
- `git diff --check` -- 无空白错误；`git status --short --branch` -- 除本规格和实现变更外无意外文件。

**Results:**
- 共享协议与 launcher：46 项通过；composition catalog：3 项通过。新增 common token/private-key 与普通字段 Bearer 拒绝、provider value 扫描、目录成员稳定性、中间级 symlink 拒绝、failed redaction ready gate、序列化快照大小门禁覆盖；ready 发布现先清理快照再执行最终 CAS。同时保留 Markdown shortcut reference、代码/注释排除、严格 angle destination、receipt/contract 完整绑定、配置 TOCTOU、参数规范化和 reasoning 枚举回归。
- Quick Dev TDD：72 项通过；VDD：64 项通过；Refactor Acceptance：263 项通过。四个消费者均覆盖 missing、wrong-consumer、stale receipt 在首个权威动作前 fail closed。
- Bootstrap Review 主套件：204 项通过。
- Refactor Acceptance 将 context artifact 复制进 append-only run custody；direct create、resume、中文路径 binding、custody drift 和 stale successor 均重新校验 run 内副本。
- 真实 Codex CLI smoke：`--ignore-user-config --ephemeral`、禁用工具配置和安全 provider 重放成功，固定 JSON 输出通过；输入从完整子会话验证的约 117,930 token 降至 12,760 token。
- Bootstrap 全量 discover 的两个既存 companion fixture 仍因历史 `review-input.json` 缺少 profile identity 失败；本次未修改这些 fixture，主套件和相关组合测试通过。

## Suggested Review Order

**子进程可信边界**

- 从候选 receipt 构造唯一、完整绑定的 child request。
  [`launch_skill_input_consumer.py:377`](../../scripts/python/launch_skill_input_consumer.py#L377)

- 同一配置快照驱动 identity 校验与真实 Codex 启动。
  [`launch_skill_input_consumer.py:472`](../../scripts/python/launch_skill_input_consumer.py#L472)

- ready 发布前统一验证输出脱敏与所有 sidecar 绑定。
  [`validate_skill_input_consumption.py:427`](../../scripts/python/validate_skill_input_consumption.py#L427)

**输入闭包**

- 屏蔽代码、注释和转义区域，避免伪链接污染 source graph。
  [`skill_input_consumption.py:297`](../../scripts/python/skill_input_consumption.py#L297)

- 解析 full、collapsed 与 shortcut reference，并拒绝未解析引用。
  [`skill_input_consumption.py:421`](../../scripts/python/skill_input_consumption.py#L421)

- 展开后按路径稳定排序，确保序列化输入可复现。
  [`skill_input_consumption.py:537`](../../scripts/python/skill_input_consumption.py#L537)

**Acceptance 证据保管**

- 验证 run 内 context custody 的路径、哈希与 symlink 边界。
  [`execution_control.py:112`](../../.agents/skills/run-refactor-implementation-acceptance/scripts/execution_control.py#L112)

- 创建 run 时复制 context，并绑定来源与 custody 路径。
  [`execution_control.py:155`](../../.agents/skills/run-refactor-implementation-acceptance/scripts/execution_control.py#L155)

- stale successor 仅从已复核的 predecessor custody 继承。
  [`execution_control.py:369`](../../.agents/skills/run-refactor-implementation-acceptance/scripts/execution_control.py#L369)

**消费者接入**

- Bootstrap 首个权威动作读取并绑定 ready context artifact。
  [`bootstrap_review.py:4751`](../../.agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py#L4751)

- Quick Dev TDD 在 prepare 前执行共享 gate。
  [`adapter.py:58`](../../.agents/skills/quick-dev-tdd-adapter/tools/adapter.py#L58)

- VDD knowledge preflight 在处理输入前执行共享 gate。
  [`vdd_knowledge_preflight.py:83`](../../.agents/skills/vdd-execution-plan/scripts/vdd_knowledge_preflight.py#L83)

**组合验证**

- fake runner 解析完整 serialized snapshot 并逐源核验内容。
  [`skill_input_composition_support.py:116`](../../scripts/python/tests/skill_input_composition_support.py#L116)

- 覆盖配置 TOCTOU、参数规范化与真实 typed 输出路径。
  [`test_skill_input_consumption.py:447`](../../scripts/python/tests/test_skill_input_consumption.py#L447)

- 覆盖 custody resume、漂移阻断与 stale successor 复制。
  [`test_control.py:712`](../../.agents/skills/run-refactor-implementation-acceptance/tests/test_control.py#L712)
