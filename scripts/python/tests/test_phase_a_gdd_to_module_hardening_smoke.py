#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
PYTHON_DIR = REPO_ROOT / "scripts" / "python"
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

import phase_a_gdd_to_module_hardening_smoke as smoke  # noqa: E402


class PhaseAGddToModuleHardeningSmokeTests(unittest.TestCase):
    def test_phase0_baseline_passes_for_repository(self) -> None:
        events: list[dict[str, object]] = []

        failures = smoke.check_phase0_baseline(REPO_ROOT, events)

        self.assertEqual([], failures)
        self.assertEqual("phase0_baseline_checked", events[-1]["event"])

    def test_phase0_baseline_fails_when_required_fixture_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in smoke.REQUIRED_BASELINE_FILES:
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                if rel.endswith(".json"):
                    path.write_text("{}", encoding="utf-8")
                else:
                    path.write_text("", encoding="utf-8")
            (root / "PhaseA.Platform.Tests/Fixtures/evidence-ref-kind.v1.json").unlink()

            failures = smoke.check_phase0_baseline(root, [])

        self.assertIn("missing_baseline_file:PhaseA.Platform.Tests/Fixtures/evidence-ref-kind.v1.json", failures)

    def test_project_route_state_hash_chain_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            gdd_hash = self._write_project_chain(project_root)

            events: list[dict[str, object]] = []
            failures = smoke.check_project_route_state(project_root, events)

        self.assertEqual([], failures)
        self.assertEqual(gdd_hash, events[-1]["gdd_hash"])

    def test_project_route_state_hash_chain_fails_when_contract_uses_stale_scene_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            self._write_project_chain(project_root)
            self._write_json(
                project_root / "routes/prototype-contract/latest.json",
                {
                    "status": "ready",
                    "source_scene_route_hash": "stale",
                    "source_boundary_enforced": True,
                    "source_boundary": {
                        "recovery_source_order_ref": "hosted-route-recovery-order.v1",
                        "authority_sources": ["docs/gdd/GDD.md"],
                        "source_hashes": {"docs/gdd/GDD.md": "x"},
                    },
                },
            )

            failures = smoke.check_project_route_state(project_root, [])

        self.assertIn("source_scene_route_hash_mismatch:routes/prototype-contract/latest.json", failures)

    def _write_project_chain(self, project_root: Path) -> str:
        gdd_path = project_root / "docs/gdd/GDD.md"
        gdd_path.parent.mkdir(parents=True, exist_ok=True)
        gdd_path.write_text("# Test GDD\n", encoding="utf-8")
        gdd_hash = hashlib.sha256("# Test GDD".encode("utf-8")).hexdigest()
        scene_hash = "scene-hash-1"
        boundary = {
            "recovery_source_order_ref": "hosted-route-recovery-order.v1",
            "authority_sources": ["docs/gdd/GDD.md", "meta/project-execution-guide.md"],
            "source_hashes": {"docs/gdd/GDD.md": gdd_hash},
            "forbidden_source_patterns": ["docs/game-type-guides/** raw excerpts"],
        }
        self._write_json(
            project_root / "meta/routes/scene-route/latest.json",
            {
                "status": "confirmed",
                "confirmed_scene_route_hash": scene_hash,
                "source_generated_gdd_hash": gdd_hash,
            },
        )
        self._write_json(
            project_root / "meta/routes/gdd-document/latest.json",
            {"status": "ready", "generated_gdd_hash": gdd_hash},
        )
        self._write_json(
            project_root / "meta/routes/gdd-requirements/latest.json",
            {
                "status": "ready",
                "source_scene_route_hash": scene_hash,
                "source_boundary_enforced": True,
                "source_boundary": boundary,
            },
        )
        self._write_json(
            project_root / "routes/prototype-contract/latest.json",
            {
                "status": "ready",
                "source_scene_route_hash": scene_hash,
                "source_boundary_enforced": True,
                "source_boundary": boundary,
            },
        )
        self._write_json(
            project_root / "meta/routes/prototype-skeleton/latest.json",
            {
                "status": "ready",
                "source_scene_route_hash": scene_hash,
                "source_boundary_enforced": True,
                "source_boundary": boundary,
            },
        )
        return gdd_hash

    @staticmethod
    def _write_json(path: Path, payload: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    unittest.main()
