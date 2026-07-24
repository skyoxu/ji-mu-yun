from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
VALIDATOR_PATH = REPOSITORY_ROOT / "scripts" / "python" / "validate_execution_plan_report_index.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("report_index_validator", VALIDATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ReportIndexValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.validator = load_validator()

    def write_index(self, root: Path, entries: list[dict[str, str]]) -> None:
        plans = root / "execution-plans"
        plans.mkdir()
        for entry in entries:
            report = plans / entry["plan_directory"] / entry["report_filename"]
            report.parent.mkdir()
            report.write_text("report\n", encoding="utf-8", newline="\n")
        (plans / "95-implementation-report-index.v1.json").write_text(
            json.dumps(
                {
                    "schema_version": "jimuyun.execution-plan-95-report-index.v1",
                    "entries": entries,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )

    def test_valid_index_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_index(
                root,
                [
                    {"plan_directory": "alpha-plan", "report_filename": "95-report.md"},
                    {"plan_directory": "beta-plan", "report_filename": "95-evolution.md"},
                ],
            )
            self.assertEqual([], self.validator.validate_index(root))

    def test_unsorted_entries_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_index(
                root,
                [
                    {"plan_directory": "beta-plan", "report_filename": "95-evolution.md"},
                    {"plan_directory": "alpha-plan", "report_filename": "95-report.md"},
                ],
            )
            self.assertEqual(["entries are not case-insensitively sorted"], self.validator.validate_index(root))

    def test_escaping_directory_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plans = root / "execution-plans"
            plans.mkdir()
            (plans / "95-implementation-report-index.v1.json").write_text(
                json.dumps(
                    {
                        "schema_version": "jimuyun.execution-plan-95-report-index.v1",
                        "entries": [
                            {"plan_directory": "../escape", "report_filename": "95-report.md"}
                        ],
                    }
                ),
                encoding="utf-8",
                newline="\n",
            )
            self.assertIn("unsafe plan_directory", self.validator.validate_index(root)[0])

    def test_missing_report_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plans = root / "execution-plans"
            (plans / "alpha-plan").mkdir(parents=True)
            (plans / "95-implementation-report-index.v1.json").write_text(
                json.dumps(
                    {
                        "schema_version": "jimuyun.execution-plan-95-report-index.v1",
                        "entries": [
                            {"plan_directory": "alpha-plan", "report_filename": "95-report.md"}
                        ],
                    }
                ),
                encoding="utf-8",
                newline="\n",
            )
            self.assertIn("missing or escaping report", self.validator.validate_index(root)[0])


if __name__ == "__main__":
    unittest.main()
