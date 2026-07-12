# 计划新增要求台账

所有 requirement 均来自用户批准的 ECC 研究结论和本仓升级安全约束。状态 `active|superseded`；每条 active 要求必须具有唯一 owner 和 acceptance ref。

| ID | Requirement | Owner | Phase | Acceptance ref | Status |
| --- | --- | --- | --- | --- | --- |
| RFG-001 | 零 finding 合法，禁止 minimum finding count | 02 | R1 | `review-gate://RFG-001/zero-finding-fixture` | active |
| RFG-002 | 所有 candidate 通过四问事实门禁 | 02 | R1 | `review-gate://RFG-002/fact-gate-tests` | active |
| RFG-003 | P0–P2 全部要求三联证明 | 02 | R1 | `review-gate://RFG-003/proof-triplet-tests` | active |
| RFG-004 | failed layer 与 clean 明确区分 | 02 | R1 | `review-gate://RFG-004/incomplete-result-fixture` | active |
| RFG-005 | code/document/plan 使用共享核心和专用 adapter | 03 | R1 | `review-gate://RFG-005/adapter-contract-tests` | active |
| RFG-006 | 文档 finding 必须绑定 authority、consumer、validator | 03 | R1 | `review-gate://RFG-006/document-adapter-fixtures` | active |
| RFG-007 | gateway 做 schema、line-range、severity/status、evidence、hash 和 guard 校验 | 04 | R2 | `review-gate://RFG-007/gateway-validation-tests` | active |
| RFG-008 | dedup 使用稳定 evidence fingerprint | 04 | R2 | `review-gate://RFG-008/dedup-tests` | active |
| RFG-009 | rejected/refuted 在输入未变时不得重现 | 04 | R2 | `review-gate://RFG-009/disposition-memory-tests` | active |
| RFG-010 | P0/P1 由独立 verifier 核验且 verifier 不得发现新问题 | 04 | R2 | `review-gate://RFG-010/verifier-scope-tests` | active |
| RFG-011 | 一次 discovery/verification，P2 不触发自动循环 | 04 | R2 | `review-gate://RFG-011/lifecycle-tests` | active |
| RFG-012 | 不修改 installer-managed BMAD/GDS 文件 | 05 | R3 | `review-gate://RFG-012/upgrade-regression` | active |
| RFG-013 | 使用 team custom override 与仓库 wrapper | 05 | R3 | `review-gate://RFG-013/customization-resolver-tests` | active |
| RFG-014 | 平台开发 Codex 通过共享 gateway | 05 | R2 | `review-gate://RFG-014/platform-pipeline-tests` | active |
| RFG-015 | 前台触发 Codex 通过共享 gateway 和项目隔离 adapter | 05 | R4 | `review-gate://RFG-015/phase-route-isolation-smoke` | active |
| RFG-016 | 两类 Codex 共享 severity/schema，仅 adapter 不同 | 01 | R1 | `review-gate://RFG-016/schema-identity-test` | active |
| RFG-017 | 运行时接入等待两个上游重构完成 | 01 | R0 | `review-gate://RFG-017/upstream-handoff-evidence` | active |
| RFG-018 | shadow 指标同时评估 precision、recall、噪音和成本 | 06 | R5 | `review-gate://RFG-018/shadow-report` | active |
| RFG-019 | evidence sidecar 遵守隔离、redaction 和兼容性 | 06 | R2 | `review-gate://RFG-019/evidence-security-tests` | active |
| RFG-020 | AGENTS/README/索引从 R1 起按能力 operational 阶段同批同步，R6 只做最终状态收口 | 05 | R1 | `review-gate://RFG-020/documentation-sync-check` | active |
| RFG-021 | Whole-directory review 使用同一事实门禁、允许零 finding，并结构化验证 96–99 | 96 | R0 | `review-gate://RFG-021/plan-review-result` | active |
| RFG-022 | candidate confidence 必须不低于 0.8 且不能替代三联证明 | 02 | R1 | `review-gate://RFG-022/confidence-threshold-test` | active |
| RFG-023 | 当前 7 月 7 日 in-flight review 与历史 finding 不受本计划切换影响 | 05 | R3 | `review-gate://RFG-023/in-flight-route-isolation` | active |
| RFG-024 | Blind、Edge、Acceptance 三个 reviewer 只能经 adapter 产生 candidate | 03 | R3 | `review-gate://RFG-024/three-layer-adapter-tests` | active |
| RFG-025 | 合并 finding 必须保留三个 reviewer 的机器可读 provenance | 04 | R2 | `review-gate://RFG-025/source-reviewer-dedup-test` | active |
| RFG-026 | required/completed/failed/skipped reviewer layer 必须完备、互斥并阻止 all-skipped clean | 02 | R1 | `review-gate://RFG-026/skipped-layer-result-test` | active |
| RFG-027 | old/new review route 的 candidate、finding、result、rejection、fingerprint 和 metrics 必须绑定 routeVersion | 05 | R3 | `review-gate://RFG-027/route-version-isolation-test` | active |
| RFG-028 | source、failed、skipped、rejection 必须使用同一 reviewer role vocabulary | 02 | R1 | `review-gate://RFG-028/reviewer-role-vocabulary-test` | active |
| RFG-029 | fixture 必须区分 JSON Schema validity 与 schema+gateway composite validity | 96 | R0 | `review-gate://RFG-029/staged-fixture-validation` | active |
| RFG-030 | requiredLayers 必须由 gateway-assigned reviewProfile/policyRevision 派生，producer 不得改选 profile 或自行缩小 | 02 | R1 | `review-gate://RFG-030/trusted-layer-policy-test` | active |
| RFG-031 | unverified P0/P1 必须具有 gateway-owned class/disposition，并与 blocked/incomplete 唯一对应 | 02 | R1 | `review-gate://RFG-031/unverified-disposition-test` | active |
| RFG-032 | 关键 negative fixture 必须断言目标失败原因，不能依赖无关约束维持 invalid | 03 | R1 | `review-gate://RFG-032/targeted-negative-fixture-test` | active |

## 验收标准

- ID 唯一、连续且没有未声明 supersession；
- 每条 active requirement 在 99 中恰好覆盖一次 owner/phase；
- acceptance ref 稳定且不能只指向 assistant prose；
- 新 requirement 先进入本台账，再进入实施。
