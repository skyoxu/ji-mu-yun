# S1 Input Contract Closure

The S1 implementation contract did not permit the producer chain required by
the adopted semantic contract. `active-acceptance-manifest.v1.json` contains
seven active Acceptance IDs, while `semantic-verification.v1.json` previously
covered only `A-SEMANTIC`. S1 also materialized only semantic intent, so the
compiler could not consume the two authoritative inputs from its run root.

Repair scope:

- add the two authority inputs and the S1 input builder/materializer to S1's
  declared read/write boundary;
- align semantic verification coverage to the active seven-ID manifest;
- invalidate the old implementation authorization after contract bytes change;
- preserve all existing Quick Dev run evidence as historical and create no
  replacement RED evidence during this VDD repair.

The repair changes no product requirement, no accepted semantic disposition,
and no external review decision. It invalidates S1 and all downstream slices
because every slice consumes the repaired S1 semantic artifact chain.

The source snapshot also exposed a pre-existing S5 closure defect:
`predecessor-judge-freeze.v1.json` was declared as a plan-root source despite
being a future runtime artifact. The repair removes that plan-root reference.
S5 must derive its predecessor receipt only from its explicit run-local S3/S4
lineage when Quick Dev later implements the slice; no placeholder freeze file
is created by VDD.
