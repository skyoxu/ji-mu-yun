---
title: 'Phase Boundary Whole Directory Review Closure'
type: 'chore'
created: '2026-07-12'
status: 'done'
review_loop_iteration: 0
baseline_commit: 'f58c1d2819ca4cffeb5ad02bdf06fd5a0718990b'
context:
  - 'C:/jimuyun/AGENTS.md'
  - 'C:/jimuyun/README.md'
  - 'C:/jimuyun/execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Whole-directory review 发现 2 个 P0、12 个 P1 和 3 个 P2：目录缺少实际 schemas 和可运行的 plan-readiness validator，historical finding 无 closure 状态，PBR/98/99/阶段/术语/文档同步存在不一致。

**Approach:** 增加仓库内只负责文档可实施性的 validator、真实 JSON Schemas 和 generated closure fixture；保留仓库外 BH-HANDOFF verifier 作为安全信任根；同步 00～99、AGENTS.md 和 README.md，并重跑 Whole-directory review。

## Boundaries & Constraints

**Always:** 计划保持 `paused`；不修改 `2026-07-07` 上游目录、Phase 源码、runtime、live DB/workspace；仓库内 validator 只能证明 plan readiness，不能签发 Permit 或满足 BH-HANDOFF 信任。

**Ask First:** 选择实际外部 verifier/HSM/KMS/lock backend，启动 BH-HANDOFF/BH-SF0A，修改 protected Phase paths。

**Never:** 用仓库内脚本替代受保护 verifier；把 `plan_closed` 声称为代码完成；在 README 中把未落地 `/ui-v2`/Permit/Preflight 写成当前能力。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| plan-readiness review | 顶层+全部 Markdown+schemas/fixtures | 本地 validator 输出 zero findings/open closures | 缺文件/链接/映射/字段立即失败 |
| BH-HANDOFF review | signed contract + protected verifier | 仓库外 verifier 校验安全证据 | 本地 validator 结果不得被接受为信任证明 |
| original source unavailable | 无原始字节快照 | 使用显式 19-family canonical registry 做语义覆盖 | 禁止声称逐行/字节一致 |

</frozen-after-approval>

## Code Map

- `../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/tools/validate_whole_directory.py` -- plan-readiness validator 和 generated closure registry。
- `../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/schemas/**` -- bootstrap/handoff/review/original-family schemas 与 fixtures。
- `../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/96-global-review-and-split-validation.md` -- 分离 plan review 与 protected handoff review。
- `../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/97-post-split-requirements-ledger.md` -- F8/PBR/acceptance/closure registry。
- `../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/98-original-to-split-audit.md` -- 19-family semantic source audit。
- `../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/99-source-coverage.md` -- books/schemas/PBR/original-family 覆盖。
- `../../AGENTS.md`, `../../README.md` -- 实施前过渡门禁和当前能力/后续同步时机。

## Tasks & Acceptance

**Execution:**
- [x] `schemas/**`, `tools/validate_whole_directory.py` -- 新增可解析 schema/fixture 和可重跑 validator。
- [x] `00～09`, `96` -- 统一 phase、handoff tuple、deferral、derived snapshot、containment、retry 和 glossary。
- [x] `97` -- 增加 PBR-085～101、stable acceptance refs、finding closure registry 和 F5/F8 覆盖。
- [x] `98`, `99` -- 用 19-family canonical registry 完成可机械语义覆盖，不做虚假字节保真。
- [x] `AGENTS.md`, `README.md` -- 增加实施前门禁与按阶段同步规则，不提前声称功能。
- [x] 重跑 Whole-directory review -- 链接、JSON、PBR/finding/owner/AC/original coverage 全部通过。

**Acceptance Criteria:**
- Given 下游计划目录，when 运行本地 validator，then 所有 Markdown/JSON/PBR/finding/AC/original-family 检查为零错误。
- Given BH-HANDOFF 未开始，when 阅读 AGENTS/README，then 文档明确功能尚未落地且不允许越过上游门禁。
- Given finding registry，when 检查 Open 项，then plan-review status 无 `open`，同时仍明确 PBR 是待实施要求。

## Spec Change Log

## Verification

**Commands:**
- `py -3 execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/tools/validate_whole_directory.py --write-generated` -- PASS: `markdown=15 schemas=9 pbr=101 findings=104 open=0 original_families=19`。
- `py -3 execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/tools/validate_whole_directory.py` -- PASS: 同上，generated registry freshness 和 zero-open 均通过。
- `py -3 -m py_compile execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/tools/validate_whole_directory.py` -- PASS。
- 临时目录负向校验 -- PASS：unresolved local schema `$ref` 报 `WD006`，重复 `ORIG-19` 报 `WD021`，缺少 coverage section 以 `WD000` fail closed 而非未处理 traceback。
- `git status --short` -- 已核对；上游 `2026-07-07`、Phase 源码、runtime 和 live data 的既有变更均未由本规格修改或回退。

## Suggested Review Order

**计划边界与可信验证**

- 先确认 paused、上游串行和 plan-readiness 非实施完成的总边界。
  [`2026-07-11-phase-frontend-boundary-hardening-execution-plan.md:79`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan.md#L79)

- 查看本地计划校验与受保护 BH-HANDOFF verifier 的职责分离。
  [`96-global-review-and-split-validation.md:7`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/96-global-review-and-split-validation.md#L7)

**机械契约与追溯闭环**

- 审查链接、schema、PBR、finding 与原始语义族的 fail-closed 校验逻辑。
  [`validate_whole_directory.py:128`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/tools/validate_whole_directory.py#L128)

- 核对 F8 修复如何落到 PBR-085～101 的 owner、phase 和验收引用。
  [`97-post-split-requirements-ledger.md:105`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/97-post-split-requirements-ledger.md#L105)

- 核对无法恢复原字节时采用 19-family 语义覆盖的诚实边界。
  [`98-original-to-split-audit.md:3`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/98-original-to-split-audit.md#L3)

- 检查全部 machine artifacts、101 条 PBR 与 19-family 的唯一覆盖。
  [`99-source-coverage.md:20`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/99-source-coverage.md#L20)

**当前状态文档同步**

- 确认 agent 路由不会把未来 Permit、Preflight 或 React 能力当成当前事实。
  [`AGENTS.md:30`](../../AGENTS.md#L30)

- 确认产品说明清楚标注计划未实施及各阶段同步时机。
  [`README.md:30`](../../README.md#L30)
