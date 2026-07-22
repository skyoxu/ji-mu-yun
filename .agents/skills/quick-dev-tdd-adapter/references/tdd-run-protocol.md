# TDD Run Protocol

`prepare` validates current hashes, the slice contract, predecessor evidence, command registry, baseline, and path boundaries.

`RED` permits only declared test or fixture changes and must observe the declared failure identity. A passing test, compile failure, harness failure, unrelated regression, stale binding, or production write before RED fails closed.

`GREEN` requires current RED evidence and permits only the declared minimal production write set. `REFACTOR` requires GREEN and reruns the declared regression checks. Each stage records its command, exit code, hashes, timestamp, and predecessor-stage hash.

The lifecycle is append-only and ordered: `prepare -> RED -> GREEN -> REFACTOR -> candidate`. A drifted or partial run is stale, not resumable proof.
