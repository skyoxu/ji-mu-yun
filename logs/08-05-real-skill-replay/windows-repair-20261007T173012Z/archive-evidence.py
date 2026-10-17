"""Lossless native evidence transport; preserve original bytes (ADR-0058)."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import tarfile

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]


def write(path, raw):
    if path.exists():
        assert path.read_bytes() == raw, "different existing evidence: " + str(path)
    else:
        with path.open("xb") as stream:
            stream.write(raw)


def bound(path):
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "source_path": str(path),
        "bytes": len(raw), "sha": hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()
    closeout = json.loads((RUN / "closeout.json").read_bytes())
    assert closeout["source_commit"] == "ae311a29b15c8c75fb0dcaaa1c57c8cb9bd5ac7e"
    assert closeout["status"] == "direct-validation-passed"
    assert closeout["pytest_passed"] == 340 and closeout["unittest_passed"] == 41
    assert not closeout["native_windows_verified"]
    assert closeout["C3"] == "OPEN" and closeout["Acceptance"] == "blocked"
    trace_paths = sorted((RUN / "full").glob("*/native-processes/*.jsonl"))
    assert len(trace_paths) == closeout["native_diagnostic_file_count"]
    tar_path = RUN / "full/native-processes.tar.gz"
    assert not tar_path.exists()
    with tarfile.open(tar_path, "w:gz") as archive:
        for path in trace_paths:
            archive.add(path, arcname=path.relative_to(RUN / "full").as_posix(), recursive=False)
    trace_index = []
    with tarfile.open(tar_path, "r:gz") as archive:
        for path in trace_paths:
            name = path.relative_to(RUN / "full").as_posix()
            raw = path.read_bytes()
            assert archive.extractfile(name).read() == raw
            trace_index.append({"original_path": path.relative_to(RUN).as_posix(),
                "member": name, "raw_bytes": len(raw), "raw_sha256": hashlib.sha256(raw).hexdigest()})
    index_path = RUN / "full/native-processes-archive-index.json"
    write(index_path, (json.dumps({"schema": "jimuyun.native-process-archive.v1",
        "archive": tar_path.relative_to(RUN).as_posix(), "archive_sha256": hashlib.sha256(tar_path.read_bytes()).hexdigest(),
        "members": trace_index, "authorizes": []}, indent=2) + "\n").encode())
    rows, originals = [], []
    for path in sorted(RUN.rglob("*")):
        if not path.is_file() or "native-processes" in path.parts or path.name == "archive-manifest.json" or path.suffix == ".gz":
            continue
        raw, stored = path.read_bytes(), path
        if path.suffix in {".txt", ".jsonl"} or len(raw) > 131072:
            stored = path.with_name(path.name + ".gz")
            write(stored, gzip.compress(raw, mtime=0))
            assert gzip.decompress(stored.read_bytes()) == raw
        originals.append({"original_path": path.relative_to(RUN).as_posix(),
            "stored_path": stored.relative_to(RUN).as_posix(), "raw_bytes": len(raw),
            "raw_sha256": hashlib.sha256(raw).hexdigest(), "stored_sha256": hashlib.sha256(stored.read_bytes()).hexdigest()})
        rows.append(bound(stored))
    rows.append(bound(tar_path))
    manifest = RUN / "archive-manifest.json"
    write(manifest, (json.dumps({"schema": "jimuyun.lossless-native-evidence-archive.v1",
        "entries": originals, "trace_archive_index": index_path.relative_to(RUN).as_posix(),
        "C3": "OPEN", "Acceptance": "blocked", "authorizes": []}, indent=2) + "\n").encode())
    rows.append(bound(manifest))
    with Path(args.manifest).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(rows, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"files": len(rows), "native_trace_members": len(trace_index),
        "stored_bytes": sum(row["bytes"] for row in rows), "largest_blob": max(row["bytes"] for row in rows)}))
