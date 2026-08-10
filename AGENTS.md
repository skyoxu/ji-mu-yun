# Repository Agent Contract

This is the Ji Mu Yun Phase A/B cloud prototype platform, not a game project.
This always-loaded file keeps only routing, authorization, and cross-tree
invariants; owning documents contain procedures.

## Context Layers

Keep these responsibility layers separate:

1. **Toolchain control plane** - workflows, skills, validators, knowledge, and
   plans. Start at `knowledge/toolchain-workflow-index.md`.
2. **Phase service layer** - application, host, accounts, metadata, routes,
   LLM execution, and evidence. Start at the Phase architecture and standards
   indexes.
3. **User sandbox layer** - each Hosted workspace and its structured project,
   route, repair, diagnostic, and acceptance state.

These layers never share snapshot, current, cache, or LKG authority. Knowledge
selection retains ADR-0044's four dimensions.

## Read Routing

Read only the row that matches the task, then follow its local links.

| Task area | Required entry |
| --- | --- |
| Product status and startup | `README.md` |
| Phase application or browser/API | `PhaseA.Platform/AGENTS.md` |
| Host startup, watchdog, Caddy, or recovery | `runtime/phase-a/AGENTS.md` |
| Phase architecture or ADR decisions | `docs/architecture/phase-service/_index.md` and `docs/architecture/ADR_INDEX_PHASE.md` |
| API, DB, security, errors, logs, tests, or status | `docs/standards/phase-service.md` |
| Hosted Godot behavior | the relevant entry in `docs/standards/_index.md` |
| Repository delivery toolchain | `knowledge/toolchain-workflow-index.md` |
| Documentation discovery | `docs/PROJECT_DOCUMENTATION_INDEX.md` |
| Plan- or decision-scoped work | the explicit target under `execution-plans/` or `decision-logs/` |

Before modifying a subtree, follow its nearest `AGENTS.md`. Do not preload
unrelated indexes or document trees.

`AGENTS.md` files inside `logs/`, `backup/`, acceptance snapshots, or
`artifact-view/tree/` are frozen evidence or imported payloads, not active
repository instructions. Do not use those directories as a general session
working root.

## Non-Negotiable Rules

- Communicate with the user in Chinese.
- Default environment is Windows; use Windows-compatible commands and paths.
- Keep code, scripts, tests, comments, logs, and printed messages in English.
- Do not use emoji.
- Preserve user changes and avoid destructive Git or filesystem operations.
- Ask before high-risk actions or modifications to protected paths.
- Prefer small, deterministic, testable changes; never disable tests to pass.
- Write run, smoke, drill, recovery, and acceptance evidence under `logs/`.
- Code or test changes cite an Accepted ADR. Changed thresholds, contracts,
  security posture, or release policy update or supersede the ADR set.
- Route architecture work in arc42 order: irreversible decisions,
  cross-cutting rules, runtime backbone, then feature slices.

## Highest Encoding Rule

- Read and write Chinese text only with Python and explicit UTF-8, for example
  `Path(path).read_text(encoding="utf-8")` and
  `Path(path).write_text(text, encoding="utf-8", newline="\n")`.
- Never use PowerShell or Windows-native text commands for Chinese content.
- If a command script needs Chinese literals, use a Python file or ASCII-only
  Python source with Unicode escapes.
- This applies to guidance, Markdown, skills, prototype records, and
  project-health documentation.

## Protected Changes

Ask before modifying:

- live metadata, runtime state, or Hosted workspaces under
  `logs/phase-a-innernet/`;
- Phase runtime startup/watchdog scripts or Caddy configuration;
- Phase auth, token hashing, account isolation, or audit code;
- shared LLM/Codex entrypoints owned by `LlmRouteEngine`,
  `CodexHostedProcessCommandFactory`, or `scripts/sc/_llm_backend.py`;
- delivery/security profiles, public URLs, bind addresses, secret authority,
  or listener behavior;
- generated evidence or failure history when the intent is to rewrite or
  delete it rather than append sidecar evidence.

Never mutate the live Phase database manually or commit secret material.

## Phase Service Contract

- Browser-consumed APIs are backward-compatible by default. Breaking routes,
  fields, status, auth, or artifact paths needs approval and a compatibility
  plan.
- Schema changes preserve existing data and include a migration or recovery
  path unless an approved decision explicitly says otherwise.
- API changes cover the handler/DTO, browser caller, auth boundary, public
  behavior documentation, targeted platform tests, and the relevant smoke.
- Auth changes verify denial, authorization, isolation, hashing, audit, and no
  token leakage.
- Runtime or proxy changes validate local Phase health before public health and
  append runtime evidence.
- Hosted route changes validate workspace boundaries, safe readback, recovery,
  route/repair state, and acceptance evidence.
- A run is never complete based only on assistant text. Validators, diagnostics,
  generated sidecars, database-bound artifacts, or other current machine
  evidence must establish completion.

Detailed matrices and conventions belong to the Phase standard and local
`AGENTS.md`.

## Critical Execution Boundaries

### Hosted Route Recovery

For file-changing Hosted routes, follow
`docs/architecture/phase-service/prototype-routes-and-recovery.md`.
Consume its project-local sources in order. Missing sources fail closed;
current live blockers beat historical summaries and route memory.

### Shared LLM And Codex

All Phase LLM/Codex work uses
`docs/architecture/phase-service/llm-codex-execution.md` and UTF-8 stdin.
Read-only decisions are schema/JSON parsed; writes require an executable route,
`workspace-write`, and acceptance. Extend the shared entrypoint and tests before
adding unsupported execution behavior.

### Runtime Recovery

Follow the runtime README: check local health first, use canonical live-server
scripts, then inspect the proxy. Never use plain `dotnet run` for the live
server. Append recovery evidence.

### Planned Capabilities

Plans are intent, not proof. Current status lives in `README.md`; the paused
frontend hardening plan remains downstream of its protected handoff.

## Repository Workflow Policy

`workflow.md` is the legacy repository-local formal delivery kernel, not the
default Phase browser/API path. Do not read or apply it unless the request
matches an allowlisted trigger in `knowledge/toolchain-workflow-index.md`.
Prefer the narrow chapter skill or source named by that index instead of
loading the whole file.

A standalone requirements Markdown file is direct implementation input. It
must not create a VDD directory unless the user explicitly requests creation
or repair of a complete execution-plan directory. Ordinary Phase service work
must not enter Taskmaster triplets, Chapter 3-7 orchestration, overlay-generator
flows, local Chapter 6 review recovery, or game-template release work.

## Definition Of Done

- Targeted validation passed, or the exact validation gap and required
  follow-up evidence are recorded.
- Required tests and smokes match the changed contract and blast radius.
- Runtime or workflow evidence is appended under `logs/`; historical failures
  remain intact.
- Documentation is updated only where public behavior or ownership changed.
- No secret material, live database mutation, unsupported compatibility break,
  or assistant-only completion claim was introduced.

## Maintenance Budget

Target 6,000-8,000 characters; use 10,000 as the hard ceiling.
Do not add command catalogs, repeated path maps, workflow chapters, detailed
test matrices, or status narratives here. Add or update the owning source and
link it through one existing routing entry.
