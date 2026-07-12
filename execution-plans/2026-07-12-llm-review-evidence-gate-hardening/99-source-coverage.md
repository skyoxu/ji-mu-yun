# 来源覆盖图

## 1. Required Books

- 00 index；
- 01 scope/authority/non-goals；
- 02 finding/severity；
- 03 adapters；
- 04 gateway/dedup/verifier/memory；
- 05 BMAD/GDS/Codex integration；
- 06 testing/observability/rollout；
- 07 phases；
- 08 risks/DoD/glossary；
- 96 global review；
- 97 requirement ledger；
- 98 source audit；
- 99 source coverage。

## 2. Required Machine Artifacts

- `schemas/review-finding.v1.schema.json`；
- `schemas/review-rejection.v1.schema.json`；
- `schemas/review-result.v1.schema.json`；
- `schemas/review-validation-fixtures.v1.json`；
- `tools/validate_whole_directory.py`。

## 3. Requirement Coverage

| Owner/phase | RFG IDs |
| --- | --- |
| 02 / R1 | RFG-001, RFG-002, RFG-003, RFG-004, RFG-022, RFG-026, RFG-028, RFG-030, RFG-031 |
| 03 / R1 | RFG-005, RFG-006, RFG-032 |
| 04 / R2 | RFG-007, RFG-008, RFG-009, RFG-010, RFG-011 |
| 04 / R2 | RFG-025 |
| 05 / R3 | RFG-012, RFG-013, RFG-023, RFG-027 |
| 03 / R3 | RFG-024 |
| 05 / R2 | RFG-014 |
| 05 / R4 | RFG-015 |
| 01 / R1 | RFG-016 |
| 01 / R0 | RFG-017 |
| 06 / R5 | RFG-018 |
| 06 / R2 | RFG-019 |
| 05 / R1 | RFG-020 |
| 96 / R0 | RFG-021, RFG-029 |

## 4. Cross-cutting Coverage

| Dimension | Covered by |
| --- | --- |
| 零 finding、failed layer | 02, schema result, fixtures |
| P0–P2 三联证明 | 02, finding schema, fixtures |
| 文档 authority graph | 03, finding schema |
| 去重与 false-positive memory | 04 |
| bounded lifecycle | 04 |
| BMAD/GDS upgrade safety | 05, 06 |
| 两类 Codex | 01, 05 |
| 项目/账户隔离 | 05, 06 |
| 上游顺序与不重复 | 00, 01, 07, 98 |
| 测试、metrics、rollout | 06 |
| 阶段退出和 DoD | 07, 08 |
| Whole-directory plan review | 96 |
| 三层 reviewer 后续路由与 provenance | 03, 04, 05, 06, 07 |

## 5. Completion

覆盖完成要求：required books/artifacts 全部存在；RFG-001 至 RFG-032 在 97 唯一且在本文件恰好覆盖一次；本地 validator 通过；96 ledger 无 Open P0–P2；Whole-directory review 结论明确“plan-ready 不等于 code-complete”。
