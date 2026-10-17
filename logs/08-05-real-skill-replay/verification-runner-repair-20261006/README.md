# Direct verification observability repair

Base commit: `7a8ddaabd78c8da766529e27b2ae66ed2b2060c3`.
Owning decision: Accepted ADR-0058, 2026-10-06 direct verification observability.
This is a direct code repair and verification handoff. It does not publish Q8,
Acceptance, Trust Approval or a Consumer exception. `authorizes=[]`; C3 is OPEN.

## Evidence boundary

The user reported 32 successful Windows unittest cases, 587 collected pytest
cases and an interrupted full pytest run without JUnit. The reported r2
`windows-reverification-20261006-r2/summary.json` returned 404 through GitHub at
the base branch HEAD. Its exact pytest command and the hung node are therefore
not independently available here. This repair does not identify that Windows
node, claim that its underlying fault was fixed, or report Windows completion.

The earlier documented scope (two replay test files and `tc_d1_cer`) really
collects 340 tests. `scope-mismatch/summary.json` demonstrates that asking for
587 with that scope is rejected before any pytest execution. It is not a
substitute full verification of the user's 587-test scope.

## Changes

- `scripts/sc/verify_skill_replay.py` records the exact selected node manifest,
  native stdout/stderr, setup/call/teardown events, ten-second console progress,
  and sixty-second pytest-parent stack dumps. It observes tests without
  deselection, skipped fixtures or altered outcomes. Each test and each idle
  startup has a 300-second default supervisor deadline. Timeout or interruption
  terminates only its own process tree and preserves an unsuccessful summary;
  missing native pytest JUnit is never manufactured.
- The entry first runs the existing replay regression unittest group, then
  collects and executes the original selected pytest scope. Passing requires
  exact node coverage, successful actual phase reports, no skip/xfail reports,
  successful process/session termination and unchanged source identities.
  Environment selectors and automatic external pytest plugins are excluded;
  required missing plugins or fixtures produce visible errors.
- `dependency_closure` memoizes only exact-byte import syntax and repeated
  filesystem queries within one traversal. Later traversals rebuild their file
  index and rehash resources. New/deleted/changed modules are tested. Owning
  resources, fixed-point closure and immutable Git trust checks are preserved.
  No trusted baseline, capability, verdict or C3 authorization was changed.

## Actual online verification

All executions below ran on Linux with Python 3.12.14 and pytest 9.1.1.
They are separate verification scopes, not an aggregate completion metric.

| Scope | Actual result | Evidence |
| --- | --- | --- |
| Watchdog and closure freshness tests | 5 passed, no skips | `watchdog-published.xml`, stdout/stderr |
| Existing regression unittest | 32 passed, no failures/errors/skips | `unittest-stderr.txt` and `native-unit/unittest/` |
| Native repository S13 replay through the new CLI | 17 passed, no skips, source stable | `native-s13/summary.json`, native JUnit, events and process results |
| Native base replay through the final CLI | 8 passed, no skips, source stable; preceding unittest 32 passed | `native-unit/summary.json`, native JUnit, events and process results |
| Exact-scope mismatch control | 340 collected; expected 587 rejected before execution | `scope-mismatch/summary.json`, selected node manifest and native collection output |

The initial watchdog run genuinely failed because a helper name beginning with
`pytest_` was interpreted as an unknown pytest hook. Its failed XML/stdout and
`plugin-debug/` are retained. The helper was renamed and the real tests rerun.
The S13 demonstration preceded the final additional guard against failed or
skipped subtest reports being hidden by a passing parent report. Final watchdog
and native base replay evidence cover the published guard.

Closure measurements are independent performance diagnostics: the original
1534-member closure took 3.8409 seconds. The repaired 1536-member closure took
3.5737 seconds cold and 1.4631 seconds warm in that measurement. No prior member
was removed; the two new source files were added. This is not a whole-suite
speedup claim. The measurement preceded the appended ADR text.

Large raw JSON/collection files have lossless `.gz` archive copies for GitHub
publication; `archive-manifest.json` records original names, lengths and SHA-256
identities. Empty native output files are preserved. Prior Windows, Q7/Q8 and
compiler history are untouched.

## Windows handoff

Synchronize the published repair commit without deleting existing logs. Do not
start VDD, Quick Dev, Acceptance or a live backend for this verification.

First run the small runner regression group, which also exercises native
Windows owned-process cleanup:

```powershell
python -B -m pytest -q scripts/sc/tests/test_skill_replay_verification.py
```

To rerun the earlier documented 340-test scope, use the observable entry:

```powershell
python -u -B scripts/sc/verify_skill_replay.py --expected-count 340
```

To reproduce r2's 587-test scope, first recover the original pytest selectors
from the r2 summary or raw command. Save those same selectors as a UTF-8 JSON
array in a new repository-relative file, for example
`logs/08-05-real-skill-replay/windows-r2-scope.json`, then run:

```powershell
python -u -B scripts/sc/verify_skill_replay.py --scope-file logs/08-05-real-skill-replay/windows-r2-scope.json --expected-count 587
```

Do not guess selectors, reduce the count, omit failing nodes or reconstruct a
pass from collection alone. If r2 did not record its command, publish its raw
evidence to resolve the scope first. Every invocation chooses a new output
directory and prints it. Existing output directories are refused, not reused.

On failure, retain and push the full new directory: summary, process results,
selected node manifest, events, stack dumps, native output and any genuine
JUnit. The summary will identify timeout, process failure, changed source or a
scope mismatch. The next investigation should target the recorded node/phase;
do not blindly repeat a silent full run or raise deadlines without evidence.

No Windows whole-suite pass or Acceptance readiness is established by this
commit. C3 remains OPEN and formal sealing remains blocked.
