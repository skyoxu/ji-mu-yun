本次定向复核确认 **1 项 P2，未确认 P0/P1**。实际发布者 mutex 的误阻塞已得到修正，但“所有 tracked 变化仍保留审核触发”的主张尚不能关闭：从 Git 跟踪中删除该路径、同时保留被忽略的 mutex 文件时，新分类会遗漏基线中的删除变化。

审核候选为 `HEAD 2d68e7c1d7ec2afcd9c8ea9b145781d84b4a33f5` 加 [PUBLICATION-MUTEX-REPAIR-MANIFEST.json](/workspace/ji-mu-yun/logs/package-b-rebuild-20261028/PUBLICATION-MUTEX-REPAIR-MANIFEST.json) 中六个文件。六项大小、SHA256、五项前驱身份及新增测试身份均已独立核对；收尾复查未发现漂移。此次沿用原 B 上下文及 `review-delivery-workflow-b`，没有读取另一臂材料。

**P2：mutex 豁免会吞掉相对授权基线的 tracked 删除**

位置：[skill_input_candidate.py:64](/workspace/ji-mu-yun/scripts/python/skill_input_candidate.py:64)、[skill_input_candidate.py:107](/workspace/ji-mu-yun/scripts/python/skill_input_candidate.py:107)。

具体触发：

1. 授权 `skill_input_baseline` 中跟踪 `knowledge/indexes/.publication-acquire.lock`。现有 [tracked 测试](/workspace/ji-mu-yun/scripts/python/tests/test_skill_input_publication_mutex.py:74)已经建立这种支持场景。
2. 将该路径从 index 移除，但保留物理文件；该路径受忽略规则覆盖，物理文件成为单链接、单 NUL 字节普通文件。
3. 相对基线的 `git diff` 包含该路径的删除；`git ls-files --others --ignored` 同时把保留的文件列为 ignored/untracked。
4. 当前实现合并两个集合后，仅因路径出现在 `ignored_knowledge` 且形状合格便 `continue`，丢失原有删除变化。

影响：该路径不再进入 `changed_paths` 和 candidate hash。[Knowledge gate](/workspace/ji-mu-yun/scripts/python/knowledge_gate_projection.py:19)据此无法识别此次 Knowledge 自身变化；没有其他阻塞条件时，`prepare` 可进入 `ready` 路径。后续 generation 验证重复使用同一 observer，不能补回遗漏。

这与当前文档“相对授权基线观察 tracked changes、deletions，并保留审核触发”的合同冲突。现有保护只覆盖**仍在 index 中的 tracked 内容修改**；单链接、字节、路径和稳定性检查不解决 Git 来源集合重叠。

最小修正方向：保留独立的基线 tracked 差异集合；只有不属于该集合的 ignored/untracked 精确 mutex 才能豁免。增加“基线已跟踪 → index 删除但保留 ignored NUL 文件”的回归用例，确认路径仍进入候选并触发 `review-required`。这是静态调用链确认的可达缺陷，本次未创建仓库夹具或运行复现。

**其余受影响主张**

- 发布者 [`_acquisition_guard()`](/workspace/ji-mu-yun/scripts/python/publish_knowledge_catalog.py:361)确实使用 `os.open(O_CREAT | O_RDWR)`，在空文件中写入一个 NUL，并在解锁后保留文件。当前实际文件为普通文件、链接数 1、大小 1、字节 `00`、模式 `0700`，且 Git 判定为 ignored/untracked。不能将 executable 位作为拒绝该真实产物的依据。
- 新 observer 不获取或释放发布锁，也不修改模式、截断或删除文件。普通异常内容、邻近路径、未忽略精确路径、当前仍被跟踪的修改、硬链接、静态 symlink/reparse 路径、目录/FIFO，以及测试中的读取期间 inode 替换，均有直接拒绝或审核路径。
- 新增三条策略路由都是精确文件路径；没有增加目录级匹配、删除检查或授予权限。策略修订哈希可重算，既有正负断言未削弱。模式正例与真实发布者的 umask 行为一致。

**原始证据核对**

| 原始日志 | 实际结果及解释 |
|---|---|
| [publication-mutex-causal-red.log](/workspace/ji-mu-yun/logs/package-b-rebuild-20261028/publication-mutex-causal-red.log) | `4 failed, 13 passed`：真实发布者正例、目录/FIFO 拒绝失败，以及 helper 缺失；最后一项不是业务 RED |
| [publication-mutex-frozen-green-and-compatibility.log](/workspace/ji-mu-yun/logs/package-b-rebuild-20261028/publication-mutex-frozen-green-and-compatibility.log) | `3 failed, 113 passed`：两项模型配置前置失败、一项模块导入失败，原记录保留 |
| [publication-mutex-frozen-compatible-environment.log](/workspace/ji-mu-yun/logs/package-b-rebuild-20261028/publication-mutex-frozen-compatible-environment.log) | `116 passed`；当前测试文件与冻结副本字节一致 |
| [publication-mutex-route-causal-red.log](/workspace/ji-mu-yun/logs/package-b-rebuild-20261028/publication-mutex-route-causal-red.log) | `1 failed, 1 passed, 9 deselected`，失败原因是旧策略缺少路径覆盖 |
| [publication-mutex-route-final-green.log](/workspace/ji-mu-yun/logs/package-b-rebuild-20261028/publication-mutex-route-final-green.log) | **`11 passed`，不是清单文字中的 10** |

这些绿色日志记录了执行结果，但摘要型日志本身没有逐用例事件及完整命令绑定，不能把它们等同于已刷新且绑定六个新源码字节的原生 Q8。r14 Q8 按明确范围仍是历史证据；本次没有将其重新标记为当前成功。

**逐文件覆盖**

| 文件 | 处置与检查范围 |
|---|---|
| `scripts/python/skill_input_candidate.py` | reviewed：完整新逻辑、前驱差异、Git 集合合并、文件观察及真实调用链 |
| `scripts/python/tests/test_skill_input_publication_mutex.py` | reviewed：全部新增测试、参数化边界、真实发布者正例、冻结副本 |
| `docs/workflows/skill-input-v2.md` | reviewed：新增条款及相邻基线、删除观察和 gate 合同 |
| `docs/adr/ADR-0060-skill-input-selection-generation-and-retention.md` | reviewed：完整相关决定及新增澄清 |
| `…/policies/toolchain-code-review.v1.json` | reviewed：三条新增路由、匹配规则、检查集合及修订哈希 |
| `…/tests/test_toolchain_domain.py` | reviewed：三条新增路径及既有正负断言消费关系 |

变更枚举为 **6/6 reviewed，0 partial，0 pending**。直接上下文包括 publisher、路径约束、Skill-input prepare/重读/generation 验证、Knowledge gate、live consumer gate、既有测试夹具及策略匹配器；未扩展为全框架或任意并发安全证明。

本次仅作只读文件、哈希及 Git 检查，没有写文件、运行测试或项目代码、启动工作流、改变锁状态或创建 worktree。没有 Windows 实测结论，也没有授予 Acceptance 权限。

建议先修正上述 tracked 删除遗漏，再冻结源码并刷新受影响原生证明。当前 mutex 正常场景修复可保留，但尚不支持无条件关闭本轮修复并以 r14 证明继续交接。
