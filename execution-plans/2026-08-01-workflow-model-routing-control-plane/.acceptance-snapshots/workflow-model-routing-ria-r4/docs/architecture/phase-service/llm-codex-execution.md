# LLM And Codex Execution Architecture

## Intent

Phase routes use LLM and Codex execution for chat, planning, prototype route decisions, repair planning, asset judgement, and file-changing workflow runs. The architecture keeps all provider and Codex invocation behavior behind shared entrypoints so routes do not construct ad hoc subprocesses or provider calls.

## Boundary

In scope:

- Read-only structured LLM calls through `ILlmRouteEngine` and `LlmRouteEngine`.
- Executable Codex workflow command construction through `CodexHostedProcessCommandFactory`.
- Python script LLM/Codex calls through `scripts/sc/_llm_backend.py::run_llm_exec` or thin wrappers.
- Repository workflow model classification and child-route decisions through
  `scripts/sc/workflow_model_routing.py` and its versioned policy.
- Account LLM binding, usage recording, stop-loss, cost summaries, audit readback, and admin aggregate views.

Out of scope:

- Direct route-specific `codex exec` command construction.
- Provider-specific calls from arbitrary services.
- Platform dependency on external gateway internal database tables.
- Raw prompt or provider response exposure as default browser/API readback.
- Replacement of the model in an already-running Codex session.

## Key Decisions

- Prompt transport is stdin-first for executable Codex workflows.
- JSON-only/read-only decisions stay read-only and are parsed through route engines or shared script backends.
- File-changing workflows must stay on explicit executable routes with workspace-write semantics and acceptance/smoke validation.
- Account/user binding is manual in Phase B; API-driven provisioning is deferred.
- LLM cost summaries in platform metadata are readback/audit copies, not billing authority.
- Workflow consumers emit typed, hash-bound, non-authorizing route decisions.
  Classification is separate from execution; only the shared launcher invokes
  the Python backend. `observe_only` records the decision and launches nothing.
- An active route starts a separate child with explicit full model ID, effort,
  and sandbox. It never mutates the root session model and never silently
  falls back to another model.

## Invariants

- If a new route needs model, reasoning effort, sandbox, output path, billing, credentials, or retry behavior that shared entrypoints cannot express, extend the shared entrypoint and tests first.
- Do not write provider keys, user tokens, raw prompts, raw command environments, or secrets into git-tracked docs or browser-readable logs.
- Stop-loss and concurrency controls must remain visible and testable.
- Admin readback may summarize LLM usage, but raw provider secrets and token material remain hidden.
- Bootstrap Review profile and launch authority remain outside the workflow
  model policy. Quick Dev, VDD, and Refactor Acceptance can be disabled as
  independent consumers.

## Change Rules

- Changing Codex command construction requires `CodexHostedProcessCommandFactoryTests`.
- Changing read-only LLM routing requires `LlmRouteEngineTests`.
- Changing Python LLM backend behavior requires `scripts/sc/tests/test_llm_backend.py`.
- Changing workflow model policy, classification, or launcher behavior requires
  `scripts/sc/tests/test_workflow_model_routing.py` and the affected consumer
  integration tests. Candidate activation additionally requires exact-surface
  capability evidence and representative shadow predicates.
- Caller-specific routes need their own tests in addition to shared entrypoint tests.
- New LLM readback fields must define redaction and account/admin scope.

## Related Code

- `PhaseA.Platform/Llm/LlmRouteEngine.cs`
- `PhaseA.Platform/Runs/CodexHostedProcessCommandFactory.cs`
- `scripts/sc/_llm_backend.py`
- `scripts/sc/workflow_model_routing.py`
- `scripts/sc/workflow_model_routing_evaluation.py`
- `PhaseA.Platform/Llm/LlmBindingService.cs`
- `PhaseA.Platform/Llm/LlmStopLossService.cs`
- `PhaseA.Platform/Llm/ChatService.cs`
- `PhaseA.Platform/Readback/AdminLlmUsageReadback.cs`
- `PhaseA.Platform/Readback/AdminLlmRunAuditReadback.cs`

## Related Tests

- `PhaseA.Platform.Tests/Runs/CodexHostedProcessCommandFactoryTests.cs`
- `PhaseA.Platform.Tests/Llm/LlmRouteEngineTests.cs`
- `PhaseA.Platform.Tests/Llm/LlmBindingServiceTests.cs`
- `PhaseA.Platform.Tests/Llm/LlmStopLossServiceTests.cs`
- `scripts/sc/tests/test_llm_backend.py`
- `scripts/sc/tests/test_workflow_model_routing.py`
- `scripts/sc/tests/test_workflow_model_routing_evaluation.py`
