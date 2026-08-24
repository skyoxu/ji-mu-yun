import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ENTRY = ROOT / "scripts" / "sc" / "skill_package_replay.py"
CAP = ROOT / "scripts" / "sc" / "config" / "skill-package-validator-capability.v1.json"

class SkillPackageReplayTests(unittest.TestCase):
    def test_validate_package_emits_non_authorizing_receipt(self):
        result = subprocess.run([sys.executable, str(ENTRY), "validate-package", "--target", ".agents/skills/vdd-execution-plan", "--capability", str(CAP.relative_to(ROOT))], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([], json.loads(result.stdout)["authorizes"])

    def test_capability_rejects_escape(self):
        value = json.loads(CAP.read_text(encoding="utf-8")); value["validator_entrypoint"] = "../run-refactor-implementation-acceptance/scripts/validate_skill_contract.py"
        temp = ROOT / "scripts" / "sc" / "tests" / "fixtures" / "bad-capability.json"; temp.parent.mkdir(parents=True, exist_ok=True); temp.write_text(json.dumps(value), encoding="utf-8")
        try:
            result = subprocess.run([sys.executable, str(ENTRY), "validate-package", "--target", ".agents/skills/vdd-execution-plan", "--capability", str(temp.relative_to(ROOT))], cwd=ROOT, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
        finally:
            temp.unlink(missing_ok=True)

if __name__ == "__main__": unittest.main()
