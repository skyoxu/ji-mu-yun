# Execution Policy

本 companion 固定此前未决的 v1 实现参数。它是首版实现的规范性 authority，由 validator、恢复逻辑与验收 fixtures 共同消费。

## Retry Ceilings

| Failure family | 最大总 attempts | 达到上限后的 action |
| --- | ---: | --- |
| `timeout` | 3 | `blocked` + `inspect_transport` |
| `transport_failure` | 3 | `blocked` + `inspect_transport` |
| `obligation_extraction_invalid` | 2 | `blocked` + `inspect_extraction`；停止 model call |
| `obligation_extraction_unstable` | 3 个 valid samples | quarantine affected shard 并 `blocked`；只有有效的显式 semantic handoff 可改变路由 |

Attempt counter 由 `run_id`、failure family 和 shard/operation identity 联合定键。新 run 使用新 counter。Retry 不得把 deterministic failure 改造成 retryable failure。

## Deterministic Shards

输入是 source manifest 所绑定的精确 UTF-8 bytes；不得进行 Unicode、BOM、空白或换行 normalization。空 normative source 或 invalid UTF-8 产生 `schema_error`。可选 UTF-8 BOM 只属于第一行 bytes，不参与 heading marker 判断。Logical line 以最先出现的 `CRLF`、单独 `LF`、单独 `CR` 或 EOF 终止；terminator bytes 属于该行，未终止的末行也计一行。范围统一为 zero-based half-open byte range `[start_byte,end_byte)`；line count 是范围中完整 logical lines 的数量。

对每个 normative source 独立按 manifest path 的 UTF-8 byte order 排序，然后从 byte 0 开始重复执行 greatest-fit greedy cut：

1. 候选 boundary offset 必须严格大于当前 `start_byte`；普通候选边界位于 logical line terminator 后，EOF 也是候选边界。不得产生 zero-length shard。
2. Heading boundary 是去除可选首行 BOM 后，line content 的首个 byte 为 `#`，随后连续 1–6 个 `#`，再跟 ASCII space 或 content EOF；boundary 位于该 heading 行的原始起始 byte，因此 heading 与 BOM（如有）归入后一个 shard。
3. Blank-line boundary 位于 content 长度为零的 logical line 后；该 line terminator 归入前一个 shard。
4. Line boundary 位于任意其他 logical line 后。
5. 在不超过 32,768 bytes 且不超过 400 lines 的候选中，先选择 byte offset 最大的 heading boundary；没有时选择最大的 blank-line boundary；再没有时选择最大的 line/EOF boundary。
6. 若从当前 start 到第一个 logical-line boundary 已超过 soft limit，仅允许把这一整行作为单独 shard，但不得超过 49,152 bytes；超过 hard limit 产生 `schema_error`。除这一情形外不得超过 32,768 bytes 或 400 logical lines，也不得切开一行；600-line hard limit 仅作为防御性 validator 上限，不授权超过 400-line soft limit。

每个 shard identity 为以下精确 UTF-8 payload 的 lowercase SHA-256 hex：`vcec-shard-v1\n<manifest_path>\n<source_sha256_hex>\n<start_byte>\n<end_byte>\n`。`manifest_path` 使用 manifest 已验证的 normalized repository-relative POSIX path；hash 字段是不带 `sha256:` 前缀的 64 位 lowercase hex，整数使用无前导零十进制。Identity、范围和 source bytes 共同进入 `shard_reuse_fingerprint`。

当 valid extraction 的 obligation count、boundary、active state 或 mapping 与前一个 valid sample 不同时，shard 进入 `hotspot`。第三个 valid sample 后仍不稳定则进入 `quarantined`；该 shard 继续保留在 active normative universe 中并阻断 `conformant`。

## Bounded Output

Model-visible summary 的精确序列化结果（含尾部换行）上限为 12,000 UTF-8 bytes 和 3,000 estimated tokens。在该 envelope 内，`affected_ids` 上限为 100，`finding_ids` 为 50，structured `errors` 为 20。任何省略都必须设置 `truncated=true`，并提供 current full-artifact path 与 SHA-256。Producer 与 validator 负责计算，caller 声明不构成证据。

## Schema Registry

v1 registry 固定为：

- `run-manifest.v1.schema.json`
- `obligation-inventory.v1.schema.json`
- `shard-result.v1.schema.json`
- `conformance-matrix.v1.schema.json`
- `conformance-result.v1.schema.json`
- `conformant-receipt.v1.schema.json`
- `vdd-repair-input.v1.schema.json`

以上七个 schema 由 exact-cover 拥有。VDD 独立拥有 `.agents/skills/vdd-execution-plan/references/schemas/vdd-source-freeze-manifest.v1.schema.json`；exact-cover 只绑定并验证其 path/hash/version，不复制该 schema。不兼容的字段或语义变更必须采用新的 schema major version 与 validator identity。Prior artifacts 随即 stale；不存在隐式 compatibility alias。

## Policy Fixtures

- 相同 counter key 的第四次 timeout/transport attempt 在发起 model/transport call 前被拒绝，并返回 `blocked` + `inspect_transport`。
- 第三次 malformed extraction attempt 在 model call 前被拒绝；第二次失败已经返回 `blocked` + `inspect_extraction`。
- 同一 frozen shard 的三个 valid 且不相同的 extraction samples 产生 `quarantined`；删除该 shard 或返回 `conformant` 均验证失败。
- 对相同 manifest-bound bytes 重复分片，必须产生相同的有序 shard identities 与 zero-based half-open byte ranges；BOM、CRLF、LF、CR、无 terminator 末行、invalid UTF-8、oversized line、heading/blank-line priority、soft-limit exact boundary 与 shard-ID payload 均有 golden/negative fixtures。
- 序列化 summary 恰好位于任一上限时通过；超过任一 byte/token/item-count 上限时必须设置 `truncated=true` 并提供有效 full-artifact path/hash，否则验证失败。
- 每个 exact-cover 输出 artifact 的 schema name 必须属于七项 registry；VDD source-freeze artifact 必须匹配其独立 owner path/hash/version。Unknown、incompatible、copied 或 drifted schema fail closed，并使 prior aggregate/receipt evidence stale。
