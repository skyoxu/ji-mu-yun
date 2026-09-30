"""Audit an explicit Quick Dev predecessor set against the plan and Git tree."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


PLAN_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = PLAN_DIR.parents[1]


def load_json(path: Path) -> object:
    return json.JSONDecoder().raw_decode(path.read_text(encoding="utf-8-sig"))[0]


def git_bytes(commit: str, relative_path: str) -> bytes | None:
    result = subprocess.run(
        ["git", "show", f"{commit}:{relative_path}"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


def audit(source: Path, commit: str) -> dict[str, object]:
    plan_slices = load_json(PLAN_DIR / "slices.v1.json")
    assert isinstance(plan_slices, list)
    plan_ids = [row["slice_id"] for row in plan_slices]
    if len(plan_ids) != len(set(plan_ids)):
        raise ValueError("Plan contains duplicate slice IDs")
    plan_set = set(plan_ids)

    candidate = load_json(source)
    assert isinstance(candidate, dict)
    seen: set[str] = set()
    verified: list[dict[str, str]] = []
    invalid: list[dict[str, str]] = []
    for entry in candidate["valid_predecessors"]:
        sid = entry["slice_id"]
        ref = entry["result_ref"]
        reason = ""
        if sid not in plan_set:
            reason = "not-in-current-plan"
        elif sid in seen:
            reason = "duplicate-slice"
        else:
            seen.add(sid)
            ref_path = Path(ref)
            if ref_path.is_absolute() or ".." in ref_path.parts:
                reason = "invalid-result-ref"
            else:
                content = git_bytes(commit, ref)
                if content is None:
                    reason = "result-ref-not-in-commit"
                elif "sha256:" + hashlib.sha256(content).hexdigest() != entry["result_sha256"]:
                    reason = "result-hash-mismatch"
                else:
                    try:
                        result = json.JSONDecoder().raw_decode(content.decode("utf-8-sig"))[0]
                    except (UnicodeError, json.JSONDecodeError):
                        reason = "invalid-result-json"
                    else:
                        if result.get("slice_id") != sid or result.get("status") != "pass":
                            reason = "result-not-passing-slice"
        if reason:
            invalid.append({"slice_id": sid, "result_ref": ref, "reason": reason})
        else:
            verified.append(entry)

    verified_ids = {entry["slice_id"] for entry in verified}
    return {
        "schema": "quick-dev.predecessor-aggregation-audit.v1",
        "plan_id": candidate["plan_id"],
        "audited_commit": commit,
        "candidate_source": source.relative_to(REPO_ROOT).as_posix(),
        "plan_slice_count": len(plan_ids),
        "verified_predecessors": verified,
        "verified_count": len(verified),
        "missing_slices": [sid for sid in plan_ids if sid not in verified_ids],
        "invalid_entries": invalid,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--commit", default="HEAD")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = audit((REPO_ROOT / args.source).resolve(), args.commit)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps({"verified_count": result["verified_count"], "missing_slices": result["missing_slices"], "invalid_entries": result["invalid_entries"]}))


if __name__ == "__main__":
    main()
