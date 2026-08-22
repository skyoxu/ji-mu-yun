from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

import knowledge_context_validation as validation
from knowledge_context_validation import _main_source_hashes, canonical_hash, validate_context


def payload(*, path: str = "AGENTS.md", digest: str = "a" * 64) -> dict:
    request = {
        "schema_version": "jimuyun.knowledge-locator-request.v1",
        "request_id": "context-validation-1",
        "snapshot": {"ref": "refs/heads/main", "commit": "a" * 40},
    }
    result = {
        "schema_version": "jimuyun.knowledge-locator-result.v1",
        "request_id": "context-validation-1",
        "snapshot": request["snapshot"],
        "status": "matched",
        "candidates": [{"path": path, "source_sha256": digest}],
    }
    return {
        "schema_version": "jimuyun.vdd-knowledge-context.v1",
        "locator_request": request,
        "locator_result": result,
        "required_modules": ["repository-rules"],
        "decisions": [{
            "owner": "adapter",
            "decision": "accepted", "satisfies": ["repository-rules"],
            "candidate": {"path": path, "source_sha256": digest},
            "rejection_reason": None,
        }],
        "request_sha256": canonical_hash(request),
        "result_sha256": canonical_hash(result),
    }


class KnowledgeContextValidationTests(unittest.TestCase):
    def test_stale_catalog_source_refresh_rebinds_current_bytes_without_snapshot_match(self) -> None:
        payload = validation.refresh_context_read_set
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "knowledge/catalogs").mkdir(parents=True)
            (root / "knowledge/policies").mkdir(parents=True)
            (root / "AGENTS.md").write_text("current\n", encoding="utf-8")
            catalog = {"schema_version": "jimuyun.repository-knowledge-catalog.v2", "source_snapshot": {"ref": "refs/heads/main", "commit": "new", "snapshot_id": "new"}}
            (root / "knowledge/catalogs/repository-knowledge-catalog.v2.json").write_text(json.dumps(catalog), encoding="utf-8")
            (root / "knowledge/policies/consumer-policies.v2.json").write_text(json.dumps({"policy_revision": "policy"}), encoding="utf-8")
            original = {"schema_version": "jimuyun.vdd-knowledge-context.v1", "locator_request": {"schema_version": "jimuyun.knowledge-locator-request.v1", "request_id": "r", "consumer": "vdd", "snapshot": {"ref": "refs/heads/main", "commit": "old"}, "policy_revision": "policy", "allow_stale_catalog": True}, "locator_result": {"schema_version": "jimuyun.knowledge-locator-result.v1", "request_id": "r", "snapshot": {"ref": "refs/heads/main", "commit": "old"}, "status": "matched", "source_snapshot_id": "old", "policy_revision": "policy", "candidates": [{"path": "AGENTS.md", "source_sha256": "0" * 64, "read_set": [{"path": "AGENTS.md", "source_sha256": "0" * 64}]}]}, "required_modules": ["rules"], "decisions": [{"owner": "adapter", "decision": "accepted", "satisfies": ["rules"], "candidate": {"path": "AGENTS.md", "source_sha256": "0" * 64}}]}
            original["locator_result"]["candidates"].append({"path": "retired.md", "source_sha256": "1" * 64})
            original["decisions"].append({"owner": "adapter", "decision": "rejected", "satisfies": [], "rejection_reason": "insufficient_specificity", "candidate": {"path": "retired.md", "source_sha256": "1" * 64}})
            original["request_sha256"] = canonical_hash(original["locator_request"])
            original["result_sha256"] = canonical_hash(original["locator_result"])
            original["preflight"] = {"status": "ready", "failure_code": None, "knowledge_freshness": "degraded", "catalog_failure_code": "catalog_stale", "source_freshness": "refreshed", "context_sha256": canonical_hash({key: value for key, value in original.items() if key != "preflight"})}
            refreshed = payload(original, root)
            self.assertEqual(canonical_hash({key: value for key, value in refreshed.items() if key != "preflight"}), refreshed["preflight"]["context_sha256"])
            with mock.patch.object(validation, "validate_catalog_freshness", return_value="catalog_stale"):
                self.assertIsNone(validate_context(refreshed, repository_root=root, verify_catalog=True, verify_sources=True, expected_consumer="vdd", require_preflight=True))
    def test_refresh_ignores_rejected_missing_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            accepted = root / "accepted.md"
            accepted.write_text("current\n", encoding="utf-8")
            payload = {
                "schema_version": "jimuyun.vdd-knowledge-context.v1",
                "locator_request": {"schema_version": "jimuyun.knowledge-locator-request.v1", "request_id": "r", "consumer": "vdd"},
                "locator_result": {"schema_version": "jimuyun.knowledge-locator-result.v1", "request_id": "r", "status": "matched", "candidates": [
                    {"path": "accepted.md", "source_sha256": "0" * 64, "read_set": [{"path": "accepted.md", "source_sha256": "0" * 64}]},
                    {"path": "deleted-history.md", "source_sha256": "1" * 64},
                ]},
                "required_modules": ["rules"],
                "decisions": [
                    {"owner": "adapter", "decision": "accepted", "satisfies": ["rules"], "candidate": {"path": "accepted.md", "source_sha256": "0" * 64}},
                    {"owner": "adapter", "decision": "rejected", "satisfies": [], "rejection_reason": "insufficient_specificity", "candidate": {"path": "deleted-history.md", "source_sha256": "1" * 64}},
                ],
            }
            payload["request_sha256"] = canonical_hash(payload["locator_request"])
            payload["result_sha256"] = canonical_hash(payload["locator_result"])
            refreshed = validation.refresh_context_read_set(payload, root)
            self.assertEqual(hashlib.sha256(accepted.read_bytes()).hexdigest(), refreshed["decisions"][0]["candidate"]["source_sha256"])
            self.assertEqual("deleted-history.md", refreshed["decisions"][1]["candidate"]["path"])
    def test_stale_catalog_flag_cannot_bypass_validator_implementation_freshness(self) -> None:
        prepare = Path(__file__).resolve().parents[3] / ".agents/skills/vdd-execution-plan/scripts/prepare_knowledge_context.py"
        source = prepare.read_text(encoding="utf-8")
        freshness_block = source[source.index("def _validator"):source.index("def main")]
        self.assertIn("knowledge context validator must match current main", freshness_block)
        self.assertNotIn("and not allow_stale_catalog", freshness_block)

    def test_catalog_stale_precedes_blocked_locator_result(self) -> None:
        document = payload()
        document["locator_result"].update({"status": "blocked", "candidates": []})
        document["decisions"] = []
        document["result_sha256"] = canonical_hash(document["locator_result"])
        with mock.patch.object(validation, "validate_catalog_freshness", return_value="catalog_stale"):
            self.assertEqual(
                "catalog_stale",
                validate_context(document, repository_root=Path.cwd(), verify_catalog=True),
            )

    def test_vdd_explicit_stale_catalog_opt_in_is_non_blocking(self) -> None:
        self.assertIsNone(
            validation.catalog_freshness_failure("catalog_stale", {"allow_stale_catalog": True})
        )

    def test_stale_catalog_opt_in_does_not_bypass_invalid_publication(self) -> None:
        self.assertEqual(
            "catalog_publication_invalid",
            validation.catalog_freshness_failure(
                "catalog_publication_invalid", {"allow_stale_catalog": True}
            ),
        )

    def test_catalog_validation_fails_closed_when_publication_pointer_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / validation.CATALOG_RELATIVE
            catalog.parent.mkdir(parents=True)
            catalog.write_text(json.dumps({"source_snapshot": {"sources": []}}), encoding="utf-8")
            with mock.patch.object(validation, "verify_current_publication", return_value=False):
                self.assertEqual("catalog_publication_invalid", validation.validate_catalog_freshness(root))

    def test_generic_context_binds_the_declared_consumer(self) -> None:
        document = payload()
        document["schema_version"] = "jimuyun.knowledge-consumer-context.v1"
        document["consumer"] = "refactor-acceptance"
        document["locator_request"]["consumer"] = "vdd"
        document["request_sha256"] = canonical_hash(document["locator_request"])
        self.assertEqual("knowledge_consumer_mismatch", validate_context(document))

    def test_catalog_source_snapshot_may_be_an_ancestor_when_registered_sources_are_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "--quiet"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "knowledge@example.invalid"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Knowledge Test"], cwd=root, check=True)
            source = root / "AGENTS.md"
            source.write_text("rules\n", encoding="utf-8")
            subprocess.run(["git", "add", "AGENTS.md"], cwd=root, check=True)
            subprocess.run(["git", "commit", "--quiet", "-m", "source"], cwd=root, check=True)
            source_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True, encoding="utf-8").strip()
            (root / "derived.json").write_text(json.dumps({"generated": True}), encoding="utf-8")
            subprocess.run(["git", "add", "derived.json"], cwd=root, check=True)
            subprocess.run(["git", "commit", "--quiet", "-m", "derived"], cwd=root, check=True)
            subprocess.run(["git", "branch", "-M", "main"], cwd=root, check=True)
            catalog = {
                "source_snapshot": {
                    "commit": source_commit,
                    "sources": [{"path": "AGENTS.md", "sha256": "unused"}],
                }
            }
            hashes = _main_source_hashes(root, catalog)
            self.assertIn("AGENTS.md", hashes)

    def test_rejects_non_string_catalog_snapshot_commit(self) -> None:
        with self.assertRaisesRegex(ValueError, "catalog_source_snapshot_invalid"):
            _main_source_hashes(Path.cwd(), {"source_snapshot": {"commit": None, "sources": []}})

    def test_requires_read_set_when_catalog_entry_has_resources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog_path = root / validation.CATALOG_RELATIVE
            catalog_path.parent.mkdir(parents=True)
            digest = "a" * 64
            catalog_path.write_text(json.dumps({
                "source_snapshot": {"ref": "refs/heads/main", "commit": "a" * 40},
                "modules": [{
                    "source_path": "AGENTS.md",
                    "source_sha256": digest,
                    "resources": [{"path": "README.md", "source_sha256": "b" * 64}],
                }],
            }), encoding="utf-8")
            document = payload(digest=digest)
            with mock.patch.object(validation, "validate_catalog_freshness", return_value=None):
                self.assertEqual(
                    "locator_candidate_read_set_required",
                    validate_context(document, repository_root=root, verify_catalog=True),
                )

    def test_rejects_forged_accepted_candidate(self) -> None:
        document = payload()
        document["decisions"][0]["candidate"]["path"] = "README.md"
        self.assertEqual("accepted_candidate_not_locator_bound", validate_context(document))

    def test_rejects_path_escape_before_source_read(self) -> None:
        document = payload(path="../outside.md")
        self.assertEqual(
            "candidate_path_outside_repository",
            validate_context(document, repository_root=Path.cwd(), verify_sources=True),
        )

    def test_requires_a_decision_for_every_locator_candidate(self) -> None:
        document = payload()
        document["locator_result"]["candidates"].append({"path": "README.md", "source_sha256": "b" * 64})
        document["result_sha256"] = canonical_hash(document["locator_result"])
        self.assertEqual("locator_candidate_decision_missing", validate_context(document))

    def test_rejects_non_adapter_decision_owner(self) -> None:
        document = payload()
        document["decisions"][0]["owner"] = "llm"
        self.assertEqual("consumption_decision_owner_invalid", validate_context(document))

    def test_requires_accepted_coverage_for_each_required_module(self) -> None:
        document = payload()
        document["required_modules"] = ["repository-rules", "phase-service"]
        self.assertEqual("required_modules_unsatisfied", validate_context(document))

    def test_rejects_unregistered_rejection_reason(self) -> None:
        document = payload()
        document["decisions"][0].update({
            "decision": "rejected",
            "satisfies": [],
            "rejection_reason": "not-selected-by-vdd-adapter",
        })
        self.assertEqual("rejected_candidate_invalid", validate_context(document))

    def test_rejects_accepted_coverage_outside_required_modules(self) -> None:
        document = payload()
        document["decisions"][0]["satisfies"].append("undeclared")
        self.assertEqual("consumption_modules_outside_required", validate_context(document))

    def test_rejects_preflight_hash_or_status_drift(self) -> None:
        document = payload()
        document["preflight"] = {
            "status": "ready",
            "failure_code": None,
            "context_sha256": "sha256:" + "0" * 64,
        }
        self.assertEqual("preflight_context_hash_mismatch", validate_context(document))
        document["preflight"]["context_sha256"] = canonical_hash({key: value for key, value in document.items() if key != "preflight"})
        document["preflight"]["status"] = "blocked"
        self.assertEqual("preflight_status_invalid", validate_context(document))

    def test_expected_consumer_is_enforced(self) -> None:
        document = payload()
        document["locator_request"]["consumer"] = "vdd"
        document["request_sha256"] = canonical_hash(document["locator_request"])
        self.assertEqual("knowledge_consumer_mismatch", validate_context(document, expected_consumer="bootstrap"))

    def test_rejects_migration_candidate_before_source_read(self) -> None:
        document = payload(path="docs/migration/legacy.md")
        self.assertEqual("candidate_path_excluded", validate_context(document))

    def test_rejects_read_set_that_does_not_start_with_primary_source(self) -> None:
        document = payload()
        document["locator_result"]["candidates"][0]["read_set"] = [
            {"role": "supporting-source", "path": "README.md", "source_sha256": "b" * 64}
        ]
        document["result_sha256"] = canonical_hash(document["locator_result"])
        self.assertEqual("locator_candidate_read_set_invalid", validate_context(document))

    def test_consumer_can_require_ready_preflight(self) -> None:
        document = payload()
        self.assertEqual("preflight_invalid", validate_context(document, require_preflight=True))

    def test_worktree_source_hash_is_revalidated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "AGENTS.md"
            source.write_text("rules\n", encoding="utf-8")
            document = payload(digest=hashlib.sha256(source.read_bytes()).hexdigest())
            self.assertIsNone(validation.validate_worktree_sources(document, root))

    def test_hash_only_read_set_drift_is_refreshed_without_selection_expansion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "AGENTS.md"
            source.write_text("new rules\n", encoding="utf-8")
            document = payload(digest="a" * 64)
            refreshed = validation.refresh_context_read_set(document, root)
            candidate = refreshed["locator_result"]["candidates"][0]
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            self.assertEqual("AGENTS.md", candidate["path"])
            self.assertEqual(digest, candidate["source_sha256"])
            self.assertEqual("current_worktree_read_set", refreshed["source_refresh"]["mode"])
            self.assertIsNone(
                validate_context(refreshed, repository_root=root, verify_sources=True)
            )

    def test_read_set_refresh_rejects_path_escape(self) -> None:
        document = payload(path="../outside.md")
        with self.assertRaisesRegex(ValueError, "candidate_path_outside_repository"):
            validation.refresh_context_read_set(document, Path.cwd())
            source.write_text("changed\n", encoding="utf-8")
            self.assertEqual(
                "candidate_worktree_source_hash_mismatch",
                validation.validate_worktree_sources(document, root),
            )


if __name__ == "__main__":
    unittest.main()
