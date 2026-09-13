from __future__ import annotations

import json
from pathlib import Path
import sys
import types

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import semantic_worker_transport_patch as transport


def test_bounded_trace_preserves_failure_tail() -> None:
    trace = "header\n" + ("prompt" * 100) + "\nerror: invalid output schema keyword uniqueItems"
    bounded = transport._bounded_trace(trace)
    assert len(bounded) <= 500
    assert bounded.startswith("header")
    assert "[trace truncated]" in bounded
    assert bounded.endswith("error: invalid output schema keyword uniqueItems")


def test_v1_and_v3_have_native_structured_output_schemas() -> None:
    v1 = transport._worker_output_schema("v1-FR-1")
    v3 = transport._worker_output_schema("v3-schema-repair")
    assert v1 is not None and v1["required"] == ["obligations"]
    assert v3 is not None and set(v3["required"]) == {"acceptances", "failure_intents", "slice_hints"}
    family = v3["properties"]["failure_intents"]["items"]["properties"]["failure_family"]
    assert "expected-red" in family["enum"]
    assert "semantic-contract-gap" in family["enum"]


def test_codex_worker_isolation_disables_each_configured_mcp_without_changing_provider(
    tmp_path: Path, monkeypatch
) -> None:
    config = tmp_path / "config.toml"
    config.write_text(
        "[mcp_servers.context7]\ncommand = 'context7'\n"
        "[mcp_servers.\"sequential-thinking\"]\ncommand = 'thinking'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(transport, "_codex_config_path", lambda: config)

    args = transport.codex_worker_isolation_args()

    assert args[:3] == ["-c", "features.skills=false", "--ignore-rules"]
    assert "mcp_servers.context7.enabled=false" in args
    assert "mcp_servers.sequential-thinking.enabled=false" in args
    assert "--ignore-user-config" not in args


def test_schema_repair_transport_uses_bounded_longer_timeout_and_medium_reasoning(tmp_path: Path, monkeypatch) -> None:
    calls: list[dict] = []

    def run_llm_exec(**kwargs):
        calls.append(kwargs)
        output = kwargs["output_last_message"]
        assert not output.exists(), "stale output must be removed before live execution"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({"acceptances": [], "failure_intents": [], "slice_hints": []}) + "\n", encoding="utf-8")
        return 0, "ok", ["codex", "exec"]

    fake = types.SimpleNamespace(
        resolve_llm_backend=lambda _raw: "codex-cli",
        run_llm_exec=run_llm_exec,
    )
    monkeypatch.setitem(sys.modules, "_llm_backend", fake)

    stale = tmp_path / "plan" / ".compiler-work" / "v3-schema-repair-last-message.json"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text("stale", encoding="utf-8")

    result = transport.transport_invoke_worker(
        root=tmp_path,
        out_dir=tmp_path / "plan",
        stage="v3-schema-repair",
        payload={"original_stage": "v3", "input": {"obligations": []}, "validator_findings": ["x"]},
        prompt="Repair the V3 JSON object.",
    )
    assert set(result) == {"acceptances", "failure_intents", "slice_hints"}
    assert len(calls) == 1
    call = calls[0]
    assert call["timeout_sec"] == 300
    assert 'model_reasoning_effort="medium"' in call["codex_configs"]
    assert "features.skills=false" in call["codex_extra_args"]
    assert "--output-schema" in call["codex_extra_args"]
    schema_path = Path(call["codex_extra_args"][call["codex_extra_args"].index("--output-schema") + 1])
    assert schema_path.is_file()


def test_old_codex_without_output_schema_falls_back_only_at_transport_layer(tmp_path: Path, monkeypatch) -> None:
    calls: list[list[str]] = []

    def run_llm_exec(**kwargs):
        extra = list(kwargs.get("codex_extra_args") or [])
        calls.append(extra)
        if "--output-schema" in extra:
            return 2, "error: unexpected argument '--output-schema'", ["codex", "exec"]
        output = kwargs["output_last_message"]
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({"obligations": [{"subject": "x"}]}) + "\n", encoding="utf-8")
        return 0, "ok", ["codex", "exec"]

    fake = types.SimpleNamespace(
        resolve_llm_backend=lambda _raw: "codex-cli",
        run_llm_exec=run_llm_exec,
    )
    monkeypatch.setitem(sys.modules, "_llm_backend", fake)

    result = transport.transport_invoke_worker(
        root=tmp_path,
        out_dir=tmp_path / "plan",
        stage="v1-FR-1",
        payload={"source": {"source_ref": "req.md#FR-1"}},
        prompt="Extract obligations.",
    )
    assert result["obligations"][0]["subject"] == "x"
    assert len(calls) == 2
    assert "--output-schema" in calls[0]
    assert "--output-schema" not in calls[1]
    assert "features.skills=false" in calls[1]
