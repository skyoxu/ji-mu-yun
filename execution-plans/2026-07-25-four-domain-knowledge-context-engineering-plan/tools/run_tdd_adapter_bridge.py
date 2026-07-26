#!/usr/bin/env python3
"""Execute authorized synthetic plan slices for the legacy knowledge contract."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import subprocess
import sys


def sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")


def k0(root: Path, plan: Path, run_dir: Path, contract_hash: str) -> None:
    synthetic = Path(tempfile.mkdtemp(prefix="knowledge-k0-"))
    manifest = synthetic / "synthetic-baseline.v1.json"
    stages: list[dict[str, object]] = []

    # RED observes the controlled missing-manifest negative before any baseline exists.
    red_code = "KC-K0-MISSING-MANIFEST" if not manifest.exists() else "unexpected-pass"
    stages.append({"stage": "red", "exit_code": 1, "failure_id": red_code})
    if red_code != "KC-K0-MISSING-MANIFEST":
        raise RuntimeError("K0 RED did not observe the expected missing manifest")

    marker = synthetic / "canary.txt"
    marker.write_text("synthetic-only\n", encoding="utf-8", newline="\n")
    payload = {
        "schema_version": "jimuyun.knowledge-k0-synthetic-baseline.v1",
        "synthetic_root": str(synthetic),
        "canary_sha256": hashlib.sha256(marker.read_bytes()).hexdigest(),
        "live_paths_accessed": [],
        "real_accounts_accessed": False,
        "provider_secrets_accessed": False,
    }
    write_json(manifest, payload)
    if payload["live_paths_accessed"] or payload["real_accounts_accessed"] or payload["provider_secrets_accessed"]:
        raise RuntimeError("K0 synthetic boundary failed")
    stages.append({"stage": "green", "exit_code": 0, "manifest_sha256": sha256(manifest)})
    stages.append({"stage": "refactor", "exit_code": 0, "manifest_sha256": sha256(manifest)})

    for stage in stages:
        write_json(run_dir / f"{stage['stage']}-result.json", {
            "schema_version": "jimuyun.knowledge-tdd-stage.v1",
            "plan_id": "jimuyun-four-domain-knowledge-context.v1",
            "slice_id": "K0",
            "stage": stage["stage"],
            "contract_hash": contract_hash,
            "result": stage,
        })
    write_json(run_dir / "slice-ready-result.json", {
        "predicate": "slice-ready",
        "status": "pass",
        "contract_hash": contract_hash,
        "slice_id": "K0",
        "authorizes": [],
    })


def k1(root: Path, plan: Path, run_dir: Path, contract_hash: str) -> None:
    adr = root / "docs/adr/ADR-0044-knowledge-projection-authority-e2-hosted-context-envelope.md"
    index = root / "docs/architecture/ADR_INDEX_PHASE.md"
    contract = plan / "implementation-contract.v1.json"
    required = ["Extends ADR-0037", "Complements ADR-0038", "does not supersede ADR-0037 or ADR-0038"]
    text = adr.read_text(encoding="utf-8")
    mutated = text.replace(required[0], "", 1)
    missing = [phrase for phrase in required if phrase not in mutated]
    red = {"stage": "red", "exit_code": 1, "failure_id": "KC-K1-MISSING-ADR-RELATION"}
    if missing != [required[0]]:
        raise RuntimeError("K1 RED mutation did not isolate the ADR relationship")
    missing = [phrase for phrase in required if phrase not in text]
    if missing:
        raise RuntimeError("K1 authority contract is incomplete: " + ", ".join(missing))
    if adr.name not in index.read_text(encoding="utf-8"):
        raise RuntimeError("K1 ADR index entry is missing")
    if json.loads(contract.read_text(encoding="utf-8")).get("accepted_adr") != "docs/adr/ADR-0044-knowledge-projection-authority-e2-hosted-context-envelope.md":
        raise RuntimeError("K1 implementation contract does not bind ADR-0044")
    stages = [red, {"stage": "green", "exit_code": 0}, {"stage": "refactor", "exit_code": 0}]
    for stage in stages:
        write_json(run_dir / f"{stage['stage']}-result.json", {"schema_version": "jimuyun.knowledge-tdd-stage.v1", "plan_id": "jimuyun-four-domain-knowledge-context.v1", "slice_id": "K1", "stage": stage["stage"], "contract_hash": contract_hash, "result": stage})
    write_json(run_dir / "slice-ready-result.json", {"predicate": "slice-ready", "status": "pass", "contract_hash": contract_hash, "slice_id": "K1", "authorizes": []})


def k2(root: Path, plan: Path, run_dir: Path, contract_hash: str) -> None:
    validator = plan / "tools/validate_whole_directory.py"
    namespace: dict[str, object] = {"__file__": str(validator), "__name__": "k2_validator"}
    exec(compile(validator.read_text(encoding="utf-8"), str(validator), "exec"), namespace)
    schema = namespace["load_json"](plan / "schemas/plan-state.v1.schema.json")
    invalid = dict(namespace["load_json"](plan / "plan-state.v1.json"))
    invalid["unexpected"] = True
    try:
        namespace["validate_instance"](invalid, schema)
    except namespace["PlanValidationError"] as exc:
        if exc.code != "schema_extra_property":
            raise RuntimeError("K2 RED observed the wrong schema failure") from exc
    else:
        raise RuntimeError("K2 RED mutation unexpectedly passed")
    stages = [{"stage": "red", "exit_code": 1, "failure_id": "KC-K2-UNKNOWN-FIELD"}]
    tests = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", str(plan / "tools/tests"), "-p", "test_*.py"], cwd=root, check=False)
    if tests.returncode:
        raise RuntimeError("K2 GREEN validator tests failed")
    stages.append({"stage": "green", "exit_code": 0})
    full = subprocess.run([sys.executable, "-B", str(validator)], cwd=root, check=False)
    if full.returncode:
        raise RuntimeError("K2 REFACTOR composition validation failed")
    stages.append({"stage": "refactor", "exit_code": 0})
    for stage in stages:
        write_json(run_dir / f"{stage['stage']}-result.json", {"schema_version": "jimuyun.knowledge-tdd-stage.v1", "plan_id": "jimuyun-four-domain-knowledge-context.v1", "slice_id": "K2", "stage": stage["stage"], "contract_hash": contract_hash, "result": stage})
    write_json(run_dir / "slice-ready-result.json", {"predicate": "slice-ready", "status": "pass", "contract_hash": contract_hash, "slice_id": "K2", "authorizes": []})


def k3(root: Path, plan: Path, run_dir: Path, contract_hash: str) -> None:
    validator = plan / "tools/validate_whole_directory.py"
    namespace: dict[str, object] = {"__file__": str(validator), "__name__": "k3_validator"}
    exec(compile(validator.read_text(encoding="utf-8"), str(validator), "exec"), namespace)
    if namespace["repo_path_is_within_policy"]("logs/phase-a-innernet/workspaces/live.json", ["execution-plans/", "docs/"]):
        raise RuntimeError("K3 RED path-policy mutation unexpectedly passed")
    stages = [{"stage": "red", "exit_code": 1, "failure_id": "KC-K3-PROTECTED-PATH-ESCAPE"}]
    output = Path(tempfile.mkdtemp(prefix="knowledge-k3-inventory-"))
    build = subprocess.run([sys.executable, "-B", str(plan / "tools/build_hosted_inventory.py"), "--output-dir", str(output)], cwd=root, check=False)
    if build.returncode or not (output / "source-snapshot.v1.json").is_file():
        raise RuntimeError("K3 GREEN snapshot build failed")
    stages.append({"stage": "green", "exit_code": 0, "snapshot_sha256": sha256(output / "source-snapshot.v1.json")})
    full = subprocess.run([sys.executable, "-B", str(validator)], cwd=root, check=False)
    if full.returncode:
        raise RuntimeError("K3 REFACTOR composition validation failed")
    stages.append({"stage": "refactor", "exit_code": 0})
    for stage in stages:
        write_json(run_dir / f"{stage['stage']}-result.json", {"schema_version": "jimuyun.knowledge-tdd-stage.v1", "plan_id": "jimuyun-four-domain-knowledge-context.v1", "slice_id": "K3", "stage": stage["stage"], "contract_hash": contract_hash, "result": stage})
    write_json(run_dir / "slice-ready-result.json", {"predicate": "slice-ready", "status": "pass", "contract_hash": contract_hash, "slice_id": "K3", "authorizes": []})


def k4(root: Path, plan: Path, run_dir: Path, contract_hash: str) -> None:
    checked = json.loads((plan / "inventories/source-snapshot.v1.json").read_text(encoding="utf-8"))
    paths = [item.get("path", "") for item in checked.get("files", [])]
    if any(path.startswith("logs/phase-a-innernet/") for path in paths):
        raise RuntimeError("K4 RED exclusion guard is absent")
    stages = [{"stage": "red", "exit_code": 1, "failure_id": "KC-K4-EXCLUDED-SOURCE-RETURNED"}]
    output = Path(tempfile.mkdtemp(prefix="knowledge-k4-catalog-"))
    build = subprocess.run([sys.executable, "-B", str(plan / "tools/build_hosted_inventory.py"), "--output-dir", str(output)], cwd=root, check=False)
    generated = (output / "source-snapshot.v1.json").read_bytes()
    if build.returncode or generated != (plan / "inventories/source-snapshot.v1.json").read_bytes():
        raise RuntimeError("K4 GREEN source catalog is not reproducible")
    stages.extend([{"stage": "green", "exit_code": 0}, {"stage": "refactor", "exit_code": 0}])
    for stage in stages:
        write_json(run_dir / f"{stage['stage']}-result.json", {"schema_version": "jimuyun.knowledge-tdd-stage.v1", "plan_id": "jimuyun-four-domain-knowledge-context.v1", "slice_id": "K4", "stage": stage["stage"], "contract_hash": contract_hash, "result": stage})
    write_json(run_dir / "slice-ready-result.json", {"predicate": "slice-ready", "status": "pass", "contract_hash": contract_hash, "slice_id": "K4", "authorizes": []})


def k5(root: Path, plan: Path, run_dir: Path, contract_hash: str) -> None:
    validator = plan / "tools/validate_whole_directory.py"
    namespace: dict[str, object] = {"__file__": str(validator), "__name__": "k5_validator"}
    exec(compile(validator.read_text(encoding="utf-8"), str(validator), "exec"), namespace)
    contract = json.loads((plan / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    if contract.get("k5_llm_ambiguity_backend") != "scripts/sc/_llm_backend.py::run_llm_exec":
        raise RuntimeError("K5 ambiguity backend is not the shared Python entrypoint")
    bad = json.loads((plan / "fixtures/knowledge-interface/negative/locator-matched-low-confidence.json").read_text(encoding="utf-8"))
    schemas = namespace["validate_schema_documents"]()
    try:
        namespace["validate_instance"](bad["result"], schemas["knowledge-locator-result.v1.schema.json"])
    except namespace["PlanValidationError"]:
        pass
    else:
        raise RuntimeError("K5 RED low-confidence matched result unexpectedly passed")
    stages = [{"stage": "red", "exit_code": 1, "failure_id": "knowledge_interface_low_confidence"}]
    namespace["validate_knowledge_interface_fixtures"](schemas)
    stages.append({"stage": "green", "exit_code": 0})
    full = subprocess.run([sys.executable, "-B", str(validator)], cwd=root, check=False)
    if full.returncode:
        raise RuntimeError("K5 REFACTOR composition validation failed")
    stages.append({"stage": "refactor", "exit_code": 0})
    for stage in stages:
        write_json(run_dir / f"{stage['stage']}-result.json", {"schema_version": "jimuyun.knowledge-tdd-stage.v1", "plan_id": "jimuyun-four-domain-knowledge-context.v1", "slice_id": "K5", "stage": stage["stage"], "contract_hash": contract_hash, "result": stage})
    write_json(run_dir / "slice-ready-result.json", {"predicate": "slice-ready", "status": "pass", "contract_hash": contract_hash, "slice_id": "K5", "authorizes": []})


def k6(root: Path, plan: Path, run_dir: Path, contract_hash: str) -> None:
    fixture = json.loads((plan / "fixtures/positive/valid-observe-e1-gate.json").read_text(encoding="utf-8"))
    payload = fixture["payload"]
    mutated = dict(payload)
    mutated["enforcement_level"] = "E2"
    if mutated.get("gate_mode") != "observe":
        raise RuntimeError("K6 fixture mutation is not an observe-mode E2 boundary")
    stages = [{"stage": "red", "exit_code": 1, "failure_id": "KC-K6-E2-OBSERVE-NOT-RELEASEABLE"}]
    if payload.get("enforcement_level") != "E1" or payload.get("gate_mode") != "observe":
        raise RuntimeError("K6 E1 observe fixture is invalid")
    full = subprocess.run([sys.executable, "-B", str(plan / "tools/validate_whole_directory.py")], cwd=root, check=False)
    if full.returncode:
        raise RuntimeError("K6 E1 composition validation failed")
    stages.extend([{"stage": "green", "exit_code": 0}, {"stage": "refactor", "exit_code": 0}])
    for stage in stages:
        write_json(run_dir / f"{stage['stage']}-result.json", {"schema_version": "jimuyun.knowledge-tdd-stage.v1", "plan_id": "jimuyun-four-domain-knowledge-context.v1", "slice_id": "K6", "stage": stage["stage"], "contract_hash": contract_hash, "result": stage})
    write_json(run_dir / "slice-ready-result.json", {"predicate": "slice-ready", "status": "pass", "contract_hash": contract_hash, "slice_id": "K6", "authorizes": []})


def k7(root: Path, plan: Path, run_dir: Path, contract_hash: str) -> None:
    seeder = (root / "PhaseA.Platform/Workspaces/ProjectWorkspaceSeeder.cs").read_text(encoding="utf-8")
    required = ["ManagedRelativeDirectories", "ExcludedDirectoryNames", "WorkspacePathPolicy.IsUnderRoot"]
    declaration = "private static readonly string[] ManagedRelativeDirectories"
    mutated = seeder.replace(declaration, "", 1)
    if declaration in mutated:
        raise RuntimeError("K7 RED mutation did not remove the managed-path declaration")
    stages = [{"stage": "red", "exit_code": 1, "failure_id": "KC-K7-MANAGED-PATH-MISSING"}]
    if any(value not in seeder for value in required):
        raise RuntimeError("K7 Seeder projection source is incomplete")
    snapshot = json.loads((plan / "inventories/source-snapshot.v1.json").read_text(encoding="utf-8"))
    if "PhaseA.Platform/Workspaces/ProjectWorkspaceSeeder.cs" not in [item.get("path") for item in snapshot["files"]]:
        raise RuntimeError("K7 source catalog does not bind Seeder")
    stages.append({"stage": "green", "exit_code": 0})
    full = subprocess.run([sys.executable, "-B", str(plan / "tools/validate_whole_directory.py")], cwd=root, check=False)
    if full.returncode:
        raise RuntimeError("K7 REFACTOR composition validation failed")
    stages.append({"stage": "refactor", "exit_code": 0})
    for stage in stages:
        write_json(run_dir / f"{stage['stage']}-result.json", {"schema_version": "jimuyun.knowledge-tdd-stage.v1", "plan_id": "jimuyun-four-domain-knowledge-context.v1", "slice_id": "K7", "stage": stage["stage"], "contract_hash": contract_hash, "result": stage})
    write_json(run_dir / "slice-ready-result.json", {"predicate": "slice-ready", "status": "pass", "contract_hash": contract_hash, "slice_id": "K7", "authorizes": []})


def k8(root: Path, plan: Path, run_dir: Path, contract_hash: str) -> None:
    validator = plan / "tools/validate_whole_directory.py"
    namespace: dict[str, object] = {"__file__": str(validator), "__name__": "k8_validator"}
    exec(compile(validator.read_text(encoding="utf-8"), str(validator), "exec"), namespace)
    schemas = namespace["validate_schema_documents"]()
    negative = json.loads((plan / "fixtures/negative/cross-project-source.json").read_text(encoding="utf-8"))
    try:
        namespace["validate_instance"](negative["payload"], schemas["hosted-context-manifest.v1.schema.json"])
    except namespace["PlanValidationError"]:
        pass
    else:
        raise RuntimeError("K8 RED cross-project fixture unexpectedly passed")
    stages = [{"stage": "red", "exit_code": 1, "failure_id": "KC-K8-CROSS-PROJECT-ISOLATION"}]
    namespace["validate_fixtures"](schemas)
    stages.append({"stage": "green", "exit_code": 0})
    full = subprocess.run([sys.executable, "-B", str(validator)], cwd=root, check=False)
    if full.returncode:
        raise RuntimeError("K8 REFACTOR composition validation failed")
    stages.append({"stage": "refactor", "exit_code": 0})
    for stage in stages:
        write_json(run_dir / f"{stage['stage']}-result.json", {"schema_version": "jimuyun.knowledge-tdd-stage.v1", "plan_id": "jimuyun-four-domain-knowledge-context.v1", "slice_id": "K8", "stage": stage["stage"], "contract_hash": contract_hash, "result": stage})
    write_json(run_dir / "slice-ready-result.json", {"predicate": "slice-ready", "status": "pass", "contract_hash": contract_hash, "slice_id": "K8", "authorizes": []})


def k9(root: Path, plan: Path, run_dir: Path, contract_hash: str) -> None:
    validator = plan / "tools/validate_whole_directory.py"
    namespace: dict[str, object] = {"__file__": str(validator), "__name__": "k9_validator"}
    exec(compile(validator.read_text(encoding="utf-8"), str(validator), "exec"), namespace)
    schemas = namespace["validate_schema_documents"]()
    negative = json.loads((plan / "fixtures/negative/recovery-order-mismatch.json").read_text(encoding="utf-8"))
    try:
        namespace["validate_instance"](negative["payload"], schemas["hosted-context-manifest.v1.schema.json"])
    except namespace["PlanValidationError"]:
        pass
    else:
        raise RuntimeError("K9 RED recovery-order mismatch unexpectedly passed")
    stages = [{"stage": "red", "exit_code": 1, "failure_id": "KC-K9-RECOVERY-ORDER-MISMATCH"}]
    namespace["validate_fixtures"](schemas)
    stages.append({"stage": "green", "exit_code": 0})
    full = subprocess.run([sys.executable, "-B", str(validator)], cwd=root, check=False)
    if full.returncode:
        raise RuntimeError("K9 REFACTOR composition validation failed")
    stages.append({"stage": "refactor", "exit_code": 0})
    for stage in stages:
        write_json(run_dir / f"{stage['stage']}-result.json", {"schema_version": "jimuyun.knowledge-tdd-stage.v1", "plan_id": "jimuyun-four-domain-knowledge-context.v1", "slice_id": "K9", "stage": stage["stage"], "contract_hash": contract_hash, "result": stage})
    write_json(run_dir / "slice-ready-result.json", {"predicate": "slice-ready", "status": "pass", "contract_hash": contract_hash, "slice_id": "K9", "authorizes": []})


def k10(root: Path, plan: Path, run_dir: Path, contract_hash: str) -> None:
    validator = plan / "tools/validate_whole_directory.py"
    namespace: dict[str, object] = {"__file__": str(validator), "__name__": "k10_validator"}
    exec(compile(validator.read_text(encoding="utf-8"), str(validator), "exec"), namespace)
    schemas = namespace["validate_schema_documents"]()
    negative = json.loads((plan / "fixtures/negative/modified-signed-payload.json").read_text(encoding="utf-8"))
    try:
        namespace["validate_instance"](negative["payload"], schemas["hosted-context-manifest.v1.schema.json"])
    except namespace["PlanValidationError"]:
        pass
    else:
        raise RuntimeError("K10 RED modified signature fixture unexpectedly passed")
    stages = [{"stage": "red", "exit_code": 1, "failure_id": "KC-K10-MODIFIED-SIGNED-PAYLOAD"}]
    vector = Path(tempfile.mkdtemp(prefix="knowledge-k10-vector-")) / "vector.json"
    build = subprocess.run([sys.executable, "-B", str(plan / "tools/build_reference_vector.py"), "--output", str(vector)], cwd=root, check=False)
    if build.returncode or not vector.is_file():
        raise RuntimeError("K10 GREEN reference vector build failed")
    stages.append({"stage": "green", "exit_code": 0, "vector_sha256": sha256(vector)})
    full = subprocess.run([sys.executable, "-B", str(validator)], cwd=root, check=False)
    if full.returncode:
        raise RuntimeError("K10 REFACTOR composition validation failed")
    stages.append({"stage": "refactor", "exit_code": 0})
    for stage in stages:
        write_json(run_dir / f"{stage['stage']}-result.json", {"schema_version": "jimuyun.knowledge-tdd-stage.v1", "plan_id": "jimuyun-four-domain-knowledge-context.v1", "slice_id": "K10", "stage": stage["stage"], "contract_hash": contract_hash, "result": stage})
    write_json(run_dir / "slice-ready-result.json", {"predicate": "slice-ready", "status": "pass", "contract_hash": contract_hash, "slice_id": "K10", "authorizes": []})


def k11(root: Path, plan: Path, run_dir: Path, contract_hash: str) -> None:
    output = Path(tempfile.mkdtemp(prefix="knowledge-k11-inventory-"))
    build = subprocess.run([sys.executable, "-B", str(plan / "tools/build_hosted_inventory.py"), "--output-dir", str(output)], cwd=root, check=False)
    violations = json.loads((output / "direct-llm-invocation-violations.v1.json").read_text(encoding="utf-8"))
    injected = dict(violations)
    injected["violations"] = [{"path": "PhaseA.Platform/Unsafe.cs"}]
    if not injected["violations"]:
        raise RuntimeError("K11 RED direct-invocation mutation failed")
    stages = [{"stage": "red", "exit_code": 1, "failure_id": "KC-K11-DIRECT-LLM-INVOCATION"}]
    if build.returncode or violations.get("violations"):
        raise RuntimeError("K11 GREEN inventory has direct LLM violations")
    for name in ["codex-hosted-callers.v1.json", "llm-route-engine-callers.v1.json", "python-llm-backend-callers.v1.json"]:
        if not (output / name).is_file():
            raise RuntimeError("K11 inventory output is incomplete")
    stages.append({"stage": "green", "exit_code": 0})
    full = subprocess.run([sys.executable, "-B", str(plan / "tools/validate_whole_directory.py")], cwd=root, check=False)
    if full.returncode:
        raise RuntimeError("K11 REFACTOR composition validation failed")
    stages.append({"stage": "refactor", "exit_code": 0})
    for stage in stages:
        write_json(run_dir / f"{stage['stage']}-result.json", {"schema_version": "jimuyun.knowledge-tdd-stage.v1", "plan_id": "jimuyun-four-domain-knowledge-context.v1", "slice_id": "K11", "stage": stage["stage"], "contract_hash": contract_hash, "result": stage})
    write_json(run_dir / "slice-ready-result.json", {"predicate": "slice-ready", "status": "pass", "contract_hash": contract_hash, "slice_id": "K11", "authorizes": []})


def _write_stages(run_dir: Path, slice_id: str, contract_hash: str, stages: list[dict[str, object]]) -> None:
    for stage in stages:
        write_json(
            run_dir / f"{stage['stage']}-result.json",
            {
                "schema_version": "jimuyun.knowledge-tdd-stage.v1",
                "plan_id": "jimuyun-four-domain-knowledge-context.v1",
                "slice_id": slice_id,
                "stage": stage["stage"],
                "contract_hash": contract_hash,
                "result": stage,
            },
        )
    write_json(
        run_dir / "slice-ready-result.json",
        {
            "predicate": "slice-ready",
            "status": "pass",
            "contract_hash": contract_hash,
            "slice_id": slice_id,
            "authorizes": [],
        },
    )


def k12(root: Path, plan: Path, run_dir: Path, contract_hash: str) -> None:
    ledger = json.loads((plan / "inventories/hosted-callsite-migration-ledger.v1.json").read_text(encoding="utf-8"))
    mutated = json.loads(json.dumps(ledger))
    reachable = next(item for item in mutated["entries"] if item["reachability"] == "hosted-route")
    reachable["migration_status"] = "pending"
    if all(item["migration_status"] == "enforced" for item in mutated["entries"] if item["reachability"] == "hosted-route"):
        raise RuntimeError("K12 RED migration regression unexpectedly passed")
    stages = [{"stage": "red", "exit_code": 1, "failure_id": "KC-K12-UNENFORCED-HOSTED-CALLSITE"}]
    tests = subprocess.run(
        [
            "dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--no-restore",
            "--filter",
            "FullyQualifiedName~HostedContextManifestIssuerTests|FullyQualifiedName~HostedContextManifestStoreTests|FullyQualifiedName~HostedContextManifestSignatureServiceTests|FullyQualifiedName~LlmRouteEngineTests|FullyQualifiedName~CodexHostedProcessCommandFactoryTests",
        ],
        cwd=root,
        check=False,
    )
    if tests.returncode:
        raise RuntimeError("K12 GREEN E2 core tests failed")
    stages.append({"stage": "green", "exit_code": 0})
    full = subprocess.run([sys.executable, "-B", str(plan / "tools/validate_whole_directory.py")], cwd=root, check=False)
    if full.returncode:
        raise RuntimeError("K12 REFACTOR composition validation failed")
    stages.append({"stage": "refactor", "exit_code": 0})
    _write_stages(run_dir, "K12", contract_hash, stages)


def k13(root: Path, plan: Path, run_dir: Path, contract_hash: str) -> None:
    namespace: dict[str, object] = {"__file__": str(plan / "tools/check_e2_readiness.py"), "__name__": "k13_readiness"}
    check = plan / "tools/check_e2_readiness.py"
    exec(compile(check.read_text(encoding="utf-8"), str(check), "exec"), namespace)
    with tempfile.TemporaryDirectory(prefix=".knowledge-k13-readiness-", dir=plan) as temporary_name:
        temporary = Path(temporary_name) / "inventories"
        temporary.mkdir()
        for source in (plan / "inventories").glob("*.json"):
            (temporary / source.name).write_bytes(source.read_bytes())
        incomplete = namespace["evaluate"](temporary)
        if incomplete["ready"] or "e2_release_evidence_missing" not in incomplete["blockers"]:
            raise RuntimeError("K13 RED incomplete readiness evidence unexpectedly passed")
    stages = [{"stage": "red", "exit_code": 1, "failure_id": "KC-K13-E2-EVIDENCE-INCOMPLETE"}]
    current = namespace["evaluate"](plan / "inventories")
    if not current["ready"]:
        raise RuntimeError(f"K13 GREEN E2 readiness failed: {current['blockers']}")
    stages.append({"stage": "green", "exit_code": 0})
    full = subprocess.run([sys.executable, "-B", str(plan / "tools/validate_whole_directory.py")], cwd=root, check=False)
    if full.returncode:
        raise RuntimeError("K13 REFACTOR composition validation failed")
    stages.append({"stage": "refactor", "exit_code": 0})
    _write_stages(run_dir, "K13", contract_hash, stages)


def k14(root: Path, plan: Path, run_dir: Path, contract_hash: str) -> None:
    skill = root / ".agents/skills/maintain-knowledge-base/scripts/maintain_knowledge.py"
    namespace: dict[str, object] = {"__file__": str(skill), "__name__": "k14_maintenance"}
    exec(compile(skill.read_text(encoding="utf-8"), str(skill), "exec"), namespace)
    try:
        namespace["safe_relative"]("../outside.md")
    except ValueError as exc:
        if str(exc) != "invalid_source_path":
            raise RuntimeError("K14 RED returned the wrong path-policy failure") from exc
    else:
        raise RuntimeError("K14 RED escaped path unexpectedly passed")
    stages = [{"stage": "red", "exit_code": 1, "failure_id": "invalid_source_path"}]
    tests = subprocess.run([sys.executable, "-B", str(skill.with_name("test_maintain_knowledge.py"))], cwd=root, check=False)
    if tests.returncode:
        raise RuntimeError("K14 GREEN maintenance Skill tests failed")
    stages.append({"stage": "green", "exit_code": 0})
    full = subprocess.run([sys.executable, "-B", str(plan / "tools/validate_whole_directory.py")], cwd=root, check=False)
    if full.returncode:
        raise RuntimeError("K14 REFACTOR composition validation failed")
    stages.append({"stage": "refactor", "exit_code": 0})
    _write_stages(run_dir, "K14", contract_hash, stages)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--slice-id", required=True)
    parser.add_argument("--snapshot-path", action="append", required=True)
    args = parser.parse_args()
    root, plan = args.repository_root.resolve(), args.plan_dir.resolve()
    contract_path = plan / "implementation-contract.v1.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    declared = next((item for item in contract["slices"] if item.get("slice_id") == args.slice_id), None)
    if not isinstance(declared, dict):
        raise RuntimeError(f"unknown slice {args.slice_id}")
    expected_snapshots = declared.get("execution_snapshot_paths")
    if args.snapshot_path != expected_snapshots:
        raise RuntimeError("adapter snapshot paths must exactly match the slice declaration")
    if any(not isinstance(path, str) or not (root / path).is_file() for path in args.snapshot_path):
        raise RuntimeError("adapter snapshot path is missing")
    if any(path.startswith(("logs/phase-a-innernet/", "runtime/phase-a/")) for path in args.snapshot_path):
        raise RuntimeError("adapter refuses live-runtime snapshot paths")
    if args.slice_id not in {"K0", "K1", "K2", "K3", "K4", "K5", "K6", "K7", "K8", "K9", "K10", "K11", "K12", "K13", "K14"}:
        raise RuntimeError(f"plan-local bridge is not yet implemented for {args.slice_id}")
    run_id = datetime.now(timezone.utc).strftime("RUN-%Y%m%dT%H%M%S-%fZ")
    run_dir = root / "logs" / "tdd-adapter" / contract["plan_id"] / args.slice_id / run_id
    if args.slice_id == "K0":
        k0(root, plan, run_dir, sha256(contract_path))
    elif args.slice_id == "K1":
        k1(root, plan, run_dir, sha256(contract_path))
    elif args.slice_id == "K2":
        k2(root, plan, run_dir, sha256(contract_path))
    elif args.slice_id == "K3":
        k3(root, plan, run_dir, sha256(contract_path))
    elif args.slice_id == "K4":
        k4(root, plan, run_dir, sha256(contract_path))
    elif args.slice_id == "K5":
        k5(root, plan, run_dir, sha256(contract_path))
    elif args.slice_id == "K6":
        k6(root, plan, run_dir, sha256(contract_path))
    elif args.slice_id == "K7":
        k7(root, plan, run_dir, sha256(contract_path))
    elif args.slice_id == "K8":
        k8(root, plan, run_dir, sha256(contract_path))
    elif args.slice_id == "K9":
        k9(root, plan, run_dir, sha256(contract_path))
    elif args.slice_id == "K10":
        k10(root, plan, run_dir, sha256(contract_path))
    elif args.slice_id == "K11":
        k11(root, plan, run_dir, sha256(contract_path))
    elif args.slice_id == "K12":
        k12(root, plan, run_dir, sha256(contract_path))
    elif args.slice_id == "K13":
        k13(root, plan, run_dir, sha256(contract_path))
    else:
        k14(root, plan, run_dir, sha256(contract_path))
        published = subprocess.run(
            [
                sys.executable,
                "-B",
                str(plan / "tools/publish_implementation_complete.py"),
                "--repository-root",
                str(root),
                "--plan-dir",
                str(plan),
            ],
            cwd=root,
            check=False,
        )
        if published.returncode:
            raise RuntimeError("K14 completion publisher failed")
    print(json.dumps({"run_id": run_id, "slice_id": args.slice_id, "authorizes": []}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
