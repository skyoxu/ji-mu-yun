---
title: '模型可见工具轮次合同硬化'
type: 'bugfix'
created: '2026-08-12'
status: 'done'
baseline_commit: 'bd287a3e869da898c516f3b9b553e20d6f3539fa'
review_loop_iteration: 0
context:
  - 'C:/jimuyun/docs/model-visible-tool-round-contract.md'
  - 'C:/jimuyun/docs/adr/ADR-0038-phase-evidence-sidecars-readback.md'
  - 'C:/jimuyun/knowledge/toolchain-workflow-index.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 合同仍允许自报 preflight、证据内凭据、负重试、fallback/Schema
分叉、无生命周期的 background complete、历史 summary 覆盖和 measurement
sidecar 漏校验，可能产生不可信验收或泄密。

**Approach:** 统一 Schema、dependency-free validator、producer、示例和回归
测试；未注册 adapter 的并行继续 fail closed，background complete 必须绑定
job/退出码/日志范围/轮询信息，本地 evidence 只追加创建。

## Boundaries & Constraints

**Always:** 保留现有改动；拒绝 symlink/reparse escape、凭据和绝对 host path；
producer 从 operation/round evidence 重算指标；正式 Schema 与 fallback 同义；
没有受信 adapter 时并行 fail closed。

**Ask First:** 需要外部密钥、签名服务、真实 provider adapter、修改 Accepted
ADR 安全边界或标记 observed=true 时先停止。本修复不注册真实 adapter。

**Never:** 回滚/清理其他变更，覆盖历史 evidence，修改 live/Hosted/共享
LLM 入口，或放宽校验、跳过测试。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| UNTRUSTED_PREFLIGHT | 并行 summary 引用未注册 adapter 的 sidecar | validator 拒绝并行授权 | 返回结构化 contract 错误 |
| REPARSE_ROOT | workspace root 或 evidence path 是 symlink/reparse | validator/producer fail closed | 不读取或写入目标 |
| SECRET_IN_EVIDENCE | 本地日志含 ghp_/authorization 等凭据 | summary 被拒绝且诊断不回显凭据 | 返回 evidence/redaction 错误 |
| BLOCKED_ZERO_ATTEMPTS | blocked operation attempts=0 | summary 合法，retries=0 | 非 blocked attempts=0 仍拒绝 |
| BACKGROUND_INCOMPLETE | background operation 缺 job/lifecycle 或日志范围 | 不得声明 complete | 返回 lifecycle 错误 |
| EXISTING_OUTPUT | 输出 summary 已存在 | 新写入被拒绝，原文件不变 | 返回 append-only 错误 |
| MEASUREMENT_MISMATCH | sidecar bytes/events/boundary 与 summary 不一致 | validator 拒绝 | 返回交叉字段错误 |

</frozen-after-approval>

## Code Map

- `scripts/sc/schemas/model-visible-tool-round-summary.v1.schema.json` -- operation lifecycle shape.
- `scripts/sc/schemas/model-visible-tool-preflight.v1.schema.json` -- adapter identity and manifest binding.
- `scripts/python/validate_model_visible_tool_round_summary.py` -- all structural, trust, redaction and cross-field gates.
- `scripts/python/build_model_visible_tool_round_summary.py` -- normalization and append-only output.
- `scripts/python/tests/test_validate_model_visible_tool_round_summary.py` -- confirmed counterexamples.
- `docs/model-visible-tool-round-contract.md` and `docs/workflows/examples/model-visible-tool-round-*.json` -- public contract and golden data.

## Tasks & Acceptance

**Execution:**

- [x] Update the three schemas and both Python implementations -- enforce trust, lifecycle, redaction, reparse containment, metric/measurement parity and append-only writes.
- [x] Extend focused tests -- encode all seven findings without requiring jsonschema.
- [x] Update the contract and golden examples -- document unregistered-preflight fail-closed and background evidence requirements.

**Acceptance Criteria:**

- Given a self-authored preflight sidecar with no registered adapter, when parallelization is requested, then validation fails closed and cannot produce complete.
- Given a symlink/reparse root or evidence member, when producer or validator resolves it, then it rejects the path before I/O.
- Given a common credential in summary text or local evidence bytes, when validation runs, then it rejects without exposing the credential in diagnostics.
- Given a blocked operation with zero attempts, when metrics are recomputed, then retries is zero and the summary validates.
- Given a background operation, when lifecycle/job/exit/log-range evidence is absent or inconsistent, then complete is rejected; a bound terminal lifecycle can validate.
- Given an existing output path, when the producer writes, then it returns an error and preserves the original bytes.
- Given a measurement sidecar or external boundary with mismatched bytes, events, or observed state, when validation runs, then it rejects the summary.

## Spec Change Log

## Design Notes

The trusted preflight adapter registry remains empty until separately accepted; local
booleans cannot prove authorization. Lifecycle may be null only for a never-started
blocked background operation; every started job binds a verified log evidence ref.

## Verification

**Commands:**

- `py -3 -m unittest discover -s scripts/python/tests -p "test_validate_model_visible_tool_round_summary.py"` -- all focused tests pass.
- `py -3 -m py_compile scripts/python/build_model_visible_tool_round_summary.py scripts/python/validate_model_visible_tool_round_summary.py scripts/python/tests/test_validate_model_visible_tool_round_summary.py` -- compile succeeds.
- `py -3 scripts/python/validate_model_visible_tool_round_summary.py docs/workflows/examples/model-visible-tool-round-summary.example.json --root .` -- golden example validates.
- Parse all three JSON schemas with Python and run the explicit fallback-path counterexamples -- no schema or parity drift.

## Suggested Review Order

**Contract and trust boundaries**

- Start with the public fail-closed contract and deferred external enforcement boundary.
  [`model-visible-tool-round-contract.md:17`](../../docs/model-visible-tool-round-contract.md#L17)

- Follow the central cross-field state, metric, boundary, and attribution checks.
  [`validate_model_visible_tool_round_summary.py:922`](../../scripts/python/validate_model_visible_tool_round_summary.py#L922)

- Inspect preflight authority, manifest, and registered-adapter gating.
  [`validate_model_visible_tool_round_summary.py:688`](../../scripts/python/validate_model_visible_tool_round_summary.py#L688)

**Evidence and lifecycle integrity**

- Review canonical evidence binding, hashing, redaction, ownership, and alias checks.
  [`validate_model_visible_tool_round_summary.py:602`](../../scripts/python/validate_model_visible_tool_round_summary.py#L602)

- Review started background job lifecycle and complete-state proof requirements.
  [`validate_model_visible_tool_round_summary.py:849`](../../scripts/python/validate_model_visible_tool_round_summary.py#L849)

- Confirm producer metrics derivation and validation before publication.
  [`build_model_visible_tool_round_summary.py:146`](../../scripts/python/build_model_visible_tool_round_summary.py#L146)

- Confirm append-only atomic publication preserves existing evidence.
  [`build_model_visible_tool_round_summary.py:282`](../../scripts/python/build_model_visible_tool_round_summary.py#L282)

**Schemas and regressions**

- Check the operation schema's zero-attempt blocked constraints.
  [`model-visible-tool-round-summary.v1.schema.json:172`](../../scripts/sc/schemas/model-visible-tool-round-summary.v1.schema.json#L172)

- Check preflight manifest and timezone-aware authority evidence shape.
  [`model-visible-tool-preflight.v1.schema.json:36`](../../scripts/sc/schemas/model-visible-tool-preflight.v1.schema.json#L36)

- Finish with adversarial regression coverage for the repaired boundaries.
  [`test_validate_model_visible_tool_round_summary.py:339`](../../scripts/python/tests/test_validate_model_visible_tool_round_summary.py#L339)
