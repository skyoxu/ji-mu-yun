from __future__ import annotations

import importlib.util
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def load(name: str, relative: str):
    module_path = REPOSITORY_ROOT / relative
    spec = importlib.util.spec_from_file_location(name, module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    previous_path = list(sys.path)
    try:
        sys.path.insert(0, str(module_path.parent))
        sys.path.insert(0, str(REPOSITORY_ROOT / "scripts/python"))
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = previous_path
    return module


class KnowledgeAdapterHandoffTests(unittest.TestCase):
    def test_vdd_context_is_accepted_by_quick_dev_and_bootstrap(self) -> None:
        validation = load("handoff_validation", "scripts/python/knowledge_context_validation.py")
        vdd = load("handoff_vdd", ".agents/skills/vdd-execution-plan/scripts/vdd_knowledge_preflight.py")
        quick = load("handoff_quick", ".agents/skills/quick-dev-tdd-adapter/tools/knowledge_context.py")
        bootstrap = load("handoff_bootstrap", ".agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py")
        catalog = json.loads((REPOSITORY_ROOT / "knowledge/catalogs/repository-knowledge-catalog.v2.json").read_text(encoding="utf-8"))
        entry = next(item for item in catalog["modules"] if item["source_path"] == "AGENTS.md")
        snapshot = {key: catalog["source_snapshot"][key] for key in ("ref", "commit")}
        request = {
            "schema_version": "jimuyun.knowledge-locator-request.v1",
            "request_id": "adapter-handoff-1", "consumer": "vdd", "snapshot": snapshot,
            "policy_revision": "knowledge-consumer-policies.v2", "allow_stale_catalog": True,
        }
        read_set = [{"role": "primary", "path": entry["source_path"], "source_sha256": entry["source_sha256"]}]
        result = {
            "schema_version": "jimuyun.knowledge-locator-result.v1",
            "request_id": "adapter-handoff-1", "snapshot": snapshot,
            "source_snapshot_id": catalog["source_snapshot"]["snapshot_id"],
            "policy_revision": "knowledge-consumer-policies.v2",
            "status": "matched", "candidates": [{"path": "AGENTS.md", "source_sha256": entry["source_sha256"], "module_id": entry["module_id"], "read_set": read_set}],
        }
        context = {
            "schema_version": "jimuyun.vdd-knowledge-context.v1",
            "locator_request": request, "locator_result": result,
            "required_modules": ["repository-rules"],
            "decisions": [{
                "owner": "adapter",
                "decision": "accepted", "satisfies": ["repository-rules"],
                "candidate": {"path": "AGENTS.md", "source_sha256": entry["source_sha256"]},
                "rejection_reason": None,
            }],
            "request_sha256": validation.canonical_hash(request),
            "result_sha256": validation.canonical_hash(result),
        }
        catalog_freshness = validation.validate_catalog_freshness(REPOSITORY_ROOT)
        context["preflight"] = {
            "status": "ready", "failure_code": None,
            "knowledge_freshness": "degraded" if catalog_freshness == "catalog_stale" else "current",
            "catalog_failure_code": "catalog_stale" if catalog_freshness == "catalog_stale" else None,
            "context_sha256": validation.canonical_hash(context),
        }
        preflight = vdd.evaluate_preflight(context, repository_root=REPOSITORY_ROOT)
        self.assertEqual("ready", preflight["status"], preflight)
        with tempfile.TemporaryDirectory() as raw:
            plan_dir = Path(raw)
            context_bytes = json.dumps(context).encode("utf-8")
            (plan_dir / "knowledge-context.v1.json").write_bytes(context_bytes)
            (plan_dir / "knowledge-context.freeze.v1.json").write_text(json.dumps({
                "schema_version": "jimuyun.vdd-knowledge-freeze.v1",
                "context_path": "knowledge-context.v1.json",
                "context_sha256": "sha256:" + hashlib.sha256(context_bytes).hexdigest(),
                "canonical_context_sha256": validation.canonical_hash(context),
                "request_sha256": context["request_sha256"],
                "result_sha256": context["result_sha256"],
                "snapshot": snapshot,
                "source_snapshot_id": result["source_snapshot_id"],
                "policy_revision": request["policy_revision"],
                "accepted": [{
                    "path": "AGENTS.md", "source_sha256": entry["source_sha256"],
                    "satisfies": ["repository-rules"],
                }],
                "authorizes": [],
            }), encoding="utf-8")
            with mock.patch.object(quick, "_validator", return_value=validation):
                quick_result = quick.verify_plan_context(REPOSITORY_ROOT, plan_dir)
            self.assertEqual("verified", quick_result["status"], quick_result)
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as raw:
            context_path = Path(raw) / "knowledge-context.v1.json"
            context_bytes = json.dumps(context).encode("utf-8")
            context_path.write_bytes(context_bytes)
            freeze_path = context_path.with_name("knowledge-context.freeze.v1.json")
            freeze_path.write_text(json.dumps({
                "schema_version": "jimuyun.vdd-knowledge-freeze.v1",
                "context_path": context_path.name,
                "context_sha256": "sha256:" + hashlib.sha256(context_bytes).hexdigest(),
                "canonical_context_sha256": validation.canonical_hash(context),
                "request_sha256": context["request_sha256"],
                "result_sha256": context["result_sha256"],
                "snapshot": snapshot,
                "source_snapshot_id": result["source_snapshot_id"],
                "policy_revision": request["policy_revision"],
                "accepted": [{
                    "path": "AGENTS.md", "source_sha256": entry["source_sha256"],
                    "satisfies": ["repository-rules"],
                }],
                "authorizes": [],
            }), encoding="utf-8")
            relative = context_path.relative_to(REPOSITORY_ROOT).as_posix()
            with mock.patch.object(bootstrap, "_bound_knowledge_validator", return_value=validation):
                frozen = bootstrap.freeze_knowledge_context(
                    REPOSITORY_ROOT, relative,
                    [
                        {"artifact": "AGENTS.md", "sha256": "sha256:" + entry["source_sha256"]},
                        {"artifact": relative, "sha256": "sha256:" + hashlib.sha256(context_bytes).hexdigest()},
                        {
                            "artifact": freeze_path.relative_to(REPOSITORY_ROOT).as_posix(),
                            "sha256": "sha256:" + hashlib.sha256(freeze_path.read_bytes()).hexdigest(),
                        },
                    ],
                )
            self.assertEqual("AGENTS.md", frozen["accepted"][0]["path"])


if __name__ == "__main__":
    unittest.main()
