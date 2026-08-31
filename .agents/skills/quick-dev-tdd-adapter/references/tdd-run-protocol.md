# TDD Run Protocol

For new Chapter 4/5/6 plans, `tools/current_lifecycle.py` is the current executor/judge/runtime-edge path and `tools/coverage_predicates.py` owns Q7 `slice-ready` and Q8 `implementation-complete`. Historical `loop_plan_directory.py`, `run_slice_lifecycle.py`, `stage_command.py`, plan-local combined writer artifacts, and the earlier `canonical_lifecycle.py`/`evidence_pipeline.py` bridge are compatibility inputs only. They may be projected or rejected for replay, but they cannot write current completion evidence.

`prepare` validates the VDD semantic-plan bundle, current product/execution roots, descriptor identity, target/fixture bindings, candidate identity, write/read boundaries, and the runtime-resolved launcher/interpreter/test-runner environment. Architecture registry, memlog, spine, review, binding, authorization, and ordinary governance bytes do not enter the runtime snapshot unless a named product/execution contract explicitly adopts their semantics.

`RED` resolves the VDD failure intent into a shell-free descriptor, executes the real process through the executor trust zone, and then lets the independent judge classify the immutable receipt. VDD never writes a receipt, run ID, process result, observation, or pass/fail. A passing RED, timeout, zero-case/harness result, stale target/fixture/argv binding, unrelated failure, or production write before RED fails closed.

The executor is the sole writer of immutable `process-receipt.v2`; the independent judge is the sole writer of `observation.v2`; the runtime-edge validator is the sole writer of `runtime-assertion-edge.v2`. Strict create-if-absent writes never overwrite concurrently created evidence.

A successful RED/GREEN/REFACTOR/terminal stage requires a real process attempt, at least one test execution and case, current target/fixture hashes, and descriptor binding. Timeout and pre-observation harness failures may legitimately carry zero test executions/cases, but can never satisfy a successful stage predicate.

`GREEN` and `REFACTOR` reuse RED selector identity, target refs, fixture refs, assertion IDs, and cwd. Only stage/run/candidate successor identity may change. Any selector/test/fixture contract mutation invalidates the lineage back to RED.

Q7 `slice-ready` re-reads every RED/GREEN/REFACTOR edge, observation, receipt, target, and fixture, proves the exact assertion-ID set for every active Acceptance, rejects extras/duplicates, and requires one selector identity and candidate lineage across all three stages. It writes the complete assertion coverage map; no single runtime edge is allowed to stand in for omitted assertions.

Q8 consumes one explicit Q7 predecessor per partitioned slice. For each `(slice, Acceptance, stage)` it deterministically chooses the first assertion edge only as the closure tuple representative after Q7 has already proved the full assertion set. Q8 then re-reads that edge lineage, requires terminal assertion coverage and the same selector identity, validates the exact tuple key set/cardinality, recomputes the current snapshot, and writes `implementation-complete` only if the snapshot is unchanged.

The current snapshot contains exactly eight runtime root kinds: `candidate_tree`, `plan`, `contract`, `descriptor`, `fixture`, `source`, `validator_judge`, and `plan_state_transition`. The resolver rejects governance roots, absolute/escaping paths, symlink escape, untracked/unlisted Git delta, and unknown root kinds. Evidence logs are not snapshot roots unless a named execution dependency explicitly adopts them.

The lifecycle is append-only and ordered: `prepare -> RED -> implementation successor -> GREEN -> REFACTOR -> slice-ready -> whole-plan-terminal`. Recovery references explicit immutable predecessors; glob, mtime, latest-success scans, and receipt-only recovery are not authority.

A drifted or partial run is never completion proof. Quick Dev may publish only `implementation-complete`; external semantic acceptance remains a separate authority.
