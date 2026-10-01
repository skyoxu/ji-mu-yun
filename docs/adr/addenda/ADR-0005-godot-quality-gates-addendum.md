---
adr: ADR-0005
title: Addendum — Quality Gates for Godot + C#
date: 2025-11-08
status: Active
scope: Windows-only CI, Godot 4.5 (.NET)
---

# ADR-0005 补充：Godot+C# 质量门禁对齐

## Context

模板从旧的 Web/LegacyDesktopShell 工具链迁移到 Godot+C# 后，质量门禁需要以 **.NET 单测 + Godot headless/场景测试** 为主，同时保持“单入口编排、工件可追溯、Windows 兼容”。

## Decisions

- 单元测试（领域层）：`dotnet test` + coverlet（XPlat Code Coverage）；覆盖率门禁口径为 lines ≥ 90%、branches ≥ 85%（详见 `docs/testing-framework.md`）。
- 场景测试（引擎层）：GdUnit4 headless；非 0 退出码视为失败；JUnit/XML 与摘要写入 `logs/e2e/**`。
- 单入口（Windows）：PowerShell 入口 `scripts/ci/quality_gate.ps1`，Python 入口 `scripts/python/quality_gates.py`；两者保持同一门禁集合。
- 工件：门禁/测试输出统一落盘 `logs/**`（目录口径见 `docs/testing-framework.md`）。

## Commands（示例）

- `dotnet test --collect:\"XPlat Code Coverage\"`
- `py -3 scripts/python/run_gdunit.py --godot-bin \"%GODOT_BIN%\" --project Tests.Godot --add tests/Security/Hard`
- `pwsh -File scripts/ci/quality_gate.ps1 -GodotBin \"%GODOT_BIN%\"`

## Verification

- CI 中可看到：覆盖率摘要 + GdUnit4 pass/fail + 对应 `logs/**` 工件。

## CI process-budget implementation clarification (2026-09-30)

The existing Windows workflow declares `CI_DOTNET_STAGE_TIMEOUT_MS=4200000`.
The Python driver and .NET runner must consume that total restore/test budget,
with a bounded wrapper margin for cleanup and terminal-summary persistence.
Without an override, the runner retains its original 900-second restore and
test bounds. Invalid non-positive or non-integer overrides fail closed.

The Godot wrapper budget must cover its existing internal attempt bounds:
optional build (600 seconds), first run (300 seconds), prewarm (120 seconds),
retry (300 seconds), and a bounded cleanup/summary margin. This changes neither
the gate set nor any acceptance or coverage threshold.

`scripts/python/ci_process.py` persists subprocess output under `logs/ci/**`
while the command runs. On timeout it terminates the process tree before the
next gate starts and retains exit code 124. Windows CI runs real subprocess
cleanup regressions and archives `logs/unit/**` with the CI diagnostic package.
Timeouts and non-zero test exits remain hard failures; incomplete tests cannot
be reported as passed.


## CI build reuse and bounded diagnosis (2026-10-01)

Windows Quality Gate restores and builds Debug once before its regression and
full-suite stages. Both stages reuse that same validated configuration; standalone
Python callers still restore/build by default. Coverage and every test remain enabled.
The Godot runtime self-check and its existing retry remain hard gates on a successful
.NET stage, but do not repeat the already completed solution build.

The workflow opts into fail-fast after a hard .NET failure. Unexecuted downstream
gates are recorded as `not_run`, never passed; the whole pipeline remains failed.
VSTest uses a 10-minute per-test hang diagnostic with dump type `none`: a hanging
host is terminated, its sequence/TRX is archived, and the run fails. This bound is
a diagnostic ceiling, not a relaxed product deadline or a replacement for tests.

Subprocess wrappers print bounded heartbeats containing only elapsed time and
output byte counts. Per-process timing JSON and all project TRX/hang sequences
remain under `logs/**`; command arguments and raw child output are not streamed
by the heartbeat. Existing total stage budgets remain unchanged.


### 2026-10-01: preserve source fixtures without CI tool payloads

Run 36849950332 completed all 1846 PhaseA and 44 Core tests. Its .NET stage took 2821.756 seconds; the three GDD source-seeding test classes accounted for 2563.1 summed test seconds. Those fixtures repeatedly seeded the CI checkout, including generated Godot downloads and caches. Reuse a source projection per test class, retaining real source/template bytes and custom mutable test repositories while excluding generated root tool/cache payloads. Keep conservative two-collection scheduling and the full covered suite.

Browser fixture subprocesses must drain both pipes while running, use asynchronous waits, and terminate/drain timed-out child trees. A 30-second fixture process budget covers Node startup; it does not change product deadlines. S15 teardown uses bounded asynchronous deletion after child-server exit and does not clear other tests' SQLite pools. Persistent cleanup locks and subprocess timeouts remain failures.


### 2026-10-01: build the separate Godot runtime project directly

`Game.sln` contains the pure .NET platform/core projects, while the Godot runtime lives in `GodotGame.csproj`. Reusing the former does not build the latter. Windows Quality Gate explicitly restores/builds the Godot project in Debug before prewarm and self-check, then reuses that output. This preserves the runtime compilation gate without invoking the Godot editor's previously timed-out 600-second `--build-solutions` path. The covered .NET suite and runtime self-check remain required.
