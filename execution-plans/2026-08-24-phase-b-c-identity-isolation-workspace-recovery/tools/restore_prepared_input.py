"""ADR-0041: restore hash-bound prepared input, then verify; no VDD or model."""
from pathlib import Path, PurePosixPath
import hashlib
import io
import json
import subprocess
import sys
import tarfile
import uuid

ROOT = Path(__file__).resolve().parents[3]
PLAN = Path(__file__).resolve().parents[1]
PREFIX = PLAN.relative_to(ROOT).as_posix() + "/"
ARCHIVE_HASH = "b55adb57fd7223398c6315a5cad2374a350e57bc7884af6a73643b9839b1a915"
MARKER = PLAN / "prepared-input-restoration.v1.json"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def target(ref):
    path = PurePosixPath(ref)
    if path.is_absolute() or ".." in path.parts or not ref.startswith(PREFIX):
        raise ValueError("Archive path outside plan: " + ref)
    result = ROOT / ref
    if result.resolve() != result:
        raise ValueError("Archive target contains a symlink: " + ref)
    return result


def run(argv):
    result = subprocess.run(argv, cwd=ROOT, shell=False, capture_output=True,
                            encoding="utf-8", errors="strict")
    if result.returncode:
        raise RuntimeError(json.dumps({"argv": argv, "stdout": result.stdout, "stderr": result.stderr}))
    return result.stdout


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")


def main():
    archive = (PLAN / "rebuild-inputs/prepared-inputs.tar.xz").read_bytes()
    if sha(archive) != ARCHIVE_HASH:
        raise ValueError("Prepared archive digest mismatch")
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:xz") as tar:
        members = tar.getmembers()
        if len({m.name for m in members}) != len(members) or any(not m.isfile() for m in members):
            raise ValueError("Non-regular or duplicate archive member")
        manifest = json.load(tar.extractfile("prepared-input-manifest.json"))
        expected = {r["path"] for r in manifest["files"]} | {"prepared-input-manifest.json"}
        if {m.name for m in members} != expected:
            raise ValueError("Archive manifest/member mismatch")
        files = {}
        for row in manifest["files"]:
            target(row["path"])
            data = tar.extractfile(row["path"]).read()
            if sha(data) != row["sha256"] or len(data) != row["bytes"]:
                raise ValueError("Prepared file digest mismatch: " + row["path"])
            data.decode("utf-8")
            files[row["path"]] = data
        for ref in manifest["delete"]:
            target(ref)
    if not MARKER.exists():
        dirty = run(["git", "status", "--porcelain", "--", str(PLAN.relative_to(ROOT))])
        if dirty.strip():
            raise ValueError("Preserve or commit local plan edits before restoring prepared input")
        for ref, data in files.items():
            path = target(ref)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(data.decode("utf-8"), encoding="utf-8", newline="\n")
        for ref in manifest["delete"]:
            target(ref).unlink(missing_ok=True)
        write_json(MARKER, {"schema": "phase-b-c.prepared-input-restoration.v1",
                            "archive_sha256": ARCHIVE_HASH, "status": "restored-checks-pending", "authorizes": []})
    marker = json.loads(MARKER.read_text(encoding="utf-8"))
    if marker.get("archive_sha256") != ARCHIVE_HASH:
        raise ValueError("Restoration marker belongs to a different archive")
    for ref, data in files.items():
        if not target(ref).is_file() or target(ref).read_bytes() != data:
            raise ValueError("Prepared input changed; refusing to overwrite: " + ref)
    if any(target(ref).exists() for ref in manifest["delete"]):
        raise ValueError("Retired current projection reappeared")
    tools = ROOT / ".agents/skills/quick-dev-tdd-adapter/tools/tests"
    guard = run([sys.executable, "-B", "-m", "pytest", str(tools / "test_dotnet_production_entry.py"),
                 str(tools / "test_ch456_red_production_entry_guard.py"), "-q", "-p", "no:cacheprovider"])
    print(guard, end="")
    result = json.loads(run([sys.executable, "-B", str(PLAN / "tools/verify_prepared_input.py")]))
    result["guard_regression_output"] = guard
    result["archive_sha256"] = ARCHIVE_HASH
    result["scope"] = "Prepared input only; no Phase implementation completion"
    evidence = ROOT / "logs/phase-b-c-input-repair/prepared-restoration" / (uuid.uuid4().hex + ".json")
    write_json(evidence, result)
    marker["status"] = "input-checks-passed"
    write_json(MARKER, marker)
    print(json.dumps({"status": "input-checks-passed", "first_slice": "S12", "slices": 73,
                      "obligations": 351, "vdd_called": False, "model_called": False,
                      "evidence": evidence.relative_to(ROOT).as_posix()}))


if __name__ == "__main__":
    main()
