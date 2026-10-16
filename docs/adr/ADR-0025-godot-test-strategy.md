# ADR-0025: Godot 测试策略（xUnit + GdUnit4）

- Status: Accepted
- Context: 本仓库为 Godot 4.5 + C#/.NET 8（Windows-only）模板，需要在不启动引擎的前提下完成快速 TDD（领域层），并在 headless 下验证关键场景/信号链路（引擎层），同时将测试产物统一归档到 `logs/**` 便于取证与排障。
- Decision:
  - 领域层（不依赖引擎）：使用 xUnit + FluentAssertions + NSubstitute；覆盖率使用 coverlet，门禁口径为 lines ≥ 90%、branches ≥ 85%（阈值可通过环境变量覆盖，具体以测试框架文档为准）。
  - 引擎层（依赖引擎）：使用 GdUnit4（headless）覆盖关键节点可见性、Signals 连通、资源路径与安全烟测小集。
  - 门禁编排：PowerShell 入口 `scripts/ci/quality_gate.ps1` 与 Python 入口 `scripts/python/quality_gates.py` 保持一致；CI 优先执行 unit，再执行引擎自检/场景小集。
  - 工件归档：统一落盘 `logs/unit/<YYYY-MM-DD>/`、`logs/e2e/<YYYY-MM-DD>/`、`logs/ci/<YYYY-MM-DD>/`（目录口径见 `docs/testing-framework.md`）。
- Consequences:
  - 领域逻辑必须保持纯 C#（Core 不引用 Godot 类型），否则会破坏毫秒级红绿灯循环。
  - 场景测试只覆盖关键路径，避免把所有逻辑塞进引擎测试导致维护成本与波动上升。
  - 所有新增可执行门禁必须同步产出可下载工件（日志/摘要/JUnit/XML），否则难以定位 CI 偶发失败。
- References:
  - `docs/testing-framework.md`
  - `docs/migration/Phase-10-Unit-Tests.md`
  - `docs/migration/Phase-11-Scene-Integration-Tests.md`
  - `docs/migration/Phase-12-Headless-Smoke-Tests.md`
  - `scripts/ci/quality_gate.ps1`
  - `scripts/python/quality_gates.py`


## Fixture addendum (2026-10 actual engine observations)

Signal fixtures use shared callback observations and assert the actual event
count and payload. Reopening a database creates a new node and explicitly binds
repository readback to that node; the closed source cannot satisfy the check.
WAL backup fixtures retain the user:// destination, copy real database/WAL
bytes, and query the destination connection. They close owned connections and
restore the journal override. UTF-8 roundtrip assertions compare the complete
stored username. No missing-result tolerance, disabled cases, or lowered
assertions establish fixture success.

A GdUnit result belongs to the current invocation only when the report was
written after that invocation started. Missing, empty or failed reports
cannot satisfy success even when the process exits zero. A process timeout
remains exit 124; compatibility normalization only uses complete current
results and retains the explicit strict-exit option.
