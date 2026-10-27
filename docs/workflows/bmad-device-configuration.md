# BMAD 部署设备知识库配置指引

## 适用范围与当前结论

本指引以远端 main `863ce37a80bc56b8cda37e4c3c4c839f3de72ee0` 为核对基线（2026-10-27），固定使用 BMAD-METHOD **v6.12.4**，不声称这是最新版本。它说明设备侧如何准备配置，以及当前尚不能靠配置完成的接入。本文不授予安装、部署、知识库发布、修改共享合同或运行任何交付流程的权限。

先读 [仓库约束](../../AGENTS.md)、[工具链路由](../../knowledge/toolchain-workflow-index.md) 和 [原生 wrapper 指引](bmad-native-wrappers.md)。安装、字节锁和 wrapper 命令以最后一项为准，本文不重复安装历史。

| 能力 | 当前实际状态 |
| --- | --- |
| VDD 查询交付 | 已交付；`scripts/vdd/compile_plan.py` 调用 `adapter.prepare_consumption`。这不证明 BMAD 阶段已接线。 |
| 本地 planning adapter | `scripts/toolchain/knowledge_query/adapter.py` 有 `prepare-consumption --repository-root` CLI，通过 UTF-8 stdin 接收 JSON；无须新增 MCP 服务。 |
| 阶段与预算配置 | `knowledge/planning-query.toml` 保留 prd/spec/architecture/vdd-create/vdd-repair；enabled=true，候选12、输出65536字节、调用3次、超时30秒。配置存在不等于调用发生。 |
| BMAD 消费身份 | adapter 将前三阶段映射为 `bmad-planning`，但当前请求 schema、projection schema 和 policy 不支持完整接入；禁止冒用 `vdd`。 |
| PRD 接线 | 当前 tracked tree 没有 `_bmad/custom/bmad-prd.toml`；设备本地文件须另查。没有交付默认 PRD 查询 hook。 |
| SPEC / Architecture | 已有 `jimuyun-spec` / `jimuyun-architecture` 原生包装；不自动执行知识库查询，不自动传递外层 per-skill 配置。 |

[部署侧台账](../../logs/scoped-input-preparation-20261024-v3/deployment-ledger.md) 和 [范围变更来源](../../logs/scoped-input-preparation-20261024-v3/SCOPE-SOURCE.md) 保留 25 项迁移去向。它们是溯源，不是已完成状态或当前可执行合同；不要把旧日志中的 PRD hook、SPEC 补查、Architecture 接线方案重新当作已交付要求。本文也不重新激活这些历史义务。

## 设备前置检查

1. 确认工作区、已有改动、当前分支与远端 main。知识库事实固定到本地 `refs/heads/main`，不会自动 fetch；`origin/main` 更新不代表本地 main 已更新。由维护者按设备现有 Git 策略同步，不重置工作区或覆盖改动。
2. 区分仓库根与 wrapper 私有根。先检查源、schema、policy、current generation 是否齐全，再选择真实任务的显式输入。不要扫描凭据目录或 live Hosted 工作区。
3. Python 必须为 3.11+，uv 已在 PATH。BMAD CLI 版本输出不证明项目原生 Skill 已安装。原生资源必须在该仓库 `.agents/skills/` 下，不能用 home/global 安装冒充。
4. 两个 wrapper 的受控安装器只安装 `bmad-spec`、`bmad-architecture` 和锁定 runtime。**不安装 PRD、bmad-customize 或所有可选 reviewer 技能**。PRD 要另行授权安装同版完整官方技能及其实际依赖；不能仅复制一份 SKILL.md，也不能把两个 wrapper 的 verify 当 PRD 验证。
5. 获准安装时复用 [既有安装入口](bmad-native-wrappers.md#clean-clone-and-explicit-installation)。保留原生 LF 和锁定字节，不改官方文件、Python launcher 或 manifest，不自动使用 `--replace-native`。

以下 PowerShell 仅为只读前置检查；`C:\src\ji-mu-yun` 是设备路径占位，先替换。此文档工作没有执行这些设备检查或安装。

```powershell
Set-Location 'C:\src\ji-mu-yun'
git status --short
git branch --show-current
git rev-parse refs/heads/main
git ls-remote origin refs/heads/main
py -3 --version
uv --version
Test-Path '.agents/skills/bmad-prd/SKILL.md'
Test-Path '.agents/skills/bmad-prd/customize.toml'
git check-ignore -v _bmad/custom/bmad-prd.toml _bmad/custom/bmad-spec.user.toml
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:UV_OFFLINE='1'
py -3 -B -m scripts.toolchain.bmad_native verify
```

最后一条只验证两个锁定技能、runtime、版本及 central TOML；未安装时应明确报告未安装，不能因此假称 PRD 可用。该版本/字节验证不是查询执行，也不是原生方法执行。

## 必须先解决的消费者与发布阻塞

当前 [请求 schema](../../knowledge/contracts/knowledge-locator-request.v1.schema.json) 的 consumer 枚举只有 `vdd`、`quick-dev`、`bootstrap`、`refactor-acceptance`；[projection schema](../../knowledge/contracts/knowledge-consumer-projections.v1.schema.json) 同样没有 `bmad-planning`。[消费者 policy](../../knowledge/policies/consumer-policies.v2.json) 无此身份。adapter 的映射不构成注册，单独添加设备 TOML 无法合法查询。

以下是**尚需另行授权的实施工作**，本指引不执行，也没有一条现成的 BMAD setup 命令可以包办：

| 事项 | 真实负责入口与完成条件 |
| --- | --- |
| 消费合同与最小权限 | 仓库工具链维护者按 Accepted ADR-0044/0048 和 `knowledge/contracts/`、`knowledge/policies/` 的现有 owner 扩展合法身份；明确 domain、visibility、lifecycle、status、路径、候选上限、冻结点，复核所有消费/结果 schema 与验证器。不能只让 TOML 拼入 consumer 或跳过校验。 |
| 同代派生与正式发布 | [知识库 README](../../knowledge/README.md) 与 [maintain-knowledge-base](../../.agents/skills/maintain-knowledge-base/SKILL.md) 是入口；正式 owner 是 `scripts/python/publish_knowledge_catalog.py`。catalog / policy / projection / snapshot / manifest / current 的 hash 必须同代并通过 owner 检查，不能手改 generation 或 current。 |
| 发布授权材料 | `prepare_publication_request.py` 当前要求真实 target plan、hash 验证过的 stale-maintenance route、当前本地 main 和维护者确认。设备配置本身不满足这些前置。没有合法 route 时交由发布 owner 决定后续授权工作，不伪造 plan、route 或 `--ack-maintainer`。 |
| BMAD 调用与结果传递 | 设备维护者明确 PRD 调用位置；SPEC/Architecture 的调用者需确定查询发生于外层真实仓库，并将获准结果/源文件送入私有原生执行。自动接线或修改 wrapper 是独立实施范围。 |

不要借 `build_knowledge_catalog.py`、改 policy_revision、换 consumer、删除 current 或关闭查询来绕过拒绝。`enabled=false` 仍检查 publication 和权限，且是仓库配置，不是本任务的回退按钮。发布控制脚本还须与 pinned main 一致；未提交的设备补丁不会成为可发布事实。维护/发布不是消费失败后的自动恢复步骤。

## 官方配置层与本仓库差异

固定版本来源：[团队采用指引](https://github.com/bmad-code-org/BMAD-METHOD/blob/v6.12.4/docs/customize/adopt-bmad-across-a-team.md)、[定制与合并规则](https://github.com/bmad-code-org/BMAD-METHOD/blob/v6.12.4/docs/customize/customize-bmad.md)。实际 schema 是各技能目录的 `customize.toml`，不要修改它。

每技能低到高：官方 `customize.toml` → `_bmad/custom/<真实 skill 名>.toml` → `_bmad/custom/<真实 skill 名>.user.toml`。标量后者覆盖；table 深合并；全带 code 或全带 id 的 table 数组按键替换/追加；其他数组按 base/team/user 顺序追加。空数组不能清除已有项，重复配置会重复追加。

central config 低到高：`_bmad/config.toml` → `_bmad/config.user.toml` → `_bmad/custom/config.toml` → `_bmad/custom/config.user.toml`。前两项由安装器管理，持久定制放后两项。central 身份/语言配置不是知识库权限，也不能代替 per-skill workflow 配置。

官方把不带 user 的文件作为团队共享文件；**本仓库 `.gitignore` 的 `_bmad/*` 将整个 custom 目录忽略**，所以两种文件目前都属于设备本地状态，不会随 Git pull 分发。不要 force-add 或修改 ignore；若需要团队分发，另行明确授权。不得在 TOML、查询、结果、memlog 中放 API key、token、用户凭据或敏感环境变量值。

### PRD：按需来源与任务延迟触发

先核对官方 [bmad-prd schema](https://github.com/bmad-code-org/BMAD-METHOD/blob/v6.12.4/src/bmm-skills/plan/bmad-prd/customize.toml)。它支持 `external_sources`，但这是自然语言的按需来源登记，**不是自动预查调度器**。需要事实判断时，必须在任务身份、输入已知之后，第一次仓库事实/复用范围结论之前实际执行查询并读源。交互模式尚未获得输入时应等待；headless 由调用者一开始提供输入。activation 仅加载规则不算调用。

下面是获准接入后可采用的稀疏规则样例，不是当前已经生效的安装文件；无需新 MCP。英文指令遵守仓库代码/配置约定。若已有同名键，应合并内容，不能重复声明 TOML 键。

```toml
# _bmad/custom/bmad-prd.user.toml
[workflow]
persistent_facts = [
  "Never treat query output as adopted fact or delivery authority. Record actual source reads and adoption decisions in the native memlog.",
]
activation_steps_append = [
  "Load the local query procedure. If task identity or selected input paths are unknown, wait for them; do not claim a query. After inputs are known, apply the source rule before the first repository fact decision.",
]
external_sources = [
  "When a PRD scope or reuse decision needs repository facts, use scripts/toolchain/knowledge_query/adapter.py prepare-consumption against the real repository root, stage prd, with the actual task_id, operation, inputs and query as documented in docs/workflows/bmad-device-configuration.md. Require approved consumer admission first. Inspect the returned status and source hashes, read current sources, then record accepted/rejected reasons and scope impact. Stop on policy or integrity failure.",
]
```

### SPEC 与 Architecture：分别使用支持的字段

[SPEC schema](https://github.com/bmad-code-org/BMAD-METHOD/blob/v6.12.4/src/bmm-skills/plan/bmad-spec/customize.toml) **没有 external_sources**。用 `persistent_facts` / activation hooks 约束接收输入后补查；不要复制 PRD 的字段。上游已采纳依据保留来源与角色，仅新问题、缺依据或相关源变化触发必要补查；纯编辑复用需记录理由并重新核对当前权限和依赖，不以旧成功记录跳过权限。

```toml
# _bmad/custom/bmad-spec.user.toml
[workflow]
persistent_facts = [
  "Preserve valid upstream capabilities, constraints, exclusions and unresolved questions. Keep provenance separate from normative companions.",
  "After task inputs are known and before factual decisions, inspect supplied query evidence and actual sources. Supplement only for a new question, missing basis or relevant source change, using stage spec at the authorized outer repository. Record reuse or supplement reasons and native adoption decisions. Stop on permission or integrity failure.",
]
activation_steps_append = [
  "Confirm the caller supplied the real task and approved source evidence. Missing task inputs mean awaiting input, not a completed source check.",
]
```

[Architecture schema](https://github.com/bmad-code-org/BMAD-METHOD/blob/v6.12.4/src/bmm-skills/plan/bmad-architecture/customize.toml) 支持 `external_sources`。在 `_bmad/custom/bmad-architecture.user.toml` 的 `[workflow]` 中可使用下列条目：

```toml
[workflow]
external_sources = [
  "Before an implementation-affecting decision needing repository facts, use approved outer-repository planning evidence for stage architecture. Read relevant Accepted ADRs, current owners, interfaces and implementation, compare upstream adopted conclusions, and record conflicts, impact and owner resolution in native memory. Never let an index summary silently replace normative scope.",
]
```

这些规则不删除原生 reviewer、coherence 或 preservation 要求。配置 `on_complete` / `external_handoffs` 不能补救事前缺失的事实核查，也不授权对外发布。

## wrapper 隔离与原生消费边界

源码依据：[公共隔离构造](../../scripts/toolchain/bmad_native/__init__.py)、[SPEC bridge](../../.agents/skills/jimuyun-spec/scripts/bridge.py)、[Architecture invoke](../../.agents/skills/jimuyun-architecture/scripts/invoke.py)。

- 两者新建 `logs/bmad-wrappers/<unique-run>/native`，复制锁定原生文件/runtime、AGENTS.md、工具链索引和显式选择的输入；不是复制整个仓库。查询器、catalog/policy/generation 不会自动出现在 native 根。
- 外层 central config 由官方 resolver 合并后，只传递 `user_name`、`communication_language`、`document_output_language`、`project_name`；重新绑定 `core.output_folder` 与 `modules.bmm.planning_artifacts` 到私有输出。不是保留全部 central 键。
- 外层 `_bmad/custom/bmad-*.toml` / `.user.toml` **不会自动复制**。SPEC prepare 自己生成私有 `bmad-spec.toml`，写入 spec_output_path 和 run_folder_pattern。Architecture 的 doc_workspace 由调用者入口绑定。不要覆盖这些隔离路径。
- 私有根的 resolver 必须使用私有 `--project-root`，外层解析成功不能证明私有解析成功。`{project-root}` 在私有执行中指向 native，不是外层仓库，不能据此调用不存在的查询器。
- 当前没有自动的查询结果注入/采纳接口。未来获准的设备操作可在 prepare 后、原生激活前显式补充私有 custom 规则、可读输入与调用者上下文，保留 wrapper 已生成字段，并分别验证外层查询证据和私有规则；这一步不是当前 prepare 自动完成的行为。若要持久自动传递，应另行修改/验证 wrapper 合同，不临时修改官方文件或绕过路径限制。
- 查询针对获准的外层真实仓库，原生只写私有产物。不得把外层根当作原生写根来“解决”缺文件。SPEC 正式 typed 发布仍由 jimuyun-spec publish 拥有，Architecture 结果采纳为 companion 是独立显式操作；知识库发布是另一 owner。

## Windows 查询与解析示例

**当前 BMAD 消费合同阻塞未解除，下面的 PRD 查询不具备成功前置，不应直接作为可用部署执行。** 获准接入、同代发布、任务授权和原生安装都满足后，再按实际任务替换路径与内容。CLI 的输入字段来自 `prepare_consumption`，不要给它发送底层 Locator 的 schema_version/consumer/snapshot/policy_revision；函数会从阶段和正式数据生成这些字段。

示例 `logs/bmad-device/request.json` 内容如下；`requirements/example.md` 是占位，必须替换成真实、获准、仓库相对的现有 UTF-8 文档。所有 payload 路径用 `/`，不得用绝对路径、`..`、凭据路径。输入文件最大262144字节，stdin 最大65536字节，scope 最多64条；输入中显式反引号文件引用还可能扩展 scope。

```json
{
  "stage": "prd",
  "operation": "create",
  "task_id": "device-prd-example-001",
  "mode": "headless",
  "inputs": ["requirements/example.md"],
  "scope": ["requirements/example.md"],
  "query": "Identify current implementation and reuse boundaries for the selected requirement",
  "narrow_overrides": {"max_calls": 1}
}
```

stage 对应 prd/spec/architecture；operation 为 create/repair/update/resume。不要为 BMAD 改成 vdd-create。mode 支持 headless/interactive，但不会自动实现聊天等待调度；缺 task_id 返回 awaiting-input、queried=false。显式 scope 不是绕过权限的白名单；缩小预算只能取仓库约束的交集。

用编辑器或 Python `Path.write_text(..., encoding="utf-8", newline="\n")` 写 JSON/TOML；中文不得通过 PowerShell 文本写入命令保存。以下已核实接口示例通过 Python 传 UTF-8 字节，避开 PowerShell 管道编码；仅在上述前置全部满足后执行：

```powershell
py -3 -B -c "from pathlib import Path; import subprocess,sys; p=Path('logs/bmad-device/request.json'); r=subprocess.run([sys.executable,'-B','scripts/toolchain/knowledge_query/adapter.py','prepare-consumption','--repository-root','.'],input=p.read_bytes()); sys.exit(r.returncode)"
```

示例不含 `record_path`，查询不自动写记录；后续要留存可显式添加 `record_path: logs/bmad-device/<unique-run>/query.md`（替换占位）。adapter 会创建/追加调用者记录，故此选项不再是纯只读调用。允许的记录是 logs/ 或 execution-plans/ 下 Markdown，或 `.memlog.md`；不能用源码文件充当记录。源与正式知识库仍只读。不要向查询请求直接塞入凭据、真实密钥或整段不相关历史。

安装完且依赖已备好时，可以只解析定制，不运行 BMAD：

```powershell
uv run .\_bmad\scripts\resolve_customization.py --skill .\.agents\skills\bmad-prd --project-root . --key workflow
```

只有 PRD 真实安装后才使用此路径。SPEC/Architecture 换成各自真实技能目录；wrapper 则将脚本、skill、project-root 三者都明确指向该 run 的 native 根。解析 JSON 中出现规则，只证明合并结果，不能证明工具调用、读源或采纳发生。禁止把 native run 的不存在路径当成功配置。

## 结果解释、采纳与最小端到端核对

| 观察 | 正确处理 |
| --- | --- |
| NATIVE_INSTALLATION_MISSING 等 | BMAD 本地安装失败，按原生指引处理；不是知识库 no_match。版本冲突、字节漂移和 TOML 无效必须分别报告。 |
| awaiting-input / queried=false | 尚无任务身份，不声称查过；获得任务后由调用者显式触发。 |
| not_installed / queried=false | 知识库整套不存在才是可选未安装；仅在允许的直接源路径独立核查，不能声称知识库通过。 |
| publication_incomplete / integrity_failed / publication_missing | 已有安装残迹或同代/hash/发布损坏；阻塞，不降级成未安装或空结果。 |
| policy_denied / invalid_request / unknown_failure | 停止相应事实判断并保留原始错误。当前不支持的 consumer 可能被 schema 验证表现为错误，不能硬认定只会返回 policy_denied。 |
| no_match / degraded / unavailable | 分别看 reason_code（如 empty、stale_verified、timeout、config_missing）；要求独立直接源核查，缺关键事实则停止结论。 |
| cancelled / budget_exhausted | 终止该 episode，不通过换 task_id、重试或删记录绕过预算。 |
| hit | 仍不是采纳；读实际源、验证当前身份/hash，再由原生作者判断。 |

不要只看退出码：CLI 0 也可能是 awaiting-input 或 prepared 的降级结果，2 表示 blocked；`queried=true` 是尝试计数，不等于成功。读取 status、availability、query_result.outcome/reason_code、diagnostic.raw_status、permission_checked、incomplete、budget_usage 和 authorizes（应为空）。

未来获得端到端运行授权后，按同一真实任务留存以下最小证据，不运行 VDD/Quick Dev/Acceptance 来替代 BMAD 证明：

1. 设备版本、实际原生路径/字节验证、配置前后备份与 resolver JSON；wrapper 另记私有根与私有合并结果。
2. 任务与输入确定时间、事实判断前的真实查询返回、topic/consumer/原始状态、generation/index identity、source path/hash/read identity。分清 main、branch、dirty worktree、direct-source；索引片段不能替代当前源码、调用者、测试和合同读取。
3. 原生 memlog 中逐项 accepted/rejected、原因、实际用途和复用/新增范围影响；区分已实现、仅计划、已排除、拟新增、未验证，明确上游结论冲突由哪个 owner 处理。adapter 不能预填“已采纳”。
4. 至少核对一个真实成功链与一个缺身份/拒绝链；只有实际完整执行才可声称端到端通过。配置解析、prepare invocation、tree verify 各自只能证明自己的范围，不能证明 reviewer 或语义结果。
5. 当前阶段若卡在消费者接入，就在此停止并记录阻塞；不要为凑成功样例篡改权限或发布。此文档仅做静态核对，未在 Windows 或任何原生 BMAD 流程做端到端验证。

## 回退配置

在获准设备配置前，用 UTF-8/字节保真方式备份已有 custom 文件，记录文件路径与 hash。回退时恢复该设备原内容，或移走此次新建的 override；同时检查 team 和 user 两层，不能以空数组抵消追加规则。然后对实际执行根重新运行 resolver，确认回到预期合并值。

wrapper 私有 run 保留为历史证据，不在已执行的 run 内重写配置/结果伪造旧状态；下一次使用新 run 并明确新配置。回退不得删除 generation、修改 policy/schema、回退官方原生字节或自动调用 restore-lkg。知识库恢复须走其独立发布 owner 和授权，且保留失败证据。
