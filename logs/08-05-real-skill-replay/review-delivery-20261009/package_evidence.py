"""Package immutable replay evidence for remote review (Accepted ADR-0058)."""
from __future__ import annotations

import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "logs/08-05-real-skill-replay"
OUTPUT = Path(__file__).resolve().parent
FIRST = BASE / "observable-verification-budget-resplit-20261009"
RESUME = FIRST / "resume-20261009-r2"


def digest(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=True)
        stream.write("\n")


def events(directory):
    return [json.loads(line) for line in
            (directory / "pytest-events.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()]


def phases(rows):
    result = {}
    for row in rows:
        if row["kind"] == "report":
            result.setdefault(row["nodeid"], []).append(row)
    return result


def main():
    original, resumed = phases(events(FIRST)), phases(events(RESUME))
    expected = load(FIRST / "selected-nodeids.json")
    resume_nodes = load(RESUME / "selected-nodeids.json")
    assert len(expected) == len(set(expected)) == 340
    assert len(resume_nodes) == len(set(resume_nodes)) == 47
    assert set(resume_nodes).issubset(expected)
    assert load(RESUME / "summary.json")["status"] == "direct-validation-passed"
    assert load(FIRST / "summary.json")["unittest"]["tests"] == 51
    observations = []
    for node in expected:
        rows = resumed[node] if node in resume_nodes else original[node]
        assert {r["phase"] for r in rows} == {"setup", "call", "teardown"}, node
        assert all(r["outcome"] == "passed" and not r["wasxfail"] for r in rows), node
        observations.append({"nodeid": node, "reports": rows,
                             "evidence": (RESUME if node in resume_nodes else FIRST).relative_to(ROOT).as_posix()})
    assert set(original) | set(resumed) == set(expected)

    bindings = {}
    for directory in (FIRST, RESUME):
        before, after = load(directory / "source-before.json"), load(directory / "source-after.json")
        assert before == after, directory
        for row in before["files"]:
            assert bindings.setdefault(row["path"], row["sha256"]) == row["sha256"], row["path"]
    for name, identity in bindings.items():
        assert digest((ROOT / name).read_bytes()) == identity, name
    source_head = load(FIRST / "source-before.json")["head"]
    assert source_head == load(RESUME / "source-before.json")["head"]
    assert source_head == subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()

    directories = sorted((p for p in BASE.iterdir() if p.is_dir() and
                          ("20261008" in p.name or p.name == FIRST.name or p.name == "windows-debug-trace")),
                         key=lambda p: p.name)
    secret_patterns = [re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
                       re.compile(rb"\b(?:ghp_|github_pat_|sk-proj-)[A-Za-z0-9_\-]{24,}"),
                       re.compile(rb"\bsk-[A-Za-z0-9]{32,}"),
                       re.compile(rb"(?i)\bBearer\s+[A-Za-z0-9._\-]{32,}")]
    manifest, archives = [], []
    for directory in directories:
        files = sorted((p for p in directory.rglob("*") if p.is_file()),
                       key=lambda p: p.relative_to(ROOT).as_posix())
        archive = OUTPUT / (directory.name + ".tar.gz")
        with archive.open("xb") as destination:
            with gzip.GzipFile(fileobj=destination, mode="wb", filename="", mtime=0) as compressed:
                with tarfile.open(fileobj=compressed, mode="w|") as bundle:
                    for path in files:
                        assert not path.is_symlink(), path
                        raw = path.read_bytes()
                        assert not any(pattern.search(raw) for pattern in secret_patterns), (
                            "Potential credential material; publication stopped: " + path.relative_to(ROOT).as_posix())
                        name = path.relative_to(ROOT).as_posix()
                        manifest.append({"path": name, "bytes": len(raw), "sha256": digest(raw),
                                         "archive": archive.name})
                        entry = tarfile.TarInfo(name)
                        entry.size, entry.mode, entry.mtime = len(raw), 0o644, 0
                        bundle.addfile(entry, io.BytesIO(raw))
        archives.append({"archive": archive.name, "directory": directory.relative_to(ROOT).as_posix(),
                         "files": len(files), "bytes": archive.stat().st_size,
                         "sha256": digest(archive.read_bytes())})

    # Verify the published archive bytes against every original file, not just counts.
    identities = {row["path"]: row["sha256"] for row in manifest}
    archived = set()
    for row in archives:
        with tarfile.open(OUTPUT / row["archive"], "r:gz") as bundle:
            for entry in bundle:
                assert entry.isfile() and entry.name not in archived
                assert digest(bundle.extractfile(entry).read()) == identities[entry.name]
                archived.add(entry.name)
    assert archived == set(identities)

    for label, directory in (("original", FIRST), ("resume", RESUME)):
        for name in ("summary.json", "source-before.json", "source-after.json", "selected-nodeids.json",
                     "pytest-events.jsonl", "junit.xml"):
            source = directory / name
            if source.exists():
                with (OUTPUT / (label + "-" + name)).open("xb") as stream:
                    stream.write(source.read_bytes())
    save(OUTPUT / "archives.json", {"archives": archives, "authorizes": []})
    save(OUTPUT / "file-manifest.json", {"files": manifest, "authorizes": []})
    save(OUTPUT / "node-observations.json", {"nodes": observations, "authorizes": []})
    save(OUTPUT / "review-summary.json", {
        "status": "segmented-verification-complete-for-review",
        "source_head_recorded_by_runs": source_head,
        "candidate_binding": "original source-before/source-after bytes, not a replacement commit binding",
        "current_source_bytes_match_original_bindings": True,
        "original_status": load(FIRST / "summary.json")["status"],
        "original_passed": 293, "original_failed": 1, "original_unfinished": 46,
        "resume_status": load(RESUME / "summary.json")["status"],
        "resume_passed": 47, "unique_nodes_with_passing_setup_call_teardown": 340,
        "single_uninterrupted_340_node_pass": False,
        "unittest_passed_in_original_run": 51,
        "history_rewritten": False, "receipt_rebound": False,
        "original_failures_and_timeout_cause_remain_reviewable": True,
        "archive_count": len(archives), "archived_file_count": len(manifest),
        "archive_byte_verification": True,
        "credential_pattern_scan": "no matches in archived files",
        "C3": "OPEN", "authorizes": [],
        "implementation_complete_published": False, "acceptance_published": False,
    })
    print(json.dumps({"archive_count": len(archives), "archived_file_count": len(manifest),
                      "archive_bytes": sum(row["bytes"] for row in archives),
                      "verified_nodes": len(observations), "authorizes": []}))


if __name__ == "__main__":
    main()
