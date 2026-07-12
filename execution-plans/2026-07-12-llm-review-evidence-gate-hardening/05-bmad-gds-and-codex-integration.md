# BMAD/GDS 与两类 Codex 集成

## 1. 不修改安装文件

禁止直接编辑 `.agents/skills/bmad-*` 和 `.agents/skills/gds-*` 以落实本计划。原因是安装/升级会覆盖这些文件，并可能重新引入强制 finding 规则。

## 2. BMAD/GDS 薄适配

团队级、可提交的覆盖文件：

- `_bmad/custom/bmad-code-review.toml`；
- `_bmad/custom/gds-code-review.toml`；
- `_bmad/custom/bmad-quick-dev.toml`；
- `_bmad/custom/gds-quick-dev.toml`。

它们只通过 `persistent_facts` 加载 `docs/standards/llm-review-findings.md` 并声明 stock reviewer 输出为 candidate。实施测试必须运行 `resolve_customization.py`，证明覆盖仍生效。

通用 adversarial reviewer 没有 customization surface，因此不得把它放在最终阻断链。仓库自有 wrapper/gateway 负责过滤或替代它；不能依赖冲突 prompt 自动服从。

后续 review route 明确包含：

- Blind Hunter → `blind_hunter` candidate adapter；
- Edge Case Hunter → `edge_case_hunter` candidate adapter；
- Acceptance Auditor → `acceptance_auditor` candidate adapter。

三者的原始输出格式可以保留在 adapter 输入边界，但 adapter 之后只能使用统一 machine contract。后台不得把任一原始 Markdown/JSON 输出直接转换为 blocker、repair action 或完成状态。

## 3. 当前 7 月 7 日审查隔离

- 当前运行中的 7 月 7 日目录审查继续由现有流程完成；
- 不修改其 reviewer prompt、任务输入、historical ledger、severity 或 closure；
- 不使用新 gateway 重新解释已经产生的 finding；
- handoff 时只记录旧 route 的输入/输出格式、完成状态和不可变 evidence ref；
- R3 之后的新审查才切换到三个 candidate adapter；切换必须有 `routeVersion`、生效边界和 rollback evidence。

## 4. 平台长期开发 Codex

主要接入点：

- `scripts/sc/run_review_pipeline.py`；
- `scripts/sc/agent_to_agent_review.py`；
- task-run sidecars 和 recovery summary；
- 仓库自有 code/document/plan review wrapper。

作业前自检至少确认 authority、scope、protected paths、已有 tests、允许修改路径和 review contract revision。作业后 finding 必须通过 gateway 才能进入 repair guide。

## 5. 前台用户触发 Codex

主要接入点需在上游重构完成后重新定位，并遵守 Protected Phase Paths 审批：

- `ILlmRouteEngine` 只用于结构化/只读判断；
- 可执行 workflow 继续通过 `CodexHostedProcessCommandFactory`；
- Python 入口继续通过 `scripts/sc/_llm_backend.py::run_llm_exec`；
- file-changing route 继续使用 `workspace-write`、项目 recovery authority 和 route-specific acceptance。

前台 adapter 必须绑定 account/project/workspace、route action、authority hash、current acceptance blocker 和 browser-safe output。用户项目间的 finding、fingerprint 和 evidence 不得串读。

## 6. AGENTS 与 README 同步时机

- R1 新增 `docs/standards/llm-review-findings.md` 的同一变更，更新 standards index、`docs/PROJECT_DOCUMENTATION_INDEX.md`、相关 architecture index，并在 `README.md` 只增加标准导航和“gateway 尚未启用”的明确状态；此时不改 active AGENTS route。
- R2 平台开发 gateway 真正 operational 的同一变更，更新 `AGENTS.md`，加入平台开发 Codex 的 review standard、gateway 入口和不可绕过规则，并更新 agent workflow 深文档。
- R3 三层 reviewer 新 route 切换的同一变更，再更新 `AGENTS.md`，声明 Blind/Edge/Acceptance 只能产生 candidate，并记录 active `routeVersion`；旧 7 月 7 日历史不变。
- R4 前台用户可见行为、状态或 API 实际改变的同一变更，更新 `README.md` 和 Phase public behavior docs，只描述已有测试、smoke 和 evidence 的行为。
- R6 只同步最终 blocking/advisory、rollout 和迁移完成状态，不作为第一次 AGENTS/README 更新。
- 任何阶段不得在实现前写成“当前已启用”，也不得在能力 operational 后继续保留旧路由说明。

## 7. 升级回归闸门

BMAD/GDS 升级后必须验证：customization resolver 加载成功、stock skill 未成为最终 authority、gateway schema 未漂移、零 finding fixture 通过、直接绕过调用被测试阻断。

## 验收标准

- Given BMAD/GDS 重新安装，When运行 upgrade regression，Then仓库标准与 gateway 不被覆盖。
- Given stock reviewer 产生十条候选，When只有零条通过门禁，Then用户看到 clean result 而不是十条噪音。
- Given 前台项目 A 的 finding，When项目 B 发起审查，Then B 无法读取 A 的 evidence 或 disposition memory。
- Given 7 月 7 日审查仍在运行，When R3 尚未取得 handoff，Then三个 reviewer 的现有 route、输出和 ledger 均不改变。
