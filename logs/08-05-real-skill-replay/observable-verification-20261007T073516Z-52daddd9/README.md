# Full original-scope failed verification

Source candidate: `de6e6a4b0427bc53a8dd9d03b528be075ce0e3d5`.
Command: `python3 -u -B scripts/sc/verify_skill_replay.py --expected-count 340`.
Linux, Python 3.12.14, pytest 8.4.2, jsonschema 4.26.0; FastCtx unavailable.

The supervisor completed naturally with exit 1: 36 unittest tests passed;
all original 340 pytest nodes completed with 333 passes and seven call failures.
A real pytest JUnit report exists: 340 tests, seven failures, zero errors/skips.
`summary.json` is `direct-validation-failed`, exact coverage is true, and
`source_stable=true`. The ordered node manifest is byte-identical to the
published Windows failure manifest. S17 completed and passed without timeout.

Six failures in S14/S15/S18 require the hard-coded Windows temporary root.
S26 requires a win32 label even for a native Linux replay. These are failed
results; no failed report was converted into successful coverage. Native events,
process result, traceback, stdout/stderr and JUnit are preserved. Large files
are available as lossless gzip archives with raw identities in the manifest.

C3 remains OPEN; Acceptance remains blocked. `authorizes=[]`. No VDD,
Quick Dev, Acceptance or live backend was called. The original Windows failure,
old Q7/Q8 and historical artifact bytes are unchanged.
