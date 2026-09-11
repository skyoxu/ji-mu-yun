"""Repository-owned, bounded Skill package validation and replay."""
from __future__ import annotations
import argparse, hashlib, json, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()

def manifest(root: Path) -> str:
    entries = []
    for path in sorted(p for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"):
        entries.append({"path": path.relative_to(root).as_posix(), "sha256": digest(path)})
    return "sha256:" + hashlib.sha256(json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def contained(path: Path, root: Path, label: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"{label} escapes the repository") from exc
    return resolved

def capability(path: Path) -> tuple[Path, dict]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("state", "active") != "active":
        raise ValueError("validator capability is not active")
    allowed = (ROOT / value["allowed_root"]).resolve()
    entry = value["validator_entrypoint"]
    validator = (allowed / entry).resolve()
    validator.relative_to(allowed)
    if not validator.is_file() or not validator.name.endswith(".py"):
        raise ValueError("validator capability is absent")
    if value.get("validator_sha256") != digest(validator):
        raise ValueError("validator identity drift")
    probe_args = value.get("probe_args")
    if not isinstance(probe_args, list) or probe_args.count("{target}") != 1 or not all(isinstance(item, str) for item in probe_args):
        raise ValueError("validator capability probe_args must bind exactly one target")
    return validator, value

def validator_command(validator: Path, value: dict, target: Path) -> list[str]:
    return [sys.executable, str(validator), *[str(target) if item == "{target}" else item for item in value["probe_args"]]]

def run_validator(validator: Path, value: dict, target: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(validator_command(validator, value, target), cwd=ROOT, capture_output=True, text=True, check=False)

def validate_package(target: str, capability_path: str) -> dict:
    target_root = contained(ROOT / target, ROOT, "target package")
    if not target_root.is_dir():
        raise ValueError("target package is absent")
    validator, value = capability(contained(ROOT / capability_path, ROOT, "capability"))
    result = run_validator(validator, value, target_root)
    if result.returncode != 0:
        raise RuntimeError(result.stdout + result.stderr)
    with tempfile.TemporaryDirectory(dir=ROOT / "logs") as temporary:
        negative = run_validator(validator, value, Path(temporary))
    if negative.returncode == 0:
        raise ValueError("negative compatibility probe unexpectedly passed")
    return {"schema_version": "jimuyun.skill-package-validation-receipt.v1", "status": "pass", "exit_code": 0, "target_package": {"path": target, "manifest_sha256": manifest(target_root)}, "resolved_validator": {"path": validator.relative_to(ROOT).as_posix(), "sha256": digest(validator), "package_identity": value.get("package_identity", "unknown")}, "probes": [{"probe_id": "detached-positive", "status": "pass", "exit_code": result.returncode}, {"probe_id": "detached-negative", "status": "expected-failure", "exit_code": negative.returncode}], "authorizes": []}

def main() -> int:
    parser = argparse.ArgumentParser(); sub = parser.add_subparsers(dest="op", required=True)
    p = sub.add_parser("validate-package"); p.add_argument("--target", required=True); p.add_argument("--capability", required=True)
    p = sub.add_parser("replay-package"); p.add_argument("--target", required=True); p.add_argument("--capability", required=True); p.add_argument("--probe-mode", required=True)
    p = sub.add_parser("replay-matrix"); p.add_argument("--matrix", required=True)
    args = parser.parse_args()
    if args.op == "validate-package":
        print(json.dumps(validate_package(args.target, args.capability), sort_keys=True)); return 0
    if args.op == "replay-package":
        replay = validate_package(args.target, args.capability)
        replay["capability"] = {"path": args.capability, "sha256": digest(ROOT / args.capability)}
        replay["entrypoint"] = "scripts/sc/skill_package_replay.py"; replay["command"] = ["py", "-3", "-B", "scripts/sc/skill_package_replay.py", "replay-package", "--target", args.target, "--capability", args.capability, "--probe-mode", args.probe_mode]
        receipt = {"schema_version": "jimuyun.tc-d1-historical-replay-receipt.v1", "status": "pass", "exit_code": 0, "authorizes": [], "historical_portability": "machine-bound", "historical_validator": {"path": "execution-plans/2026-08-01-refactor-acceptance-toolchain-compact-vdd/tools/validate_implementation.py", "sha256": digest(ROOT / "execution-plans/2026-08-01-refactor-acceptance-toolchain-compact-vdd/tools/validate_implementation.py")}, "historical_command_evidence": {"path": "execution-plans/2026-08-01-refactor-acceptance-toolchain-compact-vdd/95-implementation-evolution-and-completion-report.md", "sha256": digest(ROOT / "execution-plans/2026-08-01-refactor-acceptance-toolchain-compact-vdd/95-implementation-evolution-and-completion-report.md"), "command": ["py", "-3", "execution-plans/2026-08-01-refactor-acceptance-toolchain-compact-vdd/tools/validate_implementation.py"], "recorded_result": "pass"}, "current_wrapper_replay": replay}
        print(json.dumps(receipt, sort_keys=True)); return 0
    matrix_path = contained(ROOT / args.matrix, ROOT, "matrix")
    matrix = json.loads(matrix_path.read_text(encoding="utf-8")); results = []
    cases = matrix.get("cases")
    if matrix.get("schema_version") != "jimuyun.stable-candidate-replay-matrix.v2" or not isinstance(cases, list) or not cases:
        raise ValueError("matrix must contain executable v2 cases")
    for case in cases:
        target = contained(ROOT / case["target"], ROOT, "matrix target")
        validator, value = capability(contained(ROOT / case["capability"], ROOT, "matrix capability"))
        observed = run_validator(validator, value, target)
        expected = case["expected_exit"]
        matched = observed.returncode != 0 if expected == "nonzero" else observed.returncode == expected
        results.append({"case_id": case["case_id"], "status": "pass" if matched else "fail", "executed": True, "observed_exit_code": observed.returncode, "stdout_sha256": "sha256:" + hashlib.sha256(observed.stdout.encode()).hexdigest(), "stderr_sha256": "sha256:" + hashlib.sha256(observed.stderr.encode()).hexdigest()})
    status = "pass" if all(item["status"] == "pass" for item in results) else "fail"
    print(json.dumps({"status": status, "exit_code": 0 if status == "pass" else 1, "case_results": results, "authorizes": [], "runner_entrypoint": "scripts/sc/skill_package_replay.py", "command": ["py", "-3", "-B", "scripts/sc/skill_package_replay.py", "replay-matrix", "--matrix", args.matrix], "matrix_path": args.matrix, "matrix_sha256": digest(matrix_path)}, sort_keys=True)); return 0 if status == "pass" else 1
if __name__ == "__main__": raise SystemExit(main())
