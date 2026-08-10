# Bootstrap Review Context-Window Failure Repair

- Title: bootstrap-review-context-window-repair
- Date: 2026-08-09
- Status: accepted
- Supersedes: none
- Superseded by: none
- Scope: `execution-plans/2026-08-07-bootstrap-review-operability-hardening/`
- Related run: `logs/reviews/broh-acceptance-20260809-r4`
- Related control plane: `bootstrap-control-plane.v2`
- Related ADRs: ADR-0041, ADR-0049, ADR-0051, ADR-0056

## 1. Problem

Bootstrap Review 的 Codex 子进程反复返回：

```text
Codex ran out of room in the model's context window
```

失败发生在 8-07 需求目录的分段执行期间。目标 Artifact View 约有 65 个文件、1.37 MB、78 个 segment。典型失败 attempt 的 stdout 约 669 KB，且子进程读取了 assigned segment 之外的大量源码。

这会造成两种容易混淆的表现：

1. reviewer child 真的因 prompt/读取范围过大而失败；
2. 旧 attempt 的失败 stdout 被历史检查或客户端显示出来，看起来像仍有子进程运行。

另外，当前 Codex 客户端进程是 `codex.exe resume`。即使 Bootstrap 子进程已经结束，继续在同一会话中发送消息仍会携带过长聊天历史，并可能再次触发主会话上下文上限。这不是 Bootstrap reviewer 进程仍存活的证明。

## 2. Evidence

- 旧 run 的 `activeAttempts` 与 `acquiredLeases` 已为空。
- reviewer PID `11024`、`11504` 已不存在。
- 当前机器核对没有 `bootstrap_review`、`run-layer` 或 Bootstrap reviewer 子进程；仅存在主 `codex.exe resume` 与其工具宿主。
- `prompt_text()` 的 Codex 合同要求读取完整 Artifact View。
- `runner_prompt()` 又重复了完整 Artifact View 遍历合同。
- segment 分支同时要求只读当前 segment，形成直接冲突。
- segment cache 原路径不包含模型身份；`gpt-5.5` 生成的结果在切换到 `gpt-5.6-terra` 时被误判为 stale。
- 全量 Bootstrap 回归测试最终通过 198 个测试，说明修复后的确定性控制面行为成立。

## 3. Root Cause

### 3.1 Runtime prompt contradiction

父进程的 whole-view completeness 合同被原样带入每个 segment child。虽然 segment 分支之后又写了“只读当前 segment”，但模型首先看到了更宽的读取要求，因而可能遍历完整 manifest、权威源码和消费者闭包。大 Artifact View 下，这会把传输和分析 token 一起推过上下文上限。

### 3.2 Cache identity collision

segment result path 只按 role、ordinal 和 segment ID 定位，没有绑定 selected model。模型切换后，旧结果既不能可靠复用，又会被当作当前模型结果校验，造成不必要的 stale failure 或重复执行。

### 3.3 Lifecycle re-entry confusion

停止 child 只结束操作系统进程，不会自动改变 run 的生命周期关系。旧 run 仍可能处于 `authorized/active`，恢复或客户端重试逻辑仍可重新选择它。

### 3.4 Main-session history overflow

`codex.exe resume` 恢复的是主 Codex 会话，不等于创建全新上下文。历史聊天中的重复错误、长日志和工具输出会继续占用主模型上下文。关闭 reviewer child 无法清除主会话历史。

## 4. Options And Confidence

| 方案 | 内容 | 置信度 | 结论 |
| --- | --- | ---: | --- |
| A. 只改 prompt | 删除 segment child 的全量读取文字 | 0.68 | 能降低溢出概率，但不能解决模型缓存串用和旧 run 重入 |
| B. Prompt + model cache | 加 segment prompt、模型隔离缓存、旧合同回归测试 | 0.84 | 采用，覆盖已观察到的三个控制面根因 |
| C. 仅缩小 Artifact View | 减少 scope 或允许 sampling | 0.42 | 拒绝；违反 `artifactCoverage=all` 与 `samplingAllowed=false` |
| D. 仅换更大模型 | 切换 Sol 或提高 effort | 0.35 | 拒绝；增加成本，不能修复读取合同冲突 |

方案 B 的 0.84 置信度表示：它高度覆盖当前已确认的运行时根因，但不保证任意未来 prompt 注入、异常 authority closure 或客户端会话缓存都不会造成新的上下文问题。

## 5. Selected Design

### 5.1 Parent-owned whole-view completeness

- 父进程继续冻结完整 Artifact View。
- 父进程生成稳定有序 segment plan。
- 每个 child 只接收一个 segment 和明确的 delegated authority 映射。
- child 返回 `bootstrap-artifact-view-segment-receipt.v1`。
- 父进程校验 role、ordinal、总数、行范围、artifact hash、content hash、重复和重叠。
- 只有所有 segment receipt 通过后，父进程才生成完整 role output。
- 缺失或传输失败只重试当前 segment，不缩小 Artifact View，也不消耗新的 semantic round。

### 5.2 Segment-aware runtime prompt

分段 prompt 必须明确：

- 不打开或遍历完整 Artifact View manifest。
- 只读取 assigned snapshot path 和 inclusive line range。
- 允许读取 parent 明确映射的 delegated Bootstrap authority。
- whole-view completeness 由 parent 聚合 receipts。
- child 不修改 formal output，不运行 `validate-layer`，不返回 coverage path arrays。

非分段 prompt 保持原有“完整读取全部 Artifact View”的合同，以维持 `artifactCoverage=all`。

### 5.3 Model-bound segment cache

新缓存路径为：

```text
segment-coverage/<role>/<sha256(model)>/<ordinal>-<segment-id>.json
```

读取规则：

1. 优先读取模型隔离的新路径。
2. 新路径不存在时，只读兼容旧路径。
3. 旧记录的 `model` 与当前请求相同，才允许复用。
4. 旧记录模型不同，视为 cache miss，不报告 stale。
5. 新写入只写模型隔离路径；历史文件不改写、不删除。

### 5.4 Lifecycle closure

当 transport failure 已发生且没有 active event-backed attempt 时，使用 append-only `seal-run` 标记旧 run 为 `abandoned`。封存不修改 reviewer、verifier、gate、stdout、stderr、token 或 process-event evidence。

## 6. Implemented Changes

- [bootstrap_review.py](../.agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py)
  - `prompt_text(..., segmented=True)` 生成 segment-aware 合同。
  - `runner_prompt()` 在分段 child 使用 segment prompt，禁止 full-view traversal。
  - `segment_result_path()` 加入模型 SHA-256 目录。
  - `load_segment_result()` 只兼容同模型旧缓存。
  - `list-runs` 对缺失 `accessProbePolicy` 的历史 manifest 使用默认策略并继续 fail-closed 检查。
- [test_bootstrap_review.py](../.agents/skills/run-phase-bootstrap-review/tests/test_bootstrap_review.py)
  - 增加分段 prompt 禁止全量遍历测试。
  - 增加模型隔离缓存路径测试。
  - 保留 segment receipt 聚合、失败 segment 重试和父进程完整覆盖测试。
- [SKILL.md](../.agents/skills/run-phase-bootstrap-review/SKILL.md)
  - 记录 child segment 边界、父进程 whole-view aggregate 和模型绑定缓存规则。
- [bootstrap-review-control-plane.md](../docs/standards/bootstrap-review-control-plane.md)
  - 将 segment runtime boundary 固化为 durable standard。

## 7. Validation

已通过：

```text
py -3 .agents/skills/run-phase-bootstrap-review/tests/test_bootstrap_review.py
Ran 198 tests ... OK

py -3 execution-plans/2026-07-12-llm-review-evidence-gate-hardening/tools/validate_whole_directory.py
PASS: whole-directory plan validation succeeded

py -3 C:/Users/Administrator/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/run-phase-bootstrap-review
Skill is valid!

git diff --check
PASS
```

旧 run 已追加封存：

```text
runExecutionState: abandoned
activeAttempts: []
acquiredLeases: []
nextAction: use-successor-or-create-fresh-run
```

未启动新的 reviewer，未恢复旧 run，未修改旧失败 evidence。

## 8. Operational Procedure

### 8.1 Bootstrap run

1. 先 `inspect-lineage`、`list-runs`、`inspect-run`。
2. 旧 run 有 active attempt 时只 inspect/reattach；没有 active attempt 且属于 transport/runtime defect 时才能 seal。
3. 选择一个执行面；FastCtx proof 后不得切换 PowerShell。
4. 完成 preflight、access proof、authorize-launch，再运行 reviewer。
5. Artifact View 超过 segment threshold 时，确认 child prompt 是 segment-aware。
6. 不要通过 sampling、缩小 scope 或提高模型等级绕过完整覆盖合同。

### 8.2 Main Codex session

如果界面仍显示 `Codex ran out of room...`，先停止当前 `codex.exe resume` 会话并创建真正的新 thread。不要继续发送重复的 `go on`，因为这些消息本身会继续增长同一个会话历史。新线程只携带仓库路径、旧 run 已封存、代码测试已通过和下一步目标，不携带旧 stdout 全文。

不要误杀主 PID 6704；它是当前 Codex 会话，不是 Bootstrap reviewer。

## 9. Residual Risk And Follow-up

- 当前修复验证了 segment transport、prompt boundary 和 cache identity；尚未证明模型在所有跨文件语义场景下都能仅凭 segment 形成完整 finding。
- 因此第二阶段应评估 parent-side candidate closure synthesis：child 只产生局部证据，父进程在所有 receipts 通过后再做确定性跨 segment 合并和校验。
- 新 run 必须使用新 review ID 和新 Artifact View snapshot。旧 `r4c` 只能作为历史证据，不得重启。
- 本文不授予 plan acceptance、implementation acceptance、handoff、commit、release 或 done authority。

