# Windows P1 verification candidate

This branch transports the complete reviewed2abfbccbe532f6d934d3bba36d00c915207f5e38 content plus the exact8-file P1/static-binding overlay, its two native successor plans and selected raw originals. It is not merely host HEAD5b585094 and does not claim that this publication commit already passed tests.

The fixed commit containing this file is the Windows candidate identity. Actual prior Linux runs retain their original host/dirty-overlay hashes; no original receipt was changed. The verification branch history is retained through its prior4012465d commit. No merge or force push is used. The former BMAD-only PRD query hook is absent as already scoped out.

## Entry points

- [Publication manifest](publication-manifest.json): complete source hashes, raw original transfer inventory, active plan and workflow delta.
- [Actual repair report](../../logs/stage5-p1-native-20261026/REPORT.md), [native result summary](../../logs/stage5-p1-native-20261026/result-summary.json), [raw evidence index](../../logs/stage5-p1-native-20261026/evidence-index.json).
- [VDD bounded-mode regression](../../logs/stage5-p1-vdd-binding-fix-20261026/REPORT.md).
- [Current successor plan](../../execution-plans/2026-10-26-vdd-knowledge-query-p1-static-bindings/semantic-plan-bundle.v1.json).
- [Original complete scope/input and historical evidence entry](../stage5-review-20261026/README.md): its prior completion claims are historical, superseded for current applicability by the P1 report.
- [Exact11 runtime nodes and limitations](../../logs/stage5-p1-native-20261026/WINDOWS-PENDING.json).

## One authorized trigger

The push to verify/bmad-vdd-knowledge-query-windows triggers the existing ci-windows.yml knowledge-query-platform job. Its only workflow changes are full-history checkout and the11 explicit current runtime nodes. Runner windows-2022, Python3.12, pytest8.3.5, 1800 total/600 genuine-output inactivity supervision and windows-query-verification artifact outputs remain unchanged. Do not add a duplicate workflow_dispatch. The user monitors the run. No CI status is asserted by this manifest.

The11 cases cover path/Unicode, real process/output limits, cancellation, nonzero exit and deadlines. They do not execute the7 added P1 cases, complete VDD/QuickDev or replace every historical13-case Windows scenario.

## Result binding and pending work

After the user reports this run, preserve the downloaded original ZIP in a new location. Verify commit, platform, source hashes, exit code, all JUnit nodes/no skip and supervision before consumption. The old ZIP remains unchanged. The3 old-reader bindings still require an explicit new-original binding. Current Linux Q6/terminal/Q7 and whole-plan Q8 are not established by a Windows workflow success; affected proof refresh remains pending. No Acceptance, A/B, PR, merge or release is implied.
