from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


PLAN_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = PLAN_ROOT.parents[1]
VALIDATOR = PLAN_ROOT / "tools" / "validate_plan.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("tc_d1_validate_plan", VALIDATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError("validator import failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ValidatePlanTests(unittest.TestCase):
    def test_current_implementation_authorized_plan_is_structurally_valid(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-B", str(VALIDATOR), "--implementation-state"],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual("implementation-authorized-valid", payload["predicate"])
        self.assertEqual(["implementation-authorized"], payload["authorizes"])
        self.assertEqual(
            ["implementation-complete", "acceptance-passed", "release", "archived"],
            payload["does_not_authorize"],
        )

    def test_first_class_headings_and_forbidden_paths_are_enforced(self) -> None:
        module = load_validator()
        self.assertEqual([], module.validate_headings("\n".join(module.REQUIRED_HEADINGS)))
        self.assertTrue(module.has_forbidden_allowed_path("PhaseA.Platform/Program.cs"))
        self.assertTrue(module.has_forbidden_allowed_path("_bmad/custom/example.toml"))
        self.assertFalse(module.has_forbidden_allowed_path("scripts/sc/skill_package_replay.py"))

    def test_mutable_authority_sources_are_declared_and_hashable(self) -> None:
        module = load_validator()
        errors: list[str] = []
        hashes = module.validate_authority(errors, allow_mutable_source_drift=True)
        self.assertEqual([], errors)
        self.assertEqual(
            {
                ".agents/skills/vdd-execution-plan/SKILL.md",
                ".agents/skills/run-refactor-implementation-acceptance/SKILL.md",
            },
            set(hashes),
        )

    def test_plan_ready_rejects_historical_worktree_byte_drift(self) -> None:
        module = load_validator()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            historical = root / "historical"
            historical.mkdir()
            source = historical / "evidence.json"
            source.write_text(json.dumps({"status": "frozen"}), encoding="utf-8", newline="\n")
            for command in (
                ["git", "init", "-b", "main"],
                ["git", "config", "user.email", "test@example.invalid"],
                ["git", "config", "user.name", "TC-D1 Test"],
                ["git", "add", "historical/evidence.json"],
                ["git", "commit", "-m", "baseline"],
            ):
                subprocess.run(command, cwd=root, check=True, capture_output=True)
            commit = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
            ).stdout.strip()
            tree = subprocess.run(
                ["git", "rev-parse", "HEAD:historical"], cwd=root, check=True, capture_output=True, text=True
            ).stdout.strip()
            source.write_text(json.dumps({"status": "changed"}), encoding="utf-8", newline="\n")
            manifest = {
                "git": {"commit": commit},
                "historical_trees": [{"path": "historical", "git_tree_oid": tree}],
            }
            original_root = module.REPOSITORY_ROOT
            module.REPOSITORY_ROOT = root
            try:
                errors: list[str] = []
                module.validate_historical_candidate(manifest, errors)
            finally:
                module.REPOSITORY_ROOT = original_root
            self.assertTrue(any("historical candidate byte drift" in error for error in errors), errors)

    def test_implementation_lifecycle_rejects_overclaimed_authority(self) -> None:
        module = load_validator()
        errors: list[str] = []
        module.validate_implementation_lifecycle_state(
            {
                "state": "implementation-complete",
                "state_owner": "quick-dev-tdd-adapter",
                "authorizes": ["implementation-complete", "acceptance-passed"],
                "does_not_authorize": ["release", "archived"],
            },
            errors,
        )
        self.assertTrue(any("authority fields" in error for error in errors), errors)

    def test_implementation_lifecycle_accepts_exact_owner_contract(self) -> None:
        module = load_validator()
        errors: list[str] = []
        module.validate_implementation_lifecycle_state(
            {
                "state": "implementation-complete",
                "state_owner": "quick-dev-tdd-adapter",
                "authorizes": ["implementation-complete"],
                "does_not_authorize": ["acceptance-passed", "release", "archived"],
            },
            errors,
        )
        self.assertEqual([], errors)

    def test_implementation_authorization_binds_round3_repair_evidence(self) -> None:
        module = load_validator()
        errors: list[str] = []
        module.validate_implementation_lifecycle_state(
            {
                "state": "implementation-authorized",
                "state_owner": "maintainer",
                "implementation_authorization": {
                    "decision": "accepted-deterministic-round3-repair-evidence",
                    "evidence_path": module.ROUND3_REPAIR_EVIDENCE_PATH,
                    "evidence_sha256": module.sha256(module.REPOSITORY_ROOT / module.ROUND3_REPAIR_EVIDENCE_PATH),
                    "next_slice": "RMAP-S0",
                    "authorizes": ["implementation-authorized"],
                },
                "authorizes": ["implementation-authorized"],
                "does_not_authorize": ["implementation-complete", "acceptance-passed", "release", "archived"],
            },
            errors,
        )
        self.assertEqual([], errors)


if __name__ == "__main__":
    unittest.main()
