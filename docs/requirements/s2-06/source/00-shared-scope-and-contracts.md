# 三阶段需求的共享范围与合同

日期：2026-10-08。修订：6（补齐执行时复验、本地运行记录脱敏与最小账号软删除政策）。状态：已获用户同意的上游需求输入，尚未实施。
用途：本地 Codex CLI 的 BMAD PRD/spec/architecture → VDD → Quick Dev TDD；本文件不是 VDD 正式执行计划或验收证据。
代码基准：ji-mu-yun main@41567bd87f13060c9008846159249badeb8dcc62；newrouge main@8f93557d7f5f07b7931e3f4966a2dce04e458344。实施前按实际 HEAD 核对差异。


## 1. 已确定的产品边界

本轮只有 step1 五个业务包、step2 九个基础和安全包、step3 三个多节点草案。编号用于上游输入定位，不能当作已经生成的 VDD requirement ID，也不能据此声称实现完成。共享说明不单独形成第十八个业务需求目录。

用户项目是云端游戏原型，不提供 Git，也不连接用户 GitHub。继续使用已实现的快照、打包版本恢复及恢复后重新验收。用户游戏内容可由主 Agent 直接读取、解释、计划、创建、覆盖、编辑和删除，也可经平台提供的构建/Godot 验证入口执行；不要求强制先生成 patch，不做逐变更集审批。

**游戏项目文件采用正常删除。** 平台文件工具和项目脚本都不承担软删除保证，不建设回收区、回收站、删除拦截、管理员找回服务或每次覆盖备份。用户可恢复到已有、可用且实际覆盖目标内容的快照；删除和覆盖后没有有效快照时，不保证找回。既有账号停用/启用及 8-24 已完成的项目/快照元数据生命周期继续复用；不能把停用字段当作完整账号软删除产品政策已完成。S3-02 FR16/AC13 只补其最小授权撤销、身份/数据保留、容量与恢复语义，不做账号物理清除；正常文件删除不会删除账号或服务端项目身份。

全部写入入口都受同一账号/项目归属、低权限执行、资源、网络和服务端授权约束。用户对项目内容与误操作负责；平台继续履行已承诺的快照正确性、租户隔离和服务端边界，不把这句话扩展为法律免责条款。

当前不开放用户 MCP 安装、配置、选择或调用入口，不开放用户工具设置。工具由平台统一调度；仅服务器批准的工作流可调用指定受控 MCP。用户只安装/启用服务器已批准全局 Skill 的项目级能力。缺少 Skill 可提交工单，管理员通过最小管理页面查阅和手工判断安装，工单不触发自动下载、安装或授权。

用户和 Agent 不得安装任意外网 Skill、MCP、插件、软件或环境，用户级安装同样禁止。允许编写游戏项目自身逻辑，不声称禁止安装就能阻止任意新代码逻辑；强制约束落在环境不可变、权限、资源和网络边界上。

外网访问由受控搜索/抓取能力执行，并独立受服务器明确的出网许可策略约束。当前默认只访问批准的搜索服务与来源域名/协议/端口；search 结果或模型判断不会自动把全部公网列为许可，信誉评级不成为本轮必须依赖。主 Agent 通过关键词自行发现来源；用户指定 URL、IP、域名、编码地址或诱导指定网站不能成为访问授权。未授权内网、回环、链路本地和云元数据访问必须阻断；受控内部 MCP 是按服务、操作和权限明确注册的例外。

入口与生产节点同机仅用于测试。正式上线切割，不迁移测试账号或项目。未来入口保留普通用户注册、登录、归属查询和路由、管理员登录，不承担普通用户工作台或生产任务。每个账号持久化唯一生产节点归属，账号的全部项目、包、快照及执行保持同机；容量不足阻断新建，不静默改派。

### 1.1 组件选择与当前实施范围（2026-10-07确认）

| 板块 | 决定 | 落点与边界 |
| --- | --- | --- |
| API调试 | 未确认用户实际使用Postman；本次仓库搜索未找到Postman/Newman/Bruno配置 | 不据此前“可继续使用”断言已安装或已采用，不强制切换调试工具，不新建调试平台需求 |
| 后端 | 继续现有.NET服务 | 不引入Supabase Edge Functions或新的函数后端 |
| 身份验证 | 首选ASP.NET Core Identity | 这是认证组件；复用现有account_id、角色和ownership，接上现有存储，不另建账号权威 |
| 数据库与缓存 | 保留 SQLite 技术；共享读取先用有界节点查询缓存 | 最小字段/store 适配，不换数据库。多个 Runner 可共用一个节点服务；独立多 .NET 实例按真实需要选共享查询/KV并实证协调，不强制 Redis/Upstash，详见第1.2节 |
| 项目存储 | 继续节点本地存储 | 本轮不接OSS/第二对象后端，不跨节点存放用户项目、资产、快照或运行产物 |
| 密码恢复 | 阿里云邮件推送Direct Mail | 只发送已验证恢复邮箱的密码重置邮件；重置后仍用账号密码登录，不开邮箱验证码、magic link或其他登录方式 |
| 密码管理产品 | 暂不配置Bitwarden或其他新产品 | 现有密码hash、宿主秘密隔离、受保护配置与最小权限要求仍必须生效 |
| 平台日志 | 采用阿里云SLS | 小范围集中采集/查询平台运维日志及必要告警，不建设用户行为审计、全量跨route评估或Godot运行时分析 |
| 错误监控 | 小范围接入Sentry | 平台.NET异常与前台JavaScript错误；可沿用到React，但迁移surface须接错误边界、版本和source map；不新增全站重构 |
| 自动化产品 | 暂不配置Make/Zapier | 多节点分配、准入、队列和交接由平台原生协议实施，不以外部自动化平台承担权限或调度权威 |
| Supabase | 不再要求全家桶 | 不引入其Auth/数据库/函数/存储或Realtime作为本包依赖 |

SLS和Sentry只接收受限的平台运维事件，不上传用户项目源码、资产、快照、证据产物、完整Agent对话或原始游戏stdout/stderr。远端日志不是项目存储后端、ledger或验收权威；正式通过仍由现有受保护产物/记录与实际消费者判定。用户敏感信息、凭据、重置token、交接code和请求正文不进入遥测。

本轮新增邮件及运维出口属于受信Phase服务/平台页面的专门用途，并独立配置目标和权限；它们不授予项目Agent、游戏进程、Skill或用户主动内容网络访问。Sentry浏览器DSN是公开上报入口引用，不视为管理员秘密；其事件入口仍有采样/配额/限流。邮件、日志写入及source map上传的特权凭据留在受保护服务或构建通道。

多个工作流读取相同知识/demo，可以通过节点受控查询减少重复解析；多个 Runner 与多个独立 .NET 服务实例需区分。缓存只优化已测量的读取成本，不能代替 CPU、内存、进程、磁盘预算、锁/lease/fencing 或会话撤销。实际选择多服务实例时，相应共享预算、受保护认证状态及 Data Protection 密钥须先证明有效，不以 Redis/KV 的存在包办这些合同。

账号密码及邮件恢复的最小能力若用于正式单节点产品，应在其正式开放前完成；本包将其写在S3-02并不要求等到多节点才交付。S3-02其余节点交接细节仍是后续复审草案。

### 1.2 共享知识/demo、多实例和站内通知（本轮补充）

| 范围 | 必须达到 | 归属 |
| --- | --- | --- |
| 共享知识/demo 消费 | 已批准只读来源、具体版本、受控查询/复制；私有项目索引按账号/项目隔离 | S2-01、S2-04A、S2-05 |
| 内容来源最小连接 | 实际消费/复制关联已有 run/操作及真实版本；用户修改副本后不伪称原包字节 | S2-02；step1仅消费实际适用来源 |
| 查询缓存 | 有界内存优先；key 含来源/实现/参数/可见 scope，命中复验授权，失效/故障有限回源 | S2-01、S2-03A/B |
| 同节点多实例 | 物理 node_id 容量只计一次；多个 .NET 实例须共享预算、锁及同角色认证状态 | S2-03A、S2-06、S3-02同角色子范围 |
| 单节点站内通知 | 管理员发布/修订/撤回，明确受众/有效期，数据库持久化，用户收件箱与最小已读 | S2-04C第二内部里程碑 |
| 多节点通知 | 中心权威、鉴权增量、节点投影/游标本地事务、重试去重、离线续接及过期游标基线 | S3-03；step3仍为复审草案 |

共享原始资源置于受保护只读版本目录；复制进项目后成为独立可编辑的项目内容，全局更新不自动覆盖用户修改。只复用已有知识/Skill控制面的批准事实，补消费/预算，不实施8-05/8-06/7-31的发布、评估、升级治理。demo文件字节不因“共享”就整体搬入KV；小型查询/解析结果可以缓存。若只有一个节点服务进程调度多个Runner，先用其有界内存适配；独立服务多实例可在实测重复成本后选同节点共享查询服务或兼容Windows部署的KV，不以未来多节点数量强制选型。AddDistributedMemoryCache也不能被当作实际跨进程共享实现。

缓存命中不授予权限、不证明实际资源已应用，不保存权威密码、归属、资源承诺、route结果或恢复数据。节点容量、服务缓存/队列和游戏任务分别预算；新增KV的宿主成本也计入，不能直接据此提高安全并行上限。未消费全局知识的更新不使全部项目验收失效。

通知正文、变更序列和本地投影/已读存于受保护平台元数据，不进入游戏项目。正文不执行命令，不启动Agent、安装或授权；列表、详情、计数及已读统一按账号/归属过滤。有效全体/节点通知对有效期内新激活的符合受众账号也可见；已读只存notice/revision，不形成用户行为审计。step2先以周期刷新完成单节点，step3同步使用中心持久变更与节点原子游标；离线补收仅保证保留范围，不承诺即时撤回和无限历史。

SignalR实时刷新/Redis backplane为以后按需要选择的优化，不能作为通知事实来源：Pub/Sub/backplane不代替离线记录和补收协议。Make/Zapier不承担节点投递、权限、注册或资源调度。固定服务的节点同步/必要查询通道是受信平台用途，不把内网/外网许可传给项目Agent。

## 2. 本轮继续排除

1. 仓库现已实现的功能，特别是 8-24 的身份、Runner、ACL、Job Object、lease/fencing、快照、恢复、quota 和既有记录。
2. 8-24 已完成的能力不是重新实现的任务；必要回归和本包增量接线不算重复建设。
3. 8-05、8-06、7-31；docs/know.md、docs/know8.txt、docs/workflows/skill-control-plane-evolution-requirements.md 已规划的内容，不纳入新包。
4. 普通新项目首次接入真实 Runner、新增业务链路验收两个独立补丁，以及现已完成的打包快照/版本恢复/宿主创建排队。
5. 模式 B patch 网关、用户 Git/GitHub、第二状态权威、第二业务/hash/freshness/readback 校验器、全量 sidecar 历史迁移。
6. OIDC 或第二登录方式、账号物理清除、复杂用户审计、完整自建管理面 E2E、工具市场和自动安装平台。
7. 泛化 doctor/repair/自动批量回滚界面、外部 type-kit 整体迁移、通用工具/MCP 聚合目录和通用 handoff。
8. 第二对象存储后端、任意跨节点 Worker、账号动态迁移、跨机项目存储、完整 VM 隔离产品。
9. 全量 Phase 遥测、评估看板、skill/agent 评估升级、私有分析服务器抽取工程，继续放入用户指定的平台演进。分析服务器未来只读抽取、不回写、不向用户开放。
10. HTTPS 公网部署留到上线前最后收口，不作为本轮单独任务；正式生产会话安全不能以此为由降低。
11. 不建设 Godot 运行时分析、调用追踪或全量行为画像。当前 route 必需的实际场景执行、UI 断言和视觉采集属于已授权功能验证，不能因此延期。
12. newrouge 的专用历史 BOM 基线计数和特殊审计不移植。

## 3. 三层权限与写入路径

| 层 | 权威与写入原则 |
| --- | --- |
| 工具链控制面 | 保留其既有 workflow/Skill/validator/knowledge 权威；项目 Agent 不读取平台内部源码或改动该层，不把本包扩展为基础工作流改造 |
| Phase 服务层 | 服务端确认身份、归属、授权、run、产物、快照及激活；保护配置、数据库、凭据、全局版本和宿主控制记录 |
| 用户项目层 | 全部游戏内容可读写删增，项目配置/AGENTS/Skill 副本属于不可信项目输入，不能提升权限或伪造服务端成功 |

主 Agent → 平台已授权文件/执行工具，或已批准工作流的 MCP → 服务端确认的该项目实际工作区。相同约束覆盖后台任务、脚本、编译器和子进程。工具链二进制可按受控接口执行，但工具链源码、宿主配置、全局能力和其他租户内容不能作为普通项目文件暴露。

授权不只在 HTTP 受理时检查。S2-05 FR16/AC13 覆盖本轮实际开放入口在受理、排队后 dispatch 和关键受保护发布前的当前账号/凭据、归属、能力及工作区复验；S2-04A 能力批准不能替代该检查。账号停用或凭据撤销后的排队/运行行为须通过真实消费者验证，沿用现有取消/清理及明确撤销时效，不新造授权平台、不保证撤回已发生的游戏文件修改。该 S2 增量先使用现有 token/账号能力，不以未来 S3 登录为前置。

S2-03B FR16/AC13 同时覆盖普通 run 的 stdout/stderr、异常/evidence 在普通元数据入库前与 API/读回的既有脱敏策略，不能只保护 SLS/Sentry 出口。原始诊断若已有明确获准通道，仍受其访问、保留及容量限制；不进入普通用户结果，不新建原始日志库。输出脱敏不替代执行凭据隔离，完成本地脱敏也不放宽外部遥测的内容限制。

项目内可编辑 evidence/validation JSON 不是无条件可信。消费当前通过前，服务端须核对生产者提交的具体结果内容/证据字节与受保护 run/artifact 记录的绑定、实际检查结果、当前输入及工作区代次。真实 run ID、匹配的输入 hash 或可编辑文件自身重算的 hash，单独都不能证明结果未被篡改。项目副本改动不能更新这项受保护绑定。优先复用已有数据库绑定产物及完整性机制；若缺结果内容绑定，只在该既有记录上做最小兼容扩展，不新建签名服务、第二 ledger 或第二校验器。

用户可修改的 HTML/SVG、试玩内容、HTML 产物和模型输出属于浏览器侧不可信内容。不得在平台登录 origin 内无约束执行、读取平台 Cookie/localStorage/父页面或调用管理 API。复用现有安全读回/CSP，补齐嵌入、直接访问、新窗口和非 index.html 入口；需要执行游戏脚本时采用经验证的隔离 origin 或等价响应级隔离。服务器 Runner、出网限制与 HTTPS 都不能代替这条边界。S2-05 负责内容/会话隔离，S2-04B 负责浏览器实际网络请求限制；未验证前不开放相应主动内容入口。

原生 Agent/Codex 实际启动参数、配置加载、凭据及默认能力同样受服务器控制。项目内可编辑配置不得因客户端自动加载而新增 MCP、hook、插件、安装器、提供方地址或安全设置；平台不能只检查经显式 dispatcher 的调用。模型传输秘密留在受保护服务通道，不能因主 Agent 正常调用模型而流入任意项目进程。

## 4. 现有合同必须复用

| 对象 | 已有来源 | 本轮使用方式 |
| --- | --- | --- |
| account/project/workspace/run/artifact/correlation | Phase 现有元数据与 RequestContext | 引用既有身份，不重复创建另一套 ID |
| version/source | SnapshotId、SnapshotManifest.Files、恢复激活及工作区代次 | 连接来源，不能伪造 Git commit；未生成快照不填假 SnapshotId |
| validation | meta/routes/validation/latest.json，既有 validation.v1 消费合同 | 从真实执行生产，保留 validation_input_hash 语义 |
| UI 闭环 | meta/routes/ui-wiring/latest.json，ui-wiring-closure.v1 | 生产 ui_surface_matrix、现有来源 hash 和适用 full_target_closure_ledger |
| 风格 | GodotUiStyleCatalog、GodotUiStyleSnapshotSchema、既有 guide | 使用当前三种内置风格、冻结合同及真正 Theme/token/resource 消费 |
| 路由动作 | RouteActionDescriptors、RouteModuleContracts、现有 preflight/readback | 一处计算允许状态，browser/API/recommendation 共用 |
| 恢复 | WorkspaceStorageService、RestoreService、ProjectPackageRestoreService | 只消费、连接和必要回归，不再造版本管理或恢复权威 |

UI 闭环已有七项来源字段：source_iteration_session_hash、source_validation_input_hash、source_contract_hash、source_requirement_map_hash、source_godot_ui_contract_hash、source_ui_style_contract_hash、ui_style_snapshot_hash。具体字段、schema、status_dimension 和状态枚举以实施时注册表为准；文档示意不得替换运行时合同。

复用现有 status、status_reason、evidence_refs、updated_utc 以及身份字段。超时以实际运行失败原因表达；不得擅自在已有 JSON 合同添加不受支持的状态。新字段与旧 API 默认向后兼容。新表用增量迁移，测试用临时数据库和工作区，禁止用真实生产状态作夹具。

新增 source_version_ref、node_id、capability_set_ref 等名称是需由 BMAD/spec 固化的逻辑引用，不要求逐个复制进所有 sidecar。明确来源和消费者后才能选择最小存储位置。

## 5. 前台重构边界

必要的 BrowserUiRenderer/调用代码模块化作为所触及功能的前置，先稳定接口与当前业务闭环，再逐 surface 迁移 React。S1-02、S1-03、S2-04A/C 及 S2-05 的实际前台调用各承担本功能的模块边界和回归，不继续把新增 API 客户端、业务状态和渲染逻辑集中堆入巨型方法。BMAD 标明所触及 surface 的迁移/保留适配选择及可单独验证入口；不要求无关页面同期重写。Hosted Godot UI 验证和平台 React 是不同对象。有前台的S1-02、S1-03、S2-04A/C现有要求新增了本surface的模块化验收；不新增文件管理器或独立重构工程。迁移React的surface必须提供真实调用/页面验证，未迁移的surface不称React已完成。本包不重新启动 paused 的 7-11 全量前台计划，不宣称既有 BH-HANDOFF 通过，不追加整个前台重写目录。若完整 React 重建另立范围，应另行规划，不混入 S1-01B。

## 6. 下游消费与验收原则

先读取本共享说明、依赖说明和当前单包，不把十七包、全部历史计划和日志一次性装入上下文。BMAD 固化单包 PRD/spec/必要架构差异，再由本地 VDD 生成完整正式需求目录，Quick Dev TDD 按其有效计划实现；本文件不代替其权限与完成判定。

每个包自己的验收包含成功路径及其特有失败、取消、恢复、隔离和过期边界。外部审核检查实际增量、源码、机器结果及未解决问题，不要求创造另一套审核平台。现有消费者负例、真实 Windows 隔离、真实 Godot/UI 采集各证明不同层级，不能互相冒充。

保护路径修改及 ADR/安全合同变更遵守仓库 AGENTS 和当时有效授权；上游文档不是生产数据库修改、公开部署或基础工具链修改的授权。审查问题的FR/AC/开放条件是对现有preflight、授权、读取及执行保护的实施约束，不要求为每个RV编号创建新运行时gate、第二校验器、签名服务或状态权威。文档缺口修正不能作为实际验收通过的输入。需要补或修订 Accepted ADR 时由当地规划确定，不能仅把 Proposed ADR 写成 Accepted。

## 7. 依据

- [AGENTS](https://github.com/skyoxu/ji-mu-yun/blob/41567bd87f13060c9008846159249badeb8dcc62/AGENTS.md)、[README](https://github.com/skyoxu/ji-mu-yun/blob/41567bd87f13060c9008846159249badeb8dcc62/README.md)、[Phase AGENTS](https://github.com/skyoxu/ji-mu-yun/blob/41567bd87f13060c9008846159249badeb8dcc62/PhaseA.Platform/AGENTS.md)。
- docs/architecture/ADR_INDEX_PHASE.md：Accepted ADR-0035/0036/0038/0044/0061；docs/standards/phase-service.md。
- docs/workflows/phase-service-runner-and-business-acceptance.md；docs/standards/godot-ui-capability-contract.md；docs/standards/godot-ui-style-contract.md。
- [Identity自定义存储](https://learn.microsoft.com/en-us/aspnet/core/security/authentication/identity-custom-storage-providers?view=aspnetcore-10.0)、[ASP.NET Core分布式缓存](https://learn.microsoft.com/en-us/aspnet/core/performance/caching/distributed?view=aspnetcore-8.0)、[阿里云邮件推送](https://www.alibabacloud.com/help/en/direct-mail/product-overview/directmail)、[SLS](https://www.alibabacloud.com/help/zh/sls/)、[Sentry官方SDK](https://github.com/getsentry/sentry-javascript)、[Sentry .NET SDK](https://github.com/getsentry/sentry-dotnet)。官方通用资料用于设计核对，具体依赖版本须兼容仓库当时的.NET/前台版本，不因资料版本自动升级框架。
- [Windows文件缓存](https://learn.microsoft.com/en-us/windows/win32/fileio/file-caching)、[ASP.NET Core缓存接口](https://learn.microsoft.com/en-us/aspnet/core/performance/caching/distributed?view=aspnetcore-10.0)、[SignalR Redis backplane](https://learn.microsoft.com/en-us/aspnet/core/signalr/redis-backplane?view=aspnetcore-10.0)、[Redis Pub/Sub](https://redis.io/docs/latest/develop/pubsub/)。这些资料用于区分文件字节/查询对象、进程内/共享缓存与实时转发/持久补收，不要求采用 Redis 或升级框架。

- [Windows Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)、[NTFS quota](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/fsutil-quota)、[OWASP SSRF](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)、[OWASP session](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)。它们用于实现约束核对，不代表本平台已实现对应增量。