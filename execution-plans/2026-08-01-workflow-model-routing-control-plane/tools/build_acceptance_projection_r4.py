from __future__ import annotations

import json
from pathlib import Path


PLAN_ROOT = Path(__file__).resolve().parents[1]
SOURCE = PLAN_ROOT / "acceptance-projection-request.r3.v1.json"
OUTPUT = PLAN_ROOT / "acceptance-projection-request.r4.v1.json"


def main() -> int:
    value = json.loads(SOURCE.read_text(encoding="utf-8"))
    value["runId"] = "workflow-model-routing-ria-r4"
    value["changeId"] = "workflow-model-routing-control-plane-with-acceptance-prerequisite-r4"
    value["targetPlanPaths"] = sorted({
        *value["targetPlanPaths"],
        "acceptance-projection-request.r3.v1.json",
        "acceptance-runs/acceptance-f26e17dc243c29af/run-input.v1.json",
        "acceptance-runs/acceptance-f26e17dc243c29af/run-state.json",
        "tools/build_acceptance_projection_r4.py",
    })
    if OUTPUT.exists():
        raise SystemExit("r4 projection request is append-only")
    OUTPUT.write_text(
        json.dumps(value, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
