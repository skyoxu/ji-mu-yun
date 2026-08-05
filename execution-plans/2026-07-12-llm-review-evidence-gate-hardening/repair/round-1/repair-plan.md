# Repair Round 1 - Scope And Ownership Correction

- Repair type: user-directed VDD scope repair
- Predecessor: original 7-12 plan-ready directory and current repository
  Bootstrap/Acceptance implementation
- Finalized semantic finding set: empty; this repair is not a P0/P1 review
  re-entry and consumes no Bootstrap semantic round
- Lifecycle authority: `authorizes=[]`

## Trigger

The original plan mixed Toolchain review control, dated 7-07/7-11 review
coordination, BMAD/GDS adaptation, and Phase-facing Codex integration. The
repository has since implemented the durable Bootstrap owner, Refactor
Acceptance routing, baseline/cost projections, and bounded review lifecycle.
The remaining plan would duplicate current capabilities and incorrectly wait
on Phase feature plans.

## Repair Slices

1. Replace the current index with a v2 scope and preserve old books as
   compatibility/history.
2. Add current requirements, implementation contract, command registry,
   lifecycle/resume state, baseline/scope, and continuity report.
3. Relocate R4 to existing 7-11 PBR ownership without adding a new PBR family.
4. Add a terminal validator that composes the old 7-12 and 7-11 validators and
   checks current non-overlap and knowledge readiness.

## RED, GREEN, And Recovery

- RED/legacy regression: both historical directory validators must pass before
  the repaired plan can be declared ready; current VDD knowledge preflight is
  blocked while the Current Catalog is stale and publication controls are
  dirty. VDD has no publication authority.
- GREEN: the new terminal validator passes with a ready frozen knowledge
  context, exact requirement/slice closure, R4 receiving markers, and both
  historical validators green.
- Recovery: keep the plan `draft`, preserve all original artifacts, remove no
  historical evidence, and retry the knowledge step only after current-main
  publication controls are stable. Publication requires a separate explicit
  maintainer confirmation through `maintain-knowledge-base`; VDD resumes only
  at context freeze.

## Review Re-entry Boundary

No Bootstrap review is requested by this repair. Callsite inventory,
producer/consumer composition receipts, and a hash-bound repair closure become
mandatory only if a later P0/P1 implementation repair re-enters semantic
review. This draft must not fabricate those artifacts.
