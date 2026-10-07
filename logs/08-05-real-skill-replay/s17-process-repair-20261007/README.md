# S17 and fresh replay repair

Base: `7abdfb25dcc1342d0f2f7b3dc0dbb9268f2bd39f` on
`fix/08-05-real-skill-replay`. Accepted ADR-0058 owns this direct repair.
C3 is OPEN; `authorizes=[]`. No VDD, Quick Dev, Acceptance or live backend was
started. Phase, shared LLM entrypoints, capability authority and old Q7/Q8 are
unchanged.

## Original evidence and diagnosis

The published Windows verification ran at source candidate
`69bb7f87e28a67ee7a017d805088e2ecff7d5d35`. Of 340 collected nodes, 46 finished
before S17 timed out: 32 passed, seven call failures and seven setup errors.
The source-identity and S10 positive replay failures and S13 fixture errors are
also failures. The parent tracebacks show waiting for child output; they do not
show the fresh child's internal stack. No native JUnit was generated, and none
is manufactured here. Original evidence stays under its original directory;
the Windows copies in this directory retain the same raw Git bytes.

A real descendant-leak control reproduced the old native adapter's root-only
kill: a descendant in a separate process group wrote its leak marker after the
timeout. `transport-behavior-red-stderr.txt` preserves this failure. The first
attempt at cleanup also exposed the local container's host `/proc` versus local
PID mismatch; `transport-green.xml` retains that failed attempt. Corrected
namespace-aware cleanup and actual nested-group controls then passed. The
first `transport-red-*` invocation was a missing-pytest preflight error, not a
behavioral RED. Pytest 8.4.2 was installed and real checks were run afterwards.
`collection-control-driver-*` preserves a rejected local invocation referencing
a historical log scope file absent from the sparse working copy; it is not a
collection or suite result.

Profiling one real fresh replay on Linux located repeated syntax and call
surface analysis as a large cost. Git materialization was already batched and
was not the dominant cost. The same profiled invocation took 156.011 seconds
before and 67.596 seconds after repair. Both really passed, with 36 transition
calls and nine separately captured Prior Route baselines. Existing dependencies
were retained; the new regression file accounts for the 1536-to-1537 member
change. This measurement does not prove a Windows speedup or whole-suite pass.

## Repair

- Analyze identical source bytes once across current, historical and fresh
  checkout paths. Cache only immutable import names and call-site line numbers.
  Re-read source and rehash the complete closure and manifest on each check.
  Unknown new callers and changed source bytes still invalidate current inputs.
- Preserve original import, alias and native-command selection semantics.
  `syntax-equivalence.json` independently compares the original algorithm with
  the repaired analysis over every current Python source file.
- Use file-backed input/output and finite owned-process capture for replay
  integrations. Native execution keeps 60 seconds and 8 MiB; parent CER
  integration keeps 180 seconds and Matrix fixture capture keeps 90 seconds.
  Output exhaustion terminates execution while it is running. Native timeout,
  interruption and outer-supervisor timeout clean the owned descendants,
  including nested POSIX groups; Windows retains PID-scoped `taskkill /T /F`.
- Keep S17 on the active Python runtime. Preserve every original assertion and
  selector, real positive/negative Probes, Prior Route calls, fresh checkout and
  exact verdict/coverage/snapshot comparison.
- Persist bounded pytest failure details as soon as each failed report occurs,
  so a later timeout cannot erase preceding failures by aborting final reporting.

## Actual direct validation

Environment: Linux, Python 3.12.14, pytest 8.4.2. FastCtx was not attached;
local inspection/execution used the available command plane. Windows behavior
still requires local verification.

| Scope | Result | Evidence |
| --- | --- | --- |
| Existing regression group plus four new transport/syntax controls | 36 passed, no failures/errors/skips | `unittest-stderr.txt` |
| Direct watchdog and transport/syntax controls | 9 passed, no skips | `watchdog-published.xml`, stdout/stderr |
| Source identity, S10, S13 and S17 real replay scopes | 29/29 passed, no skips; exact coverage, all phases passed, source stable | `native-targeted/summary.json`, native JUnit, events, raw output |
| Original three pytest selectors | 340 collected | `collection-stdout.txt`, stderr |

These are separate scopes, not an additive completion metric. Native targeted
replay used the final published source bytes. Prior failures and diagnostic
attempts remain append-only. Large evidence files have lossless gzip archive
copies; `archive-manifest.json` records raw identities. Full 340-node execution
and Windows pass are not claimed by this repair.

## Windows verification

Synchronize the repair commit and preserve all old logs. First run the default
regression group plus the same 29 failure-family nodes through the observable
entry (it includes unittest automatically):

```powershell
py -3 -u -B scripts/sc/verify_skill_replay.py --scope-file logs/08-05-real-skill-replay/s17-process-repair-20261007/targeted-scope.json --expected-count 29
```

Require successful exit, 29/29 completed, no skips, `source_stable=true` and real
JUnit. If a failure or timeout remains, push that new complete evidence directory
before repeating it; immediate failure details now identify earlier failed nodes.

After targeted verification passes, run the unchanged original 340-node scope:

```powershell
py -3 -u -B scripts/sc/verify_skill_replay.py --expected-count 340
```

Both commands allocate new append-only output directories. Neither invokes a
formal workflow or grants Trust Approval. Keep C3 OPEN; do not publish
`acceptance-passed` from these direct tests.
