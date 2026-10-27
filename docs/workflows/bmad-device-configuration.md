# BMAD 部署设备知识库配置指引

## 适用范围与当前结论

本指引核对已合并管理员只读接入的 main `a4fdd19df060222741172bfc559ffa866b6254a2` 及后续查询绑定修复（2026-10-27），固定使用 BMAD-METHOD **v6.12.4**，不声称它是最新版本。适用于管理员配置 PRD、SPEC、Architecture 的知识查询；它不授权安装、业务生成、评审、知识库维护或发布。具体操作须有相应授权。

先读 [仓库约束](../../AGENTS.md)、[工具链路由](../../knowledge/toolchain-workflow-index.md) 和 [原生 wrapper 指引](bmad-native-wrappers.md)。保持两条边界：共享接入能力进入 Git；本机配置、原生安装和运行材料进入现有忽略范围。不要用设备补丁冒充共享能力，也不要直接修改 main。

| 能力 | 实际边界 |
| --- | --- |
| 两个 wrapper、三个阶段 | `jimuyun-spec` 包装官方 SPEC；`jimuyun-architecture` 包装官方 Architecture。PRD 使用独立官方安装，没有第三个仓库 wrapper。本次不修改两个 wrapper。 |
| 只读查询 | 复用 `scripts/python/knowledge_locator.py`，固定合法身份 `bmad-planning`。官方 skill 须自己执行真实查询并读源，外层预查摘要不能替代。 |
| 共享接入补丁 | 请求、projection、评估 schema 与 policy、builder、发布校验、测试接纳新 reader；不增加 daemon、MCP、数据库或新上下文协议，不改变 VDD/Quick Dev 职责。 |
| 内容范围 | 管理员可查询现有正式知识库内全部合格 repository-source 内容，包括文档、相关代码、conditional 和 historical；不另设文档／源码／历史类别白名单。未索引文件不会因此变成可查询内容。 |
| 权限边界 | 不授予知识库写入、维护或发布权限。现有源排除、semantic eligibility、snapshot、policy/projection、发布身份与哈希校验仍有效；不会开放仓库外凭据或 live workspace。consumer 字符串不是账号认证，设备和会话访问由管理员控制。 |
| 当前验证状态 | 本轮官方安装和配置解析已完成；一次真实只读 CLI 返回 `blocked`，因为正式 main-bound 代次未接纳新身份／新 policy。**尚未证明官方 skill 成功查询、读源和采纳，也未验证 Windows 端到端。** |

[部署侧台账](../../logs/scoped-input-preparation-20261024-v3/deployment-ledger.md) 与 [范围变更来源](../../logs/scoped-input-preparation-20261024-v3/SCOPE-SOURCE.md) 只保留历史迁移去向，不重新激活旧义务或声称旧实现已交付。

## 设备前置检查

1. 核对当前分支、HEAD、未提交内容与远端 main。知识事实固定到本地 `refs/heads/main`；更新 `origin/main` 不等于本地 main 已同步。保护原工作，不 reset、clean、自动 stash 或强制切换。
2. 区分外层真实仓库与私有 native 根。外层拥有正式知识库；native 根拥有该次官方执行的安装、配置及产物。不要扫描凭据或 live Hosted 工作区。
3. Python 3.11+、uv 与实际原生资源必须齐全。BMAD CLI 的版本输出不证明某项目已安装 skill，home/global 安装也不证明本次 native 根可用。
4. 两个 wrapper 的受控安装器仅安装锁定 SPEC、Architecture 及 runtime，**不安装 PRD、bmad-customize 或所有可选技能**。复用已核对的同版官方源码和 [既有安装入口](bmad-native-wrappers.md#clean-clone-and-explicit-installation)，不要改原生文件或自动使用 `--replace-native`。
5. PRD 用完整官方安装器安装到设备的 ignored 私有项目根，不能只复制 SKILL.md。本轮官方 Core+BMM 模块安装粒度为29个本地 skill；这不是运行过29个工作流。核对 PRD 全目录、必要 runtime 和有效配置中的实际技能依赖；不要把 SPEC/Architecture 的 verify 当作 PRD 验证。

官方源码须锁定 v6.12.4 的 commit `bab9082c3e884e0d72c759bcd1a6d90bcc01be84`。源码已有且字节正确时直接复用。官方 Node 安装器需要其 lockfile 对应依赖；获准时使用 `npm ci --omit=dev --ignore-scripts --no-audit --no-fund`，不得下载另一版 BMAD 或执行未核准安装脚本。本轮固定依赖安装119个包；离线缓存不全与源版本错误应分别报告。安装器自带版本提示不授权更新。

以下是**占位操作模板**，不是自动安装授权；变量必须由管理员设为已核实路径。私有 PRD 根应位于本仓库已忽略的 `_bmad/` 下，避免覆盖已有安装：

```powershell
# Run from the outer repository; set $BmadSource to verified official source.
$RepoRoot = (Resolve-Path '.').Path
$PrdRoot = Join-Path $RepoRoot '_bmad/prd-native'
node (Join-Path $BmadSource 'tools/installer/bmad-cli.js') install --directory $PrdRoot --modules bmm --tools codex --yes --no-shims
```

本轮已验证 PRD 的8个文件和4个 runtime 文件与官方源码一致，配置显式引用的 `bmad-review` 已安装但未执行。上述事实仅证明相应设备安装，不是查询成功或业务验收。

`git status` 的 tracked 修改和 untracked 文件要分别说明。一个 `M` 也可能来自仓库保存的 CRLF 与当前 LF 过滤规则差异；先比较 HEAD、index、原始字节、过滤后 blob 和 attributes，再判断是否有语义改动。不要把它未经核实称为用户修改，也不要为清除标记覆盖原文件。

## 消费者与正式发布前置

共享补丁接纳 `bmad-planning` 的**直接 Locator 查询路径**；它不冒用 `vdd/bootstrap`，不声明新增 VDD 冻结上下文或通用 attestation。权限在 [policy](../../knowledge/policies/consumer-policies.v2.json) 中固定；[请求 schema](../../knowledge/contracts/knowledge-locator-request.v1.schema.json)、[projection schema](../../knowledge/contracts/knowledge-consumer-projections.v1.schema.json)、catalog 与评估接口须一致。仅在分支增加身份或本地 TOML，不会使现有发布代次自动有效。

| 前置 | 真实 owner 与要求 |
| --- | --- |
| 同代正式数据 | [知识库 README](../../knowledge/README.md) 与 [维护 skill](../../.agents/skills/maintain-knowledge-base/SKILL.md) 规定维护入口；`scripts/python/publish_knowledge_catalog.py` 拥有正式发布。catalog、policy、projection、snapshot、manifest、current 必须一致，不手改派生产物。 |
| main 身份 | 发布控制脚本必须匹配 pinned main。共享补丁经正常审核合入后，才可按实际 main 准备发布；不能把功能分支偷偷命名为 main 或让本地脏字节成为事实。 |
| 授权请求 | `prepare_publication_request.py` 支持 `operator-requested`，该模式**不要求 stale route**；`catalog-stale-maintenance` 才要求真实、hash 验证的维护 route。两者均须真实的直接 target plan、其在当前 main 上的 `00-index.md`、当前 main 绑定及明确维护者确认。 |
| 禁止替代 | 不伪造 plan、route、维护者 ack；不复制修改后的 schema/policy 到 ignored 目录；不传 stale/unpublished 绕过参数，不删除 current、不关闭校验、不自动发布。 |

设备配置和只读查询授权不等于正式发布授权。现有 [adapter](../../scripts/toolchain/knowledge_query/adapter.py) 及 `knowledge/planning-query.toml` 的阶段映射和预算仍保留，但映射存在不证明 BMAD 已接通；本次直接 Locator 路径不冒称 adapter 的全部冻结／消费合同已支持新身份。

## 官方配置层与本仓库差异

固定版本参考：[团队采用](https://github.com/bmad-code-org/BMAD-METHOD/blob/v6.12.4/docs/customize/adopt-bmad-across-a-team.md)、[定制合并规则](https://github.com/bmad-code-org/BMAD-METHOD/blob/v6.12.4/docs/customize/customize-bmad.md)。每个 skill 的官方 `customize.toml` 是支持字段来源，不修改它。

每技能低到高：官方 `customize.toml` → `_bmad/custom/<skill>.toml` → `_bmad/custom/<skill>.user.toml`。标量覆盖、table 深合并；全带 code/id 的 table 数组按键合并，其他数组追加。空数组不能清除已有项；不要把已完整合并结果再次叠回官方 base，导致重复追加。

central config 低到高：`_bmad/config.toml` → `_bmad/config.user.toml` → `_bmad/custom/config.toml` → `_bmad/custom/config.user.toml`。central 身份／语言不授予知识权限，也不能代替 per-skill workflow 规则。

本仓库 `_bmad/*` 已忽略 custom、安装及设备辅助材料；原生技能和 wrapper 运行目录也有现有忽略规则。**不 force-add，不修改 tracked ignore，不用 skip-worktree/assume-unchanged 隐藏 tracked 改动，不自动 git rm --cached。** 共享合同／代码／测试进入独立分支；真实设备路径、启用选择、`.user.toml`、本地脚本、安装与日志不提交，不向查询、配置或 memlog 放入凭据和敏感环境值。

### PRD：按需来源与任务延迟触发

PRD 支持 `external_sources`，但它是自然语言规则，不是自动调度器。管理员给出真实 task、输入和外层查询命令后，官方 skill 必须在首次仓库事实判断前执行命令并读源；任务未知时等待，不能把加载规则算成查询。

以下仅为规则模板。`<device-query-command>` 必须替换为设备已验证的命令，真实路径只存 ignored 文件；已有相同键时合并内容，不重复声明 TOML 键：

```toml
# In the actual PRD project's _bmad/custom/bmad-prd.user.toml
[workflow]
persistent_facts = [
  "Administrator-operated knowledge access is read-only. Never invoke maintenance or publication. Query output is not adopted fact or delivery authority.",
]
activation_steps_append = [
  "After actual task and inputs are known, execute the supplied outer-repository query procedure before factual decisions. Stop on blocked/integrity failure. For a query-only check, stop before generation or reviewers.",
]
external_sources = [
  "Execute <device-query-command> against the real outer repository with consumer bmad-planning. Read hash-verified sources and record adoption/rejection, reason and use in the native memlog.",
]
```

### SPEC 与 Architecture：分别使用支持的字段

SPEC **没有 `external_sources`**。在该次 native 根的 `bmad-spec.user.toml` 使用 `persistent_facts` 与 activation hooks，让**官方 SPEC 自己执行**管理员提供的外层查询命令；不要把 PRD 字段复制进来，也不要仅检查外层预查摘要。

```toml
[workflow]
persistent_facts = [
  "Preserve upstream constraints and provenance. Execute the authorized outer-repository read-only query command yourself before new repository-fact decisions; reread verified sources and record decisions. Never maintain or publish knowledge.",
]
activation_steps_append = [
  "Wait for actual task/inputs if missing. Apply the supplied query procedure; stop on blocked. A query-only check must not start generation, finalization or reviewers.",
]
```

Architecture 支持 `external_sources`；在实际 native 根的 `bmad-architecture.user.toml` 使用同样的只读原则，查询 stage 语义为 architecture，读取相关源并记录与上游结论的冲突。`on_complete` 或 `external_handoffs` 不能补救事前缺失的事实核查，也不授予发布权。配置不修改原生 reviewer/coherence/preservation 要求；本次查询验证不启动这些后续工作。

## wrapper 隔离与原生消费边界

依据：[隔离构造](../../scripts/toolchain/bmad_native/__init__.py)、[SPEC bridge](../../.agents/skills/jimuyun-spec/scripts/bridge.py)、[Architecture invoke](../../.agents/skills/jimuyun-architecture/scripts/invoke.py)。**两个 wrapper 均不修改。**

1. 按现有公开 `prepare` 创建新的 `logs/bmad-wrappers/<unique-run>/native`。SPEC 目标须为合法 `_bmad-output/specs/.../SPEC.md`，package id 使用 `SPEC-` 前缀；不要通过任意输出路径绕过检查。
2. prepare 只复制锁定原生文件/runtime、必要仓库上下文和显式输入。外层的查询器、正式知识库和 per-skill `.user.toml` 不会自动复制。central 只传四个身份／语言字段并重绑私有输出。
3. **prepare 完成后、官方 skill 激活前**，管理员或设备本地启动脚本将对应 `.user.toml` 放入这个新 run 的 `_bmad/custom/`。保留 SPEC 已生成的 spec_output_path/run_folder_pattern、Architecture doc_workspace 和所有 owner/path 约束；不覆盖已有配置，不重写已经执行的历史 run。
4. 将实际 task/输入、真实外层根、可调用的绝对查询命令及只读限制作为明确调用者上下文。可以使用现存 ignored 本地辅助脚本组织这一步；本轮辅助命令接收 `--stage`、`--task-id`、`--query`，固定 reader，执行真实 CLI 并核对返回源。**它不是 Git 交付文件，也不是两个 wrapper 的新参数。** 其他设备不得假定此脚本随 pull 存在，可以按下节直接使用现有 CLI。
5. 官方 resolver 的脚本路径、`--skill` 和 `--project-root` 都指向该次 native 根。验证合并规则确实包含外层只读命令，再按原 invocation 激活官方 skill。外层解析成功不能代替私有解析成功。
6. 官方 skill 从私有根调用外层真实查询入口。不要让 native 冒充发布仓库，不把整个外层根当作可写原生根，不把外层摘要称为官方实际调用。SPEC typed 发布仍归 wrapper publish；知识库发布另归维护 owner。

### 新 run 自动继承的真实前置

官方 resolver 只读取显式 `--project-root` 下的配置；`new_workspace` 不会继承外层 per-skill TOML。因此，上面的逐 run 安装步骤本身不是自动继承。两个 wrapper 与官方 BMAD 文件保持不变时，必须由**已加载设备规则的宿主**在正常 prepare 成功后、官方激活前，自动完成第3步，再运行原 resolver。不得另造替代 wrapper 或把旧 run 的手工配置称为新 run 自动加载。

Codex 的 `developer_instructions` 可承载本机规则（[配置说明](https://learn.chatgpt.com/docs/config-file/config-reference)）。规则与辅助脚本必须保持 Git ignored；设备负责让**实际云端宿主会话**加载该规则，不能只在另一个 checkout 写入 `.codex/config.toml` 就宣称生效。规则应要求：从 prepare 原始结果取得新的 native 根，仅向合法新 run 安装对应配置，遇到已有冲突或已开始执行的 run 拒绝覆盖，随后按原官方激活路径解析并执行真实只读查询。

最低验证是从正常入口连续创建两个全新 run，无额外 prompt 或手工复制，分别证明宿主自动安装、官方 resolver 实际加载、官方 skill 自行查询并读源。配置文件解析或外层预查摘要都不能替代这三个事实。

2026-10-27 云端检查尚未证明自动继承。`codex -C <checkout> debug prompt-input` 在**嵌套 CLI 初始化**时，因只读 Codex home 的 `installation_id` 创建失败而退出；它没有进入指令加载验证，不能据此断言正在运行的云端宿主不支持该配置。不得改认证、权限或 Codex home 来绕过此失败。需要宿主侧确认其实际加载的设备指令，再进行上述两次真实验证；未确认前保留未完成状态。

## Windows 查询与解析示例

**先满足合法 consumer、同代正式发布和任务前置；当前记录的真实查询仍 blocked。** 下面是现有只读 Locator 的调用模板，无需新 MCP 或通用 helper。管理员先在外层仓库取得 `$RepoRoot`，再将相应命令和真实路径作为设备本地输入提供给官方 skill。示例不发明新 API，也不把 Locator 请求与 adapter 的 stage/operation payload 混用。

```powershell
$RepoRoot = (Resolve-Path '.').Path
$QueryProcedure = @'
from pathlib import Path
import json, subprocess, sys
root = Path(sys.argv[1]).resolve()
catalog = json.loads((root / "knowledge/catalogs/repository-knowledge-catalog.v2.json").read_text(encoding="utf-8"))
policy = json.loads((root / "knowledge/policies/consumer-policies.v2.json").read_text(encoding="utf-8"))
request = {"schema_version": "jimuyun.knowledge-locator-request.v1",
           "request_id": sys.argv[2], "consumer": "bmad-planning", "query": sys.argv[3],
           "snapshot": {"ref": "refs/heads/main", "commit": catalog["source_snapshot"]["commit"]},
           "policy_revision": policy["policy_revision"]}
result = subprocess.run([sys.executable, "-B", str(root / "scripts/python/knowledge_locator.py"),
                         "--repository-root", str(root)], cwd=root,
                        input=json.dumps(request).encode("utf-8"), capture_output=True, timeout=30)
if result.returncode:
    sys.stderr.buffer.write(result.stderr)
    raise SystemExit(result.returncode)
value = json.loads(result.stdout)
print(json.dumps(value, ensure_ascii=True))
raise SystemExit(0 if value.get("status") == "matched" else 2)
'@
# Replace these task/query placeholders with the actual task and question.
py -3 -B -c $QueryProcedure $RepoRoot 'actual-task-id' 'repository-rules'
```

这是**定位步骤**，不是自动采纳。matched 后仍须读取返回候选的真实源：用返回 path 在当前 pinned main 读字节，核对 source_sha256、main/read identity，再用于事实判断。不要把本地 dirty 文件冒充 main；拒绝路径越界和哈希漂移。需要当前工作树事实时单独标明身份，不能改写返回 receipt。

只解析配置而不运行 BMAD，可在**实际安装的 native 根**执行：

```powershell
$Resolver = Join-Path $NativeRoot '_bmad/scripts/resolve_customization.py'
$SkillRoot = Join-Path $NativeRoot '.agents/skills/bmad-spec'
uv run $Resolver --skill $SkillRoot --project-root $NativeRoot --key workflow
```

PRD/Architecture 换成各自实际安装根和技能名。`$NativeRoot` 由已完成的安装／prepare 返回，不是虚构目录。上述 Windows 示例只做语法核对，未在 Windows 实跑。中文文件用 Python 显式 UTF-8 写入，不用 PowerShell 文本写入命令保存；TOML、JSON 和 stdin 都保持 UTF-8。

## 结果解释、采纳与最小端到端核对

| 观察 | 能证明什么、如何处理 |
| --- | --- |
| CLI 版本、安装或字节 verify 通过 | 只证明相应安装范围；不证明查询、配置生效或业务执行。 |
| resolver JSON 包含规则 | 只证明该执行根的合并结果；不证明官方 skill 实际调用。 |
| prepare 返回 invocation | 只证明创建了私有执行材料；不是运行官方方法。 |
| Locator `blocked` / 候选为空 | 保留原返回并停止事实判断；核对身份、发布、projection、snapshot 和哈希，不冒用其他 consumer 或降级伪称成功。 |
| Locator `insufficient_match` | 知识库没有足够匹配；不能把零结果当事实成立，也不能冒称端到端通过。 |
| Locator `matched` | 有候选位置；官方调用者还须实际读源、核对身份／哈希并自行决定采纳。 |
| adapter awaiting-input / queried=false | 尚未执行查询；adapter 与 Locator 的退出码及字段语义分别解释，不混用。 |
| timeout / cancelled / integrity failure | 保留失败，按其真实原因处理；不通过换身份、改 snapshot、忽略返回或无界重试制造通过。 |

Locator CLI 的退出码0也可能携带 `blocked`，所以示例显式检查 payload status；不能只看进程退出。现有 adapter 的 `queried=true` 同样只表示尝试，不表示成功。本次共享接入不授予任何 authorizes，查询结果不能驱动自动维护或发布。

获准部署后的最小真实验证，不运行完整 PRD/SPEC/Architecture 生成或额外 reviewer，也不以 VDD/Quick Dev/Acceptance 替代：

1. 保留实际根、版本／字节、配置备份与正确根的 resolver JSON。
2. 满足正式发布后，选择一个真实、有限的问题，由**官方 skill 在激活规则中亲自调用**只读入口。记录 task、query、consumer、generation/snapshot、返回状态和源 path/hash，读取至少一个真实源并核验。
3. 在原生 memlog 记录 accepted/rejected、理由及用途；不由 helper 预填采纳，不把索引摘要当源权威。
4. 保留一个成功链和一个缺身份／拒绝链，明确阶段和平台覆盖。若仍 blocked，停在真实阻塞，不运行完整业务来掩盖。

2026-10-27 已在合并后的真实 main 核对安装、私有根配置解析与原生手工激活读源。直接读取来源不等于 Locator 查询成功，更不等于未来 run 自动继承。正式维护检查为106/110：三个既有 Quick Dev/Acceptance 查询在入口精简后出现过时术语或漏绑操作指南，BMAD 正例只有标题证据；另有两个 BMAD case ID 不合现有 schema。修复应保留原排名、来源哈希、正文证据和负例门禁，不改发布信任规则。修复分支的候选评估不授权正式发布：发布入口仍要求控制代码和输入字节与真实本地 main 匹配。修复合法进入 main 后，重新准备当前 main 绑定请求、通过发布检查，再更新本地派生代次并补真实查询。不得把分支冒充 main；不推送派生代次或设备配置。**自动继承、正式 Locator 成功查询与 Windows 端到端仍未完成。**

## 回退配置

配置前保全已有设备文件原字节和哈希。回退时恢复原 override 或移走此次新增文件，检查 team/user 两层；空数组不能抵消追加规则。对实际执行根重新解析，确认恢复预期合并值。

私有 run、失败和原件保留为历史；新配置用新 run，不重写历史 receipt。回退不删除 generation、不篡改 policy/schema/current、不改官方字节，也不自动 restore-lkg。正式知识恢复仍须独立发布 owner 及其授权。
