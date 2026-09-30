# 8-24 外部实施审查

- 仓库：skyoxu/ji-mu-yun
- 分支：implementation/8-24-identity-isolation-recovery-v2
- 审查候选：8c71281c969e2b234fc09975114129dd025644d5
- 审查结论：**request-changes；不能认可 Quick Dev implementation-complete。**
- 本报告不宣布 Acceptance 通过，也不修改需求、实现、历史证据或 GitHub review 状态。

## 范围与方法

对照 2026-08-23 PRD/addendum、当前 Spec 六文件、Architecture Spine，以及 8-24 修复后的实现输入、351 项原子义务和 73 个 slice，检查正式入口、核心生产服务、对应边界测试和候选中可获取的执行证据。确认存在 73 个对应的 C# BoundaryTests 文件，但文件数量不代表行为覆盖完成。

从 GitHub 固定提交读取文件；复用的本地缓存先与该提交 Git blob SHA 核对。核对重点包括 HTTP 到业务服务、Windows Runner 注册与启动、Snapshot 内容/密钥/配额、Restore 发布与恢复、当前凭据/fencing、独立证据读取器。未对 351 项逐项签发通过结论；以下阻断已足以否定整目录完成。

当前环境为 Linux，无 dotnet/Windows Runner 权限环境，未重跑 .NET 全套或 Windows ACL/Job Object 测试。实际执行了一项针对 S53 的复现：直接提取候选测试内嵌 Python 读取器，提交未进行任何生产验证但具备类别、自填哈希、时间戳和 executed=true 的测试包，返回 accepted=true。该复现不冒充 .NET 或 Windows 测试。

历史完成状态不能替代候选行为证据。以下发现均来自候选代码和当前上游合同，不引入多节点、容器、OIDC 部署、React 重构、治理或本地评估体系等新范围。

## 必须修复的阻断

### R1 / P1：三个异步操作入口直接标记成功，没有执行对应业务

**位置：** [Program.cs L409、L433-L451](https://github.com/skyoxu/ji-mu-yun/blob/8c71281c969e2b234fc09975114129dd025644d5/PhaseA.Platform/Program.cs#L409)。

Snapshot、Restore、ACL repair 共用 HandleDurableWorkspaceOperationAsync。它创建 operation Run，排队后执行 TryMarkRunStartedAsync，随即调用 CompleteRunAsync(..., "succeeded", ...)。该回调没有创建 Snapshot、调用 RestoreService 或修复 ACL。请求体只有 OperationKey，Restore 连源 Snapshot 的选择都未进入业务合同。

**违反：** FR-018、FR-019、FR-023；PIWR-025、026、033；AD-7；实现输入 A01、T09。

**测试为何漏检：** S14 检查 Accepted、非空 operationId/result 及重复请求结果相同；InvokeThenDisconnectAsync 等待完整响应并读完 body，不能证明“接受后断开、后台继续完成真实业务”。S14 自身义务明确排除了仅有惰性数据库记录。

**最小关闭要求：** 接通真实业务操作与结果；Restore 绑定服务端解析的源 Snapshot/目标；成功必须依赖业务结果。通过认证 HTTP 创建非空 Snapshot、恢复到替代根、检查 ACL、route/readback 和受控 Run；在执行中断开客户端并验证持久完成及幂等重入。

### R2 / P1：Runner 隔离是可选的内存注册分支，未注册时继承平台身份

**位置：** [HostedProcessRunner.cs L30-L54](https://github.com/skyoxu/ji-mu-yun/blob/8c71281c969e2b234fc09975114129dd025644d5/PhaseA.Platform/Runs/HostedProcessRunner.cs#L30)、[RunnerIsolationPolicy.cs L31-L74](https://github.com/skyoxu/ji-mu-yun/blob/8c71281c969e2b234fc09975114129dd025644d5/PhaseA.Platform/Security/RunnerIsolationPolicy.cs#L31)。

只有 Windows 且 TryGetWorkspaceDescriptor 成功时，HostedProcessRunner 才配置独立 UserName/Password 和 Job Object。找不到描述符时仍继续 Process.Start，使用平台进程身份。描述符与预期 ACL 都在静态内存字典中；没有从持久状态恢复的逻辑。已读正式启动、workspace seeder、command factory 路径没有接入 PrepareWorkspace；S54 测试构造器则主动调用它。

因此 S54 的受限 fixture 即使通过，也不能证明正式 Hosted 路径必然受限；重启后的未注册根同样有降级路径。

**违反：** FR-010..012、PIWR-015..020、AD-4，及当前单节点隔离要求。

**最小关闭要求：** 正式项目创建/恢复/启动路径装配服务端身份与授权根；缺失注册、凭据、ACL 或恢复状态必须阻断。增加经正式创建和 dispatch 的用例，以及进程重启后仍受限、缺少描述符时拒绝启动的负例。无需引入更强容器等级。

### R3 / P1：恢复路由 authority 被固定记录和请求字符串替代

**位置：** [RestoreService.cs L62-L71](https://github.com/skyoxu/ji-mu-yun/blob/8c71281c969e2b234fc09975114129dd025644d5/PhaseA.Platform/Workspaces/RestoreService.cs#L62)、[L301-L308](https://github.com/skyoxu/ji-mu-yun/blob/8c71281c969e2b234fc09975114129dd025644d5/PhaseA.Platform/Workspaces/RestoreService.cs#L301)、[L352-L354](https://github.com/skyoxu/ji-mu-yun/blob/8c71281c969e2b234fc09975114129dd025644d5/PhaseA.Platform/Workspaces/RestoreService.cs#L352)。

EnsureRouteRecoveryEvidence 在构造服务时写入 authority_count=8、has_current_blocker=1、is_blocked=0、can_continue=1。SignalsMissingOrStaleRouteAuthority 仅判断 idempotencyKey 是否含 missing-authority 或 stale-authority。没有在这些分支解析真实八项 authority 或 current blocker。

**测试为何漏检：** [S40BoundaryTests.cs](https://github.com/skyoxu/ji-mu-yun/blob/8c71281c969e2b234fc09975114129dd025644d5/PhaseA.Platform.Tests/PhaseB/Repair/S40BoundaryTests.cs#L68) 读取上述记录，负例调用 Restore("missing-authority")。这验证了固定记录和字符串分支，未验证业务前置条件。

**违反：** FR-021、PIWR-030、AD-9/AD-12、T09。

**最小关闭要求：** 调用现有 route recovery 真实解析链；由实际缺失/过期的来源决定拒绝。幂等键必须保持不透明，换任意键不能改变业务授权结论。用删除/过期真实 authority 的测试关闭。

### R4 / P1：Restore 的发布前校验和崩溃协调不完整

**位置：** [RestoreService.cs L57-L100](https://github.com/skyoxu/ji-mu-yun/blob/8c71281c969e2b234fc09975114129dd025644d5/PhaseA.Platform/Workspaces/RestoreService.cs#L57)、[L319-L349](https://github.com/skyoxu/ji-mu-yun/blob/8c71281c969e2b234fc09975114129dd025644d5/PhaseA.Platform/Workspaces/RestoreService.cs#L319)。

- staging 写完后直接移动旧目录和新目录，没有应用/复核目标 owner/ACL，也没有真实 route/readback 前置检查。
- lease 只在前段验证；文件拷贝到发布期间若出现新 fencing，最终目录切换和 Published 元数据写入没有再做持久条件检查。
- ReconcileInterruptedAttempts 仅将 Staging 行改为 Quarantined 并追加记录，不检查/修复 .restore-current、.restore-previous 或 staging 的实际目录状态。例如旧目录已移走而新目录尚未切入时进程终止，重启逻辑不会恢复旧 ready 内容。
- 同幂等键的读取、Attempt upsert、文件发布不是统一的抢占/条件发布协议；顺序重复调用测试不能证明并发或重入发布安全。

**违反：** FR-019/020、PIWR-026/028/038、AD-4/7/8/10、A07/A11/A13。

**最小关闭要求：** 发布前验证 ACL、authority、当前身份和 fencing；持久记录切换意图及补偿状态，按实际文件状态完成继续/回滚/隔离。在拷贝、校验后、目录切换间、最终元数据提交前后终止独立进程，重启验证旧 ready 和新结果。覆盖单节点并发同键与复制期间 fencing 变化即可，不要求分布式系统。

### R5 / P1：拒绝旧恢复凭据时反而将旧凭据写回当前权威

**位置：** [RestoreService.cs L356-L367](https://github.com/skyoxu/ji-mu-yun/blob/8c71281c969e2b234fc09975114129dd025644d5/PhaseA.Platform/Workspaces/RestoreService.cs#L356)。

DemandCurrentRuntimeCredential 发现输入 CredentialId 与持久当前值不同时，先 PersistCurrentRuntimeCredential(context, workspaceId)，再抛 UnauthorizedAccessException。被拒绝的一次旧凭据尝试因此已经改变了当前权威；第二次同凭据会通过这道检查，而原当前凭据可能被拒绝并再次覆盖它。

这不等于已证明旧 HTTP token 可穿透所有其他认证；它明确证明恢复凭据边界本身不满足撤销/拒绝语义。

**测试为何漏检：** S13 的旧凭据用例只尝试一次，未检查失败后的数据库值、第二次旧凭据及当前凭据可用性。

**违反：** FR-004/020、PIWR-027、A12、AD-3/9。

**最小关闭要求：** 拒绝路径不修改当前权威，只有授权轮换可发布新凭据。测试连续两次旧凭据拒绝、失败前后持久值不变，以及当前凭据继续有效。旧 lease 失效也须跨 RestoreService 实例/重启保留，不能只依赖 _invalidatedLeaseIds。

### R6 / P1：Snapshot 加密密钥可完全由公开 manifest 推导

**位置：** [SnapshotManifest.cs L100](https://github.com/skyoxu/ji-mu-yun/blob/8c71281c969e2b234fc09975114129dd025644d5/PhaseA.Platform/Workspaces/SnapshotManifest.cs#L100)、同文件解密分支；[S22BoundaryTests.cs L123](https://github.com/skyoxu/ji-mu-yun/blob/8c71281c969e2b234fc09975114129dd025644d5/PhaseA.Platform.Tests/PhaseB/Repair/S22BoundaryTests.cs#L123)。

AES 密钥是 SHA256("s22-static-profile/" + KeyReference)。KeyReference 存于 manifest，固定前缀存在源码中。拿到 Snapshot 的读取者无需任何受保护秘密即可计算密钥并解密；AES-GCM 调用存在并不建立要求的静态保护边界。

S22 使用同一公开派生式验证解密成功，因此不能证明 key-reference 指向受保护密钥。

**违反：** 当前 operations profile 的 encryption-at-rest/key-reference 要求；实现输入 W12；NFR-002。

**最小关闭要求：** KeyReference 解析到平台受保护的密钥材料，不能从 Snapshot 内容或公开标识推出。保留正常恢复正例，增加仅有 Snapshot 无密钥时不能恢复、缺失/错误密钥拒绝的负例；不要求新增远程 KMS。

### R7 / P1：Snapshot 内容过滤和用户配额统计没有实现声明的边界

**位置：** [WorkspaceStorageService.cs L193-L198](https://github.com/skyoxu/ji-mu-yun/blob/8c71281c969e2b234fc09975114129dd025644d5/PhaseA.Platform/Workspaces/WorkspaceStorageService.cs#L193)、[L117-L123](https://github.com/skyoxu/ji-mu-yun/blob/8c71281c969e2b234fc09975114129dd025644d5/PhaseA.Platform/Workspaces/WorkspaceStorageService.cs#L117)、[L173-L190](https://github.com/skyoxu/ji-mu-yun/blob/8c71281c969e2b234fc09975114129dd025644d5/PhaseA.Platform/Workspaces/WorkspaceStorageService.cs#L173)。

ReadSnapshotFiles 递归读取所有非 reparse 文件，仅按调用者传入的扩展名黑名单过滤。缓存、临时构建内容、秘密/ticket 文件和已生成 .snapshots-* 文件没有相应边界过滤，因此再次 Snapshot 会将旧 Snapshot 文件纳入候选内容。读取全部字节发生在配额判断之前。

GetQuota(accountId) 又将无 accountId 参数的 MeasureLiveWorkspaceBytes() 加到当前账户用量。该函数扫描 DB 所在目录下 placements 的全部文件，并排除任何包含 .snapshots-*.json 的整个根目录。这既无法区分用户，也可能漏掉有 Snapshot 的活动 Workspace；不能证明用户级实际占用。

**违反：** FR-017/022、PIWR-024/031、AD-6、NFR-002/007。

**最小关闭要求：** 在真实 producer 实施固定的支持/排除规则与生效的版本化 admin 策略，排除内部 Snapshot 存储；按服务端账户/项目 placement 统计实际用量，并保留软删除后的逻辑释放语义。测试含 cache/build/secret/ticket/旧 Snapshot 的非空树以及两个账户、多个项目和重启后的配额。仅检查 manifest 字段和单项目数字不足。

### R8 / P1：A18 读取器仍接受未执行的证据包，权限/故障证据也弱于需求

**位置：** [S53BoundaryTests.cs L120-L140](https://github.com/skyoxu/ji-mu-yun/blob/8c71281c969e2b234fc09975114129dd025644d5/PhaseA.Platform.Tests/PhaseB/Repair/S53BoundaryTests.cs#L120)、[L159-L165](https://github.com/skyoxu/ji-mu-yun/blob/8c71281c969e2b234fc09975114129dd025644d5/PhaseA.Platform.Tests/PhaseB/Repair/S53BoundaryTests.cs#L159)。

permissionObserved 只比较 Account/Project 字段和 acl: 前缀；faultObserved 只是读取不存在文件得到 FileNotFoundException。它们不能替代真实 OS 权限拒绝、Restore 故障与恢复证据。

独立 Python 进程只验证调用者填写的 executed、时间、类别和内容自填哈希。它没有核验具体测试执行/结果、候选及实际产物，不能拒绝内容与哈希一起重写的未执行包。

**本次实际复现：** 从目标 C# 文件提取原样 Python reader。五类 artifact 的 content 全设为 “No production verification was performed.”，各自计算普通 SHA256，executed=true、当前时间。结果：

```json
{"accepted": true, "reason": "accepted", "checkedArtifacts": ["snapshot", "permission", "fault", "migration", "redaction"]}
```

**违反：** PIWR-A18、AD-12、实现输入 A09 和 S53 对“未实际执行/仅声明通过”的拒绝义务。

**最小关闭要求：** 让新进程读取本轮真实执行记录与对应 OS/round-trip/fault/migration/redaction 产物，检查所需用例确实执行且通过、内容与结果绑定。负例包含“只有声明的结果”和“内容及自填 hash 一起替换”。这只是修复既定 A18，不要求签名治理或新建本地评估体系。

## 终态证据情况

固定提交的完整 Git tree 中，logs/phase-b-c-implementation 下 115 个已提交文件均属于 S54 相关执行/诊断。未在该候选中定位到修复后全 73 slices 的当前 Q7/Q8、当前 full-suite TRX 与所有终态类别闭环包。不能据此断言用户本地从未执行，但外部审查不能把未提供的证据视为通过。

LOCAL-HANDOFF.md 明确说明旧 compiler、source freeze 和 terminal 记录不能证明修复后的 candidate；旧 terminal/acceptance-handoff.v2.json 绑定 553c9096…，implementation-completion-handoff.v1.json 仍是历史 not-ready。这里没有要求重写历史状态：应提供新的、明确指向当前实现与本轮运行的 completion/evidence 入口。

即使补交全部本地日志，R1–R8 仍是代码/测试语义问题，不能靠日志数量关闭。

## 认可状态

| 判断项 | 本次结论 |
| --- | --- |
| 上游是否足以定义当前实施目标 | 足以界定本次阻断；这些都是已有要求 |
| 修复输入是否存在 351 obligations / 73 slices | 是 |
| 是否可以因测试文件齐全而认可实现 | 否，存在正式入口缺失和弱 oracle |
| Quick Dev implementation-complete | 不认可，request-changes |
| 是否应直接把整目录作为已完成交给 Acceptance | 当前不具备，先修上述实现和对应测试 |
| 是否要求重跑 VDD 或扩充新需求目录 | 否 |
| 是否已修改或推送实现 | 否，本次仅外部审核 |

建议在现有 8-24 目录内修复：先收紧真实入口与 Runner 边界，再修 Snapshot/Restore 的安全与恢复状态机，同时修正对应 oracle；最后运行同一候选的定向回归、完整平台套件、非跳过 Windows 实测和真实 A18，再生成本轮 Q7/Q8 入口并复审。这是既有范围的完成条件，不是新增增强。
