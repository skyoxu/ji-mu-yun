**结论：确认 1 个 P2，未发现 P0/P1。本次 mutex 修复的正常生产者场景成立，但“不得隐藏 tracked Knowledge 变化”的边界尚未完整满足，建议修复后再刷新原生证明。当前 r14 Q8 不覆盖这六个新文件字节。**

本轮仍为原独立 A 上下文，使用原 `review-delivery-workflow` 技能。已核实 HEAD 为 `2d68e7c1d7ec2afcd9c8ea9b145781d84b4a33f5`，清单六文件的当前大小、SHA256 和已有前代哈希全部匹配；结束前再次核对，候选未变。

**P2：基线中已跟踪的 mutex 被删除后，以 ignored 文件重建，会被错误地从 candidate 差异中排除。**

位置：[skill_input_candidate.py:64](/workspace/ji-mu-yun/scripts/python/skill_input_candidate.py:64)、[skill_input_candidate.py:107](/workspace/ji-mu-yun/scripts/python/skill_input_candidate.py:107)。

具体触发条件：

1. authority 的 `skill_input_baseline` 中已跟踪 `knowledge/indexes/.publication-acquire.lock`。
2. 当前候选将该路径从索引删除，但工作区留下或重建一个被忽略、单链接、普通的一字节 NUL 文件。
3. 相对 baseline 的 Git diff 会包含该 tracked 删除；`ls-files --others --ignored` 同时会包含当前工作区的这个路径。
4. 代码先合并两组路径，随后仅凭 `path in ignored_knowledge` 和物理形状合格执行 `continue`，没有保留“该路径也来自 tracked Git 差异”的信息。

因此，真实 tracked 删除不会进入返回的 `changes`、`changed_paths` 和 candidate hash。[skill_input_v2.py:114](/workspace/ji-mu-yun/scripts/python/skill_input_v2.py:114) 随后把该列表交给 [knowledge_gate_projection.py:19](/workspace/ji-mu-yun/scripts/python/knowledge_gate_projection.py:19)，该删除便不能触发原本要求的 `review-required`。这违反本次 ADR/doc 明确保留 tracked changes 的边界。

现有 `test_tracked_mutex_change_remains_candidate_authority` 只覆盖“路径仍在索引中、内容改变”的情况，没有覆盖“baseline 已跟踪、当前索引删除、ignored 工作区同路径重建”的交叉情况。上述结论来自源码和真实门禁调用链的静态追踪，本轮没有执行复现测试；当前固定仓库的该 mutex 本身未被跟踪，未声称现场已经发生此问题。

**最小修正方向：**保留独立的 baseline Git diff 路径集合，仅当 mutex 不属于该 tracked 差异集合时允许 metadata 排除；新增上述删除后重建的负例，确保路径保留且 `prepare` 仍要求 review。无需扩大为通用锁文件分类框架。

**其余已确认事项**

- [publisher 的 `_acquisition_guard`](/workspace/ji-mu-yun/scripts/python/publish_knowledge_catalog.py:361) 使用 `os.open(..., O_CREAT | O_RDWR)`，在空文件写入 NUL，释放 OS 锁后仅关闭 descriptor，保留 inode。默认创建权限受 umask 影响；现场文件确为一字节 NUL、单链接、模式 `0700`。不因 execute 位拒绝该固定形状，与真实生产者一致。
- 分类器限制精确路径和当前 ignored/untracked 身份；普通文件、大小、链接数、descriptor 与路径身份及读取前后时间戳均检查。邻接路径、不同内容、hardlink、symlink/reparse、目录/FIFO 和读取期间替换有对应拒绝路径或测试。
- observer 没有获取、释放、截断或删除 publisher mutex。
- policy 仅新增三条具体源码、测试、文档路径，原 checks、cross-domain 路由不变，policyRevision 重算匹配。ADR 已由既有 `docs/adr/` 路由覆盖，没有新增目录权利。

**原始证据核验**

- 因果 RED 为 **4 failed、13 passed**：生产者正常文件误判、目录和 FIFO 未拒绝，以及缺少新 helper。最后一项不计作业务行为 RED。
- 初次兼容运行 **113 passed、3 failed**；原件明确为两项 model 配置失败和一项 `skill_input_gate` 导入失败，均保留。
- 修正测试环境后的原始日志为 **116 passed**，包括当前 20 个新增定向用例；当前测试文件与冻结测试副本一致。
- 路由因果日志为 **1 failed、1 passed**；最终路由日志实际为 **11 passed**，采用原始结果而非清单中的旧计数。

本轮只读检查六文件差异、生产者、直接 Skill-input 门禁、文档和原始日志；未运行测试或项目代码、未修改文件、未读取另一臂报告，也未重启此前 387 载荷的全量审核。没有 Windows 实测或通用并发安全证明的新增声明。

**修复上述 P2 后，应对受影响原生证明重新冻结和刷新。** 本报告不授予 Acceptance authority，不选择输入基线，也不豁免其他真实 Knowledge 变化的 review-required。
