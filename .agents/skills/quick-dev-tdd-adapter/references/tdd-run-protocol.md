# TDD Run Protocol

`prepare` validates current hashes, the slice contract, predecessor evidence, command registry, baseline, and path boundaries.

`RED` permits only declared test or fixture changes and must observe the declared failure identity. A passing test, compile failure, harness failure, unrelated regression, stale binding, or production write before RED fails closed.

`GREEN` requires current RED evidence and permits only the declared minimal production write set. `REFACTOR` requires GREEN and reruns the declared regression checks. Each stage records its command, exit code, hashes, timestamp, and predecessor-stage hash.

The lifecycle is append-only and ordered: `prepare -> RED -> GREEN -> REFACTOR -> candidate`. Immutable observations are the recovery facts; `stage-state.json` is only a rebuildable cache. A drifted or partial run is never completion proof, but a verified observation prefix may resume from its first missing stage or through a hash-bound successor without repeating an already observed stage.
