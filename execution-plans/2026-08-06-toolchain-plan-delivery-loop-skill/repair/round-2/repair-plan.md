# Repair Round 2 - Terminal Implementation Authorization Gate

- Repair type: confirmed Bootstrap P1 repair
- Predecessor review: `toolchain-plan-delivery-loop-bootstrap-r1-retry-20260806`
- Finding: `BSR-021C56320E84F1EB`
- Lifecycle authority: `authorizes=[]`

## Root Cause

`tools/validate_implementation.py` ran the plan validator with
`--implementation-state`, which permitted `plan-ready`, then emitted
`implementation-complete` authorization after terminal checks. That skipped
the maintainer-owned `implementation-authorized` lifecycle transition.

## Repair

Add a deterministic lifecycle-entry check before terminal implementation
validation. It accepts only `implementation-authorized` with maintainer
ownership or an idempotent `implementation-complete` state with Quick Dev
ownership. All other states fail with a stable typed diagnostic.

## Validation

- RED: terminal validation from the current `plan-ready` state returns
  `implementation-authorization-required:plan-ready` and no authorization.
- GREEN: focused tests cover rejected `plan-ready` and accepted
  maintainer-owned entry; plan and validator test suites pass.
- Composition: the implementation validator test suite imports and executes
  the terminal validator's lifecycle-entry function.

## Review Scope

`repair/round-2/` is the minimal complete repair closure directory: it holds
the exact predecessor finding binding, changed-set hashes, root-cause
inventory, registered commands, and controlled RED/GREEN receipts. The
focused verifier receives this directory together with the two changed source
artifacts, their direct consumer, lifecycle authority, and repository rules.

## Recovery

Preserve the finalized Bootstrap evidence and Round 1 repair. If the repair
does not validate, revert only this round's candidate changes and retain all
recorded failures. This upstream-plan predecessor is not eligible for the
implementation-only focused-repair profile, so re-entry uses the same
`bootstrap-upstream-plan` profile with an explicit typed finding-mode
authorization, the same lineage family, and this bounded repair closure.
