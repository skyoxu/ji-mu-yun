from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
import unittest


TOOLS = Path(__file__).resolve().parents[1]
PLAN_ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import validate_all  # noqa: E402
import validate_plan  # noqa: E402


def _load(relative: str) -> dict[str, object]:
    return validate_plan.strict_load(PLAN_ROOT / relative)


def _rule_ids(findings: list[dict[str, str]]) -> set[str]:
    return {item["rule_id"] for item in findings}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_quick_dev_validator():
    path = PLAN_ROOT.parents[1] / ".agents" / "skills" / "quick-dev-tdd-adapter" / "tools" / "validate_adapter_contract.py"
    spec = importlib.util.spec_from_file_location("quick_dev_adapter_contract_validator", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Quick Dev adapter contract validator is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StrictJsonTests(unittest.TestCase):
    def test_duplicate_json_key_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "duplicate.json"
            path.write_text('{"case_id":"one","case_id":"two"}\n', encoding="utf-8", newline="\n")
            with self.assertRaises(validate_plan.StrictJsonError):
                validate_plan.strict_load(path)


class CoverageTests(unittest.TestCase):
    def test_missing_requirement_coverage_is_rejected(self) -> None:
        contract = copy.deepcopy(_load("implementation-contract.v1.json"))
        contract["slices"][-1]["requirement_ids"] = []
        text = (PLAN_ROOT / "01-requirements-and-acceptance.md").read_text(encoding="utf-8")
        findings = validate_plan.validate_requirement_coverage(text, contract)
        self.assertIn("KWI-PLAN-REQUIREMENT-COVERAGE", _rule_ids(findings))

    def test_invalid_slice_dependency_is_rejected(self) -> None:
        contract = copy.deepcopy(_load("implementation-contract.v1.json"))
        contract["slices"][4]["depends_on"] = ["RMAP-S2"]
        findings = validate_plan.validate_slices(contract, validate_plan.REPOSITORY_ROOT)
        self.assertIn("KWI-PLAN-SLICE-DEPENDENCY", _rule_ids(findings))

    def test_quick_dev_contract_command_is_plan_bound(self) -> None:
        registry = copy.deepcopy(_load("command-registry.v1.json"))
        contract = _load("implementation-contract.v1.json")
        command = next(item for item in registry["commands"] if item["id"] == "quick-dev-contract")
        command["argv"] = command["argv"][:-1]
        findings = validate_plan.validate_commands(registry, contract)
        self.assertIn("KWI-PLAN-QUICK-CONTRACT-COMMAND", _rule_ids(findings))

    def test_terminal_preflight_command_must_fit_bootstrap_timeout(self) -> None:
        registry = copy.deepcopy(_load("command-registry.v1.json"))
        contract = _load("implementation-contract.v1.json")
        command = next(item for item in registry["commands"] if item["id"] == "knowledge-workflow-terminal")
        command["timeout_seconds"] = 901
        findings = validate_plan.validate_commands(registry, contract)
        self.assertIn("KWI-PLAN-BOOTSTRAP-PREFLIGHT-TIMEOUT", _rule_ids(findings))

    def test_quick_dev_adapter_boundary_is_required(self) -> None:
        contract = copy.deepcopy(_load("implementation-contract.v1.json"))
        contract["backend"]["hidden_state"] = True
        findings = validate_plan.validate_slices(contract, validate_plan.REPOSITORY_ROOT)
        self.assertIn("KWI-PLAN-QUICK-BACKEND", _rule_ids(findings))

    def test_current_contract_satisfies_quick_dev_adapter_validator(self) -> None:
        contract = _load("implementation-contract.v1.json")
        self.assertEqual([], _load_quick_dev_validator().validate(contract))

    def test_rmap_s2_requires_index_publication_guard(self) -> None:
        contract = copy.deepcopy(_load("implementation-contract.v1.json"))
        contract["slices"][2]["tdd"]["refactor"]["invocations"] = [
            {"command_id": "locator-full-suite", "expected_exit": "zero"}
        ]
        findings = validate_plan.validate_slices(contract, validate_plan.REPOSITORY_ROOT)
        self.assertIn("KWI-PLAN-INDEX-GUARD", _rule_ids(findings))

    def test_index_publication_command_selector_is_fixed(self) -> None:
        registry = copy.deepcopy(_load("command-registry.v1.json"))
        contract = _load("implementation-contract.v1.json")
        command = next(item for item in registry["commands"] if item["id"] == "index-publication-test")
        command["argv"][-1] = "test_wrong_selector"
        findings = validate_plan.validate_commands(registry, contract)
        self.assertIn("KWI-PLAN-INDEX-GUARD-COMMAND", _rule_ids(findings))


class ProtocolFixtureTests(unittest.TestCase):
    def test_llm_owned_envelope_case_is_fail_closed(self) -> None:
        fixtures = copy.deepcopy(_load("fixtures/protocol-cases.v1.json"))
        case = next(item for item in fixtures["cases"] if item["case_id"] == "llm-owned-envelope")
        case["expected"] = "matched"
        findings = validate_plan.validate_protocol_fixtures(fixtures)
        self.assertIn("KWI-PLAN-LLM-ENVELOPE", _rule_ids(findings))

    def test_quick_dev_scope_expansion_routes_to_vdd_repair(self) -> None:
        fixtures = copy.deepcopy(_load("fixtures/protocol-cases.v1.json"))
        case = next(item for item in fixtures["cases"] if item["case_id"] == "quick-dev-scope-expansion")
        case["expected"] = "continue"
        findings = validate_plan.validate_protocol_fixtures(fixtures)
        self.assertIn("KWI-PLAN-QUICK-SCOPE", _rule_ids(findings))

    def test_high_score_wrong_domain_does_not_count(self) -> None:
        fixtures = copy.deepcopy(_load("fixtures/protocol-cases.v1.json"))
        case = next(item for item in fixtures["cases"] if item["case_id"] == "high-score-wrong-domain")
        case["expected"] = "accepted"
        findings = validate_plan.validate_protocol_fixtures(fixtures)
        self.assertIn("KWI-PLAN-CONSUMPTION-WRONG-DOMAIN", _rule_ids(findings))

    def test_keyword_match_without_specificity_does_not_count(self) -> None:
        fixtures = copy.deepcopy(_load("fixtures/protocol-cases.v1.json"))
        case = next(item for item in fixtures["cases"] if item["case_id"] == "keyword-match-insufficient-specificity")
        case["semantic_fit"] = True
        findings = validate_plan.validate_protocol_fixtures(fixtures)
        self.assertIn("KWI-PLAN-CONSUMPTION-SPECIFICITY", _rule_ids(findings))

    def test_all_rejected_required_module_remains_uncovered(self) -> None:
        fixtures = copy.deepcopy(_load("fixtures/protocol-cases.v1.json"))
        case = next(item for item in fixtures["cases"] if item["case_id"] == "all-candidates-rejected")
        case["expected"] = "plan-ready"
        findings = validate_plan.validate_protocol_fixtures(fixtures)
        self.assertIn("KWI-PLAN-CONSUMPTION-ALL-REJECTED", _rule_ids(findings))

    def test_index_lock_requires_complete_owner_identity(self) -> None:
        fixtures = copy.deepcopy(_load("fixtures/protocol-cases.v1.json"))
        case = next(item for item in fixtures["cases"] if item["case_id"] == "index-concurrent-owner-conflict")
        case["lock_owner_covers"].remove("process_creation_identity")
        findings = validate_plan.validate_protocol_fixtures(fixtures)
        self.assertIn("KWI-PLAN-INDEX-LOCK", _rule_ids(findings))

    def test_unvalidated_staging_cannot_publish(self) -> None:
        fixtures = copy.deepcopy(_load("fixtures/protocol-cases.v1.json"))
        case = next(item for item in fixtures["cases"] if item["case_id"] == "index-unvalidated-staging-publish")
        case["expected"] = "published"
        findings = validate_plan.validate_protocol_fixtures(fixtures)
        self.assertIn("KWI-PLAN-INDEX-STAGING", _rule_ids(findings))

    def test_index_pointer_updates_must_be_atomic(self) -> None:
        fixtures = copy.deepcopy(_load("fixtures/protocol-cases.v1.json"))
        case = next(item for item in fixtures["cases"] if item["case_id"] == "index-non-atomic-pointer-update")
        case["expected"] = "published"
        findings = validate_plan.validate_protocol_fixtures(fixtures)
        self.assertIn("KWI-PLAN-INDEX-ATOMIC", _rule_ids(findings))

    def test_failed_index_build_preserves_lkg(self) -> None:
        fixtures = copy.deepcopy(_load("fixtures/protocol-cases.v1.json"))
        case = next(item for item in fixtures["cases"] if item["case_id"] == "index-failed-build-preserves-lkg")
        case["pointer_advanced"] = True
        findings = validate_plan.validate_protocol_fixtures(fixtures)
        self.assertIn("KWI-PLAN-INDEX-LKG", _rule_ids(findings))


class AuthorityTests(unittest.TestCase):
    def test_upstream_index_and_requirement_ledger_are_required_authority(self) -> None:
        manifest = copy.deepcopy(_load("authority-manifest.v1.json"))
        manifest["sources"] = [
            item
            for item in manifest["sources"]
            if not item["path"].endswith("requirements-ledger.v1.json")
        ]
        findings = validate_plan.validate_authority(
            manifest,
            _load("plan-state.v1.json"),
            validate_plan.REPOSITORY_ROOT,
        )
        self.assertIn("KWI-PLAN-UPSTREAM-AUTHORITY", _rule_ids(findings))

    def test_successor_policy_reentry_is_consumed_and_lineage_bound(self) -> None:
        self.assertEqual([], validate_plan.validate_successor_reentry(validate_plan.REPOSITORY_ROOT))
        decision = json.loads(
            (validate_plan.REPOSITORY_ROOT / validate_plan.SUCCESSOR_POLICY_DECISION).read_text(encoding="utf-8")
        )
        decision["successorChangeId"] = "wrong-successor-change"
        findings = validate_plan.validate_successor_reentry(validate_plan.REPOSITORY_ROOT, decision)
        self.assertIn("KWI-PLAN-SUCCESSOR-REENTRY", _rule_ids(findings))


class MigrationFixtureTests(unittest.TestCase):
    def test_historical_migration_bytes_must_be_preserved(self) -> None:
        fixtures = copy.deepcopy(_load("fixtures/migration-cases.v1.json"))
        fixtures["cases"][0]["historical_bytes_mutated"] = True
        findings = validate_plan.validate_migration_fixtures(fixtures)
        self.assertIn("KWI-PLAN-MIGRATION-BYTES", _rule_ids(findings))


class PublicationTests(unittest.TestCase):
    def test_plan_ready_publication_updates_only_temporary_files(self) -> None:
        real_paths = [
            PLAN_ROOT / "plan-state.v1.json",
            PLAN_ROOT / "resume-state.v1.json",
            PLAN_ROOT / "00-index.md",
        ]
        before = {path: _sha(path) for path in real_paths}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for source in real_paths:
                shutil.copy2(source, root / source.name)
            state_path = root / "plan-state.v1.json"
            index_path = root / "00-index.md"
            state = validate_plan.strict_load(state_path)
            state["status"] = "draft"
            state["authorizes"] = []
            state["status_history"] = [
                {
                    "status": "draft",
                    "reason": "Temporary publication fixture.",
                    "evidence": [],
                }
            ]
            state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8", newline="\n")
            index_text = index_path.read_text(encoding="utf-8")
            index_text = re.sub(r"^- Status: [^\r\n]+$", "- Status: draft", index_text, count=1, flags=re.MULTILINE)
            index_path.write_text(index_text, encoding="utf-8", newline="\n")
            self.assertTrue(validate_plan.publish_plan_ready_files(root))
            published = validate_plan.strict_load(state_path)
            self.assertEqual("plan-ready", published["status"])
            self.assertEqual(["plan-ready"], published["authorizes"])
            self.assertIn("- Status: plan-ready", index_path.read_text(encoding="utf-8"))
        self.assertEqual(before, {path: _sha(path) for path in real_paths})


class FreshnessIdentityTests(unittest.TestCase):
    def test_lifecycle_projection_is_not_candidate_implementation_input(self) -> None:
        self.assertFalse(validate_all._normative_worktree_path(
            "execution-plans/2026-07-26-knowledge-locator-workflow-integration/00-index.md"
        ))

    def test_candidate_identity_and_snapshot_are_complete(self) -> None:
        identity = validate_all.current_candidate_identity("RMAP-S6")
        required_identity = {
            "head",
            "index_tree",
            "tracked_diff_hash",
            "untracked_manifest_hash",
            "contract_hash",
            "command_registry_hash",
            "validator_hash",
            "authority_manifest_hash",
            "candidate_worktree_hash",
            "plan_hash",
        }
        self.assertTrue(required_identity.issubset(identity))
        self.assertTrue(all(isinstance(identity[key], str) and identity[key] for key in required_identity))
        snapshot = validate_all.slice_validation_snapshot("RMAP-S6")
        self.assertEqual(set(validate_all.SNAPSHOT_ROOTS), set(snapshot))
        self.assertTrue(all(isinstance(value, str) and value for value in snapshot.values()))


class WholeDirectoryTests(unittest.TestCase):
    def test_current_directory_is_valid(self) -> None:
        result = validate_plan.validate_directory()
        self.assertEqual("pass", result["status"], result["findings"])


if __name__ == "__main__":
    unittest.main()
