"""Run one real false-green mutation and its corrected pair."""
from __future__ import annotations
import hashlib, json, sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from false_green_registry import FIXTURE_REGISTRY
from semantic_oracle import validate_descriptor, validate_judge, validate_many_to_many_cover, validate_promotion, validate_semantic_intent
from promotion_gate import validate_fixture_observation
from artifact_owners import _bound

def _hash(value):
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def _file_hash(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()

def _resolve_artifact(root, reference, producer, slice_id):
    required = {"path", "sha256", "producer", "slice_id", "run_id"}
    logs = next((parent for parent in root.resolve().parents if parent.name == "logs"), None)
    if not isinstance(reference, dict) or set(reference) != required or logs is None:
        raise ValueError("fixture artifact reference is invalid")
    if reference["producer"] != producer or reference["slice_id"] != slice_id:
        raise ValueError("fixture artifact reference is invalid")
    target = (logs.parent / reference["path"]).resolve()
    try:
        target.relative_to(logs)
    except ValueError as exc:
        raise ValueError("fixture artifact reference escapes logs") from exc
    if not target.is_file() or _file_hash(target) != reference["sha256"]:
        raise ValueError("fixture artifact reference is stale")
    value = json.loads(target.read_text(encoding="utf-8"))
    if not _bound(value, producer, slice_id, reference["run_id"]):
        raise ValueError("fixture artifact reference is unbound")
    return value


def _require_artifacts(root):
    try:
        source = json.loads((root / "false-green-fixture-input.v1.json").read_text(encoding="utf-8"))
        refs = source.get("artifact_refs") if isinstance(source, dict) else None
        logs = next((parent for parent in root.resolve().parents if parent.name == "logs"), None)
        if logs is None:
            artifacts = {
                "semantic": json.loads((root / "semantic-artifacts.v1.json").read_text(encoding="utf-8")),
                "descriptor": json.loads((root / "execution-descriptor.v1.json").read_text(encoding="utf-8")),
                "receipt": json.loads((root / "process-receipt.v1.json").read_text(encoding="utf-8")),
                "coverage": json.loads((root / "acceptance-coverage.v1.json").read_text(encoding="utf-8")),
            }
        else:
            if not isinstance(refs, dict) or set(refs) != {"semantic", "descriptor", "receipt", "coverage"}:
                return None
            artifacts = {
                "semantic": _resolve_artifact(root, refs["semantic"], "vdd", "S1"),
                "descriptor": _resolve_artifact(root, refs["descriptor"], "quick-dev", "S2"),
                "receipt": _resolve_artifact(root, refs["receipt"], "independent-judge", "S3"),
                "coverage": _resolve_artifact(root, refs["coverage"], "coverage-gate", "S4"),
            }
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    receipt, coverage = artifacts["receipt"], artifacts["coverage"]
    if receipt.get("producer") != "independent-judge" or receipt.get("status") != "pass" or receipt.get("slice_id") != "S3" or coverage.get("producer") != "coverage-gate" or coverage.get("status") != "pass" or coverage.get("slice_id") != "S4":
        return None
    def digest(value):
        body = {key: item for key, item in value.items() if key != "evidence_sha256"}
        return "sha256:" + hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if (receipt.get("evidence_sha256") != digest(receipt)
            or coverage.get("evidence_sha256") != digest(coverage)
            or coverage.get("receipt_evidence_sha256") != receipt.get("evidence_sha256")):
        return None
    return source, artifacts

def _evaluate(fixture_id, variant):
    spec = FIXTURE_REGISTRY[fixture_id]
    semantic, descriptor = {}, {}
    receipt, observation = {}, {}
    acceptance, observations, edges = [], [], []
    root = Path.cwd()
    resolved = _require_artifacts(root)
    if resolved is None:
        return False, "PROMOTION-FALSE-GREEN-RED" if spec["validator"] == "promotion" else spec["failure_id"]
    source, artifacts = resolved
    try:
        if spec["validator"] == "semantic":
            semantic = artifacts["semantic"]["semantic_intent"]
        elif spec["validator"] == "descriptor":
            descriptor = artifacts["descriptor"]["descriptor"]
        elif spec["validator"] == "judge":
            receipt, observation = artifacts["receipt"]["receipt"], artifacts["receipt"]["observation"]
        elif spec["validator"] == "coverage":
            coverage = artifacts["coverage"]
            acceptance, observations, edges = coverage["acceptance_ids"], coverage["observation_ids"], coverage["edges"]
    except KeyError:
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
        coverage = artifacts["coverage"]
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
        result = {"fixture_id": fixture_id, "category": spec["category"], "source_ref": spec["source_ref"], "validator": spec["validator"], "predecessor_judge_hash": observed_predecessor, "baseline_hash": artifacts["receipt"]["evidence_sha256"], "candidate_hash": artifacts["receipt"]["receipt"].get("candidate_hash"), "coverage_hash": artifacts["coverage"]["evidence_sha256"], "mutation_hash": _hash({"fixture_id": fixture_id, "field": spec["mutation"]})}
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
    resolved = _require_artifacts(root)
    if resolved is None:
        return 2
    _, artifacts = resolved
    receipt_value, coverage_value = artifacts["receipt"], artifacts["coverage"]
    baseline = receipt_value["evidence_sha256"]
    mutation = _hash({"fixture_id": fixture_id, "field": spec["mutation"]})
    predecessor_hash = os.environ.get("FG_PREDECESSOR_JUDGE_HASH")
    if not isinstance(predecessor_hash, str) or not predecessor_hash.startswith("sha256:"):
        return 2
    candidate = baseline
    try:
        candidate = receipt_value.get("receipt", {}).get("candidate_hash")
        receipt_candidate = receipt_value.get("receipt", {}).get("candidate_hash")
    except (AttributeError, TypeError):
        return 2
    if not isinstance(candidate, str) or not candidate.startswith("sha256:") or candidate == "sha256:fixture":
        return 2
    if candidate != receipt_candidate:
        return 2
    coverage_hash = coverage_value["evidence_sha256"]
    result = {"fixture_id": fixture_id, "category": spec["category"], "source_ref": spec["source_ref"], "validator": spec["validator"], "expected_failure_id": spec["failure_id"], "baseline_hash": baseline, "candidate_hash": candidate, "coverage_hash": coverage_hash, "predecessor_judge_hash": predecessor_hash, "mutation_hash": mutation, "mutation_applied": variant == "blocked", "variant": variant, "status": "blocked" if variant == "blocked" else "corrected", "failure_id": failure_id or None}
    print(json.dumps(result, sort_keys=True));
    if variant == "blocked":
        return 1 if (not ok and failure_id == spec["failure_id"]) else 2
    return 0 if ok and failure_id is None else 2

if __name__ == "__main__":
    raise SystemExit(main())
