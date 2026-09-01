# FR-901

The VDD compiler must reject an active requirement when its Acceptance is not observable, must stop before any semantic model call when deterministic source preflight fails, and must return a structured `repair-vdd` recommendation that identifies the blocking reason.

# FR-902

Quick Dev recommendation-only must read an explicit current snapshot, must distinguish reusable observations from invalidated observations, must never run tests, must never create a run, must never call a model, and must never write lifecycle state.

# FR-903

During RED execution, a timeout must not count as expected RED, a zero-case test run must be classified as a harness failure, repository noise must not authorize implementation, an unexpected green must not authorize implementation, and a second identical deterministic failure fingerprint must stop another unchanged rerun.

# FR-904

GREEN and REFACTOR must preserve the RED selector identity, target, fixture, assertion scope, and safe cwd; implementation and refactor changes must remain inside the declared production write set, and changing selector or fixture bytes must invalidate the prior RED lineage.

# FR-905

Whole-plan terminal validation must consume explicit hash-bound run-local predecessors, must reject glob/mtime/latest-success history inference, must recompute exact coverage for every active Acceptance, must re-read runtime evidence and the current snapshot before publication, and self-hosted promotion must bind detached positive, negative, and mutation fixtures plus an independent judge outside the candidate tree.
