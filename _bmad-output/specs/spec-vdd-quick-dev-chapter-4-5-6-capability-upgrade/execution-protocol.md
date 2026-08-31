# Execution Protocol — VDD V0–V7 / Quick Dev Q0–Q8

本 companion 是规范性实现输入，承接 adopted companion `docs/vdd-quick-dev-chapter-4-5-6-capability-upgrade-draft.md` 第 15、16、18.5 节。它保留会改变 schema、状态机或执行行为的协议；纯 wrapper 叙述不改变合同。

## 1. VDD compiler protocol (V0–V7)

### V0 source-index

输入是 canonical requirements 和明确列出的补充来源。输出 `source-index.v1.json`，每项包含 requirement ID、repository-relative source path、唯一 anchor、source text、source hash、text hash 和 source order。路径必须在仓库内，anchor 唯一，source text 非空；输入变化使旧 semantic result 失效。

### V1 obligation-extract

通过统一 read-only wrapper 调用 `codex exec`，以参数数组、`shell=False`、只读 sandbox、stdin 或只读临时 prompt 输入，强制 JSON Schema 输出。一次只处理一个 requirement 或受 token 上限的小批次，并记录 model、prompt version、input/prompt hash、耗时和退出状态。worker 不能写计划状态或 evidence。

输出 obligation 至少包含 stable ID、source ref/span、subject、trigger、state before/after、expected behavior、observable result、forbidden result、requirement type 和 unresolved fragments。

### V2 obligation-guard

确定性检查 source ref/span 可解析、语义五元组非空、ID 无重复、每个 requirement 有 obligation、强制句片段均被覆盖，且 unsupported semantics/unresolved fragments 被显式标记。schema error 只允许带 validator error 修复一次；相同 fingerprint 再次出现即停止并返回 repair。

### V3 acceptance-compile

从通过 guard 的 obligations 生成 Acceptance：`acceptance_id`、obligation IDs、source refs、given/when/then、observable、expected、forbidden 和 assertion 语义。多 obligation 只有在 subject、生命周期、owner、oracle 和独立 assertion 均兼容时才可合并。

### V4 semantic-align

必须调用第二个独立、只读 semantic worker。它只能读取 frozen source、obligations、Acceptance 和 RED intent 候选，不能读取第一轮 worker 的解释过程。输出 covered IDs、missing/invented semantics、oracle alignment 和 repairs；`valid` 只是 coverage 输入，不是最终 pass。

### V5 exact-cover

确定性构建双向多对多图：requirement ↔ obligation ↔ Acceptance ↔ source ref ↔ RED intent ↔ slice ↔ verification lane ↔ terminal aggregation。必须无 orphan、无无源 RED intent、无 hard-uncovered；不要求 exclusive partition。

### V6 slice-partition

先按依赖拓扑、production owner、verification lane、state transition、failure family、fixture/runtime 和 write-set 建 bucket。不同生命周期、独立失败机制、不相容 fixture/runtime 或无法共同 GREEN 的节点必须拆分。不同 owner 默认拆分，但允许 producer/consumer 原子修改跨 owner 合并，前提是同一最小变更不可分、共享 state transition/lane/write set，且保留独立 assertion edge。

每个 slice contract 必须包含 `behavior_change`、`affected_subjects`、`state_transition`、`proof.acceptance_ids`、`proof.selector_intents`、`proof.assertion_ids`、`rollback_scope.production_paths` 和 `rollback_scope.state_or_schema_compatibility`。

### V7 feasibility

模拟 `Acceptance → failure intent → selector target → real production entry → allowed test/production paths → plausible GREEN owner → same-selector REFACTOR`。selector 必须绑定真实生产入口；planned new files、materializer、producer、owner、validator 均须在合法写集。固定失败、不可执行 selector、未来 evidence 依赖或无法合法 GREEN 的 slice 直接返回 `repair-vdd`。

## 2. Quick Dev protocol (Q0–Q8)

### Q0 recommendation-only

只读取当前 plan/slice、candidate、显式 run refs、changed paths 和 observation index，输出 `recommended_action`、`forbidden_actions`、`reason_code`、`blocked_by`、`reusable_observations` 和 `invalidated_observations`。不得启动模型、运行测试、创建 run 或修改状态。

### Q1 preflight

检查 contract、Acceptance、refs、failure intents、complexity class、verification lane、context lookup、minimum RED scope、upgrade conditions、selector target/fixture/cwd、非空 argv、shell=false、正 timeout、write-set、predecessor ref、candidate/plan/slice identity 和本地 `py -3`/pytest probe。缺失或不闭合时路由 `repair-vdd`；合法但缺 RED 测试时路由 `author-red`；环境缺失则 `environment-blocked`。

### Q2 RED author/materialize

若测试缺失，`red-author` 只能修改 test write set，必须调用真实 production entry，不能写 production 或制造恒定失败。随后生成 descriptor，记录 run/slice/candidate、argv、cwd、shell=false、timeout、target/fixture refs 和 Acceptance assertions；descriptor 仍是 `planned-only`。

### Q3 RED execute/classify

用等价 `subprocess.run(argv, cwd, shell=False, timeout, capture_output=True, text=True)` 执行真实进程。receipt 记录 actual argv/cwd、时间、exit code、执行/收集计数、输出摘要 hash、candidate/descriptor/target/fixture hash、observed assertion/failure ID 和 executor identity。只有 executions≥1、target/fixture/argv 匹配、声明 assertion 真实失败、非 harness/repo-noise/timeout 且 exit 语义双向匹配时才是 `expected-red`。

### Q4 production implementation

只有 clean `expected-red` 才能调用 implementation worker。调用前后计算 changed paths；必须全在 production write set，不能改 selector、fixture、Acceptance、plan 或历史 evidence；不能直接写 GREEN receipt/status。若修改测试合同，当前 RED 立即失效并回到 Q2/Q3。

### Q5 GREEN

GREEN descriptor 复用 RED selector identity、target、fixture、assertion 集合和 cwd，只允许 successor/run identity 变化。必须 executions≥1、selector identity 完全相同、exit=0、所有 assertions 为真且无 harness/repo-noise/timeout；失败保持 successor 并按 failure family 路由。

### Q6 REFACTOR

前置要求是当前 lineage 中真实 observed GREEN，且 selector identity 未变。refactor worker 只能写 production paths；随后重跑同一 slice selector 及必要 regression/schema validators。任何新增失败都阻断 slice-ready。

### Q7 slice-ready

对每个 Acceptance 验证真实 RED/GREEN/REFACTOR assertion edge、artifact ref/hash/run/candidate/selector identity 可重读匹配、result/status 由 validator 派生、coverage 只来自 dependency closure、predecessor 语义有效且无 hard-uncovered/未来 evidence。输出只能由 validator 写入。

### Q8 whole-plan terminal

terminal input 显式列出 candidate、plan、每个 slice 的 run-local predecessor/result ref/hash、terminal selector 和 active Acceptance IDs。aggregator 逐项重读 artifact，验证 lineage/hash，重算 exact cover，执行 terminal、regression、mutation 和全部 active Acceptance，最后才写 `implementation-complete`。禁止 glob/mtime 选历史结果、绑定未来 completion 或 producer 自报完成。

## 3. Failure, replay and responsibility

至少支持 `semantic-contract-gap`、`expected-red`、`unexpected-green`、`task-implementation-failure`、`test-harness-failure`、`target-binding-failure`、`repo-noise`、`timeout-no-observation`、`repeated-deterministic-failure`、`artifact-integrity`。分类从真实 observation 派生；同一 deterministic fingerprint 连续两次即停止原参数重跑；unexpected-green 转 regression/current-behavior proof 或 VDD repair。

requirements/Acceptance/ref、selector/fixture/target、production owner、descriptor compiler、validator、predecessor 的变化按影响矩阵使相应 observation 失效。production owner 变化至少重跑 GREEN/REFACTOR；若 failure intent 语义变化必须从 RED 重跑。普通非语义文档和 development governance artifact 默认不影响 TDD 路由。

最终责任链固定为：

```text
VDD → Quick Dev TDD → plan-local terminal deterministic full validation
→ implementation-complete → external independent semantic acceptance
→ acceptance-passed 或 VDD/Quick Dev repair → maintainer commit/PR/release decision
```

Quick Dev 不发布 `acceptance-passed`，外部验收不由 Quick Dev 自证；development 可跳过重型治理，但不跳过真实性 predicate。
