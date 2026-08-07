from __future__ import annotations
import json
from pathlib import Path
PLAN_DIR = Path(__file__).resolve().parents[1]
REQUIRED = {"BROH-001","BROH-002","BROH-003","BROH-004","BROH-005","BROH-006","BROH-007"}
REQUIRED_CASES = {"missing-context-diagnostic","planned-new-file","dependency-omission","closure-binding-preview","dead-attempt-recovery","windows-safe-transport-heartbeat","readonly-repository-access","exact-evidence-crlf-range","repeated-stale-evidence-stop-loss"}
def validate_plan() -> list[str]:
    errors=[]
    for name in ["00-index.md","requirements.v1.json","plan-state.v1.json","resume-state.v1.json","command-registry.v1.json","authority-manifest.v1.json","implementation-contract.v1.json"]:
        if not (PLAN_DIR/name).is_file(): errors.append("missing:"+name)
    req=json.loads((PLAN_DIR/"requirements.v1.json").read_text(encoding="utf-8"))
    if {x.get("id") for x in req.get("requirements",[])} != REQUIRED: errors.append("requirements-incomplete")
    state=json.loads((PLAN_DIR/"plan-state.v1.json").read_text(encoding="utf-8"))
    if state.get("state") != "plan-ready" or state.get("authorizes") != ["plan-ready"]: errors.append("state-invalid")
    contract=json.loads((PLAN_DIR/"implementation-contract.v1.json").read_text(encoding="utf-8"))
    if len(contract.get("slices",[])) != 4: errors.append("slice-count-invalid")
    commands=json.loads((PLAN_DIR/"command-registry.v1.json").read_text(encoding="utf-8"))
    if {x.get("id") for x in commands.get("commands",[])} != {"plan-validator","plan-validator-tests","skill-tests","skill-whole-directory-validator","terminal-validation"}: errors.append("command-set-invalid")
    fixtures=json.loads((PLAN_DIR/"fixtures/operability-cases.v1.json").read_text(encoding="utf-8"))
    if fixtures.get("authorizes") != [] or {x.get("case_id") for x in fixtures.get("cases",[])} != REQUIRED_CASES: errors.append("fixtures-invalid")
    return sorted(set(errors))
if __name__ == "__main__":
    errors=validate_plan(); print(json.dumps({"status":"pass" if not errors else "fail","errors":errors,"authorizes":[]},sort_keys=True)); raise SystemExit(0 if not errors else 1)
