**结论：此前 tracked 删除被隐藏的 P2 可以关闭。本轮直接相关新增 P0/P1/P2 均为 0。支持在此冻结版本上刷新受影响原生证明；不授予 Acceptance authority。**

已确认 HEAD 仍为 `2d68e7c1d7ec2afcd9c8ea9b145781d84b4a33f5`，r2 清单六文件的大小和 SHA256 全部匹配。相对上一轮，仅 classifier 源码和新增测试文件变化，四个文档、policy、路由测试文件保持已审字节。

关闭依据：

- [skill_input_candidate.py:64](/workspace/ji-mu-yun/scripts/python/skill_input_candidate.py:64) 在合并未跟踪及 ignored 路径前，独立保留 `tracked_changes`；`changed` 使用副本，不会破坏该集合。
- [skill_input_candidate.py:108](/workspace/ji-mu-yun/scripts/python/skill_input_candidate.py:108) 仅在精确 mutex 路径**不属于 baseline Git 差异**时允许 metadata 排除。因此，暂存删除和已提交删除后重建 ignored NUL 文件，都会保留在 `changed_paths`，继续触发既有 `review-required`。
- [新增测试:90](/workspace/ji-mu-yun/scripts/python/tests/test_skill_input_publication_mutex.py:90) 使用真实隔离 Git fixture 覆盖这两个情形，同时断言路径保留和 `prepare` 拒绝。原始因果日志中两项均因路径被遗漏而失败，准确复现了原问题。
- 对原本未跟踪、被忽略、形状合法的生产者 mutex，新增条件不会改变识别结果；原有精确路径、文件身份、内容、链接和稳定性检查未放宽。

[因果 RED](/workspace/ji-mu-yun/logs/package-b-rebuild-20261028/publication-mutex-tracked-delete-causal-red.log) 为 **2 failed、20 deselected**；[当前组合日志](/workspace/ji-mu-yun/logs/package-b-rebuild-20261028/publication-mutex-r2-frozen-green-and-compatibility.log) 为 **118 passed**。这些日志支持修复闭合，本轮没有自行运行测试。

此次仅复核原 P2 及最小修改的直接回归，没有写文件、运行项目代码、读取另一臂报告或扩展全项目审核。**r14 Q8 仍是历史证明，尚未覆盖当前六文件字节；后续须刷新，不能重贴为当前成功。** Acceptance 输入、authority 和其他真实 Knowledge 变化的 review-required 均保持原边界。
