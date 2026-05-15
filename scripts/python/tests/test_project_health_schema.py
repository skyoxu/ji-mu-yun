#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
PYTHON_DIR = REPO_ROOT / "scripts" / "python"
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))


def _load_module(name: str, relative_path: str):
    path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"failed to load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


project_health_schema = _load_module(
    "project_health_schema_test_module",
    "scripts/python/_project_health_schema.py",
)


class ProjectHealthSchemaTests(unittest.TestCase):
    def test_dashboard_payload_should_allow_prototype_specific_extensions(self) -> None:
        payload = {
            "kind": "project-health-dashboard",
            "status": "ok",
            "generated_at": "2026-05-15T00:00:00+00:00",
            "records": [],
            "report_catalog_summary": {
                "total_json": 0,
                "invalid_json": 0,
                "catalog_json": "logs/ci/project-health/report-catalog.latest.json",
            },
            "active_task_summary": {
                "total": 0,
                "clean": 0,
                "top_records": [],
            },
            "project_overview": {
                "game_name": "Demo",
                "game_type": "rpg",
                "documents": {
                    "prd": [],
                    "gdd": [],
                    "prototype": [],
                    "prototype_spec": [],
                },
                "prototype_core": {
                    "game_feature": "",
                    "core_gameplay_loop": "",
                    "win_fail_conditions": "",
                },
                "game_type_specifics": {
                    "game_type": "rpg",
                    "guide_path": "docs/prototypes/type-kits/rpg.md",
                    "needs_narrative": True,
                    "selected_sections": [
                        {
                            "id": "combat_system",
                            "title": "Combat System",
                            "prompt": "Describe the combat loop.",
                            "answer": "Small-scale RPG combat loop.",
                        }
                    ],
                },
                "prototype_type_kit": {
                    "game_type": "rpg",
                    "kit_path": "",
                    "manifest_path": "",
                    "manifest": {},
                },
                "prototype_blueprint": {
                    "prototype_spec": "",
                    "prototype_file": "",
                    "game_feature": "",
                    "core_gameplay_loop": "",
                    "win_fail_conditions": "",
                    "minimum_playable_loop": "",
                    "gameplay_flow": [],
                    "prototype_scene_ui": [],
                    "tdd": {
                        "red": "pending",
                        "green": "pending",
                        "refactor": "pending",
                    },
                },
            },
        }

        project_health_schema.validate_project_health_dashboard_payload(payload)


if __name__ == "__main__":
    unittest.main()
