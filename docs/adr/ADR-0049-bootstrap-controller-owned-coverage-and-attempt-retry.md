# ADR-0049: Bootstrap Controller-Owned Coverage And Attempt Retry

- Status: Accepted
- Date: 2026-07-28

## Context

ADR-0041 assigns Bootstrap execution and formal evidence to the repository
control plane. In repeated Codex Exec runs, discovery reviewers were also asked
to reproduce the complete ordered Artifact View path arrays in their candidate
JSON. Semantically useful responses were repeatedly rejected because one path
was omitted, reordered, duplicated, or emitted as malformed JSON. Operators
then treated attempt transport defects as new semantic rounds or successor
lineages, causing a bounded review to loop without adding review value.

Implementation-conformance callers also tended to pass entire Skill, plan,
source, test, document, or evidence directories. That increased review cost
and made unrelated P2 observations more likely even when the actual consumer
closure was small.

## Decision

Bootstrap separates controller evidence, child semantics, transport attempts,
and semantic rounds.

- A Codex discovery reviewer returns semantic status, findings, and a compact
  `bootstrap-artifact-view-read-receipt.v1` bound to the frozen Artifact View
  manifest hash and artifact count. It does not return coverage path arrays.
- The parent validates the same-session access handshake and compact receipt,
  then constructs formal `requiredArtifacts`, `readArtifacts`, and
  `missingArtifacts` from the frozen manifest in canonical order.
- Manual and specialized-agent modes retain explicit formal coverage because
  their reads occur outside the repository-owned Codex process boundary.
- Child launch or exit failure, malformed strict JSON, invalid binding, invalid
  compact receipt, or invalid candidate shape is a transport attempt failure.
  It appends `attempt-failed`, preserves formal output bytes, and may retry the
  same role in the same run. It consumes no semantic round and requires no
  successor lineage.
- Bounded implementation, Skill-route, and focused-change profiles use the
  smallest complete consumer closure. Explicit files are the default. A
  directory scope requires the exact
  `directory-is-minimal-complete-closure` attestation and remains subject to
  complete Artifact View coverage.
- A clean or P2-only finalized predecessor does not trigger another complete
  semantic review. P2 findings are disposed in the current run and use typed
  targeted closure or recheck evidence.
- Consumer workflows keep the original execution-plan directory as their
  acceptance target unless a separate explicit supersede or incompatible-
  scope decision exists.

This ADR extends ADR-0041, complements ADR-0045, and supersedes neither. It
does not change reviewer isolation, verifier independence, the three-round hard
limit, profile authority, provider routing, plan-local acceptance, protected
handoff, release, commit, or done authority.

## Consequences

- Reviewer output is smaller and deterministic coverage bookkeeping cannot
  fail because a model reproduced a long path list incorrectly.
- A compact receipt is an execution binding, not proof of model cognition;
  complete semantic reading remains a reviewer instruction and review
  invariant.
- Transport failures remain auditable without consuming the review budget.
- Review cost follows the affected consumer graph instead of repository
  directory size by default.
- Historical formal reviewer output and finalized evidence remain compatible.

## References

- `docs/adr/ADR-0041-bootstrap-review-execution-control-plane-ownership.md`
- `docs/adr/ADR-0045-bootstrap-verifier-semantic-commit-and-recovery.md`
- `docs/standards/bootstrap-review-control-plane.md`
- `.agents/skills/run-phase-bootstrap-review/SKILL.md`
- `.agents/skills/run-phase-bootstrap-review/schemas/bootstrap-artifact-view-read-receipt.v1.schema.json`
