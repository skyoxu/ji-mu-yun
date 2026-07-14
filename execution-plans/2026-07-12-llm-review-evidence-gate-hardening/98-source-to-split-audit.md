# 来源到拆分审计

## 1. 来源边界

本计划没有冻结的单体 execution-plan。批准来源由以下内容组成：

- 用户要求研究 ECC reviewer 反幻觉、四问门禁、P0/P1/P2 三联证明、零 finding 和误报清单；
- 用户批准仓库自有 standard、gateway、schema/validator、BMAD/GDS 薄适配方案；
- 用户明确要求不修改 BMAD/GDS 安装文件；
- 用户明确要求三联证明覆盖 P0–P2；
- 用户批准与 ECC 当前 review 能力对齐，并要求补齐角色/误报投影、受审内容不可信边界、deterministic preflight 和完整 Review 轮次止损，避免逐 finding 重跑；
- 用户要求修复过早启动、authority 运行中变化、Quick Dev 与 Bootstrap 重复审查、实施计划完整检查遗漏、长进程超时重复启动和高成本无预估等控制面问题；
- 用户明确要求在 7-07/7-11 完成前先具备 7-12 review 能力，并由用户手工执行 reviewer；
- ECC pinned-source 研究文档；
- `AGENTS.md` 的 Phase scope、Protected Phase Paths、shared LLM/Codex entrypoint 和文档放置规则。

因此本审计证明语义覆盖，不声称逐字还原对话或 ECC 仓库内容。

## 2. 来源要求映射

| 来源要求 | 稳定 requirement | Normative owner |
| --- | --- | --- |
| 零 finding 合法、禁止凑数 | RFG-001, RFG-004 | 02 |
| 四问事实门禁 | RFG-002 | 02 |
| 候选可信度门槛 | RFG-022 | 02, schemas |
| P0–P2 三联证明 | RFG-003 | 02, schemas |
| 代码、文档、计划审查均适用，关键负例验证目标失败原因 | RFG-005, RFG-006, RFG-021, RFG-032 | 03, 96, fixtures |
| 输出层机器门禁 | RFG-007 | 04 |
| 去重、驳回记忆、有限复审 | RFG-008, RFG-009, RFG-011 | 04 |
| blocker 独立核验与 unverified 唯一处置 | RFG-010, RFG-031 | 04, schemas |
| 不直接修改 BMAD/GDS | RFG-012 | 05 |
| upgrade-safe override 与 wrapper | RFG-013 | 05 |
| 平台开发和前台触发 Codex | RFG-014, RFG-015, RFG-016 | 01, 05 |
| 不与两个进行中重构冲突 | RFG-017 | 00, 01, 07 |
| shadow 与指标 | RFG-018 | 06 |
| evidence 隔离与兼容 | RFG-019 | 04, 06 |
| AGENTS/README/索引按 operational phase 同批同步且不提前宣称完成 | RFG-020 | 05, 07 |
| 当前 7 月 7 日审查不受干扰 | RFG-023 | 00, 05, 07 |
| Blind/Edge/Acceptance 纳入后续 candidate route | RFG-024, RFG-025 | 03, 04, 05 |
| reviewer layer 完备性、可信 policy 派生、no-spec applicability 与全链 route-version 切换 | RFG-026, RFG-027, RFG-030 | 02, 04, 05 |
| 三层 reviewer 跨合同身份一致 | RFG-028 | 02, schemas |
| fixture 分阶段 schema/composite validity | RFG-029 | 96, schemas, tools |
| handoff 前手工 Bootstrap Review、目标只读与 supplemental authority | RFG-033, RFG-034, RFG-035, RFG-039 | 01, 04, 09 |
| hash-bound stale gate、零 finding/layer 与手工 verifier | RFG-036, RFG-037, RFG-038 | 04, schemas, tools |
| Bootstrap 到 R1 合同身份连续 | RFG-040 | 05, 07 |
| Bootstrap Codex exec 跨会话模型策略与工具探针 | RFG-041 | 03, 06, 09, bootstrap/review-profiles.v1.json, tools/run_bootstrap_review.py |
| Review 对象 profile 与不可降级完整性 | RFG-042, RFG-045 | 01, 03, 06, 09, bootstrap/review-profiles.v1.json |
| Gate 重跑 verifier 决策保护 | RFG-043 | 04, 06, tools/run_bootstrap_review.py, tools/tests/test_run_bootstrap_review.py |
| Severity-safe evidence-root dedup | RFG-044 | 03, 04, 06, tools/run_bootstrap_review.py, tools/tests/test_run_bootstrap_review.py |
| Bootstrap sidecar route binding 与 gate-only 状态 Schema | RFG-046, RFG-047 | 04, 09, schemas/bootstrap-review-gate-result.v1.schema.json, schemas/review-result.v1.schema.json, tools/run_bootstrap_review.py, tools/tests/test_run_bootstrap_review.py |
| Failure tuple 占位文本拒绝 | RFG-048 | 02, 09, tools/run_bootstrap_review.py, tools/tests/test_run_bootstrap_review.py |
| Coverage 顺序无关与 verifier evidence 相关性 | RFG-049, RFG-050 | 04, 09, tools/run_bootstrap_review.py, tools/tests/test_run_bootstrap_review.py |
| 严格 JSON 有限数与 path-only 整文件覆盖 | RFG-051, RFG-052 | 02, 04, 09, tools/run_bootstrap_review.py, tools/tests/test_run_bootstrap_review.py |
| Required context class 到 scope artifact 的 prepare-time 绑定 | RFG-053 | 01, 09, bootstrap/review-profiles.v1.json, tools/run_bootstrap_review.py, tools/tests/test_run_bootstrap_review.py |
| Skill-route context 语义 predicate 与 finalized run 的 gate/finalize 不可重开 | RFG-054, RFG-055 | 01, 04, 09, tools/run_bootstrap_review.py, tools/tests/test_run_bootstrap_review.py |
| 三角色 rubric、profile 专用误报抑制与不可信内容边界 | RFG-056, RFG-057 | 03, 09, bootstrap/review-profiles.v1.json, tools/run_bootstrap_review.py, tools/tests/test_run_bootstrap_review.py |
| Reviewer 前确定性 preflight 与完整 Review 轮次止损 | RFG-058, RFG-059 | 04, 06, 08, 09, bootstrap/review-profiles.v1.json, tools/run_bootstrap_review.py, tools/tests/test_run_bootstrap_review.py |
| Reviewer 写回后的只读 coverage/candidate 自校验 | RFG-060 | 04, 06, 09, tools/run_bootstrap_review.py, tools/tests/test_run_bootstrap_review.py |
| Reviewer 前 authority freeze 与跨 run round/predecessor lineage | RFG-061, RFG-062 | 04, 09, schemas/bootstrap-review-launch-authorization.v1.schema.json, tools/run_bootstrap_review.py, tools/tests/test_run_bootstrap_review.py |
| Quick Dev/BMAD/GDS 语义互斥与 implementation plan-bound required checks | RFG-063, RFG-064 | 09, bootstrap/review-profiles.v1.json, tools/run_bootstrap_review.py, tools/tests/test_run_bootstrap_review.py |
| 高成本显式确认与 PID process lease/reattach | RFG-065 | 06, 08, 09, schemas/bootstrap-process-leases.v1.schema.json, tools/run_bootstrap_review.py, tools/tests/test_run_bootstrap_review.py |

## 3. 结构规范化

- 00 只做路由、authority 和顺序；
- 01–06 每个主题只有一个主要 owner；
- 07 只编排阶段，不复制合同；
- 08 集中风险、stop condition、DoD 和术语；
- 96–99 分别拥有 review、增量 requirement、来源审计和覆盖；
- schema 是字段/枚举结构权威，Markdown 是语义权威。

## 验收标准

- 所有用户批准要求至少映射一个 RFG，且每个 RFG 在 97 有 owner/acceptance；
- 99 证明每个 RFG 的 owner 与 phase；
- 本审计不把 ECC pilot workflow 描述成已量化验证的生产方案；
- 本审计不把本计划 PASS 描述成代码完成。
