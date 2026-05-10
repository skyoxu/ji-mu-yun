# Phase A Prototype Lane Implementation Route

- Title: Phase A Prototype Lane Implementation Route
- Date: 2026-05-11
- Status: accepted
- Supersedes: none
- Superseded by: none
- Branch: main
- Git Head: 0b20008cb9110c8f74394a438a588c23c1c727ca
- Why now: Phase A 已从通用云端任务执行平台收敛为公网账号体系下的 Prototype lane 云端原型平台，需要明确实现路线，避免在平台自举阶段误用 Chapter 3-6 正式交付流水线。
- Context: Phase A 当前范围是 single-admin 账号、按账号项目配额、单项目单 workspace、admin-defined project rule、Chapter 2 bootstrap、prototype 7day playable、prototype TDD、new-api 手动绑定、Caddy HTTPS、ASP.NET Core 8 Minimal API、SQLite 元数据和项目级 runner lock。
- Decision: 本次 Phase A 不使用 Chapter 3-6 作为实现流程；采用 architecture overlay + execution plan + implementation backlog + targeted tests + local hard checks 的实现路线。Chapter 3-6 保留为 Phase A 之后正式产品化或长期交付能力的路线，不作为 Phase A 自举实现路径。
- Consequences: 实现工作按可验证切片推进；每个切片产出局部测试和 `logs/**` 证据；不创建 `.taskmaster/tasks/*.json` 正式任务，不要求 acceptance refs、overlay refs 或 Chapter 6 review pipeline。若某个切片改变安全、runner lock、LLM gateway、项目规则等长期架构边界，则补充 decision log 或 ADR。
- Recovery impact: 后续恢复 Phase A 时先读 `execution-plans/2026-05-11-phase-a-prototype-lane-implementation-backlog.md`，再读本决策日志和 `docs/architecture/overlays/PHASE-A-CLOUD-RUNNER/08/08-Phase-A-Cloud-Runner-Architecture.md`；不要直接进入 Chapter 3-6。
- Validation: Validate with `py -3 scripts/python/validate_recovery_docs.py --dir decision-logs`, `py -3 scripts/python/validate_recovery_docs.py --dir execution-plans`, `py -3 scripts/python/validate_overlay_execution.py --prd-id PHASE-A-CLOUD-RUNNER`, and targeted implementation tests per slice.
- Related ADRs: ADR-0018, ADR-0019, ADR-0025, ADR-0031
- Related execution plans: execution-plans/2026-05-10-phase-a-cloud-runner-requirements.md; execution-plans/2026-05-11-phase-a-prototype-lane-implementation-backlog.md
- Related task id(s): n/a，因为 Phase A 自举实现明确不进入 Taskmaster / Chapter 3-6 正式任务流。
- Related run id: n/a，因为本决策是实现路线决策，不绑定既有 pipeline run。
- Related latest.json: n/a，因为本决策不对应 task-scoped latest.json。
- Related pipeline artifacts: n/a

## Rationale

Chapter 3-6 的价值在正式业务任务交付中很高，但本次 Phase A 是平台自身的原型化自举。若直接套用 Chapter 3-6，会引入 task triplet、acceptance refs、semantic review、Chapter 6 recovery sidecar 等正式交付成本，反而会延迟 Prototype lane 云端平台的第一版闭环。

Phase A 应该先证明这些核心能力：

- 用户能登录公网平台。
- 用户能在账号配额内创建原型项目。
- 项目能通过 Chapter 2 bootstrap 形成可用 metadata。
- 用户能通过 prototype 7day playable router 完成 intake 与 Day 1-5 证据。
- 用户能运行 prototype TDD 与查看工件。
- 平台能通过 new-api 手动绑定进行 LLM 访问和计费关联。

这些能力更适合小切片实现和 targeted tests，而不是完整 Chapter 3-6。

## Trigger To Reconsider

重新评估是否进入 Chapter 3-6 的触发条件：

- Phase A 已经可稳定跑通完整 Prototype lane。
- 平台功能开始服务长期正式交付，而不只是原型验证。
- 需要多人协作、正式验收、正式 release gate 或长期维护任务拆分。
- 某个平台功能开始改变已接受 ADR 或全局 workflow contract。
