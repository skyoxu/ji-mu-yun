from __future__ import annotations

import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "quick_dev_input_router.py"
REPOSITORY_ROOT = MODULE_PATH.parents[4]
SPEC = importlib.util.spec_from_file_location("quick_dev_input_router", MODULE_PATH)
assert SPEC and SPEC.loader
router = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(router)


def normal_facts() -> dict:
    return {
        **{name: False for name in router.model_routing.ARCHITECTURAL_FACTS},
        **{name: False for name in router.model_routing.COMPLEX_FACTS},
        "production_write_roots": 1,
        "matching_test_roots": 1,
        "deterministic_transform": False,
        "behavior_fully_specified": True,
        "introduces_contract": False,
        "introduces_dependency": False,
        "unknown_facts": [],
        "contradictory_facts": [],
    }


class QuickDevInputRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        (self.repo / "execution-plans").mkdir(parents=True)
        schema_root = self.repo / ".agents/skills/quick-dev-tdd-adapter/schemas"
        schema_root.mkdir(parents=True)
        for name in (
            "implementation-contract.v1.schema.json",
            "plan-owned-implementation-contract.v1.schema.json",
            "plan-owned-implementation-contract.v2.schema.json",
        ):
            (schema_root / name).write_text(
                (REPOSITORY_ROOT / ".agents/skills/quick-dev-tdd-adapter/schemas" / name).read_text(
                    encoding="utf-8"
                ),
                encoding="utf-8",
            )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def compact_plan(self, name: str = "compact") -> Path:
        plan = self.repo / "execution-plans" / name
        (plan / "tools").mkdir(parents=True)
        (plan / "00-index.md").write_text("# Compact\n", encoding="utf-8")
        (plan / "95-implementation-evolution-and-completion-report.md").write_text(
            "# Completion\n", encoding="utf-8"
        )
        (plan / "tools" / "validate_plan.py").write_text(
            "import json\n"
            f"def validate():\n    return {{'status': 'pass', 'validated_state': 'implementation-authorized', 'plan_id': '{name}'}}\n\n"
            "def main():\n    print(json.dumps(validate()))\n    return 0\n\n"
            "if __name__ == '__main__':\n    raise SystemExit(main())\n",
            encoding="utf-8",
        )
        (plan / "tools" / "validate_implementation.py").write_text(
            "def main():\n    return 0\n", encoding="utf-8"
        )
        documents = {
            "plan-state.v1.json": {
                "schema_version": "vdd.plan-state.v1",
                "plan_id": name,
                "profile": "self-hosted",
                "state": "implementation-authorized",
                "state_owner": "terminal-validator",
                "slices": [{"id": "S1", "status": "pending", "depends_on": []}],
                "authorizes": ["implementation-authorized"],
            },
            "requirements.v1.json": {
                "schema_version": "vdd.requirements.v1",
                "plan_id": name,
                "profile": "self-hosted",
                "requirements": [{"id": "R1"}],
                "acceptance": [{"id": "A1"}],
                "slices": [{"id": "S1"}],
                "authorizes": [],
            },
            "baseline-and-scope.v1.json": {
                "schema_version": "vdd.scoped-dirty-worktree-baseline.v1",
                "plan_id": name,
                "git": {"head": "0" * 40},
                "scope_roots": ["src/"],
                "authorizes": [],
            },
        }
        for filename, value in documents.items():
            (plan / filename).write_text(json.dumps(value), encoding="utf-8")
        return plan

    def test_routes_standalone_strict_and_compact_inputs(self) -> None:
        requirement = self.repo / "requirement.md"
        requirement.write_text("# Requirement\n", encoding="utf-8")
        standalone = router.route_input(self.repo, requirement, normal_facts())
        self.assertEqual("standalone_requirement", standalone["lane"])
        self.assertEqual("normal", standalone["modelDecision"]["classification"])
        self.assertEqual("observe_only", standalone["modelDecision"]["status"])

        strict = self.repo / "execution-plans" / "strict"
        strict.mkdir()
        (strict / "implementation-contract.v1.json").write_text(
            (
                REPOSITORY_ROOT
                / "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/implementation-contract.v1.json"
            ).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        self.assertEqual(
            "strict_tdd_plan",
            router.route_input(self.repo, strict, normal_facts())["lane"],
        )

        compact = self.compact_plan()
        result = router.route_input(self.repo, compact, normal_facts())
        self.assertEqual("verified_compact_vdd", result["lane"])
        self.assertEqual("direct-plan-implementation", result["backend"])
        self.assertFalse((compact / "implementation-contract.v1.json").exists())

    def test_damaged_contract_never_downgrades_to_compact(self) -> None:
        plan = self.compact_plan("damaged")
        (plan / "implementation-contract.v1.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(router.InputRoutingError, "schema-invalid"):
            router.route_input(self.repo, plan, normal_facts())

    def test_routes_schema_valid_plan_owned_contract_to_strict_adapter(self) -> None:
        plan = self.repo / "execution-plans" / "plan-owned"
        plan.mkdir()
        contract = {
            "schema_version": "example.implementation-contract.v1",
            "plan_id": "plan-owned",
            "profile": "resumable",
            "command_registry": "command-registry.v1.json",
            "backend": {"hidden_state": False},
            "protocol_artifacts": {
                "context_layout": "context/<capsule-id>",
                "attempt_layout": "attempts/<attempt-id>",
            },
            "authority": {"authority_manifest": "authority-manifest.v1.json"},
            "slices": [{
                "slice_id": "EXAMPLE-S0",
                "title": "Example",
                "requirement_ids": ["EXAMPLE-001"],
                "acceptance_ids": ["EXAMPLE-ACC-001"],
                "source_refs": ["requirements.md"],
                "depends_on": [],
                "allowed_changes": {"production": ["src/example.py"], "tests": ["tests/test_example.py"], "documentation": []},
                "execution_snapshot_paths": ["src/example.py"],
                "forbidden_changes": ["runtime/phase-a/**"],
                "execution_read_set": ["AGENTS.md"],
                "dependency_closure": ["requirements.md"],
                "tdd": {
                    "red": {"command_id": "example-red", "test_selector": "test_example", "expected_exit": "nonzero", "expected_failure_family": "example", "expected_failure_ids": ["EXAMPLE-RED"]},
                    "green": {"command_id": "example-green", "expected_exit": "zero"},
                    "refactor": {"invocations": [{"command_id": "example-green", "expected_exit": "zero"}]},
                },
                "post_refactor_command_id": "example-predicate",
                "exit_predicate": "slice-ready",
                "recovery": "Revert the bounded candidate and rerun RED.",
            }],
        }
        (plan / "implementation-contract.v1.json").write_text(
            json.dumps(contract), encoding="utf-8"
        )

        result = router.route_input(self.repo, plan, normal_facts())

        self.assertEqual("strict_tdd_plan", result["lane"])
        self.assertEqual("quick-dev-tdd-adapter", result["backend"])

    def test_routes_schema_valid_plan_owned_v2_contract_to_strict_adapter(self) -> None:
        plan = self.repo / "execution-plans" / "plan-owned-v2"
        plan.mkdir()
        contract = {
            "schema_version": "plan-owned-v2.implementation-contract.v2",
            "plan_id": "plan-owned-v2",
            "profile": "self-hosted",
            "command_registry": "command-registry.v1.json",
            "backend": {"hidden_state": False},
            "protocol_artifacts": {
                "context_layout": "context/<capsule-id>",
                "attempt_layout": "attempts/<attempt-id>",
            },
            "authority": {"authority_manifest": "authority-manifest.v1.json"},
            "slices": [{
                "slice_id": "S3",
                "title": "Example v2",
                "requirement_ids": ["R1"],
                "acceptance_ids": ["A1"],
                "source_refs": ["requirements.md"],
                "depends_on": [],
                "allowed_changes": {"production": ["src/example.py"], "tests": ["tests/test_example.py"], "documentation": []},
                "execution_snapshot_paths": ["src/example.py"],
                "forbidden_changes": [],
                "execution_read_set": ["requirements.md"],
                "dependency_closure": ["requirements.md"],
                "tdd": {
                    "red": {"test_selector": "test_example", "expected_failure_ids": ["RED-1"]},
                    "green": {"command_id": "green", "expected_exit": "zero"},
                    "refactor": {"invocations": [{"command_id": "green", "expected_exit": "zero"}]},
                },
                "post_refactor_command_id": "predicate",
                "exit_predicate": "slice-ready",
                "recovery": "Replay the same binding.",
            }],
        }
        (plan / "implementation-contract.v1.json").write_text(json.dumps(contract), encoding="utf-8")
        result = router.route_input(self.repo, plan, normal_facts())
        self.assertEqual("strict_tdd_plan", result["lane"])
        self.assertEqual("quick-dev-tdd-adapter", result["backend"])

    def test_rejects_unknown_plan_owned_contract_version(self) -> None:
        plan = self.repo / "execution-plans" / "plan-owned-v3"
        plan.mkdir()
        (plan / "implementation-contract.v1.json").write_text(
            json.dumps({"schema_version": "plan-owned-v3.implementation-contract.v3"}),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(router.InputRoutingError, "unsupported schema_version"):
            router.route_input(self.repo, plan, normal_facts())

    def test_rejects_malformed_plan_owned_v2_contract(self) -> None:
        plan = self.repo / "execution-plans" / "malformed-v2"
        plan.mkdir()
        (plan / "implementation-contract.v1.json").write_text(
            json.dumps({"schema_version": "malformed-v2.implementation-contract.v2"}),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(router.InputRoutingError, "schema-invalid"):
            router.route_input(self.repo, plan, normal_facts())

    def test_callers_cannot_consume_another_lane(self) -> None:
        requirement = self.repo / "requirement.md"
        requirement.write_text("# Requirement\n", encoding="utf-8")
        standalone = router.route_input(self.repo, requirement, normal_facts())
        router.enforce_caller_lane(standalone, "bmad-quick-dev")
        with self.assertRaisesRegex(
            router.InputRoutingError,
            "handoff required to ordinary-quick-dev",
        ):
            router.enforce_caller_lane(standalone, "quick-dev-tdd-adapter")

        strict = self.repo / "execution-plans" / "strict-caller"
        strict.mkdir()
        (strict / "implementation-contract.v1.json").write_text(
            (
                REPOSITORY_ROOT
                / "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/implementation-contract.v1.json"
            ).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        strict_route = router.route_input(self.repo, strict, normal_facts())
        router.enforce_caller_lane(strict_route, "quick-dev-tdd-adapter")
        with self.assertRaisesRegex(
            router.InputRoutingError,
            "handoff required to quick-dev-tdd-adapter",
        ):
            router.enforce_caller_lane(strict_route, "bmad-quick-dev")

    def test_unknown_caller_fails_closed(self) -> None:
        with self.assertRaisesRegex(router.InputRoutingError, "caller is unknown"):
            router.enforce_caller_lane({"lane": "strict_tdd_plan"}, "unknown")

    def test_cli_requires_explicit_caller(self) -> None:
        requirement = self.repo / "requirement.md"
        requirement.write_text("# Requirement\n", encoding="utf-8")
        facts = self.repo / "facts.json"
        facts.write_text(json.dumps(normal_facts()), encoding="utf-8")
        with redirect_stderr(io.StringIO()):
            with self.assertRaisesRegex(SystemExit, "2"):
                router.main(
                    [
                        "--repository-root",
                        str(self.repo),
                        "--input",
                        str(requirement),
                        "--facts",
                        str(facts),
                    ]
                )

    def test_standalone_and_compact_inputs_must_be_readable_and_structural(self) -> None:
        empty = self.repo / "empty.md"
        empty.write_text(" \n", encoding="utf-8")
        with self.assertRaisesRegex(router.InputRoutingError, "must not be empty"):
            router.route_input(self.repo, empty, normal_facts())
        binary = self.repo / "binary.md"
        binary.write_bytes(b"\xff\xfe")
        with self.assertRaisesRegex(router.InputRoutingError, "readable UTF-8"):
            router.route_input(self.repo, binary, normal_facts())
        compact = self.compact_plan("fake-validator")
        (compact / "tools" / "validate_plan.py").write_text("# comment only\n", encoding="utf-8")
        with self.assertRaisesRegex(router.InputRoutingError, "entrypoint"):
            router.route_input(self.repo, compact, normal_facts())

    def test_contract_free_incomplete_plan_fails_closed(self) -> None:
        plan = self.repo / "execution-plans" / "incomplete"
        plan.mkdir()
        with self.assertRaisesRegex(router.InputRoutingError, "not a verified compact"):
            router.route_input(self.repo, plan, normal_facts())

    def test_existing_compact_plans_have_stable_direct_lane(self) -> None:
        for name in (
            "2026-08-01-refactor-acceptance-toolchain-compact-vdd",
            "2026-08-01-workflow-model-routing-control-plane",
        ):
            result = router.route_input(
                REPOSITORY_ROOT,
                REPOSITORY_ROOT / "execution-plans" / name,
                normal_facts(),
            )
            self.assertEqual("verified_compact_vdd", result["lane"])
            self.assertEqual("direct-plan-implementation", result["backend"])


if __name__ == "__main__":
    unittest.main()
