# PRD 补充：来源核查与后续选择

## 1. 输入与运行身份

源文件 sources/bmad-vdd-knowledge-query-requirements.md 保留资料库完整原文（22056 bytes、236 行、v1.0），SHA-256 为 ce45693489d02227442c04c9b4e7220121a897d81dab03abc7867e6ceff11950。资料库修改时间 2026-10-22T09:29:32.202347Z。下载代理返回 403，随后通过 Library full read 读取全部 236 行，恢复末尾 LF 后字节 hash 与交接值完全一致；未对输入内容修订。来源身份见 sources/metadata.json。

仓库基线 a1e783c569cb5a78ea8728c83518fd13c73a99e8 经 git fetch origin main 重新核实。新工作树 /workspace/ji-mu-yun-knowledge-prd 与 feature/bmad-vdd-knowledge-query 分支从此基线创建。旧 /workspace/ji-mu-yun 的 work 分支和未提交 skill-input-context.v1.json 修改保持原位。

原始需求事实基线 bf78bb43 仅用于比较，不能把其旧原生路径视为新克隆仍然存在的入口。

## 2. 实际读取来源及结论

本轮是直接源码核查，消费者为本次 PRD 编写者，未执行 Locator、未创建 Locator 成功记录。knowledge/policies/consumer-policies.v2.json 只有 vdd、quick-dev、bootstrap、refactor-acceptance；没有获准的 BMAD 身份。无权借用这些身份。这里的文件 hash 仅证明本次读集，不是整仓冻结或新增治理门禁。

| 来源 | 核查结论与用途 |
| --- | --- |
| AGENTS.md；knowledge/toolchain-workflow-index.md | 只读工具链相关路由；不激活 workflow 全文或下游阶段。源码与 Accepted ADR 为权威 |
| docs/workflows/bmad-native-wrappers.md；scripts/toolchain/bmad_native/install.py | PR #20 后自有外壳与原生文件分离；安装器仅覆盖 SPEC/Architecture。官方文件不跟踪，原生补丁退役 |
| .agents/skills/jimuyun-spec/SKILL.md | prepare/native/publish 各有 owner；typed roles、provenance、selection 不可被原生字符串数组抹去。只读合同，未调用 |
| .agents/skills/vdd-execution-plan/SKILL.md 的治理与入口段 | development/auto 默认关闭；显式模式优先；查询不能自动产生冻结或授权。本轮未进入 create/repair |
| .agents/skills/vdd-execution-plan/references/knowledge-consumption.md | 既有强制治理下查询、快照、hash、required module 与 source_refresh 的约束存在，不是从零建设 |
| knowledge/policies/consumer-policies.v2.json | 现有身份、候选预算和路径边界不等于全仓索引覆盖；BMAD 接入是未来增量 |
| scripts/python/knowledge_locator.py:130–224 | CLI 同时校验来源、freshness、policy、projection、publication；某些 blocked 仍 return 0。不能以退出码单独判定成功 |
| docs/adr/ADR-0048-repository-knowledge-locator-workflow-consumption.md | 查询是定位，读取与 hash 验证不可由摘要替代。其 fail-closed/冻结条款与开发态轻量方案的适用范围需要后续明确增量 |
| docs/adr/ADR-0062-repository-skill-authoring-contract.md | Package A 既有标准已采纳；Package B 和其余 owner 未被自动启动 |

上述为当前 main 字节的静态核查，不把文档宣称扩展为运行验证。政策中的 quick-dev 身份不等于已经退役的 stock bmad-quick-dev 原生入口；quick-dev-tdd-adapter 与其既有交接仍需保护。

## 3. 官方技能核查

从官方 https://github.com/bmad-code-org/BMAD-METHOD 的 v6.12.4 取得提交 bab9082c3e884e0d72c759bcd1a6d90bcc01be84。在新工作树安装原生 bmad-prd、其必需 bmad-review，以及 memlog.py、resolve_config.py、resolve_customization.py、config_utils.py；不覆盖既有技能、配置或共享 runtime。此次没有使用两外壳的小型安装器冒充 PRD 安装。

真实执行路径为 .agents/skills/bmad-prd/SKILL.md → references/headless.md（intent=create）→ assets/headless-schemas.md、prd-template.md → Finalize input reconciliation → references/validate.md 的 rubric walker 与 prd-validation-checklist.md → bmad-review structure、prose。读入官方引用并由当前代理按原生方法执行；没有声称存在独立“生成 PRD”CLI。

本地 _bmad/config.toml 指定项目和规划目录，原生 resolver 实际运行；workflow hooks、persistent_facts、external_sources、external_handoffs 和 on_complete 均为空。官方 customize.toml 未修改。UV_CACHE_DIR 指向 /tmp 避免默认只读缓存；这不更改网络、权限、凭据或云端模板。文件完整性记录位于 logs/bmad-prd/2026-10-22-knowledge-query/。

技能/研究子代理检查证实：普通数组追加，不天然去重；带 code/id 的表数组采用身份合并。external_sources 是按需咨询注册表，不是默认查询已接线。本轮只记录这个事实，不把未来功能提前装入 activation hook。

## 4. 后续阶段必须处理的技术选择

以下保留原始需求的深度，未形成 Architecture 或 SPEC 产物：

- 共享 BMAD 消费者或分阶段身份、最小策略范围、注册与发布生产来源。
- 团队覆盖、hook 与外置适配器职责；交互/headless 一致性；普通数组追加时避免重复运行。
- 从通用 blocked 到可用性/完整性诊断的最小适配，及公共结果兼容方式。
- 查询摘要复用现有产物或 memlog 的位置，来源身份与结论的表达；不新增全局冻结。
- 有界预算、相关性判定、复用与补查条件；初次显式发布有效代次的最小步骤。
- Accepted ADR 适用范围增量、现有消费者回归与 Windows 实例；不因本轮 Linux 成功而免除平台验证。

## 5. 时序边界

保留原文 §7 不改字节。技术上稳定工具链足以支持 S2，不意味着维护者已允许现在执行、并行实施或改变排期。Q1 由维护者确认；Package B、S1/S2 游戏业务和沙箱重构都不是本轮实施目标。用户随后条件授权六阶段顺序交付及全部完成后 push/PR，但必须逐阶段通过独立 Work 会话 A/B 两组审核，并由工作会话同意。当前仅交 PRD 审核包，不提前进入下一阶段或推送。
