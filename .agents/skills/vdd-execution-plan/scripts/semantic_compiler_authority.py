"""Stable VDD Chapter 4/5/6 compiler authority.

The lower-level semantic_compiler_gate supplies the normative worker envelope
and preflight-bearing schema. This layer owns stable publication semantics:
failed semantic attempts are content-addressed diagnostics, while canonical
plan artifacts are written only after the corresponding gate is valid.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
from typing import Any, Mapping, Sequence

import semantic_compiler_gate as gate
import semantic_feasibility_patch  # noqa: F401  # installs normative planned-new-file V7 rule
from semantic_chain_audit import audit_bundle
from semantic_progress import stage_call


def _resolved_backend_metadata(root: Path, *, injected: bool) -> tuple[str, str]:
    """Return a concrete runtime backend/model identity for worker receipts."""
    if injected:
        return "injected-worker-cache", "fixture-v1"
    scripts = root / "scripts" / "sc"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    try:
        from _llm_backend import inspect_llm_backend, resolve_llm_backend

        backend = resolve_llm_backend(None)
        info = inspect_llm_backend(backend)
        backend_name = str(info.get("backend") or backend or "unknown-backend")
        model = str(info.get("model") or "runtime-default-model")
        version = str(
            info.get("sdk_version")
            or info.get("executable_version")
            or info.get("version")
            or "runtime-resolved"
        )
        return f"{backend_name}:{model}", version
    except Exception:
        return "shared-llm-backend:runtime-default-model", "runtime-resolved"


# The lower-level gate writes the receipt; stable authority supplies the
# runtime-resolved backend metadata so a string backend is never misreported as
# Python type `str`.
gate._backend_metadata = _resolved_backend_metadata


_BASE_WORKER_SCHEMA_FINDINGS = gate._worker_schema_findings
_V1_REQUIRED_TEXT_FIELDS = (
    "subject",
    "trigger",
    "state_before",
    "state_after",
    "expected_behavior",
    "observable_result",
)
_V1_STRING_LIST_FIELDS = (
    "source_refs",
    "forbidden_result",
    "unresolved_fragments",
    "depends_on",
)


def _strict_worker_schema_findings(stage: str, value: Mapping[str, Any]) -> list[str]:
    """Validate V1 obligation shape early enough for the one-shot repair lane.

    The lower-level gate historically checked only that `obligations[]` existed.
    Real model output could therefore pass the worker boundary and fail later in
    `_normalize_obligation()` or V2, after the schema-repair opportunity had been
    lost. Keep the canonical obligation contract strict, but surface those
    failures at the worker boundary so the existing one-attempt repair contract
    can correct formatting without weakening semantic truth.
    """
    findings = list(_BASE_WORKER_SCHEMA_FINDINGS(stage, value))
    if not stage.startswith("v1-"):
        return findings
    obligations = value.get("obligations")
    if not isinstance(obligations, list) or not obligations:
        return findings

    for index, raw in enumerate(obligations):
        prefix = f"worker-output:obligations[{index}]"
        if not isinstance(raw, Mapping):
            findings.append(f"{prefix}:not-object")
            continue
        for field in _V1_REQUIRED_TEXT_FIELDS:
            item = raw.get(field)
            if not isinstance(item, str) or not item.strip():
                findings.append(f"{prefix}:{field}:nonempty-string-required")
        for field in _V1_STRING_LIST_FIELDS:
            item = raw.get(field)
            if not isinstance(item, list) or any(not isinstance(entry, str) for entry in item):
                if field == "depends_on":
                    findings.append(
                        f"{prefix}:depends_on:string-list-required-use-empty-list-when-source-declares-no-dependency"
                    )
                else:
                    findings.append(f"{prefix}:{field}:string-list-required")
        requirement_type = raw.get("requirement_type")
        if requirement_type not in {"Product", "Platform", "Governance"}:
            findings.append(f"{prefix}:requirement_type:invalid")
        kind = raw.get("obligation_kind", "behavior")
        if kind not in {"behavior", "quality", "constraint", "governance"}:
            findings.append(f"{prefix}:obligation_kind:invalid")
        status = raw.get("status", "active")
        if status not in {"active", "deferred", "not_applicable"}:
            findings.append(f"{prefix}:status:invalid")
        unresolved = raw.get("unresolved_fragments")
        if status == "active" and isinstance(unresolved, list) and unresolved:
            findings.append(
                f"{prefix}:active-unresolved:mandatory-active-obligations-require-empty-unresolved_fragments"
            )
    return findings


# The normative worker wrapper resolves this global on every invocation. Patch it
# once here so both normal compilation and schema-repair validation use the same
# strict V1 contract.
gate._worker_schema_findings = _strict_worker_schema_findings


_BASE_VALIDATE = gate.validate_semantic_bundle_with_preflight


def _strict_validate_semantic_bundle(bundle: Mapping[str, Any]) -> tuple[bool, list[str]]:
    """Compose structural/preflight validation with exact semantic-chain audit."""
    base_valid, base_findings = _BASE_VALIDATE(bundle)
    audit = audit_bundle(bundle)
    findings = list(base_findings) + [str(item) for item in audit["findings"]]
    return bool(base_valid and audit["valid"] and not findings), findings


# `_ORIGINAL_COMPILE_PLAN` resolves this symbol from semantic_compiler globals at
# runtime, so this patch blocks plan-ready publication rather than auditing only
# after canonical artifacts have already been written.  Resume validation uses
# the gate-level name, so patch both authorities.
gate.validate_semantic_bundle_with_preflight = _strict_validate_semantic_bundle
gate.sc.validate_semantic_bundle = _strict_validate_semantic_bundle


def _attempt(out_dir: Path, label: str, value: Mapping[str, Any]) -> None:
    digest = gate.sc.sha256_value(value)[7:31]
    gate.sc.atomic_json(out_dir / ".compiler-attempts" / f"{label}-{digest}.json", dict(value))


def _archive_repair_publications(out_dir: Path) -> None:
    """Move prior canonical publications aside before an append-only repair publish."""
    names = (
        "source-index.v1.json", "obligations.v1.json", "acceptances.v1.json",
        "failure-intents.v1.json", "pre-slice-coverage.v1.json", "slices.v1.json",
        "final-plan-coverage.v1.json", "semantic-alignment.v1.json", "feasibility.v1.json",
        "semantic-plan-bundle.v1.json", "compiler-state.v1.json",
    )
    for name in names:
        path = out_dir / name
        if not path.is_file():
            continue
        sidecar = path.with_name(path.name + ".stale-p1-round-7-refresh")
        suffix = 1
        while sidecar.exists():
            sidecar = path.with_name(path.name + f".stale-p1-round-7-refresh-{suffix}")
            suffix += 1
        path.rename(sidecar)
    context_root = out_dir / "agent-context"
    if context_root.is_dir():
        for path in context_root.glob("*/agent-context.json"):
            sidecar = path.with_name(path.name + ".stale-p1-round-7-refresh")
            suffix = 1
            while sidecar.exists():
                sidecar = path.with_name(path.name + f".stale-p1-round-7-refresh-{suffix}")
                suffix += 1
            path.rename(sidecar)


def _archive_stale_publication(out_dir: Path, name: str) -> None:
    """Preserve a superseded intermediate publication before a repaired reissue."""
    path = out_dir / name
    if not path.is_file():
        return
    sidecar = path.with_name(path.name + ".stale-p1-round-7-refresh")
    suffix = 1
    while sidecar.exists():
        sidecar = path.with_name(path.name + f".stale-p1-round-7-refresh-{suffix}")
        suffix += 1
    path.rename(sidecar)


def _explicit_fixture_cache_wins(out_dir: Path, worker_cache: Mapping[str, Any] | None) -> None:
    """An explicitly supplied deterministic worker fixture supersedes old cache.

    `.compiler-cache` is a replay optimization rather than evidence authority.
    Keeping an older cache ahead of an explicit repair fixture would make the
    stable `--resume-from first-failed-stage` contract impossible to exercise
    and would turn cache presence into semantic authority.
    """
    if worker_cache is None:
        return
    cache_dir = out_dir / ".compiler-cache"
    if cache_dir.exists():
        shutil.rmtree(cache_dir)


def _plan_chain_audit(out_dir: Path) -> Mapping[str, Any]:
    bundle_path = out_dir / "semantic-plan-bundle.v1.json"
    if not bundle_path.is_file():
        raise ValueError("plan-ready result is missing semantic bundle")
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    if not isinstance(bundle, Mapping):
        raise ValueError("semantic bundle must be object")
    audit = audit_bundle(bundle)
    if not audit["valid"]:
        raise ValueError("plan-ready semantic chain audit failed: " + ",".join(audit["findings"]))
    audit_path = out_dir / "semantic-chain-audit.v1.json"
    if audit_path.is_file() and audit_path.read_bytes() != gate.sc.canonical_bytes(audit):
        # The chain audit is a derived current publication. Preserve its prior
        # successful snapshot as append-only repair history before publishing
        # the audit for the repaired semantic bundle.
        _archive_stale_publication(out_dir, audit_path.name)
    gate.sc.atomic_json(audit_path, audit)
    return audit


def _published_recall_matches_obligations(out_dir: Path) -> bool:
    """Require the published V4 witness to cover the actual published V1 set."""
    try:
        obligations = json.loads((out_dir / "obligations.v1.json").read_text(encoding="utf-8"))
        recall = json.loads((out_dir / "atomic-recall-alignment.v1.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    if not isinstance(obligations, list) or not isinstance(recall, Mapping) or recall.get("valid") is not True:
        return False
    active = {str(item.get("obligation_id")) for item in obligations if isinstance(item, Mapping) and item.get("status") == "active"}
    worker = recall.get("worker")
    supported = worker.get("supported_obligation_ids") if isinstance(worker, Mapping) else None
    return bool(active) and isinstance(supported, list) and set(supported) == active


def compile_plan(
    *,
    requirements: Path,
    out_dir: Path,
    companions: Sequence[Path] = (),
    profile: str = "standard",
    worker_cache: Mapping[str, Any] | None = None,
    recommendation_only: bool = False,
    resume_from: str | None = None,
) -> dict[str, Any]:
    if resume_from not in {None, "first-failed-stage"}:
        raise ValueError("unsupported VDD resume mode")
    if recommendation_only and resume_from is not None:
        raise ValueError("recommendation-only cannot be combined with resume")

    if resume_from == "first-failed-stage":
        completed = gate._completed_resume(out_dir)
        if completed is not None and _published_recall_matches_obligations(out_dir):
            audit = _plan_chain_audit(out_dir)
            return {**completed, "semantic_chain_metrics": audit["metrics"]}
        if completed is not None:
            _archive_repair_publications(out_dir)
        elif not _published_recall_matches_obligations(out_dir):
            _archive_stale_publication(out_dir, "atomic-recall-alignment.v1.json")

    if recommendation_only:
        return gate._ORIGINAL_COMPILE_PLAN(
            requirements=requirements,
            out_dir=out_dir,
            companions=companions,
            profile=profile,
            worker_cache=worker_cache,
            recommendation_only=True,
        )

    _explicit_fixture_cache_wins(out_dir, worker_cache)
    root = gate.sc.repository_root(requirements.parent)
    source_index = stage_call(out_dir, "V0", gate.sc.build_source_index, root, requirements, companions)
    preflight = stage_call(out_dir, "V0A", gate.sc.source_preflight, root, source_index)
    if not preflight["valid"]:
        result = {"status": "repair-vdd", "stage": "V0A", "source_index": source_index, "preflight": preflight}
        _attempt(out_dir, "v0a", result)
        return result

    obligations = stage_call(out_dir, "V1", gate.sc.compile_obligations,
        root=root, out_dir=out_dir, source_index=source_index, worker_cache=worker_cache
    )
    guard = stage_call(out_dir, "V2", gate.sc.guard_obligations, source_index, obligations)
    if not guard["valid"]:
        result = {"status": "repair-vdd", "stage": "V2", "findings": guard["findings"]}
        _attempt(out_dir, "v2", result)
        return result

    acceptances, failures, _hints = stage_call(out_dir, "V3", gate.sc.compile_acceptances,
        root=root, out_dir=out_dir, obligations=obligations, worker_cache=worker_cache
    )
    plan_preflight = stage_call(out_dir, "V3A", gate.sc.semantic_preflight, obligations, acceptances, failures)
    if not plan_preflight["valid"]:
        result = {"status": "repair-vdd", "stage": "V3A", "findings": plan_preflight["findings"]}
        _attempt(out_dir, "v3a", result)
        return result

    recall = stage_call(out_dir, "V4-atomic-recall", gate.atomic_recall_alignment,
        root=root,
        out_dir=out_dir,
        source_index=source_index,
        obligations=obligations,
        worker_cache=worker_cache,
    )
    if not recall["valid"]:
        if (
            isinstance(recall.get("findings"), list)
            and recall["findings"]
            and all(str(item).startswith("atomic-recall:source-gap-count:") for item in recall["findings"])
            and isinstance(recall.get("source_gap_claims"), list)
            and recall["source_gap_claims"]
        ):
            import semantic_obligation_gap_repair_patch as gap_repair
            gap_repair.configure_pending_post_v4_source_gaps(recall["source_gap_claims"], out_dir=out_dir)
            return compile_plan(
                requirements=requirements, out_dir=out_dir, companions=companions,
                profile=profile, worker_cache=worker_cache,
                recommendation_only=False, resume_from=None,
            )
        result = {
            "status": "repair-vdd",
            "stage": "V4",
            "gate": "atomic-source-recall",
            "findings": recall["findings"],
            "atomic_quality_metrics": recall["metrics"],
            "source_gap_claims": recall["source_gap_claims"],
        }
        _attempt(out_dir, "v4-atomic-recall", {**result, "alignment": recall})
        return result

    result = dict(
        gate._ORIGINAL_COMPILE_PLAN(
            requirements=requirements,
            out_dir=out_dir,
            companions=companions,
            profile=profile,
            worker_cache=worker_cache,
            recommendation_only=False,
        )
    )
    if result.get("status") != "plan-ready":
        findings = result.get("findings")
        gaps = result.get("source_gap_claims")
        # Feed back only a final V4 result that contains *only* independently
        # stated source gaps.  This is a new V1 candidate on the same frozen
        # source, not an acceptance-only repair and not a licence to discard
        # current V3 contracts.  One bounded feedback pass keeps a malformed or
        # oscillating worker result fail-closed for the caller to inspect.
        if (
            result.get("stage") == "V4"
            and isinstance(findings, list)
            and findings
            and all(str(item).startswith("atomic-recall:source-gap-count:") for item in findings)
            and isinstance(gaps, list)
            and gaps
        ):
            import semantic_obligation_gap_repair_patch as gap_repair
            gap_repair.configure_pending_post_v4_source_gaps(gaps, out_dir=out_dir)
            return compile_plan(
                requirements=requirements, out_dir=out_dir, companions=companions,
                profile=profile, worker_cache=worker_cache,
                recommendation_only=False, resume_from=None,
            )
        _attempt(out_dir, str(result.get("stage") or "compile"), result)
        return result
    # The lower-level publisher recomputes V1 while composing its canonical
    # bundle. Bind the V4 witness to those *published* obligations, never to an
    # earlier candidate from the authority preflight.
    published_obligations = json.loads((out_dir / "obligations.v1.json").read_text(encoding="utf-8"))
    final_recall = stage_call(out_dir, "V4-published-obligations", gate.atomic_recall_alignment,
        root=root, out_dir=out_dir, source_index=source_index,
        obligations=published_obligations, worker_cache=worker_cache,
    )
    if not final_recall.get("valid"):
        _archive_repair_publications(out_dir)
        result = {"status": "repair-vdd", "stage": "V4", "gate": "atomic-source-recall",
                  "findings": final_recall.get("findings", []),
                  "atomic_quality_metrics": final_recall.get("metrics", {}),
                  "source_gap_claims": final_recall.get("source_gap_claims", [])}
        _attempt(out_dir, "v4-published-obligations", result)
        return result
    _archive_stale_publication(out_dir, "atomic-recall-alignment.v1.json")
    gate.sc.atomic_json(out_dir / "atomic-recall-alignment.v1.json", final_recall)
    result["atomic_quality_metrics"] = final_recall["metrics"]
    audit = _plan_chain_audit(out_dir)
    result["semantic_chain_metrics"] = audit["metrics"]
    if resume_from is not None:
        result["resumed"] = True
        result["resume_from"] = resume_from
        result["resume_strategy"] = "first-failed-stage-cache-replay"
    return result
