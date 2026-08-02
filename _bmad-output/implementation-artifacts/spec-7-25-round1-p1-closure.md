---
title: '7-25 Round 1 P1 closure'
type: 'bugfix'
created: '2026-08-02'
status: 'done'
baseline_commit: 'fd5a8fdeaaadaf579c9e388b6233ec87d560fd83'
review_loop_iteration: 0
context:
  - 'docs/adr/ADR-0044-knowledge-projection-authority-e2-hosted-context-envelope.md'
  - 'docs/standards/phase-service.md'
---

<frozen-after-approval reason="human-owned intent - do not modify unless human renegotiates">

## Intent

**Problem:** 7-25 首轮验收确认两项 P1：Enforce 路由当前只签名紧凑的 11 字段记录，未绑定 ADR-0044 要求的完整 E2 运行合同；knowledge maintenance 的 `--output` 可覆盖 catalog source、resource 或被检查 consumer，同时仍声明零源变更。

**Approach:** 将完整、规范化 signed payload 作为签名、持久化和原子消费的共同真相；identity、workspace generation、artifact、policy、prompt 和权限均来自 metadata authority 或 server registry。Hosted route aggregate 按服务器注册的路由能力条件化：实际消费前置 aggregate 时必须完整绑定，否则使用签名覆盖的显式 `not_applicable`，caller 不能选择。所有 knowledge 输出在首次写入前完成路径边界与碰撞校验。

## Boundaries & Constraints

**Always:** 遵循 ADR-0044 与现有 `hosted-context-manifest.v1`；HMAC 覆盖完整 canonical payload，signature metadata 和 validation state 不进入 HMAC；nonce 单次原子消费；SQLite 迁移向后兼容；变更前后均不得修改 live DB/workspace；保留现有 dirty changes 和历史失败证据；code、tests、comments、CLI messages 使用 English。

**Ask First:** 只有需要改变公开 API、降低 Enforce 路由、触碰 live runtime 数据，或仍无法从现有 server authority 取得真实 binding 时才暂停请求授权。2026-08-02 已获人类授权：schema/ADR 可增加按路由能力条件化的 Hosted contract disposition，但不得削弱其他 E2 bindings。

**Never:** 不用 placeholder、常量假 hash、客户端声明或未验证 JSON 冒充完整 E2 binding；不以切回 observe/legacy 代替修复；不重写历史 review evidence；不新增 VDD 目录；不顺带修复本轮 finding 之外的 Bootstrap/Acceptance 控制面问题。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| 完整 E2 dispatch | Enforce caller 提供当前 server-owned payload 与未消费 nonce | 完整 payload hash/HMAC 验证，DB 精确匹配后单次消费并 dispatch | 任一 binding 漂移均 fail closed |
| 重放或篡改 | 已消费 nonce，或 payload 中任一 identity/policy/path/prompt/contract 字段变化 | 不执行 LLM/Codex dispatch | 返回现有稳定 context-manifest failure |
| 旧数据库 | 表中只有旧列/旧记录 | 初始化只添加兼容列；旧紧凑记录不得通过完整 E2 验证 | fail closed，不删除旧数据 |
| 合法 derived 输出 | output 位于允许的 projection/index/LKG result 目的地且与 source/log 不重叠 | 写 derived result 和新 append-only log | N/A |
| 非法 knowledge 输出 | repo escape、catalog source/resource、consumer/source、catalog/request、log collision | 不写 output、source 或 log，返回稳定失败码 | exit 2，源字节保持不变 |

</frozen-after-approval>

## Code Map

- `PhaseA.Platform/Data/HostedContextManifest*.cs`、`PhaseAMetadataStore.cs`、`SqliteMetadataSchema.cs` -- 完整 payload 的签发、签名、迁移、验证与原子消费。
- `PhaseA.Platform/Llm/HostedContextGate.cs`、`Program.cs` 及 `PhaseA.Platform/{Llm,Runs,Readback,Projects,Skills}/**/*.cs` -- envelope transport、Enforce 配置和全部 caller bindings。
- `PhaseA.Platform.Tests/{Data,Llm,Runs}/**/*Tests.cs` -- E2 trust-boundary 回归。
- `.agents/skills/maintain-knowledge-base/scripts/{maintain_knowledge.py,test_maintain_knowledge.py}` -- derived 输出 guard 与不变性测试。

## Tasks & Acceptance

**Execution:**
- [x] `PhaseA.Platform/Data/**`、`HostedContextGate.cs` -- 先写失败测试，再实现完整 canonical payload、hash/HMAC、兼容 migration、精确匹配和原子 nonce 消费。
- [x] `PhaseA.Platform/{Llm,Runs,Readback,Projects,Skills}/**/*.cs` -- 机械枚举全部 issue caller，并绑定实际 identity、artifact、policy、contracts 与 prompt hashes。
- [x] `PhaseA.Platform.Tests/**` -- 覆盖字段篡改、跨边界、过期/重放、旧记录和 LLM/Codex 消费者。
- [x] `.agents/skills/maintain-knowledge-base/scripts/**` -- 写前限制 derived destinations，拒绝 escape/collision，并证明 source/resource/consumer/catalog/request/log 字节不变。
- [x] `execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/**` -- 只刷新因修复漂移的 inventory/fixture/evidence，不改 frozen intent 或伪造结果。

**Acceptance Criteria:**
- Given 任一 signed payload 字段漂移，when Enforce 验证，then 不消费成功且不 dispatch。
- Given 同一 manifest 被提交两次，when 原子消费，then 恰有一次成功。
- Given 旧 DB/旧紧凑记录，when migration/验证，then 数据保留但旧记录不能声明 E2 有效。
- Given 非法 knowledge output，when CLI 执行，then exit 2、稳定 failure code 且无任何写入；合法 derived output 只生成 result 与 append-only log。

## Spec Change Log

- 2026-08-02: 中间实现为缺失 authority 的字段生成虚假 `hosted-context://` refs 和 succeeded-run binding。经人类明确授权，Hosted route aggregate 改为服务器注册的 `required|not_applicable` 条件合同；保留 Enforce，并禁止 caller 自选或合成 evidence。

## Design Notes

签名输入必须由 typed payload 先产生确定性 canonical UTF-8 bytes，再同时计算 SHA-256 与 HMAC；数据库保存同一 canonical payload（或其可无损表示）及 hash，validator 不接受 envelope 外的未签名布尔值替代 binding 校验。caller inventory 必须机械扫描，避免只修常见路径而遗漏 Enforce consumer。

## Verification

**Commands:**
- `py -3 .agents/skills/maintain-knowledge-base/scripts/test_maintain_knowledge.py` -- expected: PASS。
- `dotnet test PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj --filter "FullyQualifiedName~HostedContextManifest|FullyQualifiedName~LlmRouteEngine|FullyQualifiedName~CodexHostedProcessCommandFactory"` -- expected: targeted PASS。
- `dotnet test PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj` -- expected: full suite PASS。
- `py -3 execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/tools/validate_whole_directory.py` -- expected: PASS。
- `rg -n "new HostedContextManifestIssue" PhaseA.Platform -g "*.cs"` -- expected: every Enforce caller supplies complete typed bindings。

Full-suite validation gap: the unfiltered Platform test command exceeded the 600-second execution limit on 2026-08-02. The targeted 29-test trust-boundary suite passed; the timeout is not recorded as a pass.

## Suggested Review Order

**Signed Dispatch Authority**

- Canonical E2 trust payload
  [`HostedContextSignedPayloadV1.cs:8`](../../PhaseA.Platform/Data/HostedContextSignedPayloadV1.cs#L8)

- Server-owned route disposition
  [`HostedContextRouteContractPolicy.cs:4`](../../PhaseA.Platform/Data/HostedContextRouteContractPolicy.cs#L4)

- Authority-backed payload issuance
  [`HostedContextManifestIssuer.cs:35`](../../PhaseA.Platform/Data/HostedContextManifestIssuer.cs#L35)

- Atomic validated consumption
  [`HostedContextManifestValidator.cs:18`](../../PhaseA.Platform/Data/HostedContextManifestValidator.cs#L18)

**Persistence And Contract**

- Additive legacy-safe migration
  [`SqliteMetadataSchema.cs:56`](../../PhaseA.Platform/Data/SqliteMetadataSchema.cs#L56)

- Conditional aggregate schema
  [`hosted-context-manifest.v1.schema.json:368`](../../execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/schemas/hosted-context-manifest.v1.schema.json#L368)

**Knowledge Output Boundary**

- Derived-only destination guard
  [`maintain_knowledge.py:73`](../../.agents/skills/maintain-knowledge-base/scripts/maintain_knowledge.py#L73)

**Shared LLM Inventory**

- Non-secret runtime identity
  [`_llm_backend.py:32`](../../scripts/sc/_llm_backend.py#L32)

- Shared identity regression
  [`test_llm_backend.py:36`](../../scripts/sc/tests/test_llm_backend.py#L36)
