[![Windows Export Slim](https://github.com/skyoxu/ji-mu-yun/actions/workflows/windows-export-slim.yml/badge.svg)](https://github.com/skyoxu/ji-mu-yun/actions/workflows/windows-export-slim.yml) [![Windows Release](https://github.com/skyoxu/ji-mu-yun/actions/workflows/windows-release.yml/badge.svg)](https://github.com/skyoxu/ji-mu-yun/actions/workflows/windows-release.yml) [![Windows Quality Gate](https://github.com/skyoxu/ji-mu-yun/actions/workflows/windows-quality-gate.yml/badge.svg)](https://github.com/skyoxu/ji-mu-yun/actions/workflows/windows-quality-gate.yml)

# Ji Mu Yun（积木云）Phase A/B Cloud Prototype Platform

本仓已经从单纯的 Godot Windows-only C# 游戏模板，演进为一个 Windows 单机云端 Godot 原型生成与托管平台。

它的执行内核仍然是 Godot 4.5 + C#/.NET 8 游戏模板、仓库原生脚本、质量门禁、恢复 sidecar 和文档体系；云端层通过 `PhaseA.Platform` 把这些能力包装成浏览器可用的项目创建、原型生成、迭代、修复、GDD、资源、打包、聊天、审计和运行证据查看平台。

## 当前阶段结论

- Phase A 已成型：已具备单节点托管 runner、ASP.NET Core Web/API、SQLite 元数据、workspace 管理、项目创建、原型通道、浏览器 UI、Caddy 反代、运行证据和恢复链路。
- Phase B 账号隔离 / 运营审计切片已完成（当前 prototype-hardening scope）：已具备账号级访问、管理员创建用户、禁用/启用用户、轮换 token、应用层项目隔离、LLM 绑定、LLM 用量统计、管理员审计、CSV 导出和 Phase B smoke 验证。
- 仍未视为路线图中的完整 Phase B / 生产多租户隔离：独立 Windows runner 账户、项目级 NTFS ACL、完整身份系统、用户删除、浏览器 E2E 和更强 runner 隔离仍属于后续 Phase C 或预生产安全加固范围。

最新阶段状态来源：当前完成状态以 `docs/workflows/phase-b-account-isolation.md` 的 `Latest Completion Pass` 为准；`docs/workflows/cloud-platform-evolution-plan.cn.md` 是路线图，不代表所有目标都已落地。

- `docs/workflows/phase-b-account-isolation.md`
- `docs/workflows/cloud-platform-evolution-plan.cn.md`
- `docs/workflows/phase-a-security-hardening-plan.cn.md`
- `docs/architecture/overlays/PHASE-A-CLOUD-RUNNER/08/08-Phase-A-Cloud-Runner-Architecture.md`
- `execution-plans/2026-05-11-phase-a-prototype-lane-implementation-backlog.md`

## Highest Encoding Rule

- All Chinese text reads and writes must use Python with explicit UTF-8, for example `Path(path).read_text(encoding="utf-8")` and `Path(path).write_text(text, encoding="utf-8", newline="\n")`.
- Do not use PowerShell, `Get-Content`, `Set-Content`, `Out-File`, `Add-Content`, `type`, `echo`, `copy con`, or other Windows-native text tools to read or write Chinese text.
- If a command script must contain Chinese literals, write it as a Python file or use ASCII-only Python source with Unicode escapes, then write the target file as UTF-8.
- This rule applies to `AGENTS.md`, `README.md`, `workflow.md`, `docs/**/*.md`, `.agents/skills/**/SKILL.md`, prototype records, and project-health documentation.
- Code, tests, logs, and machine output remain English unless the file is explicitly user-facing documentation.

## 系统分层

### 1. Godot 模板内核

- `Game.Core/`：纯 C# 领域逻辑和契约相邻代码。
- `Game.Godot/`：Godot 运行时项目、场景、Autoload、适配层和原型资源。
- `Game.Core.Tests/`：xUnit 测试。
- `Tests.Godot/`：GdUnit4、场景、适配层、安全和集成测试。
- `docs/architecture/**`、`docs/adr/**`、`docs/testing-framework.md`：架构、ADR、测试和交付规则。

### 2. Phase A 云端平台层

- `PhaseA.Platform/`：ASP.NET Core 8 Web/API 服务。
- `PhaseA.Platform.Tests/`：平台单元和集成测试。
- `runtime/phase-a/`：稳定启动、恢复、watchdog 和 Caddy 配置。
- `logs/phase-a-innernet/`：本地运行时数据库、workspace、watchdog 和 runtime 证据；该目录是运行时生成证据，不是源码或稳定配置目录。
- `scripts/python/phase_a_*.py`：Phase A ops、runtime、public、restore、prototype E2E 和 token drill 脚本。

Phase A 的原则是：平台负责 hosting、workspace、runner、artifact readback、browser/API 和恢复；仓库脚本继续拥有 workflow decision authority。

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

本地 Phase A 服务稳定绑定：

- `http://127.0.0.1:18080`

公网反代入口：

- `http://47.86.160.138:8080`

当前 `runtime/phase-a/Caddyfile` 监听 `http://:8080`；`runtime/phase-a/start-phasea.ps1` 中的 `PUBLIC_BASE_URL=https://47.86.160.138:8080` 保留为平台公共基址配置口径，与当前 Caddy 直连 HTTP 入口并存，后续若启用证书或上游 HTTPS 终止再统一。

稳定运行配置：

- `runtime/phase-a/start-phasea.ps1`
- `runtime/phase-a/ensure-phasea.ps1`
- `runtime/phase-a/watch-phasea.ps1`
- `runtime/phase-a/Caddyfile`

重要规则：

- live server 不要用普通 `dotnet run` 写入仓库默认 `obj/bin`。
- live server 使用 `runtime/phase-a/start-phasea.ps1`。
- 启动脚本把 build output 放到仓库外的稳定目录。
- `PHASEA_ADMIN_TOKEN_HASH` 必须来自 host secret store 或服务环境，不得写入 git 跟踪文件。

常用检查：

```powershell
py -3 scripts/python/phase_a_ops_check.py
py -3 scripts/python/phase_b_account_smoke.py --base-url http://127.0.0.1:18080
py -3 scripts/python/phase_b_account_smoke.py --base-url http://47.86.160.138:8080
```

`phase_a_runtime_smoke.py` 是本地临时 smoke，会用临时端口和临时 workspace 启动测试服务；它不是 live server 启动或恢复入口。

带管理员 token 的 Phase B 授权 smoke 应通过环境变量或命令行传入 token；不要把真实 token 写入日志、README 或 docs。

## 托管项目路由恢复规则

Phase A 前端触发的 hosted game-project route 必须先读项目级恢复源，而不是把 `AGENTS.md` 当作普通项目记忆。

可修改 hosted game-project 文件的 route，至少需要按权威顺序消费：

1. 已解析的 game-type route profile 和选中的 route skill prompt block。
2. `meta/project-execution-guide.md`。
3. `routes/prototype-contract/latest.json`。
4. 当前 route 的 latest state，例如 `meta/routes/prototype/latest.json`、`meta/routes/iteration-plan/latest.json`、`meta/routes/execute-next-goal/latest.json`。
5. 当前 goal、step、repair step 或 session state。
6. repair route 还必须读取 repair ledger、失败 acceptance 或 Godot diagnostic evidence。
7. 最新 live platform acceptance blocker 优先于旧 assistant summary、route state 和 repair ledger memory。

硬规则：

- 缺少必需恢复源时 fail closed，不假装恢复成功。
- route state 和 repair ledger 是连续性记忆，不是当前验收权威。
- 不允许只凭 assistant 文本标记 step complete。
- 新 route 在接入前必须声明 recovery inputs、authority order、missing-source behavior 和 browser-safe output rules。

## AI/LLM 调用协议

新 Phase A route、service、script 和 workflow helper 必须使用共享入口：

- C# structured/read-only LLM：`PhaseA.Platform/Llm/LlmRouteEngine.cs` via `ILlmRouteEngine`。
- C# executable Codex workflow：`PhaseA.Platform/Runs/CodexHostedProcessCommandFactory.cs`。
- Python LLM/Codex script：`scripts/sc/_llm_backend.py::run_llm_exec`。

协议规则：

- 不要在新 route 或 script 中手写 raw `codex exec` subprocess。
- prompt 传输使用 stdin：`codex exec ... -`，不要把大 prompt 拼到命令行参数。
- 分析或 JSON-only 决策保持 read-only。
- 改文件的流程必须走明确 executable route、`workspace-write` 和现有 acceptance/smoke validation。
- 如果共享入口缺少 model、reasoning、sandbox、output、billing、credential 或 retry 选项，先扩展共享入口及其测试。

必需回归覆盖：

- `PhaseA.Platform.Tests/Runs/CodexHostedProcessCommandFactoryTests.cs`
- `PhaseA.Platform.Tests/Llm/LlmRouteEngineTests.cs`
- `scripts/sc/tests/test_llm_backend.py`
- 调用方自己的 route-specific tests

## Godot 模板能力

模板内核仍然支持从 0 到导出 Windows 桌面游戏。下面示例使用与当前 Phase A runtime 一致的 Godot 4.5.1 .NET/mono console 路径：

1. 安装 Godot .NET mono，并设置 `GODOT_BIN`。
2. 运行最小测试和 headless smoke。
3. 在 Godot Editor 安装 Windows Desktop Export Templates。
4. 运行 Windows export 和 exe smoke。

示例：

```powershell
$env:GODOT_BIN='C:\Godot\4.5.1-mono\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64_console.exe'
./scripts/ci/smoke_headless.ps1 -GodotBin "$env:GODOT_BIN"
./scripts/ci/export_windows.ps1 -GodotBin "$env:GODOT_BIN" -Output build\Game.exe
./scripts/ci/smoke_exe.ps1 -ExePath build\Game.exe
```

模板内容包括：

- Autoload 适配层：EventBus、DataStore、Logger、Audio、Time、Input、SqlDb。
- 场景分层：ScreenRoot、Overlays、ScreenNavigator、HUD、SettingsPanel。
- 安全基线：`res://` / `user://` 边界、HTTP 白名单、SQLite 路径校验、审计 JSONL。
- 可观测性：本地 JSONL、性能指标、run/artifact evidence。
- 测试体系：xUnit、GdUnit4、headless smoke、quality gates。
- 导出与发布：Windows-only export、smoke、tag release workflow。

## Delivery Profiles

- `DELIVERY_PROFILE=playable-ea`：最快可玩性校验档位，安全默认派生到 `host-safe`。
- `DELIVERY_PROFILE=fast-ship`：模板默认档位，保留基本主机安全、核心测试和必要发版约束。
- `DELIVERY_PROFILE=standard`：收口档位，ADR、验收、语义门禁更严格，安全默认派生到 `strict`。

生效优先级：CLI `--delivery-profile` > 环境变量 `DELIVERY_PROFILE` > 仓库默认 `fast-ship`。

`prototype lane` 是探索通道，不是新的 `DELIVERY_PROFILE`。它决定工作是否进入正式任务流，不替代正式交付门禁。

## 稳定公共入口

本节列出的是仓库本地 / 自动化脚本入口；它们不表示 Phase A 浏览器 UI 已开放所有对应能力。尤其 Chapter 3-7 正式交付路由不属于当前 Phase A 浏览器范围。

### 仓库 bootstrap / 恢复

```powershell
py -3 scripts/python/dev_cli.py run-local-hard-checks
py -3 scripts/python/dev_cli.py project-health-scan
py -3 scripts/python/dev_cli.py serve-project-health
py -3 scripts/python/dev_cli.py resume-task --task-id <id>
py -3 scripts/python/dev_cli.py inspect-run --kind <kind> [--task-id <id>]
py -3 scripts/python/dev_cli.py chapter6-route --task-id <id> --recommendation-only
```

### 原型通道

```powershell
py -3 scripts/python/dev_cli.py run-prototype-workflow --prototype-file docs/prototypes/<your-file>.md
py -3 scripts/python/dev_cli.py run-prototype-tdd --slug <slug> --stage <red|green|refactor> ...
```

### 任务交付主环

```powershell
py -3 scripts/python/dev_cli.py run-single-task-chapter6 --task-id <id> --godot-bin "$env:GODOT_BIN" --delivery-profile <profile>
py -3 scripts/sc/run_review_pipeline.py --task-id <id> --godot-bin "$env:GODOT_BIN" --delivery-profile <profile>
```

### 架构 / 任务 / 契约一致性

```powershell
py -3 scripts/python/task_links_validate.py
py -3 scripts/python/check_tasks_all_refs.py
py -3 scripts/python/validate_task_master_triplet.py
py -3 scripts/python/validate_contracts.py
py -3 scripts/python/check_domain_contracts.py
py -3 scripts/python/sync_task_overlay_refs.py --prd-id <PRD-ID> --write
```

完整入口索引：

- `docs/workflows/stable-public-entrypoints.md`
- `docs/workflows/script-entrypoints-index.md`

## Recovery First

任务在 context reset、跨会话或隔天恢复时，先走恢复链，不要直接重开完整 Chapter 6。

1. 读 `docs/agents/01-session-recovery.md`。
2. 执行 `py -3 scripts/python/dev_cli.py resume-task --task-id <id>`。
3. 如果 summary 仍然不够，再执行 `py -3 scripts/python/dev_cli.py inspect-run --kind pipeline --task-id <id>`。
4. 在重开完整 `6.7` 前，先执行 `py -3 scripts/python/dev_cli.py chapter6-route --task-id <id> --recommendation-only`。

如果恢复链显示 `planned-only`、`artifact_integrity`、`rerun_guard`、`llm_retry_stop_loss`、`sc_test_retry_stop_loss` 或 `needs-fix-fast`，先按恢复建议做窄修复或回退。

## 关键文档

### 云端平台

- `docs/workflows/phase-b-account-isolation.md`
- `docs/workflows/cloud-platform-evolution-plan.cn.md`
- `docs/workflows/cloud-user-telemetry-and-feedback-plan.cn.md`
- `docs/workflows/phase-a-security-hardening-plan.cn.md`
- `docs/workflows/phase-a-caddy-deployment.md`
- `docs/architecture/overlays/PHASE-A-CLOUD-RUNNER/08/_index.md`

### 仓库和 Agent 导航

- `AGENTS.md`
- `docs/agents/00-index.md`
- `docs/agents/01-session-recovery.md`
- `docs/agents/13-rag-sources-and-session-ssot.md`
- `docs/agents/16-directory-responsibilities.md`
- `docs/PROJECT_DOCUMENTATION_INDEX.md`

### Godot 模板和交付

- `docs/testing-framework.md`
- `DELIVERY_PROFILE.md`
- `docs/architecture/ADR_INDEX_GODOT.md`
- `docs/architecture/base/00-README.md`
- `docs/workflows/prototype-lane.md`
- `docs/workflows/prototype-lane-playbook.md`
- `docs/workflows/prototype-tdd.md`
- `docs/TEMPLATE_GODOT_GETTING_STARTED.md`

## Feature Flags

- Autoload：`/root/FeatureFlags`
- 文件：`Game.Godot/Scripts/Config/FeatureFlags.cs`
- 单项环境变量：`setx FEATURE_demo_screens 1`
- 多项环境变量：`setx GAME_FEATURES "demo_screens,perf_overlay"`
- 文件配置：`user://config/features.json`

代码示例：

```csharp
if (FeatureFlags.IsEnabled("demo_screens"))
{
    // ...
}
```

## Godot 模板发版和应用元数据

本节是 Godot 游戏模板的导出和发版入口，不是 Phase A 平台服务的 live 部署流程。

创建版本标签触发发布：

```powershell
git status
git push
git tag v0.1.1 -m "v0.1.1 release"
git push origin v0.1.1
```

Windows Release workflow 会导出并把 `build/Game.exe` 附加到 GitHub Release。

应用元数据在 `export_presets.cfg` 的 `[preset.0.options]` 段维护：

- `application/product_name`
- `application/company_name`
- `application/file_description`
- `application/*_version`
- `application/icon`

## Game Project Metadata

- Game Name: TBD
- Game Type: TBD
- Game Type Source: TBD
- Game Type Guide: TBD
