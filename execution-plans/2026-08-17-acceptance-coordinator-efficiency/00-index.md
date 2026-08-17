# Acceptance Coordinator Efficiency Execution Plan

## Status

- Plan ID: `acceptance-coordinator-efficiency`
- Profile: `self-hosted`
- Lifecycle state: `plan-ready`
- Owner of this state: `vdd-execution-plan`
- Source authority: `../2026-08-15-acceptance-review-bootstrap-efficiency/acceptance-workflow-optimization.md`
- Implementation authorization: not published; maintainer-owned

## Intent

Remove the avoidable manual orchestration and unsafe artifact substitution that
made the 8-15 Acceptance run slow. The plan changes only repository delivery
control-plane code. It keeps lifecycle ownership unchanged: VDD owns plan
readiness, the maintainer owns implementation authorization, Quick Dev owns
`implementation-complete`, and Acceptance owns `acceptance-passed`.

## Selected Profile

`self-hosted` is required because the work changes Quick Dev completion
handoff, Acceptance route/finalization behavior, and the controlling execution
path. It remains lightweight: four implementation slices, existing unit-test
suites, one terminal full command, no Bootstrap review, and no new semantic
validator or requirements/acceptance cross-product.

## Readiness Evidence

The typed VDD input receipt is ready and the Knowledge Preflight accepted the
current Refactor Acceptance and Quick Dev read-set. The first child transport
attempt returned non-JSON, but a controlled retry of the same request produced
the bound context and semantic decision. This did not alter requirements or
the four-slice scope.

## Slices

| Slice | Behavior | Depends on |
| --- | --- | --- |
| S0 | Candidate identity, bundle/context authority, and behavior-affecting environment identity | none |
| S1 | Machine-selected deterministic fast path with no semantic child or Bootstrap | S0 |
| S2 | Identical replay, stale successor recovery, and latest-successor selection | S0, S1 |
| S3 | One-shot, reentrant Acceptance coordinator with typed semantic handoff and telemetry | S0, S1, S2 |

Each slice declares its RED, GREEN, allowed write-set, dependency and exit
predicate in `implementation-contract.v1.json`. RED is observed by adding a
test to the existing owning suite before production behavior changes; a missing
future test file is not accepted as RED evidence.

## Boundaries

- `deterministic_only` is selected by machine evidence, never caller input.
- It neither starts nor calls Bootstrap.
- Semantic routes may emit only a typed Bootstrap handoff and stop at the
  explicit acknowledgement/authorization boundary.
- Existing Acceptance-owned context refresh/rehash is consumed, not rebuilt.
- Acceptance never publishes Knowledge authority or another lifecycle owner's
  state.

## Validation

Run the per-slice RED/GREEN/refactor commands from `command-registry.v1.json`.
After S3, run `terminal-full`: the existing Quick Dev adapter suite and
Acceptance suite together. This terminal command may establish only
`implementation-complete`; Refactor Acceptance remains separately responsible
for the regression run and `acceptance-passed`.
