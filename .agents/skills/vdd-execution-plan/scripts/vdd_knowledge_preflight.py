"""Build a VDD-owned, hash-bound knowledge-consumption preflight result."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
if str(REPOSITORY_ROOT / "scripts" / "python") not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT / "scripts" / "python"))

from knowledge_context_validation import canonical_hash, validate_context  # noqa: E402
from skill_input_gate import require_ready_skill_input  # noqa: E402


def _sha(value: Any) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def evaluate_consumption(*, required_modules: list[str], decisions: list[dict[str, Any]]) -> dict[str, Any]:
    satisfied: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for decision in decisions:
        accepted = decision.get("decision") == "accepted"
        modules = decision.get("satisfies", [])
        if not isinstance(modules, list) or any(not isinstance(value, str) or not value for value in modules):
            raise ValueError("invalid consumption decision modules")
        if accepted and not modules:
            raise ValueError("accepted decision must satisfy a module")
        if not accepted and modules:
            raise ValueError("rejected decision cannot satisfy a module")
        if accepted:
            satisfied.update(modules)
        normalized.append({"decision": "accepted" if accepted else "rejected", "satisfies": modules})
    missing = sorted(set(required_modules) - satisfied)
    return {"status": "blocked" if missing else "ready", "missing_required_modules": missing, "decisions": normalized}


def evaluate_preflight(payload: dict[str, Any], *, repository_root: Path | None = None) -> dict[str, Any]:
    """Validate that VDD decisions consume, rather than expand, Locator output."""
    try:
        result = evaluate_consumption(
            required_modules=payload.get("required_modules", []),
            decisions=payload.get("decisions", []),
        )
    except (AttributeError, TypeError, ValueError):
        return {
            "status": "blocked",
            "missing_required_modules": [],
            "decisions": [],
            "failure_code": "consumption_decision_invalid",
        }
    failure_code = validate_context(
        payload,
        repository_root=repository_root,
        verify_catalog=repository_root is not None,
        verify_sources=repository_root is not None,
        expected_consumer="vdd",
    )
    if failure_code:
        result["status"] = "blocked"
        result["failure_code"] = failure_code
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--skill-input-receipt", type=Path, required=True)
    parser.add_argument("--skill-input-operation", choices=["create", "repair"], default="create")
    parser.add_argument(
        "--skill-input-contract",
        type=Path,
        default=REPOSITORY_ROOT / ".agents" / "skills" / "vdd-execution-plan" / "references" / "skill-input-contract.v1.json",
    )
    args = parser.parse_args()
    require_ready_skill_input(
        receipt_path=args.skill_input_receipt,
        repository_root=args.repository_root,
        contract_path=args.skill_input_contract,
        consumer="vdd-execution-plan",
        operation=args.skill_input_operation,
    )
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    result = evaluate_preflight(payload, repository_root=args.repository_root.resolve())
    result["schema_version"] = "jimuyun.vdd-knowledge-preflight.v1"
    result["input_sha256"] = canonical_hash(payload)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
