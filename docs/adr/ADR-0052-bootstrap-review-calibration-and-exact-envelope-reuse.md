# ADR-0052: Bootstrap Review Calibration And Exact Envelope Reuse

- Status: Accepted
- Date: 2026-07-30

## Context

ADR-0051 bounded semantic review re-entry, but the cost estimate still used an
unversioned fixed sample count and historical runs had no reproducible
operational projection. Refactor Acceptance could revalidate an explicitly
named finalized run, but it could not prove that the run covered the current
Acceptance candidate and custody bytes.

This repository has one maintainer assisted by AI. It needs deterministic
crash and drift protection, not reviewer identities, signatures, or a general
cross-run LLM cache.

## Decision

- Bootstrap exposes `build-review-baseline` over the validated run registry or
  explicitly named formal run directories. It emits an append-only history
  index and cost-calibration candidate under `logs/`.
- Every finalized run is fully replayed. A failed finalized replay fails the
  build. Nonterminal runs remain operational rows; only complete structured
  token and process-event evidence enters a cost cohort. Token evidence is
  extracted from Codex JSONL for the same attempt, attempt directories must be
  event-backed, zero-token samples are excluded, and mixed-model runs stay out
  of single-model cohorts. The history index and calibration candidate publish
  atomically as one append-only directory.
- Generated history and calibration candidates carry `authorizes=[]`. They do
  not authorize clean status, acceptance, handoff, commit, release, or done.
- A promoted calibration is a reviewed, committed Skill reference bound by
  schema, path, and hash. Missing cohorts use its conservative fallback;
  missing or substituted promoted bytes fail closed. Promotion is never
  automatic.
- Historical exact evidence is not copied into a finding corpus. Small
  synthetic confirmed/refuted pairs are shadow-regression fixtures only and
  never enter runtime prompts or current clean decisions.
- New finalized validation envelopes expose the frozen
  `candidateBindingHash`. Legacy manifests remain replayable but produce a null
  binding and are ineligible for exact reuse.
- Refactor Acceptance may reuse one explicitly selected clean finalized run
  only after revalidating the current append-only `prepare-run` document,
  candidate manifest, declared changed paths, custody, any frozen knowledge
  context and its sources, and Bootstrap finalized evidence. The prepared
  Acceptance input, candidate manifest, frozen knowledge context, accepted
  knowledge sources must all be members of the Bootstrap frozen artifact
  binding. The complete seven-class route scope must be frozen, and every
  declared changed path must be in the route's changed-production-code class.
  The exact `prepare-bootstrap` route is bound directly by its file and
  canonical document hashes because Round 1 cannot declare a repair-route
  artifact.
- Exact reuse is emitted only through `bootstrap-import-envelope.v3`. The route
  must select full implementation conformance or focused repair, describe the
  immediate predecessor lineage state of the selected finalized run, and that
  run must be the current lineage head. Existing v2 imports remain readable
  under their original finalized v1/v2 contract but cannot grant exact reuse.
  Current profile, policy, authority, and candidate binding must still match.
- Rejected reuse does not create a semantic round and does not convert the
  existing bounded route into a pass. The caller continues that route.

This extends ADR-0041 and ADR-0051 and supersedes none. Round limits, reviewer
isolation, severity handling, model routing, and plan-local acceptance
authority do not change.

## Consequences

- Review cost estimates have explicit provenance and conservative fallback.
- Historical evidence can be compared without becoming semantic truth.
- Byte-identical finalized work can avoid a new semantic run, while any drift
  follows the existing bounded review route.
- Old runs remain useful for history and replay but cannot gain exact-reuse
  authority retroactively.

## References

- `docs/adr/ADR-0041-bootstrap-review-execution-control-plane-ownership.md`
- `docs/adr/ADR-0051-bootstrap-lineage-family-and-bounded-repair-reentry.md`
- `docs/standards/bootstrap-review-control-plane.md`
- `.agents/skills/run-phase-bootstrap-review/SKILL.md`
- `.agents/skills/run-refactor-implementation-acceptance/SKILL.md`
- `.agents/skills/vdd-execution-plan/SKILL.md`
- `.agents/skills/quick-dev-tdd-adapter/SKILL.md`
