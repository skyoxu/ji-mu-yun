from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PLAN = ROOT / "execution-plans/2026-08-06-skill-authoring-standard"
ROUND = PLAN / "repair/round-5"
LOG = ROOT / "logs/tdd-adapter/skill-authoring-standard/repair-round-5"
PATHS = [
    "tools/validate_plan.py", "tools/validate_implementation.py",
    "tools/tests/test_validate_plan.py", "tools/tests/test_validate_implementation.py",
    "00-index.md", "authority-manifest.v1.json", "baseline-and-scope.v1.json",
    "implementation-contract.v1.json", "requirements.v1.json", "resume-state.v1.json",
]

def digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()

def digest(path: Path) -> str:
    return digest_bytes(path.read_bytes())

def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")

def refresh_authority_and_baseline(main_commit: str) -> None:
    contract = json.loads((PLAN / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    source_paths = []
    for raw in contract.get("source_authority", []):
        path = raw.split("#", 1)[0]
        if path not in source_paths:
            source_paths.append(path)
    authority = json.loads((PLAN / "authority-manifest.v1.json").read_text(encoding="utf-8"))
    authority["git"] = {"commit": main_commit, "tree": subprocess.check_output(["git", "rev-parse", f"{main_commit}^{{tree}}"], cwd=ROOT, text=True).strip()}
    authority["source_files"] = [{"path": p, "sha256": digest(ROOT / p)} for p in source_paths]
    authority["validator_bindings"] = [{"path": p, "sha256": digest(ROOT / p)} for p in [".agents/skills/vdd-execution-plan/scripts/vdd_knowledge_preflight.py", ".agents/skills/quick-dev-tdd-adapter/tools/validate_adapter_contract.py"]]
    authority["authorizes"] = []
    write(PLAN / "authority-manifest.v1.json", authority)
    baseline = json.loads((PLAN / "baseline-and-scope.v1.json").read_text(encoding="utf-8"))
    baseline["git"] = {"commit": main_commit, "tree": subprocess.check_output(["git", "rev-parse", f"{main_commit}^{{tree}}"], cwd=ROOT, text=True).strip(), "main_ref": "refs/heads/main"}
    baseline["scope"]["untracked_paths"] = ["docs/know70.txt"]
    baseline["scope"]["untracked_manifest"] = [{"path":"docs/know70.txt","sha256":digest(ROOT / "docs/know70.txt")}] if (ROOT / "docs/know70.txt").is_file() else []
    baseline["scope"]["dirty_scope_hash"] = digest(ROOT / "docs/workflows/skill-control-plane-evolution-requirements.md")
    write(PLAN / "baseline-and-scope.v1.json", baseline)

def main() -> None:
    ROUND.mkdir(parents=True, exist_ok=True)
    main_commit = subprocess.check_output(["git", "rev-parse", "refs/heads/main"], cwd=ROOT, text=True).strip()
    refresh_authority_and_baseline(main_commit)
    current = {p: digest(PLAN / p) for p in PATHS}
    baseline = {}
    for p in PATHS:
        raw = subprocess.check_output(["git", "show", f"{main_commit}:execution-plans/2026-08-06-skill-authoring-standard/{p}"], cwd=ROOT)
        baseline[p] = digest_bytes(raw)
    write(ROUND / "baseline-content-manifest.v1.json", {"schemaVersion":"vdd-repair-content-manifest.v1","role":"baseline","sourceCommit":main_commit,"files":[{"path":p,"sha256":baseline[p]} for p in PATHS],"authorizes":[]})
    write(ROUND / "candidate-content-manifest.v1.json", {"schemaVersion":"vdd-repair-content-manifest.v1","role":"candidate","files":[{"path":p,"sha256":current[p]} for p in PATHS],"authorizes":[]})
    write(ROUND / "callsite-inventory.v1.json", {"schemaVersion":"vdd-root-cause-callsite-inventory.v1","inventoryCommand":{"argv":["git","diff","--name-only","refs/heads/main","--",*PATHS]},"callSites":[{"path":p,"disposition":"changed" if current[p] != baseline[p] else "unchanged","consumer":"plan-validator"} for p in PATHS],"authorizes":[]})
    command = ["py","-3","-B","-m","unittest","discover","-s","execution-plans/2026-08-06-skill-authoring-standard/tools/tests","-p","test_*.py"]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", shell=False)
    output = LOG / "plan-validator-composition-receipt.v1.stdout.log"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(completed.stdout + completed.stderr, encoding="utf-8", newline="\n")
    receipt_path = "logs/tdd-adapter/skill-authoring-standard/repair-round-5/plan-validator-composition-receipt.v1.json"
    receipt = {"schemaVersion":"vdd-producer-consumer-composition-receipt.v1","generatedAt":datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z"),"commandId":"package-ab-plan-tests","argv":command,"shell":False,"timeoutSeconds":180,"status":"passed" if completed.returncode == 0 else "failed","exitCode":completed.returncode,"producerPaths":PATHS[:7],"consumerPaths":PATHS[7:],"inputHashes":current,"stdoutPath":output.relative_to(ROOT).as_posix(),"stdoutSha256":digest(output),"authorizes":[]}
    write(LOG / "plan-validator-composition-receipt.v1.json", receipt)
    closure = {"schemaVersion":"vdd-repair-closure.v1","repairKind":"package-ab-retirement-refreeze","semanticRound":5,"predecessorRun":"repair/round-4","predecessorValidationEnvelope":{"path":"execution-plans/2026-08-06-skill-authoring-standard/repair/round-4/repair-closure.json","sha256":digest(PLAN/"repair/round-4/repair-closure.json")},"findingIds":["PACKAGE-C-RETIREMENT","ACTIVE-SOURCE-REFREEZE"],"repairPaths":PATHS,"items":[{"findingId":"PACKAGE-C-RETIREMENT","disposition":"fixed","fixRefs":["00-index.md","requirements.v1.json","implementation-contract.v1.json"],"evidence":[{"path":"docs/workflows/skill-control-plane-evolution-requirements.md","sha256":digest(ROOT/"docs/workflows/skill-control-plane-evolution-requirements.md")} ]},{"findingId":"ACTIVE-SOURCE-REFREEZE","disposition":"fixed","fixRefs":["tools/validate_plan.py","authority-manifest.v1.json"],"evidence":[{"path":"repair/round-5/candidate-content-manifest.v1.json","sha256":digest(ROUND/"candidate-content-manifest.v1.json")}]}],"baselineManifest":{"path":"repair/round-5/baseline-content-manifest.v1.json","sha256":digest(ROUND/"baseline-content-manifest.v1.json")},"candidateManifest":{"path":"repair/round-5/candidate-content-manifest.v1.json","sha256":digest(ROUND/"candidate-content-manifest.v1.json")},"callsiteInventory":{"path":"repair/round-5/callsite-inventory.v1.json","sha256":digest(ROUND/"callsite-inventory.v1.json")},"compositionReceipt":{"path":receipt_path,"sha256":digest(LOG/"plan-validator-composition-receipt.v1.json")},"authorizes":[]}
    write(ROUND / "repair-closure.json", closure)
    print(json.dumps({"status":receipt["status"],"main":main_commit,"candidate":current}, indent=2))

if __name__ == "__main__":
    main()
