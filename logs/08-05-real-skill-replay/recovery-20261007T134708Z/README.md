# Fixed-source native replay recovery

Executed source: `8d9893054d7fdbb3120e4457128e6ac0bca83bde`. Accepted ADR-0058 owns the
execution, portability and non-authorizing boundaries. The earlier source
repairs remain unchanged: exact-byte syntax reuse, bounded file-backed
transport, owned process-tree cleanup, immediate failure diagnostics, and
portable CER fixtures using real production verifiers.

The original 340-node direct scope completed on Linux with 36 unittest passes,
340 pytest passes, all 1020 phase reports passed, native exit 0, no skips,
xfail outcomes or timeout, and unchanged source bytes and HEAD. Pytest itself
generated `full/junit.xml`; its 340 ordered test identities match the manifest.
The original ordered node-manifest bytes remain identical, SHA-256:
`6a6f4ac8c8825522c83c44410b9de8cfdf7fd50e1ea5b5a52b7f91169eac7232`.

Native pytest elapsed: 1872.07 seconds.
The formerly blocked S17 replay node took
38.566388 seconds from native start to finish.
The formerly interrupted S44 node took
43.494591 seconds. All four S17 nodes passed.
The per-node verification deadline remains 300 seconds; native and aggregate
Matrix deadlines remain unchanged. `targeted` also contains the separate
five-node S17/S44 check with genuine JUnit and unchanged source.

`full/summary.json`, native process results, stdout/stderr, ordered nodes,
events, traceback files, driver output, and before/after bindings are retained.
`full/consistency-audit.json` checks those original files; it does not replace
a native result or create JUnit. `audit-native-evidence.py` reproduces the
consistency checks against decompressed original bytes.

`recovered-interrupted-run` preserves newly accessible bytes from the previous
environment interruption. Its events contain 292 finished nodes with no failed
report observed. It has no terminal summary, native pytest exit result, JUnit,
or source-after; its separate recovery observation remains explicitly
unsuccessful/incomplete. The earlier checkpoint stays a historical running
observation. Original Windows failures, earlier failed/incomplete Linux runs,
and Q7/Q8 have not been rewritten.

Large files and native text are stored as lossless gzip. `archive-manifest.json`
maps original relative names to stored files and binds both raw and archive
SHA-256 hashes. Decompression restores the exact original native bytes,
including raw newline bytes; no output normalization is used to pass checks.

This is Linux with Python 3.12.14, pytest 8.4.2, jsonschema 4.26.0 and real
PowerShell 7.6.6. Native local Windows verification remains pending. After
fetching the repair branch, run the same scope in a fixed Windows checkout:

```powershell
py -3 -u -B scripts/sc/verify_skill_replay.py --expected-count 340
```

Retain that actual new summary, process results, events, JUnit, and source
bindings. Linux success is not native Windows verification. C3 remains OPEN;
formal Acceptance remains blocked; authorizes=[]. No VDD, Quick Dev, formal
Acceptance, live backend, main merge or release was invoked.
