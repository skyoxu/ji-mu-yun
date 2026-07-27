from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, REPOSITORY_ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class KnowledgeAdapterHandoffTests(unittest.TestCase):
    def test_vdd_context_is_accepted_by_quick_dev_and_bootstrap(self) -> None:
        validation = load("handoff_validation", "scripts/python/knowledge_context_validation.py")
        vdd = load("handoff_vdd", ".agents/skills/vdd-execution-plan/scripts/vdd_knowledge_preflight.py")
        quick = load("handoff_quick", ".agents/skills/quick-dev-tdd-adapter/tools/knowledge_context.py")
        bootstrap = load("handoff_bootstrap", ".agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py")
        catalog = json.loads((REPOSITORY_ROOT / "knowledge/catalogs/repository-knowledge-catalog.v1.json").read_text(encoding="utf-8"))
        entry = next(item for item in catalog["entries"] if item["source_path"] == "AGENTS.md")
        snapshot = {key: catalog["source_snapshot"][key] for key in ("ref", "commit")}
        request = {
            "schema_version": "jimuyun.knowledge-locator-request.v1",
            "request_id": "adapter-handoff-1", "snapshot": snapshot,
        }
        result = {
            "schema_version": "jimuyun.knowledge-locator-result.v1",
            "request_id": "adapter-handoff-1", "snapshot": snapshot,
            "status": "matched", "candidates": [{"path": "AGENTS.md", "source_sha256": entry["source_sha256"]}],
        }
        context = {
            "schema_version": "jimuyun.vdd-knowledge-context.v1",
            "locator_request": request, "locator_result": result,
            "required_modules": ["repository-rules"],
            "decisions": [{
                "decision": "accepted", "satisfies": ["repository-rules"],
                "candidate": {"path": "AGENTS.md", "source_sha256": entry["source_sha256"]},
                "rejection_reason": None,
            }],
            "request_sha256": validation.canonical_hash(request),
            "result_sha256": validation.canonical_hash(result),
        }
        self.assertEqual("ready", vdd.evaluate_preflight(context, repository_root=REPOSITORY_ROOT)["status"])
        with tempfile.TemporaryDirectory() as raw:
            plan_dir = Path(raw)
            (plan_dir / "knowledge-context.v1.json").write_text(json.dumps(context), encoding="utf-8")
            self.assertEqual("verified", quick.verify_plan_context(REPOSITORY_ROOT, plan_dir)["status"])
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as raw:
            context_path = Path(raw) / "knowledge-context.v1.json"
            context_path.write_text(json.dumps(context), encoding="utf-8")
            relative = context_path.relative_to(REPOSITORY_ROOT).as_posix()
            frozen = bootstrap.freeze_knowledge_context(
                REPOSITORY_ROOT, relative,
                [{"artifact": "AGENTS.md", "sha256": "sha256:" + hashlib.sha256((REPOSITORY_ROOT / "AGENTS.md").read_bytes()).hexdigest()}],
            )
            self.assertEqual("AGENTS.md", frozen["accepted"][0]["path"])


if __name__ == "__main__":
    unittest.main()
