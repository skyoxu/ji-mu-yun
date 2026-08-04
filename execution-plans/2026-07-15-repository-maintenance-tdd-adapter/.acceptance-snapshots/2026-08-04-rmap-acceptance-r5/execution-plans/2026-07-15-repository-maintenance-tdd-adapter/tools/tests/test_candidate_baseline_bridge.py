from __future__ import annotations

import importlib.util
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest


TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
SPEC = importlib.util.spec_from_file_location("candidate_lineage_builder", TOOLS / "candidate_lineage_builder.py")
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)
from replay_baseline_guards import load_replay_baseline  # noqa: E402


class CandidateBaselineBridgeTests(unittest.TestCase):
    def test_bridge_requires_explicit_hash_bound_transition(self) -> None:
        with self.assertRaisesRegex(ValueError, "bridge"):
            BUILDER.validate_baseline_bridge({"schema_version": "jimuyun.candidate-baseline-bridge.v1"})

    def test_complete_non_authoritative_bridge_is_accepted(self) -> None:
        bridge = {
            "schema_version": "jimuyun.candidate-baseline-bridge.v1",
            "from_slice_id": "RMAP-S0",
            "to_slice_id": "RMAP-S1",
            "from_baseline_hash": "sha256:" + "1" * 64,
            "to_baseline_hash": "sha256:" + "2" * 64,
            "transition_files": [],
            "transition_hash": "sha256:" + "3" * 64,
            "authorizes": [],
        }
        self.assertIsNone(BUILDER.validate_baseline_bridge(bridge))

    def test_replay_manifest_excludes_only_current_hash_bound_path(self) -> None:
        repository_root = TOOLS.parents[2]
        entry = {"change_type": "add", "baseline_path": None, "candidate_path": "docs/bootstrap.txt", "before_sha256": None, "after_sha256": "sha256:" + "a" * 64}
        with tempfile.TemporaryDirectory(dir=repository_root / "logs") as temporary:
            root = Path(temporary)
            source = root / "mismatch.json"; source.write_text("{}", encoding="utf-8")
            manifest = {
                "schema_version": "jimuyun.replay-baseline-manifest.v1", "plan_id": "repository-maintenance-tdd-adapter",
                "source_mismatch_ref": source.relative_to(repository_root).as_posix(),
                "source_mismatch_sha256": "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest(),
                "paths": [{"path": "docs/bootstrap.txt", "candidate_change": entry}],
                "authorizes": [], "does_not_authorize": ["slice-ready", "implementation-candidate", "implementation-accepted"], "root_hash": "",
            }
            from candidate_lineage_guards import manifest_root_hash
            manifest["root_hash"] = manifest_root_hash(manifest)
            path = root / "replay.json"; path.write_text(json.dumps(manifest), encoding="utf-8")
            reference = {"path": path.relative_to(repository_root).as_posix(), "sha256": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()}
            excluded, findings = load_replay_baseline(TOOLS.parent, repository_root, reference, {"docs/bootstrap.txt": entry})
            self.assertEqual({"docs/bootstrap.txt"}, excluded)
            self.assertEqual([], findings)
            _, findings = load_replay_baseline(TOOLS.parent, repository_root, reference, {})
            self.assertEqual({"RMAP-REPLAY-BASELINE"}, {item["rule_id"] for item in findings})


if __name__ == "__main__":
    unittest.main()
