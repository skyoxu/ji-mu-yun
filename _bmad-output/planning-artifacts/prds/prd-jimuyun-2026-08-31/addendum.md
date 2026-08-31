# Addendum：VDD 与 Quick Dev Chapter 4/5/6 协议补充

本补充承接正式 PRD，记录不宜放入产品主叙事的机制、字段和迁移约束，供后续 `bmad-spec` 与 `bmad-architecture` 使用。

## A. 责任链

VDD 读取原始 source，生成 obligation、Acceptance、source refs、slice、failure intent、allowed write set 和 terminal predicate。VDD 不生成 command descriptor、run ID、receipt、exit code、observation 或 pass 状态。

Quick Dev 在候选冻结后物化 descriptor，执行真实进程，分类 observation，调用实现 worker，并运行 GREEN/REFACTOR 与 slice-ready。terminal aggregator 只消费显式 predecessor 和当前 candidate，最终由确定性 predicate 产生 `implementation-complete`。之后必须经过 Quick Dev 之外的独立语义验收，得到 `acceptance-passed` 或 VDD/Quick Dev repair，最后才由 maintainer 决定 commit、PR 或 release。

`codex exec` 只用于只读语义提取/对齐或受写集限制的 test/production worker；它不能直接写 plan-ready、pass 或 observed evidence。开发态治理默认关闭不代表关闭认证、TDD、写集、语义 predicate 或运行安全检查。

## B. VDD 编译阶段

```text
source-index → obligation-extract → obligation-guard → acceptance-compile
→ semantic-align → coverage → slice-partition → feasibility → plan-ready
```

1. `source-index` 确认仓库内路径、唯一锚点、非空 source text 和 source hash。
2. `obligation-guard` 拒绝遗漏强制语义、重复行为五元组、unsupported semantics 和 unresolved fragments。
3. `acceptance-compile` 为每条 active Acceptance 生成 observable/expected/forbidden oracle 与 source refs。
4. `semantic-align` 为 Acceptance 标记 valid、partial、unsupported、overbroad 或 untestable；模型结果不是最终 pass。
5. `coverage` 构建双向多对多图，要求无 orphan requirement、obligation、Acceptance、slice 或 RED intent。
6. `slice-partition` 先应用 owner、lane、stage、failure、fixture、runtime 和 write-set 硬拆分，再在兼容 bucket 内稳定合并。
7. `feasibility` 模拟 Acceptance → failure intent → selector target → production entry → write set → GREEN owner → REFACTOR；固定失败或未来 evidence 依赖直接返回 repair。

### B.1 Preflight 与 slice contract 的承重字段

每条 VDD semantic plan 的 Acceptance/slice 节点必须保留以下字段，不能在 Spec 编译时压缩掉：

```json
{
  "complexity_class": "simple|complex|architectural",
  "verification_lane": "unit|integration|matrix|runtime",
  "context_lookup_required": true,
  "context_lookup_reason": "跨模块 producer/consumer 需要实现上下文",
  "minimum_red_scope": "单一行为和其 failure family",
  "upgrade_conditions": ["跨多个测试根", "需要独立 judge"]
}
```

每个 slice contract 还必须回答行为和回滚问题，而不只是列 ID 或路径：

```json
{
  "behavior_change": "改变什么可观察行为",
  "affected_subjects": ["受影响主体"],
  "state_transition": "什么状态如何变化",
  "proof": {"acceptance_ids": [], "selector_intents": [], "assertion_ids": []},
  "rollback_scope": {"production_paths": [], "state_or_schema_compatibility": "..."}
}
```

### B.2 独立 semantic align

`semantic-align` 必须由第二个独立、只读的 semantic worker 执行。该 worker 只能读取 frozen source、obligations、Acceptance 和 RED intent 候选，不能读取首轮 worker 的解释过程或中间结论。它输出 covered obligation IDs、missing/invented semantics、oracle alignment 和 repair recommendation；其 `valid` 只是输入 coverage gate 的候选结果，不能直接决定 plan-ready。

### B.3 Slice split/merge 例外

不同 production owner 默认分开，但允许明确的 producer/consumer 原子修改跨 owner 合并，前提是两个 owner 在同一最小变更中不可分割、共享同一 state transition、同一 verification lane 和合法 write set，且每个 Acceptance 仍有独立 assertion edge。否则必须拆分。该例外不能跨生命周期阶段、未来 evidence、互不相容 fixture/runtime 或独立 failure mechanism。

## C. Quick Dev 状态机与证据

```text
planned-only → preflight-passed → red-materialized → red-observed
→ implementation-successor → green-observed → refactor-observed
→ slice-ready → whole-plan-terminal
```

禁止从 planned-only 或仅 materialized descriptor 跳到实现；expected-red 之外的 RED 分类不能进入实现；GREEN 失败不能进入 REFACTOR；缺局部 assertion 的 slice-ready 不能进入 terminal。

RED descriptor 记录 target、fixture、argv、cwd、shell=false、timeout 和 expected assertion，但 descriptor 仍是 planned-only。真实执行 receipt 至少记录 actual argv/cwd、时间、exit code、执行/收集计数、输出摘要 hash、candidate/descriptor/target/fixture hash、observed assertion/failure ID 和 executor identity。

GREEN/REFACTOR 必须保持 RED 的 selector identity、target、fixture、assertion 集合和安全 cwd；允许 run/candidate successor 变化，不允许删 case、换入口或复制 expected 值。

Quick Dev 不应重新读取整个需求目录猜测上下文。VDD 必须确定性投影每个 slice 的 `agent-context.json`：

```json
{
  "slice_id": "S...",
  "requirement_ids": [],
  "obligation_ids": [],
  "acceptance_ids": [],
  "source_refs": [],
  "contracts": [],
  "allowed_paths": [],
  "forbidden_paths": [],
  "selector_intents": [],
  "validation_commands": []
}
```

该投影是 canonical semantic plan 和 slice contract 的只读入口，不是手工新增的治理文档；缺字段时应返回 repair recommendation。

## D. Failure taxonomy 与重放

失败分类至少包括：`semantic-contract-gap`、`expected-red`、`unexpected-green`、`task-implementation-failure`、`test-harness-failure`、`target-binding-failure`、`repo-noise`、`timeout-no-observation`、`repeated-deterministic-failure`、`artifact-integrity`。分类必须来自真实 observation，不能从 registry expected 值复制。

变化影响矩阵：requirements/Acceptance/ref 变化重算 coverage 并重跑受影响 selector；selector/fixture/target/case source 变化使对应全部阶段失效；production owner 变化至少重跑 GREEN/REFACTOR，且如果 failure intent 语义发生变化必须从 RED 重跑；descriptor compiler 或 validator 变化使其生成/判断的结果失效；predecessor 变化使下游失效；普通非语义文档默认可复用；development governance artifact 不影响 TDD 路由。

## E. Terminal 与独立验收

terminal input 必须显式列出 candidate、plan、每个 slice 的 run-local predecessor/result ref/hash、terminal selector 和 active Acceptance ID。aggregator 逐个重读 artifact，重算 exact cover，执行 terminal、回归和 mutation，并拒绝 glob/mtime 历史推断、未来 completion 绑定和 producer 自报完成。

detached fixture 至少覆盖 positive、negative、mutation 以及所有 failure family；独立 judge 的输入、版本和结果与被测 Quick Dev 分离。8-25 replay 和一个全新中等任务用于 dogfood，不能以现有计划单独证明泛化能力。

## F. Profile 与迁移

- `fast-ship`：仅运行受影响 oracle，仍必须真实执行并满足 P0/P1 硬门。
- `standard`：完整 slice terminal、负例和 mutation matrix。
- `self-hosted`：增加冻结 predecessor judge 和完整反假绿套件。

旧 v1 plan 通过只读 compatibility adapter 投影为 semantic plan；任何不能映射 source、selector、write set 或 lineage 的字段都产生 repair recommendation，不得静默猜测或写回旧 evidence。旧历史 evidence 只读保留。

## G. 验收分母

“约 90% 能力”只计算属于 VDD/Quick Dev 的可泛化能力：Chapter 4 基线与 feasibility、Chapter 5 obligation/Acceptance/ref 稳定化、Chapter 6.3-6.6 TDD/recommendation/recovery，并保留 Chapter 6.9 的通用 terminal deterministic full validation。排除 Taskmaster-compatible overlay 数据模型、Godot/GdUnit、6.7/6.8、多节点治理、游戏仓 pre-commit pipeline 和 commit/PR/release authority。文档或 happy path 单测不能单独证明 90%；必须加 detached mutation、8-25 replay 和新任务盲测。
