# 来源到拆分审计

## 1. 来源边界

本计划没有冻结的单体 execution-plan。批准来源由以下内容组成：

- 用户要求研究 ECC reviewer 反幻觉、四问门禁、P0/P1/P2 三联证明、零 finding 和误报清单；
- 用户批准仓库自有 standard、gateway、schema/validator、BMAD/GDS 薄适配方案；
- 用户明确要求不修改 BMAD/GDS 安装文件；
- 用户明确要求三联证明覆盖 P0–P2；
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
