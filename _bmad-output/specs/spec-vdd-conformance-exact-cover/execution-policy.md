# Execution Policy

本 companion 记录 architecture reconciliation 后的 runtime-policy contract。Maintainer-owned approved registry 是具体运行值的唯一 authority；下列历史数值只保留为 candidate defaults，未经 registry ratification、stable policy identity 与 canonical hash binding 不得生效。

## Candidate Retry Defaults

| Failure family | Candidate maximum | Stable exhaustion action |
| --- | ---: | --- |
| `timeout` | 3 | `blocked` + `inspect_transport` |
| `transport_failure` | 3 | `blocked` + `inspect_transport` |
| `obligation_extraction_invalid` | 2 | `blocked` + `inspect_extraction`；停止 model call |
| `obligation_extraction_unstable` | 3 个 valid samples | quarantine affected shard 并 `blocked`；只有有效的显式 semantic handoff 可改变路由 |

Architecture 只要求每个 retry family 有 finite positive maximum、stable exhaustion outcome 和 hash-bound approved profile。Attempt counter 由 `run_id`、failure family 和 shard/operation identity 联合定键；retry 不得把 deterministic failure 改造成 retryable failure。

## Ratified Shard Identity And Candidate Partition Defaults

输入是 source manifest 所绑定的精确 UTF-8 bytes；不得进行 Unicode、BOM、空白或换行 normalization。空 normative source 或 invalid UTF-8 产生 `schema_error`。可选 UTF-8 BOM 只属于第一行 bytes，不参与 heading marker 判断。Logical line 以最先出现的 `CRLF`、单独 `LF`、单独 `CR` 或 EOF 终止；terminator bytes 属于该行，未终止的末行也计一行。范围统一为 zero-based half-open byte range `[start_byte,end_byte)`；line count 是范围中完整 logical lines 的数量。

The exact source-byte model, boundary semantics, and `vcec-shard-v1` identity below are ratified. The 32,768/400 and 49,152/600 thresholds and the specific greedy profile remain candidate runtime-policy values until approved by the maintainer registry. Under an approved profile, process each normative source independently in manifest-path UTF-8 byte order:

1. 候选 boundary offset 必须严格大于当前 `start_byte`；普通候选边界位于 logical line terminator 后，EOF 也是候选边界。不得产生 zero-length shard。
2. Heading boundary 是去除可选首行 BOM 后，line content 的首个 byte 为 `#`，随后连续 1–6 个 `#`，再跟 ASCII space 或 content EOF；boundary 位于该 heading 行的原始起始 byte，因此 heading 与 BOM（如有）归入后一个 shard。
3. Blank-line boundary 位于 content 长度为零的 logical line 后；该 line terminator 归入前一个 shard。
4. Line boundary 位于任意其他 logical line 后。
5. 在不超过 32,768 bytes 且不超过 400 lines 的候选中，先选择 byte offset 最大的 heading boundary；没有时选择最大的 blank-line boundary；再没有时选择最大的 line/EOF boundary。
6. 若从当前 start 到第一个 logical-line boundary 已超过 soft limit，仅允许把这一整行作为单独 shard，但不得超过 49,152 bytes；超过 hard limit 产生 `schema_error`。除这一情形外不得超过 32,768 bytes 或 400 logical lines，也不得切开一行；600-line hard limit 仅作为防御性 validator 上限，不授权超过 400-line soft limit。

每个 shard identity 为以下精确 UTF-8 payload 的 lowercase SHA-256 hex：`vcec-shard-v1\n<manifest_path>\n<source_sha256_hex>\n<start_byte>\n<end_byte>\n`。`manifest_path` 使用 manifest 已验证的 normalized repository-relative POSIX path；hash 字段是不带 `sha256:` 前缀的 64 位 lowercase hex，整数使用无前导零十进制。Identity、范围和 source bytes 共同进入 `shard_reuse_fingerprint`。

当 valid extraction 的 obligation count、boundary、active state 或 mapping 与前一个 valid sample 不同时，shard 进入 `hotspot`。Candidate profile 在第三个 valid sample 后仍不稳定时进入 `quarantined`；实际 sample maximum 与 transition predicate 必须来自 approved profile。任何 quarantined shard 都继续保留在 active normative universe 中并阻断 `conformant`。

## Bounded Output

Model-visible summary 的精确 wire serialization（含 schema-required 尾部换行）上限为 12,000 UTF-8 bytes，这是唯一 hard gate。`estimated_tokens_v1 = ceil(exact_serialized_utf8_bytes / 4)`，并以 `measurement_mode: estimated`、`measurement_method: utf8-bytes-ceil-div-4-v1` 输出，仅作 telemetry。`affected_ids=100`、`finding_ids=50`、`errors=20` 是 candidate presentation defaults；任何省略都必须设置 `truncated=true` 并提供 current full-artifact path/hash。

## Candidate Schema Layout

首版 implementation contract 可 ratify、amend 或 defer 下列 candidate filenames；最终 registry 不得产生 duplicate authority：

- `run-manifest.v1.schema.json`
- `obligation-inventory.v1.schema.json`
- `shard-result.v1.schema.json`
- `conformance-matrix.v1.schema.json`
- `conformance-result.v1.schema.json`
- `conformant-receipt.v1.schema.json`
- `vdd-repair-input.v1.schema.json`

Exact-cover owns its consumer/result schemas after implementation-contract ratification. VDD independently owns its source-freeze producer schema; exact-cover only binds and verifies its path/hash/version and never copies it. Incompatible field or semantic changes require a successor schema major version and validator identity; prior artifacts become stale and no compatibility alias may create duplicate authority.

## Policy Fixtures And Ratification

- Candidate `3/3/2/3` retry profile 只有在 registry approval 后才运行其边界 fixtures；所有 profiles 都必须证明 finite maximum、unique attempts、stable exhaustion 和 evidence invalidation on policy change。
- Candidate three-sample instability profile is tested only after registry approval; every approved profile must prove that its terminal quarantine transition retains the shard and blocks `conformant`.
- 对相同 manifest-bound bytes 重复分片，必须产生相同的有序 shard identities 与 zero-based half-open byte ranges；BOM、CRLF、LF、CR、无 terminator 末行、invalid UTF-8、oversized line、heading/blank-line priority、soft-limit exact boundary 与 shard-ID payload 均有 golden/negative fixtures。
- Serialized summary exactly at 12,000 bytes passes; above it fails explicitly rather than silently truncating a success artifact. Token telemetry never changes pass/fail. Candidate item-count limits are tested only when selected by the approved profile.
- Every output artifact must match the implementation-contract-ratified registry; VDD source-freeze artifact must match its independent owner path/hash/version. Unknown, incompatible, copied, aliased, or drifted schemas fail closed and stale prior aggregate/receipt evidence.
