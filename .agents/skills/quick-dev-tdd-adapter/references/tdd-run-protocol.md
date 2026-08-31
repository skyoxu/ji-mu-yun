# TDD Run Protocol

For new Chapter 4/5/6 plans, the current runtime authority is `tools/current_lifecycle.py`. Historical `loop_plan_directory.py`, `run_slice_lifecycle.py`, `stage_command.py`, plan-local combined writer artifacts, and the earlier `canonical_lifecycle.py`/`evidence_pipeline.py` bridge are compatibility inputs only. They may be projected or rejected for replay, but they cannot write current completion evidence.

`prepare` validates the VDD semantic-plan bundle, current product/execution roots, descriptor identity, target/fixture bindings, candidate identity, write/read boundaries, and the runtime-resolved launcher/interpreter/test-runner environment. Architecture registry, memlog, spine, review, binding, authorization, and ordinary governance bytes do not enter the runtime snapshot unless a named product/execution contract explicitly adopts their semantics.

`RED` resolves the VDD failure intent into a shell-free descriptor, executes the real process through the executor trust zone, and then lets the independent judge classify the immutable receipt. VDD never writes a receipt, run ID, process result, observation, or pass/fail. A passing RED, timeout, zero-case/harness result, stale target/fixture/argv binding, unrelated failure, or production write before RED fails closed.

The executor is the sole writer of immutable `process-receipt.v2`; the independent judge is the sole writer of `observation.v2`; the runtime-edge validator is the sole writer of `runtime-assertion-edge.v2`. Strict create-if-absent writes never overwrite concurrently created evidence.

A successful RED/GREEN/REFACTOR/terminal stage requires a real process attempt, at least one test execution and case, current target/fixture hashes, and descriptor binding. Timeout and pre-observation harness failures may legitimately carry zero test executions/cases, but can never satisfy a successful stage predicate.

`GREEN` and `REFACTOR` reuse RED selector identity, target refs, fixture refs, assertion IDs, and cwd. Only stage/run/candidate successor identity may change. Any selector/test/fixture contract mutation invalidates the lineage back to RED.

The lifecycle is append-only and ordered: `prepare -> RED -> implementation successor -> GREEN -> REFACTOR -> slice-ready -> whole-plan-terminal`. Recovery references explicit immutable predecessors; glob, mtime, latest-success scans, and receipt-only recovery are not authority.

Terminal closure is an exact-set check over the V6A `(slice, Acceptance, stage)` universe. `tuple_key` must equal `slice_id|acceptance_id|stage`; tuple keys must be unique; actual key set/cardinality must equal the expected set; and every tuple binds a current runtime-edge hash, selector identity, and current-snapshot hash. Q8 re-reads each runtime edge, observation and receipt.

The current snapshot contains exactly eight runtime root kinds: `candidate_tree`, `plan`, `contract`, `descriptor`, `fixture`, `source`, `validator_judge`, and `plan_state_transition`. The resolver rejects governance roots, absolute/escaping paths, symlink escape, untracked/unlisted Git delta, and unknown root kinds. Q8 computes the snapshot before lineage validation and again immediately before publishing `implementation-complete`; the two hashes must be identical.

A drifted or partial run is never completion proof. Quick Dev may publish only `implementation-complete`; external semantic acceptance remains a separate authority.
