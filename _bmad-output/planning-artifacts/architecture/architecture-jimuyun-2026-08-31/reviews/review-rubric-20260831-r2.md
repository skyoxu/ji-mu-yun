# Architecture Spine Rubric Review — 2026-08-31 (r2)

Target: `ARCHITECTURE-SPINE.md` (feature-altitude build substrate)

Review basis: current spine revision and the canonical SPEC kernel/companions. The spine was not modified by this review.

## Gate verdict

**Needs revision before finalization.** The spine now fixes the previously material trust-boundary, staged-cover, terminal-closure, selector-identity, failure-layer, and NN+1 issues. One high-severity source-of-truth conflict remains in the architecture memlog and two medium consistency/closure items should be cleaned up before setting `status: final`. No CAP-1…CAP-10 contradiction is present in the rendered spine.

## Critical / high findings

### H1 — Architecture memlog still contradicts the rendered writer split

The rendered AD-3/AD-4/AD-6 correctly assign process receipts to the executor, observations/classification to the independent judge, runtime assertion edges to the runtime-edge validator, and coverage/completion artifacts to their named gate roles. However, the architecture run's canonical `.memlog.md` still contains the earlier decision that “Quick Dev 是 descriptor、run state、RED/GREEN/REFACTOR receipt/observation 的唯一写者”. Because the spine is re-derived from the memlog, a future update can silently reintroduce the exact receipt/observation authority ambiguity that this revision removed.

**Disposition:** append a superseding memlog decision with `memlog.py` (do not hand-edit the log) stating that Quick Dev owns descriptors, run state and recovery projection only; the executor is the sole process-receipt writer; the independent judge/observation validator is the sole observation/classification writer; and the runtime-edge validator is the sole runtime-edge writer. Then re-distill and rerun the gate. This is a source-of-truth repair, not a new CAP.

## Medium findings

### M1 — Operational envelope needs an explicit local-only deployment statement

AD-13 usefully fixes the initial Windows/`py -3`/pytest baseline, repository-root cwd, containment, atomic evidence writes and the Deferred triggers for concurrency, quotas, retention and cross-platform execution. The spine does not explicitly state whether deployment/provider strategy is intentionally local-only for v1 or which owner decides process isolation, timeout/resource enforcement and cleanup operations. At feature altitude this can still let two adapters choose different launch or cleanup behavior while both claim conformance.

**Disposition:** add one compact invariant or Deferred row: v1 is repository-local (no remote provider/service deployment); executor/adapter owns shell-free process isolation, timeout and containment; retention/cleanup and concurrent-run policy remain Deferred with triggers before those features are enabled. Do not invent a provider choice.

### M2 — Duplicate Deferred entry for unexpected-green proof

The Deferred table lists “unexpected-green proof” twice (with materially identical rationale and trigger). Duplicate rows make status tracking and later resolution ambiguous.

**Disposition:** keep one row with the existing re-decision trigger and remove the duplicate during the next memlog-derived render.

### M3 — Draft lifecycle is not yet a final handoff

Frontmatter still says `status: draft`. That is appropriate while this r2 gate is open, but it is not a finalized architecture handoff.

**Disposition:** after H1 and the chosen M1/M2 cleanup are applied and the complete Reviewer Gate passes, set `status: final` and append the `spine finalized` event. Do not claim final readiness while it remains `draft`.

## Good-spine checklist

| Check | Result | Notes |
| --- | --- | --- |
| Named paradigm and coherent model | pass | Hexagonal, append-only evidence pipeline is explicit. |
| Divergence points for VDD, Quick Dev, executor/judge, SUT, coverage gate, coordinator | pass in rendered spine; H1 source conflict | AD-1, AD-3, AD-4 and AD-6 are explicit; memlog must be corrected. |
| Every AD has Binds/Prevents/Rule and is enforceable | pass | AD-1…AD-13 all carry the three fields; rules name owners and gates. |
| SPEC CAP-1…CAP-10 represented | pass | Capability map covers all ten; no scope contradiction found. |
| Layered result legality and exact cover | pass | AD-5/AD-7 define legal combinations and sound-and-complete many-to-many cover. |
| V5/V6/V6A ordering and stage scope | pass | AD-2 fixes pre-slice versus final plan cover and ordered full stage scope. |
| RED/GREEN/REFACTOR identity and write-set isolation | pass | AD-8/AD-9 bind selector/target/fixture/assertions/cwd and successor write sets. |
| NN+1 promotion and frozen judge | pass | AD-10 supplies content-addressed, detached, read-only minimum gate. |
| Reuse, invalidation and recovery | pass | AD-11 names a repository-owned versioned impact resolver and predecessor minimum. |
| Named technologies verified current | pass with evidence follow-up | Python/pytest versions and verification date are recorded in AD-13/Stack. |
| Brownfield roots/conventions ratified | pass | Structural seed names the existing skill and plan-local roots; dispatcher exception is scoped. |
| Operational/environmental envelope | partial (M1) | Execution baseline is fixed; local deployment/provider and cleanup ownership should be explicit. |
| Deferred decisions have non-silent triggers | partial (M2) | Triggers are concrete, but duplicate unexpected-green row should be removed. |

## Recommended gate outcome

Do not set `status: final` yet. First append the H1 superseding ownership decision to `.memlog.md`, re-render the spine, and clean up M1/M2 as a single revision. Then rerun deterministic lint and the complete Reviewer Gate against the new frozen revision. If the local-only deployment boundary is intentionally already covered by the SPEC assumption, it may be marked explicitly N/A rather than adding a new decision; the trigger and ownership must still be visible.

