# ADR-0054: Refactor Acceptance Manual-Pause Deterministic Closure

- Status: Accepted
- Date: 2026-08-01

## Context

ADR-0051 limits one Bootstrap lineage family to three semantic rounds and
routes an exhausted family to `manual_pause`. A confirmed Round 3 blocker can
be repaired deterministically, but the current Refactor Acceptance contract
has no typed path that distinguishes a current, complete repair from an ad hoc
waiver. Reopening Round 4 or renaming the target would defeat the bounded
review decision, while leaving every repaired target permanently unable to
reach `acceptance-passed` makes `manual_pause` an unrecoverable terminal state.

This repository has one maintainer assisted by AI. It needs exact byte and
finding closure plus an explicit maintainer decision, not signatures or a new
semantic review round.

## Decision

Refactor Acceptance owns a two-stage deterministic manual-pause closure lane.

- The lane is available only when the current repository-owned lineage
  projection has consumed exactly three rounds, reports `manual_pause`, and has
  no next round.
- It consumes the current Acceptance-produced manual-pause route and its
  hash-bound `prepare-bootstrap` producer request, canonically reprojects the
  complete route, derives the lineage family from the route review scope, the exact
  blocked Round 3 finalized v3 envelope, and every hash-bound final Bootstrap
  artifact referenced by that envelope. Bootstrap history remains immutable.
- It reloads the repository-owned Bootstrap producer and performs a complete
  historical replay of the finalized run. The saved envelope must have the
  same field set and match every replayed run-fact field. Only `generatedAt`
  and `validatorHash` may rotate, and the challenge binds the current replayed
  validator hash; selected-field or artifact-hash checks cannot substitute for
  canonical replay. The producer is loaded from the request repository's own
  Bootstrap Skill rather than the Acceptance caller's adjacent installation.
  Repository-root spellings are compared by resolved path identity.
- The exact confirmed finding set is derived from the frozen candidates and
  verifier decisions. The caller cannot omit, add, refute, or renumber a
  finding.
- Every verifier decision must be terminally confirmed or refuted. Any
  `unverified` decision, including `security` or `data_loss`, blocks this lane;
  maintainer acknowledgement cannot resolve independent-verifier uncertainty.
- Every confirmed finding maps to current changed paths, targeted tests, and
  validation references in one reproducible Round 3 repair-completeness
  projection. Composition receipts bind every producer, consumer, and targeted
  test byte, and the resolved command argv explicitly names each targeted test.
- `prepare-manual-pause-closure` publishes an append-only challenge with
  `status=awaiting-maintainer-ack` and `authorizes=[]`. It cannot publish a
  lifecycle transition.
- `finalize-manual-pause-closure` reads one immutable challenge byte snapshot,
  hashes those same validated bytes, and recomputes the challenge from
  current repository bytes. It requires an explicit maintainer acknowledgement
  bound to the challenge hash and exact confirmed finding IDs.
- Only the final schema-valid closure result publishes
  `authorizes=["acceptance-passed"]`. It does not authorize commit, release, or
  archive.
- This lane does not run a model, create Round 4, reset a lineage family,
  import a blocked Bootstrap result as clean, or reinterpret the original
  reviewer and verifier decisions.
- A change to this closure protocol must pass deterministic Skill validation
  and an independent `bootstrap-skill-route` review before its first use on a
  real exhausted target. A closure protocol cannot approve the unreviewed
  revision that introduced itself.

## Consequences

- A repaired exhausted target can reach formal implementation acceptance
  without an unbounded semantic review loop.
- Human acknowledgement cannot substitute for repair, test, receipt, lineage,
  finalized-run replay, verifier closure, or finding completeness evidence.
- Round 3 remains visibly blocked in Bootstrap history even when the consuming
  Acceptance lifecycle later advances.
- Historical targets remain unchanged unless they explicitly enter this lane.

## References

- `docs/adr/ADR-0041-bootstrap-review-execution-control-plane-ownership.md`
- `docs/adr/ADR-0051-bootstrap-lineage-family-and-bounded-repair-reentry.md`
- `docs/adr/ADR-0052-bootstrap-review-calibration-and-exact-envelope-reuse.md`
- `docs/standards/bootstrap-review-control-plane.md`
- `.agents/skills/run-refactor-implementation-acceptance/SKILL.md`
