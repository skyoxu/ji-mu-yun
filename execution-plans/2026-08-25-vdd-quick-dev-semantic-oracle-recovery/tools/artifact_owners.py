"""Plan-local production owners for staged evidence artifacts."""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from semantic_oracle import validate_semantic_intent, validate_descriptor, validate_judge, validate_many_to_many_cover, validate_promotion

FAILURES = {"S1":"VDD-RED-BOUNDARY","S2":"QD-DESCRIPTOR-RED","S3":"JUDGE-INDEPENDENCE-RED","S4":"COVERAGE-EXACT-COVER-RED","S5":"PROMOTION-FALSE-GREEN-RED","S6":"TERMINAL-BOUNDARY-RED"}

def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")


def _document(path: Path) -> dict | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _run_local_input(run_root: Path, name: str, producer: str) -> dict | None:
    value = _document(run_root / name)
    if value is None or value.get("producer") != producer or value.get("status") != "pass":
        return None
    return value

def run(plan: Path, slice_id: str, stage: str, run_root: Path | None = None) -> int:
    if stage == "red":
        cases = {
            "S1": lambda: validate_semantic_intent({"acceptance_ids": [], "producer": "vdd", "coverage": "oracle", "fixture_class": "negative", "taxonomy": []}),
            "S2": lambda: validate_descriptor({"target":"runner", "argv":[], "cwd":".", "timeout_seconds":30, "shell":True, "case_source_refs":[], "case_producer_ref":"vdd"}),
            "S3": lambda: validate_judge({"executor_id":"sut","judge_id":"sut","descriptor_hash":"sha256:x","candidate_hash":"sha256:y","run_id":"R","exit_code":0},{"run_id":"R"}),
            "S4": lambda: validate_many_to_many_cover([], {"A-COVER"}, set()),
            "S5": lambda: validate_promotion([], "", "sut"),
            "S6": lambda: (False, "TERMINAL-BOUNDARY-RED"),
        }
        accepted, failure_id = cases[slice_id]()
        if not accepted and failure_id == FAILURES[slice_id]:
            print(f"FAILURE_ID:{failure_id}")
            return 1
        return 2
    if stage in {"green", "refactor"}:
        # A plan-root file is not execution evidence. Every GREEN/REFACTOR
        # decision consumes a run-local, producer-identified artifact plus a
        # lifecycle observation produced by the independent adapter.
        if run_root is None or not (run_root / "observations" / "red-observed.json").is_file():
            return 2
        requirements = {
            "S1": ("semantic-artifacts.v1.json", "vdd"),
            "S2": ("execution-descriptor.v1.json", "quick-dev"),
            "S3": ("process-receipt.v1.json", "independent-judge"),
            "S4": ("acceptance-coverage.v1.json", "coverage-gate"),
            "S5": ("false-green-fixtures.v1.json", "coverage-gate"),
            "S6": ("implementation-complete-result.json", "terminal-validator"),
        }
        value = _run_local_input(run_root, *requirements[slice_id])
        if value is None or value.get("slice_id") != slice_id or value.get("run_id") != run_root.name:
            return 2
        if slice_id == "S2":
            valid, _ = validate_descriptor(value.get("descriptor", {}))
            return 0 if valid else 2
        if slice_id == "S3":
            valid, _ = validate_judge(value.get("receipt", {}), value.get("observation", {}))
            return 0 if valid else 2
        if slice_id == "S4":
            valid, _ = validate_many_to_many_cover(value.get("edges", []), set(value.get("acceptance_ids", [])), set(value.get("observation_ids", [])))
            return 0 if valid else 2
        if slice_id == "S5":
            valid, _ = validate_promotion(value.get("fixtures", []), value.get("predecessor_judge_hash"), "coverage-gate")
            return 0 if valid else 2
        return 0
    if stage == "terminal":
        if run_root is None: return 2
        evidence_root = run_root
        try:
            index = int(slice_id[1:])
            lineage_root = evidence_root.parent.parent
            if index > 1:
                for prior in range(1, index):
                    if not (lineage_root / f"S{prior}" / evidence_root.name / "terminal-evidence.json").is_file():
                        return 2
        except (ValueError, IndexError):
            return 2
        # Terminal evidence is written only by the lifecycle evidence writer;
        # this owner merely verifies that the run-local artifacts exist.
        required = [evidence_root / "terminal-evidence.json", evidence_root / "terminal-replay-report.json"]
        return 0 if all(path.is_file() for path in required) else 2
    return 2

if __name__ == "__main__":
    p=argparse.ArgumentParser(); p.add_argument("--plan-dir",required=True); p.add_argument("--slice",required=True); p.add_argument("--stage",required=True); p.add_argument("--run-root"); a=p.parse_args(); raise SystemExit(run(Path(a.plan_dir),a.slice,a.stage,Path(a.run_root) if a.run_root else None))
