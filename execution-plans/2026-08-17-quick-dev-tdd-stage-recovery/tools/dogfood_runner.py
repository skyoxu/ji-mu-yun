from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / ".agents" / "skills" / "quick-dev-tdd-adapter" / "tools"
CONSUMER_PLAN = ROOT / "execution-plans" / "2026-08-17-acceptance-coordinator-efficiency"


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _descriptor(command_id: str, argv: list[str], timeout_seconds: int = 600) -> dict[str, object]:
    return {
        "id": command_id,
        "executable": sys.executable,
        "argv": argv,
        "cwd": ".",
        "timeout_seconds": timeout_seconds,
        "shell": False,
    }


def _context(run_id: str, red: dict[str, object], green: dict[str, object], refactor: list[dict[str, object]], terminal: dict[str, object], red_test: Path) -> dict[str, object]:
    contract_path = CONSUMER_PLAN / "implementation-contract.v1.json"
    authority_path = CONSUMER_PLAN / "authority-manifest.v1.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    selected = next(item for item in contract["slices"] if item["slice_id"] == "S3")
    contract_bytes = contract_path.read_bytes()
    authority_bytes = authority_path.read_bytes()
    validator_path = TOOLS / "route_plan_directory.py"
    command_ids = [red["id"], green["id"], *[item["id"] for item in refactor], terminal["id"]]
    return {
        "plan_id": contract["plan_id"],
        "slice_id": "S3",
        "run_id": run_id,
        "authority_refs": [{"role": "authority-manifest", "path_type": "plan_path", "path": authority_path.name, "payload": authority_bytes}],
        "implementation_contract": {"role": "implementation-contract", "path_type": "plan_path", "path": contract_path.name, "payload": contract_bytes},
        "requirement_ids": selected["requirement_ids"],
        "acceptance_ids": selected["acceptance_ids"],
        "source_refs": selected["source_refs"],
        "boundaries": {"allowed_write_set": [path for group in selected["allowed_changes"].values() for path in group] + [red_test.relative_to(ROOT).as_posix()], "forbidden_write_set": selected["forbidden_changes"], "execution_read_set": [*selected["execution_read_set"], red_test.relative_to(ROOT).as_posix()], "dependency_closure": selected["dependency_closure"]},
        "target_command_ids": command_ids,
        "stage_results": {
            "red": {"schema_version": "rmap.tdd-stage-result.v1", "plan_id": contract["plan_id"], "slice_id": "S3", "run_id": run_id, "status": "red-observed", "mode": "red", "legacy_predecessor": None, "prior_red": None, "command_id": red["id"], "test_selector": red["argv"][3], "expected_failure_ids": ["DOGFOOD-RED"], "contract_hash": _sha(contract_bytes), "validator_hash": _sha(validator_path.read_bytes()), "pre_implementation_candidate": {"candidate_binding_hash": _sha(contract_bytes), "validator_hash": _sha(validator_path.read_bytes())}},
            "green": {"schema_version": "rmap.tdd-stage-result.v1", "plan_id": contract["plan_id"], "slice_id": "S3", "run_id": run_id, "status": "green-observed", "command_id": green["id"], "contract_hash": _sha(contract_bytes), "validator_hash": _sha(validator_path.read_bytes())},
            "refactor": {"schema_version": "rmap.tdd-stage-result.v1", "plan_id": contract["plan_id"], "slice_id": "S3", "run_id": run_id, "status": "refactor-verified", "command_id": refactor[0]["id"], "command_ids": [item["id"] for item in refactor], "contract_hash": _sha(contract_bytes), "validator_hash": _sha(validator_path.read_bytes())},
        },
    }


def _run_lifecycle(run_dir: Path, support_dir: Path, context_path: Path, refactor: list[dict[str, object]], red_test: Path, stage: str) -> None:
    command = [sys.executable, "-B", str(TOOLS / "run_slice_lifecycle.py"), "--workspace", str(ROOT), "--plan-dir", str(CONSUMER_PLAN), "--run-dir", str(run_dir), "--slice-id", "S3", "--run-context", str(context_path), "--terminal-command", str(support_dir / "terminal-command.json"), "--snapshot-path", red_test.relative_to(ROOT).as_posix(), "--command", f"red={support_dir / 'red-command.json'}", "--command", f"green={support_dir / 'green-command.json'}"]
    for index in range(len(refactor)):
        command.extend(["--command", f"refactor={support_dir / f'refactor-command-{index}.json'}"])
    if stage != "all":
        command.extend(["--stage", stage])
    completed = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True, encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(f"staged {stage} action failed: {completed.stdout}{completed.stderr}")


def main() -> int:
    run_id = "RUN-DOGFOOD-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_dir = ROOT / "logs" / "tdd-adapter" / "acceptance-coordinator-efficiency" / "S3" / run_id
    support_dir = ROOT / "logs" / "tdd-adapter" / "acceptance-coordinator-efficiency" / "dogfood-support" / run_id
    support_dir.mkdir(parents=True, exist_ok=False)
    red_test = ROOT / "logs" / "tdd-adapter" / "acceptance-coordinator-efficiency" / "dogfood-red-probe.py"
    red_test.parent.mkdir(parents=True, exist_ok=True)
    red_test.write_text("def test_dogfood_red_probe():\n    assert False\n", encoding="utf-8", newline="\n")
    green_script = support_dir / "dogfood_green.py"
    green_script.write_text("from pathlib import Path\nimport subprocess\nimport sys\npath = Path(sys.argv[1])\npath.write_text('def test_dogfood_red_probe():\\n    assert True\\n', encoding='utf-8', newline='\\n')\nraise SystemExit(subprocess.call([sys.executable, '-B', '-m', 'pytest', '.agents/skills/run-refactor-implementation-acceptance/tests/test_coordinator.py', '-q']))\n", encoding="utf-8", newline="\n")
    red = _descriptor("dogfood-red", ["-B", "-m", "pytest", red_test.relative_to(ROOT).as_posix(), "-q"], 300)
    green = _descriptor("dogfood-green", ["-B", str(green_script.relative_to(ROOT)), red_test.relative_to(ROOT).as_posix()], 600)
    refactor = [
        _descriptor("dogfood-acceptance-suite", ["-B", "-m", "pytest", ".agents/skills/run-refactor-implementation-acceptance/tests", "-q"], 900),
        _descriptor("dogfood-quick-dev-suite", ["-B", "-m", "pytest", ".agents/skills/quick-dev-tdd-adapter/tools/tests", "-q"], 900),
    ]
    terminal = _descriptor("dogfood-s3-terminal", ["-B", "execution-plans/2026-08-17-acceptance-coordinator-efficiency/tools/terminal_full.py", "--slice", "S3"], 600)
    for name, value in [("red-command.json", red), ("green-command.json", green), ("terminal-command.json", terminal)]:
        (support_dir / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")
    for index, value in enumerate(refactor):
        (support_dir / f"refactor-command-{index}.json").write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")
    context = _context(run_id, red, green, refactor, terminal, red_test)
    context_path = support_dir / "run-context.json"
    encoded_context = dict(context)
    encoded_context["authority_refs"] = [
        {key: value for key, value in item.items() if key != "payload"} | {"payload_base64": base64.b64encode(item["payload"]).decode("ascii")}
        for item in context["authority_refs"]
    ]
    contract_ref = context["implementation_contract"]
    encoded_context["implementation_contract"] = {key: value for key, value in contract_ref.items() if key != "payload"} | {"payload_base64": base64.b64encode(contract_ref["payload"]).decode("ascii")}
    context_path.write_text(json.dumps(encoded_context, indent=2) + "\n", encoding="utf-8", newline="\n")
    _run_lifecycle(run_dir, support_dir, context_path, refactor, red_test, "red")
    _run_lifecycle(run_dir, support_dir, context_path, refactor, red_test, "green")
    _run_lifecycle(run_dir, support_dir, context_path, refactor, red_test, "refactor")
    sys.path.insert(0, str(TOOLS))
    from stage_lifecycle_runner import LifecycleRunner
    observations = {stage: json.loads((run_dir / "observations" / f"{stage}-observed.json").read_text(encoding="utf-8")) for stage in ("red", "green", "refactor")}
    decoded = json.loads(context_path.read_text(encoding="utf-8"))
    for item in [*decoded["authority_refs"], decoded["implementation_contract"]]:
        item["payload"] = base64.b64decode(item.pop("payload_base64"), validate=True)
    for stage in ("green", "refactor"):
        decoded["stage_results"][stage]["exit_code"] = observations[stage]["exit_code"]
        decoded["stage_results"][stage]["observed_at"] = observations[stage]["observed_at"]
    lifecycle = LifecycleRunner(ROOT, run_dir, [red_test.relative_to(ROOT).as_posix()])
    lifecycle.resume_observations(run_dir, ["red", "green", "refactor"])
    lifecycle.close(decoded, {})
    terminal_result = subprocess.run([terminal["executable"], *terminal["argv"]], cwd=ROOT, check=False, capture_output=True, text=True, encoding="utf-8")
    if terminal_result.returncode != 0:
        raise RuntimeError(terminal_result.stdout + terminal_result.stderr)
    if not (run_dir / "attempt-ledger-manifest.v1.json").is_file():
        raise RuntimeError("staged dogfood did not close the protocol bundle")
    print(json.dumps({"status": "pass", "consumer_plan": "acceptance-coordinator-efficiency", "stages": ["red", "green", "refactor"], "terminal": "slice-ready", "run_id": run_id, "terminal_output_sha256": _sha(terminal_result.stdout.encode() + terminal_result.stderr.encode())}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
