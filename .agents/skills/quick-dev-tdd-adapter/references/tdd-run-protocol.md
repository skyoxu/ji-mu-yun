# TDD Run Protocol

New Chapter 4/5/6 plans use `tools/canonical_lifecycle.py` as the current evidence path. Historical v1 `loop_plan_directory.py` / `run_slice_lifecycle.py` runs are compatibility inputs only: they may be projected or rejected, but their legacy combined observation or aggregate execution fields are not current evidence authority.

`prepare` validates current product/execution roots, the slice contract, predecessor evidence, descriptor identity, baseline, and path boundaries. Architecture registry, memlog, spine, review, binding, authorization, and ordinary governance bytes do not enter the runtime snapshot unless a named product/execution contract explicitly adopts their semantics.

`RED` resolves the VDD failure intent into a shell-free descriptor, executes the real process through the canonical executor, and then lets the independent judge classify the immutable receipt. A passing RED, compile/harness failure, timeout, zero-case result, unrelated regression, stale binding, or production write before RED fails closed. VDD never writes a receipt, run ID, process result, or observed pass/fail.

`GREEN` requires current expected-RED evidence and reuses the same selector identity, target refs, fixture refs, assertions, and cwd. `REFACTOR` requires GREEN and preserves that identity. The executor is the sole writer of `process-receipt.v1`; the independent judge is the sole writer of `observation.v1`; the runtime-edge validator is the sole writer of runtime assertion edges.

Every current process receipt records `process_attempts`, `test_executions`, `cases`, exit/timeout, stdout/stderr hashes, candidate/descriptor/target/fixture hashes, profile identity, and executor identity. Every observation records the layered `evidence_state`, `verification_outcome`, failure family/ID when required, and judge identity. A producer must never pre-fill semantic pass/fail into the process receipt.

The lifecycle is append-only and ordered: `prepare -> RED -> GREEN -> REFACTOR -> slice-ready -> whole-plan-terminal`. Recovery references explicit immutable predecessors; glob, mtime, latest-success scans, and receipt-only recovery are not authority.

Terminal closure is a deterministic exact-set check over V6A-declared `(slice, Acceptance, stage)` tuples. `tuple_key` must equal `slice_id|acceptance_id|stage`, keys must be unique, and the actual key set/cardinality must equal the V6A expected set. Each tuple binds a current runtime-edge hash and current-snapshot hash.

The current snapshot is a closed eight-kind runtime root set: `candidate_tree`, `plan`, `contract`, `descriptor`, `fixture`, `source`, `validator_judge`, and `plan_state_transition`. The resolver rejects unknown roots, absolute/escaping paths, symlink/junction escape, stale hashes, and unlisted Git delta.

A drifted or partial run is never completion proof. A verified observation prefix may resume only through explicit predecessor refs and current-byte revalidation. Quick Dev may publish only `implementation-complete`; external acceptance remains a separate authority.
