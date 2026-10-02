---
ADR-ID: ADR-0005
title: 质量门禁（Windows-only）- Godot + C# 统一入口
status: Accepted
decision-time: '2025-12-16'
deciders: [架构团队, 开发团队]
archRefs: [CH07, CH09]
verification:
  - path: scripts/ci/quality_gate.ps1
    assert: Single entrypoint runs hard gates and writes artifacts under logs/**
  - path: scripts/python/quality_gates.py
    assert: CI-aligned orchestration (dotnet + selfcheck + encoding; optional gdunit/smoke)
  - path: scripts/ci/check_perf_budget.ps1
    assert: Parses [PERF] p95_ms from headless.log and enforces threshold when enabled
  - path: scripts/sc/acceptance_check.py
    assert: Task-scoped deterministic acceptance gate supports security-profile aware controls
  - path: .github/workflows/windows-quality-gate.yml
    assert: Writes `SecurityProfile: <host-safe|strict>` to Step Summary
impact-scope:
  - Game.Core/
  - Game.Godot/
  - Tests.Godot/
  - scripts/
  - .github/workflows/
tech-tags: [quality-gates, windows, godot, csharp, dotnet, xunit, gdunit4, perf, encoding, security-profile]
depends-on: [ADR-0011, ADR-0018, ADR-0019, ADR-0031, ADR-0003, ADR-0015, ADR-0025, ADR-0020]
depended-by: [ADR-0008]
supersedes: []
---

# ADR-0005: 质量门禁（Godot + C#）

## Context

模板必须做到“复制即可跑 CI”：一旦门禁分散在多个脚本和工作流里，就会出现“本地通过、CI 失败”或“同一问题重复审查”。
当前项目采用 Godot + C#，门禁应默认对齐模板可复制场景，并允许按项目阶段切换强度。

## Decision

### 1) 单入口优先

- CI 与本地统一入口优先使用 Python 脚本编排（Windows 兼容）。
- 所有门禁必须写入 `logs/**` 工件，保证可追溯与可审计。

### 2) 最小硬门禁集合（默认）

- dotnet：编译与单元测试（xUnit）。
- Godot：headless self-check（启动 + 关键 Autoload 兜底）。
- 编码：UTF-8 / 无 BOM / 无语义级乱码（文档与工作流关键目录）。

### 3) 可选硬门禁（按需启用）

- GdUnit4 小集（安全/关键装配）。
- Headless smoke（严格模式 marker/DB）。
- 性能 P95 门禁（阈值口径见 ADR-0015）。

### 4) 软门禁（不阻断，但必须产出工件）

- 契约引用对齐：`scripts/python/validate_contracts.py`。
- 其他质量/可观测补充扫描。

### 5) Security Profile 驱动门禁强度

- 统一配置：`SECURITY_PROFILE=host-safe|strict`，默认 `host-safe`。
- `host-safe`（模板默认）：
  - `security-path-gate=require`
  - `security-sql-gate=require`
  - `security-audit-schema-gate=warn`
  - `ui-event-json-guards=skip`
  - `ui-event-source-verify=skip`
  - `security-audit-evidence=skip`
- `strict`（项目可选）：
  - 上述安全门禁全部 `require`。
- 安全 profile 语义来源见 ADR-0031；安全边界来源见 ADR-0019。

### 6) 工件（统一落盘）

- 单元测试：`logs/unit/<YYYY-MM-DD>/`
- 引擎/场景：`logs/e2e/<YYYY-MM-DD>/`
- CI 汇总与扫描：`logs/ci/<YYYY-MM-DD>/`

## Verification

本地最小验收（Windows）：

```powershell
pwsh -File scripts/ci/quality_gate.ps1 -GodotBin "$env:GODOT_BIN"
```

CI 侧应能在 `logs/**` 中找到对应摘要与日志文件；失败时可直接定位到具体 gate 输出。

## Consequences

- 正向：门禁入口统一、Windows 兼容、失败可定位、产物可回溯。
- 代价：需要保持“单入口优先”的纪律，避免把门禁逻辑散落到示例脚本或临时 workflow 里。

## Addendum (2026-02 Security profile + 5 scripts)

- `scripts/sc/acceptance_check.py` remains the blocking decision source for task delivery.
- `scripts/sc/llm_review.py`, `scripts/sc/llm_extract_task_obligations.py`, `scripts/sc/llm_check_subtasks_coverage.py`, and `scripts/sc/llm_semantic_gate_all.py` are advisory/diagnostic by default.
- CI must expose one explicit line in Step Summary: `SecurityProfile: <host-safe|strict>`.
- Default profile stays `host-safe`; `strict` is opt-in per project phase.

## Addendum (2026-10 CI regression consolidation)

- The Windows quality workflow executes the complete `Game.sln` test suite once
  with coverage and hang diagnostics, including all Runner and Phase fixtures.
- Filtered Runner/Phase regressions must not repeat serially before that same
  covered suite. The independent Phase entry workflow remains a quick focused
  signal and does not replace the complete quality gate.
- Test failures remain blocking. Test coverage, profiles, required check names,
  and production execution timeouts remain unchanged.
- Superseded pull-request quality runs share a concurrency group and are
  cancelled when a newer commit arrives. Main and manual runs are not actively
  cancelled; cancelled runs retain their GitHub history.
