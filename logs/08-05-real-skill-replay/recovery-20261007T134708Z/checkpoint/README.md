# Native recovery checkpoint

Source remains fixed at `8d9893054d7fdbb3120e4457128e6ac0bca83bde`.
The four S17 nodes and the previously interrupted S44 node passed natively
with unchanged source and genuine pytest JUnit. The full 340-node run is
still running at this checkpoint; this directory grants no full-suite pass.

Previously inaccessible native files from the interrupted run are copied
byte-for-byte to `../recovered-interrupted-run`. They contain 292 finished
nodes, zero failed reports observed, and no terminal summary, JUnit, pytest
exit observation or source-after. `recovery-observation.json` is a separate
recovery observation, not a reconstructed native verdict.

The checkpoint archive manifest maps compressed files to their original
relative names and SHA-256 hashes. Decompression restores exact native bytes.
The original Windows S17 failure, Q7/Q8, and earlier failed/incomplete runs
are unchanged. Native Windows verification is pending. C3 remains OPEN;
Acceptance remains blocked; authorizes=[].
