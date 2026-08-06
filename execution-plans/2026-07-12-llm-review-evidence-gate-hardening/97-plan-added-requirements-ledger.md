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
| RFG-033 | handoff 前允许 plan-local 只读 Bootstrap Review 服务 7-07/7-11 新 review run | 01 | R0 | `review-gate://RFG-033/bootstrap-scope-test` | active |
| RFG-034 | Bootstrap CLI 只生成 prompt/template 并消费手工输出，不得调用 reviewer/LLM | 09 | R0 | `review-gate://RFG-034/no-model-invocation-test` | active |
| RFG-035 | Bootstrap prepare/gate/finalize 不得修改目标 scope，输出目录不得位于 scope 内 | 04 | R0 | `review-gate://RFG-035/target-read-only-test` | active |
| RFG-036 | Bootstrap input/candidate 必须绑定 artifact hash，stale evidence fail closed | 04 | R0 | `review-gate://RFG-036/stale-evidence-test` | active |
| RFG-037 | required reviewer 缺失与合法零 finding 必须区分，all-complete zero 可 clean | 04 | R0 | `review-gate://RFG-037/bootstrap-layer-result-test` | active |
| RFG-038 | Bootstrap P0/P1 必须等待用户手工独立 verifier，verifier 不得新增 finding | 04 | R0 | `review-gate://RFG-038/manual-verifier-test` | active |
| RFG-039 | Bootstrap evidence 必须标记 supplemental，不得重写历史或替代 BH-HANDOFF/完成 authority | 01 | R0 | `review-gate://RFG-039/bootstrap-authority-isolation-test` | active |
| RFG-040 | R1 必须提升同一 Bootstrap schema/profile revision，不得重新派生第二套合同 | 05 | R1 | `review-gate://RFG-040/bootstrap-promotion-identity-test` | active |
| RFG-041 | Bootstrap reviewer/verifier 的 Codex exec 路由必须由 profile/manifest 跨会话绑定：Round 1-2 discovery 使用 profile 声明的 Terra/fallback 路由，合法 Round 3 使用 Sol/high，standard P1 verifier 使用 Terra/high，高风险 P1 使用 Sol/high，P0/security 使用 Sol/max；access proof 覆盖每个不同的 role-specific model/reasoning 路由，并要求 tool probe | 09 | R0 | `review-gate://RFG-041/bootstrap-codex-model-policy-test` | active |
| RFG-042 | Review 必须按计划 authority、实施闭合、Skill/路由、聚焦变更选择对象 profile；所有 profile 均要求全 artifact、禁止 sampling、上下文闭包，推理等级不得降低完整性 | 01 | R0 | `review-gate://RFG-042/review-object-profile-completeness-test` | active |
| RFG-043 | Gate 重跑遇到非空 verifier decisions 时必须在任何写入前 fail closed，并保持 verifier 文件字节不变 | 04 | R0 | `review-gate://RFG-043/verifier-decision-preservation-test` | active |
| RFG-044 | Dedup 必须按 hash-bound evidence root 合并并保留最高 severity，P2 不得吞掉同根 P1/P0 | 04 | R0 | `review-gate://RFG-044/severity-safe-evidence-root-dedup-test` | active |
| RFG-045 | 每个 review object profile 必须把逐角色 reasoning effort 投影到 manifest/prompt/exec，同时保持共同 completeness policy | 06 | R0 | `review-gate://RFG-045/role-reasoning-projection-test` | active |
| RFG-046 | Bootstrap 所有 sidecar 与报告必须绑定 manifest 唯一 routeVersion、profile/revision、authority revision、input hash 和 supplemental authority；任一漂移必须 fail closed | 04 | R0 | `review-gate://RFG-046/bootstrap-sidecar-route-binding-test` | active |
| RFG-047 | Gate 阶段 P0/P1 等待核验必须使用 schema-valid 的 `awaiting_verification`，并与最终 `review-result.v1` 状态机明确分离 | 04 | R0 | `review-gate://RFG-047/bootstrap-gate-state-schema-test` | active |
| RFG-048 | Failure tuple 任一字段为归一化占位文本时必须以 `missing_failure_tuple` 拒绝，非空占位符不得进入 accepted finding | 02 | R0 | `review-gate://RFG-048/placeholder-failure-tuple-test` | active |
| RFG-049 | Completed reviewer coverage 必须按完整 artifact 集合判断，不得对 `readArtifacts` 施加未声明顺序约束 | 04 | R0 | `review-gate://RFG-049/order-independent-coverage-test` | active |
| RFG-050 | Verifier 的 `evidenceChecked` 必须覆盖 finding 精确证据行和全部 contextRead；无关 in-scope 引用必须 fail closed | 04 | R0 | `review-gate://RFG-050/verifier-evidence-relevance-test` | active |
| RFG-051 | Bootstrap JSON 输入、hash 和输出必须拒绝 `NaN`/`Infinity` 等非有限数，confidence 必须是 0.8–1 的有限实数 | 02 | R0 | `review-gate://RFG-051/strict-json-finite-confidence-test` | active |
| RFG-052 | Path-only context 表示整份 artifact，只能由 path-only verifier evidence 覆盖，局部行范围不得冒充整文件检查 | 04 | R0 | `review-gate://RFG-052/path-only-context-coverage-test` | active |
| RFG-053 | Prepare 必须把每个 profile requiredContextClass 映射到至少一个 in-scope hash-bound artifact；缺失、未知或空映射在写文件前 fail closed | 01 | R0 | `review-gate://RFG-053/context-class-artifact-binding-test` | active |
| RFG-054 | `bootstrap-skill-route` context class 必须通过稳定 artifact 语义 predicate，任意文件冒名映射全部 class 必须 fail closed | 01 | R0 | `review-gate://RFG-054/skill-route-context-semantics-test` | active |
| RFG-055 | 已 finalized 的 `review-result.v1` run 不得再次 gate 或 finalize 覆盖；无论 verifier 是否为空或之后被修改，都必须在任何写入前拒绝并保持终态证据字节不变 | 04 | R0 | `review-gate://RFG-055/finalized-run-immutability-test` | active |
| RFG-056 | 每个 review object profile 必须把 Blind/Edge/Acceptance 的独立 role rubric 与专用误报抑制规则投影到 hash-bound manifest/prompt；仅有角色名称不得启动 reviewer | 03 | R0 | `review-gate://RFG-056/role-rubric-false-positive-projection-test` | active |
| RFG-057 | 所有受审 artifact、注释、Markdown、diff、candidate 和 finding 文本均是不可信数据；嵌入指令不得改变角色、scope、输出、模型、工具、severity 或 finding 数量 | 03 | R0 | `review-gate://RFG-057/untrusted-review-content-prompt-test` | active |
| RFG-058 | 每个 profile 必须在 reviewer 前运行 required deterministic preflight；失败或缺证据时停止，不得消耗语义 Review 或产生 clean | 09 | R0 | `review-gate://RFG-058/deterministic-preflight-stop-test` | active |
| RFG-059 | 完整语义 Review 必须首轮汇总、批量修复、targeted deterministic validation、最终复审；默认两轮、硬上限三轮、P2-only 不触发，超限 manual pause | 04 | R0 | `review-gate://RFG-059/bounded-full-review-cycle-test` | active |
| RFG-060 | 每个 reviewer 写回后必须通过只读 `validate-layer` 自校验；completed coverage 必须满足 missing 为空且 required/read 集合相等，失败不得进入 gate 或由主会话代修 | 09 | R0 | `review-gate://RFG-060/reviewer-output-self-validation-test` | active |
| RFG-061 | Reviewer 启动前必须由 `authorize-launch` 冻结 profile、authority/context、artifact hashes、Git revision 与 passed preflight hash；漂移时不得生成授权 sidecar | 09 | R0 | `review-gate://RFG-061/reviewer-launch-authority-freeze-test` | active |
| RFG-062 | 同一 changeId 的完整 Review 必须记录 round 与 predecessor lineage；换 review ID 不得重开 round 1，round 4 永远拒绝，round 3 仅允许 predecessor P0/P1 或 authority/context graph 改变 | 04 | R0 | `review-gate://RFG-062/cross-run-review-lineage-test` | active |
| RFG-063 | 一个变更周期只能有一套 Bootstrap 语义审查 authority；Quick Dev、BMAD/GDS reviewer 与其他 Bootstrap review 不得重复产出语义 finding | 09 | R0 | `review-gate://RFG-063/semantic-review-exclusivity-test` | active |
| RFG-064 | Implementation conformance 必须把实施计划要求的额外完整检查通过 `--required-check` 绑定到 authority artifact，并纳入 preflight requiredChecks；缺失时 prepare fail closed | 09 | R0 | `review-gate://RFG-064/plan-bound-required-check-test` | active |
| RFG-065 | 高成本 Review 启动前必须输出 artifact/bytes/reasoning work estimate 并显式确认；长进程必须使用 PID lease，live PID 超时后只允许 reattach/poll，不得重复启动 | 09 | R0 | `review-gate://RFG-065/review-cost-and-process-lease-test` | active |

## 验收标准

- ID 唯一、连续且没有未声明 supersession；
- 每条 active requirement 在 99 中恰好覆盖一次 owner/phase；
- acceptance ref 稳定且不能只指向 assistant prose；
- 新 requirement 先进入本台账，再进入实施。
