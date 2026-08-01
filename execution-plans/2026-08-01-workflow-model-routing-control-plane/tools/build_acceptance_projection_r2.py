from __future__ import annotations

import json
from pathlib import Path


PLAN_ROOT = Path(__file__).resolve().parents[1]
SOURCE = PLAN_ROOT / "acceptance-projection-request.r1.v1.json"
OUTPUT = PLAN_ROOT / "acceptance-projection-request.r2.v1.json"


def main() -> int:
    value = json.loads(SOURCE.read_text(encoding="utf-8"))
    value["runId"] = "workflow-model-routing-ria-r2"
    value["changeId"] = "workflow-model-routing-control-plane-with-acceptance-prerequisite-r2"
    value["knowledgeContextPath"] = "knowledge-context.refactor-acceptance.r3.v1.json"
    value["changedPaths"] = sorted({
        *value["changedPaths"],
        ".agents/skills/run-refactor-implementation-acceptance/scripts/prepare_knowledge_context.py",
        ".agents/skills/run-refactor-implementation-acceptance/tests/test_knowledge_context.py",
    })
    value["affectedConsumerRefs"] = sorted({
        *value["affectedConsumerRefs"],
        ".agents/skills/run-refactor-implementation-acceptance/scripts/prepare_knowledge_context.py",
    })
    value["targetPlanPaths"] = sorted({
        *value["targetPlanPaths"],
        "acceptance-projection-request.r1.v1.json",
        "knowledge-context.refactor-acceptance.r2.v1.json",
        "knowledge-context.refactor-acceptance.r3.v1.json",
        "tools/build_acceptance_projection_r2.py",
    })
    if OUTPUT.exists():
        raise SystemExit("r2 projection request is append-only")
    OUTPUT.write_text(
        json.dumps(value, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
