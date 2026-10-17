# Resume the two V4 binding repairs

Baseline: `0ecdf97e82e3360175dc390c42106943da77e6cb`.
The existing failed directory remains `repair-vdd`. This input does not claim
`plan-ready`, implementation completion or Acceptance. C3 remains OPEN.

## Corrections

- `O-DE636F1F6D78`: replace the seed-artifact check with an actual non-owner
  lifecycle publication attempt, denial/no-publication observations and a
  matched current-owner positive control. Use the existing S27 planned test
  and deterministic finalization production owner. The failure is an executable
  expected-RED role; missing approvals and fixture/setup failures are not RED.
  Keep seed `authorizes=[]` under its independently covered obligation.
- `O-53C2E081003F`: use current obligation-scoped assertions and a dedicated
  root-escape failure marker, retaining rejection before validator execution
  and absence of a trusted result.

These are candidate contracts, not performed test cases or semantic approval.
No test placeholders, production changes or historical evidence edits are made.

## Local Windows resume

Run from the repository root after syncing this branch. Keep the original
compiler caches and failed attempts. The requirements file is unchanged, so
existing stage caches remain eligible under the compiler's ordinary identity
checks. Do not use `--worker-cache` to import a passing result.

```powershell
$scope = "execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/repair/round-7/recompilation-4/cer-repair-1"
py -3 scripts/vdd/compile_plan.py --requirements "$scope/compiler-requirements.md" --out-dir "$scope/s1-q6-selector-repair/current-plan" --profile self-hosted --resume-from first-failed-stage --v3-contract-repair "$scope/v4-binding-repair-1/candidate-contracts.json" --result-json "logs/08-05-real-skill-replay/v4-binding-repair-1/compiler-result.json"
```

V1/source recall and unselected V3 contracts are not deliberately invalidated.
V4 must assess the changed contracts; downstream identities and gates must be
recomputed as necessary. This command does not promise V4-only execution.
The ordinary repair budget remains unchanged. If compilation fails, preserve
its result/progress and stop rather than repeating the same attempt or manually
promoting it. Resume Quick Dev only after the canonical result is `plan-ready`;
use its newly published assertion/selector identities and fresh case evidence.
S1's completed production implementation is not reopened by this repair.
