# Hosted Game Project

This repository copy is a Ji Mu Yun Hosted game-project workspace. The Phase
service creates and operates it for one account/project identity and invokes
approved Godot prototype workflows inside it.

Project name, game type, route profile, goals, and progress are stored in
project metadata and structured project files rather than placeholder values in
this README.

## Runtime Sources

- `meta/project-execution-guide.md`: project-specific execution guidance.
- `routes/prototype-contract/latest.json`: current prototype contract.
- `meta/routes/**/latest.json`: current route state.
- Current goal, step, session, and repair records under project metadata.
- Acceptance evidence and Godot diagnostics for the current run.
- Server-frozen knowledge context containing only accepted, hash-verified
  repository sources when a future server-owned Phase adapter explicitly
  enables repository knowledge for the route.

## Repository Knowledge Status

The repository Knowledge Locator currently serves VDD, Quick Dev, and
Bootstrap Review. Phase browser routes do not yet expose a Locator adapter.
Project Skills must therefore use the project and route sources above and must
not treat a direct CLI query as trusted Hosted context.

## Workflow

```text
browser route
  -> server policy and project identity
  -> route recovery and source validation
  -> optional server-owned knowledge lookup after a Phase adapter exists
  -> frozen run context and signed dispatch manifest
  -> approved Skill/LLM/Codex execution
  -> route acceptance, artifacts, and browser readback
```

The workspace is project data. It does not own Phase host configuration,
account administration, public proxy behavior, server gate policy, or signing
secrets. Missing or stale required context blocks the affected workflow rather
than falling back to unrelated repository instructions.

See `AGENTS.md` for the project execution and recovery contract.
