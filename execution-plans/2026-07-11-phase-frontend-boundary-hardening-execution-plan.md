# Phase 平台边界、React 与 Codex 治理执行计划

- Title: Phase 平台边界、React 与 Codex 治理执行计划
- Status: paused
- Branch: main
- Plan authoring baseline: non-authoritative; the only executable source baseline is the `finalCommit` selected by UpstreamHandoffActiveRegistry after BH-HANDOFF
- Goal: 在 `2026-07-07` GDD-to-module workflow hardening 完整实施、全局复审和 closure 证据冻结之后，不复制或改写其 route/status/readback/diagnostic/UI/GDD 业务规范，继续建立可信 Codex 授权、进程隔离、事务化文件回写、`/ui-v2` React 技术迁移、平台内部模块化、correlation、版本和生产治理。
- Scope: 顶层文件是恢复索引；详细实施规则位于同名分册目录。本计划与 `2026-07-07` 重构严格串行：上游未完成 BH-HANDOFF 时，禁止创建或启动本计划的代码、DB、React、Gate、runtime 或 protected-path 实施任务；只允许只读分析和不落地的草案。
- Current step: 计划保持 paused，唯一当前工作是等待并验证 `2026-07-07` 上游 Phase 0-6、global review、closure ledger、durable standards 和最终 commit 完成；BH-HANDOFF 未通过前不得创建 BH-SF0A 或任何更晚阶段的实施任务。
- Last completed step: 完成 Whole-directory F8 计划闭环：补齐真实 schemas、plan-readiness validator、finding closure registry、101 条 PBR 稳定验收引用、19-family 原计划语义覆盖，以及 AGENTS/README 的 paused/分阶段同步声明；这只证明计划可实施，不表示代码完成或 BH-HANDOFF 已通过。
- Stop-loss: BH-HANDOFF 未通过时，禁止修改 `PhaseA.Platform/**`、`PhaseA.Platform.Tests/**`、runtime、Phase scripts、metadata DB、Browser/Program、React 工程或 standards/ADR；禁止启用 Change Origin Gate、legacy freeze、Hosted pilot 或 React pilot。Handoff 后仍禁止将 Codex 自检当授权、只靠事后 diff 声称隔离、修改 live DB/live workspace/secret/历史 evidence 或无授权修改 protected paths。
- Next action: 继续执行并完成 `2026-07-07` 重构；其 Phase 6/global review/closure 完成后，按预冻结 BootstrapHandoffContract 运行 handoff-only 验证，原子发布 Manifest/SourceMap/derived snapshots/StateEvent/ActiveRegistry。只有 BH-HANDOFF 通过后，才可由用户授权创建 BH-SF0A task、owner/approver 和决策日志。
- Recovery command: py -3 -c "from pathlib import Path; print(Path(r'execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan.md').read_text(encoding='utf-8'))"
- Open questions: 1) 远程 Attestation Authority 采用哪个组织/安全管理域与 HSM/KMS 产品；2) hosted Codex/Acceptance runner 的 Windows restricted-token/tool-broker 原型能否满足 provider/tool 网络分离；3) React 工程最终目录名称；4) Phase 首个正式 SemVer；5) 完整 per-project Windows runner 账户和 NTFS ACL 是否进入本轮预算。BH-HANDOFF bootstrap verifier/lock/signature 不是待定项；其冻结契约和允许后端必须在 handoff task 前选定并签名。
- Exit criteria: 本目录 plan-readiness validator 对全部 Markdown、schemas/fixtures、101 条 PBR、104 条 finding closure、19 个原始语义族和 AGENTS/README 同步规则通过；随后受保护的 BH-HANDOFF 绑定上游最终 commit、零未解决 finding 的 Phase 0-6/global review/closure evidence、上游已承诺 machine fixtures/standards/compatibility refs，并通过 HandoffSourceMap 绑定下游只读 frontend/API/persistence observations；Manifest + StateEvent + ActiveRegistry 唯一生效；下游未复制上游业务权威；十三个分册必做验收通过；独立 signer、paired manifests、trusted Test/Acceptance Attestation、Platform/Hosted containment、fenced Mutation、`/ui-v2`、architecture/Data/version/evidence/performance 均有机械验证。Plan-readiness PASS 不等于任何实施 phase 或代码完成。
- Related ADRs: ADR-0032, ADR-0037；BH-HANDOFF 前必须有 bootstrap verifier/lock/registry/signature 安全决策记录；BH-SF0A 及后续必须新增或更新 Threat Model/Permit Trust、Codex Containment、React/Auth、内部依赖方向和 Phase Version ADR。
- Related decision logs: BootstrapHandoffContract 签名记录和双人审批引用在 handoff-only task 前必须存在；BH-SF0A 通用 Authority 决策日志仍不得在 BH-HANDOFF 前进入实施。
- Related execution plans: `execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/00-index.md`, `execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/00-index.md`
- Related task id(s): n/a，上游全部完成后仅可创建一个 handoff-only task；BH-HANDOFF 通过前禁止创建 BH-SF0A 实施 task；之后仍不得在无 task/owner/approver 情况下修改 protected Phase paths。
- Related run id: n/a，当前未运行实现或验证流水线。
- Related latest.json: n/a，当前未绑定 task-scoped pipeline。
- Related pipeline artifacts: n/a，后续 task/run evidence 写入各自 `logs/` 路径。

## Authority

- 当前 GDD-to-module 实施权威：[上游重构索引](2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/00-index.md)。
- 本计划详细权威：[本计划分册索引](2026-07-11-phase-frontend-boundary-hardening-execution-plan/00-index.md)。
- 上游拥有业务 route、status、readback、diagnostic、UI capability/style 和 GDD workflow。
- 本计划拥有 Permit/attestation、Profile/containment、Mutation transaction、React 技术迁移、平台内部架构、版本和证据治理。
- 上游完成后由不可变 UpstreamHandoffManifest、append-only UpstreamHandoffStateEvent 和唯一 UpstreamHandoffActiveRegistry 冻结其业务 authority；下游只可从冻结上游代码/产物生成标记为 `downstream_derived` 的技术快照，不得反向要求上游补充新业务合同。
- Durable rule 落地后必须迁移到 standards/ADR/workflow；执行计划不是最终规范源。

## Gate Summary

| Gate | 条件 | 允许启动 |
| --- | --- | --- |
| BH-HANDOFF | 上游 Phase 0-6/global review 零未解决 P0/P1/P2；业务 capability deferral 仅按上游 ledger 分类；预冻结 bootstrap verifier/lock/source-map contract 完整 | 原子发布 Manifest + StateEvent + ActiveRegistry；仍不允许下游实施 |
| BH-SF0A | BH-HANDOFF 通过，实际 owner/approver/task/ADR/protected-path 授权完整 | 仅启动通用 downstream threat model、Attestation Authority/verifier/signer 和 manifest-family 决策；不重做 BH-HANDOFF bootstrap，BH-SF0B 及更晚阶段仍等待直接前序退出 |
| BH-REACT1 | BH-RP1 退出，active handoff 不变，frontend/API downstream-derived snapshots 和 compatibility 清单验证 | `/ui-v2` shell 和单 surface 技术迁移 |
| BH-ARCH | BH-REACT2 全部 mandatory surface 退出，architecture/compatibility baseline 批准 | 平台架构 ratchet；BH-DATA/BH-RELEASE 仍等待直接前序 |

## Implementation Books

1. [Authority, Threat Model, And Gates](2026-07-11-phase-frontend-boundary-hardening-execution-plan/01-authority-threat-model-and-gates.md)
2. [Permit Trust And Attestation](2026-07-11-phase-frontend-boundary-hardening-execution-plan/02-permit-trust-and-attestation.md)
3. [Profiles, Preflight, And Containment](2026-07-11-phase-frontend-boundary-hardening-execution-plan/03-profiles-preflight-and-containment.md)
4. [Mutation Lease, Journal, And Acceptance](2026-07-11-phase-frontend-boundary-hardening-execution-plan/04-mutation-lease-journal-and-acceptance.md)
5. [React UI-V2 Migration](2026-07-11-phase-frontend-boundary-hardening-execution-plan/05-react-ui-v2-migration.md)
6. [Platform Architecture, Data, And Version](2026-07-11-phase-frontend-boundary-hardening-execution-plan/06-platform-architecture-data-and-version.md)
7. [Evidence, Telemetry, And Performance](2026-07-11-phase-frontend-boundary-hardening-execution-plan/07-evidence-telemetry-and-performance.md)
8. [Implementation Phases](2026-07-11-phase-frontend-boundary-hardening-execution-plan/08-implementation-phases.md)
9. [Risks, Definition Of Done, And Glossary](2026-07-11-phase-frontend-boundary-hardening-execution-plan/09-risks-dod-and-glossary.md)
10. [Global Review And Split Validation](2026-07-11-phase-frontend-boundary-hardening-execution-plan/96-global-review-and-split-validation.md)
11. [Post-Split Requirements Ledger](2026-07-11-phase-frontend-boundary-hardening-execution-plan/97-post-split-requirements-ledger.md)
12. [Original-To-Split Audit](2026-07-11-phase-frontend-boundary-hardening-execution-plan/98-original-to-split-audit.md)
13. [Source Coverage](2026-07-11-phase-frontend-boundary-hardening-execution-plan/99-source-coverage.md)

## Global Order

```text
UPSTREAM Phase 0-6 + global review + closure + final commit
  -> BH-HANDOFF immutable manifest validation
  -> BH-SF0A general downstream threat/verifier/signer/manifest-family decision
  -> BH-SF0B Permit/attestation/protected evidence minimum
  -> BH-SF0C central factory fail-closed
  -> BH-SF1 Platform + Hosted containment feasibility
  -> BH-SF2 Profiles/Preflight/Change Origin integration
  -> BH-SF3 fenced lease/journal/Mutation/Acceptance rollback
  -> BH-SF4 evidence/capacity/telemetry/performance
  -> BH-PILOT first handoff-bound Hosted enforcement integration
  -> BH-RP1 correlation/minimal version
  -> BH-REACT1 `/ui-v2` shell/single-surface technical migration
  -> BH-REACT2 mandatory surface migration
  -> BH-ARCH architecture ratchet/endpoint split
  -> BH-DATA transaction-domain/online migration refactor
  -> BH-RELEASE SemVer/release/legacy retirement closure
```

## Global Completion

- 仓库内 Whole-directory validator 只证明计划文本、machine contracts 和覆盖关系可实施；受保护 BH-HANDOFF、各 phase exit 和代码完成必须分别由其权威 evidence 证明。
- `AGENTS.md` 和 `README.md` 在 BH-SF2、BH-SF3、BH-RP1、BH-REACT1/BH-REACT2、BH-RELEASE 对应行为实际落地时与代码同批同步，禁止提前把未来能力写成当前能力。

- 没有依赖 HMAC 私钥的 PR/CI attestation 验证。
- verifier 由仓库外或独立保护的信任锚提供，PR 不能修改自己的 verifier。
- Codex provider network 与工具子进程 network 被分离和负向验证。
- Platform 和 Hosted Codex 都执行确定性 Preflight；所有受支持 Platform Codex 入口通过 canonical launcher。
- Platform protected-path diff 由 protected Postflight supervisor 计算并由远程 Attestation Authority 签发，绑定最终 manifest/test/evidence hash。
- Postflight signing service 使用独立受保护身份，不接受 caller 声称的 diff/test/completion，不成为 Codex 可调用的 signing oracle。
- Protected completion 使用独立重跑或 trusted Test/Acceptance Attestation，并用 Platform SourceChangeManifest、Hosted SnapshotChangeManifest 和 HostEffectiveManifest 覆盖实际内容语义。
- Permit、Mutation 和 Acceptance 使用独立状态机。
- Mutation lease 覆盖 Acceptance、trusted Postflight 持久化和 rollback 全周期；Acceptance 默认失败回滚并保留隔离 evidence。
- `/ui-v2` 不使用 JS 可读长期 token，不在未关闭 HTTPS/CSRF 前开放公网试运行。
- React bundle 具备 lockfile、SBOM、provenance、版本化部署和 previous-bundle 回退。
- 平台架构、online Data migration、correlation、version、trusted evidence custody/capacity 和 supported-workspace performance 通过分册定义的机械验收。
- Previous bundle 只在 current DB schema 满足 expand-contract 兼容矩阵时允许回退。
- 任何下游实施 evidence 都引用 ActiveRegistry 选定的同一 UpstreamHandoffManifest/StateEvent/epoch；没有上游未完成时的并行任务、重复 surface/action/status/diagnostic/schema，或未授权删除 compatibility shim。

## Recovery Metadata Supplement (2026-09-30)

Added for recovery-document schema completeness. Original source text,
authority notices, paused states, non-goals, and evidence remain unchanged.
These fields are source locators, not a new implementation status or approval.

- Git Head: n/a - the plan explicitly defers its executable baseline to the finalCommit selected by UpstreamHandoffActiveRegistry after BH-HANDOFF; the authoring baseline is non-authoritative
