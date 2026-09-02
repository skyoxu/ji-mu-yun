from __future__ import annotations

from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import semantic_compiler_gate as gate
import semantic_feasibility_patch  # noqa: F401  # installs the complete stable worker stack
import semantic_worker_v3_execution_contract_patch as v3_execution
import semantic_worker_v4_domain_patch as v4_domain


def test_v4_specialization_composes_over_v3_execution_transport() -> None:
    # V4 is intentionally the final transport specialization in the stable import
    # order, but non-V4 calls must continue through every previously installed V3
    # validator/repair layer instead of jumping back to raw transport.
    assert gate._ORIGINAL_INVOKE_WORKER is v4_domain.v4_transport_invoke_worker
    assert v4_domain._BASE_TRANSPORT is v3_execution.execution_contract_transport


def test_v4_non_atomic_stage_delegates_to_installed_v3_chain(monkeypatch, tmp_path: Path) -> None:
    seen: list[str] = []

    def fake_v3_chain(**kwargs):
        seen.append(str(kwargs["stage"]))
        return {"ok": True}

    monkeypatch.setattr(v4_domain, "_BASE_TRANSPORT", fake_v3_chain)
    result = v4_domain.v4_transport_invoke_worker(
        root=tmp_path,
        out_dir=tmp_path / "plan",
        stage="v3-schema-repair",
        payload={"input": {"obligations": []}},
        prompt="repair",
        worker_cache=None,
    )
    assert result == {"ok": True}
    assert seen == ["v3-schema-repair"]
