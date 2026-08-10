# Hosted Game Project Guide

This workspace is one account-scoped game project hosted by the Ji Mu Yun Phase
service. It is not the platform repository. Platform maintenance, host runtime,
account administration, and other projects are outside this workspace scope.

## Authority And Lifecycle

- The primary Domain is `workspace`. Phase or Toolchain knowledge is available
  only when the server-selected route policy declares it as a dependency.
- Once copied into a project, this file is project-instance guidance. It does
  not inherit instruction authority from the platform repository file that
  originally seeded the workspace.
- Project files and metadata may narrow permissions but never expand the
  server route, published Skill, account, sandbox, network, or tool ceiling.
- Repository projections and indexes are `derived_cache`; current project
  source, structured route contracts, metadata authority, and the latest live
  acceptance blocker take precedence.

## Recovery Authority Order

Before a file-changing Hosted route executes, consume and validate the
applicable sources in this order:

1. Parsed game-type route profile.
2. Selected route Skill prompt block.
3. `meta/project-execution-guide.md`.
4. `routes/prototype-contract/latest.json`.
5. Current route latest state under `meta/routes/**`.
6. Current goal, step, repair step, or session state.
7. Repair ledger and failing acceptance or Godot diagnostics when applicable.
8. Latest live platform acceptance blocker, which overrides stale summaries,
   route memory, and old repair state.

The server-owned recovery contract is authoritative if it evolves. Missing
required sources fail closed. Assistant prose never completes a step.

## Workspace Non-Negotiables

- Use Windows-compatible paths and keep code, tests, scripts, and logs in
  English. Write Chinese text, and scripts containing Chinese literals, with
  Python and explicit UTF-8. FastCtx read/grep and encoding-preserving replace
  may inspect or mechanically update UTF-8 text; do not use PowerShell or
  Windows-native text commands to write Chinese content.
- Preserve user changes and structured evidence. Never perform destructive Git
  or filesystem operations, expose secrets, or manually edit live state.
- Ask before changing anything outside the server-selected workspace or using
  an unapproved tool, provider, network, or process path.

## Skill And Knowledge Context

- Use only the route-selected, server-published Skill and capability set.
- The repository Locator is not currently exposed through a Phase browser
  route. A child Skill must not call its CLI independently and treat that
  result as server-approved Hosted context.
- Knowledge Locator output is a location recommendation, not a factual answer.
- When a server-owned Phase adapter is introduced, it must verify the pinned
  snapshot and each `source_sha256`, then reread the exact source bytes before
  making any candidate available to the run.
- Consume only adapter-accepted candidates in the frozen run context. Do not
  add, reclassify, or independently query knowledge after the parent freezes
  the run Artifact View.
- A stale snapshot, policy mismatch, hash drift, missing required module, or
  out-of-policy path blocks dispatch.

## Workspace Change Rules

- Keep all reads and writes inside the server-selected project workspace.
- Do not access platform implementation, host paths, other accounts/projects,
  live metadata, host secrets, or public deployment configuration.
- Preserve structured route state, ledgers, diagnostics, and failure evidence.
- Use repository-provided scripts and validators; do not construct a parallel
  provider or raw `codex exec` path.
- Keep shared C# contracts Godot-free and keep Godot behavior consistent with
  the project-selected engine, UI, diagnostics, and acceptance standards.
- Validate changed behavior with the route-specific acceptance and relevant
  Godot/.NET tests before reporting completion.

## Project Sources

Project identity and current execution status belong to project metadata,
`meta/**`, `routes/**`, source files, run records, ledgers, and acceptance
evidence. Do not infer them from this template or from platform-root docs.
