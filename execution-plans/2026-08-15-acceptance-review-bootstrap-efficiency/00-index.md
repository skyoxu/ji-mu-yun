---
plan_id: acceptance-review-bootstrap-efficiency
profile: self-hosted
state: plan-ready
authority: _bmad-output/specs/spec-acceptance-review-bootstrap-efficiency/SPEC.md
---

# Acceptance Review And Bootstrap Efficiency

This self-hosted plan consumes the complete selected Canonical Spec Package.
The PRD files are provenance only. The adopted Architecture Spine is normative.

## Outcome

Replace whole-directory acceptance review with an evidence-gated Artifact DAG:
Acceptance freezes identities, computes a complete Consumer Closure, runs real
required checks, selects a typed route, and imports non-authorizing Bootstrap
evidence. Bootstrap uses event-sourced state only inside semantic execution and
recovery. Lifecycle ownership remains decentralized.

## Delivery Order

| Slice | Milestone | Behavior | Recovery |
| --- | --- | --- | --- |
| S0 | M0 | Shared canonical evidence primitive, strict JSON, golden vectors, and legacy verification. | Restore the last passing vector set; never mint through legacy. |
| S1 | M0 | Mandatory producer/consumer migrations and removal of private or plan-local canonical implementations. | Keep the current consumer on legacy verify-only until its current vectors pass. |
| S2 | M0 | Bootstrap runtime policy, Process Events, Effective Progress, watchdog, terminal classification, lease reconciliation, and bounded retry. | Rebuild lease only from events and current process identity; return typed recovery. |
| S3 | M1 | Acceptance admission, Changed-set Manifest, Consumer Closure, real required checks, typed route, and cost decision. | Rebuild the stale owner artifact; deterministic failure launches zero reviewers. |
| S4 | M0/M1 | Full-source delivery, Range Projection, stable Segment Descriptor, segment-only snapshot, and inherited access proof. | Reproject or repartition with a successor identity; never expand child scope. |
| S5 | M1/M2 | Complete three-role Bootstrap execution, gate/verifier, evidence import, and Acceptance finalization. | Reject stale or incomplete evidence; Bootstrap remains non-authorizing. |
| S6 | M2 | 8-13 regression, semantic corpus, telemetry, historical replay, and default-switch gate. | Keep whole-directory default until parity and counter-metrics pass. |

## Lifecycle

VDD publishes `draft -> plan-ready` only. Maintainer authorization is still
required before Quick Dev starts. Quick Dev owns `implementation-complete`;
Acceptance owns `acceptance-passed`; Bootstrap publishes neither.

## Validation

Run `py -3 execution-plans/2026-08-15-acceptance-review-bootstrap-efficiency/tools/validate_all.py --validate-plan` before authorization. Implementation executes each registered RED/GREEN/refactor command, then `terminal-full` once.
