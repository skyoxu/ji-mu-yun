# 8-24 本地 Codex 修复执行方案

## 1. 任务与目标

仓库：skyoxu/ji-mu-yun  
分支：implementation/8-24-identity-isolation-recovery-v2  
外部审核基线：8c71281c969e2b234fc09975114129dd025644d5  
审查报告：8-24-external-review-8c71281c.md

本任务修复外部审核发现的 R1–R8，实现现有 8-24 要求，并修正不能证明这些要求的测试。

目标是具备可信的 Quick Dev implementation-complete 条件，并提供可供外部复审的当前实现和证据。不得自行宣布外部审核通过或 Acceptance 通过。

请直接进行实施，持续推进至完成或遇到明确的权限、环境或产品决策阻断；不要只输出计划。

## 2. 范围与工作原则

1. 在现有 8-24 需求目录内修复，不创建新的 VDD 目录，不重跑 VDD，不扩充上游需求。
2. 不引入多节点、容器、远程 KMS、持久模型会话、React 重构、签名治理或通用评估平台。
3. 保留已有正确实现。禁止为了制造 RED 回滚正确生产行为。
4. 不降低断言、不增加跳过条件、不用固定成功字段替代真实行为。
5. 不修改历史 RED/GREEN、TRX、回执或失败证据；新一轮证据追加保存。
6. 读取并遵循根目录和相关子目录的 AGENTS.md，以及当前 Quick Dev Skill 的执行和恢复说明。
7. 先检查本地已有授权。对尚未授权的受保护修改，按仓库规则集中列出必要授权，不重复请求已有授权。
8. 不触碰真实 Hosted Workspace、生产数据库、运行中的平台、Caddy 或生产账号。
9. 独立 Windows 测试账号、凭据和 ACL 使用隔离测试资源；涉及系统级账号配置时遵循已有授权和配置规程。
10. 提交、推送、部署和合并遵循当前会话已有授权；本文件不额外授权部署或合并。

## 3. 开始前必须完成的检查

### 3.1 固定候选

- 检查当前分支、HEAD、工作区修改和目标基线关系。
- 保留用户修改；必要时使用隔离 worktree。
- 若 HEAD 已包含后续修复，逐项复核，不覆盖或重复实施。
- 记录实际修复起点。旧报告中的行号只作定位提示，以当前代码为准。

### 3.2 读取权威输入

需求目录：

execution-plans/2026-08-24-phase-b-c-identity-isolation-workspace-recovery/

优先读取：

- LOCAL-HANDOFF.md
- implementation-repair-input.md
- implementation-order.v1.json
- implementation-case-map.v1.json
- slices.v1.json
- obligations.v1.json
- 当前受影响 slice 的 agent-context

上游：

- _bmad-output/planning-artifacts/prds/prd-jimuyun-2026-08-23/prd.md
- 同目录 addendum.md
- _bmad-output/specs/spec-phase-b-c-identity-isolation-workspace-recovery/ 下当前 Spec 包
- _bmad-output/planning-artifacts/architecture/architecture-phase-b-c-identity-isolation-workspace-recovery-2026-08-23/ARCHITECTURE-SPINE.md
- ADR-0061 及受影响的已接受 ADR

保留当前 351 项义务、73 个 slice 的语义范围，不因修复困难删除或判定不适用。

### 3.3 建立修复对照表

在本轮 logs 目录保存简洁对照表：

| 字段 | 内容 |
| --- | --- |
| finding | R1–R8 |
| source | 对应上游条款 |
| slices | 当前映射中的受影响 slice |
| production | 实际生产入口和拥有者 |
| selector | 真实可执行测试 selector |
| baseline | 当前观察结果 |
| fix | 实施修改 |
| evidence | 本轮验证位置 |
| disposition | open / fixed / already-fixed / blocked |

只追踪 R1–R8 及其直接依赖，不开展无边界问题挖掘。

## 4. 测试与 Quick Dev 执行规则

外部审核发现了弱 oracle。本次允许修正对应测试，但不能在同一冻结运行中偷偷改变测试后沿用原 RED/GREEN。

正确顺序：

1. 读取当前测试及上游语义。
2. 将弱测试修正为真实行为测试，保留仍然有效的旧回归。
3. 为变化的测试建立新的运行或 successor，记录替代原因。
4. 验证 discovery、真实生产调用、精确 selector 和失败归因。
5. 冻结本轮测试、fixture、selector 和执行依赖。
6. 观察当前行为：
   - missing：真实因果 RED 后修复。
   - present：执行回归，不制造 RED。
   - partially-present：保留已有行为，只修缺失部分。
   - unverifiable：记录环境阻断。
7. GREEN/REFACTOR 使用同一冻结 selector。
8. 必须修改冻结测试时，终止其证明效力并建立 successor，不混用前后证据。

构建失败、账号权限缺失、超时、未发现测试、错误 TRX 和未执行用例均不能算产品 RED 或通过。

使用仓库当前 Quick Dev 入口和支持的恢复方式，不编造参数或绕过校验器。

## 5. 修复顺序

| 顺序 | 修复内容 | 对应发现 |
| --- | --- | --- |
| 1 | 当前凭据只读拒绝与持久失效 | R5 |
| 2 | 正式 Runner 强制隔离及重启恢复 | R2 |
| 3 | Snapshot 密钥、内容边界和用户配额 | R6、R7 |
| 4 | 真实 route authority 解析 | R3 |
| 5 | Restore 安全发布与故障协调 | R4 |
| 6 | HTTP 异步业务闭环 | R1 |
| 7 | 真实证据独立复核 | R8 |
| 8 | 集成回归、终态与外部交接 | 全部 |

开始时即可建立 R1 的端到端回归；其 GREEN 依赖前面的服务修复完成。

## 6. 各项实施要求

### R5：旧凭据拒绝不得改变当前权威

主要位置：

PhaseA.Platform/Workspaces/RestoreService.cs

修复：

- DemandCurrentRuntimeCredential 的拒绝路径不得写入当前凭据。
- 只有授权的轮换/恢复状态转换能够发布新的运行时凭据。
- 明确区分 API 登录凭据与恢复后运行时 capability。
- 旧运行时凭据和旧 lease 的失效必须跨服务实例和进程重启保持。
- 不以一个内存 HashSet 作为失效的唯一权威。

必须验证：

- 连续两次使用旧凭据均拒绝。
- 每次拒绝前后，持久当前凭据不变。
- 当前合法凭据仍然可用。
- 新服务实例及独立进程重启后结果一致。
- 使用有效的其他输入隔离验证凭据边界，避免因另一个错误而“碰巧拒绝”。

优先检查 S13、S6 及映射中的直接依赖。

### R2：正式 Hosted Runner 必须强制执行隔离

主要位置：

- PhaseA.Platform/Runs/HostedProcessRunner.cs
- PhaseA.Platform/Security/RunnerIsolationPolicy.cs
- 正式 workspace 创建、恢复、启动和 command factory 路径

修复：

- 服务端为需要隔离的 Hosted 工作装配项目身份和授权根。
- 缺少描述符、账号、凭据、ACL 或合法 lease 时，启动前拒绝。
- 禁止找不到内存描述符就退回平台身份。
- 重启后从服务端持久配置恢复身份绑定，并重新验证实际 ACL。
- 不能直接将重启时观察到的 ACL 当作可信策略；策略必须来自权威配置。
- 保留已有平台维护进程的必要能力，但与用户 Hosted dispatch 明确区分，调用者不能切换为高权限模式。
- 保留 Job Object、取消、超时、子进程清理与秘密生命周期要求。

必须验证：

- 经正式创建与 dispatch 启动的 Runner 使用独立低权限身份。
- 能操作本项目授权根。
- 不能枚举 Account 根、访问同账户兄弟项目、跨账户目录及平台受保护资源。
- 缺少隔离注册时，子进程没有启动。
- 平台进程重启后仍满足相同边界。
- ACL 漂移导致拒绝，受保护修复后才能恢复。
- Job Object 和取消实际终止子进程树。

S54 fixture 中主动注册隔离不能替代正式接入测试。

### R6：KeyReference 必须引用受保护密钥

主要位置：

PhaseA.Platform/Workspaces/SnapshotManifest.cs

修复：

- 移除从固定字符串和公开 KeyReference 推导密钥的方案。
- 使用现有平台秘密管理能力；若不足，采用适合当前单节点 Windows 的受保护本地密钥机制。
- 密钥随机生成并受访问控制保护，KeyReference 只作标识。
- 密钥不得进入 manifest、Snapshot、日志、测试输出或仓库。
- 保留认证加密和恢复完整性验证。
- 明确旧格式兼容行为：不能静默把不安全旧格式当作安全格式，也不能修改历史 Snapshot。
- 若兼容旧数据，采用明确受控的导入/新版本创建路径并记录边界。

必须验证：

- 授权密钥可恢复原始内容。
- 仅持有 Snapshot 和源码不能获得密钥。
- 缺失或错误密钥拒绝恢复，且不发布结果。
- 密文或认证元数据被修改时拒绝。
- 密钥引用、策略版本和内容保持正确绑定。

修正 S22，不得重复公开派生公式来证明“加密有效”。

### R7：Snapshot 内容边界与账户配额

主要位置：

PhaseA.Platform/Workspaces/WorkspaceStorageService.cs

内容边界修复：

- 将支持的持久文件和禁止内容规则落实在实际读取路径。
- 组合固定安全排除规则与服务端生效的版本化 admin 扩展名策略。
- 排除 cache、临时 build、秘密、ticket、内部 Snapshot 文件和不安全链接。
- 不能允许普通调用者自选空 blacklist 绕过策略。
- 再次创建 Snapshot 不得递归包含历史 Snapshot 文件。
- 使用受控枚举/流式处理与实际大小检查，避免先无限制读入内存再判配额。
- 发布必须保留不可变版本；中断的新 Snapshot 不影响最后有效恢复点。

配额修复：

- 从服务端 Account/Project/Workspace 关系解析实际 placement。
- 按用户累计活动 Workspace 和 Snapshot，用量不得混入其他账户。
- 有 Snapshot 的 Workspace 不能整根排除。
- 覆盖实际存储表示，并明确避免重复计数的规则。
- 软删除项目只释放一次逻辑配额，重启后不能重复释放或重新计入。
- 保留受控物理清理、pin、active restore 输入保护和审计语义。

必须验证：

- 混合非空目录中支持内容保留、禁止内容确实未进入 payload。
- 第二次 Snapshot 不包含第一次 Snapshot 的内部文件。
- admin 策略变更只影响新 Snapshot。
- 两账户、多项目、已有 Snapshot、软删除、重启下的用量正确。
- 超额或处理失败不发布部分结果、不破坏上一有效 Snapshot。

### R3：使用真实 route recovery authority

主要位置：

PhaseA.Platform/Workspaces/RestoreService.cs
以及现有 hosted route recovery 拥有者

修复：

- 删除初始化时固定写入“八项已具备”的成功证据。
- 删除基于幂等键特殊文本判断 authority 的分支。
- 消费现有八来源恢复顺序及当前 live blocker。
- staging 阶段执行发布所需前置检查；发布后验证当前 readback/route 绑定。
- 证据由实际解析结果产生，并关联来源及本次 Attempt。
- 幂等键作为不透明请求标识，不参与业务规则判断。

必须验证：

- 完整真实输入可继续。
- 删除、替换或使实际 authority 过期后必须拒绝。
- 当前 blocker 能覆盖历史成功记录。
- 输入相同、使用不同合法幂等键，业务判断一致。
- 即使幂等键包含 missing-authority，真实来源完整时也不能被特殊分支误拒绝。
- readback 只返回当前账户、当前发布结果。

优先修正 S40。

### R4：安全发布、fencing 与崩溃协调

主要位置：

- RestoreService.cs
- RestoreAttempt.cs
- 当前 metadata/schema、lease、publication 拥有者

修复：

- 持久绑定 requester、Account、Project、Snapshot、目标 Workspace 和幂等键。
- 同键不同请求拒绝；同键重试保持稳定操作身份和追加历史。
- 用单节点持久抢占/条件转换保证只有合法 Attempt 能发布。
- 发布前验证实际内容、owner/ACL、当前授权、route 前置与 fencing。
- fencing 检查必须与发布权获取和最终提交协调，不能仅在复制前查一次。
- 明确记录目录切换前后的意图、结果及补偿状态。
- 启动协调同时检查数据库和实际目录；恢复旧 ready、完成合法新结果或隔离异常。
- 不允许仅修改状态名而把半完成目录留作可用结果。
- 清理仅限本 Attempt 拥有的安全路径，保护旧 ready 与 active inputs。
- 实际状态、审计和错误类别一致。

必须在独立进程验证以下中断点：

| 中断点 | 必须证明 |
| --- | --- |
| staging 写入中 | 旧 ready 保持可用；半成品不发布 |
| 校验完成后 | 重启能识别和处置未完成 Attempt |
| 旧目录移走、新目录未切入 | 重启恢复可用状态或明确隔离 |
| 新目录切入、最终 metadata 未提交 | DB/文件系统协调有确定结果 |
| metadata 提交后、cleanup 前 | 结果可重入，cleanup 幂等且不误删 |

同时验证：

- 同键并发请求不会形成两个独立发布结果。
- 复制期间新 fencing 生效，旧持有者不能发布。
- 复制期间账号停用/凭据撤销，下一发布边界拒绝。
- 发布前 ACL 漂移被发现。
- 失败、重试、重启的历史保留。

只实现当前单节点必要的一致性，不扩展分布式协议。

### R1：接通真实异步 API

主要位置：

Program.cs 的 HandleDurableWorkspaceOperationAsync
及当前 operation、queue、readback 相关服务

修复：

- Snapshot、Restore、ACL repair 分派到真实业务拥有者。
- Restore 从服务端逻辑标识解析源 Snapshot 和合法目标；不信任客户端绝对路径或 accountId。
- 接受请求时持久化 operation 和不可变身份绑定。
- 排队执行前及关键发布边界重新授权。
- 接受后由应用生命周期拥有执行，不依赖浏览器连接。
- operation 状态来自实际业务结果。
- 重启后可处置 pending/running operation，不能留下永久惰性记录。
- 维持稳定 operationId、幂等重入、受保护查询和安全 evidence pointer。
- 公共 API 优先 additive。旧请求缺少必要信息时给出明确有界响应，不能返回虚假成功。

必须验证：

- 认证 HTTP 创建实际非空 Snapshot。
- 指定该 Snapshot 恢复到受控替代根，并验证内容、ACL、route/readback、受控 Run。
- ACL repair 实际修复可观察的权限问题。
- 在操作确实执行中断开客户端，操作仍达到真实结果。
- 重入返回相同 operationId 和业务结果。
- 应用重启后的恢复路径有效。
- 错误输入、跨账户、排队期间停用和真实业务失败不会标记 succeeded。

断开测试使用确定性的阶段同步；不能读完响应后关闭连接就宣称验证了后台存活。

优先修正 S14 及对应 HTTP 测试。

### R8：独立验证本轮实际证据

主要位置：

S53BoundaryTests.cs 及当前独立证据 helper；
S25、S46 和实际 evidence producers

修复：

- 让独立进程读取本轮实际 TRX/执行记录和对应产物。
- 核验精确用例被发现、执行、非跳过且结果符合预期。
- 权限证据必须包含真实受限子进程、实际访问尝试与 OS 拒绝。
- 故障证据必须来自真实 Restore 阶段终止和重启协调。
- round-trip、旧数据迁移和 redaction 均绑定真实生产操作。
- 普通 hash 用于绑定内容，不能把同一包内的自填 hash 当作执行真实性证明。
- 执行记录的定位由当前运行上下文控制，不能让被验证包自行声明任意权威。
- 新进程本身不是充分条件；检查的内容必须符合业务语义。
- 不增加签名服务、通用 benchmark 或外部治理。

必须拒绝：

- 只有 passed/accepted/executed 声明。
- 内容和自填 hash 一起替换。
- 用例缺失、未执行、跳过或失败。
- 使用旧候选、其他运行或无关测试的证据。
- 有类别名但没有真实权限/故障验证。
- 产物缺失或与执行记录不一致。

保留正常真实证据包的通过正例，避免实现为一律拒绝。

## 7. 全局验证与完成条件

修复过程中只重跑受影响测试及直接依赖。实现稳定后：

1. 对 R1–R8 完成逐项关闭核查。
2. 检查既有 351 项义务的映射没有丢失，受影响证明已更新。
3. 在 Windows 运行非跳过的真实身份、ACL、Job Object 测试。
4. 运行持久重启、故障切点、单节点 fencing 和幂等发布测试。
5. 运行认证 HTTP Snapshot→Restore→route/readback→controlled Run。
6. 验证真实旧数据库升级与复用，以及秘密排除和用户配额。
7. 独立进程验证本轮实际证据。
8. 运行完整平台测试：

```powershell
dotnet test PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj --logger trx --results-directory <本轮证据目录>
```

命令中的目录占位符必须替换为真实路径。

通过当前 Quick Dev Skill 支持的入口形成 Q7/Q8。不得手写 passed 回执、复用已失效旧 RED 或调用历史 terminal 捷径。

若运行期间继续修改生产代码或测试，重新执行受影响验证；最终 full-suite 与终态证据必须能够明确对应最终源码状态。

不得因为修复“看起来完成”而跳过必需验证。缺少 Windows 权限等环境时，结果明确记录 blocked/not-verified。

## 8. 证据与交接

建议使用：

logs/phase-b-c-implementation/<本轮唯一运行目录>/

保存：

- 修复起点、最终代码提交及源码状态。
- R1–R8 对照表和实际修改摘要。
- 精确命令、selector、执行结果和 TRX。
- Windows OS 边界证据。
- HTTP 业务结果、替代根 round-trip 证据。
- 故障注入与重启协调结果。
- A18 实际独立验证结果及负例。
- 当前 Q7/Q8 入口。
- 尚未解决的阻断；没有则明确为零。

不要将秘密、凭据、真实用户数据或未经脱敏的诊断提交到 Git。

避免为 evidence-only 提交制造循环哈希要求：明确标出被测试的代码提交，以及随后保存证据的提交；若后者改变代码，重新验证受影响范围。

更新当前导航，使外部 reviewer 能找到本轮材料；保留历史文件及其原始状态，不把旧 not-ready/pass 改写成本轮结果。

## 9. 最终回复要求

本地 Codex 完成后只需报告：

1. 实际分支和最终提交。
2. R1–R8 各自 fixed / already-fixed / blocked。
3. 定向测试、完整平台测试、Windows 实测和 A18 的实际结果。
4. 当前 Q7/Q8 和复审入口路径。
5. 是否已按既有授权推送。
6. 是否仍有未验证项。

只有全部必需条件满足，才能报告“已形成 Quick Dev implementation-complete 候选，等待外部复审”。

不得报告“外部审核已通过”或“Acceptance 已通过”。

遇到后续新问题，仅处理阻断上述闭环的直接依赖；无关问题记录后停止扩展。
