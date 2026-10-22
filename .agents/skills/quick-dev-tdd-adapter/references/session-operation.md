# Explicit Quick Dev Session

Use for sequential native execution or recovery of a current CER plan. Read the
execution and recovery guides for returned worker actions. This route invokes no
model. It does not replace implementation workers, Q7/Q8 or Acceptance.

## Prepare and inspect

Create one JSON request with these exact fields. Reuse the plan's declared
snapshot input sets; do not invent roots to hide changes or omit dependencies.
All repository paths use POSIX separators, including on Windows.

| Field | Value |
| --- | --- |
| `schema` | `quick-dev.execution-session.v1` |
| `plan_sha256` | `sha256:` plus SHA-256 of actual semantic bundle bytes |
| `profile` | Quick Dev execution profile, independent of VDD plan shape |
| `source_commit`, `base_commit` | Explicit full Git commit IDs; baseline must be an ancestor of source |
| `targeted_timeout_seconds` | Integer 1..600; respect the declared execution budget |
| `slices` | Every current slice exactly once in dependency order |
| `snapshot_roots` | Whole-plan native eight-root input array |
| `out` | Fresh Q8 result path under `logs/`, outside all run directories |
| `detached_bundle` | Required only for self-hosted execution; existing validated detached bundle path |
| `failure_history` | Optional explicit repository-relative ordered failure-history JSON path |

Each slice has exactly `slice_id`, `run_dir`, `snapshot_roots`, `ready_path`.
Use distinct, non-overlapping `logs/` run directories. Place ready results outside
those directories, for example `logs/example/S1-ready.json` beside
`logs/example/S1/`. Each snapshot root names `root_kind`, `inclusion_reason`, and
either `repository_relative_posix_path` or `repository_relative_posix_paths`.
The exact eight kinds are `candidate_tree`, `plan`, `contract`, `descriptor`,
`fixture`, `source`, `validator_judge`, `plan_state_transition`. Include the
slice's `run_dir/descriptors` in its descriptor root. Include all declared
execution dependencies; missing planned test files remain Q2 work.

```text
py -3 scripts/quick_dev/run.py --plan <plan> --action preflight-session --execution-request <request.json>
py -3 scripts/quick_dev/run.py --plan <plan> --slice <id> --action inspect-selection
py -3 scripts/quick_dev/run.py --plan <plan> --action advance-session --execution-request <request.json> --max-steps 8
```

Preflight is read-only and creates no run. Inspect its status and diagnostics;
preflight success is not observed product behavior. Execution freezes
`session-input.v1.json` beside the Q8 output. Changing the request needs an
explicit successor output; it cannot relabel existing stage proof.

## Advance and resume

Advance materializes a probe only when all existing test mappings are ready.
Otherwise it returns `worker-required / author-red`; invoke normal `author-red`
for the named slice and run, using the existing local or caller-session backend.
A missing behavior reaches real RED and returns `worker-required / implement`.
Use the existing Q4 worker or handoff/finish route. After GREEN it returns
`worker-required / run-refactor` until the native refactor worker completes.
Pass the same source/base identities and that slice's root array to worker calls.

Reinvoke the same advance command after the worker succeeds or after `paused`.
`--max-steps` bounds newly started deterministic stages (1..100, default 8);
verified reused terminal results do not consume this budget. The route rechecks
Q7, runs or verifies terminal, gathers exact predecessors, and invokes native Q8.
It writes `acceptance-current-quick-dev-binding.json` beside the Q8 result for the
existing Acceptance consumer. It never invokes Acceptance automatically.

A failed, interrupted or stale run remains immutable. Follow native recovery;
do not delete it, overwrite evidence, retry unchanged input through a new name,
or infer a successful predecessor by filename order. Supply explicit prior
failure history when making a justified successor attempt. Every native stage
retains reentry and repeat stop-loss checks. A blocked session returns nonzero;
paused and worker-required statuses are explicit non-completion handoffs.

## Validation limits

Native fixture tests cover process execution, partial behavior, pause/resume,
unchanged reuse, stale evidence, forbidden paths and missing profile/baseline
inputs. Linux verification is not proof of Windows ACL or actual .NET execution.
Maintain existing .NET wrappers; their reusable TRX helper is deferred to pre-S2.
