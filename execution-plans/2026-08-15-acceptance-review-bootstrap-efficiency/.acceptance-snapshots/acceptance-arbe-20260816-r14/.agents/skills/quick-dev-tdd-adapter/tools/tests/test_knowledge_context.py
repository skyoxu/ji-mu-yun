from __future__ import annotations

import importlib.util
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


TOOLS = Path(__file__).resolve().parents[1]
MODULE_PATH = TOOLS / "knowledge_context.py"


def load_module():
    if not MODULE_PATH.is_file():
        raise FileNotFoundError(MODULE_PATH)
    spec = importlib.util.spec_from_file_location("quick_dev_knowledge_context", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class QuickDevKnowledgeContextTests(unittest.TestCase):
    def test_quick_dev_adapter_has_no_locator_query_path(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("knowledge_locator.py", source)

    def test_locator_result_or_consumption_decision_cannot_expand_frozen_context(self) -> None:
        try:
            module = load_module()
        except FileNotFoundError:
            self.fail("KWI-QUICK-SCOPE-EXPANSION: verify-bound knowledge context is missing")
        frozen = {"accepted": [{"path": "docs/a.md", "source_sha256": "a" * 64, "satisfies": ["repository-rules"]}]}
        proposed = {"accepted": [{"path": "docs/a.md", "source_sha256": "a" * 64, "satisfies": ["repository-rules", "extra"]}]}
        result = module.verify_frozen_context(frozen, proposed)
        self.assertEqual("vdd-repair", result["status"])
        self.assertEqual("KWI-QUICK-SCOPE-EXPANSION", result["failure_code"])

    def test_publication_drift_routes_to_vdd_repair_before_red(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temporary:
            plan = Path(temporary)
            (plan / "knowledge-context.v1.json").write_text("{}\n", encoding="utf-8")
            (plan / "knowledge-context.freeze.v1.json").write_text("{}\n", encoding="utf-8")
            validator = SimpleNamespace(validate_context=lambda *_args, **_kwargs: "catalog_publication_invalid")
            with mock.patch.object(module, "_validator", return_value=validator):
                result = module.verify_plan_context(Path.cwd(), plan)
        self.assertEqual("vdd-repair", result["status"])
        self.assertEqual("catalog_publication_invalid", result["detail"])

    def test_missing_freeze_receipt_routes_to_vdd_repair(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temporary:
            plan = Path(temporary)
            (plan / "knowledge-context.v1.json").write_text("{}\n", encoding="utf-8")
            result = module.verify_plan_context(Path.cwd(), plan)
        self.assertEqual("vdd-repair", result["status"])
        self.assertEqual("freeze_receipt_missing", result["detail"])

    def test_recomputed_context_hashes_cannot_bypass_vdd_freeze_receipt(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temporary:
            plan = Path(temporary)
            context_path = plan / "knowledge-context.v1.json"
            context = {
                "locator_request": {"snapshot": {}, "policy_revision": "policy-v2"},
                "locator_result": {"source_snapshot_id": "sha256:" + "a" * 64},
                "request_sha256": "sha256:" + "b" * 64,
                "result_sha256": "sha256:" + "c" * 64,
                "decisions": [{
                    "decision": "accepted",
                    "candidate": {"path": "AGENTS.md", "source_sha256": "d" * 64},
                    "satisfies": ["repository-rules"],
                }],
            }
            context_bytes = (json.dumps(context, indent=2) + "\n").encode("utf-8")
            context_path.write_bytes(context_bytes)
            validator = SimpleNamespace(
                validate_context=lambda *_args, **_kwargs: None,
                validate_worktree_sources=lambda *_args, **_kwargs: None,
                canonical_hash=lambda value: "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            )
            receipt = {
                "schema_version": "jimuyun.vdd-knowledge-freeze.v1",
                "context_path": context_path.name,
                "context_sha256": "sha256:" + hashlib.sha256(context_bytes).hexdigest(),
                "canonical_context_sha256": validator.canonical_hash(context),
                "request_sha256": context["request_sha256"],
                "result_sha256": context["result_sha256"],
                "snapshot": {},
                "source_snapshot_id": context["locator_result"]["source_snapshot_id"],
                "policy_revision": "policy-v2",
                "accepted": [{"path": "AGENTS.md", "source_sha256": "d" * 64, "satisfies": ["repository-rules"]}],
                "authorizes": [],
            }
            (plan / "knowledge-context.freeze.v1.json").write_text(json.dumps(receipt) + "\n", encoding="utf-8")
            context["decisions"][0]["satisfies"].append("expanded")
            context_path.write_text(json.dumps(context, indent=2) + "\n", encoding="utf-8")
            with mock.patch.object(module, "_validator", return_value=validator):
                result = module.verify_plan_context(Path.cwd(), plan)
        self.assertEqual("vdd-repair", result["status"])
        self.assertEqual("freeze_receipt_mismatch", result["detail"])

    def test_worktree_source_drift_routes_to_vdd_repair(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temporary:
            plan = Path(temporary)
            context = {
                "locator_request": {"snapshot": {}, "policy_revision": "policy-v2"},
                "locator_result": {"source_snapshot_id": "sha256:" + "a" * 64},
                "request_sha256": "sha256:" + "b" * 64,
                "result_sha256": "sha256:" + "c" * 64,
                "decisions": [],
            }
            context_bytes = (json.dumps(context) + "\n").encode("utf-8")
            (plan / "knowledge-context.v1.json").write_bytes(context_bytes)
            (plan / "knowledge-context.freeze.v1.json").write_text("{}\n", encoding="utf-8")
            validator = SimpleNamespace(
                validate_context=lambda *_args, **_kwargs: None,
                validate_worktree_sources=lambda *_args, **_kwargs: "candidate_worktree_source_hash_mismatch",
            )
            with mock.patch.object(module, "_validator", return_value=validator):
                result = module.verify_plan_context(Path.cwd(), plan)
        self.assertEqual("candidate_worktree_source_hash_mismatch", result["detail"])

    def test_worktree_gate_uses_only_accepted_locator_candidates(self) -> None:
        module = load_module()
        context = {
            "locator_request": {"snapshot": {}, "policy_revision": "policy-v2"},
            "locator_result": {"source_snapshot_id": "sha256:" + "a" * 64, "candidates": [
                {"path": "AGENTS.md", "source_sha256": "b" * 64},
                {"path": "docs/stale.md", "source_sha256": "c" * 64},
            ]},
            "request_sha256": "sha256:" + "d" * 64,
            "result_sha256": "sha256:" + "e" * 64,
            "decisions": [
                {"decision": "accepted", "candidate": {"path": "AGENTS.md", "source_sha256": "b" * 64}, "satisfies": ["repository-rules"]},
                {"decision": "rejected", "candidate": {"path": "docs/stale.md", "source_sha256": "c" * 64}, "satisfies": []},
            ],
        }
        with tempfile.TemporaryDirectory() as temporary:
            plan = Path(temporary)
            context_path = plan / "knowledge-context.v1.json"
            context_bytes = (json.dumps(context) + "\n").encode("utf-8")
            context_path.write_bytes(context_bytes)
            captured = []
            def validate_worktree_sources(payload, _root):
                captured.extend(payload["locator_result"]["candidates"])
                return None
            validator = SimpleNamespace(
                validate_context=lambda *_args, **_kwargs: None,
                validate_worktree_sources=validate_worktree_sources,
                canonical_hash=lambda value: "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            )
            receipt = {
                "schema_version": "jimuyun.vdd-knowledge-freeze.v1",
                "context_path": context_path.name,
                "context_sha256": "sha256:" + hashlib.sha256(context_bytes).hexdigest(),
                "canonical_context_sha256": validator.canonical_hash(context),
                "request_sha256": context["request_sha256"],
                "result_sha256": context["result_sha256"],
                "snapshot": {},
                "source_snapshot_id": context["locator_result"]["source_snapshot_id"],
                "policy_revision": "policy-v2",
                "accepted": [{"path": "AGENTS.md", "source_sha256": "b" * 64, "satisfies": ["repository-rules"]}],
                "authorizes": [],
            }
            (plan / "knowledge-context.freeze.v1.json").write_text(json.dumps(receipt) + "\n", encoding="utf-8")
            with mock.patch.object(module, "_validator", return_value=validator):
                result = module.verify_plan_context(Path.cwd(), plan)
        self.assertEqual("verified", result["status"])
        self.assertEqual(["AGENTS.md"], [candidate["path"] for candidate in captured])


if __name__ == "__main__":
    unittest.main()
