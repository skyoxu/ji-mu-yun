# S34 FR-6 Split V4 Source-Gap Diagnostic

The successor consumed the reviewed FR-6 split and V4 alignment addendum.
V4 coverage completed with 115 active obligations, precision 1.0, and no
invented obligations. Quick Dev handoff marker mismatches were reduced to zero
by adding explicit assertion bindings to existing test files; no test behavior
or production code was changed by those bindings.

The compiler still returned `repair-vdd` at V4 because the canonical source
recall identified three source-bound gaps:

1. FR-13 requires `authorizes` to be machine-verifiably present on every
   derived artifact, not merely empty when present.
2. FR-4 requires execution of the detached positive Probe as a real process.
3. FR-4 requires execution of the detached negative Probe as a real process.

No existing reviewed repair input in this round authorizes these three new
obligations. They must not be inferred from historical evidence or satisfied by
test-count/marker changes. C3 remains OPEN and all derived artifacts retain
`authorizes=[]`.

Machine result: `compiler-result.json` in this directory; status `repair-vdd`,
stage `V4`, with three `source_gap_claims`.
