# S34 FR-6 Split Handoff Diagnostic

The canonical published-repair compilation reached V1, V3, V4, V5, V6, V7,
and final validation. The FR-6 split was consumed as two active obligations and
the former `O-8E718A411378` identity was removed. V6 accepted the one-to-two
slice expansion as `S34-R1` and `S34-R2`.

The compiler returned `repair-vdd` only at the Quick Dev handoff gate. The
machine findings are:

- Existing assertion-marker mismatches: S2, S4, S6, S7, S24, S25, S26, S28,
  S31, S32, S40, S41, S42, and S44.
- S34-R1 and S34-R2 also require new assertion markers because the reviewed
  split created two independent Acceptance assertions.

This is not evidence that the FR-6 split contract failed. It is a repository
call-surface binding mismatch between existing test files and the current
semantic plan. The predecessor was already plan-ready, so unrelated historical
slice markers are not repaired in this S34-only round. No handoff gate is
weakened, no old evidence is re-authorized, and C3 remains OPEN.

Machine result: `compiler-result.json` in this directory; status
`repair-vdd`, stage `quick-dev-handoff`.
