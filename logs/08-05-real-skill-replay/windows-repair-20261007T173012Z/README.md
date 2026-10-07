# Windows replay repair: fixed-source Linux verification

The original 340-node direct scope passed on Linux at source commit
`ae311a29b15c8c75fb0dcaaa1c57c8cb9bd5ac7e`: 41 unittest tests and 340 pytest
tests passed, with zero skips or xfail outcomes. Pytest exited zero after
1549.328 seconds and produced the real `full/junit.xml` with 340 test cases.
All 1020 setup/call/teardown reports passed. The ordered node manifest is
byte-identical to the original scope, and all 1539 source bindings and HEAD
are unchanged before and after execution. This is direct Linux validation;
native Windows verification remains pending. C3 is OPEN and Acceptance is blocked.

The previous native Windows result remains unsuccessful and unchanged at
`e461d19e558b75db60c0fecdcfc32a34a9e22a5f`, under
`logs/08-05-real-skill-replay/observable-verification-20261007T150204Z-ec03037f`:
318 finished nodes, 54 unique failing nodes, 22 unfinished nodes, an
`0xC0000005` exit, and no native JUnit. `failure-analysis.json` binds its actual
event, stderr and traceback Git blobs and retains all failed node identities.

## Repair and validation

The Accepted ADR-0058 implementation contains Windows descendants in unnamed,
non-inheritable kill-on-close Job Objects. Each owned child starts suspended,
joins its job, and then resumes its initial thread. Explicit Win32 signatures
preserve pointer widths, assignment failures fail closed, and cleanup drains
descendants before closing transport files, including after normal leader exit.
CER replay and Matrix parents now share the owned file-backed transport.
Windows API integration still requires execution on the original machine.

Traversal-local directory/import indexes eliminate repeated missing-path probes
while preserving fresh membership, byte hashes and immutable trust checks on
every next traversal. S2/S4 digest oracles use literal POSIX UTF-8 path ordering.
S19 uses the bound interpreter. Periodic Python stack snapshots replace the
recurring C-level watchdog; the native crash cause is not proven and no Windows
crash-resolution claim is made. Native process diagnostics record actual PIDs,
commands, budgets and terminal outcomes without logging stdin.

`assertion-preservation.json` verifies unchanged test selectors, decorators and
assertion ASTs in the 21 changed CER files. `closure-traversal-comparison.json`
records byte-identical conservative bindings on the same immutable baseline.
`process-controls-junit.xml` is real native pytest output: 22 process, Win32 ABI
and verifier controls passed. A separate six-test verifier unittest run also
passed, including controls that reject incomplete or skipped verification.

The complete run contains 5085 native process diagnostic files: 5082 terminal
exits and three unsuccessful terminal records from intentional timeout/output
budget negative controls. Every file has its actual start and terminal record.
All 54 previously failing Windows nodes passed on Linux. S17's detached replay
took 32.977824 seconds; the former final S7 node took 34.665108 seconds.
These timings do not substitute for native Windows timings.

Native child and aggregate Matrix limits remain 60 seconds and 8 MiB. Replay
integration parents retain 180 seconds, Matrix parents retain 90 seconds, and
the direct per-node supervisor retains 300 seconds. No semantic result,
assertion, skip or execution authority is relaxed.

## Evidence transport

`full/summary.json`, `closeout.json` and `full/consistency-audit.json` describe
the direct result and its source, node, phase and native JUnit checks. Native
stdout/stderr, event streams, traceback files, source snapshots and process
results are preserved losslessly. Files stored with `.gz` decompress to their
original bytes; `archive-manifest.json` records raw and stored SHA-256 hashes.
`full/native-processes.tar.gz` contains every original native process JSONL;
`full/native-processes-archive-index.json` binds each member's original bytes.
The audit and transport scripts grant no execution or Acceptance authority.
Prior failed evidence and Q7/Q8 records are not rewritten.

## Required native Windows recheck

After updating the authorized `fix/08-05-real-skill-replay` branch, run the same
full scope from the repository root without editing sources during execution:

```powershell
py -3 -u -B scripts/sc/verify_skill_replay.py --expected-count 340
```

The optional `targeted-windows-failed-nodes.json` is the exact 54-node historical
failure list for diagnosis via `--scope-file`; it does not replace the required
full 340-node verification. A pass still requires all 340 nodes, all native
phases, zero skips, zero process exit, real JUnit and stable source bindings.
No VDD, Quick Dev, formal Acceptance or live backend workflow was invoked.
Every receipt remains `authorizes: []`.
