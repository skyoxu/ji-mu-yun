# Manual-Pause Closure Protocol Incompatible-Scope Decision

- Status: Accepted
- Date: 2026-08-01
- Decision ID: `manual-pause-closure-protocol-incompatible-scope-v1`
- Authority: repository maintainer

## Context

The Round 1 Skill-route review at
`logs/ci/2026-08-01/manual-pause-closure-protocol-r1` evaluated the original
target `refactor-acceptance-manual-pause-closure` under lineage family
`ria-manual-pause-closure-protocol-v1`. All three discovery layers completed
and the gate retained six P1 candidates:

- `BSR-2F46188817FBB46B`
- `BSR-3D2D052158771770`
- `BSR-88E58B1FB239AD35`
- `BSR-AA1ED33E8F29F55C`
- `BSR-F2E70BCBC3A97B75`
- `BSR-F540DC0BA3F2D1B1`

Independent verification required the profile-owned Sol/max security route.
The frozen target did not include the Bootstrap execution dependency whose
typed placeholder still allowed only `medium|high`. Repairing that dependency
correctly changed `controlPlanePolicy`, so the old launch authorization became
stale before the verifier could run.

The gate candidates also showed that the original target omitted two required
acceptance boundaries: complete canonical replay of the finalized Bootstrap
run, and fail-closed handling of unresolved verifier decisions.

## Decision

The old target is not renamed or retried. It remains immutable, stale,
`awaiting_verification` history and does not authorize acceptance.

The reviewed target is incompatible with the complete consumer closure needed
for first real use. Supersede it with the new target
`refactor-acceptance-manual-pause-closure-with-bootstrap-max-replay`, using the
new lineage family
`ria-manual-pause-closure-protocol-v2-max-replay`.

The new target must include all of the following in one minimal complete
Skill-route closure:

- the repaired Refactor Acceptance manual-pause implementation, schemas,
  tests, Skill instructions, ADR-0054, and Bootstrap standard;
- canonical historical replay through the repository-owned Bootstrap
  producer, with exact envelope comparison excluding only `generatedAt`;
- rejection of every unresolved `unverified` verifier decision;
- Bootstrap typed-placeholder support for the profile-owned `max` effort;
- historical replay compatibility for the exact outgoing `medium|high`
  control-plane policy, without permitting that old policy for a current
  launch;
- this decision and all six old gate candidates as usage and recovery
  evidence.

This is a genuinely broader acceptance target because it adds a previously
missing execution dependency and a historical-policy compatibility contract.
It is not a successor directory or change-ID rename for the old target.

## Boundaries

- Do not modify or delete the old run, reviewer outputs, gate, attempts, or
  process events.
- Do not use the new family to reinterpret the old gate as clean or verified.
- Do not publish `acceptance-passed` from either review.
- The new target requires its own deterministic preflight, high-cost
  acknowledgement, three isolated reviewers, gate, and independent verifier
  when required.
- A clean new review authorizes only first-use eligibility of the closure
  protocol. The original 8-1 target still requires its own deterministic
  repair evidence, maintainer challenge acknowledgement, and Acceptance
  lifecycle transition.

## References

- `docs/adr/ADR-0054-refactor-acceptance-manual-pause-closure.md`
- `docs/adr/ADR-0051-bootstrap-lineage-family-and-bounded-repair-reentry.md`
- `docs/standards/bootstrap-review-control-plane.md`
- `logs/ci/2026-08-01/manual-pause-closure-protocol-r1/review-candidates.json`
- `logs/ci/2026-08-01/manual-pause-closure-protocol-r1/review-gate-result.json`

## Recovery Metadata Supplement (2026-09-30)

Added for recovery-document schema completeness. The original narrative,
conclusions, and evidence above remain unchanged. This supplement does not
create a new acceptance result or a historical candidate binding.

- Title: Manual-Pause Closure Protocol Incompatible-Scope Decision
- Supersedes: none
- Superseded by: none
- Branch: n/a - the original narrative did not capture its decision-time branch
- Git Head: n/a - the original narrative did not capture its decision-time commit; this metadata supplement does not infer a historical binding
- Why now: Round 1 retained six P1 candidates and the required max-effort dependency made the old launch authorization stale.
- Context: See Context above.
- Decision: See Decision above: preserve the old stale target and use the explicitly broader v2-max-replay target.
- Consequences: The new target requires its own complete review and verification; old evidence grants no acceptance.
- Recovery impact: Preserve the old run and all six candidates; follow Boundaries above for new first-use eligibility.
- Validation: Round 1 discovery completed with six retained P1 candidates; independent verification had not run under the stale authorization.
- Related ADRs: ADR-0054, ADR-0051 (References above)
- Related execution plans: n/a - the original narrative names review targets rather than an execution-plan directory
- Related task id(s): n/a - no stable task identifier was captured in the original narrative
- Related run id: manual-pause-closure-protocol-r1
- Related latest.json: n/a - no canonical latest.json pointer was captured in the original narrative
- Related pipeline artifacts: `logs/ci/2026-08-01/manual-pause-closure-protocol-r1/review-candidates.json`, `logs/ci/2026-08-01/manual-pause-closure-protocol-r1/review-gate-result.json`
