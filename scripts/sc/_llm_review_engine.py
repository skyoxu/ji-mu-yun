#!/usr/bin/env python3
"""
Engine for sc-llm-review.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
import tomllib
from pathlib import Path
from typing import Any

from _acceptance_artifacts import build_acceptance_evidence
from _deterministic_review import DETERMINISTIC_AGENTS, build_deterministic_review
from _llm_review_acceptance import build_acceptance_semantic_context, read_text, strip_emoji, truncate
from _llm_review_cli import (
    apply_delivery_profile_defaults,
    apply_prompt_budget,
    build_parser,
    parse_agent_timeout_overrides,
    resolve_agents,
    summary_base,
    validate_args,
)
from _llm_review_exec import auto_resolve_commit_for_task, build_diff_context, run_codex_exec
from _llm_backend import inspect_llm_backend
from _llm_review_identity import (
    LLM_INPUT_IDENTITY_SCHEMA,
    LLM_REVIEW_METRICS_SCHEMA,
    LLM_RUNTIME_IDENTITY_SCHEMA,
    canonical_hash,
)
from _llm_review_models import ReviewResult
from _llm_review_prompting import (
    agent_prompt,
    build_task_context,
    build_threat_model_context,
    normalize_host_safe_needs_fix,
    parse_verdict,
    resolve_claude_agents_root,
    resolve_threat_model,
)
from _security_profile import build_security_profile_context, resolve_security_profile, security_profile_payload
from _taskmaster import resolve_triplet
from _util import ci_dir, repo_rel, repo_root, write_json, write_text


_SEMANTIC_AGENT = "semantic-equivalence-auditor"
_DEFERRED_REASON_CODE = "deferred_until_prior_reviewers_clean"


def _sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _canonical_hash(value: Any) -> str:
    return canonical_hash(value)


def _hash_optional_file(path: Path) -> str:
    try:
        return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "absent"
    except OSError:
        return "unresolved"


def _command_version_sha256(executable: str) -> str:
    try:
        result = subprocess.run(
            [executable, "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return "unresolved"
    if result.returncode != 0 or not result.stdout:
        return "unresolved"
    return "sha256:" + hashlib.sha256(bytes(result.stdout)).hexdigest()


def _backend_adapter_sha256() -> str:
    payload = bytearray()
    for name in ("_llm_backend.py", "_llm_review_exec.py"):
        path = Path(__file__).resolve().with_name(name)
        try:
            payload.extend(name.encode("ascii"))
            payload.extend(b"\0")
            payload.extend(path.read_bytes())
            payload.extend(b"\0")
        except OSError:
            return "unresolved"
    return "sha256:" + hashlib.sha256(bytes(payload)).hexdigest()


def _runtime_input_descriptor(args: argparse.Namespace) -> dict[str, Any]:
    backend = str(getattr(args, "llm_backend", "") or "").strip()
    model = "unresolved"
    config_sha256 = "not-applicable"
    executable_sha256 = "not-applicable"
    version_sha256 = "not-applicable"
    endpoint_sha256 = "not-applicable"
    sdk_version = ""
    errors: list[str] = []
    adapter_sha256 = _backend_adapter_sha256()
    if adapter_sha256 == "unresolved":
        errors.append("backend_adapter_unreadable")
    if backend == "openai-api":
        backend_info = inspect_llm_backend(backend)
        model = str(backend_info.get("model") or "unresolved")
        endpoint_sha256 = str(backend_info.get("endpoint_sha256") or "unresolved")
        sdk_version = str(backend_info.get("sdk_version") or "unresolved")
        version_sha256 = str(backend_info.get("sdk_version_sha256") or "unresolved")
        if sdk_version == "unresolved" or version_sha256 == "unresolved":
            errors.append("openai_sdk_unresolved")
        # Credential/account identity is deliberately not persisted. Without an
        # explicit non-secret cache scope, API results are not reusable.
        errors.append("openai_credential_scope_unbound")
    elif backend == "codex-cli":
        codex_root = Path(str(os.environ.get("CODEX_HOME") or (Path.home() / ".codex")))
        config_path = codex_root / "config.toml"
        config_sha256 = _hash_optional_file(config_path)
        executable = shutil.which("codex")
        if executable:
            executable_sha256 = _hash_optional_file(Path(executable))
            version_sha256 = _command_version_sha256(executable)
        else:
            executable_sha256 = "unresolved"
            version_sha256 = "unresolved"
            errors.append("codex_executable_unresolved")
        try:
            config_payload = tomllib.loads(config_path.read_text(encoding="utf-8")) if config_path.is_file() else {}
            model = str(config_payload.get("model") or "").strip() or "unresolved"
        except (OSError, UnicodeError, tomllib.TOMLDecodeError):
            model = "unresolved"
            errors.append("codex_config_unreadable")
        if config_sha256 in {"absent", "unresolved"}:
            errors.append("codex_config_unbound")
        if model == "unresolved":
            errors.append("codex_model_unresolved")
        if executable_sha256 == "unresolved":
            errors.append("codex_executable_unreadable")
        if version_sha256 == "unresolved":
            errors.append("codex_version_unresolved")
    else:
        errors.append("backend_unresolved")
    return {
        "schema_version": LLM_RUNTIME_IDENTITY_SCHEMA,
        "backend": backend,
        "model": model,
        "reasoning_effort": str(getattr(args, "model_reasoning_effort", "") or "").strip(),
        "sandbox": "read-only",
        "prompt_transport": "stdin",
        "config_sha256": config_sha256,
        "backend_executable_sha256": executable_sha256,
        "backend_version_sha256": version_sha256,
        "backend_adapter_sha256": adapter_sha256,
        "endpoint_sha256": endpoint_sha256,
        "sdk_version": sdk_version,
        "complete": not errors,
        "error_codes": sorted(set(errors)),
    }


def _review_out_dir(default_name: str) -> Path:
    requested = str(os.environ.get("SC_LLM_REVIEW_OUT_DIR") or "").strip()
    if not requested:
        return ci_dir(default_name)
    candidate = Path(requested).resolve()
    allowed_root = (repo_root() / "logs" / "ci").resolve()
    try:
        candidate.relative_to(allowed_root)
    except ValueError as exc:
        raise ValueError("SC_LLM_REVIEW_OUT_DIR must stay beneath logs/ci") from exc
    candidate.mkdir(parents=True, exist_ok=True)
    return candidate


def _build_review_metrics(
    results: list[ReviewResult],
    *,
    args: argparse.Namespace,
    requested_agents: list[str],
    security_profile: str,
    threat_model: str,
    template_meta: dict[str, Any],
    runtime: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    prompt_rows: list[dict[str, Any]] = []
    prompt_chars_by_agent: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    llm_invocation_count = 0
    llm_duration_sec_total = 0.0
    output_chars_total = 0
    prompt_truncated_agents: list[str] = []
    for result in results:
        status = str(result.status or "unknown").strip().lower() or "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1
        details = result.details if isinstance(result.details, dict) else {}
        prompt_sha256 = str(details.get("prompt_sha256") or "").strip()
        prompt_chars = int(details.get("prompt_chars") or 0)
        if prompt_sha256:
            prompt_rows.append({"agent": result.agent, "prompt_sha256": prompt_sha256})
            prompt_chars_by_agent[result.agent] = prompt_chars
        if details.get("llm_invoked") is True:
            llm_invocation_count += 1
        llm_duration_sec_total += float(details.get("llm_duration_sec") or 0.0)
        output_chars_total += int(details.get("output_chars") or 0)
        prompt_budget = details.get("prompt_budget") if isinstance(details.get("prompt_budget"), dict) else {}
        if prompt_budget.get("truncated") is True:
            prompt_truncated_agents.append(result.agent)

    requested_llm_agents = [agent for agent in requested_agents if agent not in DETERMINISTIC_AGENTS]
    observed_prompt_agents = {row["agent"] for row in prompt_rows}
    identity_payload = {
        "schema_version": LLM_INPUT_IDENTITY_SCHEMA,
        "requested_agents": list(requested_agents),
        "prompt_set": prompt_rows,
        "runtime": runtime,
        "delivery_profile": str(getattr(args, "delivery_profile", "") or "").strip(),
        "security_profile": security_profile,
        "threat_model": threat_model,
        "review_profile": str(getattr(args, "review_profile", "") or "").strip(),
        "template_sha256": str(template_meta.get("review_template_sha256") or "absent"),
        "diff_mode": str(getattr(args, "diff_mode", "") or "").strip(),
        "semantic_gate": str(getattr(args, "semantic_gate", "") or "").strip(),
        "prompt_max_chars": int(getattr(args, "prompt_max_chars", 0) or 0),
        "prompt_budget_gate": str(getattr(args, "prompt_budget_gate", "") or "").strip(),
        "skip_agent_prompts": bool(getattr(args, "skip_agent_prompts", False)),
    }
    identity_complete = set(requested_llm_agents).issubset(observed_prompt_agents) and runtime.get("complete") is True
    input_identity = {
        **identity_payload,
        "complete": identity_complete,
        "input_identity_hash": _canonical_hash(identity_payload) if identity_complete else "",
    }
    metrics = {
        "schema_version": LLM_REVIEW_METRICS_SCHEMA,
        "requested_reviewer_count": len(requested_agents),
        "result_count": len(results),
        "status_counts": status_counts,
        "llm_invocation_count": llm_invocation_count,
        "llm_duration_sec_total": round(llm_duration_sec_total, 3),
        "prompt_chars_total": sum(prompt_chars_by_agent.values()),
        "prompt_chars_max": max(prompt_chars_by_agent.values(), default=0),
        "prompt_chars_by_agent": prompt_chars_by_agent,
        "prompt_set_sha256": _canonical_hash(prompt_rows),
        "prompt_truncated_count": len(prompt_truncated_agents),
        "prompt_truncated_agents": prompt_truncated_agents,
        "output_chars_total": output_chars_total,
        "runtime": runtime,
    }
    return metrics, input_identity


def _prompt_shape_for_agent(
    agent: str,
    *,
    delivery_profile: str | None = None,
    resolved_agents: list[str] | None = None,
    semantic_gate: str | None = None,
) -> dict[str, str]:
    if agent == "semantic-equivalence-auditor":
        return {
            "task_context_mode": "semantic",
            "acceptance_semantic_profile": "semantic",
            "diff_position": "tail",
        }
    normalized_profile = str(delivery_profile or "").strip().lower()
    normalized_gate = str(semantic_gate or "").strip().lower()
    reviewer_set = {str(item).strip() for item in (resolved_agents or []) if str(item).strip()}
    if normalized_profile in {"playable-ea", "fast-ship"} and "semantic-equivalence-auditor" not in reviewer_set and normalized_gate in {"skip", "warn"}:
        return {
            "task_context_mode": "compact",
            "acceptance_semantic_profile": "none",
            "diff_position": "before_acceptance_semantic",
        }
    return {
        "task_context_mode": "compact",
        "acceptance_semantic_profile": "compact",
        "diff_position": "before_acceptance_semantic",
    }


def _compose_prompt(*, blocks: list[str], diff_ctx: str, acceptance_semantic_ctx: str, diff_position: str) -> str:
    rendered = [*blocks]
    if diff_position == "before_acceptance_semantic":
        rendered.append(diff_ctx)
    if acceptance_semantic_ctx:
        rendered.append(acceptance_semantic_ctx)
    if diff_position != "before_acceptance_semantic":
        rendered.append(diff_ctx)
    return "\n\n".join([b for b in rendered if str(b or "").strip()]).strip() + "\n"


def _fit_prompt_context(
    *,
    blocks: list[str],
    diff_ctx: str,
    diff_ctx_summary: str | None,
    acceptance_semantic_ctx: str,
    diff_position: str,
    max_chars: int,
    allow_drop_acceptance_semantic: bool,
) -> tuple[str, dict[str, Any]]:
    prompt = _compose_prompt(
        blocks=blocks,
        diff_ctx=diff_ctx,
        acceptance_semantic_ctx=acceptance_semantic_ctx,
        diff_position=diff_position,
    )
    meta: dict[str, Any] = {
        "diff_mode_used": "full",
        "acceptance_semantic_included": bool(acceptance_semantic_ctx),
        "fallbacks_applied": [],
        "pre_budget_chars": len(prompt),
    }
    if len(prompt) <= max_chars:
        return prompt, meta

    if diff_ctx_summary and diff_ctx_summary != diff_ctx:
        summary_prompt = _compose_prompt(
            blocks=blocks,
            diff_ctx=diff_ctx_summary,
            acceptance_semantic_ctx=acceptance_semantic_ctx,
            diff_position=diff_position,
        )
        if len(summary_prompt) < len(prompt):
            prompt = summary_prompt
            meta["diff_mode_used"] = "summary"
            meta["fallbacks_applied"].append("summary_diff")
            meta["pre_budget_chars"] = len(prompt)

    if len(prompt) > max_chars and allow_drop_acceptance_semantic and acceptance_semantic_ctx:
        reduced_prompt = _compose_prompt(
            blocks=blocks,
            diff_ctx=diff_ctx_summary if meta["diff_mode_used"] == "summary" and diff_ctx_summary else diff_ctx,
            acceptance_semantic_ctx="",
            diff_position=diff_position,
        )
        if len(reduced_prompt) < len(prompt):
            prompt = reduced_prompt
            meta["acceptance_semantic_included"] = False
            meta["fallbacks_applied"].append("drop_acceptance_semantic")
            meta["pre_budget_chars"] = len(prompt)

    return prompt, meta


def _review_result_is_clean(result: ReviewResult | dict[str, Any]) -> bool:
    if isinstance(result, ReviewResult):
        status = str(result.status or "").strip().lower()
        rc = int(result.rc or 0)
        details = result.details if isinstance(result.details, dict) else {}
    else:
        status = str(result.get("status") or "").strip().lower()
        rc = int(result.get("rc") or 0)
        details = result.get("details") if isinstance(result.get("details"), dict) else {}
    verdict = str(details.get("verdict") or "").strip().upper()
    if status != "ok" or rc != 0:
        return False
    return verdict in {"", "OK"}


def _build_agent_execution_plan(agents: list[str]) -> dict[str, Any]:
    ordered_agents = [str(agent).strip() for agent in agents if str(agent).strip()]
    llm_agents = [agent for agent in ordered_agents if agent not in DETERMINISTIC_AGENTS]
    if _SEMANTIC_AGENT not in llm_agents or len(llm_agents) <= 1:
        return {
            "ordered_agents": ordered_agents,
            "primary_agents": ordered_agents,
            "deferred_agents": [],
            "primary_llm_agents": llm_agents,
            "stages": {agent: "primary" for agent in ordered_agents},
            "semantic_deferred": False,
        }

    primary_agents = [agent for agent in ordered_agents if agent != _SEMANTIC_AGENT]
    deferred_agents = [agent for agent in ordered_agents if agent == _SEMANTIC_AGENT]
    return {
        "ordered_agents": [*primary_agents, *deferred_agents],
        "primary_agents": primary_agents,
        "deferred_agents": deferred_agents,
        "primary_llm_agents": [agent for agent in primary_agents if agent not in DETERMINISTIC_AGENTS],
        "stages": {
            agent: ("deferred" if agent == _SEMANTIC_AGENT else "primary")
            for agent in ordered_agents
        },
        "semantic_deferred": True,
    }


def _run_self_check(args: argparse.Namespace) -> int:
    out_dir = ci_dir("sc-llm-review-self-check")
    security_profile = resolve_security_profile(args.security_profile)
    errors = validate_args(args)
    summary = summary_base(mode="self-check", out_dir=out_dir, args=args, security_profile=security_profile, status="fail" if errors else "ok")
    summary["arg_validation"] = {"valid": len(errors) == 0, "errors": errors}
    write_json(out_dir / "summary.json", summary)
    for e in errors:
        print(f"[sc-llm-review] ERROR: {e}")
    print(f"SC_LLM_REVIEW_SELF_CHECK status={summary['status']} out={repo_rel(out_dir)}")
    return 0 if not errors else 2


def _run_dry_plan(args: argparse.Namespace) -> int:
    security_profile = resolve_security_profile(args.security_profile)
    errors = validate_args(args)
    if errors:
        for e in errors:
            print(f"[sc-llm-review] ERROR: {e}")
        return 2

    triplet = None
    if args.task_id:
        try:
            triplet = resolve_triplet(task_id=str(args.task_id).split(".", 1)[0])
        except Exception as exc:  # noqa: BLE001
            print(f"[sc-llm-review] ERROR: failed to resolve task: {exc}")
            return 2

    requested_agents = resolve_agents(args.agents, str(args.semantic_gate))
    execution_plan = _build_agent_execution_plan(requested_agents)
    agents = list(execution_plan["ordered_agents"])
    overrides = parse_agent_timeout_overrides(args.agent_timeouts)
    per_agent_timeout_sec = int(args.agent_timeout_sec)
    out_dir = ci_dir(f"sc-llm-review-dry-plan-task-{triplet.task_id}") if triplet else ci_dir("sc-llm-review-dry-plan")
    plan = []
    for agent in agents:
        plan.append(
            {
                "agent": agent,
                "deterministic": agent in DETERMINISTIC_AGENTS,
                "timeout_sec": overrides.get(agent, per_agent_timeout_sec),
                "will_execute_llm": (not bool(args.prompts_only)) and agent not in DETERMINISTIC_AGENTS,
                "execution_stage": str(execution_plan["stages"].get(agent) or "primary"),
                "activation_condition": "all_prior_reviewers_clean" if agent in set(execution_plan["deferred_agents"]) else "always",
                "prompt_budget_gate": str(args.prompt_budget_gate),
                "prompt_max_chars": int(args.prompt_max_chars),
            }
        )
    summary = summary_base(mode="dry-run-plan", out_dir=out_dir, args=args, security_profile=security_profile, status="ok")
    summary["task_id"] = triplet.task_id if triplet else None
    summary["agents"] = agents
    summary["requested_agents"] = requested_agents
    summary["execution_plan"] = execution_plan
    summary["plan"] = plan
    write_json(out_dir / "summary.json", summary)
    print(f"SC_LLM_REVIEW_DRY_RUN_PLAN status={summary['status']} out={repo_rel(out_dir)}")
    return 0


def main() -> int:
    args = apply_delivery_profile_defaults(build_parser().parse_args())
    if bool(args.self_check):
        return _run_self_check(args)
    if bool(args.dry_run_plan):
        return _run_dry_plan(args)

    errors = validate_args(args)
    if errors:
        for e in errors:
            print(f"[sc-llm-review] ERROR: {e}")
        return 2

    triplet = None
    if args.task_id:
        try:
            triplet = resolve_triplet(task_id=str(args.task_id).split(".", 1)[0])
        except Exception as exc:  # noqa: BLE001
            print(f"[sc-llm-review] ERROR: failed to resolve task: {exc}")
            return 2

    if args.auto_commit:
        sha = auto_resolve_commit_for_task(triplet.task_id if triplet else "")
        if not sha:
            print("[sc-llm-review] ERROR: failed to auto-resolve commit. Use --commit <sha>.")
            return 2
        args.commit = sha

    codex_configs: list[str] = []
    if str(args.model_reasoning_effort or "").strip():
        codex_configs.append(f'model_reasoning_effort="{str(args.model_reasoning_effort).strip()}"')

    out_dir = _review_out_dir(f"sc-llm-review-task-{triplet.task_id}" if triplet else "sc-llm-review")
    claude_agents_root = resolve_claude_agents_root(args.claude_agents_root)
    security_profile = resolve_security_profile(args.security_profile)
    requested_agents = resolve_agents(args.agents, str(args.semantic_gate or "skip").strip().lower())
    execution_plan = _build_agent_execution_plan(requested_agents)
    agents = list(execution_plan["ordered_agents"])
    per_agent_overrides = parse_agent_timeout_overrides(args.agent_timeouts)
    total_timeout_sec = int(args.timeout_sec)
    per_agent_timeout_sec = int(args.agent_timeout_sec)
    runtime_input = _runtime_input_descriptor(args)

    threat_model = resolve_threat_model(args.threat_model)
    threat_ctx = build_threat_model_context(threat_model)
    security_ctx = build_security_profile_context(security_profile)
    acceptance_ctx = ""
    acceptance_meta: dict[str, Any] | None = None
    if triplet:
        acceptance_ctx, acceptance_meta = build_acceptance_evidence(task_id=triplet.task_id)

    review_template = ""
    template_meta: dict[str, Any] = {"review_profile": str(args.review_profile)}
    template_path_arg = str(args.review_template or "").strip()
    if template_path_arg:
        p = repo_root() / template_path_arg
        if p.is_file():
            review_template = truncate(strip_emoji(read_text(p)), max_chars=8_000)
            template_meta["review_template_source"] = template_path_arg.replace("\\", "/")
            template_meta["review_template_sha256"] = _sha256_text(review_template)
        else:
            template_meta["review_template_source"] = None
            template_meta["review_template_error"] = f"missing:{template_path_arg}"
    elif str(args.review_profile).strip().lower() == "bmad-godot":
        p = repo_root() / "scripts/sc/templates/llm_review/bmad-godot-review-template.txt"
        if p.is_file():
            review_template = truncate(strip_emoji(read_text(p)), max_chars=8_000)
            template_meta["review_template_source"] = str(p.relative_to(repo_root())).replace("\\", "/")
            template_meta["review_template_sha256"] = _sha256_text(review_template)
        else:
            template_meta["review_template_source"] = None
            template_meta["review_template_error"] = "missing:built_in_bmad_godot_template"

    if str(args.semantic_gate).lower() == "require":
        acc_status = str((acceptance_meta or {}).get("acceptance_status") or "").strip().lower()
        if acc_status and acc_status != "ok":
            print("[sc-llm-review] ERROR: --semantic-gate require needs sc-acceptance-check status=ok.")
            return 1

    acceptance_semantic_cache: dict[str, tuple[str, dict[str, Any] | None]] = {}
    diff_ctx = build_diff_context(args)
    diff_ctx_summary: str | None = None

    results: list[ReviewResult] = []
    hard_fail = False
    had_warnings = False
    prompt_truncated_agents: list[str] = []
    deadline_ts = time.monotonic() + total_timeout_sec

    for agent in agents:
        execution_stage = str(execution_plan["stages"].get(agent) or "primary")
        if execution_stage == "deferred":
            blocked_by_agents = [result.agent for result in results if not _review_result_is_clean(result)]
            if blocked_by_agents:
                results.append(
                    ReviewResult(
                        agent=agent,
                        status="skipped",
                        rc=0,
                        details={
                            "execution_stage": execution_stage,
                            "reason_code": _DEFERRED_REASON_CODE,
                            "blocked_by_agents": blocked_by_agents,
                            "note": "Deferred reviewer skipped because prior reviewers are not yet clean.",
                        },
                    )
                )
                continue
        remaining = int(deadline_ts - time.monotonic())
        if remaining <= 0:
            status = "fail" if args.strict else "skipped"
            had_warnings = True
            if status == "fail":
                hard_fail = True
            results.append(
                ReviewResult(
                    agent=agent,
                    status=status,
                    rc=124,
                    details={"execution_stage": execution_stage, "note": "Skipped due to total timeout budget exhausted.", "total_timeout_sec": total_timeout_sec, "agent_timeout_sec": per_agent_overrides.get(agent, per_agent_timeout_sec)},
                )
            )
            continue

        if agent in DETERMINISTIC_AGENTS:
            det = build_deterministic_review(agent=agent, out_dir=out_dir, task_id=triplet.task_id if triplet else None)
            verdict = (det.get("details") or {}).get("verdict")
            if det.get("status") != "ok" or verdict not in {None, "OK"}:
                had_warnings = True
            if det.get("status") == "fail":
                hard_fail = True
            results.append(
                ReviewResult(
                    agent=agent,
                    status=str(det.get("status")),
                    rc=det.get("rc"),
                    cmd=det.get("cmd"),
                    prompt_path=det.get("prompt_path"),
                    output_path=det.get("output_path"),
                    details={"execution_stage": execution_stage, "claude_agents_root": str(claude_agents_root), "agent_prompt_source": agent_prompt(agent, claude_agents_root=claude_agents_root, skip_agent_files=bool(args.skip_agent_prompts))[1].get("agent_prompt_source"), "security_profile": security_profile_payload(security_profile), **(det.get("details") or {}), "note": "Deterministic mapping: generated from sc-acceptance-check artifacts."},
                )
            )
            continue

        base_prompt, prompt_meta = agent_prompt(agent, claude_agents_root=claude_agents_root, skip_agent_files=bool(args.skip_agent_prompts))
        agent_prompt_sha256 = _sha256_text(base_prompt)
        prompt_shape = _prompt_shape_for_agent(
            agent,
            delivery_profile=str(getattr(args, "delivery_profile", "") or ""),
            resolved_agents=list(execution_plan["primary_llm_agents"]) if execution_stage == "primary" and bool(execution_plan["semantic_deferred"]) else agents,
            semantic_gate=str(args.semantic_gate or "skip").strip().lower(),
        )
        ctx = build_task_context(triplet, mode=prompt_shape["task_context_mode"])
        acceptance_semantic_ctx = ""
        acceptance_semantic_meta: dict[str, Any] | None = None
        acceptance_semantic_profile = prompt_shape["acceptance_semantic_profile"]
        if triplet and acceptance_semantic_profile != "none" and not bool(args.no_acceptance_semantic):
            if acceptance_semantic_profile not in acceptance_semantic_cache:
                try:
                    acceptance_semantic_cache[acceptance_semantic_profile] = build_acceptance_semantic_context(
                        triplet,
                        profile=acceptance_semantic_profile,
                    )
                except Exception:  # noqa: BLE001
                    acceptance_semantic_cache[acceptance_semantic_profile] = ("", {"status": "error", "profile": acceptance_semantic_profile})
            acceptance_semantic_ctx, acceptance_semantic_meta = acceptance_semantic_cache[acceptance_semantic_profile]
        task_requirements_blob = "\n".join([ctx, acceptance_ctx, acceptance_semantic_ctx, review_template])
        blocks = [base_prompt]
        if review_template:
            blocks.append("## Structured Review Template\n" + review_template.strip() + "\n")
        if ctx:
            blocks.append(ctx)
        if threat_ctx:
            blocks.append(threat_ctx)
        if security_ctx:
            blocks.append(security_ctx)
        if acceptance_ctx:
            blocks.append(acceptance_ctx)
        if str(args.diff_mode or "").strip().lower() == "full" and diff_ctx_summary is None:
            diff_args = argparse.Namespace(**vars(args))
            diff_args.diff_mode = "summary"
            diff_ctx_summary = build_diff_context(diff_args)
        prompt, prompt_fit_meta = _fit_prompt_context(
            blocks=blocks,
            diff_ctx=diff_ctx,
            diff_ctx_summary=diff_ctx_summary,
            acceptance_semantic_ctx=acceptance_semantic_ctx,
            diff_position=prompt_shape["diff_position"],
            max_chars=int(args.prompt_max_chars),
            allow_drop_acceptance_semantic=(agent != "semantic-equivalence-auditor"),
        )
        prompt_used, budget_meta = apply_prompt_budget(prompt, max_chars=int(args.prompt_max_chars))
        prompt_sha256 = _sha256_text(prompt_used)
        if bool(budget_meta.get("truncated")):
            prompt_truncated_agents.append(agent)
            if str(args.prompt_budget_gate) in {"warn", "require"}:
                had_warnings = True
            if str(args.prompt_budget_gate) == "require":
                hard_fail = True

        prompt_path = out_dir / f"prompt-{agent}.md"
        output_path = out_dir / f"review-{agent}.md"
        trace_path = out_dir / f"trace-{agent}.log"
        write_text(prompt_path, prompt_used)

        if bool(args.prompts_only):
            had_warnings = True
            results.append(
                ReviewResult(
                    agent=agent,
                    status="skipped",
                    prompt_path=str(prompt_path.relative_to(repo_root())).replace("\\", "/"),
                    details={"execution_stage": execution_stage, "trace": str(trace_path.relative_to(repo_root())).replace("\\", "/"), "claude_agents_root": str(claude_agents_root), "agent_prompt_source": prompt_meta.get("agent_prompt_source"), "agent_prompt_sha256": agent_prompt_sha256, "prompt_sha256": prompt_sha256, "prompt_chars": len(prompt_used), "llm_invoked": False, "llm_duration_sec": 0.0, "output_chars": 0, "security_profile": security_profile_payload(security_profile), "prompt_budget": budget_meta, "prompt_shape": {**prompt_shape, **prompt_fit_meta}, "acceptance_semantic_meta": acceptance_semantic_meta, "note": "--prompts-only: LLM execution skipped."},
                )
            )
            write_text(trace_path, "--prompts-only: LLM execution skipped.\n")
            continue

        agent_cap = per_agent_overrides.get(agent, per_agent_timeout_sec)
        remaining_before_sec = max(0, int(remaining))
        effective_timeout = max(1, int(agent_cap))
        llm_started = time.perf_counter()
        rc, trace_out, cmd = run_codex_exec(
            backend=str(args.llm_backend),
            prompt=prompt_used,
            output_last_message=output_path,
            timeout_sec=effective_timeout,
            codex_configs=codex_configs,
        )
        llm_duration_sec = round(max(0.0, time.perf_counter() - llm_started), 3)
        write_text(trace_path, trace_out)

        last_msg = ""
        if output_path.is_file():
            last_msg = output_path.read_text(encoding="utf-8", errors="ignore")
            write_text(output_path, last_msg)

        status = "ok" if (rc == 0 and last_msg.strip()) else ("fail" if args.strict else "skipped")
        if status != "ok":
            had_warnings = True
        if status == "fail":
            hard_fail = True

        semantic_gate = str(args.semantic_gate or "skip").strip().lower()
        semantic_agent = _SEMANTIC_AGENT
        verdict = parse_verdict(last_msg)
        verdict_normalization: dict[str, Any] | None = None
        if last_msg and agent != semantic_agent:
            normalized_msg, normalized_verdict, verdict_normalization = normalize_host_safe_needs_fix(
                agent=agent,
                text=last_msg,
                security_profile=security_profile,
                task_requirements_blob=task_requirements_blob,
            )
            if normalized_msg != last_msg:
                last_msg = normalized_msg
                write_text(output_path, last_msg)
            if normalized_verdict:
                verdict = normalized_verdict
        if agent == semantic_agent:
            if semantic_gate == "warn" and verdict != "OK":
                had_warnings = True
            if semantic_gate == "require" and verdict != "OK":
                had_warnings = True
                hard_fail = True

        results.append(
            ReviewResult(
                agent=agent,
                status=status,
                rc=rc,
                cmd=cmd,
                prompt_path=str(prompt_path.relative_to(repo_root())).replace("\\", "/"),
                output_path=str(output_path.relative_to(repo_root())).replace("\\", "/"),
                details={"execution_stage": execution_stage, "trace": str(trace_path.relative_to(repo_root())).replace("\\", "/"), "claude_agents_root": str(claude_agents_root), "agent_prompt_source": prompt_meta.get("agent_prompt_source"), "agent_prompt_sha256": agent_prompt_sha256, "prompt_sha256": prompt_sha256, "prompt_chars": len(prompt_used), "llm_invoked": True, "llm_duration_sec": llm_duration_sec, "output_chars": len(last_msg), "security_profile": security_profile_payload(security_profile), "total_timeout_sec": total_timeout_sec, "agent_timeout_sec": effective_timeout, "remaining_before_sec": remaining_before_sec, "prompt_budget": budget_meta, "prompt_shape": {**prompt_shape, **prompt_fit_meta}, "acceptance_semantic_meta": acceptance_semantic_meta, "verdict": verdict, "verdict_normalization": verdict_normalization, "note": "This step is best-effort. Use --strict to make it a hard gate."},
            )
        )

    review_metrics, input_identity = _build_review_metrics(
        results,
        args=args,
        requested_agents=requested_agents,
        security_profile=security_profile,
        threat_model=threat_model,
        template_meta=template_meta,
        runtime=runtime_input,
    )
    summary = summary_base(
        mode="uncommitted" if args.uncommitted else ("commit" if args.commit else "base"),
        out_dir=out_dir,
        args=args,
        security_profile=security_profile,
        status="fail" if hard_fail else ("warn" if had_warnings else "ok"),
    )
    summary.update(
        {
            "base": args.base,
            "commit": args.commit,
            "task_id": triplet.task_id if triplet else None,
            "threat_model": threat_model,
            "template_meta": template_meta,
            "acceptance_meta": acceptance_meta,
            "acceptance_semantic_meta": acceptance_semantic_meta,
            "requested_agents": requested_agents,
            "execution_plan": execution_plan,
            "results": [r.__dict__ for r in results],
            "review_metrics": review_metrics,
            "input_identity": input_identity,
            "prompt_budget": {
                "max_chars": int(args.prompt_max_chars),
                "gate": str(args.prompt_budget_gate),
                "truncated_count": len(prompt_truncated_agents),
                "truncated_agents": prompt_truncated_agents,
            },
        }
    )
    write_json(out_dir / "summary.json", summary)
    print(f"SC_LLM_REVIEW status={summary['status']} out={repo_rel(out_dir)}")
    return 0 if summary["status"] in ("ok", "warn") else 1
