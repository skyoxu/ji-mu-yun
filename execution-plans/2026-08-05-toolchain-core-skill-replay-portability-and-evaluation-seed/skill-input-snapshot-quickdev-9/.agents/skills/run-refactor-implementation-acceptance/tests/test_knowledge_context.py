from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _load(name: str):
    path = SCRIPTS / name
    spec = importlib.util.spec_from_file_location(f"refactor_acceptance_{path.stem}", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RefactorAcceptanceKnowledgeContextTests(unittest.TestCase):
    def test_prepare_adapter_uses_refactor_consumer_and_canonical_locator(self) -> None:
        module = _load("prepare_knowledge_context.py")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            catalog = root / "knowledge" / "catalogs" / "repository-knowledge-catalog.v2.json"
            catalog.parent.mkdir(parents=True)
            catalog.write_text(json.dumps({"source_snapshot": {"ref": "refs/heads/main", "commit": "a" * 40}}), encoding="utf-8")
            policy = root / "knowledge" / "policies" / "consumer-policies.v2.json"
            policy.parent.mkdir(parents=True)
            policy.write_text(json.dumps({"policy_revision": "test-policy-v2"}), encoding="utf-8")
            output = root / "execution-plans" / "plan" / "knowledge-context.json"
            result = {
                "schema_version": "jimuyun.knowledge-locator-result.v1",
                "request_id": "request-1",
                "snapshot": {"ref": "refs/heads/main", "commit": "a" * 40},
                "source_snapshot_id": "sha256:" + "b" * 64,
                "policy_revision": "test-policy-v2",
                "status": "matched",
                "candidates": [{"path": "AGENTS.md", "source_sha256": "c" * 64}],
            }
            captured: dict[str, object] = {}

            def fake_run(command, **kwargs):
                captured["command"] = command
                captured["request"] = json.loads(kwargs["input"])
                return SimpleNamespace(returncode=0, stdout=json.dumps(result), stderr="")

            argv = [
                "prepare", "--repository-root", str(root), "--request-id", "request-1",
                "--query", "acceptance scope", "--max-candidates", "1",
                "--required-module", "acceptance-scope",
                "--target-plan", "execution-plans/plan",
                "--accept", "AGENTS.md=acceptance-scope", "--output", "execution-plans/plan/knowledge-context.json",
            ]
            with mock.patch.object(module.subprocess, "run", side_effect=fake_run), \
                 mock.patch.object(module, "validate_context", return_value=None), \
                 mock.patch.object(module, "validate_worktree_sources", return_value=None), \
                 mock.patch.object(sys, "argv", argv):
                self.assertEqual(0, module.main())
            document = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual("refactor-acceptance", captured["request"]["consumer"])
            self.assertEqual(1, captured["request"]["max_candidates"])
            self.assertIn("--allow-stale-catalog", captured["command"])
            self.assertEqual("1", captured["command"][captured["command"].index("--max-candidates") + 1])
            locator = Path(captured["command"][2])
            self.assertEqual((root / "scripts" / "python" / "knowledge_locator.py").resolve(), locator.resolve())
            self.assertEqual("ready", document["preflight"]["status"])

    def test_prepare_adapter_rejects_unbound_candidate_limits(self) -> None:
        module = _load("prepare_knowledge_context.py")
        with mock.patch.object(sys, "argv", [
            "prepare", "--request-id", "request-1", "--query", "scope",
            "--max-candidates", "0", "--target-plan", "execution-plans/plan",
            "--output", "execution-plans/plan/context.json",
        ]):
            with self.assertRaisesRegex(SystemExit, "between 1 and 12"):
                module.main()

    def test_freeze_rejects_wrong_consumer_even_when_shape_is_valid(self) -> None:
        module = _load("knowledge_context.py")
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary).resolve()
            context = target / "knowledge-context.json"
            context.write_text(json.dumps({"consumer": "vdd", "preflight": {"status": "ready"}}), encoding="utf-8")
            validator = SimpleNamespace(
                validate_context=lambda *args, **kwargs: None,
                validate_worktree_sources=lambda *args, **kwargs: None,
            )
            with mock.patch.object(module, "_repository_root", return_value=target), \
                 mock.patch.object(module, "_validator", return_value=validator):
                with self.assertRaisesRegex(module.InputError, "consumer must be refactor-acceptance"):
                    module.freeze_knowledge_context(target, "knowledge-context.json")

    def test_prepare_run_cli_requires_frozen_knowledge_context(self) -> None:
        source = (SCRIPTS / "acceptance_cli.py").read_text(encoding="utf-8")
        self.assertIn('prepare.add_argument("--knowledge-context", required=True', source)
        self.assertNotIn("knowledge_locator.py", source)

    def test_prepare_output_must_be_bound_to_explicit_target_plan(self) -> None:
        module = _load("prepare_knowledge_context.py")
        root = Path("C:/repository").resolve()
        target = module._target_plan_path(root, Path("execution-plans/plan"))
        for raw in (
            Path("C:/outside/context.json"), Path("../context.json"), Path("docs/context.json"),
            Path("execution-plans/other/context.json"),
        ):
            with self.subTest(raw=str(raw)), self.assertRaises(ValueError):
                module._output_path(root, raw, target)
        self.assertEqual(
            (root / "execution-plans/plan/context.json").resolve(),
            module._output_path(root, Path("execution-plans/plan/context.json"), target),
        )

    def test_catalog_stale_writes_degraded_context_without_maintenance_route(self) -> None:
        module = _load("prepare_knowledge_context.py")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            catalog = root / "knowledge/catalogs/repository-knowledge-catalog.v2.json"
            catalog.parent.mkdir(parents=True)
            catalog.write_text(json.dumps({"source_snapshot": {"ref": "refs/heads/main", "commit": "a" * 40}}), encoding="utf-8")
            policy = root / "knowledge/policies/consumer-policies.v2.json"
            policy.parent.mkdir(parents=True)
            policy.write_text(json.dumps({"policy_revision": "test-policy-v2"}), encoding="utf-8")
            locator = {"status": "matched", "candidates": [], "source_snapshot_id": "sha256:" + "b" * 64}
            argv = [
                "prepare", "--repository-root", str(root), "--request-id", "request-1",
                "--query", "scope", "--target-plan", "execution-plans/plan",
                "--output", "execution-plans/plan/knowledge-context.json",
            ]
            with mock.patch.object(module.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=json.dumps(locator), stderr="")), \
                 mock.patch.object(module, "validate_context", return_value=None), \
                 mock.patch.object(module, "validate_catalog_freshness", return_value="catalog_stale"), \
                 mock.patch.object(module, "validate_worktree_sources", return_value=None), \
                 mock.patch.object(sys, "argv", argv), mock.patch("builtins.print") as printed:
                self.assertEqual(0, module.main())
            result = json.loads(printed.call_args.args[0])
            self.assertEqual("ready", result["status"])
            context = json.loads((root / "execution-plans/plan/knowledge-context.json").read_text(encoding="utf-8"))
            self.assertTrue(context["locator_request"]["allow_stale_catalog"])
            self.assertEqual("degraded", context["preflight"]["knowledge_freshness"])
            self.assertEqual("catalog_stale", context["preflight"]["catalog_failure_code"])
            self.assertFalse((root / "execution-plans/plan/knowledge-context-routes").exists())

    def test_freeze_accepts_degraded_catalog_with_current_read_set(self) -> None:
        module = _load("knowledge_context.py")
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary).resolve()
            document = {
                "consumer": "refactor-acceptance",
                "locator_request": {"allow_stale_catalog": True},
                "locator_result": {"source_snapshot_id": "sha256:" + "a" * 64},
                "decisions": [],
                "request_sha256": "sha256:" + "b" * 64,
                "result_sha256": "sha256:" + "c" * 64,
            }
            document["preflight"] = {
                "status": "ready", "failure_code": None,
                "knowledge_freshness": "degraded", "catalog_failure_code": "catalog_stale",
                "context_sha256": module.canonical_hash(document),
            }
            (target / "knowledge-context.json").write_text(json.dumps(document), encoding="utf-8")
            validator = SimpleNamespace(
                validate_context=lambda *args, **kwargs: None,
                validate_worktree_sources=lambda *args, **kwargs: None,
                validate_catalog_freshness=lambda *args, **kwargs: "catalog_stale",
            )
            with mock.patch.object(module, "_repository_root", return_value=target), \
                 mock.patch.object(module, "_validator", return_value=validator):
                frozen = module.freeze_knowledge_context(target, "knowledge-context.json")
            self.assertEqual("knowledge-context.json", frozen["path"])

    def test_worktree_read_set_drift_returns_route_before_context_publication(self) -> None:
        module = _load("prepare_knowledge_context.py")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            catalog = root / "knowledge/catalogs/repository-knowledge-catalog.v2.json"
            catalog.parent.mkdir(parents=True)
            catalog.write_text(json.dumps({"source_snapshot": {"ref": "refs/heads/main", "commit": "a" * 40}}), encoding="utf-8")
            policy = root / "knowledge/policies/consumer-policies.v2.json"
            policy.parent.mkdir(parents=True)
            policy.write_text(json.dumps({"policy_revision": "test-policy-v2"}), encoding="utf-8")
            locator = {"status": "matched", "candidates": [], "source_snapshot_id": "sha256:" + "b" * 64}
            argv = [
                "prepare", "--repository-root", str(root), "--request-id", "request-2",
                "--query", "scope", "--target-plan", "execution-plans/plan",
                "--output", "execution-plans/plan/context.json",
            ]
            with mock.patch.object(module.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=json.dumps(locator), stderr="")), \
                 mock.patch.object(module, "validate_context", return_value=None), \
                 mock.patch.object(module, "validate_worktree_sources", return_value="candidate_worktree_source_hash_mismatch"), \
                 mock.patch.object(sys, "argv", argv), mock.patch("builtins.print") as printed:
                self.assertEqual(2, module.main())
            route = json.loads(printed.call_args.args[0])
            self.assertEqual("knowledge-context-repair-required", route["next_action"])
            self.assertEqual("candidate_worktree_source_hash_mismatch", route["failure_code"])
            self.assertFalse((root / "execution-plans/plan/context.json").exists())


if __name__ == "__main__":
    unittest.main()
