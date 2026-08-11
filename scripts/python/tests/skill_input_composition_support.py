from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

PYTHON_ROOT = Path(__file__).resolve().parents[1]
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from launch_skill_input_consumer import create_child_request, run_semantic_child
from prepare_skill_input_consumption import prepare
from skill_input_consumption import canonical_hash, redaction_profile_hash, sha256_bytes, write_json_atomic
from validate_skill_input_consumption import publish_ready


def _backend_inspector(backend: str) -> dict[str, Any]:
    return {
        "backend": backend,
        "available": True,
        "executable": "missing-test-codex",
        "executable_sha256": "sha256:" + "e" * 64,
    }


def _ensure_git_repository(root: Path) -> None:
    if not (root / ".git").is_dir():
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "test"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "--allow-empty", "-qm", "skill input composition fixture"], cwd=root, check=True)


def publish_ready_receipt(
    repository_root: Path,
    *,
    consumer: str,
    operation: str,
    target: str,
    role_paths: dict[str, list[str]],
    protocol_name: str = ".skill-input-composition",
) -> dict[str, Path]:
    """Run the real producer, typed child boundary, publication, and ready gate inputs."""
    root = repository_root.resolve()
    protocol_root = root / protocol_name
    protocol_root.mkdir(parents=True, exist_ok=True)
    basis = protocol_root / "budget-basis.json"
    write_json_atomic(basis, {
        "schema_version": "skill-input-budget.v1",
        "max_reference_depth": 4,
        "max_sources": 128,
        "max_context_bytes": 6000,
        "max_snapshot_bytes": 262144,
    })
    source_roles: dict[str, Any] = {}
    for role, paths in role_paths.items():
        allowed_kinds = sorted({"directory" if (root / path).is_dir() else "file" for path in paths})
        source_roles[role] = {
            "selector": role,
            "required": True,
            "root": "repository",
            "allowed_kinds": allowed_kinds,
            "reference_kinds": [],
        }
    contract = {
        "schema_version": "skill-input-contract.v1",
        "consumer": consumer,
        "mode": "strict",
        "trigger": "composition-test",
        "source_roles": source_roles,
        "operations": {operation: {"required_inputs": list(role_paths)}},
        "reference_policy": "declared-in-root-and-contained",
        "max_reference_depth": 4,
        "max_sources": 128,
        "max_context_bytes": 6000,
        "max_snapshot_bytes": 262144,
        "budget_basis": {
            "path": basis.relative_to(root).as_posix(),
            "sha256": sha256_bytes(basis.read_bytes()),
        },
        "sensitivity_policy": "deny-credential-values",
        "redaction_profile": "credential-values-v1",
        "forbidden_sources": ["logs-as-recovery-source"],
        "semantic_acceptance": "all-required-inputs-are-sufficient",
    }
    contract_path = protocol_root / "skill-input-contract.v1.json"
    write_json_atomic(contract_path, contract)
    _ensure_git_repository(root)

    receipt_path = protocol_root / "receipt.json"
    snapshot_root = protocol_root / "snapshot"
    prepare(argparse.Namespace(
        repository_root=root,
        contract=contract_path,
        consumer=consumer,
        operation=operation,
        route_identity="composition-test",
        target=target,
        source_role=[f"{role}={path}" for role, paths in role_paths.items() for path in paths],
        request_json=None,
        snapshot_root=snapshot_root,
        receipt=receipt_path,
    ))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    request = create_child_request(
        receipt,
        contract,
        root,
        contract_path=contract_path,
        receipt_root=protocol_root,
        output_root=f"{protocol_name}/output",
        backend="codex-cli",
        model="composition-model",
        backend_inspector=_backend_inspector,
    )
    request_path = protocol_root / "skill-input-child-request.v1.json"
    write_json_atomic(request_path, request)

    def fake_runner(**kwargs):
        prompt = kwargs["prompt"]
        serialized_text = prompt.split("SNAPSHOT_JSON_BEGIN\n", 1)[1].split(
            "\nSNAPSHOT_JSON_END", 1
        )[0]
        serialized = json.loads(serialized_text)
        manifest_sources = {
            source["path"]: source["semantic_snapshot_sha256"]
            for source in serialized["manifest"]["sources"]
        }
        transferred_sources = {source["path"]: source for source in serialized["sources"]}
        if manifest_sources != {
            path: source["sha256"] for path, source in transferred_sources.items()
        }:
            raise AssertionError("serialized snapshot does not cover the manifest")
        if set(manifest_sources) != {source["path"] for source in receipt["sources"]}:
            raise AssertionError("serialized snapshot does not cover every receipt source")
        for path, source in transferred_sources.items():
            if sha256_bytes(source["content"].encode("utf-8")) != manifest_sources[path]:
                raise AssertionError("serialized source content is hash-mismatched")
        output = {
            "context": {
                "schema_version": "skill-input-context.v1",
                "source_manifest_hash": receipt["source_manifest"]["sha256"],
                "sections": [{"title": "consumed-input", "content": "All declared inputs were consumed."}],
                "truncated": False,
                "omitted_items": 0,
                "generated_at": "2026-08-11T00:00:00Z",
            },
            "decision": {
                "schema_version": "skill-semantic-decision.v1",
                "producer_role": "semantic-child",
                "execution_identity": request["execution_identity"],
                "source_manifest_hash": receipt["source_manifest"]["sha256"],
                "context_artifact_hash": "sha256:" + "0" * 64,
                "source_statuses": {path: "accepted" for path in sorted(transferred_sources)},
                "status": "accepted",
                "rationale": "All declared sources are sufficient.",
                "redaction_status": "complete",
                "redaction_profile_hash": redaction_profile_hash(),
                "authorizes": [],
            },
        }
        kwargs["output_last_message"].write_text(json.dumps(output), encoding="utf-8")
        return 0, "", ["fake"]

    child_result = run_semantic_child(
        request,
        root,
        backend="codex-cli",
        model="composition-model",
        runner=fake_runner,
        backend_inspector=_backend_inspector,
    )
    context_path = Path(child_result["context_artifact"])
    decision_path = Path(child_result["semantic_decision"])
    publish_ready(receipt_path, request_path, decision_path, context_path, root, contract_path)
    candidate = json.loads(receipt_path.read_text(encoding="utf-8"))
    candidate["ready"] = False
    candidate["binding_hash"] = canonical_hash({
        key: value for key, value in candidate.items() if key != "binding_hash"
    })
    candidate_path = protocol_root / "candidate-receipt.json"
    write_json_atomic(candidate_path, candidate)
    return {
        "receipt": receipt_path,
        "candidate_receipt": candidate_path,
        "contract": contract_path,
        "context": context_path,
    }
