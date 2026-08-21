from __future__ import annotations

import importlib.util
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


SKILL_ROOT = Path(__file__).resolve().parents[2]
PREFLIGHT_PATH = SKILL_ROOT / "scripts" / "vdd_knowledge_preflight.py"
PREPARE_PATH = SKILL_ROOT / "scripts" / "prepare_knowledge_context.py"
TEST_SUPPORT = SKILL_ROOT.parents[2] / "scripts" / "python" / "tests"
if str(TEST_SUPPORT) not in sys.path:
    sys.path.insert(0, str(TEST_SUPPORT))

from skill_input_composition_support import publish_ready_receipt  # noqa: E402


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
    request.setdefault("consumer", "vdd")
    result.setdefault("schema_version", "jimuyun.knowledge-locator-result.v1")
    payload["request_sha256"] = module.canonical_hash(request)
    payload["result_sha256"] = module.canonical_hash(result)
    return payload


class VddKnowledgePreflightTests(unittest.TestCase):
    def test_replay_frozen_selection_rehashes_without_locator_query(self) -> None:
        module = load_prepare()
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = root / "AGENTS.md"
            source.write_text("current\n", encoding="utf-8")
            frozen = root / "knowledge-context.v1.json"
            request = {"schema_version": "jimuyun.knowledge-locator-request.v1", "request_id": "old", "consumer": "vdd", "snapshot": {"ref": "refs/heads/main", "commit": "a" * 40}, "policy_revision": "old", "allow_stale_catalog": True}
            result = {"schema_version": "jimuyun.knowledge-locator-result.v1", "request_id": "old", "snapshot": request["snapshot"], "status": "matched", "source_snapshot_id": "old", "policy_revision": "old", "candidates": [{"path": "AGENTS.md", "source_sha256": "0" * 64, "read_set": [{"path": "AGENTS.md", "source_sha256": "0" * 64}]}]}
            payload = {"schema_version": "jimuyun.vdd-knowledge-context.v1", "locator_request": request, "locator_result": result, "required_modules": ["repository-rules"], "decisions": [{"owner": "adapter", "candidate": {"path": "AGENTS.md", "source_sha256": "0" * 64}, "decision": "accepted", "satisfies": ["repository-rules"], "rejection_reason": None}]}
            validator = __import__("importlib").import_module("knowledge_context_validation")
            payload["request_sha256"] = validator.canonical_hash(request)
            payload["result_sha256"] = validator.canonical_hash(result)
            frozen.write_text(json.dumps(payload), encoding="utf-8")
            replayed = module._replay_frozen_selection(frozen_context=frozen, request_id="new", catalog_snapshot={"ref": "refs/heads/main", "commit": "b" * 40}, policy_revision="new", validator=validator, repository_root=root)
            self.assertEqual("new", replayed["locator_request"]["request_id"])
            self.assertEqual("AGENTS.md", replayed["decisions"][0]["candidate"]["path"])
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), replayed["decisions"][0]["candidate"]["source_sha256"])
            self.assertEqual("current_worktree_read_set", replayed["source_refresh"]["mode"])
    def test_cli_consumes_real_ready_skill_input_context(self) -> None:
        module = load_preflight()
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw) / "repo"
            target = root / "execution-plans" / "plan"
            target.mkdir(parents=True)
            requirements = root / "requirements.md"
            requirements.write_text("# Requirements\n", encoding="utf-8", newline="\n")
            artifacts = publish_ready_receipt(
                root,
                consumer="vdd-execution-plan",
                operation="create",
                target="execution-plans/plan",
                role_paths={"requirements": ["requirements.md"]},
            )
            snapshot = {"ref": "refs/heads/main", "commit": "a" * 40}
            payload = bound_payload(module, {
                "required_modules": ["repository-rules"],
                "locator_request": {"schema_version": "jimuyun.knowledge-locator-request.v1", "request_id": "request-1", "snapshot": snapshot},
                "locator_result": {"schema_version": "jimuyun.knowledge-locator-result.v1", "request_id": "request-1", "snapshot": snapshot, "status": "matched", "candidates": [{"path": "AGENTS.md", "source_sha256": "b" * 64}]},
                "decisions": [{"owner": "adapter", "decision": "accepted", "satisfies": ["repository-rules"], "candidate": {"path": "AGENTS.md", "source_sha256": "b" * 64}}],
            })
            input_path = target / "knowledge-preflight-input.json"
            input_path.write_text(json.dumps(payload), encoding="utf-8")
            output = io.StringIO()
            with mock.patch.object(sys, "argv", [
                "vdd_knowledge_preflight.py",
                "--input", str(input_path),
                "--repository-root", str(root),
                "--skill-input-receipt", str(artifacts["receipt"]),
                "--skill-input-contract", str(artifacts["contract"]),
                "--skill-input-operation", "create",
            ]), mock.patch.object(module, "validate_context", return_value=None), \
                 mock.patch.object(module, "validate_worktree_sources", return_value=None), \
                 mock.patch("sys.stdout", output):
                self.assertEqual(0, module.main())
            result = json.loads(output.getvalue())
            self.assertEqual(artifacts["context"].resolve().relative_to(root.resolve()).as_posix(), result["skill_input"]["context_artifact"])

    def test_cli_blocks_missing_wrong_and_stale_ready_receipts(self) -> None:
        module = load_preflight()
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw) / "repo"
            target = root / "execution-plans" / "plan"
            target.mkdir(parents=True)
            requirements = root / "requirements.md"
            requirements.write_text("# Requirements\n", encoding="utf-8", newline="\n")
            artifacts = publish_ready_receipt(
                root,
                consumer="vdd-execution-plan",
                operation="create",
                target="execution-plans/plan",
                role_paths={"requirements": ["requirements.md"]},
            )
            input_path = target / "knowledge-preflight-input.json"
            input_path.write_text("{}\n", encoding="utf-8", newline="\n")

            def invoke(receipt_path: Path, contract_path: Path) -> None:
                with mock.patch.object(sys, "argv", [
                    "vdd_knowledge_preflight.py",
                    "--input", str(input_path),
                    "--repository-root", str(root),
                    "--skill-input-receipt", str(receipt_path),
                    "--skill-input-contract", str(contract_path),
                    "--skill-input-operation", "create",
                ]):
                    module.main()

            with self.assertRaises(ValueError):
                invoke(root / "missing-receipt.json", artifacts["contract"])
            with self.assertRaises(ValueError):
                invoke(artifacts["candidate_receipt"], artifacts["contract"])
            wrong = publish_ready_receipt(
                root,
                consumer="wrong-vdd-consumer",
                operation="create",
                target="execution-plans/plan",
                role_paths={"requirements": ["requirements.md"]},
                protocol_name=".skill-input-composition-wrong",
            )
            with self.assertRaises(ValueError):
                invoke(wrong["receipt"], wrong["contract"])
            requirements.write_text("# Changed requirements\n", encoding="utf-8", newline="\n")
            with self.assertRaises(ValueError):
                invoke(artifacts["receipt"], artifacts["contract"])

    def test_cli_requires_skill_input_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            payload = root / "input.json"
            payload.write_text("{}\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(PREFLIGHT_PATH), "--input", str(payload), "--repository-root", str(root)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertNotEqual(0, result.returncode)
            self.assertIn("--skill-input-receipt", result.stderr)

    def test_all_rejected_candidates_block_plan_ready(self) -> None:
        try:
            module = load_preflight()
        except FileNotFoundError:
            self.fail("KWI-CONSUMPTION-REQUIRED-UNCOVERED: VDD knowledge preflight is missing")
        result = module.evaluate_consumption(
            required_modules=["repository-rules"],
            decisions=[{"owner": "adapter", "decision": "rejected", "satisfies": [], "rejection_reason": "wrong_domain"}],
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
                    "owner": "adapter",
                    "decision": "accepted",
                    "satisfies": ["repository-rules"],
                    "candidate": {"path": "AGENTS.md", "source_sha256": "b" * 64},
                }],
            }
        ))
        self.assertEqual("ready", result["status"])

    def test_rejected_candidate_drift_does_not_block_preflight(self) -> None:
        module = load_preflight()
        snapshot = {"ref": "refs/heads/main", "commit": "a" * 40}
        payload = bound_payload(module, {
            "required_modules": ["repository-rules"],
            "locator_request": {"request_id": "request-1", "snapshot": snapshot},
            "locator_result": {"request_id": "request-1", "snapshot": snapshot, "status": "matched", "candidates": [
                {"path": "AGENTS.md", "source_sha256": "b" * 64},
                {"path": "docs/stale.md", "source_sha256": "c" * 64},
            ]},
            "decisions": [
                {"owner": "adapter", "decision": "accepted", "satisfies": ["repository-rules"], "candidate": {"path": "AGENTS.md", "source_sha256": "b" * 64}},
                {"owner": "adapter", "decision": "rejected", "satisfies": [], "candidate": {"path": "docs/stale.md", "source_sha256": "c" * 64}},
            ],
        })
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            captured = []
            def validate_worktree_sources(projected, _root):
                captured.extend(projected["locator_result"]["candidates"])
                return None
            with mock.patch.object(module, "validate_context", return_value=None) as validate, \
                 mock.patch.object(module, "validate_worktree_sources", side_effect=validate_worktree_sources):
                result = module.evaluate_preflight(payload, repository_root=root)
        self.assertEqual("ready", result["status"])
        self.assertFalse(validate.call_args.kwargs["verify_sources"])
        self.assertEqual(["AGENTS.md"], [candidate["path"] for candidate in captured])

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
                "decisions": [{"owner": "adapter", "decision": "accepted", "satisfies": ["repository-rules"], "candidate": {"path": "AGENTS.md", "source_sha256": "b" * 64}}],
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
            catalog = root / "knowledge/catalogs/repository-knowledge-catalog.v2.json"
            catalog.parent.mkdir(parents=True)
            catalog.write_text(json.dumps({"source_snapshot": {"ref": "refs/heads/main", "commit": "a" * 40}}), encoding="utf-8")
            policy = root / "knowledge/policies/consumer-policies.v2.json"
            policy.parent.mkdir(parents=True)
            policy.write_text(json.dumps({"policy_revision": "test-policy-v2"}), encoding="utf-8")
            output = root / "execution-plans/plan/knowledge-context.v1.json"
            result = {
                "schema_version": "jimuyun.knowledge-locator-result.v1", "request_id": "request-1",
                "snapshot": {"ref": "refs/heads/main", "commit": "a" * 40}, "status": "matched",
                "candidates": [{"path": "AGENTS.md", "source_sha256": "b" * 64}],
            }
            validator = SimpleNamespace(
                validate_context=lambda *_args, **_kwargs: None,
                validate_worktree_sources=lambda *_args, **_kwargs: None,
                validate_catalog_freshness=lambda _root: None,
                canonical_hash=lambda value: "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            )
            with mock.patch.object(module.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=json.dumps(result), stderr="")), \
                 mock.patch.object(module, "_validator", return_value=validator), \
                 mock.patch.object(sys, "argv", ["prepare", "--repository-root", str(root), "--request-id", "request-1", "--query", "rules", "--required-module", "repository-rules", "--accept", "AGENTS.md=repository-rules", "--target-plan", "execution-plans/plan", "--output", str(output)]):
                self.assertEqual(0, module.main())
                freeze_path = output.with_name("knowledge-context.freeze.v1.json")
                freeze_path.unlink()
                self.assertEqual(0, module.main())
            document = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual("ready", document["preflight"]["status"])
            self.assertIn("context_sha256", document["preflight"])
            freeze = json.loads((output.parent / "knowledge-context.freeze.v1.json").read_text(encoding="utf-8"))
            self.assertEqual("jimuyun.vdd-knowledge-freeze.v1", freeze["schema_version"])
            self.assertEqual("test-policy-v2", freeze["policy_revision"])

    def test_prepare_freeze_receipt_uses_refreshed_context_decisions(self) -> None:
        module = load_prepare()
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "knowledge/catalogs").mkdir(parents=True)
            (root / "knowledge/catalogs/repository-knowledge-catalog.v2.json").write_text(
                json.dumps({"source_snapshot": {"ref": "refs/heads/main", "commit": "a" * 40}}), encoding="utf-8"
            )
            (root / "knowledge/policies").mkdir(parents=True)
            (root / "knowledge/policies/consumer-policies.v2.json").write_text(
                json.dumps({"policy_revision": "test-policy-v2"}), encoding="utf-8"
            )
            output = root / "execution-plans/plan/knowledge-context.v1.json"
            locator_result = {
                "schema_version": "jimuyun.knowledge-locator-result.v1", "request_id": "request-1",
                "snapshot": {"ref": "refs/heads/main", "commit": "a" * 40}, "status": "matched",
                "source_snapshot_id": "old-snapshot",
                "candidates": [{"path": "AGENTS.md", "source_sha256": "old"}],
            }
            calls = iter(["candidate_worktree_source_hash_mismatch", None])

            def refresh(payload, _root):
                refreshed = json.loads(json.dumps(payload))
                refreshed["locator_result"]["source_snapshot_id"] = "new-snapshot"
                refreshed["locator_result"]["candidates"][0]["source_sha256"] = "new"
                refreshed["decisions"][0]["candidate"]["source_sha256"] = "new"
                refreshed["result_sha256"] = validator.canonical_hash(refreshed["locator_result"])
                refreshed["source_refresh"] = {"status": "refreshed"}
                return refreshed

            validator = SimpleNamespace(
                validate_context=lambda *_args, **_kwargs: None,
                validate_worktree_sources=lambda *_args, **_kwargs: next(calls),
                validate_catalog_freshness=lambda _root: None,
                refresh_context_read_set=refresh,
                canonical_hash=lambda value: "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            )
            with mock.patch.object(module.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=json.dumps(locator_result), stderr="")), \
                 mock.patch.object(module, "_validator", return_value=validator), \
                 mock.patch.object(sys, "argv", ["prepare", "--repository-root", str(root), "--request-id", "request-1", "--query", "rules", "--accept", "AGENTS.md=repository-rules", "--target-plan", "execution-plans/plan", "--output", str(output)]):
                self.assertEqual(0, module.main())
            document = json.loads(output.read_text(encoding="utf-8"))
            freeze = json.loads(output.with_name("knowledge-context.freeze.v1.json").read_text(encoding="utf-8"))
            self.assertEqual("new", document["decisions"][0]["candidate"]["source_sha256"])
            self.assertEqual("new", freeze["accepted"][0]["source_sha256"])
            self.assertEqual("new-snapshot", freeze["source_snapshot_id"])

    def test_blocked_preflight_does_not_publish_fixed_output_files(self) -> None:
        module = load_prepare()
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            catalog = root / "knowledge/catalogs/repository-knowledge-catalog.v2.json"
            catalog.parent.mkdir(parents=True)
            catalog.write_text(json.dumps({"source_snapshot": {"ref": "refs/heads/main", "commit": "a" * 40}}), encoding="utf-8")
            policy = root / "knowledge/policies/consumer-policies.v2.json"
            policy.parent.mkdir(parents=True)
            policy.write_text(json.dumps({"policy_revision": "test-policy-v2"}), encoding="utf-8")
            output = root / "execution-plans/plan/knowledge-context.v1.json"
            result = {
                "schema_version": "jimuyun.knowledge-locator-result.v1", "request_id": "request-1",
                "snapshot": {"ref": "refs/heads/main", "commit": "a" * 40}, "status": "matched",
                "candidates": [{"path": "AGENTS.md", "source_sha256": "b" * 64}],
            }
            validator = SimpleNamespace(
                validate_context=lambda *_args, **_kwargs: "required_modules_unsatisfied",
                validate_catalog_freshness=lambda _root: None,
                canonical_hash=lambda value: "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            )
            with mock.patch.object(module.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=json.dumps(result), stderr="")), mock.patch.object(module, "_validator", return_value=validator), mock.patch.object(sys, "argv", ["prepare", "--repository-root", str(root), "--request-id", "request-1", "--query", "rules", "--required-module", "repository-rules", "--target-plan", "execution-plans/plan", "--output", str(output)]):
                self.assertEqual(2, module.main())
            self.assertFalse(output.exists())
            self.assertFalse(output.with_name("knowledge-context.freeze.v1.json").exists())

    def test_prepare_rejects_output_outside_explicit_target_plan(self) -> None:
        module = load_prepare()
        with mock.patch.object(sys, "argv", [
            "prepare", "--request-id", "request-1", "--query", "rules",
            "--target-plan", "execution-plans/plan-a",
            "--output", "execution-plans/plan-b/knowledge-context.v1.json",
        ]):
            with self.assertRaisesRegex(SystemExit, "target execution-plan"):
                module.main()


if __name__ == "__main__":
    unittest.main()
