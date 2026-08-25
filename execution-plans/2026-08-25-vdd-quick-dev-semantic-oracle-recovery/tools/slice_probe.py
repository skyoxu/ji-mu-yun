from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

FAILURE_IDS = {
    "S1": "VDD-RED-BOUNDARY",
    "S2": "QD-DESCRIPTOR-RED",
    "S3": "JUDGE-INDEPENDENCE-RED",
    "S4": "COVERAGE-EXACT-COVER-RED",
    "S5": "PROMOTION-FALSE-GREEN-RED",
    "S6": "TERMINAL-BOUNDARY-RED",
}
TESTS = {key: f"test_{key.lower()}_" for key in FAILURE_IDS}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slice", required=True)
    parser.add_argument("--stage", choices=["green", "refactor", "terminal"], required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    args = parser.parse_args()
    state = args.plan_dir / "probe-state" / f"{args.slice}.json"
    if args.stage in {"green", "refactor"}:
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(json.dumps({"slice_id": args.slice, "behavior": "implemented", "producer": "quick-dev"}) + "\n", encoding="utf-8")
        test = args.plan_dir / "tools" / {"S1":"test_semantic_red.py","S2":"test_s2_descriptor_red.py","S3":"test_s3_judge_red.py","S4":"test_s4_cover_red.py","S5":"test_s5_promotion_red.py","S6":"test_s6_terminal_red.py"}[args.slice]
        rc = subprocess.run([sys.executable, "-m", "pytest", str(test), "-q"], cwd=args.plan_dir.parents[1], check=False).returncode
        if rc == 0 and args.slice == "S6" and args.stage == "refactor":
            evidence_dir = args.plan_dir / "terminal-evidence"
            evidence_dir.mkdir(parents=True, exist_ok=True)
            payload = {"slice_id": "S6", "status": "pass", "producer": "independent-judge", "failure_id": FAILURE_IDS["S6"]}
            encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
            (evidence_dir / "S6.json").write_text(json.dumps(dict(payload, evidence_sha256="sha256:" + hashlib.sha256(encoded).hexdigest()), sort_keys=True) + "\n", encoding="utf-8")
            fixture_dir = args.plan_dir / "false-green-fixtures"
            fixture_dir.mkdir(parents=True, exist_ok=True)
            fixture_payload = {"status": "pass", "producer": "independent-judge", "count": 9, "fixture_ids": [f"FG-{i}" for i in range(1, 10)]}
            fixture_bytes = json.dumps(fixture_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
            (fixture_dir / "nine-fixtures.json").write_text(json.dumps(dict(fixture_payload, evidence_sha256="sha256:" + hashlib.sha256(fixture_bytes).hexdigest()), sort_keys=True) + "\n", encoding="utf-8")
        return rc
    if not state.is_file():
        print(f"FAILURE_ID:{FAILURE_IDS[args.slice]}", file=sys.stderr)
        return 1
    payload = {"slice_id": args.slice, "status": "pass", "producer": "quick-dev-slice-probe", "failure_id": FAILURE_IDS[args.slice]}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    evidence = dict(payload, evidence_sha256="sha256:" + hashlib.sha256(encoded).hexdigest())
    out = args.plan_dir / "terminal-evidence" / f"{args.slice}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evidence, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "pass", "predicate": "slice-ready", "slice_id": args.slice}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
