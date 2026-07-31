from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("bootstrap_review", ROOT / "scripts" / "bootstrap_review.py")
assert SPEC and SPEC.loader
bootstrap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bootstrap)


class BootstrapCompanionCapabilityTests(unittest.TestCase):
    def _bundle_inputs(self) -> tuple[dict, dict, dict]:
        reviewer = {"schemaVersion": "bootstrap-reviewer-output.v1", "reviewId": "review", "reviewerLayer": "acceptance_auditor", "routeVersion": "route", "authorityRevision": "authority", "inputHash": "sha256:" + "a" * 64, "attemptId": "attempt", "status": "completed", "coverage": {"requiredArtifacts": [], "readArtifacts": [], "missingArtifacts": []}, "candidates": []}
        attestation = {"schemaVersion": "bootstrap-acceptance-inventory-attestation.v1", "reviewId": "review", "attemptId": "attempt", "inputHash": "sha256:" + "a" * 64, "capabilityId": "acceptance-inventory-attestation", "capabilityVersion": "1.0", "producerRole": "acceptance_auditor", "status": "complete", "scopeHash": "sha256:" + "b" * 64, "coverage": []}
        manifest = {"profileName": "bootstrap-implementation-conformance", "reviewId": "review", "inputHash": "sha256:" + "a" * 64, "artifactView": {"manifestHash": "sha256:" + "b" * 64}}
        return reviewer, attestation, manifest

    def test_implementation_conformance_declares_hash_bound_inventory_attestation(self) -> None:
        profile = bootstrap.load_profile("bootstrap-implementation-conformance")
        capability = bootstrap.required_companion_capability(
            profile, "acceptance-inventory-attestation", "1.0", "acceptance_auditor"
        )
        self.assertEqual(
            ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-acceptance-inventory-attestation.v1.schema.json",
            capability["schemaPath"],
        )
        self.assertTrue(capability["schemaHash"].startswith("sha256:"))

    def test_acceptance_auditor_role_bundle_requires_same_attempt_and_input(self) -> None:
        reviewer, attestation, manifest = self._bundle_inputs()
        bundle = bootstrap.build_acceptance_auditor_role_bundle(reviewer, attestation, "attempt", manifest)
        self.assertEqual("attempt", bundle["attemptId"])
        self.assertEqual([], bundle["authorizes"])

    def test_role_bundle_rejects_cross_attempt(self) -> None:
        reviewer, attestation, manifest = self._bundle_inputs()
        with self.assertRaisesRegex(bootstrap.BootstrapError, "attempt identity"):
            bootstrap.build_acceptance_auditor_role_bundle(reviewer, attestation, "different-attempt", manifest)

    def test_role_bundle_rejects_reviewer_from_a_different_attempt(self) -> None:
        reviewer, attestation, manifest = self._bundle_inputs()
        reviewer["attemptId"] = "different-attempt"
        with self.assertRaisesRegex(bootstrap.BootstrapError, "attempt identity"):
            bootstrap.build_acceptance_auditor_role_bundle(reviewer, attestation, "attempt", manifest)

    def test_role_bundle_rejects_stale_artifact_view_scope(self) -> None:
        reviewer, attestation, manifest = self._bundle_inputs()
        manifest["artifactView"]["manifestHash"] = "sha256:" + "c" * 64
        with self.assertRaisesRegex(bootstrap.BootstrapError, "scope is stale"):
            bootstrap.build_acceptance_auditor_role_bundle(reviewer, attestation, "attempt", manifest)


if __name__ == "__main__":
    unittest.main()
