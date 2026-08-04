from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


PLAN_ROOT = Path(__file__).resolve().parents[2]
TOOLS = PLAN_ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from candidate_lineage_guards import bytes_hash, manifest_root_hash, validate_stage_evidence_projection  # noqa: E402
from stage_projection_builder import build as build_stage_projection, load_protocol_binding, write_stage_result  # noqa: E402
from protocol_fixture_support import hydrate_protocol_fixture  # noqa: E402


class StageProjectionGuardTests(unittest.TestCase):
    def test_stage_evidence_projection_binds_all_stage_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = root / "logs" / "stage-run"
            run.mkdir(parents=True)
            hashes = {}
            for stage in ("red", "green", "refactor"):
                path = run / f"{stage}-result.json"
                path.write_text(json.dumps({"stage": stage}), encoding="utf-8")
                hashes[stage] = bytes_hash(path.read_bytes())
            projection = {
                "schema_version": "jimuyun.stage-evidence-projection.v1", "plan_id": "repository-maintenance-tdd-adapter",
                "slice_id": "RMAP-S0", "run_id": "stage-run", "baseline_files": [], "effects": [],
                "stage_result_hashes": hashes, "final_event_hash": hashes["refactor"],
            }
            projection["root_hash"] = manifest_root_hash(projection)
            path = run / "stage-evidence-projection.v1.json"
            path.write_text(json.dumps(projection), encoding="utf-8")
            result, findings = validate_stage_evidence_projection(PLAN_ROOT, root, "logs/stage-run/stage-evidence-projection.v1.json", "RMAP-S0", "stage-run")
            self.assertEqual([], findings)
            self.assertEqual("RMAP-S0", result["slice_id"])
            (run / "green-result.json").write_text("stale", encoding="utf-8")
            _, findings = validate_stage_evidence_projection(PLAN_ROOT, root, "logs/stage-run/stage-evidence-projection.v1.json", "RMAP-S0", "stage-run")
            self.assertEqual({"RMAP-CANDIDATE-LINEAGE"}, {item["rule_id"] for item in findings})

    def test_stage_projection_builder_rejects_paths_outside_slice_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = root / "run"
            run.mkdir()
            for stage in ("red", "green", "refactor"):
                (run / f"{stage}-result.json").write_text("{}", encoding="utf-8")
            plan = root / "execution-plans/2026-07-15-repository-maintenance-tdd-adapter"
            plan.mkdir(parents=True)
            contract = json.loads((PLAN_ROOT / "implementation-contract.v1.json").read_text(encoding="utf-8"))
            (plan / "implementation-contract.v1.json").write_text(json.dumps(contract), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "write set"):
                build_stage_projection(root, run, "RMAP-S0", ["outside.txt"])

    def test_stage_result_writer_requires_order_and_contract_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "execution-plans/2026-07-15-repository-maintenance-tdd-adapter"
            plan.mkdir(parents=True)
            for name in ("implementation-contract.v1.json", "schemas/command-registry.v1.json"):
                source = PLAN_ROOT / name
                target = plan / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())
            run = root / "logs/tdd-adapter/repository-maintenance-tdd-adapter/RMAP-S0/test-run"
            with self.assertRaisesRegex(ValueError, "nonzero"):
                write_stage_result(root, run, "RMAP-S0", "red", ["rmap-observe-ownership-red"], 0, "2026-07-20T14:00:00Z")
            with self.assertRaisesRegex(ValueError, "prior stage"):
                write_stage_result(root, run, "RMAP-S0", "green", ["rmap-s0-preflight"], 0, "2026-07-20T14:01:00Z")

    def test_stage_result_writer_binds_protocol_on_first_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "execution-plans/2026-07-15-repository-maintenance-tdd-adapter"
            plan.mkdir(parents=True)
            for name in ("implementation-contract.v1.json", "schemas/command-registry.v1.json"):
                source = PLAN_ROOT / name
                target = plan / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())
            run = root / "logs/tdd-adapter/repository-maintenance-tdd-adapter/RMAP-S0/test-binding"
            binding = {
                "stage_binding_id": "STAGE-RED", "attempt_id": "ATTEMPT-001",
                "decision_hash": "sha256:" + "1" * 64,
                "capsule_hash": "sha256:" + "2" * 64,
                "context_hash": "sha256:" + "3" * 64,
            }
            output = write_stage_result(
                root, run, "RMAP-S0", "red", ["rmap-observe-ownership-red"], 1,
                "2026-07-20T14:00:00Z", protocol_binding=binding,
            )
            document = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(binding, {key: document[key] for key in binding})

    def test_protocol_bundle_file_derives_stage_binding(self) -> None:
        fixtures = json.loads((PLAN_ROOT / "fixtures" / "capsule-attempt-cases.v1.json").read_text(encoding="utf-8"))
        bundle, _, _ = hydrate_protocol_fixture(fixtures["valid_bundle"])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "protocol-bundle.json"
            path.write_text(json.dumps(bundle), encoding="utf-8")
            binding = load_protocol_binding(path, "green")
        self.assertEqual("STAGE-GREEN", binding["stage_binding_id"])
        self.assertEqual("ATTEMPT-002", binding["attempt_id"])


if __name__ == "__main__":
    unittest.main()
