# Repair Round 3 - Bootstrap Closure Re-entry Binding

- Repair type: confirmed Bootstrap P1 batch repair
- Predecessor review: `toolchain-plan-delivery-loop-bootstrap-r2-20260806`
- Findings: `BSR-2CCF3C796120E47B`, `BSR-4328DC7A5835A76A`
- Lifecycle authority: `authorizes=[]`

## Repair

Point the closed repair state at the Bootstrap-compatible closure for the same
round, and validate that a closed Round 2-or-later repair has exactly that path
and schema version. The VDD closure remains retained as planning evidence; it
is not used as a Bootstrap re-entry input.

## Validation

- RED: a closed repair with a VDD-style closure path is rejected by
  `resume-bootstrap-repair-closure-path-invalid`.
- GREEN: the current plan has a round-matched Bootstrap closure path and the
  plan validator tests pass.

