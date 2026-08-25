from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import re
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT / "execution-plans/2026-08-24-phase-b-c-identity-isolation-workspace-recovery"


def _hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _root_hash(paths: list[Path]) -> str:
    payload = []
    for path in paths:
        if path.is_file():
            payload.append((path.relative_to(ROOT).as_posix(), _hash(path)))
    return "sha256:" + hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def current_candidate_identity(slice_id: str | None = None) -> dict[str, str]:
    contract = PLAN / "implementation-contract.v1.json"
    registry = PLAN / "command-registry.v1.json"
    authority = PLAN / "authority-manifest.v1.json"
    validator = Path(__file__).resolve()
    roots = [contract, registry, authority, validator]
    if slice_id:
        roots.append(PLAN / "implementation-slices.md")
    candidate = _root_hash(roots)
    return {
        "candidate_hash": candidate,
        "predicate_input_root": candidate,
        "authority_root": _hash(authority),
        "validator_root": _hash(validator),
        "validator_version": "phase-b-c-identity-isolation-workspace-recovery.validate-all.v1",
        "closure_definition_hash": _root_hash([PLAN / "implementation-slices.md", PLAN / "requirements.v1.json"]),
        "validator_hash": _hash(validator),
    }


def validation_snapshot(slice_id: str | None = None) -> dict[str, str]:
    return current_candidate_identity(slice_id)


def slice_validation_snapshot(slice_id: str | None = None) -> dict[str, str]:
    return current_candidate_identity(slice_id)


def _run(command: list[str], timeout: int = 180) -> dict[str, object]:
    started = datetime.now(timezone.utc).isoformat()
    with tempfile.TemporaryDirectory(prefix="phasea-validator-") as temp_dir:
        stdout_path = Path(temp_dir) / "stdout.log"
        stderr_path = Path(temp_dir) / "stderr.log"
        with stdout_path.open("w", encoding="utf-8") as stdout_file, stderr_path.open("w", encoding="utf-8") as stderr_file:
            process = subprocess.Popen(command, cwd=ROOT, stdout=stdout_file, stderr=stderr_file, close_fds=True, creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, check=False)
                else:
                    process.kill()
                process.wait()
                stdout = stdout_path.read_text(encoding="utf-8", errors="replace")
                stderr = stderr_path.read_text(encoding="utf-8", errors="replace")
                return {"command": command, "exit_code": 124, "failure": "validation-timeout", "started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(), "stdout_tail": stdout[-4000:], "stderr_tail": stderr[-4000:]}
        stdout = stdout_path.read_text(encoding="utf-8", errors="replace")
        stderr = stderr_path.read_text(encoding="utf-8", errors="replace")
    return {"command": command, "exit_code": process.returncode, "started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(), "stdout_tail": stdout[-4000:], "stderr_tail": stderr[-4000:]}


def _dotnet_shards() -> tuple[list[dict[str, object]], int]:
    test_root = ROOT / "PhaseA.Platform.Tests"
    test_binary = test_root / "bin" / "Debug" / "net8.0" / "PhaseA.Platform.Tests.dll"
    if not test_binary.is_file() or test_binary.stat().st_size == 0:
        return [{"command": ["dotnet", "test"], "exit_code": 1, "failure": "missing-current-build-artifact"}], 0
    inventory_count = 0
    test_classes: set[str] = set()
    for source in test_root.rglob("*.cs"):
        try:
            text = source.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        method_count = len(re.findall(r"^\s*\[(?:Fact|Theory)(?:\([^\]]*)?\]", text, re.MULTILINE))
        inventory_count += method_count
        if method_count:
            scan_text = re.sub(r'""".*?"""', '', text, flags=re.DOTALL)
            scan_text = re.sub(r'(?<!@)"(?:\\.|[^"\\])*"', '', scan_text)
            namespace = re.search(r"^\s*namespace\s+([A-Za-z0-9_.]+)\s*;", scan_text, re.MULTILINE)
            class_matches = list(re.finditer(r"\b(?:public|internal|private|protected)?\s*(?:sealed\s+|abstract\s+)?class\s+([A-Za-z0-9_]+)", scan_text))
            for match in class_matches:
                body_start = scan_text.find("{", match.end())
                if body_start < 0:
                    continue
                depth = 0
                body_end = len(text)
                for position in range(body_start, len(scan_text)):
                    if scan_text[position] == "{": depth += 1
                    elif scan_text[position] == "}":
                        depth -= 1
                        if depth == 0:
                            body_end = position
                            break
                body = scan_text[body_start:body_end]
                if re.search(r"^\s*\[(?:Fact|Theory)(?:\([^\]]*)?\]", body, re.MULTILINE):
                    test_classes.add(f"{namespace.group(1) if namespace else 'PhaseA.Platform.Tests'}.{match.group(1)}")
    if inventory_count == 0:
        return [{"command": ["dotnet", "test"], "exit_code": 1, "failure": "empty-test-inventory"}], 0
    if not test_classes:
        return [{"command": ["dotnet", "test"], "exit_code": 1, "failure": "empty-test-class-inventory"}], 0
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    diagnostics = PLAN / "terminal" / "dotnet-test-runs" / run_id
    diagnostics.mkdir(parents=True, exist_ok=True)
    def run_class(index_and_class: tuple[int, str]) -> dict[str, object]:
        index, cls = index_and_class
        result = _run([
            "dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj",
            "--no-restore", "--no-build", "--disable-build-servers", "--nologo",
            "--blame-hang-timeout", "60s", "--blame-hang-dump-type", "none",
            "--filter", f"FullyQualifiedName~{cls}",
        ], 600)
        result.update({"run_id": run_id, "class": cls, "class_index": index, "test_inventory_count": inventory_count})
        if "已通过" not in str(result.get("stdout_tail", "")) and "Passed!" not in str(result.get("stdout_tail", "")):
            result["exit_code"] = 1
            result["failure"] = "test-shard-produced-no-pass-summary"
        (diagnostics / f"{index:04d}-{cls.rsplit('.', 1)[-1]}.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return result

    results: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(run_class, item) for item in enumerate(sorted(test_classes))]
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda item: int(item["class_index"]))
    return results, inventory_count


def main() -> int:
    dotnet_results, inventory_count = _dotnet_shards()
    results = [{"type": "dotnet-shards", "inventory_count": inventory_count, "shards": dotnet_results}]
    (PLAN / "terminal").mkdir(parents=True, exist_ok=True)
    (PLAN / "terminal" / "dotnet-shard-diagnostics.json").write_text(json.dumps(results[0], indent=2) + "\n", encoding="utf-8")
    if inventory_count == 0 or any(item.get("exit_code") != 0 for item in dotnet_results):
        print(json.dumps({"status": "fail", "plan_id": "2026-08-24-phase-b-c-identity-isolation-workspace-recovery", "results": results, "authorizes": []}, sort_keys=True))
        return 1
    pytest_result = _run([sys.executable, "-m", "pytest", "tests/phase_b_c_identity_isolation", "-q"], 180)
    results.append({"type": "python-behavior", **pytest_result})
    if pytest_result["exit_code"] != 0:
        print(json.dumps({"status": "fail", "plan_id": "2026-08-24-phase-b-c-identity-isolation-workspace-recovery", "results": results, "authorizes": []}, sort_keys=True))
        return int(pytest_result["exit_code"])
    print(json.dumps({"status": "pass", "validated_state": "implementation-complete", "plan_id": "2026-08-24-phase-b-c-identity-isolation-workspace-recovery", "results": results, "authorizes": []}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
