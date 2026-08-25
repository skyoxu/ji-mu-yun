# Input Reconciliation — docs/know76.txt

## Summary

`know76.txt` 与上一版 PRD 的主张一致，并补充了 Chapter 6 风格的实施内核约束。新增要求已并入主 PRD 的 FR-10 至 FR-17、UJ-4、NFR-9 至 NFR-11、MVP 范围、SM-C3、开放问题和假设索引，并在 `addendum.md` 增加实现边界。

## Covered additions

- semantic preflight：complexity class、verification lane、context lookup、minimum RED scope、upgrade conditions。
- planned-only / observed-run / recovered-run / invalid-run 四态模型。
- recommendation-only 路由及其禁止动作、阻塞原因、可复用/失效 observation 字段。
- failure family、unexpected-green 处理和 deterministic fingerprint 止损。
- 按代码、测试、schema、validator、文档、requirements/acceptance/plan、fixture/target/command 变化影响选择性重放。
- fast-ship、standard、self-hosted Profile，且真实性底线不可降低。
- Quick Dev 与 Review、commit authority、业务仓规则和 Chapter 5 批处理职责边界。

## Remaining decisions

- comparator 和输出规范化规则。
- unexpected-green 的既有行为证明。
- deterministic fingerprint 的 stop-loss 阈值。
- recommendation-only 的顶层消费者及跨会话持久化。
- 语义变化下 observation 的部分复用矩阵。
