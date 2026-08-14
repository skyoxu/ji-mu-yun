# Authority 投影与 Segment 合同

## 1. 完整读取

符合当前 model-visible budget 的 selected normative authority 必须完整传输：

- 文件工具返回 `Partial` 时，parent 按工具给出的精确 offset 续传至 `Complete`；
- 截断输入不能进入 reviewer launch；
- 摘要不能替代 selected authority；
- 读取工具可以是 FastCtx 或满足同一完整性合同的等价能力。

## 2. Range Projection

超出 budget 的 authority 只能由 parent builder 生成 Range Projection。Projection 必须绑定：

- repository-relative source path；
- full source hash；
- inclusive byte/line range 及其明确坐标语义；
- extracted bytes hash；
- inclusion reason；
- changed-set、requirement、acceptance 关联；
- identity 所需的 encoding/newline policy。

Reviewer 不能自行选择范围。Projection 不能删除适用于 changed-set 的约束、反例或例外。Path、range、source hash 或 extracted bytes 任一 mutation 必须失败。

Range Projection 沿用 shared file/model tooling owner 发布的 model-visible budget policy；whole-file/projection decision 与 descriptor 必须绑定所选 policy identity。具体 threshold 仍是 policy 数据，不得由实现者冻结。

## 3. Canonical Segment Identity

以下消费者必须调用同一个 canonical projection/hash contract：

- segment assignment producer；
- reviewer request producer；
- child receipt producer；
- parent receipt validator；
- coverage fold；
- retry/cache identity。

Architecture 必须定义一个足以绑定下列语义的 Segment Descriptor：

- review、candidate、closure 和 input identity；
- reviewer role；
- original artifact path 与 frozen artifact hash；
- inclusive byte/line range；
- segment ordinal 和 total count；
- exact segment bytes hash；
- projection/payload schema version；
- selected model identity（仅当 reuse/cache 语义依赖模型时）。

Canonical serialization、domain separation、complete identity reference、attempt 分层和 stable descriptor projection 遵循 adopted Architecture Spine 的 AD-5 与 AD-8。Artifact owner schema 负责字段命名，但不得改变上列语义集合。

## 4. Segment-only Snapshot

- Child 只能读取 assigned segment 和最小 parent validation attestation。
- Child workspace 不包含可遍历的完整 Artifact View。
- Snapshot path 由 controller 投影为唯一绝对路径，并绑定 frozen bytes。
- 相对路径、live repository path 或不存在的 snapshot 在 semantic work 前失败。
- Reviewer 不能声明未分配范围的 coverage。
- 同一 segment retry 保持相同 descriptor identity。

## 5. Access-proof Identity

Executable、model、reasoning 和 environment identity 从已验证 access proof/launch authorization 自动继承。Operator 不重新输入 executable path。人工覆盖、静默 fallback 或不同 run-layer identity 在 child launch 前失败；显式 fallback 需要独立 identity-bound authorization。

## 6. Required Mutation Rejection

至少覆盖：

- artifact path；
- range start/end；
- segment ordinal/order；
- artifact/full source hash；
- extracted bytes；
- reviewer role；
- model identity（适用时）；
- absolute snapshot path 到 live path；
- old candidate receipt replay；
- unassigned coverage claim；
- terminal 后保留 acquired lease；
- 活跃前序 lease 上启动相同 write-set retry。

Identity 和 boundary test 只能证明投影正确，不能替代语义检出回归。
