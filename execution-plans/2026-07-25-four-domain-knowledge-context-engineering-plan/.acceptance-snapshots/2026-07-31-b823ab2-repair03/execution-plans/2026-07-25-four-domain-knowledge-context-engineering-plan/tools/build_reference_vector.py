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
        "visibility_policy_revision": "visibility-policy.synthetic.v1",
        "lifecycle": "run-artifact-view",
        "enforcement_level": "E2",
        "gate_mode": "enforce",
        "route_id": "phase.synthetic.knowledge-context",
        "skill_id": None,
        "operation": "classify-\u77e5\u8bc6-GameDesignRequirementMap",
        "account_id": "account-synthetic-a",
        "project_id": "project-synthetic-a",
        "workspace_id": "workspace-synthetic-a",
        "workspace_generation": "generation-synthetic-1",
        "run_id": "run-synthetic-1",
        "attempt_id": "attempt-synthetic-1",
        "dispatch_id": "dispatch-synthetic-1",
        "global_policy_revision": "global-policy.synthetic.v1",
        "route_policy_revision": "route-policy.synthetic.v1",
        "skill_policy_revision": None,
        "account_policy_revision": "account-policy.synthetic.v1",
        "project_restrictions_sha256": synthetic_hash("project-restrictions"),
        "scope_profile_revision": "scope-profile.synthetic.v1",
        "effective_capabilities": ["read_project", "write_project_output"],
        "repository_snapshot_id": synthetic_hash("repository-snapshot"),
        "template_snapshot_id": synthetic_hash("template-snapshot"),
        "project_snapshot_id": synthetic_hash("project-snapshot"),
        "allowed_read_artifact_manifest_ref": "artifact://synthetic/allowed-read/1",
        "allowed_read_artifact_manifest_sha256": synthetic_hash("allowed-read-manifest"),
        "allowed_write_paths": ["project://output/generated.json"],
        "output_targets": ["artifact://synthetic/output/1"],
        "context_assembly_result_ref": "artifact://synthetic/context-assembly/1",
        "context_assembly_result_sha256": synthetic_hash("context-assembly"),
        "context_budget_profile_revision": "context-budget.synthetic.v1",
        "sandbox_policy": {
            "revision": "sandbox.synthetic.v1",
            "mode": "workspace-write",
        },
        "network_policy": {
            "revision": "network.synthetic.v1",
            "mode": "provider-only",
            "allowlist_sha256": synthetic_hash("provider-allowlist"),
        },
        "tool_execution_policy": {
            "revision": "tools.synthetic.v1",
            "allowed_tools": [],
            "command_policy_sha256": synthetic_hash("command-policy"),
        },
        "hosted_route_contracts": {
            "aggregate_ref": "artifact://synthetic/hosted-contracts/1",
            "aggregate_sha256": synthetic_hash("hosted-contracts"),
            "recovery_order": {
                "contract_id": "hosted-route-recovery-order.v1",
                "evidence_ref": "artifact://synthetic/recovery-order/1",
                "evidence_sha256": synthetic_hash("recovery-order"),
            },
            "forbidden_source_scan": {
                "contract_id": "hosted-route-forbidden-source-scan.v1",
                "evidence_ref": "artifact://synthetic/forbidden-source-scan/1",
                "evidence_sha256": synthetic_hash("forbidden-source-scan"),
                "status": "clean",
            },
            "database_binding": {
                "binding_id": "binding-synthetic-1",
                "binding_sha256": synthetic_hash("database-binding"),
            },
            "succeeded_run_binding": {
                "run_id": "run-synthetic-1",
                "binding_sha256": synthetic_hash("succeeded-run-binding"),
            },
            "live_acceptance": {
                "blocker_ref": "artifact://synthetic/live-blocker/none",
                "blocker_sha256": synthetic_hash("live-blocker-none"),
                "observed_at_utc": "2026-07-25T00:00:00Z",
            },
            "source_boundary_disposition": {
                "mode": "required",
                "evidence_ref": "artifact://synthetic/source-boundary/1",
                "evidence_sha256": synthetic_hash("source-boundary"),
            },
        },
        "execution_prompt_hash": synthetic_hash("execution-prompt"),
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
