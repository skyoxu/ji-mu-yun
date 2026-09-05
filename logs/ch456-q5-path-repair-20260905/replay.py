"""ADR-0041: offline replay of the captured Q5 producer-side path conflict."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "logs/ch456-live-blind-r900-1ee886c6"
sys.path.insert(0, str(ROOT / ".agents/skills/vdd-execution-plan/scripts"))


def no_live(*args, **kwargs):
    raise AssertionError("offline replay must not call a live backend")


sys.modules["_llm_backend"] = SimpleNamespace(run_llm_exec=no_live, resolve_llm_backend=no_live)
import semantic_compiler_authority  # noqa: E402,F401
import semantic_compiler_gate as gate  # noqa: E402


def main():
    plan = EVIDENCE / "live-blind/plan"
    obligations = json.loads((plan / "obligations.v1.json").read_text(encoding="utf-8"))
    raw = json.loads((plan / ".compiler-work/v3-last-message.json").read_text(encoding="utf-8"))
    prefix = "benchmarks/ch456-live-blind/idempotency-ledger-v1/"
    owner = prefix + "src/idempotency_ledger.py"
    protected = [prefix + "tests/cases.json", prefix + "tests/test_idempotency_ledger.py"]
    assert any(owner in h["execution_snapshot_paths"] for h in raw["slice_hints"])
    with tempfile.TemporaryDirectory(prefix="ch456-q5-offline-") as tmp:
        root = Path(tmp)
        (root / ".agents").mkdir()
        (root / "AGENTS.md").write_text("Offline replay root\n", encoding="utf-8")
        # V3 runs before RED authoring: preserve original source/fixture bytes,
        # but do not materialize the later generated RED test in this V3 root.
        for relative in ("requirements.md", "src/idempotency_ledger.py", "tests/cases.json"):
            target = root / prefix / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((EVIDENCE / "idempotency-ledger-v1" / relative).read_bytes())
        index = gate.sc.build_source_index(root, root / prefix / "requirements.md")
        assert gate.sc.source_preflight(root, index)["valid"]
        acceptances, failures, hints = gate.sc.compile_acceptances(
            root=root, out_dir=root / "plan", obligations=obligations, worker_cache={"v3": raw})
        slices, _ = gate.sc.partition_slices(obligations, acceptances, failures, hints)
        assert len(slices) == 1
        selected = slices[0]
        assert selected["production_owners"] == selected["allowed_write_paths"] == [owner]
        assert selected["execution_snapshot_paths"] == protected
        assert len(acceptances) == len(failures) == 11
        assert sorted(a["oracle"]["expected"] for a in acceptances) == sorted(a["oracle"]["expected"] for a in raw["acceptances"])
        assert {f["failure_id"] for f in failures} == {f["failure_id"] for f in raw["failure_intents"]}
        print(json.dumps({"status": "pass", "scope": "offline V3-to-V6 path projection",
                          "live_calls": 0, "acceptances": len(acceptances), "failure_intents": len(failures),
                          "slices": len(slices), "allowed": [owner], "protected": protected,
                          "live_green_proven": False}, sort_keys=True))


if __name__ == "__main__":
    main()
