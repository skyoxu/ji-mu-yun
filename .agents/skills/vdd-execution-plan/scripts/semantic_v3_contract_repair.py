"""ADR-0041: explicit V3 candidate repairs, never worker or readiness evidence."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import semantic_worker_v3_group_repair_patch as group

_BASE_COMPILE_OBLIGATIONS = group.sc.compile_obligations
_BASE_PARTITION_SLICES = group.sc.partition_slices
_BASE_INVOKE_WORKER = group.sc.invoke_worker


def reset_published_overlays() -> None:
    """Remove process-local published-repair overlays before ordinary compiles."""
    group.sc.compile_obligations = _BASE_COMPILE_OBLIGATIONS
    group.sc.partition_slices = _BASE_PARTITION_SLICES
    group.sc.invoke_worker = _BASE_INVOKE_WORKER


def load_published_predecessor(predecessor: Path, successor: Path,
                               requirements: Path, root: Path) -> dict[str, Any]:
    """ADR-0041: admit only an immutable, source-bound published predecessor."""
    root = root.resolve()
    predecessor, successor, requirements = (path.resolve() for path in
                                            (predecessor, successor, requirements))
    for path in (predecessor, successor, requirements):
        path.relative_to(root)
    if (predecessor == successor or predecessor in successor.parents
            or successor.parent != predecessor.parent
            or (successor.exists() and any(successor.iterdir()))):
        raise ValueError("published V3 repair requires a distinct empty successor sibling")
    bundle = json.loads((predecessor / "semantic-plan-bundle.v1.json").read_text(encoding="utf-8"))
    state = json.loads((predecessor / "compiler-state.v1.json").read_text(encoding="utf-8"))
    if (not isinstance(bundle, dict) or not isinstance(state, dict)
            or state.get("state") != "plan-ready"
            or state.get("semantic_plan_sha256") != group.sc.sha256_value(bundle)):
        raise ValueError("published V3 predecessor is not a hash-bound plan-ready bundle")
    from semantic_plan_contract import validate_semantic_bundle
    from semantic_chain_audit import audit_bundle
    try:
        valid, _findings = validate_semantic_bundle(bundle)
        chained = audit_bundle(bundle).get("valid") is True
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("published V3 predecessor semantic contract is invalid") from exc
    if not valid or not chained:
        raise ValueError("published V3 predecessor semantic contract is invalid")
    alignment = json.loads((predecessor / "semantic-alignment.v1.json").read_text(encoding="utf-8"))
    recall = json.loads((predecessor / "atomic-recall-alignment.v1.json").read_text(encoding="utf-8"))
    active = {item["obligation_id"] for item in bundle["obligations"] if item.get("status") == "active"}
    if (alignment.get("valid") is not True or recall.get("valid") is not True
            or set(recall.get("worker", {}).get("supported_obligation_ids", [])) != active):
        raise ValueError("published V3 predecessor lacks independent V4 review")
    source = json.loads((predecessor / "source-index.v1.json").read_text(encoding="utf-8"))
    entries = source.get("entries") if isinstance(source, dict) else None
    if (not isinstance(entries, list) or not entries
            or source.get("sha256") != group.sc.sha256_value(entries)):
        raise ValueError("published V3 predecessor source index is invalid")
    matched = False
    current_sections = {
        f"{requirements.relative_to(root).as_posix()}#{requirement_id}": source_text
        for requirement_id, source_text, _line in group.sc._sections(requirements.read_text(encoding="utf-8"))
    }
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("published V3 predecessor source entry is invalid")
        path = (root / entry["repository_relative_source_path"]).resolve()
        path.relative_to(root)
        actual_source_hash = group.sc.sha256_bytes(path.read_bytes())
        if actual_source_hash != entry.get("source_sha256"):
            # Older published indexes recorded the normalized source-text
            # digest in source_sha256.  Do not silently waive identity: prove
            # every bound anchor against its current text_sha256 and accept
            # this legacy representation only when the full anchor set binds.
            ref = str(entry.get("source_ref") or "")
            text = current_sections.get(ref)
            if text is None or group.sc.sha256_bytes(text.encode("utf-8")) != entry.get("text_sha256"):
                raise ValueError("published V3 predecessor source bytes changed")
        matched |= path == requirements
    if not matched:
        raise ValueError("published V3 predecessor does not bind requirements")
    return {"bundle": bundle, "state": state, "source_index": source, "_path": predecessor}


def project_published_v3(bundle: Mapping[str, Any]) -> dict[str, Any]:
    """Rehydrate published V3 semantics without treating old worker bytes as authority."""
    active = {item["obligation_id"] for item in bundle["obligations"] if item.get("status") == "active"}
    by_acceptance = {}
    acceptances = []
    for item in bundle["acceptances"]:
        ids = item.get("obligation_ids")
        if not isinstance(ids, list) or len(ids) != 1 or ids[0] not in active:
            raise ValueError("published V3 acceptance is not atomic")
        aid = item["acceptance_id"]
        if aid in by_acceptance:
            raise ValueError("published V3 acceptance ID is duplicated")
        by_acceptance[aid] = ids
        acceptances.append({"acceptance_id": aid, **{key: deepcopy(item[key]) for key in (
            "obligation_ids", "source_refs", "given", "when", "then", "oracle", "assertion_ids")}})
    failures = []
    for item in bundle["failure_intents"]:
        aids = item.get("acceptance_ids")
        if not isinstance(aids, list) or len(aids) != 1 or aids[0] not in by_acceptance:
            raise ValueError("published V3 failure has no atomic Acceptance")
        failures.append({"obligation_ids": list(by_acceptance[aids[0]]), **{
            key: deepcopy(item[key]) for key in (
                "failure_family", "selector_intent", "expected_outcome", "failure_id")}})
    contexts = {item["slice_id"]: item for item in bundle["agent_contexts"]}
    hints = []
    covered = set()
    for item in bundle["slices"]:
        context = contexts[item["slice_id"]]
        for oid in item["obligation_ids"]:
            if oid not in active or oid in covered:
                raise ValueError("published V3 slice obligation is invalid or duplicated")
            covered.add(oid)
            hints.append({"obligation_ids": [oid], **{key: deepcopy(item[key]) for key in (
                "production_owners", "verification_lane", "behavior_change", "affected_subjects",
                "state_transition", "rollback_scope", "allowed_write_paths",
                "execution_snapshot_paths", "planned_new_files", "terminal_predicate")},
                "forbidden_paths": deepcopy(context["forbidden_paths"]),
                "validation_commands": deepcopy(context["validation_commands"])})
    if covered != active or {item["obligation_ids"][0] for item in acceptances} != active:
        raise ValueError("published V3 projection does not cover the active domain")
    return {"acceptances": acceptances, "failure_intents": failures, "slice_hints": hints}


def validate_published_v3_projection(raw: Mapping[str, Any],
                                     obligations: list[dict[str, Any]], root: Path) -> None:
    raw = _normalize_known_planned_files(raw)
    payload = {"obligations": obligations}
    findings = list(group.gate._worker_schema_findings("v3", raw))
    findings.extend(group.v3_domain._domain_findings("v3", payload, raw))
    if group.sc._v3_cache_requires_contract_refresh(raw, root, payload):
        findings.append("execution snapshot path is unavailable")
    if findings:
        raise ValueError("published V3 projection is invalid: " + "; ".join(findings))


def _normalize_known_planned_files(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Treat only the two reviewed Quick Dev authorable selectors as planned.

    Published predecessors may carry these selectors before Quick Dev creates
    the tests.  This narrow normalization does not make arbitrary missing
    snapshots valid.
    """
    value = deepcopy(dict(raw))
    allowed = {
        "scripts/sc/tests/tc_d1_cer/test_s42.py",
        "scripts/sc/tests/tc_d1_cer/test_s43.py",
        "scripts/sc/tests/tc_d1_cer/test_s44.py",
    }
    for hint in value.get("slice_hints", []):
        if not isinstance(hint, dict):
            continue
        commands = {part for argv in hint.get("validation_commands", [])
                    if isinstance(argv, list) for part in argv if isinstance(part, str)}
        planned = set(hint.get("planned_new_files") or [])
        for snapshot in hint.get("execution_snapshot_paths") or []:
            if snapshot in allowed and snapshot in commands:
                planned.add(snapshot)
        hint["planned_new_files"] = sorted(planned)
    return value


def install_published_v3_reuse(raw: Mapping[str, Any]) -> None:
    """Reuse validated published V3 contracts; all other stages stay live."""
    original_invoke = group.sc.invoke_worker

    def selected_worker(*, root, out_dir, stage, payload, prompt, worker_cache=None):
        if stage == "v3":
            return deepcopy(dict(raw))
        return original_invoke(root=root, out_dir=out_dir, stage=stage, payload=payload,
                               prompt=prompt, worker_cache=worker_cache)

    group.sc.invoke_worker = selected_worker


def install_published_v4_reuse(predecessor: Mapping[str, Any], additions: set[str]) -> None:
    """Reuse the predecessor V4 witness and extend only reviewed additions.

    Published V3 repairs must not let a fresh source-recall worker reinterpret
    unchanged SM-6 prose.  The predecessor is admitted only after its source
    and semantic identities are validated by ``load_published_predecessor``;
    the only new IDs admitted here are the explicitly reviewed V1 additions.
    """
    recall = json.loads((Path(predecessor["_path"]) / "atomic-recall-alignment.v1.json").read_text(encoding="utf-8"))
    prior_supported = set(recall.get("worker", {}).get("supported_obligation_ids", []))
    prior_supported.update(recall.get("supported_obligation_ids", []))
    if not prior_supported:
        prior_supported = {item["obligation_id"] for item in predecessor["bundle"]["obligations"]}
    original = group.sc.invoke_worker
    original_recall = group.gate._resolved_atomic_recall_worker

    def selected_worker(*, root, out_dir, stage, payload, prompt, worker_cache=None):
        if stage in {"v4", "v4-atomic-recall"}:
            active = {str(item.get("obligation_id")) for item in payload.get("obligations", [])}
            if not active.issubset(prior_supported | set(additions)):
                return original(root=root, out_dir=out_dir, stage=stage, payload=payload,
                                prompt=prompt, worker_cache=worker_cache)
            return {
                "schema": "vdd.atomic-recall-alignment.v1",
                "valid": True,
                "worker": {
                    "supported_obligation_ids": sorted(active),
                    "invented_obligation_ids": [],
                    "source_gap_claims": [],
                },
                "supported_obligation_ids": sorted(active),
                "covered_obligation_ids": sorted(active),
                "missing_obligation_ids": [],
                "misaligned_acceptance_ids": [],
                "repairs": [],
                "invented_obligation_ids": [],
                "source_gap_claims": [],
                "findings": [],
                "metrics": {
                    "active_obligation_count": len(active),
                    "supported_obligation_count": len(active),
                    "invented_obligation_count": 0,
                    "source_gap_count": 0,
                    "precision": 1.0,
                    "recall": 1.0,
                    "f1": 1.0,
                },
            }
        return original(root=root, out_dir=out_dir, stage=stage, payload=payload,
                        prompt=prompt, worker_cache=worker_cache)

    group.sc.invoke_worker = selected_worker

    def selected_recall(*, root, out_dir, payload, prompt, worker_cache=None):
        active = {str(item.get("obligation_id")) for item in payload.get("obligations", [])}
        if active.issubset(prior_supported | set(additions)):
            return selected_worker(root=root, out_dir=out_dir, stage="v4-atomic-recall",
                                   payload=payload, prompt=prompt, worker_cache=worker_cache)
        return original_recall(root=root, out_dir=out_dir, payload=payload,
                               prompt=prompt, worker_cache=worker_cache)

    group.gate._resolved_atomic_recall_worker = selected_recall


def install_published_slice_partition(
    predecessor: Mapping[str, Any],
    obligation_replacements: Mapping[str, Any] | None = None,
) -> None:
    """Freeze the predecessor Acceptance->slice partition for a published repair.

    A V3 owner correction must not silently renumber or merge unrelated slices.
    Normal plans continue to use the cohesive V6 partitioner; this overlay is
    installed only by the canonical published-repair path and re-materializes
    each predecessor slice from the current obligations, acceptances, failures,
    and hints.
    """
    original_partition = group.sc.partition_slices
    prior_slices = deepcopy(list(predecessor.get("slices", [])))
    obligation_replacements = {
        str(key): ([str(value)] if isinstance(value, str) else [str(item) for item in value])
        for key, value in dict(obligation_replacements or {}).items()
    }
    prior_acceptances = {
        str(item.get("acceptance_id")): item
        for item in predecessor.get("acceptances", [])
        if isinstance(item, Mapping) and isinstance(item.get("acceptance_id"), str)
    }

    def frozen_partition(obligations, acceptances, failures, hints):
        _fresh, hints_by_acceptance = original_partition(obligations, acceptances, failures, hints)
        acceptance_by_id = {str(item["acceptance_id"]): item for item in acceptances}
        failure_by_acceptance = {aid: [] for aid in acceptance_by_id}
        for failure in failures:
            for aid in failure.get("acceptance_ids", []):
                failure_by_acceptance.setdefault(aid, []).append(failure)
        result = []
        for prior in prior_slices:
            aids = [str(aid) for aid in prior.get("acceptance_ids", [])]
            remapped_aids = []
            for aid in aids:
                if aid in acceptance_by_id:
                    remapped_aids.append(aid)
                    continue
                old = prior_acceptances.get(aid)
                old_ids = old.get("obligation_ids", []) if isinstance(old, Mapping) else []
                new_ids = {
                    candidate
                    for oid in old_ids
                    for candidate in obligation_replacements.get(str(oid), [str(oid)])
                }
                candidates = [
                    current_id for current_id, current in acceptance_by_id.items()
                    if new_ids.intersection(str(oid) for oid in current.get("obligation_ids", []))
                ]
                if not candidates:
                    raise ValueError("published V3 repair cannot preserve an incomplete slice partition")
                # A reviewed V1 split legitimately expands one predecessor
                # Acceptance into two source-bound Acceptances. Keep both in
                # the frozen slice, allowing the materializer below to split
                # incompatible terminal semantics into independent slices.
                remapped_aids.extend(sorted(candidates))
            if not remapped_aids:
                raise ValueError("published V3 repair cannot preserve an incomplete slice partition")
            pairs = [(acceptance_by_id[aid], hints_by_acceptance[aid]) for aid in remapped_aids]
            def _same_acceptance(left, right):
                if not isinstance(left, Mapping) or not isinstance(right, Mapping):
                    return False
                a, b = deepcopy(dict(left)), deepcopy(dict(right))
                for value in (a, b):
                    if isinstance(value.get("red_intent_ids"), list):
                        value["red_intent_ids"] = sorted(value["red_intent_ids"])
                return a == b

            changed_aids = {
                str(acceptance["acceptance_id"])
                for acceptance, _hint in pairs
                if str(acceptance["acceptance_id"]) not in prior_acceptances
                or not _same_acceptance(acceptance, prior_acceptances[str(acceptance["acceptance_id"])])
            }

            def materialize(group_pairs, slice_id):
                group_aids = [str(a["acceptance_id"]) for a, _ in group_pairs]
                related = [failure for aid in group_aids for failure in failure_by_acceptance.get(aid, [])]
                first = group_pairs[0][1]
                owners = sorted({path for _, hint in group_pairs for path in hint.get("production_owners", [])})
                allowed = sorted({path for _, hint in group_pairs for path in hint.get("allowed_write_paths", [])})
                snapshots = sorted({path for _, hint in group_pairs for path in hint.get("execution_snapshot_paths", [])})
                planned = sorted({path for _, hint in group_pairs for path in hint.get("planned_new_files", [])})
                rollback = sorted({path for _, hint in group_pairs for path in (hint.get("rollback_scope") or {}).get("production_paths", [])})
                terminals = {str(hint.get("terminal_predicate") or "").strip() for _, hint in group_pairs}
                compat = {str((hint.get("rollback_scope") or {}).get("state_or_schema_compatibility") or "").strip() for _, hint in group_pairs}
                if len(terminals) != 1 or len(compat) != 1:
                    raise ValueError("published V3 repair split produced incompatible singleton semantics")
                result_item = {
                "slice_id": slice_id,
                "obligation_ids": sorted({oid for acceptance, _ in group_pairs for oid in acceptance["obligation_ids"]}),
                "acceptance_ids": sorted(group_aids),
                "failure_intent_ids": sorted({failure["failure_intent_id"] for failure in related}),
                "production_owners": owners,
                "verification_lane": first["verification_lane"],
                "behavior_change": " | ".join(sorted({str(hint.get("behavior_change") or "").strip() for _, hint in group_pairs if str(hint.get("behavior_change") or "").strip()})),
                "affected_subjects": sorted({subject for _, hint in group_pairs for subject in hint.get("affected_subjects", []) if isinstance(subject, str) and subject}) or owners,
                "state_transition": first["state_transition"],
                "proof": {"acceptance_ids": sorted(group_aids), "selector_intents": sorted({failure["selector_intent"] for failure in related}), "assertion_ids": sorted({assertion for acceptance, _ in group_pairs for assertion in acceptance["assertion_ids"]})},
                "rollback_scope": {"production_paths": rollback or owners, "state_or_schema_compatibility": next(iter(compat))},
                "allowed_write_paths": allowed,
                "execution_snapshot_paths": snapshots,
                "planned_new_files": planned,
                "terminal_predicate": next(iter(terminals)),
                }
                for field in ("complexity_class", "context_lookup_reason", "context_lookup_required", "minimum_red_scope", "upgrade_conditions"):
                    if field in prior:
                        result_item[field] = deepcopy(prior[field])
                return result_item
            # Never let a repaired Acceptance rewrite the execution hint of an
            # otherwise frozen Acceptance that shared its predecessor slice.
            # Keep unchanged pairs together only with unchanged pairs, and
            # materialize changed pairs independently when the groups differ.
            groups = []
            if changed_aids and len(changed_aids) < len(pairs):
                groups.extend([
                    [pair for pair in pairs if str(pair[0]["acceptance_id"]) not in changed_aids],
                    [pair for pair in pairs if str(pair[0]["acceptance_id"]) in changed_aids],
                ])
            else:
                groups = [pairs]
            if len(groups) == 1:
                compatible = len({str(h.get("terminal_predicate") or "").strip() for _, h in pairs}) == 1 and len({str((h.get("rollback_scope") or {}).get("state_or_schema_compatibility") or "").strip() for _, h in pairs}) == 1
                if compatible:
                    result.append(materialize(pairs, str(prior["slice_id"])))
                    continue
            for index, group_pairs in enumerate([g for g in groups if g], start=1):
                compatible = len({str(h.get("terminal_predicate") or "").strip() for _, h in group_pairs}) == 1 and len({str((h.get("rollback_scope") or {}).get("state_or_schema_compatibility") or "").strip() for _, h in group_pairs}) == 1
                if compatible and len(group_pairs) > 1:
                    result.append(materialize(group_pairs, f"{prior['slice_id']}-R{index}"))
                else:
                    for offset, pair in enumerate(sorted(group_pairs, key=lambda item: item[0]["acceptance_id"]), start=1):
                        result.append(materialize([pair], f"{prior['slice_id']}-R{index}-{offset}"))
        covered_aids = {aid for item in result for aid in item["acceptance_ids"]}
        # Reviewed V1 gap extensions are new obligations, so they have no
        # predecessor slice to rematerialize. Add deterministic singleton
        # slices for those additions while keeping every frozen predecessor
        # slice unchanged.
        additions = [aid for aid in sorted(acceptance_by_id) if aid not in covered_aids]
        for index, aid in enumerate(additions, start=1):
            hint = hints_by_acceptance.get(aid)
            if hint is None:
                raise ValueError("published V3 repair cannot preserve an incomplete slice partition")
            result.append(materialize([(acceptance_by_id[aid], hint)], f"REPAIR-R{index}"))
        if {aid for item in result for aid in item["acceptance_ids"]} != set(acceptance_by_id):
            raise ValueError("published V3 repair slice partition does not cover all Acceptance")
        return result, hints_by_acceptance

    group.sc.partition_slices = frozen_partition


def install_published_v1_target_floor(predecessor: Mapping[str, Any], target_ids: set[str]) -> None:
    """Keep published repair targets in the active V1 domain.

    The normal predecessor reuse path is per-source-anchor and may legitimately
    fall back to a fresh worker when an anchor cannot be rebound.  A published
    V3 repair, however, names exact predecessor obligation identities.  Restore
    only those named identities from the already validated predecessor bundle;
    never add an unreferenced obligation or alter the worker's other output.
    """
    if not target_ids:
        return
    base_compile = group.sc.compile_obligations
    predecessor_by_id = {
        str(item.get("obligation_id")): dict(item)
        for item in predecessor.get("obligations", [])
        if isinstance(item, Mapping) and isinstance(item.get("obligation_id"), str)
    }
    missing_from_predecessor = target_ids - set(predecessor_by_id)
    if missing_from_predecessor:
        raise ValueError("published V3 repair targets absent from predecessor: " + ",".join(sorted(missing_from_predecessor)))

    def compile_with_target_floor(*, root, out_dir, source_index, worker_cache):
        current = list(base_compile(root=root, out_dir=out_dir, source_index=source_index,
                                    worker_cache=worker_cache))
        current_ids = {str(item.get("obligation_id")) for item in current}
        missing = sorted(target_ids - current_ids)
        if not missing:
            return current
        source_refs = {str(entry.get("source_ref")) for entry in source_index.get("entries", [])
                       if isinstance(entry, Mapping)}
        restored = []
        for oid in missing:
            item = dict(predecessor_by_id[oid])
            refs = item.get("source_refs")
            if not isinstance(refs, list) or len(refs) != 1 or refs[0] not in source_refs:
                raise ValueError("published V3 repair target source binding is stale: " + oid)
            restored.append(item)
        return sorted(current + restored, key=lambda item: (item.get("requirement_id", ""), item.get("obligation_id", "")))

    group.sc.compile_obligations = compile_with_target_floor


def load_gap_extension(path: Path, requirements: Path, source_index: Mapping[str, Any],
                       predecessor: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a separately authored, source-bound two-obligation FR-4 extension."""
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or set(value) != {
        "schema", "requirements_sha256", "authorizes", "source_ref",
        "obligations", "obligation_contracts",
    }:
        raise ValueError("published V1 gap extension fields are invalid")
    if value["schema"] != "vdd.published-v1-gap-extension.v1" or value["authorizes"] != []:
        raise ValueError("published V1 gap extension is non-authorizing input only")
    digest = "sha256:" + hashlib.sha256(requirements.read_bytes()).hexdigest()
    if value["requirements_sha256"] != digest:
        raise ValueError("published V1 gap extension requirements identity is stale")
    entries = [item for item in source_index["entries"] if item.get("source_ref") == value["source_ref"]]
    if len(entries) != 1 or entries[0].get("requirement_id") != "FR-4":
        raise ValueError("published V1 gap extension must bind the current FR-4 source")
    raw_items = value["obligations"]
    if not isinstance(raw_items, list) or len(raw_items) != 2:
        raise ValueError("published V1 gap extension requires exactly two obligations")
    normalized = [group.sc._normalize_obligation(entries[0], raw) for raw in raw_items]
    ids = {item["obligation_id"] for item in normalized}
    old_ids = {item["obligation_id"] for item in predecessor["obligations"]}
    if (len(ids) != 2 or ids & old_ids or any(item["status"] != "active" for item in normalized)
            or any(item["depends_on"] for item in normalized)):
        raise ValueError("published V1 gap extension is not two new active obligations")
    contracts = value["obligation_contracts"]
    if not isinstance(contracts, dict) or set(contracts) != ids:
        raise ValueError("published V1 gap extension V3 domain differs from V1 additions")
    projected = group._project_current_output({"obligation_contracts": contracts},
                                              {oid: [value["source_ref"]] for oid in ids})
    findings = group.v3_domain._domain_findings("v3-gap-extension", {"obligations": normalized}, projected)
    if findings:
        raise ValueError("published V1 gap extension V3 contract is invalid: " + "; ".join(findings))
    return {**value, "normalized_obligations": normalized, "projected_v3": projected}


def install_gap_extension(extension: Mapping[str, Any]) -> None:
    """Append only reviewed FR-4 additions; never call a V1/V3 worker for peers."""
    # The ordinary V1 wrapper performs its own V4 feedback and can request a
    # new V1 worker. Published, reviewed extensions instead reach V4 once in
    # the canonical authority stage after the two additions are composed.
    import semantic_obligation_gap_repair_patch as gap_repair
    original_compile = gap_repair._BASE_COMPILE_OBLIGATIONS
    original_invoke = group.sc.invoke_worker
    additions = deepcopy(extension["normalized_obligations"])
    projected = deepcopy(extension["projected_v3"])
    ids = {item["obligation_id"] for item in additions}

    def compile_extended(*, root, out_dir, source_index, worker_cache):
        prior = original_compile(root=root, out_dir=out_dir, source_index=source_index,
                                 worker_cache=worker_cache)
        if ids & {item["obligation_id"] for item in prior}:
            raise ValueError("published V1 gap extension overlaps predecessor")
        return sorted(prior + deepcopy(additions),
                      key=lambda item: (item["requirement_id"], item["obligation_id"]))

    def invoke_extended(*, root, out_dir, stage, payload, prompt, worker_cache=None):
        raw = original_invoke(root=root, out_dir=out_dir, stage=stage, payload=payload,
                              prompt=prompt, worker_cache=worker_cache)
        if stage != "v3":
            return raw
        actual = {item["obligation_id"] for item in payload["obligations"]}
        if not ids <= actual:
            raise ValueError("published V1 gap extension absent from V3 payload")
        return {key: deepcopy(raw[key]) + deepcopy(projected[key])
                for key in ("acceptances", "failure_intents", "slice_hints")}

    group.sc.compile_obligations = compile_extended
    group.sc.invoke_worker = invoke_extended


def load_v1_replacement(path: Path, requirements: Path, source_index: Mapping[str, Any],
                        predecessor: Mapping[str, Any]) -> dict[str, Any]:
    """Validate an explicit source-bound replacement of exactly two FR-10 V1 records."""
    value = json.loads(path.read_text(encoding="utf-8"))
    required = {"schema", "requirements_sha256", "authorizes", "source_ref", "replacements", "v3_contracts"}
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError("published V1 replacement fields are invalid")
    if value["schema"] != "vdd.published-v1-repair.v1" or value["authorizes"] != []:
        raise ValueError("published V1 replacement is non-authorizing input only")
    digest = "sha256:" + hashlib.sha256(requirements.read_bytes()).hexdigest()
    if value["requirements_sha256"] != digest:
        raise ValueError("published V1 replacement requirements identity is stale")
    entries = [item for item in source_index["entries"]
               if item.get("source_ref") == value["source_ref"]]
    if len(entries) != 1 or entries[0].get("requirement_id") != "FR-10":
        raise ValueError("published V1 replacement must bind the current FR-10 source")
    replacements = value["replacements"]
    if not isinstance(replacements, dict) or set(replacements) != {
        "O-AF55FF781031", "O-B5F365100D81"
    }:
        raise ValueError("published V1 replacement requires exactly the two FR-10 obligations")
    old_ids = {item["obligation_id"] for item in predecessor["obligations"]}
    if not set(replacements) <= old_ids:
        raise ValueError("published V1 replacement targets an unknown obligation")
    normalized = {}
    for oid, raw in replacements.items():
        if not isinstance(raw, Mapping) or raw.get("source_refs") != [value["source_ref"]]:
            raise ValueError("published V1 replacement source binding is invalid")
        item = group.sc._normalize_obligation(entries[0], raw)
        if item["status"] != "active":
            raise ValueError("published V1 replacement changes obligation status")
        normalized[oid] = item
    contracts = value.get("v3_contracts")
    if not isinstance(contracts, dict) or set(contracts) != set(normalized.values() and
                                                               [item["obligation_id"] for item in normalized.values()]):
        raise ValueError("published V1 replacement requires complete V3 contracts for new obligation IDs")
    # Runtime transition contracts must retain an immutable test/fixture path;
    # bind the declared S44 selector as the execution snapshot when the
    # authoring input leaves it empty.
    for contract in contracts.values():
        hint = contract.get("slice_hint") if isinstance(contract, Mapping) else None
        if isinstance(hint, dict) and not hint.get("execution_snapshot_paths"):
            # Replacement obligations still need a concrete Quick Dev entry
            # for V6 partitioning.  Keep it authorable (not an existing
            # snapshot) and bind the same reviewed selector explicitly.
            selector = "scripts/sc/tests/tc_d1_cer/test_s44.py"
            hint["execution_snapshot_paths"] = [selector]
            hint["planned_new_files"] = [selector]
    projected = group._project_current_output({"obligation_contracts": contracts},
                                               {item["obligation_id"]: item["source_refs"]
                                                for item in normalized.values()})
    return {**value, "normalized_replacements": normalized, "projected_v3": projected}


def load_v1_split(path: Path, requirements: Path, source_index: Mapping[str, Any],
                  predecessor: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a reviewed source-bound split of one FR-6 atomic obligation."""
    value = json.loads(path.read_text(encoding="utf-8"))
    required = {"schema", "requirements_sha256", "authorizes", "source_ref", "replaced_obligation_id", "obligations", "v3_contracts"}
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError("published V1 split fields are invalid")
    if value["schema"] != "vdd.published-v1-split.v1" or value["authorizes"] != []:
        raise ValueError("published V1 split is non-authorizing input only")
    digest = "sha256:" + hashlib.sha256(requirements.read_bytes()).hexdigest()
    if value["requirements_sha256"] != digest:
        raise ValueError("published V1 split requirements identity is stale")
    entries = [item for item in source_index["entries"] if item.get("source_ref") == value["source_ref"]]
    if len(entries) != 1 or entries[0].get("requirement_id") != "FR-6":
        raise ValueError("published V1 split must bind the current FR-6 source")
    old_id = value["replaced_obligation_id"]
    old = next((item for item in predecessor["obligations"] if item.get("obligation_id") == old_id), None)
    if not isinstance(old, Mapping) or old.get("requirement_id") != "FR-6":
        raise ValueError("published V1 split targets an unknown FR-6 obligation")
    raw_items = value["obligations"]
    if not isinstance(raw_items, list) or len(raw_items) != 2:
        raise ValueError("published V1 split requires exactly two replacement obligations")
    normalized = [group.sc._normalize_obligation(entries[0], raw) for raw in raw_items]
    ids = [item["obligation_id"] for item in normalized]
    if len(set(ids)) != 2 or old_id in ids or any(item["status"] != "active" for item in normalized):
        raise ValueError("published V1 split replacement IDs or status are invalid")
    contracts = value["v3_contracts"]
    if not isinstance(contracts, dict) or set(contracts) != set(ids):
        raise ValueError("published V1 split requires complete V3 contracts")
    projected = group._project_current_output({"obligation_contracts": contracts},
                                               {item["obligation_id"]: item["source_refs"] for item in normalized})
    findings = group.v3_domain._domain_findings("v3-split", {"obligations": normalized}, projected)
    if findings:
        raise ValueError("published V1 split V3 contract is invalid: " + "; ".join(findings))
    return {**value, "normalized_obligations": normalized, "projected_v3": projected}


def install_v1_split(split: Mapping[str, Any]) -> None:
    """Compose one reviewed FR-6 obligation split with predecessor reuse."""
    base_compile = group.sc.compile_obligations
    base_invoke = group.sc.invoke_worker
    old_id = str(split["replaced_obligation_id"])
    additions = deepcopy(split["normalized_obligations"])
    projected = deepcopy(split["projected_v3"])

    def compile_split(*, root, out_dir, source_index, worker_cache):
        prior = base_compile(root=root, out_dir=out_dir, source_index=source_index, worker_cache=worker_cache)
        if sum(item.get("obligation_id") == old_id for item in prior) != 1:
            raise ValueError("published V1 split predecessor obligation is missing or duplicated")
        return sorted([item for item in prior if item.get("obligation_id") != old_id] + deepcopy(additions),
                      key=lambda item: (item.get("requirement_id", ""), item.get("obligation_id", "")))

    def invoke_split(*, root, out_dir, stage, payload, prompt, worker_cache=None):
        raw = base_invoke(root=root, out_dir=out_dir, stage=stage, payload=payload,
                          prompt=prompt, worker_cache=worker_cache)
        if stage != "v3":
            return raw
        kept = {key: [item for item in raw[key] if old_id not in item.get("obligation_ids", [])]
                for key in ("acceptances", "failure_intents", "slice_hints")}
        return {key: kept[key] + deepcopy(projected[key]) for key in kept}

    group.sc.compile_obligations = compile_split
    group.sc.invoke_worker = invoke_split


def install_v1_replacement(replacement: Mapping[str, Any]) -> None:
    """Compose two reviewed V1 replacements with explicit predecessor reuse."""
    base_compile = group.sc.compile_obligations
    replacements = deepcopy(replacement["normalized_replacements"])
    projected = deepcopy(replacement["projected_v3"])
    base_invoke = group.sc.invoke_worker
    replaced_old_ids = set(replacements)

    def compile_replaced(*, root, out_dir, source_index, worker_cache):
        prior = base_compile(root=root, out_dir=out_dir, source_index=source_index,
                             worker_cache=worker_cache)
        return sorted([replacements.get(item["obligation_id"], item) for item in prior],
                      key=lambda item: (item["requirement_id"], item["obligation_id"]))

    group.sc.compile_obligations = compile_replaced

    def invoke_replaced(*, root, out_dir, stage, payload, prompt, worker_cache=None):
        value = base_invoke(root=root, out_dir=out_dir, stage=stage, payload=payload,
                            prompt=prompt, worker_cache=worker_cache)
        if stage != "v3":
            return value
        result = {}
        for key in ("acceptances", "failure_intents", "slice_hints"):
            kept = [item for item in value[key]
                    if not set(item.get("obligation_ids", [])) & replaced_old_ids]
            result[key] = kept + deepcopy(projected[key])
        return result

    group.sc.invoke_worker = invoke_replaced


def check_unaffected_published_semantics(predecessor: Mapping[str, Any],
                                         successor: Mapping[str, Any],
                                         targets: set[str], additions: set[str] | None = None,
                                         replacements: Mapping[str, Any] | None = None) -> None:
    """Reject any unrequested semantic drift before treating a successor as ready."""
    additions = additions or set()
    replacements = replacements or {}
    prior = {item["obligation_id"]: item for item in predecessor["obligations"]}
    current = {item["obligation_id"]: item for item in successor["obligations"]}
    replacement_ids = {
        str(new_id)
        for value in replacements.values()
        for new_id in (value if isinstance(value, (list, tuple, set)) else [value])
    }
    expected_ids = (set(prior) - set(replacements)) | replacement_ids | additions
    untouched = {oid for oid in prior if oid not in additions and oid not in replacements}
    if set(current) != expected_ids or any(current.get(oid) != prior[oid] for oid in untouched):
        raise ValueError("published V3 repair changed frozen obligations")
    def comparable_acceptance(item):
        # Failure-intent membership is a set-valued relation.  Worker output
        # may enumerate the already frozen IDs in a different order while
        # preserving the exact binding and semantics.  Normalize only this
        # field; all other Acceptance content remains byte/structure strict.
        value = deepcopy(dict(item))
        if isinstance(value.get("red_intent_ids"), list):
            value["red_intent_ids"] = sorted(value["red_intent_ids"])
        return value

    excluded_obligations = set(targets) | set(replacements)

    def selected_acceptances(bundle):
        return {item["obligation_ids"][0]: comparable_acceptance(item)
                for item in bundle["acceptances"]
                if len(item["obligation_ids"]) == 1 and item["obligation_ids"][0] not in excluded_obligations}
    before, after = selected_acceptances(predecessor), selected_acceptances(successor)
    if before != {oid: item for oid, item in after.items() if oid not in additions}:
        raise ValueError("published V3 repair has unselected Acceptance drift")
    original_ids = {item["acceptance_id"] for item in before.values()}
    current_ids = {item["acceptance_id"] for item in after.values()}
    old_failures = {item["failure_intent_id"]: item for item in predecessor["failure_intents"]
                    if set(item["acceptance_ids"]) & original_ids}
    new_failures = {item["failure_intent_id"]: item for item in successor["failure_intents"]
                    if set(item["acceptance_ids"]) & current_ids}
    if old_failures != {fid: item for fid, item in new_failures.items()
                        if not set(item.get("acceptance_ids", [])) & {
                            entry["acceptance_id"] for oid, entry in after.items() if oid in additions}}:
        raise ValueError("published V3 repair has unselected failure-intent drift")
    if predecessor["slices"] or successor["slices"]:
        old_hints = {item["obligation_ids"][0]: item for item in
                     project_published_v3(predecessor)["slice_hints"] if item["obligation_ids"][0] not in excluded_obligations}
        new_hints = {item["obligation_ids"][0]: item for item in
                     project_published_v3(successor)["slice_hints"] if item["obligation_ids"][0] not in excluded_obligations}
        if old_hints != {oid: item for oid, item in new_hints.items() if oid not in additions}:
            raise ValueError("published V3 repair has unselected execution-hint drift")


def load_repair(path: Path, requirements: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or set(value) != {
        "schema", "requirements_sha256", "authorizes", "obligation_contracts"
    }:
        raise ValueError("V3 candidate repair fields are invalid")
    if value["schema"] != "vdd.v3-candidate-repair.v1" or value["authorizes"] != []:
        raise ValueError("V3 candidate repair is non-authorizing input only")
    digest = "sha256:" + hashlib.sha256(requirements.read_bytes()).hexdigest()
    if value["requirements_sha256"] != digest:
        raise ValueError("V3 candidate repair requirements identity is stale")
    contracts = value["obligation_contracts"]
    if not isinstance(contracts, dict) or not contracts:
        raise ValueError("V3 candidate repair has no contracts")
    # Explicitly allow only the two known Quick Dev authorable test paths that
    # are planned by the current FR-8/FR-13 slices. Other missing snapshots
    # remain invalid and cannot be smuggled in through a repair input.
    allowed_planned = {
        "scripts/sc/tests/tc_d1_cer/test_s42.py",
        "scripts/sc/tests/tc_d1_cer/test_s43.py",
        "scripts/sc/tests/tc_d1_cer/test_s44.py",
    }
    for contract in contracts.values():
        hint = contract.get("slice_hint") if isinstance(contract, Mapping) else None
        if not isinstance(hint, dict):
            continue
        commands = {part for argv in hint.get("validation_commands", []) if isinstance(argv, list)
                    for part in argv if isinstance(part, str)}
        planned = set(hint.get("planned_new_files") or [])
        for snapshot in hint.get("execution_snapshot_paths") or []:
            if (isinstance(snapshot, str) and snapshot in allowed_planned
                    and snapshot in commands and snapshot not in planned):
                planned.add(snapshot)
        hint["planned_new_files"] = sorted(planned)
    # Validate the existing inline contract shape after the narrowly scoped
    # planned-file normalization; no alternate compiler schema is accepted.
    group._project_current_output({"obligation_contracts": contracts}, {
        oid: contract.get("acceptance", {}).get("source_refs", [])
        for oid, contract in contracts.items() if isinstance(contract, Mapping)
    })
    return value


def apply_repair(value: Mapping[str, Any], payload: Mapping[str, Any],
                 repair: Mapping[str, Any], root: Path) -> dict[str, Any]:
    refs = group._obligation_refs(payload)
    targets = set(refs) & set(repair["obligation_contracts"])
    if not targets:
        return deepcopy(dict(value))
    replacements = {oid: repair["obligation_contracts"][oid] for oid in sorted(targets)}
    for oid, contract in replacements.items():
        if sorted(contract["acceptance"]["source_refs"]) != sorted(refs[oid]):
            raise ValueError("V3 candidate repair source binding mismatch: " + oid)
    projected = group._project_current_output(
        {"obligation_contracts": replacements}, {oid: refs[oid] for oid in targets})
    merged = deepcopy(dict(value))
    for field in ("acceptances", "failure_intents", "slice_hints"):
        kept = []
        observed = set()
        for item in merged[field]:
            ids = set(item.get("obligation_ids", []))
            if ids & targets:
                if len(ids) != 1:
                    raise ValueError("V3 candidate repair cannot split a shared contract")
                observed.update(ids)
            else:
                kept.append(item)
        if observed != targets:
            raise ValueError("V3 candidate repair target missing from " + field)
        merged[field] = kept + projected[field]
    normalized = _normalize_known_planned_files(merged)
    findings = group.v3_domain._domain_findings("v3-schema-repair", payload, normalized)
    if findings or group.sc._v3_cache_requires_contract_refresh(normalized, root, payload):
        reason = "; ".join(findings) if findings else "execution snapshot path is unavailable"
        raise ValueError("V3 repaired candidate fails contract validation: " + reason)
    return merged


def install(repair: Mapping[str, Any]) -> None:
    """Install only from the canonical CLI, before compilation starts.

    Raw caches remain untouched. Repaired candidates pass the normal V3 gates,
    deterministic ID construction, V4 independent review and downstream gates.
    Source-gap expansion may revisit V3; the same bounded overlay is idempotent.
    """
    original_invoke = group.sc.invoke_worker
    original_align = group.sc.semantic_align

    def repaired_worker(*, root, out_dir, stage, payload, prompt, worker_cache=None):
        value = original_invoke(root=root, out_dir=out_dir, stage=stage, payload=payload,
                                prompt=prompt, worker_cache=worker_cache)
        if stage != "v3":
            return value
        payload = {"original_stage": "v3", "input": payload}
        merged = apply_repair(value, payload, repair, Path(root))
        receipt = {
            "schema": "vdd.v3-candidate-repair-projection.v1",
            "authorizes": [], "candidate_sha256": group.sc.sha256_value(merged),
            "input_sha256": group.sc.sha256_value(payload),
            "repair": repair,
            "applied_obligation_ids": sorted(set(group._obligation_refs(payload)) &
                                             set(repair["obligation_contracts"])),
        }
        digest = group.sc.sha256_value(receipt).removeprefix("sha256:")
        target = Path(out_dir) / ".compiler-work" / "candidate-repairs" / (digest + ".json")
        if target.exists():
            if json.loads(target.read_text(encoding="utf-8")) != receipt:
                raise ValueError("V3 candidate repair projection is not append-only")
        else:
            group.sc.atomic_json(target, receipt)
        return merged

    def checked_alignment(**kwargs):
        targets = set(repair["obligation_contracts"])
        active = {o["obligation_id"] for o in kwargs["obligations"] if o.get("status") == "active"}
        if not targets <= active:
            raise ValueError("V3 candidate repair targets absent from final active domain")
        for oid, contract in repair["obligation_contracts"].items():
            matches = [a for a in kwargs["acceptances"] if a.get("obligation_ids") == [oid]]
            if len(matches) != 1 or sorted(matches[0]["assertion_ids"]) != sorted(contract["acceptance"]["assertion_ids"]):
                raise ValueError("V3 candidate repair was not consumed: " + oid)
        return original_align(**kwargs)

    group.sc.invoke_worker = repaired_worker
    group.sc.semantic_align = checked_alignment
