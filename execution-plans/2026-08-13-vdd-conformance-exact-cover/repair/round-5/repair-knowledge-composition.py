"""Round 5 repair composition using only the shared Skill Input protocol."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PLAN = ROOT / "execution-plans/2026-08-13-vdd-conformance-exact-cover"
ROUND = PLAN / "repair/round-5"
CONTRACT = ROOT / ".agents/skills/vdd-execution-plan/references/skill-input-contract.v1.json"
PREPARE = ROOT / "scripts/python/prepare_skill_input_consumption.py"
LAUNCH = ROOT / "scripts/python/launch_skill_input_consumer.py"
VALIDATE = ROOT / "scripts/python/validate_skill_input_consumption.py"
PREFLIGHT = ROOT / ".agents/skills/vdd-execution-plan/scripts/vdd_knowledge_preflight.py"
KNOWLEDGE = ROOT / ".agents/skills/vdd-execution-plan/scripts/prepare_knowledge_context.py"
SELF = Path(__file__).resolve()


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def checked(command: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False, timeout=300)
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout or "controlled command failed")
    return result


def validate_receipt(receipt_path: Path, closure_path: Path | None) -> None:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("schema_version") != "vdd-repair-composition-receipt.v2" or receipt.get("status") != "passed" or receipt.get("authorizes") != []:
        raise RuntimeError("composition receipt is not a passed non-authorizing v2 receipt")
    if closure_path is not None:
        closure = json.loads(closure_path.read_text(encoding="utf-8"))
        if closure.get("composition_receipt") != receipt_path.relative_to(PLAN).as_posix() or closure.get("composition_receipt_sha256") != sha(receipt_path):
            raise RuntimeError("receipt is not the closure-bound receipt")
    for item in receipt.get("programs", []):
        path = ROOT / item["path"]
        if not path.is_file() or item.get("sha256") != sha(path) or item.get("exit_code") != 0:
            raise RuntimeError("composition program binding is stale")
    for key in ("skill_input_receipt", "child_request", "semantic_decision", "context_artifact", "knowledge_context", "knowledge_freeze"):
        item = receipt[key]
        path = ROOT / item["path"]
        if not path.is_file() or item.get("sha256") != sha(path):
            raise RuntimeError(f"composition artifact binding is stale: {key}")
    ready = json.loads((ROOT / receipt["skill_input_receipt"]["path"]).read_text(encoding="utf-8"))
    if ready.get("ready") is not True or ready.get("authorizes") != []:
        raise RuntimeError("official Skill Input receipt is not ready and non-authorizing")
    skill_receipt = ROOT / receipt["skill_input_receipt"]["path"]
    skill_contract = skill_receipt.parent / "contract.json"
    checked([sys.executable, str(VALIDATE), str(skill_receipt), "--repository-root", str(ROOT), "--contract", str(skill_contract), "--require-ready"])
    checked([sys.executable, str(PREFLIGHT), "--input", str(ROOT / receipt["knowledge_context"]["path"]), "--repository-root", str(ROOT), "--skill-input-receipt", str(skill_receipt), "--skill-input-operation", "repair"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--closure", type=Path)
    parser.add_argument("--validate-receipt", action="store_true")
    args = parser.parse_args()
    receipt_path = args.receipt if args.receipt and args.receipt.is_absolute() else ROOT / (args.receipt or "")
    if args.validate_receipt:
        try:
            validate_receipt(receipt_path, args.closure)
        except (OSError, KeyError, TypeError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
            print(f"repair-knowledge-composition=blocked reason={exc}")
            return 2
        print("repair-knowledge-composition=receipt-valid")
        return 0
    try:
        # Keep the official adapter's repository-relative snapshot below Windows path limits.
        # This Round 5 binding is immutable after its first successful publication.
        run = ROUND / "e"
        binding = run / "skill-input"
        snapshot = binding / "s"
        receipt = binding / "receipt.json"
        request = binding / "request.json"
        child = binding / "child.json"
        output = binding / "o"
        context = run / "knowledge-context.v1.json"
        target_scope = ROUND / "skill-input-target-plan"
        binding.mkdir(parents=True, exist_ok=False)
        shutil.copy2(CONTRACT, binding / "contract.json")
        (run / "request.json").write_text(json.dumps({"finding":"docs/know23.txt","target_plan":PLAN.relative_to(ROOT).as_posix()}, indent=2) + "\n", encoding="utf-8")
        checked([sys.executable, str(PREPARE), "--repository-root", str(ROOT), "--contract", str(binding / "contract.json"), "--consumer", "vdd-execution-plan", "--operation", "repair", "--route-identity", "sha256:ad551c4b0f9a7573a4bdf5f78cf31c1f9ee0c7cac64d0f68ebed65065b5a5531", "--target", str(PLAN.relative_to(ROOT)), "--source-role", f"target_plan={target_scope.relative_to(ROOT).as_posix()}", "--source-role", "repair_finding=docs/know23.txt", "--request-json", str(run / "request.json"), "--snapshot-root", str(snapshot), "--receipt", str(receipt)])
        output_relative = output.relative_to(ROOT).as_posix()
        checked([sys.executable, str(LAUNCH), "--create-request", "--receipt", str(receipt), "--contract", str(binding / "contract.json"), "--request", str(child), "--binding-root", str(ROOT), "--output-root", output_relative, "--backend", "codex-cli", "--model", "gpt-5.6-terra", "--reasoning-effort", "high"])
        checked([sys.executable, str(LAUNCH), "--request", str(child), "--binding-root", str(ROOT), "--run-semantic-child", "--backend", "codex-cli", "--model", "gpt-5.6-terra", "--reasoning-effort", "high"])
        checked([sys.executable, str(VALIDATE), str(receipt), "--repository-root", str(ROOT), "--contract", str(binding / "contract.json"), "--publish-ready", "--child-request", str(child), "--semantic-decision", str(output / "semantic-decision.v1.json"), "--context-artifact", str(output / "skill-input-context.v1.json"), "--require-ready"])
        checked([sys.executable, str(KNOWLEDGE), "--repository-root", str(ROOT), "--request-id", "vdd-conformance-exact-cover-round-5", "--query", "VDD self-hosted execution plan Canonical Spec Package exact-cover conformance repository rules lifecycle authority", "--target-plan", str(PLAN.relative_to(ROOT)), "--output", str(context), "--allow-stale-catalog", "--required-module", "repository-rules", "--required-module", "adr.ADR-0044", "--required-module", "adr.ADR-0048", "--accept", "AGENTS.md=repository-rules,adr.ADR-0044,adr.ADR-0048"])
        checked([sys.executable, str(PREFLIGHT), "--input", str(context), "--repository-root", str(ROOT), "--skill-input-receipt", str(receipt), "--skill-input-operation", "repair"])
        payload = {"schema_version":"vdd-repair-composition-receipt.v2","round":5,"command_id":"repair-knowledge-composition","status":"passed","programs":[{"path":p.relative_to(ROOT).as_posix(),"sha256":sha(p),"exit_code":0} for p in (SELF, PREPARE, LAUNCH, VALIDATE, KNOWLEDGE, PREFLIGHT)],"skill_input_receipt":{"path":receipt.relative_to(ROOT).as_posix(),"sha256":sha(receipt)},"child_request":{"path":child.relative_to(ROOT).as_posix(),"sha256":sha(child)},"semantic_decision":{"path":(output/'semantic-decision.v1.json').relative_to(ROOT).as_posix(),"sha256":sha(output/'semantic-decision.v1.json')},"context_artifact":{"path":(output/'skill-input-context.v1.json').relative_to(ROOT).as_posix(),"sha256":sha(output/'skill-input-context.v1.json')},"knowledge_context":{"path":context.relative_to(ROOT).as_posix(),"sha256":sha(context)},"knowledge_freeze":{"path":context.with_name('knowledge-context.freeze.v1.json').relative_to(ROOT).as_posix(),"sha256":sha(context.with_name('knowledge-context.freeze.v1.json'))},"authorizes":[]}
        out = run / "receipt.json"
        out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"repair-knowledge-composition=blocked reason={exc}")
        return 2
    print(f"repair-knowledge-composition=passed receipt={out.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
