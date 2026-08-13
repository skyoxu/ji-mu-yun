# Requirements And Acceptance

The normative universe is the typed Canonical Spec Package graph:

- canonical root: `_bmad-output/specs/spec-vdd-conformance-exact-cover/SPEC.md`
- six `normative_companion` files under that package
- adopted Architecture Spine
- content-addressed selection record and current pointer

`execution-plans/2026-08-10-vdd-conformance-exact-cover-requirements.md` is
recorded only as provenance and contributes no active obligation.

Coverage must include VCEC-001 through VCEC-043, with every active obligation
mapped to at least one falsifiable acceptance and every acceptance mapped back
to an obligation. `authorizes` is always `[]` in VDD and exact-cover artifacts.

Important non-goals: no producer attestation, no lifecycle transition owned by
exact-cover, no copied VDD schema in exact-cover, no Chapter 5 dependency, no
automatic Bootstrap launch, and no Codex resume guarantee.
