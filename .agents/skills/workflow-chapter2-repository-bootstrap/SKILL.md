---
name: workflow-chapter2-repository-bootstrap
description: Run the fixed Chapter 2 repository bootstrap workflow from workflow.md. Use when a new business repo is copied from the template and needs name/path cleanup, entry index rebuild, local hard checks, optional project-health dashboard service, or explicit opt-in OpenAI backend bootstrap.
---

# Workflow Chapter 2 Repository Bootstrap

## Role

Operate Chapter 2 from `workflow.md` idempotently for a business repository that is a sibling of the template repository.

## Operating Contract

- Treat `workflow.md` as the normative workflow source.
- Treat business-repo logs as empirical evidence, not policy overrides.
- Use Python with UTF-8 for documentation reads and writes.
- Keep generated code, scripts, tests, comments, and log messages in English.
- Do not modify the business repo unless the user explicitly asks for that change.
- Do not rerun expensive steps before reading existing recovery artifacts.

## Repository Layout

Template and business repositories are siblings under one parent directory, for example `<parent>/godotgame`, `<parent>/<business-repo-a>`, and `<parent>/<business-repo-b>`.

## Purpose

Use this skill to bootstrap a copied template repository into a clean business repository before task triplets and overlays are created.

## Default Lane

Clean project identity and indexes first, run repository-level hard checks immediately after that, and start project-health only when an interactive local dashboard is useful.

## Primary Command Or Action

`py -3 scripts/python/dev_cli.py run-local-hard-checks --godot-bin "$env:GODOT_BIN"`

## Evidence Rule

Chapter 2 is an early bootstrap workflow. Prefer direct repository checks and project-health artifacts over historical task logs; OpenAI backend bootstrap is explicit opt-in only.

## Required Reading

1. Read the relevant Chapter 2 section in the template repo `workflow.md`.
2. Inspect the target repository state directly; Chapter 2 does not use historical business-repo evidence.
3. Refresh this skill with `py -3 scripts/python/update_workflow_chapter_skills.py <repo>` when `workflow.md` changes.

## Idempotent Procedure

1. Resolve the target business repo as a sibling of the template repo.
2. Clean copied template names, paths, workflow names, release names, project paths, and PRD ids.
3. Ensure docs/prd, docs/gdd, and docs/prototypes exist as the primary game-document directories.
4. Ask the player in two separate steps: first the game name, then the game type or reference game name.
5. Classify the second answer with codex exec against exactly one of the 25 runtime-effective ids in docs/game-type-guides/game-types.csv (24 upstream GDS ids plus the Ji Mu Yun survivorslike extension); never leave it unclassified or outside the registered set.
6. If the game-type catalog is missing, unparsable, contains duplicate ids, or points to a missing guide, stop and restore it from the template before classification.
7. Write Game Name, Game Type, Game Type Source, and Game Type Guide into AGENTS.md and README.md under Game Project Metadata.
8. Rebuild entry indexes in README.md, AGENTS.md, docs/PROJECT_DOCUMENTATION_INDEX.md, and docs/agents/00-index.md.
9. Run repository-level hard checks immediately after cleanup and index repair.
10. Optionally start the local project-health service when browser-based health inspection is useful; keep it bound to 127.0.0.1.
11. Use OpenAI backend bootstrap only when the repo explicitly opts into openai-api transport, and keep it out of default CI until checklist self-checks are clean.
12. After Chapter 2 completes, display the project-health URL from logs/ci/project-health/server.json when available, otherwise show the default local URL and the command that starts the service.


## Game Type Classification Prompt

Use `codex exec` in read-only mode from the target repository. Provide the player answer, the game name when available, and the registered CSV rows from `docs/game-type-guides/game-types.csv`. Require JSON with exactly one `game_type` id and a short reason. If the answer names a reference game, classify by gameplay fit rather than title similarity.

## User Interaction Language And Encoding

- Chapter 2 user-facing questions, confirmations, and missing-input messages must be in Chinese.
- Read and write Chinese documentation through Python with explicit `encoding="utf-8"`.
- Do not use PowerShell or Windows-native text commands to read or write Chinese documentation.
- If a temporary Python script must carry Chinese text, use ASCII-only source with Unicode escapes.

## Stop-Loss Signals

- Existing `forbidden_commands` blocks the command about to be run.
- `artifact_integrity`, `planned_only_incomplete`, or planned-only run type appears in recovery evidence.
- Route evidence recommends inspect-first, record-residual, fix-deterministic, repo-noise-stop, or pause.
- The same deterministic failure fingerprint appears repeatedly.
- The next action would duplicate work already covered by task, overlay, candidate, or manifest evidence.

## Business Evidence References

Generated evidence may live under `references/business-repos/<repo>.md`. These files are optional regression evidence from known business repositories; they must not define production generation rules.

## Maintenance

Refresh optional evidence after new business-repo logs are generated:

```powershell
py -3 scripts/python/update_workflow_chapter_skills.py <business-repo>
py -3 scripts/python/update_workflow_chapter_skills.py <business-repo-a>,<business-repo-b>
```
