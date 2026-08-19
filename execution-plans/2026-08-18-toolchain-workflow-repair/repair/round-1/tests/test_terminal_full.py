import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
PLAN = ROOT / "execution-plans/2026-08-18-toolchain-workflow-repair"


def test_terminal_consumes_lifecycle_slice_ready_results_and_publishes_completion():
    result = subprocess.run(
        ["python", str(PLAN / "tools/terminal_full.py"), "--repository-root", str(ROOT), "--plan-dir", str(PLAN)],
        capture_output=True, text=True, check=False,
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["predicate"] == "implementation-complete"
    assert payload["authorizes"] == ["implementation-complete"]
    assert payload["schema_version"] == "quick-dev-implementation-complete.v1"
    assert payload["command_registry_hash"].startswith("sha256:")
    assert payload["terminal_command_id"] == "terminal-full"
    assert payload["validated_command_ids"] == [f"w{index}-terminal" for index in range(7)]


def test_terminal_publishes_plan_local_canonical_receipt():
    receipt = PLAN / "repair/round-1/quick-dev-implementation-complete.v1.json"
    assert receipt.is_file()
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "quick-dev-implementation-complete.v1"
    assert payload["command_registry_hash"].startswith("sha256:")
    assert payload["authorizes"] == ["implementation-complete"]
    assert payload["failures"] == []
