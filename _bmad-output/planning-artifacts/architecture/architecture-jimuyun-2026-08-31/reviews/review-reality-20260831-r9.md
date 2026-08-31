# Architecture Spine Reality / Brownfield Review — 2026-08-31 r9

Target: current frozen `ARCHITECTURE-SPINE.md` and SPEC companions at
candidate `b3334eac60308ea2d8b381710a64d712cfc7d0ff`.

## Verdict

**BLOCKED.** The architecture and companions define a mechanically testable
AD-15 gate, but the current plan-local implementation does not satisfy it.
The spine must remain `status: draft`; no implementation handoff is justified
until a fresh conformance run marks every AD-15 row `pass`.

## Findings

### H1 — Artifact writer ownership is not separated

`tools/process_executor.py:8-9` only returns `CompletedProcess`. In contrast,
`tools/artifact_owners.py:78-109` executes the SUT, constructs receipt and
observation, invokes `validate_judge`, and writes the combined
`process-receipt.v1.json`. `independent_judge.py` validates that combined value
but is not the observation/classification writer. This violates AD-4/AD-6 and
the SPEC requirement that executor receipt bytes precede judge observation.

### H2 — Legacy `observed`/`executions` remain on the active path

`artifact_owners.py:104` emits aggregate `executions`, and
`independent_judge.py:30-44` validates that field directly. The active path
does not emit the SPEC companion's canonical `evidence_state` values and
separated `process_attempts`/`test_executions`/`cases`; compatibility projection
is therefore not read-only and isolated.

### H3 — Runtime-edge lineage gate is incomplete

`tools/coverage_gate.py:7-22` checks only acceptance/case/observation/assertion
shape and a `receipt.*` assertion prefix. It does not require or re-read the
descriptor, receipt, observation, target, fixture, candidate, producer,
validator, selector, or deterministic failure identity hashes required by
`implementation-contracts.md` and AD-17.

### H4 — Registered stages bypass one descriptor/executor seam

`tools/stage_command.py:17-18` exposes only `green`, `refactor`, and
`terminal`; no RED descriptor is registered. Lines 43-72 run `python -m pytest`
directly and line 79 invokes `artifact_owners.py` separately, allowing selector,
cwd, timeout, and producer identity to diverge from the frozen descriptor.
This is the registered lifecycle path, not an explicitly diagnostic-only path.

### H5 — Terminal process truth is pre-written

`stage_command.py:26-30` calls `prepare_terminal_observation()` before any
terminal command. `terminal_validator.prepare_terminal_observation()` writes an
observation with `exit_code: 0` and only then permits terminal evidence
publication. Q8 can therefore consume synthesized success rather than a
process-derived receipt/observation, violating AD-15(e).

