"""Stable VDD compiler authority for the Chapter 4/5/6 contract.

The canonical semantic_compiler still owns deterministic V0->V7 publication.
This gate adds the normative semantic-worker envelope, atomic source recall,
preflight-bearing planning fields, and resumable cache replay without granting
model workers any plan-ready or runtime-evidence authority.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import time
from typing import Any, Mapping, Sequence

import semantic_compiler as sc

_ORIGINAL_INVOKE_WORKER = sc.invoke_worker
_ORIGINAL_COMPILE_ACCEPTANCES = sc.compile_acceptances
_ORIGINAL_PARTITION_SLICES = sc.partition_slices
_ORIGINAL_VALIDATE_SEMANTIC_BUNDLE = sc.validate_semantic_bundle
_ORIGINAL_COMPILE_PLAN = sc.compile_plan

_PREFLIGHT_FIELDS = {
    "complexity_class",
    "verification_lane",
    "context_lookup_required",
    "context_lookup_reason",
    "minimum_red_scope",
    "upgrade_conditions",
}
_COMPLEXITY_ORDER = {"simple": 0, "complex": 1, "architectural": 2}


def _worker_schema_findings(stage: str, value: Mapping[str, Any]) -> list[str]:
    findings: list[str] = []
    if not isinstance(value, Mapping):
        return ["worker-output:not-object"]
    if stage.startswith("v1-"):
        obligations = value.get("obligations")
        if not isinstance(obligations, list) or not obligations:
            findings.append("worker-output:obligations")
    elif stage == "v3":
        for key in ("acceptances", "failure_intents", "slice_hints"):
            if not isinstance(value.get(key), list) or not value[key]:
                findings.append(f"worker-output:{key}")
    elif stage == "v4-atomic-recall":
        for key in ("supported_obligation_ids", "invented_obligation_ids", "source_gap_claims"):
            if not isinstance(value.get(key), list):
                findings.append(f"worker-output:{key}")
    elif stage == "v4":
        for key in ("covered_obligation_ids", "missing_obligation_ids", "invented_obligation_ids", "misaligned_acceptance_ids", "repairs"):
            if not isinstance(value.get(key), list):
                findings.append(f"worker-output:{key}")
        if not isinstance(value.get("oracle_alignment"), Mapping):
            findings.append("worker-output:oracle_alignment")
    return findings


def _source_binding_findings(stage: str, value: Mapping[str, Any], payload: Mapping[str, Any]) -> list[str]:
    if not stage.startswith("v1-"):
        return []
    source = payload.get("source")
    expected = source.get("source_ref") if isinstance(source, Mapping) else None
    if not isinstance(expected, str) or not expected:
        return ["worker-input:source_ref"]
    obligations = value.get("obligations")
    if not isinstance(obligations, list):
        return []
    findings: list[str] = []
    for index, obligation in enumerate(obligations):
        refs = obligation.get("source_refs") if isinstance(obligation, Mapping) else None
        if refs != [expected]:
            findings.append(f"worker-output:obligations[{index}]:source_refs:must-equal:{expected}")
    return findings


def _backend_metadata(root: Path, *, injected: bool) -> tuple[str, str]:
    if injected:
        return "injected-worker-cache", "fixture"
    scripts = root / "scripts" / "sc"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    try:
        from _llm_backend import resolve_llm_backend

        backend = resolve_llm_backend(None)
        model = str(
            getattr(backend, "model", None)
            or getattr(backend, "name", None)
            or getattr(backend, "backend", None)
            or type(backend).__name__
        )
        version = str(
            getattr(backend, "version", None)
            or getattr(backend, "model_version", None)
            or "runtime-resolved"
        )
        return model, version
    except Exception:
        return "shared-llm-backend", "runtime-resolved"


def _write_worker_receipt(
    *,
    root: Path,
    out_dir: Path,
    stage: str,
    payload: Mapping[str, Any],
    prompt: str,
    result: Mapping[str, Any] | None,
    findings: Sequence[str],
    duration_ms: int,
    repair_attempted: bool,
    injected: bool,
    exit_status: str,
) -> None:
    input_sha = sc.sha256_value(payload)
    prompt_sha = sc.sha256_bytes(prompt.encode("utf-8"))
    model, model_version = _backend_metadata(root, injected=injected)
    receipt = {
        "schema": "vdd.semantic-worker-receipt.v1",
        "stage": stage,
        "prompt_version": "vdd-ch456-semantic-worker.v1",
        "model": model,
        "model_version": model_version,
        "input_sha256": input_sha,
        "prompt_sha256": prompt_sha,
        "duration_ms": duration_ms,
        "exit_status": exit_status,
        "schema_valid": not findings,
        "schema_findings": list(findings),
        "schema_repair_attempted": repair_attempted,
        "result_sha256": sc.sha256_value(result) if isinstance(result, Mapping) else None,
        "worker_authority": "read-only-semantic-candidate",
        "authorizes": [],
    }
    path = out_dir / ".compiler-work" / "worker-receipts" / (
        f"{stage}-{input_sha[7:19]}-{prompt_sha[7:19]}.json"
    )
    if not path.exists():
        sc.atomic_json(path, receipt)


def normative_invoke_worker(
    *,
    root: Path,
    out_dir: Path,
    stage: str,
    payload: Mapping[str, Any],
    prompt: str,
    worker_cache: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    """Invoke one read-only semantic worker with schema repair and stop-loss."""
    started = time.perf_counter()
    injected = bool(worker_cache and stage in worker_cache)
    repair_attempted = False
    raw: Mapping[str, Any] | None = None
    findings: list[str] = []
    try:
        try:
            raw = _ORIGINAL_INVOKE_WORKER(
                root=root,
                out_dir=out_dir,
                stage=stage,
                payload=payload,
                prompt=prompt,
                worker_cache=worker_cache,
            )
            findings = _worker_schema_findings(stage, raw) + _source_binding_findings(stage, raw, payload)
        except (ValueError, RuntimeError) as first_error:
            raw = None
            findings = [f"worker-call:{type(first_error).__name__}:{first_error}"]

        if findings:
            repair_attempted = True
            first_fingerprint = sc.sha256_value({
                "stage": stage,
                "input_sha256": sc.sha256_value(payload),
                "findings": findings,
                "result": dict(raw) if isinstance(raw, Mapping) else None,
            })
            repair_prompt = (
                prompt
                + "\n\nSCHEMA REPAIR (one attempt only): the deterministic validator rejected the prior output with: "
                + json.dumps(findings, ensure_ascii=False, sort_keys=True)
                + ". Return a corrected JSON object only; preserve source semantics and do not invent runtime evidence."
            )
            repaired = _ORIGINAL_INVOKE_WORKER(
                root=root,
                out_dir=out_dir,
                stage=f"{stage}-schema-repair",
                payload={"original_stage": stage, "input": payload, "validator_findings": findings},
                prompt=repair_prompt,
                worker_cache=worker_cache,
            )
            second_findings = _worker_schema_findings(stage, repaired) + _source_binding_findings(stage, repaired, payload)
            second_fingerprint = sc.sha256_value({
                "stage": stage,
                "input_sha256": sc.sha256_value(payload),
                "findings": second_findings,
                "result": dict(repaired),
            })
            if second_findings:
                elapsed = int((time.perf_counter() - started) * 1000)
                _write_worker_receipt(
                    root=root,
                    out_dir=out_dir,
                    stage=stage,
                    payload=payload,
                    prompt=prompt,
                    result=repaired,
                    findings=second_findings,
                    duration_ms=elapsed,
                    repair_attempted=True,
                    injected=injected,
                    exit_status="schema-invalid",
                )
                if second_fingerprint == first_fingerprint:
                    raise RuntimeError("repeated deterministic semantic worker failure; stop and repair VDD")
                raise RuntimeError("semantic worker schema repair failed; stop and repair VDD")
            raw = repaired
            findings = []

        elapsed = int((time.perf_counter() - started) * 1000)
        _write_worker_receipt(
            root=root,
            out_dir=out_dir,
            stage=stage,
            payload=payload,
            prompt=prompt,
            result=raw,
            findings=findings,
            duration_ms=elapsed,
            repair_attempted=repair_attempted,
            injected=injected,
            exit_status="ok",
        )
        if raw is None:
            raise RuntimeError("semantic worker returned no result")
        return raw
    except Exception:
        if raw is None:
            elapsed = int((time.perf_counter() - started) * 1000)
            _write_worker_receipt(
                root=root,
                out_dir=out_dir,
                stage=stage,
                payload=payload,
                prompt=prompt,
                result=None,
                findings=findings or ["worker-call:failed"],
                duration_ms=elapsed,
                repair_attempted=repair_attempted,
                injected=injected,
                exit_status="failed",
            )
        raise


def _preflight_contract(hint: Mapping[str, Any]) -> dict[str, Any]:
    lane = hint.get("verification_lane")
    owners = [str(item) for item in hint.get("production_owners", []) if isinstance(item, str) and item]
    if lane == "unit":
        default_complexity = "simple"
    elif lane in {"integration", "matrix"}:
        default_complexity = "complex"
    else:
        default_complexity = "architectural"
    complexity = hint.get("complexity_class")
    if complexity not in _COMPLEXITY_ORDER:
        complexity = default_complexity
    context_required = hint.get("context_lookup_required")
    if not isinstance(context_required, bool):
        context_required = bool(len(owners) > 1 or lane in {"integration", "matrix", "runtime"})
    reason = hint.get("context_lookup_reason")
    if not isinstance(reason, str) or not reason.strip():
        reason = (
            "cross-owner or non-unit verification requires implementation context"
            if context_required
            else "single-owner unit verification is locally attributable"
        )
    minimum = hint.get("minimum_red_scope")
    if not isinstance(minimum, str) or not minimum.strip():
        minimum = "one bound Acceptance group, its failure family, and all declared assertion ids"
    upgrades = hint.get("upgrade_conditions")
    if not isinstance(upgrades, list) or any(not isinstance(item, str) or not item for item in upgrades):
        upgrades = [
            "selector spans multiple test roots",
            "independent failure mechanisms require separate observations",
            "runtime or detached judge evidence becomes mandatory",
        ]
    return {
        "complexity_class": complexity,
        "verification_lane": lane,
        "context_lookup_required": context_required,
        "context_lookup_reason": reason.strip(),
        "minimum_red_scope": minimum.strip(),
        "upgrade_conditions": list(upgrades),
    }


def compile_acceptances_with_preflight(
    *,
    root: Path,
    out_dir: Path,
    obligations: Sequence[Mapping[str, Any]],
    worker_cache: Mapping[str, Any] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    acceptances, failures, hints = _ORIGINAL_COMPILE_ACCEPTANCES(
        root=root,
        out_dir=out_dir,
        obligations=obligations,
        worker_cache=worker_cache,
    )
    normalized_hints: list[dict[str, Any]] = []
    for raw in hints:
        if not isinstance(raw, Mapping):
            raise ValueError("slice hint must be object")
        hint = dict(raw)
        hint.update(_preflight_contract(hint))
        normalized_hints.append(hint)

    enriched_acceptances: list[dict[str, Any]] = []
    for acceptance in acceptances:
        target = set(acceptance.get("obligation_ids", []))
        matches = [hint for hint in normalized_hints if set(hint.get("obligation_ids", [])) == target]
        if len(matches) != 1:
            raise ValueError(f"Acceptance {acceptance.get('acceptance_id')} preflight contract is ambiguous")
        item = dict(acceptance)
        item.update(_preflight_contract(matches[0]))
        enriched_acceptances.append(item)
    return enriched_acceptances, failures, normalized_hints


def partition_slices_with_preflight(
    obligations: Sequence[Mapping[str, Any]],
    acceptances: Sequence[Mapping[str, Any]],
    failures: Sequence[Mapping[str, Any]],
    hints: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Mapping[str, Any]]]:
    slices, by_acceptance = _ORIGINAL_PARTITION_SLICES(obligations, acceptances, failures, hints)
    acceptance_by_id = {str(item["acceptance_id"]): item for item in acceptances}
    enriched: list[dict[str, Any]] = []
    for raw in slices:
        item = dict(raw)
        contracts = [
            _preflight_contract(acceptance_by_id[aid])
            for aid in item.get("acceptance_ids", [])
            if aid in acceptance_by_id
        ]
        if not contracts:
            raise ValueError(f"slice {item.get('slice_id')} lacks preflight contracts")
        complexity = max((c["complexity_class"] for c in contracts), key=lambda value: _COMPLEXITY_ORDER[value])
        item.update({
            "complexity_class": complexity,
            "context_lookup_required": any(c["context_lookup_required"] for c in contracts),
            "context_lookup_reason": " | ".join(sorted({c["context_lookup_reason"] for c in contracts})),
            "minimum_red_scope": " | ".join(sorted({c["minimum_red_scope"] for c in contracts})),
            "upgrade_conditions": sorted({condition for c in contracts for condition in c["upgrade_conditions"]}),
        })
        enriched.append(item)
    return enriched, by_acceptance


def validate_semantic_bundle_with_preflight(bundle: Mapping[str, Any]) -> tuple[bool, list[str]]:
    valid, findings = _ORIGINAL_VALIDATE_SEMANTIC_BUNDLE(bundle)
    findings = list(findings)
    for label in ("acceptances", "slices"):
        values = bundle.get(label)
        if not isinstance(values, list):
            continue
        for index, item in enumerate(values):
            if not isinstance(item, Mapping):
                continue
            missing = _PREFLIGHT_FIELDS - set(item)
            if missing:
                findings.append(f"{label}[{index}]:preflight-fields:" + ",".join(sorted(missing)))
                continue
            if item.get("complexity_class") not in _COMPLEXITY_ORDER:
                findings.append(f"{label}[{index}]:complexity-class")
            if item.get("verification_lane") not in {"unit", "integration", "matrix", "runtime"}:
                findings.append(f"{label}[{index}]:verification-lane")
            if not isinstance(item.get("context_lookup_required"), bool):
                findings.append(f"{label}[{index}]:context-lookup-required")
            for field in ("context_lookup_reason", "minimum_red_scope"):
                if not isinstance(item.get(field), str) or not item[field].strip():
                    findings.append(f"{label}[{index}]:{field}")
            upgrades = item.get("upgrade_conditions")
            if not isinstance(upgrades, list) or not upgrades or any(not isinstance(value, str) or not value for value in upgrades):
                findings.append(f"{label}[{index}]:upgrade-conditions")
    return bool(valid and not findings), findings


# Patch the canonical module at import time. Its compile_plan function resolves these
# names from the module globals, so all stable calls pass through the normative gate.
sc.invoke_worker = normative_invoke_worker
sc.compile_acceptances = compile_acceptances_with_preflight
sc.partition_slices = partition_slices_with_preflight
sc.validate_semantic_bundle = validate_semantic_bundle_with_preflight


def _resolved_atomic_recall_worker(*, root, out_dir, payload, prompt, worker_cache):
    """ADR-0041: reuse a completed judgment, including a schema-repair result.

    Cache schema-valid failures as well as successes. Never select between old
    raw and repair caches; this receipt is created only by a completed invocation.
    Explicit injected fixtures retain precedence and are never persisted here.
    """
    stage = "v4-atomic-recall"
    if worker_cache is not None:
        return sc.invoke_worker(root=root, out_dir=out_dir, stage=stage, payload=payload,
                                prompt=prompt, worker_cache=worker_cache)
    identity = {"schema": "vdd.resolved-atomic-recall.v1", "stage": stage,
                "input_sha256": sc.sha256_value(payload), "prompt_sha256": sc.sha256_value(prompt)}
    cache_root = Path(out_dir) / ".compiler-work" / "resolved-atomic-recall"
    path = cache_root / (sc.sha256_value(identity).split(":")[-1] + ".json")
    cached = path.is_file()
    if cached:
        receipt = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(receipt, Mapping) or any(receipt.get(k) != v for k, v in identity.items()):
            raise ValueError("resolved atomic recall identity mismatch")
        raw = receipt.get("result")
        if receipt.get("result_sha256") != sc.sha256_value(raw):
            raise ValueError("resolved atomic recall result hash mismatch")
        # A prior worker may have returned a schema-valid but empty judgment
        # after truncation/transport loss.  Such a cache is not a reusable
        # semantic decision when active obligations exist; retain the receipt
        # for history but obtain a fresh bounded judgment.
        if (isinstance(raw, Mapping)
                and isinstance(raw.get("supported_obligation_ids"), list)
                and not raw.get("supported_obligation_ids")
                and not raw.get("source_gap_claims")
                and isinstance(payload.get("obligations"), list)
                and payload.get("obligations")):
            # Preserve the immutable historical receipt and use a distinct
            # retry identity for the bounded re-invocation below.
            retry_identity = {**identity, "retry": 1}
            path = cache_root / (sc.sha256_value(retry_identity).split(":")[-1] + ".json")
            identity = retry_identity
            cached = path.is_file()
            if cached:
                retry_receipt = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(retry_receipt, Mapping) or any(
                        retry_receipt.get(k) != v for k, v in identity.items()):
                    raise ValueError("resolved atomic recall retry identity mismatch")
                raw = retry_receipt.get("result")
                if retry_receipt.get("result_sha256") != sc.sha256_value(raw):
                    raise ValueError("resolved atomic recall retry result hash mismatch")
            else:
                raw = None
    else:
        raw = sc.invoke_worker(root=root, out_dir=out_dir, stage=stage, payload=payload,
                               prompt=prompt, worker_cache=None)
    if not cached and raw is None:
        raw = sc.invoke_worker(root=root, out_dir=out_dir, stage=stage,
                               payload=payload, prompt=prompt, worker_cache=None)
    from semantic_worker_v4_domain_patch import _domain_findings
    if not isinstance(raw, Mapping):
        raise ValueError("resolved atomic recall result must be object")
    findings = _worker_schema_findings(stage, raw) + _domain_findings(stage, payload, raw)
    if findings:
        raise ValueError("resolved atomic recall contract invalid: " + ";".join(findings))
    if not cached:
        sc.atomic_json(path, {**identity, "result": raw, "result_sha256": sc.sha256_value(raw), "authorizes": []})
    return raw


def atomic_recall_alignment(
    *,
    root: Path,
    out_dir: Path,
    source_index: Mapping[str, Any],
    obligations: Sequence[Mapping[str, Any]],
    worker_cache: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Independently compare frozen source claims with the V1 obligation set."""
    all_obligations = list(obligations)
    payload = {"source_index": source_index, "obligations": all_obligations}
    prompt = (
        "Independently compare each frozen requirement source to the proposed atomic obligations. "
        "Do not trust the prior extractor and do not read another worker's reasoning. Return JSON with "
        "supported_obligation_ids[], invented_obligation_ids[], source_gap_claims[]. "
        "Classify EVERY active obligation id listed in INPUT exactly once as supported or invented; never return a "
        "partial/representative list. Each source_gap_claim must be an object with source_ref, subject, behavior, "
        "reason and must describe one independently observable behavior present in source but absent from the "
        "obligation set. An obligation that merges multiple independent source behaviors is not sufficient coverage: "
        "report the unrepresented behavior as a source_gap_claim. Never invent runtime evidence."
    )

    # Large obligation domains exceed the practical structured-output context of
    # a single worker.  Compile deterministic batches, then merge the judgments;
    # this is one classification per obligation, not an independent vote.
    batch_size = 80
    if len(all_obligations) > batch_size:
        compact_context = [
            {key: item.get(key) for key in
             ("obligation_id", "subject", "source_refs", "expected_behavior")
             if key in item}
            for item in all_obligations if isinstance(item, Mapping)
        ]
        merged_supported: list[str] = []
        merged_invented: list[str] = []
        merged_gaps: list[Mapping[str, Any]] = []
        for start in range(0, len(all_obligations), batch_size):
            batch = all_obligations[start:start + batch_size]
            batch_payload = {"source_index": source_index, "obligations": batch,
                             "complete_obligation_context": compact_context,
                             "review_source_gaps": start == 0}
            batch_raw = _resolved_atomic_recall_worker(
                root=root, out_dir=out_dir, payload=batch_payload,
                worker_cache=worker_cache, prompt=prompt +
                " This is a bounded output batch; classify every active id in obligations only. "
                "complete_obligation_context is the entire candidate: an obligation outside this batch "
                "can cover source behavior and must not be reported missing merely because it is outside the batch. "
                "When review_source_gaps is true, review ALL frozen sources against the ENTIRE candidate "
                "and report every source gap. Otherwise only classify this batch and return source_gap_claims=[]."
            )
            merged_supported.extend(str(v) for v in batch_raw.get("supported_obligation_ids", []) if isinstance(v, str))
            merged_invented.extend(str(v) for v in batch_raw.get("invented_obligation_ids", []) if isinstance(v, str))
            merged_gaps.extend(v for v in batch_raw.get("source_gap_claims", []) if isinstance(v, Mapping))
        # A frozen obligation may be classified by more than one bounded batch
        # when the worker sees overlapping context.  Deduplicate only at the
        # merge boundary; single-batch worker output remains strictly checked.
        raw = {"supported_obligation_ids": list(dict.fromkeys(merged_supported)),
               "invented_obligation_ids": list(dict.fromkeys(merged_invented)),
               "source_gap_claims": merged_gaps}
    else:
        raw = _resolved_atomic_recall_worker(
            root=root, out_dir=out_dir, payload=payload,
            worker_cache=worker_cache, prompt=prompt)
    for key in ("supported_obligation_ids", "invented_obligation_ids", "source_gap_claims"):
        if not isinstance(raw.get(key), list):
            raise ValueError(f"atomic recall oracle missing {key}")

    known = {str(item["obligation_id"]) for item in obligations if item.get("status") == "active"}
    source_refs = {str(item["source_ref"]) for item in source_index.get("entries", []) if isinstance(item, Mapping)}
    supported = {str(value) for value in raw["supported_obligation_ids"] if isinstance(value, str)}
    invented = {str(value) for value in raw["invented_obligation_ids"] if isinstance(value, str)}
    findings: list[str] = []

    unknown_supported = supported - known
    unknown_invented = invented - known
    if unknown_supported:
        findings.append("atomic-recall:unknown-supported:" + ",".join(sorted(unknown_supported)))
    if unknown_invented:
        findings.append("atomic-recall:unknown-invented:" + ",".join(sorted(unknown_invented)))
    if supported & invented:
        findings.append("atomic-recall:supported-invented-overlap:" + ",".join(sorted(supported & invented)))
    if (supported | invented) != known:
        findings.append("atomic-recall:obligation-partition-incomplete:" + ",".join(sorted(known - (supported | invented))))

    normalized_gaps: list[dict[str, str]] = []
    seen_gap_keys: set[tuple[str, str, str]] = set()
    for index, raw_gap in enumerate(raw["source_gap_claims"]):
        if not isinstance(raw_gap, Mapping):
            findings.append(f"atomic-recall:gap[{index}]:not-object")
            continue
        source_ref = raw_gap.get("source_ref")
        subject = raw_gap.get("subject")
        behavior = raw_gap.get("behavior")
        reason = raw_gap.get("reason")
        if not all(isinstance(value, str) and value.strip() for value in (source_ref, subject, behavior, reason)):
            findings.append(f"atomic-recall:gap[{index}]:shape")
            continue
        source_ref = str(source_ref).strip()
        subject = str(subject).strip()
        behavior = str(behavior).strip()
        reason = str(reason).strip()
        if source_ref not in source_refs:
            findings.append(f"atomic-recall:gap[{index}]:unknown-source-ref")
            continue
        key = (source_ref, subject.casefold(), behavior.casefold())
        if key in seen_gap_keys:
            findings.append(f"atomic-recall:gap[{index}]:duplicate")
            continue
        seen_gap_keys.add(key)
        normalized_gaps.append({"source_ref": source_ref, "subject": subject, "behavior": behavior, "reason": reason})

    if invented:
        findings.append("atomic-recall:invented-obligation:" + ",".join(sorted(invented)))
    if normalized_gaps:
        findings.append("atomic-recall:source-gap-count:" + str(len(normalized_gaps)))

    true_positive = len(supported & known)
    false_positive = len(invented & known)
    false_negative = len(normalized_gaps) + len(known - (supported | invented))
    precision = true_positive / (true_positive + false_positive) if (true_positive + false_positive) else 0.0
    recall = true_positive / (true_positive + false_negative) if (true_positive + false_negative) else (1.0 if not known else 0.0)
    f1 = (2.0 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    metrics = {
        "active_obligation_count": len(known),
        "supported_obligation_count": true_positive,
        "invented_obligation_count": false_positive,
        "source_gap_count": len(normalized_gaps),
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
    }
    return {
        "schema": "vdd.atomic-recall-alignment.v1",
        "valid": not findings,
        "findings": findings,
        "metrics": metrics,
        "source_gap_claims": normalized_gaps,
        "worker": dict(raw),
        "authorizes": [],
    }


def _completed_resume(
    out_dir: Path,
    *,
    source_index_sha256: str,
    profile: str,
) -> dict[str, Any] | None:
    state_path = out_dir / "compiler-state.v1.json"
    bundle_path = out_dir / "semantic-plan-bundle.v1.json"
    if not state_path.is_file() or not bundle_path.is_file():
        return None
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if not isinstance(state, Mapping) or state.get("state") != "plan-ready":
        return None
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    if not isinstance(bundle, Mapping):
        return None
    source_index_path = out_dir / "source-index.v1.json"
    if not source_index_path.is_file():
        return {
            "status": "repair-vdd",
            "stage": "resume-context",
            "reason": "completed plan is missing its bound source index",
            "resume_strategy": "context-mismatch",
        }
    prior_source_index = json.loads(source_index_path.read_text(encoding="utf-8"))
    if not isinstance(prior_source_index, Mapping):
        raise ValueError("resume found malformed source index")
    if prior_source_index.get("sha256") != source_index_sha256:
        return {
            "status": "repair-vdd",
            "stage": "resume-context",
            "reason": "current VDD inputs differ from the completed plan",
            "resume_strategy": "context-mismatch",
        }
    if bundle.get("profile") != profile:
        return {
            "status": "repair-vdd",
            "stage": "resume-context",
            "reason": "current VDD profile differs from the completed plan",
            "resume_strategy": "context-mismatch",
        }
    current_bundle_sha256 = sc.sha256_value(bundle)
    if state.get("semantic_plan_sha256") != current_bundle_sha256:
        raise ValueError("resume found semantic bundle hash drift")
    valid, findings = validate_semantic_bundle_with_preflight(bundle)
    if not valid:
        raise ValueError("resume found invalid completed bundle: " + ",".join(findings))
    return {
        "status": "plan-ready",
        "plan_id": state.get("plan_id"),
        "semantic_plan_sha256": state.get("semantic_plan_sha256"),
        "slices": [item.get("slice_id") for item in bundle.get("slices", []) if isinstance(item, Mapping)],
        "resumed": True,
        "resume_from": "first-failed-stage",
        "resume_strategy": "validated-completed-state",
    }


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
    """Run fail-closed semantic compilation with optional cache-backed resume."""
    if resume_from not in {None, "first-failed-stage"}:
        raise ValueError("unsupported VDD resume mode")
    if recommendation_only and resume_from is not None:
        raise ValueError("recommendation-only cannot be combined with resume")
    root = sc.repository_root(requirements.parent)
    source_index = sc.build_source_index(root, requirements, companions)
    if resume_from == "first-failed-stage":
        completed = _completed_resume(
            out_dir,
            source_index_sha256=source_index["sha256"],
            profile=profile,
        )
        if completed is not None:
            return completed

    if recommendation_only:
        return _ORIGINAL_COMPILE_PLAN(
            requirements=requirements,
            out_dir=out_dir,
            companions=companions,
            profile=profile,
            worker_cache=worker_cache,
            recommendation_only=True,
        )

    preflight = sc.source_preflight(root, source_index)
    if not preflight["valid"]:
        return {"status": "repair-vdd", "stage": "V0A", "source_index": source_index, "preflight": preflight}

    obligations = sc.compile_obligations(root=root, out_dir=out_dir, source_index=source_index, worker_cache=worker_cache)
    guard = sc.guard_obligations(source_index, obligations)
    if not guard["valid"]:
        return {"status": "repair-vdd", "stage": "V2", "findings": guard["findings"]}

    acceptances, failures, _hints = sc.compile_acceptances(root=root, out_dir=out_dir, obligations=obligations, worker_cache=worker_cache)
    plan_preflight = sc.semantic_preflight(obligations, acceptances, failures)
    if not plan_preflight["valid"]:
        return {"status": "repair-vdd", "stage": "V3A", "findings": plan_preflight["findings"]}

    recall = atomic_recall_alignment(
        root=root,
        out_dir=out_dir,
        source_index=source_index,
        obligations=obligations,
        worker_cache=worker_cache,
    )
    sc.atomic_json(out_dir / "atomic-recall-alignment.v1.json", recall)
    if not recall["valid"]:
        return {
            "status": "repair-vdd",
            "stage": "V4",
            "gate": "atomic-source-recall",
            "findings": recall["findings"],
            "atomic_quality_metrics": recall["metrics"],
            "source_gap_claims": recall["source_gap_claims"],
        }

    result = _ORIGINAL_COMPILE_PLAN(
        requirements=requirements,
        out_dir=out_dir,
        companions=companions,
        profile=profile,
        worker_cache=worker_cache,
        recommendation_only=False,
    )
    result = dict(result)
    result["atomic_quality_metrics"] = recall["metrics"]
    if resume_from is not None:
        result["resumed"] = True
        result["resume_from"] = resume_from
        result["resume_strategy"] = "persistent-worker-cache-replay"
    return result
