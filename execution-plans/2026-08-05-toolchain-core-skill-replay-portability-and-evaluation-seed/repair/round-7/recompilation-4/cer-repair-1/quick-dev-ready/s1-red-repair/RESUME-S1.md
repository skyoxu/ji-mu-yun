# Resume S1 after explicit runtime RED binding

Current plan: this directory's `current-plan/`.
Predecessor: `../current-plan/` at commit 699b2b01.

Only S1's failure-role binding, selector explanation and context changed.
S2-S45 slice records and contexts are identical to the predecessor. Requirements,
acceptance oracles, production write sets, existing tests and original failure
intents were not changed. No VDD semantic worker or unrelated slice ran.

The original `FI-6AED86AC07D0` remains `target-binding-failure`. A separate
expected-red intent now binds the same failure marker:
`UNVERIFIED-CANDIDATE-EXTERNAL-TRUST-REJECTED`. The case-contract therefore
accepts a real failing machine assertion of S1's unchanged oracle. Emitting
that marker on its own, during setup, or from a non-assertion exception still
fails closed. Human approvals and C3 permissions are unchanged.

After synchronizing the branch:

1. Read the Quick Dev Skill and this successor's S1 context and repair report.
2. Preserve the failed S1 run. Start a fresh S1 current-run and bind current
   source/plan/descriptor identities. Keep the already-authored S1 test if it
   correctly asserts the unchanged oracle; do not edit it to manufacture RED.
3. Run S1 preflight, materialize a fresh descriptor and run a fresh probe.
   Inspect its case-contract for the marker above. Missing behavior then
   requires a fresh formal RED before production implementation.
4. Continue S1 through GREEN, REFACTOR and its required gates. This repair
   requests no rerun of VDD or unaffected slices. Do not copy old receipts
   across plan hashes; retain completed evidence until the consumer resolves
   its actual dependency/identity requirements.

Online verification covers the mapping and controlled probe-to-RED behavior,
including wrong-marker/setup/non-assertion rejection. The user's local S1
source and run evidence were not pushed and were not replayed online.
Windows execution and the actual S1 implementation remain local work.
