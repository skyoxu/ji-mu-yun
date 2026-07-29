from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

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


if __name__ == "__main__":
    unittest.main()
