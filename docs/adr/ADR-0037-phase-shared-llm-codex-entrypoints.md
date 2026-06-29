# ADR-0037: Shared LLM And Codex Execution Entrypoints

- Status: Accepted
- Date: 2026-06-28

## Context

Phase routes use LLM and Codex execution for chat, structured decisions, prototype planning, repair planning, asset judgement, and file-changing workflows. Direct route-specific subprocess or provider calls would scatter model, sandbox, billing, credential, and retry behavior across the codebase.

## Decision

All Phase LLM/Codex execution must go through shared entrypoints.

- C# read-only or structured LLM calls use `ILlmRouteEngine` / `LlmRouteEngine`.
- C# executable Codex workflow commands use `CodexHostedProcessCommandFactory`.
- Python LLM/Codex scripts use `scripts/sc/_llm_backend.py::run_llm_exec` or thin wrappers.
- Prompt transport for executable Codex workflows is stdin-first.
- If a new route needs unsupported model, reasoning, sandbox, output, billing, credential, or retry behavior, extend the shared entrypoint and tests first.

## Consequences

- Route behavior is easier to audit and test.
- Credential and billing handling stays centralized.
- New provider or Codex options require shared-entrypoint work before route work.
- Caller-specific routes still need their own tests in addition to shared-entrypoint tests.

## References

- `docs/architecture/phase-service/llm-codex-execution.md`
- `PhaseA.Platform/Llm/LlmRouteEngine.cs`
- `PhaseA.Platform/Runs/CodexHostedProcessCommandFactory.cs`
- `scripts/sc/_llm_backend.py`
