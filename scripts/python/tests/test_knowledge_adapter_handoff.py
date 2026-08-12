from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


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
            "policy_revision": "knowledge-consumer-policies.v2",
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
        preflight = vdd.evaluate_preflight(context, repository_root=REPOSITORY_ROOT)
        current_main = subprocess.check_output(
            ["git", "rev-parse", "refs/heads/main"], cwd=REPOSITORY_ROOT, text=True, encoding="ascii"
        ).strip()
        if snapshot["commit"] != current_main:
            self.assertEqual("blocked", preflight["status"], preflight)
            self.assertEqual("catalog_stale", preflight["failure_code"])
            return
        self.assertEqual("ready", preflight["status"], preflight)
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
                [{"artifact": "AGENTS.md", "sha256": "sha256:" + entry["source_sha256"]}],
            )
            self.assertEqual("AGENTS.md", frozen["accepted"][0]["path"])


if __name__ == "__main__":
    unittest.main()
