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
- Repository workflow model selection uses the versioned policy and typed
  decision envelope under `scripts/sc/`. Consumers may classify or project a
  route, but only the shared Python launcher may invoke `run_llm_exec`.
- Workflow model decisions start in `observe_only`. They cannot replace the
  model of an already-running Codex session. Active routing, when separately
  enabled by policy after capability and shadow evidence, starts an explicit
  child process with a full model ID, reasoning effort, and sandbox.
- VDD, Quick Dev, and Refactor Acceptance have independent policy-owned
  enablement controls. The execution boundary reloads the canonical policy;
  caller-supplied policy objects or capability dictionaries cannot authorize a
  child launch.
- Quick Dev owns four-class task classification. VDD projects its existing
  profile. Refactor Acceptance remains deterministic except for closed typed
  recovery triggers. Bootstrap Review retains its independent profile, role,
  access-proof, and launch authority.
- Automatic provider/model fallback is forbidden. Luna and Sol/max remain
  disabled until exact-surface capability and representative task predicates
  pass. Capability activation uses policy-bound path/hash references to the
  controlled producer receipt, successful process result, and representative
  shadow execution receipts; shadow summaries alone carry no activation
  authority.

## Consequences

- Route behavior is easier to audit and test.
- Credential and billing handling stays centralized.
- New provider or Codex options require shared-entrypoint work before route work.
- Caller-specific routes still need their own tests in addition to shared-entrypoint tests.
- Model routing becomes inspectable without changing the root session model or
  giving Skill adapters provider-scheduling authority.

## References

- `docs/architecture/phase-service/llm-codex-execution.md`
- `PhaseA.Platform/Llm/LlmRouteEngine.cs`
- `PhaseA.Platform/Runs/CodexHostedProcessCommandFactory.cs`
- `scripts/sc/_llm_backend.py`
- `scripts/sc/workflow_model_routing.py`
- `scripts/sc/config/workflow_model_routes.v1.json`
