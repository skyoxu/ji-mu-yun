# Bootstrap Review 手工操作指南

## 1. 适用范围

本工具用于 handoff 前的手工或受控编排审查：

- `execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/`；
- `execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/`；
- 用户显式声明的相关实现 diff 或文件 scope。

工具本身不调用 reviewer；用户可以手工运行，也可以明确授权 Codex 主会话编排 Blind Hunter、Edge Case Hunter、Acceptance Auditor。编排时每个角色必须使用相互隔离的 agent/session，主会话不得代写或修补 finding。独立 verifier 只能在 gate 产生 P0/P1 blocker 后运行，且不得复用 discovery reviewer。工具和编排会话均不得修改目标 scope、更新上游 ledger，也不得替代 7-11 BH-HANDOFF verifier。

## 2. Review 对象与 profile

| Review 对象 | Profile | 必须覆盖的上下文 | 推理配置 |
| --- | --- | --- | --- |
| 实施前计划、唯一事实源、Whole-directory | `bootstrap-upstream-plan` | 计划源、原始需求、仓库规则、当前现状、引用标准、schemas/fixtures | Blind `medium`；Edge/Acceptance/verifier `high` |
| 重构/实施完成后的代码与功能闭合 | `bootstrap-implementation-conformance` | 实施计划、全部变更生产代码、受影响消费者、测试与验收、运行证据、仓库规则、引用标准 | 全部角色 `high` |
| Skill/路由 | `bootstrap-skill-route` | Skill 本体、operator guide、route/CLI、profiles/config、schemas、tests、使用证据、仓库规则 | Blind `medium`；Edge/Acceptance/verifier `high` |
| 聚焦 bugfix/hotfix/diff | `bootstrap-focused-change` | 变更意图、全部变更文件、受影响消费者、目标测试、仓库规则、引用标准 | Blind/Acceptance `medium`；Edge/verifier `high` |

四种 profile 的完整性合同完全相同：`artifactCoverage=all`、`samplingAllowed=false`、`contextClosureRequired=true`、缺上下文时 `status=failed`。推理等级只能改变分析深度，不能减少必读文件、调用方/消费者、测试或验收证据。每个 profile 还绑定 `reviewerInstructionPolicy`、`deterministicPreflightPolicy` 与 `reviewCyclePolicy`，跨会话不得改写。

`prepare` 必须对 profile 的每个 `requiredContextClasses` 传入至少一个 `--context-class <class>=<scope>`。映射目标必须已经被某个 `--scope` 纳入，且实际含有该 class 的 authority；缺 class、未知 class 或零 artifact 映射时命令在写文件前失败。
`bootstrap-skill-route` 还执行确定性 artifact 语义校验：Skill source 必须含 `SKILL.md`；operator/CLI/profile+`openai.yaml`/schema/test/usage evidence/repository rules 必须分别匹配其稳定路径或文件形态。把同一无关文件冒名映射到全部 class 必须失败。

Skill 位于仓库外时，先在 `logs/ci` 创建 SHA-256 相同的只读快照，并把 Skill 直接委托的 operator/route/profile/schema/test/usage authority 一起纳入 scope；只审 `SKILL.md` 不构成完整 Skill/路由审查。

## 3. 准备 review run

为 7-07 创建 run：

```powershell
py -3 execution-plans/2026-07-12-llm-review-evidence-gate-hardening/tools/run_bootstrap_review.py prepare `
  --repository-root C:\jimuyun `
  --review-id gdd-to-module-manual-001 `
  --change-id gdd-to-module-hardening `
  --review-round 1 `
  --profile bootstrap-upstream-plan `
  --scope execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening `
  --scope AGENTS.md `
  --scope README.md `
  --context-class plan-source=execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening `
  --context-class original-requirements=execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening `
  --context-class repository-rules=AGENTS.md `
  --context-class current-state=README.md `
  --context-class referenced-standards=execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening `
  --context-class schemas-and-fixtures=execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening `
  --execution-mode manual `
  --semantic-review-exclusivity no-other-semantic-review-in-cycle `
  --out-dir logs/ci/2026-07-12/review-gateway-bootstrap-gdd-to-module-manual-001
```

为 7-11 创建 run 时，必须同时包含拆分目录和原单体计划，不能只替换成拆分目录：

```powershell
py -3 execution-plans/2026-07-12-llm-review-evidence-gate-hardening/tools/run_bootstrap_review.py prepare `
  --repository-root C:\jimuyun `
  --review-id frontend-boundary-manual-001 `
  --change-id frontend-boundary-hardening `
  --review-round 1 `
  --profile bootstrap-upstream-plan `
  --scope execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan `
  --scope execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan.md `
  --scope AGENTS.md `
  --scope README.md `
  --context-class plan-source=execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan `
  --context-class original-requirements=execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan.md `
  --context-class repository-rules=AGENTS.md `
  --context-class current-state=README.md `
  --context-class referenced-standards=execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan `
  --context-class schemas-and-fixtures=execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan `
  --execution-mode manual `
  --semantic-review-exclusivity no-other-semantic-review-in-cycle `
  --out-dir logs/ci/2026-07-13/review-gateway-bootstrap-frontend-boundary-manual-001
```

98/99 的 source coverage 以原单体计划为 authority；缺少第二个 scope 时 reviewer 必须 fail closed。每次 review 使用新目录，不覆盖旧 evidence。

`prepare` 还必须绑定 `changeId`、`fullReviewRound`、`executionMode` 和固定 attestation `no-other-semantic-review-in-cycle`。同一 change 的 round 1 在语义执行开始后只能存在一次；`codex-exec` 以首条 reviewer role lease 作为 round 开始，只有模型探针的失败 run 可替换且不消耗 round；round 2/3 必须用 `--predecessor-run-dir` 指向相邻已 finalized run。换 review ID 不能重开 round 1，round 4 永远拒绝，round 3 仅在 predecessor 有 P0/P1 或 authority/context graph 改变时允许。

`bootstrap-implementation-conformance` 还必须用重复 `--required-check <check-id>=<authority-scope>` 绑定实施计划要求的完整 .NET、Whole-directory 或其他必跑检查。映射 scope 必须已由 `--scope` 纳入；这些 check ID 会被追加到 preflight requiredChecks。缺少任何 plan-bound check 时 prepare fail closed。

`prepare` 必须生成：

- `review-input.json`：commit、dirty state、scope file hashes、profile 和 authority revision；
- `preflight-result.json`：required check 的 pending 模板，完成后记录 command、exitCode、`preflight/**` evidence path/hash；
- `reviewer-prompts/blind_hunter.md`；
- `reviewer-prompts/edge_case_hunter.md`；
- `reviewer-prompts/acceptance_auditor.md`；
- `reviewer-outputs/<reviewer>.json` 空模板。

`review-input.json.codexExecPolicy` 是跨会话模型权威：reviewer 和独立 verifier 首选模型固定为 `gpt-5.6-terra`，按顺序回退到 `gpt-5.5`、`gpt-5.4`，禁止使用 `gpt-5.6-sol`。主会话和子进程不得用全局默认模型覆盖该策略。
同一 manifest 的 `contextClassArtifacts` 必须对 `requiredContextClasses` 逐项提供非空、hash-bound artifact 列表；gate/finalize 恢复时重新验证映射。

同一 manifest 还必须绑定 `reviewObjectType`、`reviewDepth`、`requiredContextClasses`、`completenessPolicy`、逐角色 `reasoningEffortByRole`、role rubric、误报清单、untrusted-content、deterministic preflight 和 full-review cycle policy。任何字段缺失或与 profile 不一致时，gate/finalize 必须 fail closed。

Windows 上，CLI 必须对 reviewer 输出模板显式授予当前用户 Modify 权限，避免受限 `codex exec` token 只能在目录中新建 sidecar、却不能覆盖由提升权限父进程创建的模板。`gate` 生成的 `verifier-output.json` 同样适用；ACL 授权失败时命令必须 fail closed。

如果 out-dir 位于任一 scope 内、scope 不存在或越过 repository root，命令必须在写文件前失败。


## 3.1 确定性 preflight

`prepare` 成功后、任何 reviewer 启动前，读取 `review-input.json.deterministicPreflightPolicy.requiredChecks`，把每条命令、退出码和完整输出保存到 `<run-dir>/preflight/`。四类 profile 的最低检查是：

- `bootstrap-upstream-plan`：scope 结构/链接、schema/fixture 解析、计划 composite validator；
- `bootstrap-implementation-conformance`：targeted tests、build/compile、acceptance 或 runtime evidence；
- `bootstrap-skill-route`：Bootstrap regression tests、7-12 Whole-directory validator、Skill quick validation；
- `bootstrap-focused-change`：targeted tests、受影响 static/deterministic checks。

任一 required check 失败、缺失或无法证明时，停止在 reviewer 启动前，不生成语义 finding，也不把失败解释成 clean。每个成功 check 必须把 `status=passed`、实际 command、`exitCode=0`、run-relative `evidencePath` 和当前 `evidenceHash` 写入 `preflight-result.json`，全部成功后才把顶层 status 改为 `passed`。gate/finalize 会验证 check 集合、路径边界和 evidence hash。preflight 只负责机器可判定问题；通过后仍须完整读取 manifest 并运行三个 reviewer。

Preflight 全部通过后、任何 reviewer 启动前，必须冻结 authority：

```powershell
py -3 execution-plans/2026-07-12-llm-review-evidence-gate-hardening/tools/run_bootstrap_review.py authorize-launch `
  --run-dir <run-dir> `
  --ack-high-cost
```

CLI 会重验 Git revision、artifact hashes、profile/context graph、preflight hash、review lineage 和成本估算，并生成 `review-launch-authorization.json`。仅当 manifest 的 `reviewCostEstimate.highCost=true` 时才需要 `--ack-high-cost`；未确认时命令输出 artifact count、bytes 与 relative work units 后停止。授权后任一 authority/preflight 漂移都会使 validate/gate/finalize 失败，必须创建新 run。

## 4. 运行三个 reviewer

用户可以分别手工运行，也可以明确授权 Codex 编排三个 reviewer。一个 change cycle 只能选择 Bootstrap 作为语义 finding authority；一旦选择，不得同时运行 Quick Dev、BMAD/GDS code review 或另一套 Bootstrap reviewer。Quick Dev 只负责实现、targeted tests、build 和确定性 validator。自动编排必须满足：

- Blind Hunter、Edge Case Hunter、Acceptance Auditor 各自使用独立 agent/session；普通 Codex 可以使用三个独立的 `codex exec` 进程，不要求专用 subagent 工具；
- 每个 reviewer 只接收自己的 prompt 路径、run directory、repository root 和写回目标，不接收主会话的疑似 finding、期望数量或其他 reviewer 输出；
- 主会话只负责启动、等待、检查完成状态和执行 gateway，不得编造、合并、补足或改写 reviewer candidate；
- 任一 reviewer 失败、缺 authority 或 coverage 不完整时，保持该层失败或未完成，不得由主会话兜底成 completed；
- 三层都完成后，用户要求完整 review 时可以继续执行 gate；仅要求 prepare 或 reviewer 输出时应在对应阶段停止；
- 每个 prompt 必须包含本角色 rubric、profile 专用误报抑制清单和 untrusted-content boundary；缺少任一项时拒绝启动；
- 每个 reviewer 保存输出后必须重新读取自己的 JSON，并执行 `validate-layer --run-dir <run-dir> --layer <role>`；只有命令零退出才算该层完成。失败时由同一 reviewer 修正自己的输出或将该层保留为失败，主会话不得代修。
- 使用 `codex exec` 时，每个 probe/reviewer/verifier 必须先用 `process-lease --action acquire` 记录稳定 operation ID、role 与真实子进程 PID，结束后用 `--action release --state completed|failed` 收口。reviewer operation 固定为 `reviewer:<role>`，verifier 固定为 `verifier`。工具等待超时但 PID 仍 alive 时只能 inspect/reattach/poll，不得启动第二个相同 operation；PID dead 时 CLI 标 stale 后才允许重新 acquire。
- 使用 `codex exec` 时，通过 UTF-8 stdin 传入 prompt（`codex exec ... -`），每个角色使用独立 ephemeral 进程；启动审查前必须用相同 provider/model/reasoning 做一次终端与 workspace-write 探针。正常命令必须显式传入 `-m gpt-5.6-terra -c model_reasoning_effort=<manifest-role-value>`，不能依赖全局默认值。首选探针失败后才可依次尝试 `gpt-5.5`、`gpt-5.4`，并保存失败模型及原因；`gpt-5.6-sol` 禁止用于 reviewer/verifier。探针失败、超时、认证失败、非零退出或缺少输出均按该层 incomplete 处理，主会话不得代修 JSON。

Process lease 示例：

```powershell
py -3 execution-plans/2026-07-12-llm-review-evidence-gate-hardening/tools/run_bootstrap_review.py process-lease `
  --run-dir <run-dir> --action acquire `
  --operation-id reviewer:blind_hunter --role blind_hunter --pid <child-pid>

py -3 execution-plans/2026-07-12-llm-review-evidence-gate-hardening/tools/run_bootstrap_review.py process-lease `
  --run-dir <run-dir> --action release `
  --operation-id reviewer:blind_hunter --pid <child-pid> --state completed
```

Reviewer 示例：

```powershell
py -3 -c "from pathlib import Path; print(Path(r'<run-dir>/reviewer-prompts/blind_hunter.md').read_text(encoding='utf-8'))" |
  codex exec -C C:\jimuyun -s workspace-write --ephemeral -m gpt-5.6-terra `
    -c 'model_reasoning_effort="<manifest-role-value>"' -
```

独立 verifier 使用相同 `-m gpt-5.6-terra`，但必须启动全新进程并读取 `verification-prompt.md`。

每个 reviewer 都必须：

1. 打开对应 prompt；
2. 使用用户选择的 reviewer/session 手工执行；
3. 保留 template 中所有绑定字段；逐个读取 manifest artifact 后，将其从 `coverage.missingArtifacts` 移到 `coverage.readArtifacts`；只有 required artifact 全部已读才把 `status` 改为 `completed`；
4. 没有 finding 时保存合法空数组，不删除输出文件；
5. 不在 reviewer 输出中添加 routeVersion、status、fingerprint 或 unverified disposition，这些字段由 gateway 拥有。
6. 禁止把“至少输出十条”或任何固定 finding 数量作为完成条件；固定数量最多只能用于首轮内部假设探索，最终只保存通过事实门禁的 candidate，零 candidate 合法。
7. 如果 assigned role 所需 authority/context 不在 manifest，禁止越界读取；将 `status` 设为 `failed`、填写 `failureReason`、保持 candidates 为空，由 gate 输出 incomplete，并用包含所需 context 的新 scope 重新 prepare。

Reviewer 写回后的只读自校验命令：

```powershell
py -3 execution-plans/2026-07-12-llm-review-evidence-gate-hardening/tools/run_bootstrap_review.py validate-layer `
  --run-dir <run-dir> `
  --layer <blind_hunter|edge_case_hunter|acceptance_auditor>
```

该命令不运行 gate、不生成 candidate/rejection sidecar，也不修改 reviewer JSON。`completed` 必须满足 `missingArtifacts=[]` 且 required/read artifact 集合完全相等。

本工具不规定用户或编排会话使用哪个 Codex/BMAD/GDS 命令；prompt 和 JSON 输出文件是唯一交换边界。

## 5. 执行事实门禁

```powershell
py -3 execution-plans/2026-07-12-llm-review-evidence-gate-hardening/tools/run_bootstrap_review.py gate `
  --run-dir logs/ci/2026-07-12/review-gateway-bootstrap-gdd-to-module-manual-001
```

gate 校验 required layers、schema、scope/hash、精确行号与 evidence、failure tuple、context、guard、confidence、文档 authority 字段和 dedup。
Failure tuple 或 `existingGuardAnalysis` 只“非空”不构成通过；`TBD`、`TODO`、`N/A`、`unknown`、`placeholder` 等价占位值必须被归一化后分别以 `missing_failure_tuple` 或 `missing_guard_analysis` 拒绝。

如果现有 `verifier-output.json.decisions` 非空，CLI 必须在写任何 gate sidecar 前拒绝重跑，保持 verifier 文件字节不变，并要求新 review run。Skill preflight 只是提前提示，CLI 是最终强制点。
如果 `review-gate-result.json.schemaVersion=review-result.v1`，说明 run 已 finalized；再次 gate 或 finalize 都必须在任何写入前失败并要求新 run，包括 verifier decisions 为空的 clean/advisory 结果。不要通过修改 `verifier-output.json` 重开终态。

Dedup 以 hash-bound artifact、inclusive line range 与 exact evidence 作为 evidence root；同根候选保留最高严重等级、合并 source reviewer，其他候选写 duplicate rejection。P2 不得抢先吞掉同根 P1/P0。

输出：

- `review-candidates.json`；
- `review-rejections.json`；
- `review-gate-state.json`：只供 finalize 校验 candidate/rejection sidecar hash，不作为最终 review result；
- `review-gate-result.json`：gate 阶段遵守 [bootstrap-review-gate-result.v1.schema.json](schemas/bootstrap-review-gate-result.v1.schema.json)；
- `verification-prompt.md` 和 `verifier-output.json` 模板；没有 P0/P1 时二者为空核验合同，存在 P0/P1 时才需要人工填写。

三层输出均存在且零 accepted finding 时允许 clean。缺 required output 时 gate 结果只能 `incomplete`；存在 accepted P0/P1 且尚无 verifier decision 时只能是 gate-only `awaiting_verification`。stale input、route/profile/hash binding 漂移或 gate 自身错误必须直接失败，不能产出 clean。

## 6. 独立核验 P0/P1

如果 gate 的 `blockerCandidateCount` 大于 0：

1. 在与 discovery reviewer 分离的新 session 中手工运行，或由用户明确授权 Codex 启动独立 verifier；
2. verifier 只能对现有 finding ID 返回 `confirmed|refuted|unverified`；
3. verifier 不得新增问题或扩大 scope；
4. `unverified` 必须选择 `security|data_loss|other` class，gateway 派生 disposition；
5. 每条 `evidenceChecked` 必须覆盖 finding 精确证据行和全部 `contextRead`；无关但 in-scope 的引用无效；
   path-only context 表示整文件，不能用单行引用替代；
6. 保存到 run directory 的 `verifier-output.json`。

## 7. Finalize

```powershell
py -3 execution-plans/2026-07-12-llm-review-evidence-gate-hardening/tools/run_bootstrap_review.py finalize `
  --run-dir logs/ci/2026-07-12/review-gateway-bootstrap-gdd-to-module-manual-001
```

最终输出：

- `review-gate-result.json`；
- `review-dispositions.json`；
- `review-metrics.json`；
- `review-report.md`。

Bootstrap manifest、gate 中间结果、candidate/rejection/disposition/metrics sidecar、最终 result 和报告必须绑定同一 `review-input.json.routeVersion`、profile/revision、authority revision、input hash，并标明 `authorityClass=supplemental_bootstrap`；最终 `review-gate-result.json` 保持 `review-result.v1` 兼容，不伪造生产 authority。用户可以人工引用合格 finding 处理上游问题，但工具不会自动修改 7-07/7-11，也不会把 clean 解释为上游重构完成。


## 7.1 修复与完整 Review 轮次止损

一次完整语义 Review 包含三个 reviewer、gate 和需要时的独立 verifier。执行规则：

1. 首轮完整 Review 后汇总全部 accepted findings，再退出只读 run；
2. 在独立实现步骤中批量修复全部 accepted findings，同时检查相邻回归风险；
3. 中间只运行 targeted tests、schema、validator、build/smoke 和反例，不得逐 finding 重跑三层 reviewer；
4. 批量修复完成后，用新 review ID/input hash 运行一次最终完整 Review；目标变更导致旧 input stale，但不要求立即重跑；
5. 默认完整轮次上限为两轮；最终轮出现新的 P0/P1 或 authority/context graph 改变时，最多允许第三轮；
6. P2-only 不自动触发完整复审；达到三轮仍未闭合时进入 `manual_pause`，不得继续自动循环。

用户可以显式要求新的 Review，但普通授权不能绕过 profile 的三轮硬上限；继续需要新的 policy decision，而不是沿用旧 run。

## 8. 验收与排错

```powershell
py -3 -m unittest discover `
  -s execution-plans/2026-07-12-llm-review-evidence-gate-hardening/tools/tests `
  -p "test_*.py"

py -3 execution-plans/2026-07-12-llm-review-evidence-gate-hardening/tools/validate_whole_directory.py
```

- `prepare` 失败：先检查 scope/out-dir 边界；
- `gate` incomplete：检查 required reviewer 文件、stale hash 和 rejection reason；
- `finalize` 失败：检查每个 P0/P1 是否恰有一个 verifier decision；
- 目标文件发生变化：完成批量修复和 targeted deterministic validation 后，再重新 prepare 新 review ID；不复用旧 input hash，也不因单条 finding 立即重跑。

## 验收标准

- Given 用户只执行 prepare，When比较目标 scope hash，Then前后完全一致。
- Given 用户保存三个合法空输出，When gate，Then clean result 合法。
- Given P0/P1 缺 verifier 决策，When finalize，Then fail closed。
- Given Bootstrap review 完成，When检查上游目录，Then无工具产生的修改。
- Given gate 后已有非空 verifier decisions，When再次执行 gate，Then命令非零退出且 verifier 文件字节不变。
- Given run 已 finalized，When修改 verifier 后再次执行 finalize，Then命令非零退出，最终结果与 verifier 文件字节不变，并要求新 review run。
- Given 同一 evidence root 先出现 P2 后出现 P1，When gate dedup，Then只保留一个 P1 finding 并进入独立 verifier。
- Given 任一 profile，When prepare 生成 manifest/prompt，Then全部 artifact/context 必读且 sampling 永远为 false。
- Given required deterministic preflight 失败，When执行完整 review，Then三个 reviewer 均不得启动。
- Given reviewer 声明 completed 但 coverage 分区矛盾，When执行 `validate-layer`，Then命令非零退出且 gate sidecar 不存在。
- Given 受审内容包含嵌入指令，When reviewer 读取，Then指令不能改变角色、scope、模型、工具、severity 或 finding 数量。
- Given 首轮 accepted findings 已汇总，When进入修复，Then批量修复并只跑 targeted deterministic checks；默认只在全部修完后运行最终完整 Review。
- Given preflight 已通过但 authority 或 artifact 改变，When authorize-launch/validate/gate/finalize，Then fail closed 且旧授权不可复用。
- Given同一 operation 的 PID 仍 alive，When工具等待超时后再次 acquire，Then拒绝重复启动并要求 reattach/poll。
- Given implementation profile 未声明 plan-bound required check，When prepare，Then在写 manifest 前失败。
- Given同一 change 已有 round 1，When换 review ID 再 prepare round 1，Then失败；round 4 永远失败。
