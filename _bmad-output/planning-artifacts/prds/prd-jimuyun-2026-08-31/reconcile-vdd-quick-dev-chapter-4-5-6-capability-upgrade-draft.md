# 输入对账：Chapter 4/5/6 能力补强草案与 know103 修复意见

## 结论

草案中的产品范围、职责边界、强制真实性约束、能力分母、非目标、成功证据和待决问题已进入 `prd.md` 或 `addendum.md`。`docs/know103.txt` 指出的初版对账错误和 8 项语义遗漏已修复：命令、JSON、V0–V7/Q0–Q8、wrapper 细节及其承重规则均已逐项补入 `addendum.md`，并保留其作为 Spec/Architecture 输入。

## 映射摘要

- 草案第 3 至 5 节的 VDD 职责、语义稳定化、exact cover、slice partition 和 write-set feasibility：PRD FR-1 至 FR-8，补充 B。
- 草案第 6、16 节的 recommendation、run state、RED/GREEN/REFACTOR、failure taxonomy、replay、slice-ready 与 terminal：PRD FR-9 至 FR-18，补充 C 至 E。
- 草案第 7 节反模式和第 10、18 节成功证据：PRD 成功指标、跨切约束、风险与缓解，补充 G。
- 草案第 11、12、18.5 节的 BMAD 产物边界、治理排除和最终责任链：PRD 非目标、MVP 范围、跨切约束，补充 A、F、G。
- 草案第 13 节十项待决问题：PRD Open Questions 1 至 10，均保留 owner 和重新决策条件。
- 草案第 15.5、15.6、15.7、15.10 节的 preflight 字段、slice contract、独立 semantic align 和 agent-context projection：补充 B.1-B.3、C。
- 草案第 16.12 节的 production owner 变化规则：补充 D，明确 failure intent 语义变化必须回到 RED。
- 草案第 18.5 节的外部独立语义验收责任链：PRD §8 与补充 A、E。

## 有意下沉到补充的内容

具体命令形式、JSON 字段示例、阶段 V0-V7/Q0-Q8、`codex exec` wrapper 细节和迁移投影放入 `addendum.md`。这些是后续 Spec/Architecture 的设计输入，不改变 PRD 的功能范围；对账只在文件确实包含对应内容后声明完成。
