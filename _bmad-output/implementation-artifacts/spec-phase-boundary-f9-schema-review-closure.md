---
title: 'Phase Boundary F9 Schema Review Closure'
type: 'chore'
created: '2026-07-12'
status: 'done'
review_loop_iteration: 1
baseline_commit: 'f58c1d2819ca4cffeb5ad02bdf06fd5a0718990b'
context:
  - 'C:/jimuyun/AGENTS.md'
  - 'C:/jimuyun/execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/96-global-review-and-split-validation.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** F9 review 发现 handoff schemas 虽可解析，但 hash、签名、双 snapshot、source-map、derived observation、deferral 与 validator 约束不足，当前机械 PASS 不能证明计划可实施。

**Approach:** 修紧 schemas/validator，把 F9 findings 纳入 97/99 和显式 closure evidence，修正 06/98/99 术语，再以正向与 mutation fixture 复验。

## Boundaries & Constraints

**Always:** 计划保持 `paused`；区分本地 plan-readiness 与外部 protected verifier；使用稳定 `F9-P0/P1/P2-##`；schema 身份、hash、状态、路径和字段跨文档一致。

**Ask First:** 选择真实 verifier/HSM/KMS/lock backend，启动 BH-HANDOFF/BH-SF0A，改变阶段顺序或 protected runtime。

**Never:** 修改 `2026-07-07`、Phase 源码、runtime、live data；用本地脚本替代 protected verifier；由 PBR 映射自动关闭 finding；宣称代码完成。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|---|---|---|---|
| valid bundle | 严格 schemas、fixtures、closure evidence | validator PASS | 不改变 handoff 状态 |
| invalid trust object | 假 SHA-256、空/重复签名、单 snapshot、非法路径 | 稳定 rule ID 失败 | fail closed |
| unresolved finding | 有 PBR、无 closure evidence | `plan_open` | 阻止 PASS |
| missing original bytes | 19-family registry | 只证明批准的语义覆盖 | 禁止文本保真声明 |

</frozen-after-approval>

## Code Map

- `../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/schemas/**` -- machine contracts/fixtures。
- `../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/tools/validate_whole_directory.py` -- plan validator。
- `../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/97-post-split-requirements-ledger.md` -- F9/PBR/closure ledger。
- `../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/98-original-to-split-audit.md`、`99-source-coverage.md` -- original/owner coverage。

## Tasks & Acceptance

**Execution:**
- [x] `schemas/**` -- 分离 commit/SHA-256，约束签名、双 snapshot、deferral、observation、source-map N/A/path/identity。
- [x] `tools/validate_whole_directory.py` -- 校验 schema/fixture、99 owner/phase、显式 closure、F9 和 mutation 分支。
- [x] `06`, `96`～`99` -- 修正术语，增加 F9 requirements、批准 provenance 和覆盖。
- [x] generated fixtures -- 重新生成显式 closure registry。
- [x] Whole-directory review -- 正向和负向验证全部通过。

**Acceptance Criteria:**
- Given trust contract 被削弱，when validator 运行，then 使用稳定错误失败。
- Given 99 owner/phase 与 97 不同，when validator 运行，then mismatch 失败。
- Given finding 无 closure evidence，when registry 生成，then 保持 `plan_open` 并阻止 PASS。
- Given 原单体不可恢复，when 审查 98/99，then 只接受批准/hash 的 semantic baseline。

## Spec Change Log

- 2026-07-12: Implemented F9 schema, evidence, validator, ledger and coverage closure; positive validation and all declared mutation cases pass as expected.
- 2026-07-12: Adversarial review patched path traversal, signer/payload/approver consistency, RFC 3339 time validation, event ancestry, ActiveRegistry manifest binding, non-empty/unique observations, closure-ref shape, owner existence and atomic generated-registry writes. Local approval/closure evidence claims were narrowed to declarations pending protected verification. KEEP: strict hash/signature/snapshot/source-map/observation contracts and the local-versus-protected verifier boundary.
- 2026-07-12: Primary-agent review replaced direct generated-registry writes with same-directory temporary write, flush/fsync and atomic `os.replace`; reran all positive and mutation checks. KEEP: generated output is written only after every validation error is cleared.
- 2026-07-12: Final blind/edge review closed remaining false-PASS paths: exact fixture inventories, supported-keyword allowlist, `$ref` siblings, expected mutation error matching, unknown-case failure, closure review/status binding, path traversal/ADS, recursive deferral aliases, source-map semantic uniqueness/N-A class, coverage suffixes and generation-input recheck. External approval signatures and handoff-time locking remain explicitly protected-verifier responsibilities.

## Design Notes

Schema 拒绝非法 machine objects；本地 validator 检查 schema/fixture、映射和 closure freshness；外部 verifier 仍负责锁、真实签名、custody 和 BH-HANDOFF。

## Verification

**Commands:**
- `py -3 execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/tools/validate_whole_directory.py --write-generated` -- generated registry fresh。
- `py -3 execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/tools/validate_whole_directory.py` -- plan-readiness PASS。
- `py -3 -m py_compile execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/tools/validate_whole_directory.py` -- syntax PASS。
- mutation fixtures -- bad hash/signature/snapshot/path/owner/phase/open finding 全部失败。

**Result:** `py_compile`、`git diff --check`、atomic temporary-file cleanup PASS；`--write-generated` 与普通 plan-readiness validation 均 PASS（10 schemas、116 PBR、119 findings、0 open、19 original families）；23 个 schema/plan mutation cases 分别由 `WD025`、`WD027`、`WD028`、`WD029`、`WD030` fail closed，未知 mutation ID 非零退出。

## Suggested Review Order

**Validation Core**

- Start with the complete plan-readiness validation flow and atomic generation boundary.
  [`validate_whole_directory.py:538`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/tools/validate_whole_directory.py#L538)

- Independent closure evidence is joined with coverage; PBR mapping alone stays open.
  [`validate_whole_directory.py:199`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/tools/validate_whole_directory.py#L199)

- Positive and negative schema fixtures exercise the supported local contract subset.
  [`validate_whole_directory.py:417`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/tools/validate_whole_directory.py#L417)

- Generated registry writes use flush/fsync and atomic replacement after validation.
  [`validate_whole_directory.py:82`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/tools/validate_whole_directory.py#L82)

**Trust Schemas**

- Manifest separates commit/hash identities and binds two ordered completion snapshots.
  [`upstream-handoff-manifest.v1.schema.json:7`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/schemas/upstream-handoff-manifest.v1.schema.json#L7)

- Source map qualifies promised paths, blocks traversal, and models true N/A rows.
  [`handoff-source-map.v1.schema.json:19`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/schemas/handoff-source-map.v1.schema.json#L19)

- Closure evidence uses explicit review declarations with stable reference shape.
  [`finding-closure-evidence.v1.schema.json:7`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/schemas/finding-closure-evidence.v1.schema.json#L7)

**Ledger And Boundaries**

- F9 findings become owned, phased requirements with stable acceptance URIs.
  [`97-post-split-requirements-ledger.md:123`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/97-post-split-requirements-ledger.md#L123)

- Plan-readiness explicitly remains weaker than protected cryptographic verification.
  [`96-global-review-and-split-validation.md:7`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/96-global-review-and-split-validation.md#L7)

- Original-family provenance claims payload integrity, not unavailable-byte fidelity.
  [`98-original-to-split-audit.md:3`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/98-original-to-split-audit.md#L3)
