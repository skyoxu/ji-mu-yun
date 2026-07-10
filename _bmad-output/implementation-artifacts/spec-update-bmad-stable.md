---
title: "升级仓库 BMAD/GDS 到最新稳定版"
type: "chore"
created: "2026-07-10"
status: "done"
baseline_commit: "f585ffcc6d89153092b61e4a15002e2490528068"
context:
  - "{project-root}/AGENTS.md"
  - "{project-root}/README.md"
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 仓库当前 vendored BMAD/GDS 早于现行稳定版，且旧式安装结构会让升级器保留过期的配置解析脚本和工作流；部分 Phase A 代码还依赖旧 GDS 技能路径。继续混用会导致技能目录、帮助目录和运行时路由不一致。

**Approach:** 以干净安装快照为官方基线，将 BMAD Method 升级到 `6.10.0`、GDS 升级到稳定标签 `v0.6.0`，显式迁移本仓配置和兼容入口，并用哈希与引用审计证明自定义技能和现有业务重构未被覆盖。

## Boundaries & Constraints

**Always:** 保留 `generate2d*`、`phasea-daily-cleanup`、`prototype-*`、`workflow-chapter2-*` 至 `workflow-chapter7-*`；保留五个 `bmad-agent-game-*` 兼容别名；保留 `gds-create-gdd` 旧路径，但改为指向新版 `gds-gdd` 的薄兼容层并同步新版 game-type 资产；配置保持中文、expert/advanced、Godot、`ji-mu-yun` 和现有输出目录语义；所有升级证据写入 `logs/`。

**Ask First:** 若必须修改当前业务重构文件、实时 Phase A 状态、认证/运行时受保护路径，或需要采用非稳定上游提交，则停止并请求确认。

**Never:** 不回退用户现有改动；不把旧 `_bmad/config.toml`、旧解析脚本或已废弃完整工作流伪装成新版；不保留指向不存在技能的菜单/帮助项；不删除自定义技能或历史证据。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| 稳定版升级 | 旧式本地 BMAD + dirty worktree | 官方文件来自 `6.10.0`/`v0.6.0`，业务改动保持原样 | 哈希或边界差异失败即停止同步并从外部备份恢复 |
| 安装器遗漏 | GDS `v0.6.0` 源含 `gds-ux`，Codex 安装结果遗漏 | 从同一稳定标签源补入完整 `gds-ux` | 校验源提交和技能引用，不使用 main/next |
| 旧路径依赖 | Phase A 读取 `.agents/skills/gds-create-gdd/game-types*` | 旧路径继续可读，内容来自新版 `gds-gdd/assets/game-types*` | 运行目录与针对性测试，发现漂移则阻止完成 |

</frozen-after-approval>

## Code Map

- `_bmad/**` -- 本地安装清单、配置、共享解析脚本和帮助目录。
- `.agents/skills/**` -- Codex 使用的官方、兼容和仓库自定义技能。
- `.agents/skills/gds-create-gdd/**` -- Phase A 仍依赖的旧 GDD 路径兼容层。
- `PhaseA.Platform/Prototypes/BmadGameTypeDesignCatalog.cs` -- 旧 game-type 路径的生产读取方，仅验证，不修改。
- `logs/bmad-upgrade/2026-07-10/**` -- 升级前后哈希、版本和验证证据。

## Tasks & Acceptance

**Execution:**
- [x] `_bmad/**` -- 从已验证的干净稳定版快照同步安装器管理文件，迁移用户配置、`.gdignore` 与帮助扩展，避免旧结构被误保留。
- [x] `.agents/skills/<official>` -- 精确同步 78 个安装器生成技能，并从 GDS `v0.6.0` 标签源补入安装器遗漏的 `gds-ux`。
- [x] `.agents/skills/{bmad-agent-game-*,gds-create-gdd,generate2d*,phasea-daily-cleanup,prototype-*,workflow-chapter*}` -- 保留或重建兼容/自定义技能；删除无引用的废弃旧工作流。
- [x] `_bmad/_config/bmad-help.csv` 与 `_bmad/scripts/generate_bmad_help.py` -- 保留官方元数据并追加实际存在的兼容/自定义技能，确保目录无幽灵项。
- [x] `logs/bmad-upgrade/2026-07-10/**` -- 记录来源版本、提交、前后哈希、保留项和验证结果。

**Acceptance Criteria:**
- Given 升级完成，when 执行 BMAD status 和清单检查，then Core/BMM 为 `6.10.0`、GDS 为 `v0.6.0` 且来源提交为稳定标签提交。
- Given 技能目录，when 校验 frontmatter、菜单和帮助引用，then 每个被引用技能均存在，`gds-ux` 完整可用，废弃工作流无残留幽灵项。
- Given Phase A 的旧 GDD 路径依赖，when 运行 game-type 目录测试，then 新版类型清单和分片可从兼容路径读取且测试通过。
- Given 升级前 dirty worktree，when 比较升级边界和哈希，then 非 BMAD 业务文件没有因本次升级产生新增变化，自定义技能内容未丢失。

## Design Notes

直接 `--action update` 已在外部演练中证明会保留旧 `config.toml` 和旧 `resolve_*` 脚本，因此不能作为唯一同步机制。最终以固定版本的干净快照覆盖安装器管理面，再迁移明确列出的本仓扩展。GDS `v0.6.0` 标签包含 `gds-ux`，但 BMAD Codex 适配器漏装该目录；补丁必须从标签提交 `966fbc54db686f77fd0d68cae4164dce8cc98113` 复制，而非自行重写。

## Verification

**Commands:**
- `npx -y bmad-method@6.10.0 status` -- 显示 Core/BMM `6.10.0`、GDS `v0.6.0`。
- `py -3 logs/bmad-upgrade/2026-07-10/audit_upgrade.py` -- 配置、技能集合、frontmatter、引用、哈希与帮助目录全部通过。
- `dotnet test PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj --filter FullyQualifiedName~GameTypeTemplateCatalogTests` -- 旧路径兼容与新版 game-type 资产通过。
- `git diff -- .agents/skills` -- 仅包含预期的官方升级、兼容层和自定义保留变化。

## Suggested Review Order

**稳定版本与来源**

- 先确认安装版本、模块来源和固定 GDS 提交。
  [`manifest.yaml:1`](../../_bmad/_config/manifest.yaml#L1)

- 再确认官方安装命令与快照整体哈希。
  [`stable-source-manifest.json:1`](../../logs/bmad-upgrade/2026-07-10/stable-source-manifest.json#L1)

**Windows 运行适配**

- UTF-8 stdout 避免中文 Windows 控制台解析失败。
  [`resolve_config.py:174`](../../_bmad/scripts/resolve_config.py#L174)

- 仓库技能统一使用 Windows 可用的 Python 启动器。
  [`gds-gdd/SKILL.md:24`](../../.agents/skills/gds-gdd/SKILL.md#L24)

- 移除 GDS 文档流程对缺失旧 hook 的依赖。
  [`instructions.md:3`](../../.agents/skills/gds-document-project/instructions.md#L3)

- 每项本地适配均绑定上游与适配后哈希。
  [`local-adaptations.json:1`](../../logs/bmad-upgrade/2026-07-10/local-adaptations.json#L1)

**兼容入口与资源**

- 旧 GDD 调用只路由到新版 canonical 工作流。
  [`gds-create-gdd/SKILL.md:1`](../../.agents/skills/gds-create-gdd/SKILL.md#L1)

- 安装器遗漏的游戏 UX 技能来自同一稳定标签。
  [`gds-ux/SKILL.md:1`](../../.agents/skills/gds-ux/SKILL.md#L1)

- Phase A 旧路径继续读取新版 game-type 清单。
  [`game-types.csv:1`](../../.agents/skills/gds-create-gdd/game-types.csv#L1)

**审计、恢复与验收**

- 审计覆盖来源、哈希、引用、Windows smoke 和边界。
  [`audit_upgrade.py:59`](../../logs/bmad-upgrade/2026-07-10/audit_upgrade.py#L59)

- 双目录替换失败时统一恢复外部备份状态。
  [`apply_upgrade.py:54`](../../logs/bmad-upgrade/2026-07-10/apply_upgrade.py#L54)

- 最终摘要汇总全部通过项和零遗留风险。
  [`validation-summary.json:1`](../../logs/bmad-upgrade/2026-07-10/validation-summary.json#L1)
