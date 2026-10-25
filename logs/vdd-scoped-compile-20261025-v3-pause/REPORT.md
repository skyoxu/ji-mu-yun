# Real public V3 recovery: normal pause

Approval: Sentinel_8fde926754c88191980df2a9aa4b783f (2026-10-25 03:58 UTC).

## Actual outcome

The actual public workflow_host -> scripts/vdd/compile_plan.py command in launch.json returned paused / exit0. Compilation began 2026-10-25T04:00:01.929618+00:00 and ended 2026-10-25T04:02:10.207266+00:00; elapsed 128.278s. Both compiler and response-service processes have exited. No V4 stage started, no canonical compiler-state/plan-ready publication exists, and authorizes=[].

V0/current source and query gates, V1 replay, V2, V3, V3A and V3 execution preflight ran. The native paused result records305 obligations and305 acceptances. The original r3 directory is the resume target; it was not replaced by a new main requirements directory.

## Reuse, requests and actual acceptance

- Actual legacy V1 cache replays:61. New V1 author requests:0.
- New real native V3 caller-session requests:77 (76 groups of4 plus1 group of1),77 returned host results and77 native worker-returned events with exit_code0.
- Exactly305 distinct obligation IDs submitted once; all actual response bodies compare structurally equal to the corrected author draft. Only each genuine request's exact subset was wrapped as obligation_contracts and bound to that real request hash. No request or receipt was fabricated, no worker response/cache/state was manually injected, and no prose/oracle/owner was rewritten.
- Each request was checked against the actual frozen obligation/source identity and existing deterministic schema/domain/execution gates before host_session.respond. The native compiler then performed its own validation, composition, normalization, V3A and execution preflight. Acceptance is established by the real paused native result, not by response file existence.
- Retries / repeated obligation bindings:0. Body-regeneration calls:0. No separate real-model process was started by this session:all77 host-session responses used deterministic selection of existing bodies. These77 native backend requests are real and are not called cache hits. This work conversation itself still consumes tokens.
- The new V3 checkpoint was created by native authority only after both preflights passed; v3_checkpoint_reused=false on this first successful V3 run.

## Frozen identities

Source-index:sha256:4bdddaa521eca69d49354e1e801b18e16b6481b27f3a41f96a78b35673bba322.
Corrected author draft:47cbf5528d6b85617d9198f0f9e4b954fe3a759935419dabb17ff6e2bfd7ed8e.
Native accepted candidate digest:sha256:14436cb2a3e190627af7317b4f3cddddacff2ed5bc55598494db37fefe90c80c.
Checkpoint file digest:sha256:33a73b053412c1b6735517541d1c7375a02cfecd9d4ccc5a5b8e5aa51524715e.
Checkpoint path:execution-plans/2026-10-24-vdd-knowledge-query-scoped-v3-r3/.compiler-work/v3-checkpoints/0e519218119ed49c9f6cf56d6fac33f3cecef9686cd8071246291d88bf5ce564.json.

The61 original text anchors/current input roles and305 candidate obligations remained the same. preservation-final.json verifies all seven input file hashes, original and corrected drafts, prior source assessment/index, current approved pause implementation and unchanged prior repair inputs. cache-preservation.json verifies all97 pre-existing raw cache entries byte-identical. Old host sessions, failed/unconsumed answers and old failure history were not used as current accepted state or rewritten. New compiler progress appended naturally.

## Evidence and limitations

- launch.json / process-start.json / process.json / process-exit.json:actual argv, start, PID and exit.
- native-result.json:public paused outcome and genuine replay counters.
- response-bindings.jsonl:77 actual request/response bindings and305 IDs, body hashes, exact-source checks.
- current-progress.jsonl:current native stage/worker events only, with no V4 stage.
- compiler-console.log / binding-console.log:raw process outputs.
- run-summary.json and preservation-final.json:derived checks, non-authorizing.
- Original real request/response/result files remain under logs/vdd-scoped-compile-20261025-host-v3-pause.

The native per-unit1800-total/600-genuine-inactivity supervision remained active. The entire run took128.278s, so no unit reached either threshold. No old aggregate watchdog or unbounded retry was added. The initial prelaunch path check used an absent policy shorthand, resolved the actual policy path and verified its approved bytes before any compiler launch; the public compiler started exactly once.

This step ran no tests, BMAD skill/reviewer, A/B, implementation, Acceptance, push/PR or CI operation. No code/Skill/model configuration changed. V4 semantic alignment, V5/V6 and later publication gates remain unexecuted for this scope. Thus this is validated V3 pause, not plan-ready, implementation authorization or delivery completion.

The approved step is complete and stopped. Continuing V4 requires a separate user decision; no continuation command was run.
