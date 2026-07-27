from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


SKILL_ROOT = Path(__file__).resolve().parents[2]
PREFLIGHT_PATH = SKILL_ROOT / "scripts" / "vdd_knowledge_preflight.py"
PREPARE_PATH = SKILL_ROOT / "scripts" / "prepare_knowledge_context.py"


def load_preflight():
    if not PREFLIGHT_PATH.is_file():
        raise FileNotFoundError(PREFLIGHT_PATH)
    spec = importlib.util.spec_from_file_location("vdd_knowledge_preflight", PREFLIGHT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_prepare():
    spec = importlib.util.spec_from_file_location("prepare_knowledge_context", PREPARE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def bound_payload(module, payload: dict) -> dict:
    payload.setdefault("schema_version", "jimuyun.vdd-knowledge-context.v1")
    request = payload.setdefault("locator_request", {})
    result = payload.setdefault("locator_result", {})
    request.setdefault("schema_version", "jimuyun.knowledge-locator-request.v1")
    result.setdefault("schema_version", "jimuyun.knowledge-locator-result.v1")
    payload["request_sha256"] = module.canonical_hash(request)
    payload["result_sha256"] = module.canonical_hash(result)
    return payload


class VddKnowledgePreflightTests(unittest.TestCase):
    def test_all_rejected_candidates_block_plan_ready(self) -> None:
        try:
            module = load_preflight()
        except FileNotFoundError:
            self.fail("KWI-CONSUMPTION-REQUIRED-UNCOVERED: VDD knowledge preflight is missing")
        result = module.evaluate_consumption(
            required_modules=["repository-rules"],
            decisions=[{"decision": "rejected", "satisfies": []}],
        )
        self.assertEqual("blocked", result["status"])
        self.assertEqual(["repository-rules"], result["missing_required_modules"])

    def test_matched_locator_candidate_allows_required_module(self) -> None:
        module = load_preflight()
        snapshot = {"ref": "refs/heads/main", "commit": "a" * 40}
        result = module.evaluate_preflight(bound_payload(module,
            {
                "required_modules": ["repository-rules"],
                "locator_request": {
                    "schema_version": "jimuyun.knowledge-locator-request.v1",
                    "request_id": "request-1",
                    "snapshot": snapshot,
                },
                "locator_result": {
                    "schema_version": "jimuyun.knowledge-locator-result.v1",
                    "request_id": "request-1",
                    "snapshot": snapshot,
                    "status": "matched",
                    "candidates": [{"path": "AGENTS.md", "source_sha256": "b" * 64}],
                },
                "decisions": [{
                    "decision": "accepted",
                    "satisfies": ["repository-rules"],
                    "candidate": {"path": "AGENTS.md", "source_sha256": "b" * 64},
                }],
            }
        ))
        self.assertEqual("ready", result["status"])

    def test_snapshot_mismatch_blocks_preflight(self) -> None:
        module = load_preflight()
        result = module.evaluate_preflight(bound_payload(module,
            {
                "required_modules": [],
                "locator_request": {"schema_version": "jimuyun.knowledge-locator-request.v1", "request_id": "request-1", "snapshot": {"ref": "refs/heads/main", "commit": "a" * 40}},
                "locator_result": {"schema_version": "jimuyun.knowledge-locator-result.v1", "request_id": "request-1", "snapshot": {"ref": "refs/heads/main", "commit": "b" * 40}, "status": "matched", "candidates": []},
                "decisions": [],
            }
        ))
        self.assertEqual("blocked", result["status"])
        self.assertEqual("locator_snapshot_mismatch", result["failure_code"])

    def test_accepted_candidate_outside_locator_result_blocks_preflight(self) -> None:
        module = load_preflight()
        snapshot = {"ref": "refs/heads/main", "commit": "a" * 40}
        result = module.evaluate_preflight(bound_payload(module,
            {
                "required_modules": ["repository-rules"],
                "locator_request": {"schema_version": "jimuyun.knowledge-locator-request.v1", "request_id": "request-1", "snapshot": snapshot},
                "locator_result": {"schema_version": "jimuyun.knowledge-locator-result.v1", "request_id": "request-1", "snapshot": snapshot, "status": "matched", "candidates": [{"path": "README.md", "source_sha256": "a" * 64}]},
                "decisions": [{"decision": "accepted", "satisfies": ["repository-rules"], "candidate": {"path": "AGENTS.md", "source_sha256": "b" * 64}}],
            }
        ))
        self.assertEqual("blocked", result["status"])
        self.assertEqual("accepted_candidate_not_locator_bound", result["failure_code"])

    def test_missing_decision_for_locator_candidate_blocks_preflight(self) -> None:
        module = load_preflight()
        snapshot = {"ref": "refs/heads/main", "commit": "a" * 40}
        result = module.evaluate_preflight(bound_payload(module, {
            "required_modules": [],
            "locator_request": {"request_id": "request-1", "snapshot": snapshot},
            "locator_result": {
                "request_id": "request-1", "snapshot": snapshot, "status": "matched",
                "candidates": [{"path": "AGENTS.md", "source_sha256": "b" * 64}],
            },
            "decisions": [],
        }))
        self.assertEqual("blocked", result["status"])
        self.assertEqual("locator_candidate_decision_missing", result["failure_code"])

    def test_locator_hash_mismatch_blocks_preflight(self) -> None:
        module = load_preflight()
        snapshot = {"ref": "refs/heads/main", "commit": "a" * 40}
        payload = bound_payload(module, {
            "required_modules": [],
            "locator_request": {"request_id": "request-1", "snapshot": snapshot},
            "locator_result": {"request_id": "request-1", "snapshot": snapshot, "status": "matched", "candidates": []},
            "decisions": [],
        })
        payload["result_sha256"] = "sha256:" + "0" * 64
        result = module.evaluate_preflight(payload)
        self.assertEqual("blocked", result["status"])
        self.assertEqual("locator_hash_mismatch", result["failure_code"])

    def test_prepare_writes_and_enforces_preflight_result(self) -> None:
        module = load_prepare()
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            catalog = root / "knowledge/catalogs/repository-knowledge-catalog.v1.json"
            catalog.parent.mkdir(parents=True)
            catalog.write_text(json.dumps({"source_snapshot": {"ref": "refs/heads/main", "commit": "a" * 40}}), encoding="utf-8")
            output = root / "plan/knowledge-context.v1.json"
            result = {
                "schema_version": "jimuyun.knowledge-locator-result.v1", "request_id": "request-1",
                "snapshot": {"ref": "refs/heads/main", "commit": "a" * 40}, "status": "matched",
                "candidates": [{"path": "AGENTS.md", "source_sha256": "b" * 64}],
            }
            with mock.patch.object(module.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=json.dumps(result), stderr="")), \
                 mock.patch.object(module, "validate_context", return_value=None), \
                 mock.patch.object(sys, "argv", ["prepare", "--repository-root", str(root), "--request-id", "request-1", "--query", "rules", "--required-module", "repository-rules", "--accept", "AGENTS.md=repository-rules", "--output", str(output)]):
                self.assertEqual(0, module.main())
            document = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual("ready", document["preflight"]["status"])
            self.assertIn("context_sha256", document["preflight"])


if __name__ == "__main__":
    unittest.main()
