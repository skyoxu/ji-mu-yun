from __future__ import annotations

import json
import hashlib
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))


class RepairCompletenessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        (self.root / "src").mkdir()
        (self.root / "tests").mkdir()
        (self.root / "logs").mkdir()
        (self.root / "execution-plans" / "example").mkdir(parents=True)
        (self.root / "src" / "producer.py").write_text(
            "def shared_route():\n    return 'ok'\n",
            encoding="utf-8",
            newline="\n",
        )
        (self.root / "src" / "consumer.py").write_text(
            "from producer import shared_route\nshared_route()\n",
            encoding="utf-8",
            newline="\n",
        )
        (self.root / "tests" / "test_consumer.py").write_text(
            "from pathlib import Path\nassert Path('src/consumer.py').is_file()\n",
            encoding="utf-8",
            newline="\n",
        )
        self.check_id = "producer-consumer-check"
        self.receipt_path = self.root / "logs" / "composition.json"
        self.registry_path = self.root / "logs" / "command-registry.json"
        self.baseline_path = self.root / "logs" / "baseline.json"
        self.candidate_path = self.root / "logs" / "candidate.json"
        self._write_registry()
        self._write_manifests()
        self._write_receipt(0)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_bootstrap_loader_isolates_same_named_dependency_modules(self) -> None:
        import repair_completeness

        repository_root = SKILL_ROOT.parents[2]
        names = ("_control_plane", "knowledge_context")
        previous = {name: sys.modules.get(name) for name in names}
        collisions = {name: types.ModuleType(name) for name in names}
        sys.modules.update(collisions)
        try:
            bootstrap = repair_completeness._bootstrap_module(repository_root)
            self.assertTrue(callable(bootstrap.build_lineage_state))
            for name, collision in collisions.items():
                self.assertIs(collision, sys.modules[name])
        finally:
            for name, prior in previous.items():
                if prior is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = prior

    def test_copied_file_binds_source_and_candidate_bytes(self) -> None:
        from repair_completeness import _candidate_path_bindings

        bindings = _candidate_path_bindings(
            {
                "files": [
                    {
                        "change_type": "copied",
                        "baseline_path": "src/source.py",
                        "baseline_sha256": "sha256:" + "a" * 64,
                        "candidate_path": "src/copy.py",
                        "candidate_sha256": "sha256:" + "b" * 64,
                    }
                ]
            }
        )
        self.assertEqual("present", bindings["src/source.py"]["state"])
        self.assertEqual("present", bindings["src/copy.py"]["state"])

    def test_godot_callsites_and_nested_agent_authority_are_not_filtered(self) -> None:
        from repair_completeness import _derive_review_escalation, discover_callsites

        script = self.root / "src" / "route.gd"
        script.write_text("func shared_route():\n    pass\n", encoding="utf-8", newline="\n")
        matches = discover_callsites(self.root, "shared_route", ["src"])
        self.assertIn("src/route.gd", [item["path"] for item in matches])
        _novel, authority, _high_risk = _derive_review_escalation(
            self.root,
            "authority-family",
            0,
            None,
            ["nested/AGENTS.md"],
        )
        self.assertEqual(["nested/AGENTS.md"], authority)

    def test_adopted_lineage_accepts_legacy_change_id_at_current_head(self) -> None:
        import repair_completeness

        predecessor = self.root / "logs" / "legacy-round-3"
        predecessor.mkdir()
        manifest = {
            "reviewId": "legacy-review-r3",
            "changeId": "legacy-change-id",
            "fullReviewRound": 3,
            "inputHash": "sha256:" + "a" * 64,
            "predecessorRun": None,
        }
        (predecessor / "review-input.json").write_text(
            json.dumps(manifest), encoding="utf-8", newline="\n"
        )
        lineage = {
            "semanticRoundsConsumed": 3,
            "runs": [{
                "runDirectory": "logs/legacy-round-3",
                "reviewId": manifest["reviewId"],
                "changeId": manifest["changeId"],
                "fullReviewRound": 3,
                "inputHash": manifest["inputHash"],
            }],
        }
        module = types.SimpleNamespace(
            BootstrapError=ValueError,
            build_lineage_state=lambda *_args: lineage,
            ensure_within=lambda path, *_args: Path(path),
            read_json=lambda path: json.loads(Path(path).read_text(encoding="utf-8")),
            blocker_finding_lineage=lambda *_args: {},
        )

        with mock.patch.object(repair_completeness, "_bootstrap_module", return_value=module):
            novel, authority, high_risk = repair_completeness._derive_review_escalation(
                self.root,
                "ria-adopted-family",
                3,
                "logs/legacy-round-3",
                ["src/producer.py"],
            )

        self.assertEqual(([], [], []), (novel, authority, high_risk))

    def _write_receipt(self, exit_code: int) -> None:
        from acceptance_core import canonical_hash
        from execution_control import run_controlled_command

        receipt = run_controlled_command(
            self.root,
            self.command,
            input_paths=["src/producer.py", "src/consumer.py", "tests/test_consumer.py"],
        )
        if exit_code != 0:
            receipt["exitCode"] = exit_code
            receipt["processResult"]["exitCode"] = exit_code
            receipt["processResultHash"] = canonical_hash(receipt["processResult"])
        self.receipt_path.write_text(
            json.dumps(receipt, sort_keys=True), encoding="utf-8", newline="\n"
        )

    def _write_registry(self) -> None:
        from acceptance_core import canonical_hash

        command = {
            "id": self.check_id,
            "executable": sys.executable,
            "argv": ["tests/test_consumer.py"],
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
        self.registry_hash = canonical_hash(material)
        command["registry_hash"] = self.registry_hash
        self.command = command
        self.registry_path.write_text(json.dumps({
            "schemaVersion": "acceptance-command-registry.v1",
            "commands": [command],
            "registryHash": self.registry_hash,
        }), encoding="utf-8", newline="\n")

    @staticmethod
    def _hash_bytes(value: bytes) -> str:
        return "sha256:" + hashlib.sha256(value).hexdigest()

    def _write_manifests(self, *, deleted: tuple[str, bytes] | None = None) -> None:
        baseline_files = []
        candidate_files = []
        for relative in ("src/producer.py", "src/consumer.py"):
            digest = self._hash_bytes((self.root / relative).read_bytes())
            candidate_files.append({
                "change_type": "untracked",
                "roles": ["implementation"],
                "baseline_path": None,
                "baseline_sha256": None,
                "candidate_path": relative,
                "candidate_sha256": digest,
                "inclusion_reason": "repair candidate",
            })
        if deleted is not None:
            relative, content = deleted
            digest = self._hash_bytes(content)
            baseline_files.append({
                "path": relative,
                "sha256": digest,
                "roles": ["implementation"],
                "inclusion_reason": "repair baseline",
            })
            candidate_files.append({
                "change_type": "deleted",
                "roles": ["implementation"],
                "baseline_path": relative,
                "baseline_sha256": digest,
                "candidate_path": None,
                "candidate_sha256": None,
                "inclusion_reason": "deleted by repair",
            })
        baseline = {
            "schemaVersion": "acceptance-baseline-content-manifest.v1",
            "status": "complete", "coverageGaps": [], "authorizes": [],
            "files": baseline_files,
        }
        candidate = {
            "schemaVersion": "acceptance-candidate-content-manifest.v1",
            "status": "complete", "coverageGaps": [], "authorizes": [],
            "files": candidate_files,
        }
        self.baseline_path.write_text(json.dumps(baseline), encoding="utf-8", newline="\n")
        self.candidate_path.write_text(json.dumps(candidate), encoding="utf-8", newline="\n")

    def request(self) -> dict:
        return {
            "schemaVersion": "acceptance-repair-completeness-request.v1",
            "repositoryRoot": str(self.root),
            "acceptanceTarget": "execution-plans/example",
            "lineageFamilyId": "ria-stable-family",
            "semanticRoundsConsumed": 0,
            "predecessorRun": None,
            "baselineManifestPath": "logs/baseline.json",
            "baselineManifestHash": self._hash_bytes(self.baseline_path.read_bytes()),
            "candidateManifestPath": "logs/candidate.json",
            "candidateManifestHash": self._hash_bytes(self.candidate_path.read_bytes()),
            "changedPaths": ["src/producer.py", "src/consumer.py"],
            "directConsumers": ["src/consumer.py"],
            "targetedTests": ["tests/test_consumer.py"],
            "validationRefs": ["logs/composition.json"],
            "rootCauseInventories": [{
                "inventoryId": "shared-route-callsites",
                "searchTerm": "shared_route",
                "searchRoots": ["src"],
                "addressedPaths": ["src/producer.py", "src/consumer.py"],
                "exclusions": [],
            }],
            "compositionChecks": [{
                "checkId": self.check_id,
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

    def test_audit_binds_complete_inventory_and_successful_composition(self) -> None:
        import repair_completeness

        result = repair_completeness.audit_repair_completeness(self.request())
        self.assertEqual("passed", result["status"])
        self.assertEqual(["src"], result["rootCauseInventories"][0]["searchRoots"])
        self.assertEqual(2, len(result["rootCauseInventories"][0]["matches"]))
        self.assertEqual("src/consumer.py", result["directConsumers"][0]["path"])
        self.assertTrue(all(item["state"] == "present" for item in result["changedPathBindings"]))
        self.assertEqual([], result["authorizes"])

    def test_audit_binds_a_deleted_changed_path_as_a_tombstone(self) -> None:
        import repair_completeness

        request = self.request()
        self._write_manifests(deleted=("src/deleted-route.py", b"removed route\n"))
        request["baselineManifestHash"] = self._hash_bytes(self.baseline_path.read_bytes())
        request["candidateManifestHash"] = self._hash_bytes(self.candidate_path.read_bytes())
        request["changedPaths"].append("src/deleted-route.py")
        result = repair_completeness.audit_repair_completeness(request)
        tombstone = next(
            item for item in result["changedPathBindings"]
            if item["path"] == "src/deleted-route.py"
        )
        self.assertEqual(self._hash_bytes(b"removed route\n"), tombstone["sha256"])

    def test_audit_rejects_an_undisposed_sibling_callsite(self) -> None:
        import repair_completeness

        request = self.request()
        request["rootCauseInventories"][0]["addressedPaths"] = ["src/producer.py"]
        with self.assertRaisesRegex(repair_completeness.InputError, "dispose every"):
            repair_completeness.audit_repair_completeness(request)

    def test_audit_rejects_a_failed_composition_receipt(self) -> None:
        import repair_completeness

        self._write_receipt(1)
        with self.assertRaisesRegex(repair_completeness.InputError, "invalid or failed"):
            repair_completeness.audit_repair_completeness(self.request())

    def test_audit_rejects_self_composition(self) -> None:
        import repair_completeness

        request = self.request()
        request["compositionChecks"][0]["consumerPaths"] = ["src/producer.py"]
        request["directConsumers"] = ["src/producer.py"]
        with self.assertRaisesRegex(repair_completeness.InputError, "must be distinct"):
            repair_completeness.audit_repair_completeness(request)

    def test_audit_rejects_a_self_consistent_forged_stdout_receipt(self) -> None:
        import repair_completeness
        from acceptance_core import canonical_hash

        receipt = json.loads(self.receipt_path.read_text(encoding="utf-8"))
        receipt["processResult"]["stdout"] = "forged output"
        receipt["processResult"]["stdoutSha256"] = self._hash_bytes(b"forged output")
        receipt["processResultHash"] = canonical_hash(receipt["processResult"])
        self.receipt_path.write_text(
            json.dumps(receipt), encoding="utf-8", newline="\n"
        )
        with self.assertRaisesRegex(repair_completeness.InputError, "controlled replay"):
            repair_completeness.audit_repair_completeness(self.request())

    def test_audit_rejects_a_receipt_bound_to_a_stale_registry(self) -> None:
        import repair_completeness

        registry = json.loads(self.registry_path.read_text(encoding="utf-8"))
        registry["commands"][0]["argv"] = ["-c", "print('changed')"]
        self.registry_path.write_text(
            json.dumps(registry), encoding="utf-8", newline="\n"
        )
        with self.assertRaisesRegex(repair_completeness.InputError, "registry"):
            repair_completeness.audit_repair_completeness(self.request())

    def test_audit_rejects_a_tampered_write_manifest_receipt(self) -> None:
        import repair_completeness

        receipt = json.loads(self.receipt_path.read_text(encoding="utf-8"))
        receipt["writeManifestDelta"]["changedPaths"] = ["outside.txt"]
        self.receipt_path.write_text(
            json.dumps(receipt), encoding="utf-8", newline="\n"
        )
        with self.assertRaisesRegex(repair_completeness.InputError, "invalid or failed"):
            repair_completeness.audit_repair_completeness(self.request())

    def test_audit_rejects_receipt_for_stale_targeted_test_bytes(self) -> None:
        import repair_completeness

        (self.root / "tests" / "test_consumer.py").write_text(
            "from pathlib import Path\nassert Path('src/producer.py').is_file()\n",
            encoding="utf-8",
            newline="\n",
        )
        with self.assertRaisesRegex(repair_completeness.InputError, "invalid or failed"):
            repair_completeness.audit_repair_completeness(self.request())

    def test_audit_rejects_targeted_test_not_named_by_command(self) -> None:
        import repair_completeness

        registry = json.loads(self.registry_path.read_text(encoding="utf-8"))
        registry["commands"][0]["argv"] = ["-c", "print('ok')"]
        from acceptance_core import canonical_hash

        material = {
            "schemaVersion": "acceptance-command-registry.v1",
            "commands": [{
                key: value
                for key, value in registry["commands"][0].items()
                if key != "registry_hash"
            }],
        }
        registry_hash = canonical_hash(material)
        registry["commands"][0]["registry_hash"] = registry_hash
        registry["registryHash"] = registry_hash
        self.registry_path.write_text(
            json.dumps(registry), encoding="utf-8", newline="\n"
        )
        self.command = registry["commands"][0]
        self._write_receipt(0)
        with self.assertRaisesRegex(repair_completeness.InputError, "invalid or failed"):
            repair_completeness.audit_repair_completeness(self.request())

    def test_cli_rejects_a_caller_asserted_novel_finding_id(self) -> None:
        request = self.request()
        request["novelP0P1FindingIds"] = ["BSR-NEW-P1"]
        request_path = self.root / "request.json"
        output_path = self.root / "result.json"
        request_path.write_text(json.dumps(request), encoding="utf-8", newline="\n")
        command = [
            sys.executable,
            "-B",
            str(SKILL_ROOT / "scripts" / "acceptance_cli.py"),
            "audit-repair-completeness",
            "--request",
            str(request_path),
            "--out",
            str(output_path),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
        self.assertNotEqual(0, completed.returncode)
        self.assertFalse(output_path.exists())

    def test_audit_rejects_an_omitted_changed_file(self) -> None:
        import repair_completeness

        request = self.request()
        request["changedPaths"] = ["src/producer.py"]
        with self.assertRaisesRegex(repair_completeness.InputError, "complete candidate manifest"):
            repair_completeness.audit_repair_completeness(request)

    def test_audit_rejects_stale_composition_input_bytes(self) -> None:
        import repair_completeness

        self._write_manifests()
        request = self.request()
        (self.root / "src" / "consumer.py").write_text(
            "from producer import shared_route\nshared_route()\n# drift\n",
            encoding="utf-8", newline="\n",
        )
        with self.assertRaisesRegex(repair_completeness.InputError, "candidate authority"):
            repair_completeness.audit_repair_completeness(request)


if __name__ == "__main__":
    unittest.main()
