# Requirements And Acceptance

The normative universe is the typed Canonical Spec Package graph:

- canonical root: `_bmad-output/specs/spec-vdd-conformance-exact-cover/SPEC.md`
- six `normative_companion` files under that package
- adopted Architecture Spine
- content-addressed selection record and current pointer

`execution-plans/2026-08-10-vdd-conformance-exact-cover-requirements.md` is
recorded only as provenance and contributes no active obligation.

The requirement universe is exactly `VCEC-001..VCEC-036`; the acceptance
universe is exactly `VCEC-A01..VCEC-A43`. Every requirement is mapped to one or
more falsifiable acceptance IDs, implementation slices, and registered
commands; every acceptance maps back to one or more requirements. The complete
forward and reverse mapping is authoritative for this plan at
`repair/round-1/requirements-acceptance-slice-command.v1.json`. `authorizes`
is always `[]` in VDD and exact-cover artifacts.

Important non-goals: no producer attestation, no lifecycle transition owned by
exact-cover, no copied VDD schema in exact-cover, no Chapter 5 dependency, no
automatic Bootstrap launch, and no Codex resume guarantee.
