"""Harden live semantic-worker transport with bounded transient retries.

The canonical compiler and its one-shot semantic repair lane remain authoritative.
This compatibility layer only makes the Codex transport reliable for machine-
readable V1/V3 output: it requests native structured output when supported,
uses a larger but bounded timeout for schema repair, lowers repair reasoning cost,
removes stale output before each invocation, and retries transient worker exits
at most three times. It never guesses or rewrites malformed JSON locally.
"""
from __future__ import annotations

from semantic_progress import worker_call, stage_call

import json
import os
from pathlib import Path
import re
import sys
import tomllib
from typing import Any, Mapping

import semantic_compiler_gate as gate

sc = gate.sc
_BASE_INVOKE_WORKER = gate._ORIGINAL_INVOKE_WORKER
_NORMAL_TIMEOUT_SECONDS = 180
_REPAIR_TIMEOUT_SECONDS = 300
_MAX_TRANSPORT_ATTEMPTS = 3  # user-approved automatic retry budget
_TRACE_LIMIT = 500


def _codex_config_path() -> Path:
    """Return the active user config without treating its contents as VDD input."""
    home = os.environ.get("CODEX_HOME")
    return Path(home) / "config.toml" if home else Path.home() / ".codex" / "config.toml"


def codex_worker_isolation_args() -> list[str]:
    """Disable configured MCP tools while retaining model/provider configuration."""
    names: list[str] = []
    try:
        document = tomllib.loads(_codex_config_path().read_text(encoding="utf-8"))
        configured = document.get("mcp_servers")
        if isinstance(configured, dict):
            names = sorted(name for name in configured if isinstance(name, str) and name)
    except (OSError, tomllib.TOMLDecodeError):
        pass

    # This CLI version does not expose `skills` as a feature flag accepted by
    # `--disable`; use the equivalent typed configuration override instead.
    args = ["-c", "features.skills=false", "--ignore-rules"]
    for name in names:
        # Codex v0.153.4 accepts dotted overrides for TOML bare keys but
        # misparses quoted keys here as incomplete MCP transport tables.
        if re.fullmatch(r"[A-Za-z0-9_-]+", name):
            args.extend(["-c", f"mcp_servers.{name}.enabled=false"])
    return args


def _bounded_trace(trace: str) -> str:
    text = str(trace or "").strip()
    if len(text) <= _TRACE_LIMIT:
        return text
    marker = "\n...[trace truncated]...\n"
    tail_length = 300
    head_length = _TRACE_LIMIT - len(marker) - tail_length
    return text[:head_length] + marker + text[-tail_length:]


def _preserve_prior_output(output: Path) -> None:
    """Make a previous diagnostic append-only before another transport attempt."""
    if not output.exists():
        return
    if not output.is_file():
        raise ValueError(f"semantic worker output path is not a file: {output}")
    suffix = 1
    historical = output.with_name(f"{output.stem}.prior-{suffix}.json")
    while historical.exists():
        suffix += 1
        historical = output.with_name(f"{output.stem}.prior-{suffix}.json")
    output.rename(historical)


def _schema_kind(stage: str) -> str | None:
    if stage.startswith("v1-"):
        return "v1"
    if stage == "v3" or stage.startswith("v3-schema-repair"):
        return "v3"
    return None


def _string_array(*, nonempty: bool = False) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "array", "items": {"type": "string"}}
    if nonempty:
        schema["minItems"] = 1
    return schema


def _worker_output_schema(stage: str) -> dict[str, Any] | None:
    kind = _schema_kind(stage)
    if kind == "v1":
        obligation = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "source_refs": _string_array(nonempty=True),
                "subject": {"type": "string", "minLength": 1},
                "trigger": {"type": "string", "minLength": 1},
                "state_before": {"type": "string", "minLength": 1},
                "state_after": {"type": "string", "minLength": 1},
                "expected_behavior": {"type": "string", "minLength": 1},
                "observable_result": {"type": "string", "minLength": 1},
                "forbidden_result": _string_array(),
                "requirement_type": {"type": "string", "enum": ["Product", "Platform", "Governance"]},
                "obligation_kind": {"type": "string", "enum": ["behavior", "quality", "constraint", "governance"]},
                "unresolved_fragments": _string_array(),
                "status": {"type": "string", "enum": ["active", "deferred", "not_applicable"]},
                "depends_on": _string_array(),
            },
            "required": [
                "source_refs", "subject", "trigger", "state_before", "state_after",
                "expected_behavior", "observable_result", "forbidden_result",
                "requirement_type", "obligation_kind", "unresolved_fragments",
                "status", "depends_on",
            ],
        }
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {"obligations": {"type": "array", "minItems": 1, "items": obligation}},
            "required": ["obligations"],
        }

    if kind == "v3":
        acceptance = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "obligation_ids": {**_string_array(nonempty=True), "maxItems": 1},
                "source_refs": _string_array(nonempty=True),
                "given": {"type": "string", "minLength": 1},
                "when": {"type": "string", "minLength": 1},
                "then": {"type": "string", "minLength": 1},
                "oracle": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "observable": {"type": "string", "minLength": 1},
                        "expected": {"type": "string", "minLength": 1},
                        "forbidden": _string_array(),
                    },
                    "required": ["observable", "expected", "forbidden"],
                },
                "assertion_ids": _string_array(nonempty=True),
            },
            "required": ["obligation_ids", "source_refs", "given", "when", "then", "oracle", "assertion_ids"],
        }
        failure = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "obligation_ids": {**_string_array(nonempty=True), "maxItems": 1},
                "failure_family": {"type": "string", "enum": sorted(sc.FAILURE_FAMILIES)},
                "selector_intent": {"type": "string", "minLength": 1},
                "expected_outcome": {"type": "string", "enum": ["fail"]},
                "failure_id": {"type": "string", "minLength": 1},
            },
            "required": ["obligation_ids", "failure_family", "selector_intent", "expected_outcome", "failure_id"],
        }
        argv = {
            "type": "array",
            "minItems": 1,
            "items": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
        }
        hint = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "obligation_ids": {**_string_array(nonempty=True), "maxItems": 1},
                "production_owners": _string_array(nonempty=True),
                "verification_lane": {"type": "string", "enum": sorted(sc.LANES)},
                "behavior_change": {"type": "string", "minLength": 1},
                "affected_subjects": _string_array(nonempty=True),
                "state_transition": {"type": "string", "minLength": 1},
                "rollback_scope": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "production_paths": _string_array(nonempty=True),
                        "state_or_schema_compatibility": {"type": "string", "minLength": 1},
                    },
                    "required": ["production_paths", "state_or_schema_compatibility"],
                },
                "allowed_write_paths": _string_array(),
                "execution_snapshot_paths": _string_array(nonempty=True),
                "planned_new_files": _string_array(),
                "terminal_predicate": {"type": "string", "minLength": 1},
                "forbidden_paths": _string_array(),
                "validation_commands": argv,
            },
            "required": [
                "obligation_ids", "production_owners", "verification_lane", "behavior_change",
                "affected_subjects", "state_transition", "rollback_scope", "allowed_write_paths",
                "execution_snapshot_paths", "planned_new_files", "terminal_predicate",
                "forbidden_paths", "validation_commands",
            ],
        }
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "acceptances": {"type": "array", "minItems": 1, "items": acceptance},
                "failure_intents": {"type": "array", "minItems": 1, "items": failure},
                "slice_hints": {"type": "array", "minItems": 1, "items": hint},
            },
            "required": ["acceptances", "failure_intents", "slice_hints"],
        }
    return None


def _schema_path(out_dir: Path, stage: str, schema: Mapping[str, Any]) -> Path:
    digest = sc.sha256_value(schema)[7:19]
    path = out_dir / ".compiler-work" / "worker-schemas" / f"{_schema_kind(stage)}-{digest}.json"
    sc.atomic_json(path, dict(schema))
    return path


def _unsupported_output_schema(trace: str) -> bool:
    lowered = trace.casefold()
    return "output-schema" in lowered and any(
        token in lowered
        for token in ("unexpected argument", "unrecognized option", "unknown option", "unknown argument")
    )


def _source_role_contract(stage: str) -> str:
    """ADR-0041: source coverage concerns obligations, not every descriptive fact."""
    if not (stage.startswith("v1-") or stage.startswith("v4-atomic-recall")):
        return ""
    return (
        "\n\nSOURCE ROLE CONTRACT v1: distinguish required target behavior, explicit verification duties, "
        "and descriptive current-state context using the complete frozen source. Textual presence alone does not "
        "make a fact an active implementation obligation. Existing defects, intentionally incomplete stubs and "
        "pre-change failure descriptions belong in state_before/Given and negative-test context for the required "
        "transition; do not require implementing, restoring or preserving the defect as expected_behavior or "
        "state_after. An explicit requirement to capture or verify a baseline IS an obligation: preserve its "
        "verification action and before/after scope without turning the observed defect into the desired product. "
        "Do not discard temporal requirements merely because they say before, existing or baseline. "
        "For source recall, report gaps only for independently required behavior or verification duties. "
        "A descriptive fact already represented as transition context is not a source gap. Classify a candidate "
        "that invents a duty to preserve an unwanted current state as invented, even if its words occur in source. "
        "For gap repair, read the cited source before adding a claim: preserve an actual verification duty, never "
        "manufacture a product duty from a descriptive claim. Never omit a real required behavior to improve metrics."
    )


def transport_invoke_worker(
    *,
    root: Path,
    out_dir: Path,
    stage: str,
    payload: Mapping[str, Any],
    prompt: str,
    worker_cache: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    """Mirror the canonical worker seam with bounded structured-output transport."""
    role_contract = _source_role_contract(stage)
    cache_payload = {"source_role_contract": role_contract, "input": payload} if role_contract else payload
    cache_dir = out_dir / ".compiler-cache"
    cache_path = cache_dir / sc._worker_cache_key(stage, cache_payload)
    if cache_path.is_file():
        value = json.loads(cache_path.read_text(encoding="utf-8"))
        if not isinstance(value, Mapping):
            raise ValueError("worker cache is malformed")
        return value
    if worker_cache and stage in worker_cache:
        value = worker_cache[stage]
        if not isinstance(value, Mapping):
            raise ValueError(f"injected worker cache {stage} must be object")
        sc.atomic_json(cache_path, value)
        return value

    scripts = root / "scripts" / "sc"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    try:
        from _llm_backend import run_llm_exec, resolve_llm_backend
    except ImportError as exc:
        raise RuntimeError("shared LLM backend is unavailable") from exc

    work = out_dir / ".compiler-work"
    # Output messages are diagnostics, not cache authority.  Bind the filename
    # to the exact worker input so a later selective repair cannot overwrite a
    # retained message from a different semantic input for the same stage.
    output = work / f"{sc._worker_cache_key(stage, payload)[:-5]}-last-message.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    _preserve_prior_output(output)

    full_prompt = (
        "You are a read-only semantic compiler worker. Do not modify files. "
        "Return JSON only. Do not invent requirements or runtime evidence.\n\n"
        + prompt
        + role_contract
        + "\n\nINPUT:\n"
        + json.dumps(payload, ensure_ascii=False, sort_keys=True)
    )
    backend = resolve_llm_backend(None)
    is_repair = stage.endswith("-schema-repair")
    timeout_sec = _REPAIR_TIMEOUT_SECONDS if is_repair else _NORMAL_TIMEOUT_SECONDS
    reasoning = "medium" if is_repair else "high"
    schema = _worker_output_schema(stage)
    extra_args: list[str] = []
    if backend == "codex-cli" and schema is not None:
        extra_args = ["--output-schema", str(_schema_path(out_dir, stage, schema))]

    def execute(extra: list[str]) -> tuple[int, str, list[str]]:
        return worker_call(run_llm_exec, progress_dir=out_dir, progress_stage=stage,
            backend=backend,
            root=root,
            prompt=full_prompt,
            output_last_message=output,
            timeout_sec=timeout_sec,
            codex_configs=[f'model_reasoning_effort="{reasoning}"'],
            codex_sandbox="read-only",
            codex_extra_args=[*codex_worker_isolation_args(), *extra],
        )

    traces: list[str] = []
    code = 1
    trace = ""
    argv: list[str] = []
    for attempt in range(1, _MAX_TRANSPORT_ATTEMPTS + 1):
        _preserve_prior_output(output)
        code, trace, argv = execute(extra_args)
        if code != 0 and extra_args and _unsupported_output_schema(trace):
            # Compatibility fallback for an older Codex CLI. This remains a
            # transport fallback inside the same attempt.
            _preserve_prior_output(output)
            code, trace, argv = execute([])
        if code == 0 and output.is_file():
            break
        traces.append(f"attempt {attempt}: {_bounded_trace(trace)}")
    if code != 0 or not output.is_file():
        raise RuntimeError(f"semantic worker {stage} failed after {_MAX_TRANSPORT_ATTEMPTS} attempts: " + "\n".join(traces))

    value = sc._parse_json_output(output.read_text(encoding="utf-8"))
    sc.atomic_json(cache_path, value)
    return value


def install() -> None:
    # gate.normative_invoke_worker resolves this global on each initial and repair
    # call. Replacing only the transport preserves the one-shot semantic repair
    # policy and all existing deterministic validators.
    gate._ORIGINAL_INVOKE_WORKER = transport_invoke_worker


install()
