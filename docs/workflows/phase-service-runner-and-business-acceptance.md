# 普通项目 Runner 接入与业务链路验收

日期：2026-10-02。适用仓库：`skyoxu/ji-mu-yun`。依据：Accepted ADR-0035、ADR-0036、ADR-0038、ADR-0061。

## 普通新项目首次接入

生产宿主在 `ProjectCreationService` 中注入 `WindowsProjectRunnerProvisioner`。工作区播种和项目 README 写入后，创建流程注册项目专属的 Windows 普通用户、加入本机 Users 组、将凭据写入平台宿主 Windows 用户的凭据库，并应用现有 Runner 隔离策略。创建成功意味着身份、凭据与工作区 ACL 已完成注册；后续 Bootstrap 和业务 route 仍须各自的实际执行与验收。

逻辑账号/项目 UUID 保留在隔离 descriptor 中；本机用户名采用不超过 20 字符的随机名称。密码不写入命令参数、环境、工作区或日志。凭据使用 LOCAL_MACHINE 持久化，属于写入它的平台 Windows 用户；服务重启须保持相同宿主身份。迁移到另一台机器或另一宿主 Windows 用户不自动迁移凭据。

宿主需具备创建本地账号、管理凭据和设置 NTFS ACL 的权限。账号父目录只向平台管理员开放；Runner 在自己的项目根与 repo/runtime/meta 目录内获得 Modify 权限，不获得账号目录枚举权限。隔离 marker 由管理员保护，Runner 不能重写该注册文件。执行仍通过现有低权限进程、Job Object、超时与取消机制，不扩大 route 工具权限。Windows 的 `.cmd` / `.bat` 入口通过 `cmd.exe` 执行时保留实际脚本路径，并传递参数与 UTF-8 标准输入。普通非零退出是业务执行失败；完成清理后允许再次调度。超时与取消完成清理后同样可重试；检测到进程清理失败时仍阻断该 Runner 实例的复用。

注册失败时删除本次创建的凭据和本机用户；创建服务撤销项目元数据，并清理本次新建工作区。失败处理不使用已取消的请求 token。既有目录不进入创建失败清理范围。软删除保留期中的成功注册不在此处删除，避免破坏既有恢复契约。维护者仍须按保留期与保护规则处理最终清理；此修复不引入账号物理清除产品。

直接构造的领域测试可省略 provisioner；生产 DI 始终注册真实实现。没有注册的领域夹具不能在 Windows 上调度隔离 Runner。Linux 不被标记为完成 Windows 原生隔离。

## 新增业务链路验收

入口：`scripts/python/phase_a_business_chain_acceptance.py`。这是读取当前平台证据的验收命令，调用以下账号受保护的 GET API：

- `/api/projects/{projectId}/workflow-route`
- `/api/projects/{projectId}/prototype-contract/status`
- `/api/projects/{projectId}/ui-wiring-closure/latest`

命令不创建项目，不启动模型、Godot 或业务 route，不修改用户沙箱。凭据从环境变量读取，默认变量名 `PHASEA_USER_TOKEN`；不把 token 放进命令参数。HTTP 仅在显式 `--allow-http` 诊断时使用；不跟随重定向。返回体有大小上限，单次 HTTP 超时不超过 30 秒。报告只保存判定码和 API 引用，不复制请求凭据或完整项目内容。

```powershell
# PHASEA_USER_TOKEN is supplied privately by the operator's credential mechanism.
py -3 scripts/python/phase_a_business_chain_acceptance.py `
  --base-url https://your-phase-service.example `
  --project-id YOUR_PROJECT_ID
```

退出码：`0` 为通过，`2` 为阻断或不可验证。证据追加在 `logs/phase-a-business-chain-acceptance/<date>/<run>/acceptance.json`，指定 `--output` 时也必须位于仓库 `logs/` 下，相对路径与绝对路径使用相同的判定、报告和退出码约定。

| 判定 | 条件 |
| --- | --- |
| `passed` | 当前 GDD 问卷、场景路线、GDD 文档、需求映射、原型契约、骨架和 UI 闭环均有唯一、可用、fresh 的机器读回；模块计划、模块执行、最新项目验收和打包步骤完成；无待修复状态；契约当前有效；UI 七项来源 hash 完整，相关字段与当前契约一致，服务端 final-readiness 门禁通过。 |
| `blocked` | API 可读，但任一证据缺失、重复、过期、hash 不符、执行未完成、修复未闭合或 final-readiness 未通过。 |
| `unavailable` | 缺少凭据、无权限、项目不可见、API 不可达、发生重定向或读回不是可解析的结构化对象。 |

UI 读回保留原有字段，新增 `freshness` 并返回实际来源 hash，设置 no-store。最终成功声明须使用既有全目标能力清单校验器，检测缺行、重复行、孤立行、临时状态、owner/重查条件/验收引用缺失，以及延期理由缺失。最终来源以当前原型契约、需求映射、iteration plan 的 `plan_hash`、validation sidecar 的 `validation_input_hash` 为准；iteration 必须 ready 或 succeeded 且 fresh，既有 plan 完整性校验、来源边界与项目证据绑定必须通过；validation 必须 succeeded 且 fresh，既有结构与来源边界校验错误会直接阻断最终成功声明。ledger 内的验收和阶段评审引用必须指向当前项目边界内实际存在且可读的文件，拒绝路径越界与 reparse point；已评审不适用和明确延期的行也不豁免证据检查。缺少这些来源时阻断，不生成替代证据。

验收命令不是 UI 闭环产物生成器。当前 route 若尚未生成规范的 UI/validation sidecar，就会真实地报告 blocked。HTTP 夹具和 Windows 原生测试通过，只证明接入与验收实现可用，不等于任意实际项目已经通过真实模型/Godot 全链路验收。此命令消费现有服务权威，不成为新的状态权威。

## 验证入口

- `.github/workflows/phase-service-entry-acceptance.yml`：Windows 2022 上构建平台测试，执行普通新项目的真实身份注册、隔离进程写入、父目录枚举拒绝、独立 testhost 进程重新读入注册后的执行，以及失败回滚回归。
- `ProjectRouteStateArtifactServiceTests`：成功字符串不能绕过缺失 ledger/current input；重复能力、缺失元数据和来源变化必须阻断；hash 读回来自实际 sidecar。
- `python -m unittest scripts.python.tests.test_phase_a_business_chain_acceptance scripts.python.tests.test_phase_a_gdd_to_module_hardening_smoke -v`：消费者负例、只读 HTTP、权限拒绝、重定向拒绝和脱敏。
- 既有 Windows Quality Gate 继续负责完整仓库质量验证。生产宿主部署与真实项目验收须单独记录实际结果，不能从 CI 夹具推断。

后置扩展需求见 [Phase 服务层暂缓需求](phase-service-deferred-requirements-2026-10-02.md)。

## 打包快照与版本恢复

部署此版本后，每次成功打包会自动保存项目工作区快照。ZIP 从该快照捕获的文件生成，版本记录绑定 `snapshotId`。快照失败时，本次打包不会显示成功。构建缓存、导出包、历史恢复目录和 Windows 执行身份注册不纳入快照；平台数据库、账号、凭据和运行中进程不属于恢复对象。

下载页每个有可用快照的版本提供“恢复此版本”。用户确认后，服务按该包绑定的快照恢复，不使用“最新快照”替代。项目忙、快照不可用或执行身份未就绪时不能恢复。旧包仍可下载，不会伪造其缺失的历史快照。

恢复任务异步受理，页面读取任务真实状态；刷新后继续查看，同一操作重试使用相同 `operationKey`。恢复成功必须同时具有活动版本切换记录。文件先在项目注册边界内经过完整性和 ACL 校验，成功后以单个数据库事务切换活动工作区路径并记录任务成功；事务之前失败或中断，原活动项目仍可使用。历史下载包保持可读。

恢复后需要新的原型项目验收通过记录才能再次打包；历史包仍可下载。恢复后最新模块计划暂停待检查，前台缓存重建，旧原型验收不能直接作为当前通过结果。请检查计划与恢复文件是否对应，再使用已有原型项目验收按钮重新验收；来源变化仍由现有契约及 UI 闭环校验阻断。恢复保留平台聊天、任务和审计历史，不把数据库整体回滚到旧版本。

API：`POST /api/projects/{projectId}/packages/{fileName}/restore`，请求体为 `{"operationKey":"your-operation-key"}`。返回 `202` 和 `operationId`/`evidencePointer`；通过 `/api/runs/{operationId}` 读取结果。凭据必须属于该项目账号。调用者不能指定其他快照、目标目录或 Windows 身份。

## 创建请求与宿主任务限额

继续沿用现有 `PHASEA_MAX_CONCURRENT_*` 配置。创建操作等待当前宿主的创建执行槽位，不因默认三个槽位已占用就直接拒绝第四个不同账号。单账号创建限额、项目数量配额及后续各类任务队列保持原规则。前台显示创建/等待状态；现有创建 API 在拿到槽位并完成创建后返回结果，尚未新增可跨请求恢复的异步创建接口。

这些配置目前作用于一个服务进程，不能当作未来多服务器平台的全局总量，也不等于多实例共享的单机总预算。多服务器调度后仍应按宿主执行预算分配任务，本次不引入另一套限额配置或分布式调度器。

## 前台验收与整体交付检查

前台场景验收和原型项目验收继续负责实际构建与运行检查。现有状态展示增加“整体交付检查”，从当前已有结果检查 GDD、契约、骨架、UI、模块、原型验收和打包是否完整且有效。它不重新运行模型或 Godot，也不新增一个用户必须再次点击的验收按钮。

`workflow-route` 读回增加 `businessChain`，包含 `passed|blocked`、阻断码和 `current_stored_business_chain` 范围。CLI 继续读取现有三个项目 API；有整体检查字段时，其阻断结果同样生效。账号权限与现有项目读取一致，不扩大为跨账号管理员查询。
