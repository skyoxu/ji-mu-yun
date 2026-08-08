import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


PLAN_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PLAN_DIR.parents[2]
PLAN_ROOT = PLAN_DIR.parent
sys.path.insert(0, str(PLAN_DIR))
SPEC = importlib.util.spec_from_file_location("stage_projection_builder", PLAN_DIR / "stage_projection_builder.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)
RUNNER_SPEC = importlib.util.spec_from_file_location(
    "quick_dev_run_slice_lifecycle",
    REPOSITORY_ROOT / ".agents/skills/quick-dev-tdd-adapter/tools/run_slice_lifecycle.py",
)
RUNNER = importlib.util.module_from_spec(RUNNER_SPEC)
assert RUNNER_SPEC and RUNNER_SPEC.loader
RUNNER_SPEC.loader.exec_module(RUNNER)


class StageProjectionBuilderTests(unittest.TestCase):
    def test_build_is_plan_bound_and_hashes_observed_stage_files(self):
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp)
            for stage in ("red", "green", "refactor"):
                (run_dir / f"{stage}-result.json").write_text(stage, encoding="utf-8")
            projection = RUNNER._projection(PLAN_ROOT)
            value = projection.build(
                REPOSITORY_ROOT,
                run_dir,
                "BROH-S7",
                [".agents/skills/run-refactor-implementation-acceptance/SKILL.md"],
            )
            self.assertEqual("bootstrap-review-operability-hardening", value["plan_id"])
            self.assertEqual("BROH-S7", value["slice_id"])
            self.assertTrue(value["root_hash"].startswith("sha256:"))
            self.assertEqual([], value["effects"])

    def test_build_rejects_path_outside_slice_write_set(self):
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp)
            for stage in ("red", "green", "refactor"):
                (run_dir / f"{stage}-result.json").write_text(stage, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "write set"):
                MODULE.build(REPOSITORY_ROOT, run_dir, "BROH-S7", ["README.md"])


if __name__ == "__main__":
    unittest.main()
