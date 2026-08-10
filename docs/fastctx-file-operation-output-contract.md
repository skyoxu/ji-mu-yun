# FastCtx File Operation Output Contract

Status: Implemented (repository scope; outer orchestration enforcement pending)

This document owns the transport limits for repository file operations. It is
independent from the Skill input-consumption contract, which decides whether a
Skill has enough complete and semantically accepted input.

## Default Routing

- Ordinary file creation, reading, writing, replacement, and quantitatively
  bounded search use FastCtx first.
- High-output files, logs, rollout files, JSONL, process lists, and full
  diagnostics use FastCtx `run` in a child process. The main session reads only
  a bounded `fastctx-summary.v1` artifact.
- A failed or unavailable FastCtx call may use the repository-approved
  controlled reader. The fallback must preserve the same output limits and must
  be reported; it must not return raw high-output content.

## Output Limits

- `read`: at most 300 lines and 12,000 UTF-8 bytes per visible result. Continue
  only from the exact offset reported by `Partial`.
- `grep`: at most 100 matches and 12,000 UTF-8 bytes per visible result. On
  `Partial`, continue only from the returned exact match/entry offset with the
  same pattern, path, and filters.
- `glob`: at most 500 paths per page and no file contents. On `Partial`, continue
  only from the returned exact path offset with the same pattern and filters.
- `run` aggregation: only a `fastctx-summary.v1` result is returned to the main
  session; raw output remains in the child work area or existing evidence path.
- Write operations return status, target, and necessary errors; they do not
  reread unrelated file contents.

## Editing And Evidence

Mechanical replacement requires a dry run before `replace`. Semantic changes
and small exact patches use `apply_patch`. Deletes require explicit task
authorization and an exact target.

Summary artifacts are bounded to 3,000 repository transport-estimated tokens
(UTF-8 bytes divided by four) and
12,000 UTF-8 bytes, measured on the exact serialized artifact including its
trailing newline. They must validate against
`scripts/sc/schemas/fastctx-summary.v1.schema.json` and contain source path and
hash, query, counts, findings, continuation offsets, truncation state, and
errors. Findings, samples, and error text are restricted to bounded schema
fields and must be redacted; raw logs and rollouts are never returned as a
main-session tool result and are never used as a recovery source.

## Repository Evidence

The controlled five-read/five-write benchmark and high-output JSONL summary
evidence is
[`logs/tool-context/fastctx-ab/2026-08-11-read-write-summary.json`](../logs/tool-context/fastctx-ab/2026-08-11-read-write-summary.json).
It is validated by `scripts/python/validate_fastctx_ab_test.py`. The benchmark
measures bounded transport serialization only; it does not establish the actual
token accounting or truncation behavior of `functions.exec` or the Codex
service. Those remain external enforcement boundaries.
