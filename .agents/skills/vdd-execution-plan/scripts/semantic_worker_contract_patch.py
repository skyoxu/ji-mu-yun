"""Strengthen live semantic-worker contracts without weakening canonical truth.

The deterministic compiler owns all semantic authority. This patch only improves
its model seam: V1/V3 prompts state the exact JSON contract up front, V3 output is
validated deeply enough to enter the existing one-shot schema-repair lane, and a
failed repair re-exports its exact deterministic findings for diagnostics.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import semantic_compiler_gate as gate

_BASE_SCHEMA_FINDINGS = gate._worker_schema_findings
_BASE_NORMATIVE_INVOKE = gate.normative_invoke_worker


def _string_list(value: Any, *, nonempty: bool = False) -> bool:
    return (
        isinstance(value, list)
        and (bool(value) or not nonempty)
        and all(isinstance(item, str) and bool(item.strip()) for item in value)
    )


def _argv_commands(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(
            isinstance(command, list)
            and bool(command)
            and all(isinstance(part, str) and bool(part) for part in command)
            for command in value
        )
    )


def _worker_schema_findings(stage: str, value: Mapping[str, Any]) -> list[str]:
    """Add field-level V3 checks early enough for one deterministic repair."""
    findings = list(_BASE_SCHEMA_FINDINGS(stage, value))
    if stage != "v3":
        return findings

    acceptances = value.get("acceptances")
    if isinstance(acceptances, list):
        for index, raw in enumerate(acceptances):
            prefix = f"worker-output:acceptances[{index}]"
            if not isinstance(raw, Mapping):
                findings.append(f"{prefix}:not-object")
                continue
            if not _string_list(raw.get("obligation_ids"), nonempty=True):
                findings.append(f"{prefix}:obligation_ids:nonempty-string-list-required")
            if not _string_list(raw.get("source_refs"), nonempty=True):
                findings.append(f"{prefix}:source_refs:nonempty-string-list-required")
            for field in ("given", "when", "then"):
                item = raw.get(field)
                if not isinstance(item, str) or not item.strip():
                    findings.append(f"{prefix}:{field}:nonempty-string-required")
            oracle = raw.get("oracle")
            if not isinstance(oracle, Mapping):
                findings.append(f"{prefix}:oracle:object-required")
            else:
                for field in ("observable", "expected"):
                    item = oracle.get(field)
                    if not isinstance(item, str) or not item.strip():
                        findings.append(f"{prefix}:oracle.{field}:nonempty-string-required")
                forbidden = oracle.get("forbidden")
                if not isinstance(forbidden, list) or any(not isinstance(item, str) for item in forbidden):
                    findings.append(f"{prefix}:oracle.forbidden:string-list-required")
            if not _string_list(raw.get("assertion_ids"), nonempty=True):
                findings.append(f"{prefix}:assertion_ids:nonempty-string-list-required")

    failures = value.get("failure_intents")
    if isinstance(failures, list):
        allowed = sorted(gate.sc.FAILURE_FAMILIES)
        allowed_text = ",".join(allowed)
        for index, raw in enumerate(failures):
            prefix = f"worker-output:failure_intents[{index}]"
            if not isinstance(raw, Mapping):
                findings.append(f"{prefix}:not-object")
                continue
            if not _string_list(raw.get("obligation_ids"), nonempty=True):
                findings.append(f"{prefix}:obligation_ids:nonempty-string-list-required")
            family = raw.get("failure_family")
            if family not in gate.sc.FAILURE_FAMILIES:
                findings.append(f"{prefix}:failure_family:invalid:allowed={allowed_text}")
            selector = raw.get("selector_intent")
            if not isinstance(selector, str) or not selector.strip():
                findings.append(f"{prefix}:selector_intent:nonempty-string-required")
            if raw.get("expected_outcome") != "fail":
                findings.append(f"{prefix}:expected_outcome:must-equal-fail")
            failure_id = raw.get("failure_id")
            if not isinstance(failure_id, str) or not failure_id.strip():
                findings.append(f"{prefix}:failure_id:nonempty-string-required")

    hints = value.get("slice_hints")
    if isinstance(hints, list):
        for index, raw in enumerate(hints):
            prefix = f"worker-output:slice_hints[{index}]"
            if not isinstance(raw, Mapping):
                findings.append(f"{prefix}:not-object")
                continue
            if not _string_list(raw.get("obligation_ids"), nonempty=True):
                findings.append(f"{prefix}:obligation_ids:nonempty-string-list-required")
            if not _string_list(raw.get("production_owners"), nonempty=True):
                findings.append(f"{prefix}:production_owners:nonempty-string-list-required")
            if raw.get("verification_lane") not in gate.sc.LANES:
                findings.append(f"{prefix}:verification_lane:invalid")
            for field in ("behavior_change", "state_transition", "terminal_predicate"):
                item = raw.get(field)
                if not isinstance(item, str) or not item.strip():
                    findings.append(f"{prefix}:{field}:nonempty-string-required")
            if not _string_list(raw.get("affected_subjects"), nonempty=True):
                findings.append(f"{prefix}:affected_subjects:nonempty-string-list-required")
            rollback = raw.get("rollback_scope")
            if not isinstance(rollback, Mapping):
                findings.append(f"{prefix}:rollback_scope:object-required")
            else:
                if not _string_list(rollback.get("production_paths"), nonempty=True):
                    findings.append(f"{prefix}:rollback_scope.production_paths:nonempty-string-list-required")
                compatibility = rollback.get("state_or_schema_compatibility")
                if not isinstance(compatibility, str) or not compatibility.strip():
                    findings.append(f"{prefix}:rollback_scope.state_or_schema_compatibility:nonempty-string-required")
            for field in ("allowed_write_paths", "planned_new_files", "forbidden_paths"):
                item = raw.get(field)
                if not isinstance(item, list) or any(not isinstance(entry, str) or not entry for entry in item):
                    findings.append(f"{prefix}:{field}:string-list-required")
            if not _string_list(raw.get("execution_snapshot_paths"), nonempty=True):
                findings.append(f"{prefix}:execution_snapshot_paths:nonempty-string-list-required")
            if not _argv_commands(raw.get("validation_commands")):
                findings.append(f"{prefix}:validation_commands:nonempty-argv-array-list-required")
    return findings


def _augment_prompt(stage: str, prompt: str) -> str:
    if stage.startswith("v1-"):
        return prompt + (
            "\n\nSTRICT V1 JSON CONTRACT: every obligation field is mandatory. "
            "source_refs, forbidden_result, unresolved_fragments, and depends_on MUST be JSON arrays of strings; "
            "use depends_on=[] when the source declares no dependency. For status='active', unresolved_fragments MUST be []. "
            "Never use null, objects, or prose in place of those arrays."
        )
    if stage == "v3":
        allowed = ", ".join(sorted(gate.sc.FAILURE_FAMILIES))
        return prompt + (
            "\n\nSTRICT V3 JSON CONTRACT: failure_family MUST be exactly one of: "
            + allowed
            + ". expected_outcome MUST equal 'fail'. All obligation_ids/source_refs/assertion_ids/path fields described as [] "
            "must be JSON arrays, and validation_commands must be a non-empty array of argv arrays. "
            "Do not invent new failure-family names or prose aliases."
        )
    return prompt


def _repair_diagnostics(*, out_dir: Path, stage: str, payload: Mapping[str, Any], prompt: str) -> list[str]:
    input_sha = gate.sc.sha256_value(payload)
    prompt_sha = gate.sc.sha256_bytes(prompt.encode("utf-8"))
    path = out_dir / ".compiler-work" / "worker-receipts" / (
        f"{stage}-{input_sha[7:19]}-{prompt_sha[7:19]}.json"
    )
    if not path.is_file():
        return []
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return []
    findings = value.get("schema_findings") if isinstance(value, Mapping) else None
    return [str(item) for item in findings] if isinstance(findings, list) else []


def normative_invoke_worker(
    *,
    root: Path,
    out_dir: Path,
    stage: str,
    payload: Mapping[str, Any],
    prompt: str,
    worker_cache: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    augmented = _augment_prompt(stage, prompt)
    try:
        return _BASE_NORMATIVE_INVOKE(
            root=root,
            out_dir=out_dir,
            stage=stage,
            payload=payload,
            prompt=augmented,
            worker_cache=worker_cache,
        )
    except RuntimeError as exc:
        message = str(exc)
        if "semantic worker schema repair failed" in message or "repeated deterministic semantic worker failure" in message:
            details = _repair_diagnostics(out_dir=out_dir, stage=stage, payload=payload, prompt=augmented)
            if details:
                raise RuntimeError(message + ": " + json.dumps(details, ensure_ascii=False, sort_keys=True)) from exc
        raise


def install() -> None:
    gate._worker_schema_findings = _worker_schema_findings
    gate.normative_invoke_worker = normative_invoke_worker
    gate.sc.invoke_worker = normative_invoke_worker


install()
