"""Invalidate a stale authorization and restore the plan-ready lifecycle state."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT / "execution-plans/2026-08-25-vdd-quick-dev-semantic-oracle-recovery"
PLAN_ID = "vdd-quick-dev-semantic-oracle-recovery"
RECEIPT = PLAN / "implementation-authorization-receipt.v3.json"


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def reference(path: Path) -> dict[str, str]:
    return {"path": path.resolve().relative_to(ROOT.resolve()).as_posix(), "sha256": digest(path)}


def _current(reference_value: object) -> bool:
    if not isinstance(reference_value, dict) or set(reference_value) != {"path", "sha256"}:
        return False
    raw_path = reference_value.get("path")
    if not isinstance(raw_path, str):
        return False
    target = (ROOT / raw_path).resolve()
    try:
        target.relative_to(ROOT.resolve())
    except ValueError:
        return False
    return target.is_file() and reference(target) == reference_value


def stale_reasons(receipt: dict[str, object]) -> list[str]:
    required = ("implementation_contract", "command_registry", "authority_manifest")
    return [field for field in required if not _current(receipt.get(field))]


def main() -> None:
    state_path = PLAN / "plan-state.v1.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("plan_id") != PLAN_ID:
        raise SystemExit("plan state does not identify this plan")
    if state.get("state") == "plan-ready" and state.get("authorizes") == ["plan-ready"]:
        print(json.dumps({"status": "already-plan-ready", "authorizes": ["plan-ready"]}, sort_keys=True))
        return
    if state.get("state") != "implementation-authorized" or state.get("authorizes") != ["implementation-authorized"]:
        raise SystemExit("plan state is not an invalidatable implementation authorization")
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    reasons = stale_reasons(receipt)
    if not reasons:
        raise SystemExit("current implementation authorization must not be invalidated")

    tag = digest(RECEIPT).split(":", 1)[1][:12]
    out = PLAN / "governance" / f"implementation-authorization-invalidation.v2.{tag}.json"
    value = {
        "schema_version": "quick-dev-tdd-adapter.implementation-authorization-invalidation.v2",
        "plan_id": PLAN_ID,
        "superseded_authorization": reference(RECEIPT),
        "stale_bindings": reasons,
        "current_contract": reference(PLAN / "implementation-contract.v1.json"),
        "current_command_registry": reference(PLAN / "command-registry.v1.json"),
        "authorizes": [],
    }
    encoded = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and out.read_bytes() != encoded:
        raise SystemExit("existing invalidation evidence does not match the stale authorization")
    if not out.exists():
        out.write_bytes(encoded)
    next_state = {
        "schema_version": "vdd.lifecycle.v2",
        "plan_id": PLAN_ID,
        "state": "plan-ready",
        "owner": "vdd-execution-plan",
        "profile": state.get("profile", "self-hosted"),
        "canonical_selection_hash": state["canonical_selection_hash"],
        "authorization_invalidation": reference(out),
        "authorizes": ["plan-ready"],
    }
    state_path.write_text(json.dumps(next_state, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": "invalidated", "evidence": reference(out), "authorizes": ["plan-ready"]}, sort_keys=True))


if __name__ == "__main__":
    main()
