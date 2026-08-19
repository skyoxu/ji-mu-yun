from __future__ import annotations

import argparse
import json
from pathlib import Path


TEMPLATES = {
    "W0": """from scripts.python import skill_input_consumption as consumption\n\ndef test_typed_selection_keeps_selection_and_content_identity_separate():\n    source = [{\"role\": \"normative_source\", \"path\": \"docs/input.md\", \"module\": \"plan\", \"resource_set\": \"core\", \"sha256\": \"sha256:a\"}]\n    result = consumption.build_typed_source_selection_v2(source)\n    assert result[\"sourceSelectionHash\"].startswith(\"sha256:\")\n    assert result[\"sourceContentHash\"].startswith(\"sha256:\")\n""",
    "W1": """from scripts.python import skill_input_transport as transport\n\ndef test_transport_has_deterministic_resume_contract():\n    assert callable(getattr(transport, \"plan_transport\", None))\n    assert callable(getattr(transport, \"resume_transport\", None))\n""",
    "W2": """from scripts.python import skill_input_coverage as coverage\n\ndef test_coverage_is_adapter_owned():\n    assert callable(getattr(coverage, \"evaluate_coverage\", None))\n""",
    "W3": """from scripts.python import knowledge_gate_projection as gates\n\ndef test_knowledge_gates_are_independent():\n    assert callable(getattr(gates, \"project_knowledge_gates\", None))\n""",
    "W4": """from scripts.python import skill_input_generation as generation\nfrom scripts.python import skill_input_current as current\n\ndef test_current_pointer_is_typed():\n    assert callable(getattr(generation, \"publish_generation\", None))\n    assert callable(getattr(current, \"resolve_current\", None))\n""",
    "W5": """from scripts.python import skill_input_retention as retention\n\ndef test_retention_apply_requires_approval():\n    assert callable(getattr(retention, \"plan_retention\", None))\n    assert callable(getattr(retention, \"apply_retention\", None))\n""",
    "W6": """from scripts.python import skill_input_consumption as consumption\n\ndef test_end_to_end_workflow_has_typed_entrypoint():\n    assert callable(getattr(consumption, \"build_typed_source_selection_v2\", None))\n""",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--slice-id", required=True)
    parser.add_argument("--snapshot-path", nargs="+", required=True)
    parser.add_argument("--materialize-only", action="store_true")
    args = parser.parse_args()
    root = args.repository_root.resolve()
    plan = args.plan_dir.resolve()
    contract = json.loads((plan / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    selected = next(item for item in contract["slices"] if item["slice_id"] == args.slice_id)
    selector = selected["tdd"]["red"]["test_selector"].split("::", 1)[0]
    if selector not in selected.get("planned_new_files", []) or args.slice_id not in TEMPLATES:
        raise ValueError("current slice template is not declared")
    target = (root / selector).resolve()
    target.relative_to(root)
    if target.exists():
        if target.read_text(encoding="utf-8") != TEMPLATES[args.slice_id]:
            raise ValueError("existing planned test conflicts with bridge template")
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(TEMPLATES[args.slice_id], encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
