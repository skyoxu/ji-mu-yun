#!/usr/bin/env python3
"""Build the deterministic plan-local Context Envelope JCS/HMAC reference vector."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path

from context_crypto import canonicalize_jcs, hmac_sha256_base64, sha256_hex


PLAN_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PLAN_DIR / "fixtures/reference-vectors/jcs-hmac-reference-vector.v1.json"
TEST_KEY = b"jimuyun-plan-local-synthetic-hmac-key-v1"


def synthetic_hash(label: str) -> str:
    return hashlib.sha256(label.encode("ascii")).hexdigest()


def build_signed_payload() -> dict[str, object]:
    operation = "classify-\u77e5\u8bc6-GameDesignRequirementMap"
    prompt_hash = synthetic_hash("execution-prompt")
    project_snapshot_id = synthetic_hash("project-snapshot")
    allowed_read_artifacts = [
        {"artifact_ref": "prompt://execution", "sha256": prompt_hash},
        {"artifact_ref": "phase://projects/project-synthetic-a/snapshot", "sha256": project_snapshot_id},
    ]
    allowed_read_hash = sha256_hex(canonicalize_jcs(allowed_read_artifacts))
    context_assembly = {
        "execution_prompt_sha256": prompt_hash,
        "input_manifest_sha256": allowed_read_hash,
        "project_snapshot_id": project_snapshot_id,
    }
    return {
        "schema_version": "jimuyun.hosted-context-manifest.v1",
        "manifest_id": "manifest-synthetic-0001",
        "identity_mode": "project-bound",
        "service_principal_id": None,
        "primary_domain": "workspace",
        "allowed_dependency_domains": ["phase", "toolchain"],
        "visibility": {
            "toolchain": "dependency",
            "phase": "dependency",
            "workspace": "active",
            "marketplace": "excluded",
        },
        "visibility_policy_revision": "hosted-context-visibility.v1",
        "lifecycle": "run-artifact-view",
        "enforcement_level": "E2",
        "gate_mode": "enforce",
        "route_id": operation,
        "skill_id": None,
        "operation": operation,
        "account_id": "account-synthetic-a",
        "project_id": "project-synthetic-a",
        "workspace_id": "workspace-synthetic-a",
        "workspace_generation": "generation-synthetic-1",
        "run_id": "run-synthetic-1",
        "attempt_id": "attempt-synthetic-1",
        "dispatch_id": "dispatch-synthetic-1",
        "global_policy_revision": "hosted-context-global.v1",
        "route_policy_revision": "route-policy.synthetic.v1",
        "skill_policy_revision": None,
        "account_policy_revision": None,
        "project_restrictions_sha256": synthetic_hash("project-restrictions"),
        "scope_profile_revision": "hosted-context-project-scope.v1",
        "effective_capabilities": ["read_project", "write_project_output"],
        "repository_snapshot_id": synthetic_hash("repository-snapshot"),
        "template_snapshot_id": synthetic_hash("template-snapshot"),
        "project_snapshot_id": project_snapshot_id,
        "allowed_read_artifact_manifest_ref": "signed-payload://allowed_read_artifacts",
        "allowed_read_artifact_manifest_sha256": allowed_read_hash,
        "allowed_read_artifacts": allowed_read_artifacts,
        "allowed_write_paths": ["project://output/generated.json"],
        "output_targets": ["project://output/generated.json"],
        "context_assembly_result_ref": "signed-payload://context_assembly",
        "context_assembly_result_sha256": sha256_hex(canonicalize_jcs(context_assembly)),
        "context_assembly": context_assembly,
        "context_budget_profile_revision": "hosted-context-budget.default.v1",
        "sandbox_policy": {
            "revision": "hosted-context-sandbox.v1",
            "mode": "workspace-write",
        },
        "network_policy": {
            "revision": "hosted-context-network.provider-only.v1",
            "mode": "provider-only",
            "allowlist_sha256": None,
        },
        "tool_execution_policy": {
            "revision": "hosted-context-tools.v1",
            "allowed_tools": [],
            "command_policy_sha256": synthetic_hash("command-policy"),
        },
        "hosted_route_contracts": {
            "mode": "not_applicable",
            "applicability_policy_revision": "hosted-route-applicability.v1",
            "reason_code": "no_pre_dispatch_hosted_route_aggregate",
        },
        "execution_prompt_hash": prompt_hash,
        "persisted_prompt_hash": synthetic_hash("persisted-redacted-prompt"),
        "issued_at_utc": "2026-07-25T00:00:00Z",
        "not_before_utc": "2026-07-25T00:00:00Z",
        "expires_at_utc": "2026-07-25T00:05:00Z",
        "nonce": "nonce-synthetic-0001",
        "max_uses": 1,
    }


def build_vector() -> dict[str, object]:
    payload = build_signed_payload()
    canonical = canonicalize_jcs(payload)
    payload_sha256 = sha256_hex(canonical)
    signature = hmac_sha256_base64(TEST_KEY, canonical)
    manifest = {
        "signed_payload": payload,
        "signature": {
            "algorithm": "HMAC-SHA-256",
            "canonicalization": "RFC8785-JCS",
            "canonicalization_revision": "jimuyun-jcs.v1",
            "key_id": "synthetic-test-key-v1",
            "signed_payload_sha256": payload_sha256,
            "hmac_base64": signature,
        },
        "validation_state": {
            "revocation_status": "active",
            "nonce_status": "unused",
            "validated_at_utc": "2026-07-25T00:00:01Z",
            "gate_result_id": "gate-result-synthetic-1",
        },
    }
    return {
        "schema_version": "jimuyun.context-envelope-reference-vector.v1",
        "test_key_base64": base64.b64encode(TEST_KEY).decode("ascii"),
        "manifest": manifest,
        "expected_signed_payload_canonical_utf8_base64": base64.b64encode(canonical).decode("ascii"),
        "expected_signed_payload_sha256": payload_sha256,
        "expected_hmac_base64": signature,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    vector = build_vector()
    rendered = json.dumps(
        vector,
        ensure_ascii=True,
        sort_keys=True,
        indent=2,
        allow_nan=False,
    ) + "\n"
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8", newline="\n")
    print(
        "REFERENCE_VECTOR_BUILD PASS "
        f"payload_sha256={vector['expected_signed_payload_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
