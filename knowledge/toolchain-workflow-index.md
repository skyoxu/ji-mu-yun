# Toolchain Workflow Access Index

This is the source-level allowlist for consulting the repository-local formal
delivery workflow. It is a routing source, not fact authority, generated
acceptance evidence, or a replacement for Accepted ADRs. Knowledge catalogs
and projections remain derived caches under ADR-0044, ADR-0048, and ADR-0057.

## Default Policy

Access to `workflow.md` and `workflow.example.md` is denied by default. Do not
read either file for ordinary Phase service, Hosted project, application,
runtime, documentation, review, or standalone implementation work.

An allowlisted trigger authorizes reading only the named chapter or narrow
entrypoint. It does not authorize loading the complete workflow, creating a
formal execution plan, mutating task state, publishing knowledge, running a
protected review, or releasing artifacts.

## Allowlisted Triggers

| Explicit task intent | Narrow entrypoint |
| --- | --- |
| Bootstrap a copied business repository | `workflow-chapter2-repository-bootstrap` |
| Generate or baseline Taskmaster triplets | `workflow-chapter3-task-triplet-baseline` |
| Generate overlay and contract baselines | `workflow-chapter4-overlays-contracts-baseline` |
| Stabilize task-triplet semantics | `workflow-chapter5-semantics-stabilization` |
| Run or resume the formal single-task daily loop | `workflow-chapter6-single-task-daily-loop` |
| Close formal UI wiring after Chapter 6 | `workflow-chapter7-ui-wiring-closure` |
| Create or repair a complete VDD execution-plan directory | `vdd-execution-plan` |
| Maintain `workflow.md`, its validators, or its chapter skills | Read only the affected heading plus the controlling ADR/plan |
| User explicitly asks to inspect or review the whole workflow | Full read is allowed for that review only |

Skill names above are routing identifiers. Invoke them only when the user
explicitly requests the corresponding formal workflow outcome or the active
plan explicitly binds that entrypoint.

## Denied By Default

The following do not activate `workflow.md`:

- ordinary Phase API, browser, database, auth, runtime, Caddy, LLM, or Hosted
  route changes;
- a standalone requirements Markdown file;
- general implementation, bug fixing, testing, code review, or documentation;
- prototype generation, iteration, repair, GDD, package, preview, or asset work
  routed through the Phase service;
- the presence of `.taskmaster/`, an old execution plan, or historical workflow
  evidence without explicit current task intent;
- an assistant suggestion, inferred future need, or similarity to a workflow
  chapter.

For direct bounded implementation, prefer ordinary repository engineering or
`bmad-quick-dev` when explicitly invoked. Do not manufacture Taskmaster, VDD,
Chapter 3-7, or release state as a side effect.

## Retrieval Budget

1. Confirm one allowlisted trigger from current user intent or an explicit
   active-plan binding.
2. Load the named skill or the smallest relevant heading/source.
3. Do not read `workflow.md` end to end unless whole-document review is the
   explicit task.
4. Stop when the narrow source provides the required authority.
5. Treat missing, stale, ambiguous, or out-of-policy sources as fail-closed.

## Authority And Publication

- Repository source and Accepted ADRs remain fact authority.
- Locator results provide locations and hashes, not synthesized authority.
- Consumers must reread and hash-verify selected sources where their contract
  requires it.
- Knowledge publication is never an automatic recovery side effect; only the
  authorized `maintain-knowledge-base` flow may publish a generation.
- Runtime state, project state, acceptance evidence, and knowledge generations
  retain their separate lifecycle ownership.
