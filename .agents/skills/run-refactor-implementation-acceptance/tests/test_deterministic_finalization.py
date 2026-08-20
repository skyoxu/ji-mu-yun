from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))


def _sha(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def test_deterministic_finalization_requires_and_publishes_hash_bound_receipts(tmp_path: Path) -> None:
    import acceptance_core
    import deterministic_finalization
    import execution_control

    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "--quiet"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    tracked = root / "tracked.txt"
    tracked.write_text("before\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "--quiet", "-m", "baseline"], cwd=root, check=True)
    baseline_revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    tracked.write_text("after\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "--quiet", "-m", "candidate"], cwd=root, check=True)
    candidate_revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()

    target = root / "execution-plans" / "target"
    target.mkdir(parents=True)
    (target / "inputs").mkdir()
    baseline_hash = _sha(b"before\n")
    candidate_hash = _sha(b"after\n")
    baseline = {
        "schemaVersion": "acceptance-baseline-content-manifest.v1", "status": "complete",
        "coverageGaps": [], "authorizes": [],
        "files": [{"path": "tracked.txt", "roles": ["implementation"], "sha256": baseline_hash, "inclusion_reason": "test"}],
    }
    candidate = {
        "schemaVersion": "acceptance-candidate-content-manifest.v1", "status": "complete",
        "coverageGaps": [], "authorizes": [],
        "files": [{"change_type": "modified", "roles": ["implementation"], "baseline_path": "tracked.txt", "baseline_sha256": baseline_hash, "candidate_path": "tracked.txt", "candidate_sha256": candidate_hash, "inclusion_reason": "test"}],
    }
    (target / "inputs/baseline.json").write_text(json.dumps(baseline), encoding="utf-8")
    (target / "inputs/candidate.json").write_text(json.dumps(candidate), encoding="utf-8")
    policy = target / "inputs/policy.json"
    policy.write_text("{}\n", encoding="utf-8")
    run_input = {
        "run_id": "acceptance-test", "created_utc": "2026-08-17T00:00:00Z", "change_id": "test",
        "target": str(target), "target_plan_paths": ["inputs/candidate.json"],
        "baseline_revision": baseline_revision, "candidate_revision": candidate_revision, "candidate_mode": "commit",
        "execution_mode": "evidence_only", "baseline_content_manifest_path": "inputs/baseline.json",
        "baseline_content_manifest_hash": acceptance_core.canonical_hash(baseline), "candidate_content_manifest_path": "inputs/candidate.json",
        "candidate_content_manifest_hash": acceptance_core.canonical_hash(candidate), "code_review_domain": "toolchain",
        "code_review_policy_path": "inputs/policy.json", "code_review_policy_hash": _sha(policy.read_bytes()),
        "target_plan_hash": _sha((target / "inputs/candidate.json").read_bytes()), "validator_hash": _sha(b"validator"),
        "adapter_id": "test", "adapter_version": "v1", "adapter_hash": _sha(b"adapter"),
        "allowed_write_roots": [], "forbidden_write_roots": [], "changed_paths": ["tracked.txt"], "affected_consumer_refs": ["consumer.py"],
    }
    registry = {"schema_version": "ria.command-registry.v1", "commands": [{
        "id": "terminal-full", "executable": sys.executable,
        "argv": ["-c", "import json; print(json.dumps({'schema_version':'quick-dev-implementation-complete.v1','predicate':'implementation-complete','status':'pass','authorizes':['implementation-complete']}))"],
        "cwd": ".", "timeout_seconds": 30, "shell": False,
    }]}
    contract = target / "implementation-contract.v1.json"
    contract.write_text("{}\n", encoding="utf-8")
    registry_path = target / "command-registry.v1.json"
    registry_path.write_text(json.dumps(registry), encoding="utf-8")
    terminal_runner = target / "tools/terminal_full.py"
    terminal_runner.parent.mkdir()
    terminal_runner.write_text("# terminal runner\n", encoding="utf-8")
    implementation_receipt = {
        "schema_version": "quick-dev-implementation-complete.v1", "predicate": "implementation-complete",
        "status": "pass", "authorizes": ["implementation-complete"],
        "contract_hash": _sha(contract.read_bytes()), "command_registry_hash": acceptance_core.canonical_hash(registry),
        "terminal_command_id": "terminal-full",
    }
    implementation_receipt_path = target / "quick-dev-implementation-complete.v1.json"
    implementation_receipt_path.write_text(json.dumps(implementation_receipt), encoding="utf-8")
    bundle = {
        "schemaVersion": "compact-vdd-acceptance-prerequisite-bundle.v1",
        "implementationReceipt": {"path": "execution-plans/target/quick-dev-implementation-complete.v1.json", "sha256": _sha(implementation_receipt_path.read_bytes()), "terminalCommandId": "terminal-full"},
        "terminalRunner": {"path": "tools/terminal_full.py", "sha256": _sha(terminal_runner.read_bytes())},
    }
    bundle["bundleHash"] = acceptance_core.canonical_hash(bundle)
    bundle_path = target / "inputs/bundle.json"
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
    prepared = {
        "schemaVersion": "acceptance-run-input.v1", "input": run_input,
        "inputHash": acceptance_core.canonical_hash(run_input),
        "candidateCustody": acceptance_core.verify_manifest_bytes(target, run_input, baseline, candidate),
        "prerequisiteBundle": {"path": "inputs/bundle.json", "sha256": _sha(bundle_path.read_bytes()), "bundleHash": bundle["bundleHash"], "implementationReceipt": bundle["implementationReceipt"]},
        "authorizes": [],
    }
    prepared_path = target / "prepared.json"
    prepared_path.write_text(json.dumps(prepared), encoding="utf-8")
    actions = [{"actionId": "terminal-full", "dependsOn": [], "order": 1, "commandId": "terminal-full", "activation": True}]
    runs_root = target / "runs"
    runs_root.mkdir()
    run = execution_control.create_persisted_run(runs_root, "acceptance-test", prepared["inputHash"], "sha256:" + "a" * 64)
    execution_control.resume_persisted_run(root, run, actions, registry, prepared["inputHash"], "sha256:" + "a" * 64)
    result = deterministic_finalization.finalize_deterministic_run(root, run, prepared_path, actions, registry)
    assert result["status"] == "acceptance-passed"
    assert deterministic_finalization.finalize_deterministic_run(root, run, prepared_path, actions, registry) == result
    assert json.loads((run / "finalization/acceptance-passed.v1.json").read_text(encoding="utf-8"))["authorizes"] == ["acceptance-passed"]
    assert json.loads((run / "finalization/acceptance-result-final.v1.json").read_text(encoding="utf-8"))["authorizes"] == []
    assert json.loads((run / "finalization/acceptance-result-final.v1.json").read_text(encoding="utf-8"))["candidatePath"] == "finalization/acceptance-result-candidate.v1.json"


def test_terminal_machine_result_accepts_json_before_non_json_tail() -> None:
    import deterministic_finalization

    result = deterministic_finalization._terminal_machine_result(
        "pytest output\n"
        "{\"schema_version\": \"quick-dev-implementation-complete.v1\", \"predicate\": \"implementation-complete\", \"status\": \"pass\", \"authorizes\": [\"implementation-complete\"]}\n"
        "trailing diagnostic\n"
    )

    assert result["status"] == "pass"


def test_terminal_machine_result_skips_unrelated_json_after_completion() -> None:
    import deterministic_finalization

    result = deterministic_finalization._terminal_machine_result(
        "{\"schema_version\": \"quick-dev-implementation-complete.v1\", \"predicate\": \"implementation-complete\", \"status\": \"pass\", \"authorizes\": [\"implementation-complete\"]}\n"
        "{\"status\": \"source_frozen\"}\n"
    )

    assert result["predicate"] == "implementation-complete"


def test_terminal_machine_result_rejects_authority_free_text_marker() -> None:
    import deterministic_finalization

    with pytest.raises(Exception, match="machine-readable result"):
        deterministic_finalization._terminal_machine_result(
            "validator output\nterminal-validation=implementation-complete authorizes=[]\n"
        )
