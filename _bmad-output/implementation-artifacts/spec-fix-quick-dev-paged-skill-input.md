---
title: 'Quick Dev TDD 分页 Skill Input 兼容性修复'
type: 'bugfix'
created: '2026-08-16'
status: 'done'
baseline_commit: '08f50705a50ac5f39e977575bc09a32ebe3f9ef8'
review_loop_iteration: 0
context:
  - 'C:/jimuyun/docs/skill-input-consumption-contract.md'
  - 'C:/jimuyun/.agents/skills/quick-dev-tdd-adapter/SKILL.md'
  - 'C:/jimuyun/.agents/skills/quick-dev-tdd-adapter/references/skill-input-budget.paged-v1.json'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Quick Dev TDD 的 strict Skill Input contract 仍使用 262,144 UTF-8 bytes 的 serialized snapshot 上限。8-15 计划的完整、hash-bound source closure 约 731 KiB，因而在 action selection 前被正确阻断，无法进入 RED；直接截断、删历史证据或使用 raw snapshot 都会破坏协议。

**Approach:** 复用共享 launcher 已实现的 `paged-frozen-snapshot-stdin`，将 Quick Dev contract 的 aggregate ceiling 提升到 1 MiB，并以 32 KiB page transport 逐源覆盖至 EOF。contract、budget fixture、child request、coverage sidecar 和 validator 继续保持同一 hash-bound、fail-closed 语义。

## Boundaries & Constraints

**Always:** 保留 `plan_directory` 和 `target_files` 完整 source closure；所有源按当前 hash 冻结；每个源的 page ordinal、byte range、UTF-8 内容和 EOF coverage 可复算；`ready=true` 仍不授权 implementation、acceptance 或 commit；使用 `codex-cli` 且禁用 child file tools。

**Ask First:** 若 1 MiB 仍不足，暂停并升级预算决策，不静默增加上限；若目标目录 source count 超过 128，先修 contract scope，不改 validator ceiling。

**Never:** 不删除或重写历史 plan evidence；不把 snapshot 改为自由摘要；不允许 caller 覆盖 contract；不回退 serialized oversized input；不改变 lifecycle ownership、authorization 或 Acceptance route。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| 8-15 plan | 完整 source closure 约 731 KiB | paged request，aggregate <= 1 MiB，coverage 到 EOF | 超过 1 MiB 在 child launch 前 fail closed |
| page mutation | page hash、ordinal、range 或 source hash 改变 | coverage/decision mismatch | `ready=false`，不进入 RED |
| serialized fallback | contract 仍为 serialized 或 caller 移除 paging | 不尝试原始大快照 fallback | 明确 contract/input-mode failure |
| source drift | plan file 或 directory membership 改变 | candidate receipt stale | 重新 prepare 新 binding |

</frozen-after-approval>

## Code Map

- `.agents/skills/quick-dev-tdd-adapter/references/skill-input-contract.v1.json` -- Quick Dev strict contract and paged limits.
- `.agents/skills/quick-dev-tdd-adapter/references/skill-input-budget.paged-v1.json` -- shared budget identity consumed by contract validation.
- `scripts/python/launch_skill_input_consumer.py` -- paged request, page transport, coverage sidecar and child binding.
- `scripts/python/validate_skill_input_consumption.py` -- ready gate and page coverage validation.
- `scripts/python/tests/test_skill_input_consumption.py` -- shared paged/mutation regression coverage.
- `scripts/python/tests/test_skill_contract_composition.py` -- producer/consumer contract composition.

## Tasks & Acceptance

**Execution:**

- [x] `.agents/skills/quick-dev-tdd-adapter/references/skill-input-contract.v1.json` -- select paged mode, 1 MiB aggregate and 32 KiB chunks -- unblock complete medium-plan closure without weakening source identity.
- [x] `.agents/skills/quick-dev-tdd-adapter/references/skill-input-budget.paged-v1.json` -- update the shared budget values -- keep contract and validator limits hash-consistent.
- [x] `scripts/python/tests/test_skill_input_consumption.py` -- add 8-15-sized paged and stale-coverage fixtures -- prove no truncation or fallback.
- [x] `scripts/python/tests/test_skill_contract_composition.py` -- cover Quick Dev producer/consumer paged handoff -- prove first authoritative gate accepts only current ready evidence.

**Acceptance Criteria:**

- Given the current 8-15 source closure, when Quick Dev prepares and launches the child, then paged transport completes every source to EOF and produces a ready receipt.
- Given a page hash, range, ordinal, source hash, or coverage sidecar mutation, when validation runs, then it fails closed before action selection or RED.
- Given an oversized aggregate above 1 MiB or an invalid chunk size, when contract validation runs, then it rejects the contract without raw fallback.
- Given the updated contract, when existing shared and composition suites run, then prior serialized, redaction, source-graph, and sidecar protections remain passing.

## Spec Change Log

## Design Notes

The shared launcher already supports paged mode and exact byte-contiguous coverage. This repair changes only the Quick Dev consumer contract and its bound budget identity; it does not duplicate paging logic or change other consumers.

## Verification

**Commands:**

- `py -3 -m unittest scripts/python/tests/test_skill_input_consumption.py` -- expected: all shared paging, mutation, and legacy tests pass.
- `py -3 -m unittest scripts/python/tests/test_skill_contract_composition.py` -- expected: Quick Dev composition gate passes.
- `py -3 scripts/python/validate_skill_input_consumption.py --help` -- expected: shared validator remains available.
- Quick Dev 8-15 preflight -- expected: `ready=true` with `paged-frozen-snapshot-stdin` and `authorizes=[]`.

## Suggested Review Order

**Paged Consumer Contract**

- Start with the consumer-owned paging ceiling and transport mode.
  [`skill-input-contract.v1.json:17`](../../.agents/skills/quick-dev-tdd-adapter/references/skill-input-contract.v1.json#L17)

- Verify the budget identity binds both aggregate and page limits.
  [`skill-input-budget.paged-v1.json:1`](../../.agents/skills/quick-dev-tdd-adapter/references/skill-input-budget.paged-v1.json#L1)

**Fail-Closed Paging**

- Review deterministic UTF-8 page ranges and line cursor projection.
  [`launch_skill_input_consumer.py:457`](../../scripts/python/launch_skill_input_consumer.py#L457)

- Review page acceptance and post-redaction summary budget enforcement.
  [`launch_skill_input_consumer.py:539`](../../scripts/python/launch_skill_input_consumer.py#L539)

- Verify coverage against redacted model-visible bytes, chunks, lines, and EOF.
  [`validate_skill_input_consumption.py:164`](../../scripts/python/validate_skill_input_consumption.py#L164)

- Confirm optional paged budget fields are contract-bound when declared.
  [`skill_input_consumption.py:291`](../../scripts/python/skill_input_consumption.py#L291)

**Regression Evidence**

- Read the end-to-end paging, redaction, and mutation regressions.
  [`test_skill_input_consumption.py:1027`](../../scripts/python/tests/test_skill_input_consumption.py#L1027)

- Read the Quick Dev consumer-specific contract composition check.
  [`test_skill_contract_composition.py:35`](../../scripts/python/tests/test_skill_contract_composition.py#L35)

- Review separately scoped protocol follow-ups without widening this repair.
  [`deferred-work.md:20`](deferred-work.md#L20)
