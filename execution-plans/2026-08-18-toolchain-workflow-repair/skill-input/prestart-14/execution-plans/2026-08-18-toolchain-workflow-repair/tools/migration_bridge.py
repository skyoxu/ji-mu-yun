from __future__ import annotations

import argparse
import json
from pathlib import Path


TEMPLATES = {
    "W0": """from scripts.python import skill_input_consumption as consumption\n\ndef test_typed_selection_keeps_selection_and_content_identity_separate():\n    source = [{\"role\": \"normative_source\", \"path\": \"docs/input.md\", \"module\": \"plan\", \"resource_set\": \"core\", \"sha256\": \"sha256:a\"}]\n    result = consumption.build_typed_source_selection_v2(source)\n    assert result[\"sourceSelectionHash\"].startswith(\"sha256:\")\n    assert result[\"sourceContentHash\"].startswith(\"sha256:\")\n""",
    "W1": """from scripts.python import skill_input_transport as transport\n\ndef test_transport_resume_preserves_content_identity():\n    plan = transport.plan_transport(32768, 1048576, content_hash=\"sha256:\" + \"a\" * 64)\n    resumed = transport.resume_transport(plan, content_hash=\"sha256:\" + \"a\" * 64)\n    assert resumed[\"content_hash\"] == plan[\"content_hash\"]\n""",
    "W2": """from scripts.python import skill_input_coverage as coverage\n\ndef test_coverage_rejects_missing_required_page():\n    result = coverage.evaluate_coverage(required_pages=[\"p1\", \"p2\"], observed_pages=[\"p1\"])\n    assert result[\"status\"] == \"insufficient\"\n    assert result[\"missing\"] == [\"p2\"]\n""",
    "W3": """from scripts.python import knowledge_gate_projection as gates\n\ndef test_knowledge_gates_keep_stale_catalog_degraded():\n    result = gates.project_knowledge_gates(catalog_stale=True, read_set_same=True, source_bytes_same=True)\n    assert result[\"route\"] == \"degraded-continuation\"\n    assert result[\"publication_allowed\"] is False\n""",
    "W4": """from scripts.python import skill_input_generation as generation\nfrom scripts.python import skill_input_current as current\n\ndef test_failed_generation_does_not_advance_current_pointer(tmp_path):\n    before = current.resolve_current(tmp_path)\n    generation.publish_generation(tmp_path, generation_id=\"g1\", content=b\"x\")\n    after = current.resolve_current(tmp_path)\n    assert before == after\n""",
    "W5": """from scripts.python import skill_input_retention as retention\n\ndef test_retention_apply_requires_explicit_approval(tmp_path):\n    plan = retention.plan_retention(tmp_path, dry_run=True)\n    assert plan[\"mode\"] == \"dry-run\"\n    assert retention.apply_retention(tmp_path, approval=None)[\"status\"] == \"approval-required\"\n""",
    "W6": """from scripts.python import skill_input_consumption as consumption\n\ndef test_end_to_end_selection_exposes_independent_identity_hashes():\n    result = consumption.build_typed_source_selection_v2([])\n    assert result[\"sourceSelectionHash\"] != result[\"sourceContentHash\"]\n""",
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
