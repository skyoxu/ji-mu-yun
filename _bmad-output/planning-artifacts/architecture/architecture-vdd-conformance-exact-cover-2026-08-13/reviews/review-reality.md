# Reality Consistency Review

- `reviewer`: `reality-current-tech`
- `artifact`: `../ARCHITECTURE-SPINE.md`
- `verdict`: `NEEDS_CHANGES`
- `finding_count`: 2

## Scope And Evidence

本审查只核对 committed architecture decisions 与当前仓库合同、实现现实及已声明新增边界的一致性。完整读取并核对了 architecture spine、`docs/model-visible-tool-round-contract.md`、`docs/fastctx-file-operation-output-contract.md`、`docs/skill-input-consumption-contract.md`、`scripts/python/skill_input_consumption.py`、VDD strict standard 以及本 SPEC 的 authority/data contract。

已确认以下决定具有现实支撑：当前仓库 canonical helper 使用 UTF-8、recursive `sort_keys=True` 与 compact separators；模型可见 artifact 已有 12,000 UTF-8 bytes 精确上限；token 估算统一为 `ceil(exact_utf8_bytes / 4)` 且允许标记 `estimated`；仓库路径合同已有 resolved-root containment、repository-relative POSIX path、lexical symlink/reparse-point rejection；VDD、maintainer、Quick Dev 与 Acceptance 的 lifecycle ownership 彼此分离。

## Findings

### P1-1 - Canonical JSON 对象键排序算法仍未闭合

- `location`: `ARCHITECTURE-SPINE.md:57`, `ARCHITECTURE-SPINE.md:131`
- `trigger`: VDD producer 与 exact-cover consumer 由不同语言或不同 JSON serializer 实现，payload 含非 BMP key、私用区 key 或其他能区分 UTF-8、UTF-16 与 Unicode code-point 排序的对象键。
- `required_state`: `repository-canonical-json.v1` 必须规定一个完整、可独立实现的对象键比较算法；golden vectors 应验证规则，而不能替代规则。
- `bad_outcome`: 两边都满足“recursively sorted object keys”并通过有限 vectors，仍可能对同一 payload 输出不同 canonical bytes，重现本架构本来要消除的 manifest/fingerprint mismatch。
- `guard_gap`: 当前 Python helper 的 `sort_keys=True` 事实上采用 Python string/code-point lexical order，但 spine 只写了“sorted”，没有把该语义提升为合同。数组路径排序反而明确为 unsigned UTF-8 bytes，进一步说明 object-key order 不能靠默认理解。
- `required_change`: 明确采用与仓库 Python helper 一致的 Unicode scalar/code-point lexical order，或明确采用另一算法并提供迁移边界；同时补一组能区分 code-point、UTF-8、UTF-16 排序的 normative vectors。不要仅写“Unicode including non-BMP”。

### P1-2 - Implementation authorization preflight 的现状、owner 与强度表述错误

- `location`: `ARCHITECTURE-SPINE.md:39`, `ARCHITECTURE-SPINE.md:99`
- `trigger`: downstream 按 diagram/AD-9 寻找所谓 `Existing VDD authorization preflight`，或把 conformant receipt 当成可选 prerequisite。
- `required_state`: 对声明 canonical flow 的 plan，maintainer-owned `plan-ready -> implementation-authorized` 边界必须新增并执行 current receipt preflight；VDD 仍只拥有 `draft` 与 `plan-ready`。
- `bad_outcome`: 实现可能错误地把 preflight 放入 VDD，或者因 `may require` 而保留无需 receipt 的 canonical-flow authorization 路径，既违反当前 lifecycle ownership，也弱化源 requirements 的 mandatory prerequisite。
- `guard_gap`: 当前仓库有 maintainer-owned transition contract，但未发现现成的 conformant-receipt machine preflight；`quick-dev-tdd-adapter` 当前只路由已发布的 lifecycle state。源 requirements 与 SPEC 明确要求 existing authorization owner “必须”拒绝 missing/stale/non-conformant receipt，而不是可选消费。
- `required_change`: 将 diagram 节点改为 `Maintainer-owned implementation authorization boundary (new receipt preflight)`；将 AD-9 的 `may require` 改为 canonical-flow plan 上的 `must require`，并明确这是对现有 owner 的新增 gate，不是 VDD 已有能力。

## Verdict

`NEEDS_CHANGES`。两个 finding 都直接影响本 spine 要闭合的核心 identity 或 authority invariant。除这两项外，没有发现 canonical JSON 基础约定、12,000-byte gate、token telemetry、路径安全规则、VDD/exact-cover write authority 或 lifecycle 分层方面的其他重要现实冲突。
