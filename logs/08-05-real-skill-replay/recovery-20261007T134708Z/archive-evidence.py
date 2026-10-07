"""Prepare lossless, append-only native evidence for Git transport (ADR-0058)."""
from pathlib import Path
import argparse
import gzip
import hashlib
import json

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]


def save_new(path, raw):
    if path.exists():
        assert path.read_bytes() == raw, "Refusing to replace different evidence: " + str(path)
    else:
        with path.open("xb") as stream:
            stream.write(raw)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()
    closeout = json.loads((RUN / "closeout.json").read_bytes())
    assert closeout["full"]["status"] == "direct-validation-passed"
    assert closeout["full"]["finished_nodes"] == 340
    assert closeout["full"]["unittest_passed"] == 36
    assert closeout["native_windows_verified"] is False
    assert closeout["C3"] == "OPEN" and closeout["Acceptance"] == "blocked"
    full = closeout["full"]
    durations = full["timeout_regression_nodes"]
    s17 = next(row for row in durations if row["nodeid"].endswith(
        "test_detached_replay_binds_input_and_output_to_same_probe_identity"))
    s44 = next(row for row in durations if row["nodeid"].endswith(
        "test_fresh_checkout_contains_coverage_and_identity"))
    text = f'''# Fixed-source native replay recovery

Executed source: `{closeout['source_commit']}`. Accepted ADR-0058 owns the
execution, portability and non-authorizing boundaries. The earlier source
repairs remain unchanged: exact-byte syntax reuse, bounded file-backed
transport, owned process-tree cleanup, immediate failure diagnostics, and
portable CER fixtures using real production verifiers.

The original 340-node direct scope completed on Linux with 36 unittest passes,
340 pytest passes, all 1020 phase reports passed, native exit 0, no skips,
xfail outcomes or timeout, and unchanged source bytes and HEAD. Pytest itself
generated `full/junit.xml`; its 340 ordered test identities match the manifest.
The original ordered node-manifest bytes remain identical, SHA-256:
`{full['ordered_manifest_raw_sha256']}`.

Native pytest elapsed: {full['native_pytest_elapsed_seconds']} seconds.
The formerly blocked S17 replay node took
{s17['native_event_duration_seconds']} seconds from native start to finish.
The formerly interrupted S44 node took
{s44['native_event_duration_seconds']} seconds. All four S17 nodes passed.
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
'''
    save_new(RUN / "README.md", text.encode("utf-8"))
    files = [p for p in sorted(RUN.rglob("*")) if p.is_file()
             and p.suffix != ".gz" and p != RUN / "archive-manifest.json"]
    rows, archives = [], []
    for path in files:
        raw = path.read_bytes()
        stored = path
        if path.suffix in (".txt", ".jsonl", ".sha256") or len(raw) > 131072 or b"\r" in raw:
            stored = path.with_name(path.name + ".gz")
            if stored.exists():
                assert gzip.decompress(stored.read_bytes()) == raw
            else:
                save_new(stored, gzip.compress(raw, mtime=0))
            archives.append({
                "original_path": path.relative_to(RUN).as_posix(),
                "archive_path": stored.relative_to(RUN).as_posix(),
                "raw_bytes": len(raw), "raw_sha256": hashlib.sha256(raw).hexdigest(),
                "archive_sha256": hashlib.sha256(stored.read_bytes()).hexdigest(),
            })
        data = stored.read_bytes()
        rows.append({"path": stored.relative_to(ROOT).as_posix(), "source_path": str(stored),
                     "bytes": len(data),
                     "sha": hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()})
    manifest = RUN / "archive-manifest.json"
    raw = (json.dumps({"schema": "jimuyun.lossless-native-evidence-archive.v1",
                      "entries": archives, "C3": "OPEN", "authorizes": []},
                     indent=2, ensure_ascii=True) + "\n").encode("utf-8")
    save_new(manifest, raw)
    rows.append({"path": manifest.relative_to(ROOT).as_posix(), "source_path": str(manifest),
                 "bytes": len(raw), "sha": hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()})
    with Path(args.manifest).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(rows, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"files": len(rows), "unique_blobs": len({row['sha'] for row in rows}),
                      "archive_files": len(archives), "stored_bytes": sum(row['bytes'] for row in rows),
                      "largest_blob": max(row['bytes'] for row in rows), "manifest": args.manifest}))
