# Final Input Reconciliation: docs/know-tc-d1-rebuild.md

## Verdict

**CONDITIONAL PASS — 1 个残余阻塞。** 六项定向复核中，FR-7 双侧执行、历史 requirement disposition、历史原生命令、机器可判定的空授权集和 current Git baseline 已闭合；三个 Evaluation Seed 的稳定身份仍未实际写入 PRD 或 addendum，因此输入 reconciliation 尚不能最终通过。

## 已闭合项

- **FR-7 双侧执行：通过。** FR-7 明确要求 “Both sides execute for every Matrix Case”，已删除历史场景单侧执行例外；同时要求 stable/candidate 内容身份不同并具有能影响观察的真实 delta。SM-3 再次约束六个案例执行两个 subject。
- **`TC-D1-001..013` disposition：通过。** addendum 已逐项列出十三项旧 requirement、disposition、对应新 FR/NFR 与理由；并明确说明目录创建和 Skill-input v1 是 superseded context，现有构件的初次创建收窄为 repair/conformance。该表没有静默删除旧 requirement。
- **历史原生命令：通过。** addendum 的 Downstream Contract Constraints 明确要求保留 original machine-bound historical command 作为可审计事实，并禁止其成为当前可执行权威；`TC-D1-005` disposition 也绑定 FR-5。
- **空授权集：通过。** FR-13 保留非授权产品语义，addendum 明确要求 replay、seed、matrix、review、Quick Dev 输出以机器可验证形式声明 empty authorization set。具体字段兼容方式可由 Spec/Architecture 决定，但不得改变空集语义。
- **current Git baseline：通过。** addendum 明确将 current Git baseline 绑定为 append-only repair round 的 freshness input；SM-6 将其纳入 fresh-checkout reconstruction。

## 残余阻塞

### B1. 三个 Evaluation Seed 的稳定名称仍缺失

上游 D1-R6 明确要求保留以下三个 candidate：

- `candidate-baseline-contamination`
- `self-hosted-knowledge-read-set-collision`
- `toolchain-policy-architecture-index-gap`

修订后的 FR-6 仍只写 “the three historical repair families”，addendum 的 `TC-D1-006` disposition 只称 “the three named repair families”，但 PRD 和 addendum 实际均未列出这三个名称。六类 Matrix Case 中出现的 `knowledge read-set collision` 和 `closed-policy architecture-index gap` 也不能替代 seed 的规范身份；第一个 seed 更没有对应的显式名称。

在 FR-6 consequences 或 addendum Downstream Contract Constraints 中逐字列出三个稳定名称，并声明每个名称恰好对应一个非授权 seed 后，此阻塞即可关闭。
