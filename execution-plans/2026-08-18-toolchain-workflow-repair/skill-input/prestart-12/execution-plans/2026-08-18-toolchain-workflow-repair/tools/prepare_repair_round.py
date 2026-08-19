from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


PLAN_ID = "toolchain-workflow-repair"
BASELINE = "2050ec682bab8cdc11770bf9823549b264a9e339"
PREEXISTING_BASELINE = "a2ded39b0f67dcbe5f27acedb56c0bafbd3f3fc5"
FINDINGS = {
    "TWR-ENTRY-001": ("P0", "tools/validate_all.py is missing"),
    "TWR-ENTRY-002": ("P0", "terminal has no real pass/fail implementation path"),
    "TWR-ENTRY-003": ("P0", "migration bridge supports only W0"),
    "TWR-ENTRY-004": ("P0", "plan validation receipt does not bind its full input closure"),
    "TWR-ENTRY-005": ("P0", "authorization predecessor can be overwritten at its canonical path"),
    "TWR-ENTRY-006": ("P0", "Quick Dev authorization gate does not verify the complete binding closure"),
    "TWR-ENTRY-007": ("P0", "shared Quick Dev bootstrap changes are not fully classified"),
    "TWR-ENTRY-008": ("P0", "slice snapshots do not cover each materialized RED test"),
    "TWR-ENTRY-009": ("P1", "interim plan receipt is presented as canonical v2 authority"),
    "TWR-ENTRY-010": ("P1", "Knowledge selection has no explicit required accepted modules"),
    "TWR-ENTRY-011": ("P1", "plan validator lacks authorized repair revalidation"),
    "TWR-ENTRY-012": ("P1", "prestart tools lack a temporary-repository dogfood test"),
}


def sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value))


def git_bytes(root: Path, revision: str, relative: str) -> bytes | None:
    result = subprocess.run(["git", "show", f"{revision}:{relative}"], cwd=root, capture_output=True, check=False)
    return result.stdout if result.returncode == 0 else None


def manifest(root: Path, revision: str, paths: list[str]) -> dict:
    entries = []
    for relative in sorted(paths):
        payload = git_bytes(root, revision, relative)
        entries.append({"path": relative, "kind": "present", "sha256": sha(payload)} if payload is not None else {"path": relative, "kind": "absent", "tombstone": "absent-at-baseline"})
    return {"schema_version": "toolchain-workflow-repair.manifest.v1", "baseline_commit": revision, "paths": entries, "authorizes": []}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    args = parser.parse_args()
    root, plan = args.repository_root.resolve(), args.plan_dir.resolve()
    round_dir = plan / "repair" / "round-1"
    scoped = [
        ".agents/skills/quick-dev-tdd-adapter/tools/route_plan_directory.py",
        ".agents/skills/quick-dev-tdd-adapter/tools/build_slice_invocation.py",
        ".agents/skills/quick-dev-tdd-adapter/tools/loop_plan_directory.py",
        ".agents/skills/quick-dev-tdd-adapter/tools/tests/test_plan_directory_loop.py",
        *[path.relative_to(root).as_posix() for path in sorted(plan.glob("**/*")) if path.is_file()],
    ]
    write(round_dir / "finding-set.v1.json", {"schema_version": "toolchain-workflow-repair.finding-set.v1", "plan_id": PLAN_ID, "findings": [{"id": key, "severity": value[0], "summary": value[1], "status": "open", "affected_paths": scoped, "authorizes": []} for key, value in FINDINGS.items()], "authorizes": []})
    write(round_dir / "repair-state.v1.json", {"schema_version": "toolchain-workflow-repair.repair-state.v1", "plan_id": PLAN_ID, "round": 1, "status": "validating", "blocks_execution": True, "authorizes": []})
    baseline = manifest(root, BASELINE, scoped)
    write(round_dir / "baseline-manifest.2050ec68.v1.json", baseline)
    current = []
    for item in baseline["paths"]:
        relative = item["path"]
        path = root / relative
        current.append({"path": relative, "kind": "present", "sha256": sha(path.read_bytes())} if path.is_file() else {"path": relative, "kind": "deleted", "baseline_sha256": item.get("sha256"), "tombstone": "deleted-after-baseline"})
    candidate = {"schema_version": "toolchain-workflow-repair.repair-candidate-manifest.v1", "baseline_commit": BASELINE, "candidate_identity": "worktree", "paths": current, "authorizes": []}
    write(round_dir / "repair-candidate-manifest.v1.json", candidate)
    changed = [item for item in current if next((base for base in baseline["paths"] if base["path"] == item["path"]), {}) != item]
    write(round_dir / "repair-changed-set.v1.json", {"schema_version": "toolchain-workflow-repair.repair-changed-set.v1", "baseline_manifest_sha256": sha((round_dir / "baseline-manifest.2050ec68.v1.json").read_bytes()), "candidate_manifest_sha256": sha((round_dir / "repair-candidate-manifest.v1.json").read_bytes()), "paths": changed, "authorizes": []})
    previous = plan / "implementation-authorization-receipt.successor.v1.json"
    if previous.is_file():
        copied = round_dir / "authorization-predecessor.2050ec68.v1.json"
        if not copied.exists():
            copied.write_bytes(previous.read_bytes())
    write(round_dir / "historical-artifact-disposition.v1.json", {"schema_version": "toolchain-workflow-repair.historical-disposition.v1", "artifacts": [{"path": "canonical-skill-input-plan-receipt.v2.json", "disposition": "historical-interim-noncanonical"}], "authorizes": []})
    write(round_dir / "bootstrap-preexisting-delta.v1.json", {"schema_version": "toolchain-workflow-repair.bootstrap-preexisting-delta.v1", "baseline_commit": PREEXISTING_BASELINE, "candidate_identity": "worktree", "paths": [{"path": path, "baseline_sha256": sha(git_bytes(root, PREEXISTING_BASELINE, path) or b""), "candidate_sha256": sha((root / path).read_bytes()), "disposition": "pre-existing-bootstrap-regression"} for path in scoped if (root / path).is_file()], "authorizes": []})
    print(json.dumps({"status": "pass", "round": 1, "authorizes": []}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
