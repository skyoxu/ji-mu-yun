"""Validate and publish the Toolchain Workflow Evidence Catalog v1 plan."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


PLAN_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PLAN_ROOT.parents[1]
PLAN_ID = "toolchain-workflow-evidence-catalog-v1"
EXPECTED_SLICES = [f"TEC-S{index}" for index in range(7)]
REQUIRED_FILES = (
    "00-index.md",
    "01-requirements-and-acceptance.md",
    "95-implementation-evolution-and-completion-report.md",
    "authority-manifest.v1.json",
    "command-registry.v1.json",
    "implementation-contract.v1.json",
    "knowledge-context.v1.json",
    "knowledge-context.freeze.v1.json",
    "plan-state.v1.json",
    "resume-state.v1.json",
    "tools/validate_all.py",
    "tools/validate_plan.py",
    "tools/slice_predicate.py",
    "tools/stage_projection_builder.py",
)
JSON_FILES = tuple(value for value in REQUIRED_FILES if value.endswith(".json"))
PROTECTED_PREFIXES = (
    "logs/phase-a-innernet/",
    "runtime/phase-a/",
    "phasea.platform/",
    "phasea.platform.tests/",
    ".agents/skills/vdd-execution-plan/",
    ".agents/skills/quick-dev-tdd-adapter/",
    ".agents/skills/run-phase-bootstrap-review/",
    ".agents/skills/run-refactor-implementation-acceptance/",
    ".agents/skills/maintain-knowledge-base/",
)


def _finding(rule_id: str, path: str, detail: str) -> dict[str, str]:
    return {"rule_id": rule_id, "path": path, "detail": detail}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _git_blob(commit: str, relative: str) -> bytes:
    completed = subprocess.run(
        ["git", "show", f"{commit}:{relative}"],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        raise ValueError(completed.stderr.decode("utf-8", errors="replace").strip())
    return completed.stdout


def validate_format() -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for relative in REQUIRED_FILES:
        path = PLAN_ROOT / relative
        if not path.is_file():
            findings.append(_finding("TEC-PLAN-FILE", relative, "required file is missing"))
            continue
        data = path.read_bytes()
        if data.startswith(b"\xef\xbb\xbf") or b"\r\n" in data or (data and not data.endswith(b"\n")):
            findings.append(_finding("TEC-PLAN-ENCODING", relative, "file must be UTF-8 without BOM and use LF with a final newline"))
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as exc:
            findings.append(_finding("TEC-PLAN-ENCODING", relative, str(exc)))
    return findings


def validate_authority(manifest: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    baseline = manifest.get("git_baseline", {})
    commit = baseline.get("head")
    if commit != "dbe2a731c9465946d3dc21ac3888491e33340c28":
        findings.append(_finding("TEC-PLAN-BASELINE", "authority-manifest.v1.json", "unexpected Git baseline"))
        return findings
    for item in manifest.get("sources", []):
        relative = item.get("path")
        expected = item.get("sha256")
        binding = item.get("binding")
        if not isinstance(relative, str) or not isinstance(expected, str):
            findings.append(_finding("TEC-PLAN-AUTHORITY", "authority-manifest.v1.json", "invalid source binding"))
            continue
        try:
            if binding == "git-main":
                data = _git_blob(commit, relative)
            elif binding == "worktree":
                data = (REPOSITORY_ROOT / relative).read_bytes()
            elif binding == "plan-local":
                data = (PLAN_ROOT / relative).read_bytes()
            else:
                raise ValueError("unknown binding")
        except (OSError, ValueError) as exc:
            findings.append(_finding("TEC-PLAN-AUTHORITY", relative, str(exc)))
            continue
        if _sha(data) != expected:
            findings.append(_finding("TEC-PLAN-AUTHORITY-DRIFT", relative, "bound source hash drifted"))
    scoped = manifest.get("scoped_worktree_identity", {})
    untracked = scoped.get("relevant_untracked", [])
    if untracked != [{"path": "docs/know8.txt", "sha256": "b3371f2fa9224fa3ea177e3466897358e17d2fdd80c4ac40d99eb4d982616e13"}]:
        findings.append(_finding("TEC-PLAN-SCOPED-IDENTITY", "authority-manifest.v1.json", "relevant untracked manifest is not frozen"))
    return findings


def validate_lifecycle(state: dict[str, Any], resume: dict[str, Any], index_text: str) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    status = state.get("status")
    if state.get("schema_version") != "vdd.plan-state.v2" or state.get("plan_id") != PLAN_ID or state.get("profile") != "resumable":
        findings.append(_finding("TEC-PLAN-STATE", "plan-state.v1.json", "state identity is invalid"))
    lifecycle = ["draft", "plan-ready", "implementation-authorized", "implementation-complete", "acceptance-passed", "archived"]
    if status not in lifecycle:
        findings.append(_finding("TEC-PLAN-STATE", "plan-state.v1.json", "lifecycle state is invalid"))
    authority_by_state = {
        "draft": [],
        "plan-ready": ["plan-ready"],
        "implementation-authorized": ["plan-ready", "implementation-authorized"],
        "implementation-complete": ["plan-ready", "implementation-authorized", "implementation-complete"],
        "acceptance-passed": ["plan-ready", "implementation-authorized", "implementation-complete", "acceptance-passed"],
        "archived": ["plan-ready", "implementation-authorized", "implementation-complete", "acceptance-passed", "archived"],
    }
    expected_authorizes = authority_by_state.get(status)
    if state.get("authorizes") != expected_authorizes:
        findings.append(_finding("TEC-PLAN-STATE", "plan-state.v1.json", "state authority does not match lifecycle"))
    if len(re.findall(rf"^- Status: {re.escape(str(status))}$", index_text, re.MULTILINE)) != 1:
        findings.append(_finding("TEC-PLAN-STATE-PROJECTION", "00-index.md", "index does not project state exactly once"))
    if resume.get("schema_version") != "vdd.resume-state.v2" or resume.get("plan_id") != PLAN_ID or resume.get("profile") != "resumable":
        findings.append(_finding("TEC-PLAN-RESUME", "resume-state.v1.json", "resume identity is invalid"))
    if resume.get("current_slice") not in {None, *EXPECTED_SLICES} or resume.get("live_phase_paths_allowed") is not False:
        findings.append(_finding("TEC-PLAN-RESUME", "resume-state.v1.json", "current slice or live Phase boundary is invalid"))
    slice_status = resume.get("slice_status")
    allowed_slice_status = {"pending", "in_progress", "completed", "invalidated"}
    if not isinstance(slice_status, dict) or list(slice_status) != EXPECTED_SLICES or any(value not in allowed_slice_status for value in slice_status.values()):
        findings.append(_finding("TEC-PLAN-RESUME", "resume-state.v1.json", "slice status must list seven valid states in order"))
    return findings


def validate_contract(contract: dict[str, Any], requirements_text: str, registry: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if contract.get("plan_id") != PLAN_ID or contract.get("profile") != "resumable":
        findings.append(_finding("TEC-PLAN-CONTRACT", "implementation-contract.v1.json", "contract identity or profile is invalid"))
    if contract.get("backend") != {"hidden_state": False} or contract.get("protocol_artifacts") != {"context_layout": "context/<capsule-id>", "attempt_layout": "attempts/<attempt-id>"}:
        findings.append(_finding("TEC-PLAN-QUICK-DEV", "implementation-contract.v1.json", "Quick Dev consumer boundary is invalid"))
    slices = contract.get("slices")
    if not isinstance(slices, list) or [item.get("slice_id") for item in slices if isinstance(item, dict)] != EXPECTED_SLICES:
        findings.append(_finding("TEC-PLAN-SLICES", "implementation-contract.v1.json", "slice order must be TEC-S0 through TEC-S6"))
        return findings
    commands = registry.get("commands")
    command_ids = [item.get("id") for item in commands] if isinstance(commands, list) else []
    if not command_ids or len(command_ids) != len(set(command_ids)):
        findings.append(_finding("TEC-PLAN-COMMANDS", "command-registry.v1.json", "command IDs are missing or duplicated"))
    seen: set[str] = set()
    covered_requirements: set[str] = set()
    covered_acceptance: set[str] = set()
    for index, item in enumerate(slices):
        slice_id = item["slice_id"]
        expected_deps = [] if index == 0 else [EXPECTED_SLICES[index - 1]]
        if item.get("depends_on") != expected_deps or any(value not in seen for value in item.get("depends_on", [])):
            findings.append(_finding("TEC-PLAN-DEPENDENCY", "implementation-contract.v1.json", f"{slice_id} has an invalid dependency"))
        seen.add(slice_id)
        requirement_ids = item.get("requirement_ids", [])
        acceptance_ids = item.get("acceptance_ids", [])
        if len(requirement_ids) != len(acceptance_ids):
            findings.append(_finding("TEC-PLAN-COVERAGE", "implementation-contract.v1.json", f"{slice_id} requirement/acceptance cardinality differs"))
        for requirement_id, acceptance_id in zip(requirement_ids, acceptance_ids):
            if requirement_id not in requirements_text or acceptance_id != requirement_id.replace("TEC-", "TEC-ACC-"):
                findings.append(_finding("TEC-PLAN-COVERAGE", "01-requirements-and-acceptance.md", f"invalid mapping for {requirement_id}"))
            covered_requirements.add(requirement_id)
            covered_acceptance.add(acceptance_id)
        tdd = item.get("tdd", {})
        invoked = [tdd.get("red", {}).get("command_id"), tdd.get("green", {}).get("command_id"), item.get("post_refactor_command_id")]
        invoked.extend(value.get("command_id") for value in tdd.get("refactor", {}).get("invocations", []))
        if any(value not in command_ids for value in invoked):
            findings.append(_finding("TEC-PLAN-COMMANDS", "implementation-contract.v1.json", f"{slice_id} references an unknown command"))
        allowed = item.get("allowed_changes", {})
        for values in allowed.values() if isinstance(allowed, dict) else []:
            for value in values if isinstance(values, list) else []:
                folded = value.replace("\\", "/").casefold().lstrip("/")
                if any(folded.startswith(prefix) for prefix in PROTECTED_PREFIXES):
                    findings.append(_finding("TEC-PLAN-PROTECTED", "implementation-contract.v1.json", f"{slice_id} allows protected path {value}"))
        if not item.get("recovery"):
            findings.append(_finding("TEC-PLAN-RECOVERY", "implementation-contract.v1.json", f"{slice_id} has no recovery action"))
    expected_requirements = {f"TEC-{index:03d}" for index in range(1, 26)}
    expected_acceptance = {f"TEC-ACC-{index:03d}" for index in range(1, 26)}
    if covered_requirements != expected_requirements or covered_acceptance != expected_acceptance:
        findings.append(_finding("TEC-PLAN-COVERAGE", "implementation-contract.v1.json", "requirements 001-025 are not covered exactly once"))
    terminal = contract.get("terminal_validation", {})
    if terminal.get("command_id") != "catalog-terminal" or terminal.get("required_slice") != "TEC-S6" or terminal.get("authorizes") != ["implementation-complete"]:
        findings.append(_finding("TEC-PLAN-TERMINAL", "implementation-contract.v1.json", "terminal predicate is invalid"))
    forbidden_commands = {"scan-repository", "discover-all-runs", "infer-relations", "normalize-status"}
    serialized = json.dumps(registry, sort_keys=True)
    if any(value in serialized for value in forbidden_commands):
        findings.append(_finding("TEC-PLAN-UNBOUNDED-CLI", "command-registry.v1.json", "registry contains an unbounded command"))
    return findings


def validate_quick_dev_contract(contract: dict[str, Any]) -> list[dict[str, str]]:
    path = REPOSITORY_ROOT / ".agents/skills/quick-dev-tdd-adapter/tools/validate_adapter_contract.py"
    spec = importlib.util.spec_from_file_location("tec_quick_dev_contract", path)
    if spec is None or spec.loader is None:
        return [_finding("TEC-PLAN-QUICK-DEV", str(path), "contract validator is unavailable")]
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    errors = module.validate(contract)
    return [_finding("TEC-PLAN-QUICK-DEV", "implementation-contract.v1.json", value) for value in errors]


def validate_knowledge_context() -> list[dict[str, str]]:
    completed = subprocess.run(
        [
            sys.executable,
            str(REPOSITORY_ROOT / ".agents/skills/vdd-execution-plan/scripts/vdd_knowledge_preflight.py"),
            "--repository-root",
            str(REPOSITORY_ROOT),
            "--input",
            str(PLAN_ROOT / "knowledge-context.v1.json"),
        ],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if completed.returncode:
        return [_finding("TEC-PLAN-KNOWLEDGE", "knowledge-context.v1.json", completed.stdout.strip() or completed.stderr.strip())]
    try:
        result = json.loads(completed.stdout)
    except ValueError as exc:
        return [_finding("TEC-PLAN-KNOWLEDGE", "knowledge-context.v1.json", str(exc))]
    if result.get("status") != "ready" or result.get("missing_required_modules") != []:
        return [_finding("TEC-PLAN-KNOWLEDGE", "knowledge-context.v1.json", "knowledge preflight is not ready")]
    return []


def validate_report_index() -> list[dict[str, str]]:
    path = REPOSITORY_ROOT / "execution-plans/95-implementation-report-index.v1.json"
    try:
        value = _load(path)
    except (OSError, ValueError) as exc:
        return [_finding("TEC-PLAN-REPORT-INDEX", str(path), str(exc))]
    entries = value.get("entries", [])
    expected = {"plan_directory": PLAN_ROOT.name, "report_filename": "95-implementation-evolution-and-completion-report.md"}
    if entries.count(expected) != 1:
        return [_finding("TEC-PLAN-REPORT-INDEX", str(path), "report entry must exist exactly once")]
    names = [item.get("plan_directory") for item in entries if isinstance(item, dict)]
    if names != sorted(names, key=str.casefold):
        return [_finding("TEC-PLAN-REPORT-INDEX", str(path), "entries must remain sorted by plan directory")]
    return []


def validate_directory() -> dict[str, Any]:
    findings = validate_format()
    documents: dict[str, Any] = {}
    for relative in JSON_FILES:
        path = PLAN_ROOT / relative
        if not path.is_file():
            continue
        try:
            documents[relative] = _load(path)
        except (OSError, UnicodeError, ValueError) as exc:
            findings.append(_finding("TEC-PLAN-JSON", relative, str(exc)))
    try:
        index_text = (PLAN_ROOT / "00-index.md").read_text(encoding="utf-8")
        requirements_text = (PLAN_ROOT / "01-requirements-and-acceptance.md").read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        findings.append(_finding("TEC-PLAN-MARKDOWN", str(PLAN_ROOT), str(exc)))
        index_text, requirements_text = "", ""
    state = documents.get("plan-state.v1.json")
    resume = documents.get("resume-state.v1.json")
    contract = documents.get("implementation-contract.v1.json")
    registry = documents.get("command-registry.v1.json")
    authority = documents.get("authority-manifest.v1.json")
    if isinstance(state, dict) and isinstance(resume, dict):
        findings.extend(validate_lifecycle(state, resume, index_text))
    if isinstance(authority, dict):
        findings.extend(validate_authority(authority))
    if isinstance(contract, dict) and isinstance(registry, dict):
        findings.extend(validate_contract(contract, requirements_text, registry))
        findings.extend(validate_quick_dev_contract(contract))
    findings.extend(validate_knowledge_context())
    findings.extend(validate_report_index())
    return {
        "schema_version": "tec.plan-validation.v1",
        "plan_id": PLAN_ID,
        "status": "pass" if not findings else "fail",
        "plan_state": state.get("status") if isinstance(state, dict) else None,
        "checks": [
            "required-files-and-encoding",
            "strict-json",
            "lifecycle-and-resume",
            "scoped-git-and-authority-bindings",
            "knowledge-preflight",
            "requirement-and-acceptance-coverage",
            "slice-order-write-boundaries-and-recovery",
            "structured-command-registry",
            "quick-dev-consumer-contract",
            "terminal-predicate",
            "implementation-report-index",
        ],
        "findings": findings,
        "authorizes": [],
    }


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def publish_plan_ready() -> bool:
    state_path = PLAN_ROOT / "plan-state.v1.json"
    resume_path = PLAN_ROOT / "resume-state.v1.json"
    index_path = PLAN_ROOT / "00-index.md"
    state = _load(state_path)
    resume = _load(resume_path)
    if state.get("status") == "plan-ready":
        return False
    if state.get("status") != "draft":
        raise ValueError("plan-ready may be published only from draft")
    index_text = index_path.read_text(encoding="utf-8")
    if len(re.findall(r"^- Status: draft$", index_text, re.MULTILINE)) != 1:
        raise ValueError("index does not project draft exactly once")
    state["status"] = "plan-ready"
    state["authorizes"] = ["plan-ready"]
    state["status_history"].append(
        {
            "status": "plan-ready",
            "reason": "The complete resumable directory passed its deterministic plan-ready predicate.",
            "evidence": ["tools/validate_plan.py --publish-plan-ready"],
        }
    )
    resume["next_action"] = "Obtain explicit implementation authorization before TEC-S0."
    index_text = re.sub(r"^- Status: draft$", "- Status: plan-ready", index_text, count=1, flags=re.MULTILINE)
    index_text = re.sub(
        r"^- Current step:.*$",
        "- Current step: Await explicit implementation authorization before `TEC-S0`.",
        index_text,
        count=1,
        flags=re.MULTILINE,
    )
    _write_json(state_path, state)
    _write_json(resume_path, resume)
    index_path.write_text(index_text, encoding="utf-8", newline="\n")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish-plan-ready", action="store_true")
    args = parser.parse_args()
    result = validate_directory()
    published = False
    if args.publish_plan_ready and result["status"] == "pass":
        try:
            published = publish_plan_ready()
        except (OSError, ValueError) as exc:
            result["status"] = "fail"
            result["findings"].append(_finding("TEC-PLAN-PUBLISH", "plan-ready", str(exc)))
        else:
            result = validate_directory()
            if published and result["status"] == "pass":
                result["authorizes"] = ["plan-ready"]
    result["published"] = published
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
