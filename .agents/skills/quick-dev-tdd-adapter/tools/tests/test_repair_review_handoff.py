from __future__ import annotations

import importlib.util
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = SKILL_ROOT.parents[2]
HANDOFF_PATH = SKILL_ROOT / "tools" / "build_repair_review_handoff.py"
ACCEPTANCE_SCRIPTS = REPOSITORY_ROOT / ".agents" / "skills" / "run-refactor-implementation-acceptance" / "scripts"


def load_handoff_module():
    spec = importlib.util.spec_from_file_location("repair_review_handoff", HANDOFF_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RepairReviewHandoffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        (self.root / "execution-plans" / "example").mkdir(parents=True)
        (self.root / "src").mkdir()
        (self.root / "tests").mkdir()
        (self.root / "logs").mkdir()
        (self.root / "src" / "producer.py").write_text("def shared_route():\n    pass\n", encoding="utf-8", newline="\n")
        (self.root / "src" / "consumer.py").write_text("shared_route()\n", encoding="utf-8", newline="\n")
        (self.root / "tests" / "test_route.py").write_text("shared_route()\n", encoding="utf-8", newline="\n")
        baseline = {
            "schemaVersion": "acceptance-baseline-content-manifest.v1",
            "status": "complete", "coverageGaps": [], "authorizes": [], "files": [],
        }
        candidate = {
            "schemaVersion": "acceptance-candidate-content-manifest.v1",
            "status": "complete", "coverageGaps": [], "authorizes": [],
            "files": [
                {
                    "change_type": "untracked", "roles": ["implementation"],
                    "baseline_path": None, "baseline_sha256": None,
                    "candidate_path": relative,
                    "candidate_sha256": self._hash((self.root / relative).read_bytes()),
                    "inclusion_reason": "repair candidate",
                }
                for relative in ("src/producer.py", "src/consumer.py")
            ],
        }
        (self.root / "logs" / "baseline.json").write_text(json.dumps(baseline), encoding="utf-8", newline="\n")
        (self.root / "logs" / "candidate.json").write_text(json.dumps(candidate), encoding="utf-8", newline="\n")
        self.receipt = self.root / "logs" / "composition.json"
        sys.path.insert(0, str(ACCEPTANCE_SCRIPTS))
        from acceptance_core import canonical_hash

        command = {
            "id": "route-composition",
            "executable": sys.executable,
            "argv": [
                "-c",
                "print('ok')",
                "src/producer.py",
                "src/consumer.py",
                "tests/test_route.py",
            ],
            "cwd": ".",
            "timeout_seconds": 10,
            "shell": False,
            "allowed_write_roots": [],
            "forbidden_write_roots": [],
            "registry_hash": "",
            "environment_allowlist": [],
            "typed_placeholders": {},
            "placeholder_values": {},
        }
        material = {
            "schemaVersion": "acceptance-command-registry.v1",
            "commands": [{key: value for key, value in command.items() if key != "registry_hash"}],
        }
        registry_hash = canonical_hash(material)
        command["registry_hash"] = registry_hash
        (self.root / "logs" / "command-registry.json").write_text(json.dumps({
            "schemaVersion": "acceptance-command-registry.v1",
            "commands": [command],
            "registryHash": registry_hash,
        }), encoding="utf-8", newline="\n")
        from execution_control import run_controlled_command

        receipt = run_controlled_command(
            self.root,
            command,
            input_paths=[
                "src/producer.py",
                "src/consumer.py",
                "tests/test_route.py",
            ],
        )
        self.receipt.write_text(
            json.dumps(receipt), encoding="utf-8", newline="\n"
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _hash(value: bytes) -> str:
        return "sha256:" + hashlib.sha256(value).hexdigest()

    def input(self) -> dict:
        return {
            "schemaVersion": "quick-dev-repair-review-handoff-input.v1",
            "repositoryRoot": str(self.root),
            "acceptanceTarget": "execution-plans/example",
            "lineageFamilyId": "ria-stable-family",
            "semanticRoundsConsumed": 0,
            "predecessorRun": None,
            "baselineManifestPath": "logs/baseline.json",
            "baselineManifestHash": self._hash((self.root / "logs" / "baseline.json").read_bytes()),
            "candidateManifestPath": "logs/candidate.json",
            "candidateManifestHash": self._hash((self.root / "logs" / "candidate.json").read_bytes()),
            "changedFiles": ["src/producer.py", "src/consumer.py"],
            "directConsumers": ["src/consumer.py"],
            "targetedTests": ["tests/test_route.py"],
            "validationRefs": ["logs/composition.json"],
            "rootCauseInventories": [{
                "inventoryId": "shared-route-callsites",
                "searchTerm": "shared_route",
                "searchRoots": ["src"],
                "addressedPaths": ["src/producer.py", "src/consumer.py"],
                "exclusions": [],
            }],
            "compositionChecks": [{
                "checkId": "route-composition",
                "producerPaths": ["src/producer.py"],
                "consumerPaths": ["src/consumer.py"],
                "receiptPath": "logs/composition.json",
                "commandRegistryPath": "logs/command-registry.json",
            }],
            "novelP0P1FindingIds": [],
            "authorityGraphChanged": False,
            "highRiskBoundaryChanged": False,
            "authorizes": [],
        }

    def test_handoff_is_consumed_by_acceptance_without_translation(self) -> None:
        module = load_handoff_module()
        request = module.build_handoff(self.input())
        from repair_completeness import audit_repair_completeness

        result = audit_repair_completeness(request)
        self.assertEqual("passed", result["status"])
        self.assertEqual("execution-plans/example", result["acceptanceTarget"])
        self.assertEqual([], result["authorizes"])

    def test_handoff_requires_direct_consumers_and_does_not_choose_a_route(self) -> None:
        module = load_handoff_module()
        value = self.input()
        value["directConsumers"] = []
        with self.assertRaisesRegex(module.HandoffError, "direct consumer"):
            module.build_handoff(value)
        produced = module.build_handoff(self.input())
        self.assertNotIn("routeKind", produced)
        self.assertNotIn("nextFullReviewRound", produced)

    def test_handoff_allows_a_deleted_changed_path_as_a_tombstone(self) -> None:
        module = load_handoff_module()
        value = self.input()
        value["changedFiles"] = ["src/deleted-route.py"]
        produced = module.build_handoff(value)
        self.assertEqual(["src/deleted-route.py"], produced["changedPaths"])


if __name__ == "__main__":
    unittest.main()
