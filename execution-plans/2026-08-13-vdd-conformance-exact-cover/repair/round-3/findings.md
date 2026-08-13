# Repair Round 3 Findings

Source: `docs/know21.txt`. This round is opened by three novel P0 findings and
two P1 findings affecting command truth, terminal lifecycle ordering,
composition evidence, and repair closure binding. The prior Round 2 findings
remain historical and are not reopened.

| ID | Disposition | Repair |
| --- | --- | --- |
| P0-1 | fixed | Replace metadata-only implementation commands with fail-closed entry points that require implementation evidence; separate repair validation. |
| P0-2 | fixed | Remove lifecycle-state precondition from terminal-full; validate candidate evidence first and leave lifecycle publication to its owner. |
| P0-3 | fixed | Point all registry implementation and terminal commands to Round 3 entry points; retain no competing Round 1 terminal truth. |
| P1-1 | fixed | Execute producer-to-consumer composition through a controlled command and bind the actual execution outputs and input bytes in its receipt. |
| P1-2 | fixed | Bind the finalized finding digest, predecessor finding digest, and generated Round 3 callsite inventory in closure. |
| P2 | accepted follow-up | The validator-freshness regression remains behaviorally guarded by the production freshness check and is retained as a targeted static regression; it does not expand this round. |
