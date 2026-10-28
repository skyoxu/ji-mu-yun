**原 tracked 删除 P2 可以关闭；本次受影响复核未确认新的 P0/P1/P2。** 修正保留了相对授权基线的 tracked 差异，既覆盖 staged 删除，也覆盖已提交删除后保留 ignored mutex 的情况。支持冻结该修复并刷新受影响的原生证明；不代表 Acceptance 通过或授权。

候选仍为 `HEAD 2d68e7c1d7ec2afcd9c8ea9b145781d84b4a33f5` 加 [r2 清单](/workspace/ji-mu-yun/logs/package-b-rebuild-20261028/PUBLICATION-MUTEX-REPAIR-MANIFEST-r2.json)中的六个文件。六项大小及 SHA256 均核对一致，收尾检查未漂移。

**问题关闭依据**

[skill_input_candidate.py:64](/workspace/ji-mu-yun/scripts/python/skill_input_candidate.py:64)现在独立保存 `tracked_changes`，再复制并合并 untracked/ignored 集合。[第 108 行](/workspace/ji-mu-yun/scripts/python/skill_input_candidate.py:108)仅在精确 mutex 路径**不属于基线 tracked 差异**时允许元数据豁免。

因此，原触发中的删除路径即使同时属于 ignored/untracked，也会保留在候选中。其 `knowledge/` 路径随后仍触发既有 `review-required`；prepare 和 generation 重读使用同一修正后的 observer。正常、从未构成基线 tracked 差异的发布者 mutex 仍可按原条件识别，文件形状与稳定性检查未改变。

新增[参数化回归测试](/workspace/ji-mu-yun/scripts/python/tests/test_skill_input_publication_mutex.py:90)分别建立 staged 和 committed 删除，明确断言：

- mutex 仍在 `changed_paths` 中；
- `v2.prepare()` 因 `review-required` 拒绝。

[因果 RED 原件](/workspace/ji-mu-yun/logs/package-b-rebuild-20261028/publication-mutex-tracked-delete-causal-red.log)记录 `2 failed, 20 deselected`，两例均在路径遗漏断言处失败，准确复现此前 P2，不是环境或 helper 缺失失败。

[修复后兼容性原件](/workspace/ji-mu-yun/logs/package-b-rebuild-20261028/publication-mutex-r2-frozen-green-and-compatibility.log)记录 `118 passed`。新增测试仅增加上述两例，原有测试内容未改写。此前 `113 passed / 3 prerequisite failures`、`116 passed` 和路由 `11 passed` 原件的哈希与上一轮一致，未被覆盖。

**覆盖记录**

| 文件 | 本轮处置 |
|---|---|
| `scripts/python/skill_input_candidate.py` | reviewed：独立差异集合、新增豁免条件及后续候选/gate 关系 |
| `scripts/python/tests/test_skill_input_publication_mutex.py` | reviewed：两种删除回归及与原冻结测试的完整差异 |
| `docs/workflows/skill-input-v2.md` | reviewed：哈希未变，复用上一轮合同核对 |
| `docs/adr/ADR-0060-skill-input-selection-generation-and-retention.md` | reviewed：哈希未变，复用上一轮审核 |
| `…/policies/toolchain-code-review.v1.json` | reviewed：哈希未变，精确路由和权限结论保持 |
| `…/tests/test_toolchain_domain.py` | reviewed：哈希未变，原正负断言保持 |

共 **6/6 reviewed，0 partial，0 pending**；其中两项重新审查变化，四项在字节未变后复用既有审核。直接上下文中的 publisher、路径约束、Skill-input 消费者和 Knowledge gate 均确认未改变。本轮未扩大为通用并发或框架审核。

本次只进行了文件阅读、哈希及只读 Git 检查，没有执行测试、项目代码或工作流，也没有写文件或改变 mutex 状态。绿色摘要日志支持其记录的测试结果，但不等同于绑定新源码的完整原生证明。**r14 Q8 仍是历史证据，不能证明六个修复后源码字节；后续需完成受影响原生证明刷新。** 既有 Acceptance 输入、权限及 Knowledge 审核要求不因本报告改变。
