from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from semantic_compiler import _normalize_obligation
from semantic_compiler_gate import compile_plan


def _repo(tmp_path: Path) -> tuple[Path, Path, str, str]:
    root = tmp_path
    (root / ".agents").mkdir()
    (root / "AGENTS.md").write_text("fixture\n", encoding="utf-8")
    (root / "src").mkdir()
    (root / "tests").mkdir()
    owner = "src/compiler.py"
    selector = "tests/test_compile.py"
    (root / owner).write_text("VALUE = 1\n", encoding="utf-8")
    (root / selector).write_text("def test_compile():\n    assert True\n", encoding="utf-8")
    req = root / "requirements.md"
    req.write_text("# FR-1\nThe compiler must emit a deterministic plan.\n", encoding="utf-8")
    return root, req, owner, selector


def _cache(owner: str, selector: str) -> dict:
    source_ref = "requirements.md#FR-1"
    raw = {
        "source_refs": [source_ref],
        "subject": "compiler",
        "trigger": "a requirement is compiled",
        "state_before": "uncompiled",
        "state_after": "compiled",
        "expected_behavior": "emit a deterministic plan",
        "observable_result": "plan-ready semantic bundle",
        "forbidden_result": ["future evidence"],
        "requirement_type": "Platform",
        "obligation_kind": "behavior",
        "unresolved_fragments": [],
        "status": "active",
        "depends_on": [],
    }
    oid = _normalize_obligation({"requirement_id": "FR-1", "source_ref": source_ref}, raw)["obligation_id"]
    hint = {
        "obligation_ids": [oid],
        "production_owners": [owner],
        "verification_lane": "unit",
        "behavior_change": "compile deterministic plans",
        "affected_subjects": ["compiler"],
        "state_transition": "uncompiled->compiled",
        "rollback_scope": {"production_paths": [owner], "state_or_schema_compatibility": "compatible"},
        "allowed_write_paths": [owner],
        "execution_snapshot_paths": [selector],
        "planned_new_files": [],
        "terminal_predicate": "all active Acceptance assertions pass",
        "forbidden_paths": [],
        "validation_commands": [[sys.executable, "-m", "pytest", selector, "-q"]],
    }
    return {
        "v1-FR-1": {"obligations": [raw]},
        "v3": {
            "acceptances": [{
                "obligation_ids": [oid],
                "source_refs": [source_ref],
                "given": "a valid requirement",
                "when": "compiled",
                "then": "a deterministic plan is emitted",
                "oracle": {"observable": "semantic bundle", "expected": "plan-ready", "forbidden": ["future evidence"]},
                "assertion_ids": ["ASSERT-COMPILE"],
            }],
            "failure_intents": [{
                "obligation_ids": [oid],
                "failure_family": "expected-red",
                "selector_intent": selector,
                "expected_outcome": "fail",
                "failure_id": "COMPILE-RED",
            }],
            "slice_hints": [hint],
        },
        "v4-atomic-recall": {"supported_obligation_ids": [oid], "invented_obligation_ids": [], "source_gap_claims": []},
        "v4": {
            "covered_obligation_ids": [oid],
            "missing_obligation_ids": [],
            "invented_obligation_ids": [],
            "misaligned_acceptance_ids": [],
            "oracle_alignment": {"status": "aligned"},
            "repairs": [],
        },
    }


def test_plan_ready_contains_preflight_contracts_and_worker_receipts(tmp_path: Path) -> None:
    root, req, owner, selector = _repo(tmp_path)
    out = root / "plan"
    result = compile_plan(requirements=req, out_dir=out, worker_cache=_cache(owner, selector))
    assert result["status"] == "plan-ready"
    bundle = json.loads((out / "semantic-plan-bundle.v1.json").read_text(encoding="utf-8"))
    for item in (bundle["acceptances"][0], bundle["slices"][0]):
        assert item["complexity_class"] == "simple"
        assert item["verification_lane"] == "unit"
        assert item["context_lookup_required"] is False
        assert item["context_lookup_reason"]
        assert item["minimum_red_scope"]
        assert item["upgrade_conditions"]
    receipts = list((out / ".compiler-work" / "worker-receipts").glob("*.json"))
    assert receipts
    decoded = [json.loads(path.read_text(encoding="utf-8")) for path in receipts]
    assert all(item["schema"] == "vdd.semantic-worker-receipt.v1" for item in decoded)
    assert all(item["input_sha256"].startswith("sha256:") and item["prompt_sha256"].startswith("sha256:") for item in decoded)
    assert all(item["worker_authority"] == "read-only-semantic-candidate" and item["authorizes"] == [] for item in decoded)


def test_resume_from_completed_plan_revalidates_without_worker_cache(tmp_path: Path) -> None:
    root, req, owner, selector = _repo(tmp_path)
    out = root / "plan"
    first = compile_plan(requirements=req, out_dir=out, worker_cache=_cache(owner, selector))
    assert first["status"] == "plan-ready"
    resumed = compile_plan(requirements=req, out_dir=out, resume_from="first-failed-stage")
    assert resumed["status"] == "plan-ready"
    assert resumed["resumed"] is True
    assert resumed["resume_from"] == "first-failed-stage"
    assert resumed["resume_strategy"] == "validated-completed-state"


def test_public_cli_is_the_canonical_plan_ready_entry(tmp_path: Path) -> None:
    # ADR-0041: exercise the repository-owned entry as a process, not an internal import.
    root, req, owner, selector = _repo(tmp_path)
    out = root / "plan"
    cache_path = root / "worker-cache.json"
    cache_path.write_text(json.dumps(_cache(owner, selector)), encoding="utf-8", newline="\n")
    repository_root = Path(__file__).resolve().parents[5]
    entry = repository_root / "scripts" / "vdd" / "compile_plan.py"
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    completed = subprocess.run(
        [
            sys.executable,
            str(entry),
            "--requirements",
            str(req),
            "--out-dir",
            str(out),
            "--profile",
            "standard",
            "--worker-cache",
            str(cache_path),
        ],
        cwd=str(root),
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    result = json.loads([line for line in completed.stdout.splitlines() if line.strip()][-1])
    assert result["status"] == "plan-ready"
    assert (out / "compiler-state.v1.json").is_file()
