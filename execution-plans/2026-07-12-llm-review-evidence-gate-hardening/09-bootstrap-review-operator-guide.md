# Bootstrap Review 手工操作指南

## 1. 适用范围

本工具用于 handoff 前的手工或受控编排审查：

- `execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/`；
- `execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/`；
- 用户显式声明的相关实现 diff 或文件 scope。

工具本身不调用 reviewer；用户可以手工运行，也可以明确授权 Codex 主会话编排 Blind Hunter、Edge Case Hunter、Acceptance Auditor。编排时每个角色必须使用相互隔离的 agent/session，主会话不得代写或修补 finding。独立 verifier 只能在 gate 产生 P0/P1 blocker 后运行，且不得复用 discovery reviewer。工具和编排会话均不得修改目标 scope、更新上游 ledger，也不得替代 7-11 BH-HANDOFF verifier。

## 2. 准备 review run

为 7-07 创建 run：

```powershell
py -3 execution-plans/2026-07-12-llm-review-evidence-gate-hardening/tools/run_bootstrap_review.py prepare `
  --repository-root C:\jimuyun `
  --review-id gdd-to-module-manual-001 `
  --profile bootstrap-upstream-plan `
  --scope execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening `
  --out-dir logs/ci/2026-07-12/review-gateway-bootstrap-gdd-to-module-manual-001
```

为 7-11 创建 run 时，只替换 review ID、scope 和 out-dir。每次 review 使用新目录，不覆盖旧 evidence。

`prepare` 必须生成：

- `review-input.json`：commit、dirty state、scope file hashes、profile 和 authority revision；
- `reviewer-prompts/blind_hunter.md`；
- `reviewer-prompts/edge_case_hunter.md`；
- `reviewer-prompts/acceptance_auditor.md`；
- `reviewer-outputs/<reviewer>.json` 空模板。

如果 out-dir 位于任一 scope 内、scope 不存在或越过 repository root，命令必须在写文件前失败。

## 3. 运行三个 reviewer

用户可以分别手工运行，也可以明确授权 Codex 编排三个 reviewer。自动编排必须满足：

- Blind Hunter、Edge Case Hunter、Acceptance Auditor 各自使用独立 agent/session；
- 每个 reviewer 只接收自己的 prompt 路径、run directory、repository root 和写回目标，不接收主会话的疑似 finding、期望数量或其他 reviewer 输出；
- 主会话只负责启动、等待、检查完成状态和执行 gateway，不得编造、合并、补足或改写 reviewer candidate；
- 任一 reviewer 失败、缺 authority 或 coverage 不完整时，保持该层失败或未完成，不得由主会话兜底成 completed；
- 三层都完成后，用户要求完整 review 时可以继续执行 gate；仅要求 prepare 或 reviewer 输出时应在对应阶段停止。

每个 reviewer 都必须：

1. 打开对应 prompt；
2. 使用用户选择的 reviewer/session 手工执行；
3. 保留 template 中所有绑定字段；逐个读取 manifest artifact 后，将其从 `coverage.missingArtifacts` 移到 `coverage.readArtifacts`；只有 required artifact 全部已读才把 `status` 改为 `completed`；
4. 没有 finding 时保存合法空数组，不删除输出文件；
5. 不在 reviewer 输出中添加 routeVersion、status、fingerprint 或 unverified disposition，这些字段由 gateway 拥有。
6. 禁止把“至少输出十条”或任何固定 finding 数量作为完成条件；固定数量最多只能用于首轮内部假设探索，最终只保存通过事实门禁的 candidate，零 candidate 合法。
7. 如果 assigned role 所需 authority/context 不在 manifest，禁止越界读取；将 `status` 设为 `failed`、填写 `failureReason`、保持 candidates 为空，由 gate 输出 incomplete，并用包含所需 context 的新 scope 重新 prepare。

本工具不规定用户或编排会话使用哪个 Codex/BMAD/GDS 命令；prompt 和 JSON 输出文件是唯一交换边界。

## 4. 执行事实门禁

```powershell
py -3 execution-plans/2026-07-12-llm-review-evidence-gate-hardening/tools/run_bootstrap_review.py gate `
  --run-dir logs/ci/2026-07-12/review-gateway-bootstrap-gdd-to-module-manual-001
```

gate 校验 required layers、schema、scope/hash、精确行号与 evidence、failure tuple、context、guard、confidence、文档 authority 字段和 dedup。

输出：

- `review-candidates.json`；
- `review-rejections.json`；
- `review-gate-state.json`：只供 finalize 校验 candidate/rejection sidecar hash，不作为最终 review result；
- `review-gate-result.json`；
- `verification-prompt.md` 和 `verifier-output.json` 模板；没有 P0/P1 时二者为空核验合同，存在 P0/P1 时才需要人工填写。

三层输出均存在且零 accepted finding 时允许 clean。缺 required output 时 gate 结果只能 incomplete；stale input 或 gate 自身错误必须直接失败，不能产出 clean。

## 5. 用户手工独立核验 P0/P1

如果 gate 的 `blockerCandidateCount` 大于 0：

1. 在与 discovery reviewer 分离的新 session 中手工运行，或由用户明确授权 Codex 启动独立 verifier；
2. verifier 只能对现有 finding ID 返回 `confirmed|refuted|unverified`；
3. verifier 不得新增问题或扩大 scope；
4. `unverified` 必须选择 `security|data_loss|other` class，gateway 派生 disposition；
5. 保存到 run directory 的 `verifier-output.json`。

## 6. Finalize

```powershell
py -3 execution-plans/2026-07-12-llm-review-evidence-gate-hardening/tools/run_bootstrap_review.py finalize `
  --run-dir logs/ci/2026-07-12/review-gateway-bootstrap-gdd-to-module-manual-001
```

最终输出：

- `review-gate-result.json`；
- `review-dispositions.json`；
- `review-metrics.json`；
- `review-report.md`。

Bootstrap manifest、gate 中间结果、candidate/rejection/disposition/metrics sidecar 和报告必须标明或绑定 `authorityClass=supplemental_bootstrap`；最终 `review-gate-result.json` 保持 `review-result.v1` 兼容，不伪造生产 authority。用户可以人工引用合格 finding 处理上游问题，但工具不会自动修改 7-07/7-11，也不会把 clean 解释为上游重构完成。

## 7. 验收与排错

```powershell
py -3 -m unittest discover `
  -s execution-plans/2026-07-12-llm-review-evidence-gate-hardening/tools/tests `
  -p "test_*.py"

py -3 execution-plans/2026-07-12-llm-review-evidence-gate-hardening/tools/validate_whole_directory.py
```

- `prepare` 失败：先检查 scope/out-dir 边界；
- `gate` incomplete：检查 required reviewer 文件、stale hash 和 rejection reason；
- `finalize` 失败：检查每个 P0/P1 是否恰有一个 verifier decision；
- 目标文件发生变化：重新 prepare 新 review ID，不复用旧 input hash。

## 验收标准

- Given 用户只执行 prepare，When比较目标 scope hash，Then前后完全一致。
- Given 用户保存三个合法空输出，When gate，Then clean result 合法。
- Given P0/P1 缺 verifier 决策，When finalize，Then fail closed。
- Given Bootstrap review 完成，When检查上游目录，Then无工具产生的修改。
