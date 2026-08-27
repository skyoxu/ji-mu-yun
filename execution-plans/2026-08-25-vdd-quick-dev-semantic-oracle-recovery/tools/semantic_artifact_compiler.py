"""Named owner module for S1 semantic artifact compilation."""
from __future__ import annotations
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
TOOLS = Path(__file__).resolve().parent

def main() -> int:
    run = Path(sys.argv[1]).resolve()
    input_path = run / "semantic-intent-input.v1.json"
    value = json.loads(input_path.read_text(encoding="utf-8"))
    sys.path.insert(0, str(TOOLS))
    from semantic_oracle import validate_semantic_intent, compile_run_local_semantic_artifacts
    accepted, failure = validate_semantic_intent(value)
    if not accepted:
        print(f"FAILURE_ID:{failure}", file=sys.stderr)
        return 1
    compile_run_local_semantic_artifacts(run)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
from __future__ import annotations

from semantic_oracle import compile_run_local_semantic_artifacts

__all__ = ["compile_run_local_semantic_artifacts"]
