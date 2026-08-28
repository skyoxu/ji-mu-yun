"""Run one real false-green mutation and its corrected pair."""
from __future__ import annotations
import hashlib, json, sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from false_green_registry import FIXTURE_REGISTRY
from semantic_oracle import validate_descriptor, validate_judge, validate_many_to_many_cover, validate_promotion, validate_semantic_intent
from promotion_gate import validate_fixture_observation

def _hash(value):
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def _file_hash(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()

def _require_artifacts(root):
    required = ("process-receipt.v1.json", "acceptance-coverage.v1.json")
    if any(not (root / name).is_file() for name in required):
        return False
    try:
        receipt = json.loads((root / required[0]).read_text(encoding="utf-8"))
        coverage = json.loads((root / required[1]).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if receipt.get("producer") != "independent-judge" or receipt.get("status") != "pass" or receipt.get("slice_id") != "S3" or coverage.get("producer") != "coverage-gate" or coverage.get("status") != "pass" or coverage.get("slice_id") != "S4" or coverage.get("run_id") != receipt.get("run_id"):
        return False
    def digest(value):
        body = {key: item for key, item in value.items() if key != "evidence_sha256"}
        return "sha256:" + hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return (receipt.get("evidence_sha256") == digest(receipt)
            and coverage.get("evidence_sha256") == digest(coverage)
            and coverage.get("receipt_evidence_sha256") == receipt.get("evidence_sha256"))

def _evaluate(fixture_id, variant):
    spec = FIXTURE_REGISTRY[fixture_id]
    semantic, descriptor = {}, {}
    receipt, observation = {}, {}
    acceptance, observations, edges = [], [], []
    root = Path.cwd()
    if not _require_artifacts(root):
        return False, "PROMOTION-FALSE-GREEN-RED" if spec["validator"] == "promotion" else spec["failure_id"]
    try:
        if spec["validator"] == "semantic":
            semantic = json.loads((root / "semantic-artifacts.v1.json").read_text(encoding="utf-8"))["semantic_intent"]
        elif spec["validator"] == "descriptor":
            descriptor = json.loads((root / "execution-descriptor.v1.json").read_text(encoding="utf-8"))["descriptor"]
        elif spec["validator"] == "judge":
            doc = json.loads((root / "process-receipt.v1.json").read_text(encoding="utf-8")); receipt, observation = doc["receipt"], doc["observation"]
        elif spec["validator"] == "coverage":
            doc = json.loads((root / "acceptance-coverage.v1.json").read_text(encoding="utf-8")); acceptance, observations, edges = doc["acceptance_ids"], doc["observation_ids"], doc["edges"]
    except (OSError, KeyError, json.JSONDecodeError):
        return False, spec["failure_id"]
    if variant == "blocked":
        if spec["validator"] == "semantic": semantic[spec["mutation"]] = ""
        elif spec["validator"] == "descriptor": descriptor.pop(spec["mutation"], None) if spec["mutation"] == "case_source_refs" else descriptor.__setitem__(spec["mutation"], True)
        elif spec["validator"] == "judge":
            if spec["mutation"] == "judge_id":
                receipt["judge_id"] = "sut"
            else:
                observation["expected_exit"] = "nonzero"
                receipt["exit_code"] = 0
        elif spec["validator"] == "coverage": edges = [] if spec["mutation"] == "edge_set" else [{"acceptance_id":"A-SEMANTIC","case_id":"CASE-FIXTURE","observation_id":"OBS-DRIFT","assertion":"receipt.exit_code == 0"}]
    if spec["validator"] == "semantic": ok, failure = validate_semantic_intent(semantic)
    elif spec["validator"] == "descriptor": ok, failure = validate_descriptor(descriptor)
    elif spec["validator"] == "judge": ok, failure = validate_judge(receipt, observation)
    elif spec["validator"] == "coverage": ok, failure = validate_many_to_many_cover(edges, set(acceptance), set(observations))
    else:
        root = Path.cwd()
        source_path = root / "false-green-fixture-input.v1.json"
        coverage_path = root / "acceptance-coverage.v1.json"
        if not source_path.is_file() or not coverage_path.is_file():
            return False, "PROMOTION-FALSE-GREEN-RED"
        try:
            source = json.loads(source_path.read_text(encoding="utf-8"))
            coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False, "PROMOTION-FALSE-GREEN-RED"
        predecessor = source.get("predecessor_judge_hash")
        if not isinstance(predecessor, str) or not predecessor.startswith("sha256:") or predecessor in {"sha256:judge-predecessor", "sha256:fixture"}:
            return False, "PROMOTION-FALSE-GREEN-RED"
        entries = [item for item in source.get("fixtures", []) if isinstance(item, dict) and item.get("fixture_id") == fixture_id]
        if len(entries) != 1 or entries[0].get("blocked_argv") == entries[0].get("corrected_argv"):
            return False, "PROMOTION-FALSE-GREEN-RED"
        if coverage.get("producer") != "coverage-gate" or coverage.get("status") != "pass" or coverage.get("slice_id") != "S4" or not coverage.get("evidence_sha256", "").startswith("sha256:"):
            return False, "PROMOTION-FALSE-GREEN-RED"
        entry = entries[0]
        observed_predecessor = predecessor
        if variant == "blocked" and fixture_id == "FG-08":
            observed_predecessor = "sha256:mutated-predecessor"
        result = {"fixture_id": fixture_id, "category": spec["category"], "source_ref": spec["source_ref"], "validator": spec["validator"], "predecessor_judge_hash": observed_predecessor, "baseline_hash": _file_hash(root / "process-receipt.v1.json"), "candidate_hash": json.loads((root / "execution-input.v1.json").read_text(encoding="utf-8")).get("candidate_hash"), "coverage_hash": _file_hash(root / "acceptance-coverage.v1.json"), "mutation_hash": _hash({"fixture_id": fixture_id, "field": spec["mutation"]})}
        if variant == "blocked" and fixture_id == "FG-09":
            result["mutation_hash"] = result["baseline_hash"]
        result["mutation_applied"] = variant == "blocked"
        result["failure_id"] = spec["failure_id"] if variant == "blocked" else None
        ok, failure = validate_fixture_observation(result, predecessor, variant)
    return ok, (failure if not ok else None)

def main() -> int:
    fixture_id, variant = sys.argv[1:3]
    spec = FIXTURE_REGISTRY[fixture_id]
    ok, failure_id = _evaluate(fixture_id, variant)
    if ok and variant == "blocked":
        failure_id = spec["failure_id"]
    elif ok and variant == "corrected":
        failure_id = None
    root = Path.cwd()
    if not (root / "process-receipt.v1.json").is_file() or not (root / "acceptance-coverage.v1.json").is_file():
        return 2
    baseline = _file_hash(root / "process-receipt.v1.json")
    mutation = _hash({"fixture_id": fixture_id, "field": spec["mutation"]})
    predecessor_hash = os.environ.get("FG_PREDECESSOR_JUDGE_HASH")
    if not isinstance(predecessor_hash, str) or not predecessor_hash.startswith("sha256:"):
        return 2
    candidate = baseline
    try:
        execution_input = json.loads((root / "execution-input.v1.json").read_text(encoding="utf-8"))
        candidate = execution_input.get("candidate_hash")
        receipt_value = json.loads((root / "process-receipt.v1.json").read_text(encoding="utf-8"))
        receipt_candidate = receipt_value.get("receipt", {}).get("candidate_hash")
    except (OSError, json.JSONDecodeError):
        return 2
    if not isinstance(candidate, str) or not candidate.startswith("sha256:") or candidate == "sha256:fixture":
        return 2
    if candidate != receipt_candidate:
        return 2
    coverage_hash = _file_hash(root / "acceptance-coverage.v1.json")
    result = {"fixture_id": fixture_id, "category": spec["category"], "source_ref": spec["source_ref"], "validator": spec["validator"], "expected_failure_id": spec["failure_id"], "baseline_hash": baseline, "candidate_hash": candidate, "coverage_hash": coverage_hash, "predecessor_judge_hash": predecessor_hash, "mutation_hash": mutation, "mutation_applied": variant == "blocked", "variant": variant, "status": "blocked" if variant == "blocked" else "corrected", "failure_id": failure_id or None}
    print(json.dumps(result, sort_keys=True));
    if variant == "blocked":
        return 1 if (not ok and failure_id == spec["failure_id"]) else 2
    return 0 if ok and failure_id is None else 2

if __name__ == "__main__":
    raise SystemExit(main())
