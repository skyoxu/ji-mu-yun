# Ji Mu Yun（积木云）Phase A/B Cloud Prototype Platform

本仓已经从单纯的 Godot Windows-only C# 游戏模板，演进为一个 Windows 单机云端 Godot 原型生成与托管平台。

它的执行内核仍然是 Godot 4.5 + C#/.NET 8 游戏模板、仓库原生脚本、质量门禁、恢复 sidecar 和文档体系；云端层通过 `PhaseA.Platform` 把这些能力包装成浏览器可用的项目创建、原型生成、迭代、修复、GDD、资源、打包、聊天、审计和运行证据查看平台。

## 一眼看懂

| 问题 | 答案 |
| --- | --- |
| 产品解决什么问题 | 把 Godot 原型创建、迭代、修复、打包、审计和运行证据查看，从本地脚本流程包装成浏览器/API 可用的平台。 |
| 用户是谁 | 平台管理员、原型创建者、AI/自动化 agent、以及维护 Phase A/B 平台和托管执行内核的开发者。 |
| 核心模块 | Phase A 云端平台层、Phase B 账号和运营层、托管 Godot 原型执行内核、运行时恢复和证据体系。 |
| 当前阶段 | Phase A 已成型；Phase B 账号隔离 / 运营审计切片已完成；完整生产多租户隔离仍在后续 Phase C 或预生产加固范围。 |
| 主要技术栈 | Godot 4.5 .NET/mono、C#/.NET 8、ASP.NET Core 8、SQLite、Caddy、Python、PowerShell、xUnit、GdUnit4。 |
| 本地入口 | `http://127.0.0.1:18080` |
| 公网反代入口 | `http://47.86.160.138:8080` |
| 快速启动 / 恢复 | `powershell -ExecutionPolicy Bypass -File runtime/phase-a/ensure-phasea.ps1` |
| 继续了解 | 先读本 README，再按 `AGENTS.md`、`docs/architecture/phase-service/_index.md`、`docs/PROJECT_DOCUMENTATION_INDEX.md` 进入细节。 |

## 文档与运行上下文分层

本仓采用三个责任面，但知识运行时仍按 ADR-0044 的 Domain、Visibility、Lifecycle Instance 和 Enforcement Level 四个维度进行选择与隔离。

| 责任面 | 入口 | 服务对象 |
| --- | --- | --- |
| 根仓治理 | `AGENTS.md`、本 README | 平台、工具链、Phase 功能和共享游戏工作流的长期维护 |
| Phase 应用与宿主运维 | `PhaseA.Platform/AGENTS.md`、`PhaseA.Platform/README.md`、`runtime/phase-a/AGENTS.md`、`runtime/phase-a/README.md` | ASP.NET 应用开发，以及启动、Caddy、watchdog 和恢复 |
| Hosted 用户工作流 | `PhaseA.Platform/Workspaces/HostedProjectTemplate/**` 生成的项目入口，加项目 `meta/**`、`routes/**` 和运行证据 | 前台项目创建、GDD、原型、迭代和修复 |

根文档不是 Hosted 游戏项目说明。新 workspace 使用专用项目模板；项目级入口只负责导航，当前 route 状态、验收、知识选择和签名运行上下文仍以结构化记录为准。


## 当前阶段结论

- Phase A 已成型：已具备单节点托管 runner、ASP.NET Core Web/API、SQLite 元数据、workspace 管理、项目创建、原型通道、浏览器 UI、Caddy 反代、运行证据和恢复链路。
- Phase B 账号隔离 / 运营审计切片已完成（当前 prototype-hardening scope）：已具备账号级访问、管理员创建用户、禁用/启用用户、轮换 token、应用层项目隔离、LLM 绑定、LLM 用量统计、管理员审计、CSV 导出和 Phase B smoke 验证。
- 仍未视为路线图中的完整 Phase B / 生产多租户隔离：独立 Windows runner 账户、项目级 NTFS ACL、完整身份系统、用户删除、浏览器 E2E 和更强 runner 隔离仍属于后续 Phase C 或预生产安全加固范围。

### 前台边界加固计划状态

[`2026-07-11 Phase 前台边界加固计划`](execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan.md) 当前为 `paused`，严格等待 [`2026-07-07 GDD-to-module 重构`](execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/00-index.md) 全部完成并通过受保护的 BH-HANDOFF 后再实施。当前仓库尚未启用 `/ui-v2`、Permit/Preflight、Change Origin Gate、新 browser session path、legacy freeze 或正式 Phase 平台 SemVer；本 README 中现有启动命令、浏览器入口和运行时合同仍是当前事实。

该计划目录的本地校验器只检查 Markdown、schema、finding 和覆盖关系是否足以开始实施，不代表代码已经完成，也不能替代仓库外受保护的 BH-HANDOFF verifier。后续文档必须与代码按阶段同批更新：BH-SF2 同步 AI/Codex/Preflight 协议，BH-SF3 同步 mutation/acceptance 恢复入口，BH-RP1 同步版本投影，BH-REACT1/BH-REACT2 同步 `/ui-v2`、session 与 legacy route 状态，BH-RELEASE 同步 SemVer、发布和最终当前阶段结论。

最新阶段状态来源：当前完成状态以 `docs/workflows/phase-b-account-isolation.md` 的 `Latest Completion Pass` 为准；`docs/workflows/cloud-platform-evolution-plan.cn.md` 是路线图，不代表所有目标都已落地。
`docs/workflows/phase-b-agf-godogen-absorption.md` 记录 Phase B 对 AGF/GodoGen 能力吸收的阶段范围和后续边界。

- GDD-to-module implementation phases: `docs/workflows/phase-a-gdd-to-module-implementation-phases.md`
- GDD-to-module risks, DoD, and open questions: `docs/workflows/phase-a-gdd-to-module-risk-dod-open-questions.md`
- GDD-to-module recommended first slice: `docs/workflows/phase-a-gdd-to-module-first-slice.md`
- GDD-to-module global review standard: `docs/workflows/phase-a-gdd-to-module-global-review-standard.md`
- GDD-to-module split-added requirements: `docs/workflows/phase-a-gdd-to-module-split-added-requirements.md`
- GDD-to-module original split audit: `docs/workflows/phase-a-gdd-to-module-original-split-audit.md`
- GDD-to-module source coverage map: `docs/workflows/phase-a-gdd-to-module-source-coverage-map.md`

- `docs/workflows/phase-b-account-isolation.md`
- `docs/workflows/phase-b-agf-godogen-absorption.md`
- `docs/workflows/cloud-platform-evolution-plan.cn.md`
- `docs/workflows/phase-a-security-hardening-plan.cn.md`
- `docs/architecture/overlays/PHASE-A-CLOUD-RUNNER/08/08-Phase-A-Cloud-Runner-Architecture.md`
- `execution-plans/2026-05-11-phase-a-prototype-lane-implementation-backlog.md`

## 系统分层

### 1. 托管原型执行内核

- `Game.Core/`：纯 C# 领域逻辑和契约相邻代码。
- `Game.Godot/`：Godot 运行时项目、场景、Autoload、适配层和原型资源。
- `Game.Core.Tests/`：xUnit 测试。
- `Tests.Godot/`：GdUnit4、场景、适配层、安全和集成测试。
- `docs/architecture/**`、`docs/adr/**`、`docs/testing-framework.md`：架构、ADR、测试和交付规则。

### 2. Phase A 云端平台层

- `PhaseA.Platform/`：ASP.NET Core 8 Web/API 服务；应用结构和代码边界见 `PhaseA.Platform/README.md` 与 `PhaseA.Platform/AGENTS.md`。
- `PhaseA.Platform.Tests/`：平台单元和集成测试。
- `runtime/phase-a/`：稳定启动、恢复、watchdog 和 Caddy 配置；宿主运行说明见该目录的 `README.md` 与 `AGENTS.md`。
- `logs/phase-a-innernet/`：本地运行时数据库、workspace、watchdog 和 runtime 证据；该目录是运行时生成证据，不是源码或稳定配置目录。
- `scripts/python/phase_a_*.py`：Phase A ops、runtime、public、restore、prototype E2E 和 token drill 脚本。
- `PhaseA.Platform/Workspaces/HostedProjectTemplate/`：新项目 workspace 的入口模板；模板复制后属于项目实例，不继承根仓指令权威。
- GDD 创建流程先收集用户策划表单，再生成并让用户确认场景路由草案，最后把两份输入一起交给 GDD 路由生成大纲。

Phase A 的原则是：平台负责 hosting、workspace、runner、artifact readback、browser/API 和恢复；仓库脚本继续拥有 workflow decision authority。

## Phase 服务与仓库执行内核边界

- `workflow.md` 描述仓库本地的正式交付流程，不是 Phase 浏览器/API 入口。
- `workflow.example.md` 面向从原模板复制出的游戏业务仓，不适用于根平台仓。
- Phase 路由只把其中选定的脚本、验证器、profile、Godot 资产和 route contract 作为内部执行依赖。
- Taskmaster triplet、正式 Chapter 3-7 编排、本地 Chapter 6 review recovery、模板 feature flag 和游戏模板发布不是 Phase 默认产品路径。

### 3. Phase B 账号和运营层

Phase B B1/B2 把单管理员原型平台推进为账号作用域平台：

- Bearer token 认证支持 host admin token 和数据库用户 token。
- 用户 token 只返回一次，数据库中只保存 hash。
- 管理员可创建用户、禁用/启用用户、轮换用户 access token。
- 项目、run、artifact、package、asset、chat、workflow readback 按当前账号收敛。
- 用户可配置自己的 LLM gateway binding，并查看账号级 LLM usage。
- 管理员可查看跨账号 LLM usage、LLM run audit、账号操作审计，并导出 CSV。
- Phase B smoke 脚本验证未授权拒绝、管理员授权、用户边界和审计输出不泄露 token material。

Phase B 当前延期项：

- 用户删除。
- 完整 LLM audit export 的更细过滤和分页增强。
- 用户名/密码登录、密码重置、OAuth、OIDC、自助注册。
- 管理面板自动化浏览器 E2E。
- OS 级 Windows runner 账户和 NTFS ACL 隔离。

## 运行入口

根 README 只保留稳定入口。地址、变量、Caddy、watchdog、构建目录和完整恢复合同统一维护在 `runtime/phase-a/README.md`；受保护的修改规则见同目录 `AGENTS.md`。

优先使用一键恢复脚本。它先检查本地 `http://127.0.0.1:18080/healthz`，必要时启动服务，并把恢复证据写入 `logs/phase-a-innernet/runtime/`。

```powershell
powershell -ExecutionPolicy Bypass -File runtime/phase-a/ensure-phasea.ps1
```

长期守护使用 watchdog：

```powershell
powershell -ExecutionPolicy Bypass -File runtime/phase-a/watch-phasea.ps1
```

常用检查：

```powershell
py -3 scripts/python/phase_a_ops_check.py
py -3 scripts/python/phase_b_account_smoke.py --base-url http://127.0.0.1:18080
```

live server 不使用普通 `dotnet run`。真实 token、hash 和签名 secret 不得写入 README、脚本、日志或 Git 跟踪配置。

## 托管项目路由恢复规则

完整权威顺序位于 `AGENTS.md`、`docs/architecture/phase-service/prototype-routes-and-recovery.md` 和 Hosted 项目 `AGENTS.md`。根 README 只保留三条原则：

- 项目 route 读取项目级 profile、contract、latest state、goal/session、repair/diagnostic 和最新 live blocker，不从根文档推断项目状态。
- 缺少必需恢复源时 fail closed；旧 route memory 和 assistant 文本不是当前验收权威。
- 新 route 必须声明 recovery inputs、authority order、missing-source behavior 和 browser-safe output。

## AI/LLM 调用协议

新 Phase route 必须使用仓库共享 LLM/Codex 入口，prompt 使用 UTF-8 stdin；文件修改必须经过明确 executable route、`workspace-write` 和验收。完整协议、组件和回归测试路由见 `AGENTS.md`、`PhaseA.Platform/AGENTS.md` 与 `docs/architecture/phase-service/llm-codex-execution.md`。

知识库 Locator 当前只接入 VDD、Quick Dev 和 Bootstrap Review，不等于 Phase 前台 route 已接入。未来 Phase adapter 必须复用同一 Locator core，由服务端持有 Domain、path、snapshot、budget 和 gate 权限，重读并复验 accepted source hash，再把冻结上下文绑定到 run manifest。


## 关键文档

### 云端平台

- Phase application guide: `PhaseA.Platform/README.md`
- Phase application agent rules: `PhaseA.Platform/AGENTS.md`
- Host runtime guide: `runtime/phase-a/README.md`
- Host runtime agent rules: `runtime/phase-a/AGENTS.md`
- Phase service architecture rationale: `docs/architecture/phase-service/_index.md`
- Phase service ADR index: `docs/architecture/ADR_INDEX_PHASE.md`
- Standards index: `docs/standards/_index.md`
- Phase service standards: `docs/standards/phase-service.md`
- Godot engine semantics standard: `docs/standards/godot-engine-semantics.md`
- Godot UI capability contract: `docs/standards/godot-ui-capability-contract.md`
- Godot UI style contract: `docs/standards/godot-ui-style-contract.md`
- Godot diagnostics and quality gates: `docs/standards/godot-diagnostics-quality-gates.md`
- Godot official examples index: `docs/reference/godot-official-examples-index.md`
- `docs/workflows/phase-b-account-isolation.md`
- `docs/workflows/phase-b-agf-godogen-absorption.md`
- `docs/workflows/cloud-platform-evolution-plan.cn.md`
- `docs/workflows/cloud-user-telemetry-and-feedback-plan.cn.md`
- `docs/workflows/phase-a-security-hardening-plan.cn.md`
- `docs/workflows/phase-a-caddy-deployment.md`
- `docs/architecture/overlays/PHASE-A-CLOUD-RUNNER/08/_index.md`

### 仓库和 Agent 导航

- `AGENTS.md`
- `docs/PROJECT_DOCUMENTATION_INDEX.md`


## 贡献者编码规则

### Highest Encoding Rule

- All Chinese text reads and writes must use Python with explicit UTF-8, for example `Path(path).read_text(encoding="utf-8")` and `Path(path).write_text(text, encoding="utf-8", newline="\n")`.
- Do not use PowerShell, `Get-Content`, `Set-Content`, `Out-File`, `Add-Content`, `type`, `echo`, `copy con`, or other Windows-native text tools to read or write Chinese text.
- If a command script must contain Chinese literals, write it as a Python file or use ASCII-only Python source with Unicode escapes, then write the target file as UTF-8.
- This rule applies to `AGENTS.md`, `README.md`, `workflow.md`, `docs/**/*.md`, `.agents/skills/**/SKILL.md`, prototype records, and project-health documentation.
- Code, tests, logs, and machine output remain English unless the file is explicitly user-facing documentation.
