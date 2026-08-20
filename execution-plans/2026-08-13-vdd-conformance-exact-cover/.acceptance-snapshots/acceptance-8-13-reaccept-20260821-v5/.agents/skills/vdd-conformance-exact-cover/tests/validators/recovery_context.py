from __future__ import annotations

from pathlib import Path
import json
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / ".agents/skills/vdd-conformance-exact-cover/scripts"))
from conformance import append_checkpoint  # noqa: E402


def main() -> int:
    text = (ROOT / "_bmad-output/specs/spec-vdd-conformance-exact-cover/execution-and-recovery.md").read_text(encoding="utf-8")
    required = ("append-only `recovery-checkpoint.v1`", "fork_from", "artifact ref/hash", "truncated", "old chat")
    if not all(item in text for item in required):
        return 2
    with tempfile.TemporaryDirectory() as raw:
        path = Path(raw) / "checkpoints.json"
        append_checkpoint(path, {"schema_version":"recovery-checkpoint.v1","run_id":"r","branch_id":"b","sequence":0,"stage":"package_candidate","state":"available","validator_identity":"v","policy_identity":"p","artifact_refs":[],"attempt_binding":{"status":"unavailable","reason":"not-started"},"shard_states":[],"live_blocker":None,"next_legal_actions":[],"authorizes":[]})
        item = json.loads(path.read_text(encoding="utf-8"))
        try:
            append_checkpoint(path, item)
        except ValueError:
            return 0
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
