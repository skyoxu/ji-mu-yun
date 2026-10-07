# 2026-10-07 续接检查点

这是执行环境离线时保存的工作状态，供恢复会话后继续处理。它记录观察与已归档结果，不是本轮全量复验的原生终止报告。

修复源码已经发布到 `8d9893054d7fdbb3120e4457128e6ac0bca83bde`。证据检查点 `3769041c7f999a26a4559f6c98453d87b9dc0891` 已推送并回读确认；它只追加 138 个日志文件，源码和历史输入均未改变。

## 已完成的修复与验证

基线 `de6e6a4b` 已包含 S17 进程树、精确字节语法缓存与传输预算修复。该基线的 Linux 原范围复验原生结束：36 个 unittest 通过，340 个 pytest 节点全部结束，333 通过、7 失败，真实 JUnit，无 skip 或超时，source/HEAD 稳定。七个失败都是当前平台夹具问题。

此次修改 S14/S15/S18 的临时目录硬编码，S14 查找真实 powershell 或 pwsh，S26 对比真实 sys.platform；Windows 仍要求 win32。原生产 PowerShell 验证器、历史字节及成员变动控制没有被替换。Accepted ADR-0058 追加修复说明。共五个源码/ADR 文件，原 340 个选择器和节点 ID 均保持。

七个原失败节点的定向复验已经原生通过：36 unittest + 7 pytest，真实 JUnit 7 项、21 个阶段全部 passed，无 skip/xfail，source/HEAD 稳定。该早期定向运行绑定本地未发布提交 `7a2859a1`，发布源码 `8d989305` 的五个改动源码 blob 与它相同；不把本地提交 SHA 冒充远端 SHA。

## 本轮全量复验的实际状态

从发布源码 `8d989305` 建立干净检出后，在固定 HEAD 上运行原 340 项。环境是 Linux、Python 3.12.14、pytest 8.4.2、jsonschema 4.26.0、真实 PowerShell 7.6.6。36 unittest 已通过，原 340 项节点清单和原 Windows 尝试逐字节一致。

最后成功读取时间为 2026-10-07T10:13:22.533080Z：290/340 个节点完成，0 个 failed report，正在执行 S44 的 fresh-checkout 节点。原先超时的 S17 主回放节点从原生 start 到 finish 为 41.702775 秒，四个 S17 节点均通过。节点预算仍为 300 秒，未通过提高预算、更换 scope 或跳过节点取得进展。

随后控制连接断开，恢复读取明确返回 `409 Conflict, environment_offline: Environment is not connected`。当前未能读取本轮原生 summary、pytest process result、JUnit 或 source-after。不能断言后台进程仍在运行、已经结束或通过。该轮本地原生文件尚未上传，不把本检查点的人工观察当作它们的替代品。详细观察见 `session-observation.json`。

## 已推送的证据

| 目录（相对于 logs/08-05-real-skill-replay） | 结果 |
| --- | --- |
| observable-verification-20261006T164348Z-07aecb59 | 原 Windows 失败，S17 300 秒；保留原状 |
| observable-verification-20261007T072118Z-67900103 | 前置依赖和 Git 对象不完整，显式中断；无伪造终止结果 |
| observable-verification-20261007T072751Z-b8a02088 | 历史输入不完整，显式中断；无伪造终止结果 |
| continuation-preflight-20261007T073449Z | 真实 replay 原生 exit 0，保留完整输出 |
| observable-verification-20261007T073516Z-52daddd9 | 340 项完整失败结果：333 passed / 7 failed，真实 JUnit |
| continuation-prerequisites-20261007 | Python/PowerShell 实际版本、官方哈希及历史字节证明 |
| continuation-20261007/native-targeted | Python 环境重置后缺 pytest 的原生 blocked 结果 |
| continuation-20261007/native-targeted-2 | 七个修复节点的原生通过结果及真实 JUnit |
| continuation-20261007/native-full | 本地发布前试跑完成 46 节点后显式中断，exit 130；不是通过 |

保留原始失败、Q7/Q8、回执、计划及历史字节。原生输出没有为清除空白警告而修改。已有 archive-manifest 保留 raw/archive SHA-256；本续接目录新增的 gzip 在离线前均执行过解压等于原字节断言，并核对上传返回 Git blob SHA。它们的压缩文件身份列在 `compressed-evidence-index.json`；该索引明确不声称已记录 raw SHA-256。

`repair-note.md` 是修复时的早期检查点，其“下一步”描述按原样保留；后续已完成的定向验证和离线事实由这里追加。所有检查点均按各自时间解释。

## 恢复后的处理顺序

1. 先读取本地 `native-full-current` 目录，检查原生终止文件和进程存活情况。不要直接把遗留进度转换成通过，也不要在读取 source-after 前改变该检出的 HEAD。
2. 如果已有原生结束结果，交叉核对 340 个节点、1020 个阶段、native exit 0、无 skip/xfail、真实 JUnit 340 项且无 failure/error/skip、source-before/source-after 相同，且绑定源码为 `8d989305`。
3. 如果运行没有留下可核验的终止结果，保留本次文件与离线观察，在固定干净源码上新建输出目录重跑原 340 项。确认真实 Python 和 PowerShell 前置条件；不要覆盖现有目录。
4. 基于远端最新分支树追加结果，保留本检查点及已有 138 个日志文件，使用 expected SHA 更新分支；核对远端提交和所有证据字节。CLI 推送缺少写凭据，已使用连接的 GitHub Git-data API；不要认为读取仓库成功就表示具有 CLI 写认证。
5. 在真实本地 Windows 上执行同一复验。Linux 成功不能替代 Windows 成功。C3 仍 OPEN，Acceptance 仍阻塞；任何直接复验不授予 Trust Approval 或正式 Acceptance 权限。

Windows 复验命令（固定干净源码并具有真实依赖后）：

```powershell
py -3 -u -B scripts/sc/verify_skill_replay.py --expected-count 340
```

Linux 已用命令：

```text
PATH=/workspace/scratch/60fb44ef18f2/continuation-prerequisites/powershell-7.6.6:$PATH
/workspace/scratch/60fb44ef18f2/continuation-prerequisites/replay-python/bin/python -u -B scripts/sc/verify_skill_replay.py --expected-count 340 --output-dir logs/08-05-real-skill-replay/continuation-20261007/native-full-current
```

本地定位：原仓库 `/workspace/scratch/60fb44ef18f2/ji-mu-yun` 的最后已知 HEAD 是本地 `7a2859a1`；固定源码检出为 `/workspace/scratch/60fb44ef18f2/ji-mu-yun-fixed`，最后已知 HEAD 是 `8d989305`。执行服务离线后没有更新这些本地 HEAD，也不能重新确认工作区状态。远端证据提交由 API 创建，不能声称与这些本地 SHA 一致。

历史冻结文件 `execution-plans/2026-08-18-toolchain-workflow-repair/skill-input/prestart-40-output/skill-input-context.v1.json` 为 1731 字节，raw SHA-256 `4bfa9206a23122810ec7c41783ce8c6866d91917ab1633a795891a2937c596d9`，与 Git blob `6f20cab3ff2d01ecc515777551603429e3105a7c` 逐字节一致。此前换行归一化造成的状态误报通过私有精确路径 -text 属性处理，未改写历史字节；恢复时继续遵守此边界。

FastCtx 在该环境不可用，已记录并使用 rg/原生读取。没有启动子代理，也没有调用 VDD、Quick Dev、正式 Acceptance、live backend 或合并 main。authorizes=[]；C3=OPEN。
