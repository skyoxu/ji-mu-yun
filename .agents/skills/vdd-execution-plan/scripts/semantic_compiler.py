"""VDD Chapter 4/5/6 semantic compiler, V0 through V7.

Semantic workers are read-only inputs. Deterministic stages own validation,
coverage, partitioning, feasibility, and final artifact publication.
"""
from __future__ import annotations

from semantic_progress import worker_call, stage_call

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Any, Mapping, Sequence

from semantic_plan_contract import STAGE_SCOPE, validate_semantic_bundle

REQ_ID_RE = re.compile(r"^(FR-[0-9]+|NFR-[0-9]+|SM-[A-Z0-9-]+)$")
HEADING_RE = re.compile(r"^#{1,6}\s*(FR-[0-9]+|NFR-[0-9]+|SM-[A-Z0-9-]+)\b(?:\s*[:：\-]\s*)?(.*)$", re.I)
INLINE_REQ_RE = re.compile(r"\b(FR-[0-9]+|NFR-[0-9]+|SM-[A-Z0-9-]+)\b", re.I)
CASE_ROW_RE = re.compile(r"^\|\s*([A-Z][0-9]{2})\s*\|", re.I)
ANCHORED_CASE_ROW_RE = re.compile(
    r'^\|\s*<a\s+id=["\'](SM-[A-Z][0-9]{2})["\']></a>([A-Z][0-9]{2})\s*\|',
    re.I,
)
TABLE_SEPARATOR_RE = re.compile(r"^\|(?:\s*:?-{3,}:?\s*\|)+\s*$")
FAILURE_FAMILIES = {
    "semantic-contract-gap", "artifact-integrity", "target-binding-failure",
    "test-harness-failure", "timeout-no-observation", "repo-noise",
    "unexpected-green", "expected-red", "task-implementation-failure",
    "repeated-deterministic-failure",
}
LANES = {"unit", "integration", "matrix", "runtime"}
RUNTIME_FIELDS = {
    "run_id", "candidate_hash", "receipt_ref", "receipt_sha256", "observation_id",
    "observation_ref", "observation_sha256", "result_ref", "result_sha256",
    "runtime_edge_ref", "runtime_edge_sha256", "current_snapshot_sha256",
    "exit_code", "timed_out", "process_attempts", "test_executions", "cases",
    "verification_outcome", "actual_stage_outcome", "predicate_result",
}


def repository_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / "AGENTS.md").is_file() and (candidate / ".agents").is_dir():
            return candidate
    raise ValueError("repository root not found")


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def sha256_value(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def safe_relative(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError("path must be repository-relative POSIX")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {".", ".."} for part in path.parts):
        raise ValueError("path escapes repository")
    return path.as_posix()


def _relative(root: Path, path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError("source path is outside repository") from exc


def atomic_json(path: Path, value: Any) -> None:
    payload = canonical_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError(f"immutable artifact conflict: {path}")
        return
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.link(temporary, path)
    except FileExistsError:
        if path.read_bytes() != payload:
            raise ValueError(f"immutable artifact race: {path}")
    finally:
        if temporary.exists():
            temporary.unlink()


def _sections(text: str) -> list[tuple[str, str, int]]:
    lines = text.splitlines()
    starts: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        match = HEADING_RE.match(line.strip())
        if match:
            starts.append((index, match.group(1).upper()))
    if not starts:
        for index, line in enumerate(lines):
            match = INLINE_REQ_RE.search(line)
            if match:
                req_id = match.group(1).upper()
                if not any(existing == req_id for _, existing in starts):
                    starts.append((index, req_id))
    result: list[tuple[str, str, int]] = []
    for position, (start, req_id) in enumerate(starts):
        end = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
        body = "\n".join(lines[start:end]).strip()
        if body:
            result.append((req_id, body, start + 1))
    return result


def _behavior_case_sections(text: str) -> list[tuple[str, str, int]]:
    """Extract stable atomic behavior rows from a repair-input case table."""
    anchored_rows: list[tuple[str, str, int]] = []
    for index, line in enumerate(text.splitlines()):
        match = ANCHORED_CASE_ROW_RE.match(line.strip())
        if not match:
            continue
        requirement_id = match.group(1).upper()
        if requirement_id != f"SM-{match.group(2).upper()}":
            raise ValueError(f"anchored behavior case id mismatch: {requirement_id}")
        anchored_rows.append((requirement_id, line.strip(), index + 1))

    # Anchored IDs are authoritative when a repair input supplies them. This
    # avoids treating unrelated two-character tables as requirements and keeps
    # companions as frozen context rather than duplicate requirement sources.
    rows = anchored_rows or [
        (f"SM-{match.group(1).upper()}", line.strip(), index + 1)
        for index, line in enumerate(text.splitlines())
        if (match := CASE_ROW_RE.match(line.strip()))
    ]
    result: list[tuple[str, str, int]] = []
    seen: set[str] = set()
    for requirement_id, source_text, line_no in rows:
        if requirement_id in seen:
            raise ValueError(f"duplicate behavior case id: {requirement_id}")
        seen.add(requirement_id)
        result.append((requirement_id, source_text, line_no))
    return result


def build_source_index(root: Path, requirements: Path, companions: Sequence[Path] = ()) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    order = 0
    relative = _relative(root, requirements)
    raw = requirements.read_bytes()
    text = raw.decode("utf-8")
    source_hash = sha256_bytes(raw)
    case_sections = _behavior_case_sections(text)
    sections = case_sections or _sections(text)
    for req_id, source_text, line_no in sections:
        if not REQ_ID_RE.fullmatch(req_id):
            continue
        source_ref = f"{relative}#{req_id}"
        if source_ref in seen:
            raise ValueError(f"duplicate source anchor: {source_ref}")
        seen.add(source_ref)
        order += 1
        entries.append({
            "requirement_id": req_id,
            "repository_relative_source_path": relative,
            "anchor": req_id,
            "source_ref": source_ref,
            "source_text": source_text,
            "source_sha256": source_hash,
            "text_sha256": sha256_bytes(source_text.encode("utf-8")),
            "source_order": order,
            "line": line_no,
        })
    companion_sources: list[dict[str, Any]] = []
    for companion in companions:
        companion_relative = _relative(root, companion)
        companion_raw = companion.read_bytes()
        companion_sources.append({
            "repository_relative_source_path": companion_relative,
            "source_sha256": sha256_bytes(companion_raw),
            "source_text": companion_raw.decode("utf-8"),
        })
    # ADR-0041: table inputs retain non-row rules and every companion as
    # independently recallable source, not merely optional worker context.
    additional = []
    if case_sections:
        remaining = "\n".join(
            line for line in text.splitlines()
            if not (
                CASE_ROW_RE.match(line.strip())
                or ANCHORED_CASE_ROW_RE.match(line.strip())
                or TABLE_SEPARATOR_RE.match(line.strip())
                or (line.strip().startswith("|") and "PIWR parents" in line)
            )
        ).strip()
        if remaining:
            additional.append((relative, raw, [("SM-REPAIR-CONSTRAINTS", remaining, 1)]))
    if not case_sections:
        for companion in companions:
            path = _relative(root, companion)
            content = companion.read_bytes()
            additional.append((path, content, _sections(content.decode("utf-8"))))
    for path, content, parts in additional:
        for req_id, source_text, line_no in parts:
            source_ref = f"{path}#{req_id}"
            if source_ref in seen:
                raise ValueError(f"duplicate source anchor: {source_ref}")
            seen.add(source_ref)
            order += 1
            entries.append({
                "requirement_id": req_id,
                "repository_relative_source_path": path,
                "anchor": req_id,
                "source_ref": source_ref,
                "source_text": source_text,
                "source_sha256": sha256_bytes(content),
                "text_sha256": sha256_bytes(source_text.encode("utf-8")),
                "source_order": order,
                "line": line_no,
            })
    if not entries:
        raise ValueError("no canonical requirement anchors found")
    ids = [entry["requirement_id"] for entry in entries]
    if len(ids) != len(set(ids)):
        raise ValueError("requirement ids are ambiguous across active sources")
    if not case_sections:
        return {"schema": "source-index.v1", "entries": entries, "sha256": sha256_value(entries)}
    identity = {"entries": entries, "companions": companion_sources}
    return {"schema": "source-index.v1", **identity, "sha256": sha256_value(identity)}


def source_preflight(root: Path, source_index: Mapping[str, Any]) -> dict[str, Any]:
    findings: list[str] = []
    entries = source_index.get("entries")
    if not isinstance(entries, list) or not entries:
        return {"valid": False, "recommended_action": "repair-vdd", "findings": ["source-index:empty"]}
    refs: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            findings.append(f"source[{index}]:not-object")
            continue
        req_id = entry.get("requirement_id")
        if not isinstance(req_id, str) or not REQ_ID_RE.fullmatch(req_id):
            findings.append(f"source[{index}]:requirement-id")
        path = entry.get("repository_relative_source_path")
        try:
            relative = safe_relative(str(path))
            full = (root / relative).resolve()
            full.relative_to(root.resolve())
            if not full.is_file() or full.is_symlink():
                findings.append(f"source[{index}]:unreadable")
            elif sha256_bytes(full.read_bytes()) != entry.get("source_sha256"):
                findings.append(f"source[{index}]:stale-source-hash")
        except (OSError, UnicodeError, ValueError):
            findings.append(f"source[{index}]:unsafe-path")
        ref = entry.get("source_ref")
        if not isinstance(ref, str) or not ref:
            findings.append(f"source[{index}]:source-ref")
        elif ref in refs:
            findings.append(f"source[{index}]:duplicate-ref")
        else:
            refs.add(ref)
        text = entry.get("source_text")
        if not isinstance(text, str) or not text.strip():
            findings.append(f"source[{index}]:empty-text")
    companions = source_index.get("companions", [])
    if not isinstance(companions, list):
        findings.append("companions:not-list")
        companions = []
    for index, companion in enumerate(companions):
        if not isinstance(companion, Mapping):
            findings.append(f"companion[{index}]:not-object")
            continue
        try:
            relative = safe_relative(str(companion.get("repository_relative_source_path")))
            full = (root / relative).resolve()
            full.relative_to(root.resolve())
            if not full.is_file() or full.is_symlink():
                findings.append(f"companion[{index}]:unreadable")
            elif sha256_bytes(full.read_bytes()) != companion.get("source_sha256"):
                findings.append(f"companion[{index}]:stale-source-hash")
        except (OSError, UnicodeError, ValueError):
            findings.append(f"companion[{index}]:unsafe-path")
        if not isinstance(companion.get("source_text"), str) or not companion["source_text"].strip():
            findings.append(f"companion[{index}]:empty-text")
    return {"valid": not findings, "recommended_action": "continue" if not findings else "repair-vdd", "findings": findings}


def _worker_cache_key(stage: str, payload: Any, prompt: str = "") -> str:
    """Bind cached worker output to both frozen input and extraction policy."""
    identity = {"payload": payload, "prompt": prompt} if prompt else payload
    return f"{stage}-{sha256_value(identity)[7:31]}.json"


def _parse_json_output(text: str) -> Mapping[str, Any]:
    stripped = text.strip()
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        start, end = stripped.find("{"), stripped.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("semantic worker did not return JSON")
        value = json.loads(stripped[start:end + 1])
    if not isinstance(value, Mapping):
        raise ValueError("semantic worker JSON must be an object")
    return value


def invoke_worker(*, root: Path, out_dir: Path, stage: str, payload: Mapping[str, Any], prompt: str, worker_cache: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    cache_dir = out_dir / ".compiler-cache"
    cache_path = cache_dir / _worker_cache_key(stage, payload, prompt)
    if cache_path.is_file():
        value = json.loads(cache_path.read_text(encoding="utf-8"))
        if not isinstance(value, Mapping):
            raise ValueError("worker cache is malformed")
        return value
    if worker_cache and stage in worker_cache:
        value = worker_cache[stage]
        if not isinstance(value, Mapping):
            raise ValueError(f"injected worker cache {stage} must be object")
        atomic_json(cache_path, value)
        return value
    sc = root / "scripts" / "sc"
    if str(sc) not in sys.path:
        sys.path.insert(0, str(sc))
    try:
        from _llm_backend import run_llm_exec, resolve_llm_backend
    except ImportError as exc:
        raise RuntimeError("shared LLM backend is unavailable") from exc
    work = out_dir / ".compiler-work"
    output = work / f"{stage}-last-message.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    full_prompt = (
        "You are a read-only semantic compiler worker. Do not modify files. "
        "Return JSON only. Do not invent requirements or runtime evidence.\n\n"
        + prompt + "\n\nINPUT:\n" + json.dumps(payload, ensure_ascii=False, sort_keys=True)
    )
    code, trace, _argv = worker_call(run_llm_exec, progress_dir=out_dir, progress_stage=stage,
        backend=resolve_llm_backend(None), root=root, prompt=full_prompt,
        output_last_message=output, timeout_sec=180,
        codex_configs=["model_reasoning_effort=\"high\""], codex_sandbox="read-only",
    )
    if code != 0 or not output.is_file():
        raise RuntimeError(f"semantic worker {stage} failed: {trace.strip()[:500]}")
    value = _parse_json_output(output.read_text(encoding="utf-8"))
    atomic_json(cache_path, value)
    return value


def _normalize_obligation(entry: Mapping[str, Any], raw: Mapping[str, Any]) -> dict[str, Any]:
    required = ("subject", "trigger", "state_before", "state_after", "expected_behavior", "observable_result")
    for key in required:
        if not isinstance(raw.get(key), str) or not str(raw[key]).strip():
            raise ValueError(f"obligation missing {key}")
    source_refs = raw.get("source_refs")
    if not isinstance(source_refs, list) or not source_refs or any(ref != entry["source_ref"] for ref in source_refs):
        raise ValueError("obligation source refs must bind the active requirement source")
    requirement_type = raw.get("requirement_type")
    if requirement_type not in {"Product", "Platform", "Governance"}:
        raise ValueError("obligation requirement_type is invalid")
    kind = raw.get("obligation_kind", "behavior")
    if kind not in {"behavior", "quality", "constraint", "governance"}:
        raise ValueError("obligation kind is invalid")
    semantics = {
        "requirement_id": entry["requirement_id"], "source_refs": source_refs,
        "subject": str(raw["subject"]).strip(), "trigger": str(raw["trigger"]).strip(),
        "state_before": str(raw["state_before"]).strip(), "state_after": str(raw["state_after"]).strip(),
        "expected_behavior": str(raw["expected_behavior"]).strip(),
        "observable_result": str(raw["observable_result"]).strip(),
    }
    obligation_id = "O-" + sha256_value(semantics)[7:19].upper()
    unresolved = raw.get("unresolved_fragments", [])
    forbidden = raw.get("forbidden_result", [])
    depends = raw.get("depends_on", [])
    for name, value in (("unresolved_fragments", unresolved), ("forbidden_result", forbidden), ("depends_on", depends)):
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise ValueError(f"obligation {name} is invalid")
    status = raw.get("status", "active")
    if status not in {"active", "deferred", "not_applicable"}:
        raise ValueError("obligation status is invalid")
    return {
        "obligation_id": obligation_id, "requirement_id": entry["requirement_id"],
        "source_refs": list(source_refs), "subject": semantics["subject"], "trigger": semantics["trigger"],
        "state_before": semantics["state_before"], "state_after": semantics["state_after"],
        "expected_behavior": semantics["expected_behavior"], "observable_result": semantics["observable_result"],
        "forbidden_result": list(forbidden), "requirement_type": requirement_type,
        "obligation_kind": kind, "unresolved_fragments": list(unresolved), "status": status,
        "depends_on": list(depends),
    }


def _entry_companion_context(entry: Mapping[str, Any], companions: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Keep a repair case's semantic context to its declared source owner.

    The complete companion set remains frozen in the source index and V4
    recall.  V1 must not resend every companion to every case row: that makes
    unrelated clauses look bound to the row and multiplies output volume.
    """
    text = str(entry.get("source_text") or "")
    cells = [cell.strip() for cell in text.strip().strip("|").split("|")]
    if len(cells) < 6 or not str(entry.get("requirement_id") or "").startswith("SM-"):
        return list(companions)
    owner = Path(cells[4]).name.casefold()
    selected = [
        companion for companion in companions
        if Path(str(companion.get("repository_relative_source_path") or "")).name.casefold() == owner
    ]
    return selected or list(companions)


def compile_obligations(*, root: Path, out_dir: Path, source_index: Mapping[str, Any], worker_cache: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    obligations: list[dict[str, Any]] = []
    for entry in source_index["entries"]:
        stage = f"v1-{entry['requirement_id']}"
        payload = {"source": entry}
        if "companions" in source_index:
            payload["companions"] = _entry_companion_context(entry, source_index["companions"])
        raw = invoke_worker(
            root=root, out_dir=out_dir, stage=stage, payload=payload, worker_cache=worker_cache,
            prompt=(
                "Extract every independently assertable atomic obligation from the one requirement. The supplied "
                "companions are frozen interpretation context for this requirement only: do not duplicate every "
                "companion clause into this row, and do not emit a duty that is not explicitly bound by the row. "
                "Treat each semicolon-separated "
                "duty, named boundary, quantitative limit, required readback/evidence field, denial condition, "
                "lifecycle transition, and forbidden outcome as a candidate independent obligation; retain it unless "
                "the frozen source makes it purely descriptive context. Do not summarize a compound case row into "
                "a small representative subset. Keep a parameterized boundary family as one obligation when every "
                "member has the same trigger, production boundary and oracle shape; retain every member explicitly "
                "in that obligation's observable and forbidden results so later Acceptance can assert each one. "
                "Return {\"obligations\":[...]}. "
                "Each obligation must contain source_refs (exactly the supplied source_ref), subject, trigger, state_before, state_after, expected_behavior, observable_result, forbidden_result[], requirement_type Product|Platform|Governance, obligation_kind behavior|quality|constraint|governance, unresolved_fragments[], status active|deferred|not_applicable, depends_on[]. Split independent behaviors; do not collapse multiple observable rules into one obligation."
            ),
        )
        items = raw.get("obligations")
        if not isinstance(items, list) or not items:
            raise ValueError(f"{entry['requirement_id']} produced no obligations")
        for item in items:
            if not isinstance(item, Mapping):
                raise ValueError("obligation worker item is not object")
            obligations.append(_normalize_obligation(entry, item))
    ids = [item["obligation_id"] for item in obligations]
    if len(ids) != len(set(ids)):
        raise ValueError("obligation semantic identities collide")
    return sorted(obligations, key=lambda item: (item["requirement_id"], item["obligation_id"]))


def guard_obligations(source_index: Mapping[str, Any], obligations: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    findings: list[str] = []
    source_refs = {entry["source_ref"] for entry in source_index["entries"]}
    requirement_ids = {entry["requirement_id"] for entry in source_index["entries"]}
    covered: set[str] = set()
    seen: set[str] = set()
    for item in obligations:
        oid = item.get("obligation_id")
        if oid in seen:
            findings.append(f"obligation:{oid}:duplicate")
        seen.add(str(oid))
        rid = item.get("requirement_id")
        if rid not in requirement_ids:
            findings.append(f"obligation:{oid}:unknown-requirement")
        else:
            covered.add(str(rid))
        refs = item.get("source_refs")
        if not isinstance(refs, list) or not refs or any(ref not in source_refs for ref in refs):
            findings.append(f"obligation:{oid}:source-ref")
        unresolved = item.get("unresolved_fragments")
        if item.get("status") == "active" and isinstance(unresolved, list) and unresolved:
            findings.append(f"obligation:{oid}:active-unresolved")
        if set(item) & RUNTIME_FIELDS:
            findings.append(f"obligation:{oid}:runtime-evidence")
    missing = requirement_ids - covered
    if missing:
        findings.append("requirements-without-obligation:" + ",".join(sorted(missing)))
    return {"valid": not findings, "findings": findings}


def _stable_acceptance_id(raw: Mapping[str, Any]) -> str:
    material = {key: raw.get(key) for key in ("obligation_ids", "given", "when", "then", "oracle", "assertion_ids")}
    return "A-" + sha256_value(material)[7:19].upper()


def _stable_failure_intent_id(raw: Mapping[str, Any]) -> str:
    material = {key: raw.get(key) for key in ("acceptance_ids", "failure_family", "selector_intent")}
    return "FI-" + sha256_value(material)[7:19].upper()


def compile_acceptances(*, root: Path, out_dir: Path, obligations: Sequence[Mapping[str, Any]], worker_cache: Mapping[str, Any] | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    payload = {"obligations": list(obligations)}
    raw = invoke_worker(
        root=root, out_dir=out_dir, stage="v3", payload=payload, worker_cache=worker_cache,
        prompt=(
            "Compile observable Acceptance contracts, RED failure intents, and slice_hints. Return {\"acceptances\":[],\"failure_intents\":[],\"slice_hints\":[]}. "
            "Acceptance: obligation_ids[], source_refs[], given, when, then, oracle{observable,expected,forbidden[]}, assertion_ids[]. Do not include acceptance_id or red_intent_ids; they are assigned deterministically. "
            "Failure intent: obligation_ids[] identifying the Acceptance it serves, failure_family from the allowed taxonomy, selector_intent, expected_outcome='fail', failure_id uppercase token. "
            "Treat expected-red as a runtime observation role, never as a generic label for RED-process guards. It is eligible only when every bound frozen obligation has obligation_kind behavior or quality and requirement_type is not Governance. Constraint/governance obligations and rules about RED construction, failure-marker emission, validation commands, write scope, fixtures, or harness integrity must retain a failure intent but use the appropriate non-expected-red family. "
            "Each slice_hint: obligation_ids[], production_owners[], verification_lane unit|integration|matrix|runtime, behavior_change, affected_subjects[], state_transition, rollback_scope{production_paths[],state_or_schema_compatibility}, allowed_write_paths[], execution_snapshot_paths[], planned_new_files[], terminal_predicate, forbidden_paths[], validation_commands as argv arrays. Paths must be repository-relative POSIX."
        ),
    )
    raw_acceptances = raw.get("acceptances")
    raw_failures = raw.get("failure_intents")
    hints = raw.get("slice_hints")
    if not isinstance(raw_acceptances, list) or not raw_acceptances or not isinstance(raw_failures, list) or not raw_failures or not isinstance(hints, list) or not hints:
        raise ValueError("V3 worker output is incomplete")
    obligation_by_id = {item["obligation_id"]: item for item in obligations}
    acceptances: list[dict[str, Any]] = []
    acceptance_by_obligation_set: dict[tuple[str, ...], str] = {}
    for item in raw_acceptances:
        if not isinstance(item, Mapping):
            raise ValueError("acceptance worker item is not object")
        obligation_ids = item.get("obligation_ids")
        if not isinstance(obligation_ids, list) or not obligation_ids or any(oid not in obligation_by_id for oid in obligation_ids):
            raise ValueError("acceptance obligation binding is invalid")
        for field in ("given", "when", "then"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise ValueError(f"acceptance {field} is missing")
        oracle = item.get("oracle")
        if not isinstance(oracle, Mapping) or not isinstance(oracle.get("observable"), str) or not isinstance(oracle.get("expected"), str) or not isinstance(oracle.get("forbidden"), list):
            raise ValueError("acceptance oracle is invalid")
        assertion_ids = item.get("assertion_ids")
        if not isinstance(assertion_ids, list) or not assertion_ids or any(not isinstance(x, str) or not x for x in assertion_ids):
            raise ValueError("acceptance assertion ids are invalid")
        source_refs = sorted({ref for oid in obligation_ids for ref in obligation_by_id[oid]["source_refs"]})
        normalized = {
            "obligation_ids": sorted(set(obligation_ids)), "source_refs": source_refs,
            "given": item["given"].strip(), "when": item["when"].strip(), "then": item["then"].strip(),
            "oracle": {"observable": oracle["observable"].strip(), "expected": oracle["expected"].strip(), "forbidden": list(oracle["forbidden"])},
            "assertion_ids": sorted(set(assertion_ids)),
        }
        aid = _stable_acceptance_id(normalized)
        normalized["acceptance_id"] = aid
        normalized["red_intent_ids"] = []
        key = tuple(normalized["obligation_ids"])
        if key in acceptance_by_obligation_set:
            raise ValueError("duplicate/overlapping acceptance semantic group")
        acceptance_by_obligation_set[key] = aid
        acceptances.append(normalized)
    failures: list[dict[str, Any]] = []
    for item in raw_failures:
        if not isinstance(item, Mapping):
            raise ValueError("failure intent item is not object")
        obligation_ids = item.get("obligation_ids")
        if not isinstance(obligation_ids, list) or not obligation_ids:
            raise ValueError("failure intent obligation binding missing")
        aid = acceptance_by_obligation_set.get(tuple(sorted(set(obligation_ids))))
        if not aid:
            raise ValueError("failure intent does not bind exactly one Acceptance")
        family = item.get("failure_family")
        if family not in FAILURE_FAMILIES:
            raise ValueError("failure intent family invalid")
        selector = item.get("selector_intent")
        failure_id = item.get("failure_id")
        if not isinstance(selector, str) or not selector.strip() or not isinstance(failure_id, str) or not failure_id.strip():
            raise ValueError("failure intent selector/failure id missing")
        normalized = {
            "acceptance_ids": [aid], "failure_id": failure_id.strip().upper(), "failure_family": family,
            "selector_intent": selector.strip(), "expected_outcome": "fail",
        }
        normalized["failure_intent_id"] = _stable_failure_intent_id(normalized)
        failures.append(normalized)
        next(acc for acc in acceptances if acc["acceptance_id"] == aid)["red_intent_ids"].append(normalized["failure_intent_id"])
    if any(not acc["red_intent_ids"] for acc in acceptances):
        raise ValueError("every Acceptance needs a RED intent")
    return sorted(acceptances, key=lambda x: x["acceptance_id"]), sorted(failures, key=lambda x: x["failure_intent_id"]), list(hints)


def semantic_preflight(obligations: Sequence[Mapping[str, Any]], acceptances: Sequence[Mapping[str, Any]], failures: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    findings: list[str] = []
    active = {item["obligation_id"] for item in obligations if item.get("status") == "active"}
    covered: set[str] = set()
    acceptance_ids = {item["acceptance_id"] for item in acceptances}
    for item in acceptances:
        obligation_ids = set(item.get("obligation_ids", []))
        covered |= obligation_ids
        if len({next(ob["subject"] for ob in obligations if ob["obligation_id"] == oid) for oid in obligation_ids}) > 1 and len(obligation_ids) > 1:
            findings.append(f"acceptance:{item['acceptance_id']}:overbroad-subject")
        if not item.get("assertion_ids") or not item.get("red_intent_ids"):
            findings.append(f"acceptance:{item['acceptance_id']}:unobservable")
    missing = active - covered
    if missing:
        findings.append("hard-uncovered:" + ",".join(sorted(missing)))
    failure_acceptances = {aid for item in failures for aid in item.get("acceptance_ids", [])}
    missing_red = acceptance_ids - failure_acceptances
    if missing_red:
        findings.append("acceptance-without-red:" + ",".join(sorted(missing_red)))
    return {"valid": not findings, "recommended_action": "continue" if not findings else "repair-vdd", "findings": findings}


def _compact_alignment_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Drop duplicated provenance fields when the worker transport nears its limit."""
    compact = dict(payload)
    source = payload.get("source_index")
    if isinstance(source, Mapping):
        compact["source_index"] = {
            "schema": source.get("schema"),
            "entries": [
                {key: entry.get(key) for key in ("requirement_id", "source_ref", "source_text", "source_order") if key in entry}
                for entry in source.get("entries", []) if isinstance(entry, Mapping)
            ],
            "companions": [
                {key: item.get(key) for key in ("repository_relative_source_path", "source_text") if key in item}
                for item in source.get("companions", []) if isinstance(item, Mapping)
            ],
        }
    compact["obligations"] = [
        {key: item.get(key) for key in (
            "obligation_id", "requirement_id", "source_refs", "subject", "trigger",
            "state_before", "state_after", "expected_behavior", "observable_result", "status",
        ) if key in item}
        for item in payload.get("obligations", []) if isinstance(item, Mapping)
    ]
    compact["non_active_obligation_context"] = [
        {key: item.get(key) for key in ("obligation_id", "requirement_id", "source_refs", "status", "unresolved_fragments") if key in item}
        for item in payload.get("non_active_obligation_context", []) if isinstance(item, Mapping)
    ]
    compact["acceptances"] = [
        {key: item.get(key) for key in (
            "acceptance_id", "obligation_ids", "source_refs", "given", "when", "then",
            "oracle", "assertion_ids", "red_intent_ids",
        ) if key in item}
        for item in payload.get("acceptances", []) if isinstance(item, Mapping)
    ]
    compact["failure_intents"] = [
        {key: item.get(key) for key in (
            "failure_intent_id", "acceptance_ids", "obligation_ids", "failure_family",
            "selector_intent", "expected_outcome",
        ) if key in item}
        for item in payload.get("failure_intents", []) if isinstance(item, Mapping)
    ]
    compact["transport_projection"] = "vdd-v4-alignment-compact-v1"
    return compact


def alignment_payload(source_index, obligations, acceptances, failures) -> dict[str, Any]:
    """ADR-0041: distinguish active proof targets from retained disposition context."""
    payload = {
        "alignment_scope": "active-obligation-acceptance-coverage.v1",
        "source_index": source_index,
        "obligations": [item for item in obligations if item.get("status") == "active"],
        "non_active_obligation_context": [item for item in obligations if item.get("status") != "active"],
        "acceptances": list(acceptances),
        "failure_intents": list(failures),
    }
    if len(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))) > 800_000:
        return _compact_alignment_payload(payload)
    return payload


ALIGNMENT_SCOPE_PROMPT = (
    " Coverage targets are exactly the active records in obligations. "
    "non_active_obligation_context retains deferred/excluded records and their unresolved fragments for context; "
    "do not demand Acceptance or RED intents for those records or include their IDs in covered/missing/invented arrays. "
    "Do not merge IDs, change status, or treat descriptive similarity as proof. Independently check every active "
    "obligation against its bound Acceptance and RED intent. Source recall remains a separate gate."
)


def semantic_align(*, root: Path, out_dir: Path, source_index: Mapping[str, Any], obligations: Sequence[Mapping[str, Any]], acceptances: Sequence[Mapping[str, Any]], failures: Sequence[Mapping[str, Any]], worker_cache: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = alignment_payload(source_index, obligations, acceptances, failures)
    raw = invoke_worker(
        root=root, out_dir=out_dir, stage="v4", payload=payload, worker_cache=worker_cache,
        prompt=(
            "Independently align the frozen source to obligations, Acceptance and RED intents. Failure intents bind Acceptance IDs; evaluate the supplied Acceptance-to-RED links when classifying coverage. Do not read another worker's reasoning. Return covered_obligation_ids[], missing_obligation_ids[], invented_obligation_ids[], misaligned_acceptance_ids[], oracle_alignment object, repairs[]. A boolean valid may be included but is not authoritative."
            + ALIGNMENT_SCOPE_PROMPT
        ),
    )
    for key in ("covered_obligation_ids", "missing_obligation_ids", "invented_obligation_ids", "misaligned_acceptance_ids", "repairs"):
        if not isinstance(raw.get(key), list):
            raise ValueError(f"V4 {key} missing")
    known = {item["obligation_id"] for item in obligations if item.get("status") == "active"}
    # A full V4 response can exceed a worker's practical output budget.  Keep
    # V4 independent, but ask it to classify only the still-unreported frozen
    # IDs in bounded follow-up calls rather than treating truncation as proof
    # that those obligations are absent.
    reported = {item for item in raw["covered_obligation_ids"] if isinstance(item, str)}
    reported.update(item for item in raw["missing_obligation_ids"] if isinstance(item, str))
    for round_index in range(10):
        remaining = sorted(known - reported)
        if not remaining:
            break
        # Keep each repair response well below the worker's output budget.
        remaining_set = set(remaining[:40])
        narrowed_obligations = [item for item in obligations if item.get("obligation_id") in remaining_set]
        narrowed_acceptances = [item for item in acceptances if remaining_set.intersection(item.get("obligation_ids", []))]
        # V3 failure intents bind their Acceptance IDs, not obligation IDs.
        # Preserve the RED contract for each bounded V4 recheck by following
        # that normative binding; otherwise every recheck sees an empty RED
        # set and can only classify its obligations as missing.
        narrowed_acceptance_ids = {
            item.get("acceptance_id")
            for item in narrowed_acceptances
            if isinstance(item.get("acceptance_id"), str) and item.get("acceptance_id")
        }
        narrowed_failures = [
            item for item in failures
            if narrowed_acceptance_ids.intersection(item.get("acceptance_ids", []))
        ]
        supplement = invoke_worker(
            root=root, out_dir=out_dir, stage=f"v4-coverage-repair-{round_index}",
            payload=alignment_payload(source_index, narrowed_obligations, narrowed_acceptances, narrowed_failures),
            worker_cache=worker_cache,
            prompt=(
                "Independently classify EVERY active obligation in this bounded frozen input. Failure intents bind the supplied Acceptance IDs and are part of each obligation's RED contract. "
                "Return covered_obligation_ids[], missing_obligation_ids[], invented_obligation_ids[], "
                "misaligned_acceptance_ids[], oracle_alignment object, repairs[]. Do not omit an input ID."
                + ALIGNMENT_SCOPE_PROMPT
            ),
        )
        for key in ("covered_obligation_ids", "missing_obligation_ids", "invented_obligation_ids", "misaligned_acceptance_ids", "repairs"):
            if not isinstance(supplement.get(key), list):
                raise ValueError(f"V4 coverage repair {key} missing")
            raw[key].extend(supplement[key])
        reported.update(item for item in supplement["covered_obligation_ids"] if isinstance(item, str))
        reported.update(item for item in supplement["missing_obligation_ids"] if isinstance(item, str))
    covered = set(raw["covered_obligation_ids"])
    missing = set(raw["missing_obligation_ids"])
    invented = set(raw["invented_obligation_ids"])
    misaligned = set(raw["misaligned_acceptance_ids"])
    findings: list[str] = []
    if known - covered:
        findings.append("v4:active-not-covered:" + ",".join(sorted(known - covered)))
    if missing:
        findings.append("v4:missing:" + ",".join(sorted(missing)))
    if invented:
        findings.append("v4:invented:" + ",".join(sorted(invented)))
    if misaligned:
        findings.append("v4:misaligned-acceptance:" + ",".join(sorted(misaligned)))
    return {"valid": not findings, "findings": findings, "worker": dict(raw)}


def exact_cover(obligations: Sequence[Mapping[str, Any]], acceptances: Sequence[Mapping[str, Any]], failures: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    obligation_by_id = {item["obligation_id"]: item for item in obligations}
    failure_by_id = {item["failure_intent_id"]: item for item in failures}
    edges: list[dict[str, Any]] = []
    for acceptance in acceptances:
        for oid in acceptance["obligation_ids"]:
            obligation = obligation_by_id[oid]
            if obligation.get("status") != "active":
                continue
            for source_ref in sorted(set(obligation["source_refs"]) & set(acceptance["source_refs"])):
                for fid in acceptance["red_intent_ids"]:
                    failure = failure_by_id[fid]
                    if acceptance["acceptance_id"] not in failure["acceptance_ids"]:
                        raise ValueError("V5 failure/Acceptance edge mismatch")
                    edges.append({
                        "requirement_id": obligation["requirement_id"], "obligation_id": oid,
                        "acceptance_id": acceptance["acceptance_id"], "source_ref": source_ref,
                        "failure_intent_id": fid,
                    })
    active = {item["obligation_id"] for item in obligations if item.get("status") == "active"}
    if {edge["obligation_id"] for edge in edges} != active:
        raise ValueError("V5 hard-uncovered obligation")
    if {edge["acceptance_id"] for edge in edges} != {item["acceptance_id"] for item in acceptances}:
        raise ValueError("V5 orphan Acceptance")
    return sorted(edges, key=lambda e: tuple(e[k] for k in ("requirement_id", "obligation_id", "acceptance_id", "source_ref", "failure_intent_id")))


def _hint_for_acceptance(hints: Sequence[Mapping[str, Any]], acceptance: Mapping[str, Any]) -> Mapping[str, Any]:
    target = set(acceptance["obligation_ids"])
    matches = [hint for hint in hints if isinstance(hint, Mapping) and set(hint.get("obligation_ids", [])) == target]
    if len(matches) != 1:
        raise ValueError(f"Acceptance {acceptance['acceptance_id']} requires exactly one slice hint")
    return matches[0]


def _validate_paths(values: Any, label: str, *, nonempty: bool = False) -> list[str]:
    if not isinstance(values, list) or (nonempty and not values) or any(not isinstance(x, str) or not x for x in values):
        raise ValueError(f"{label} must be string list")
    return [safe_relative(x) for x in values]


def partition_slices(obligations: Sequence[Mapping[str, Any]], acceptances: Sequence[Mapping[str, Any]], failures: Sequence[Mapping[str, Any]], hints: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Mapping[str, Any]]]:
    failure_by_acceptance = {aid: [] for aid in [a["acceptance_id"] for a in acceptances]}
    for failure in failures:
        for aid in failure["acceptance_ids"]:
            failure_by_acceptance.setdefault(aid, []).append(failure)
    buckets: dict[str, list[tuple[Mapping[str, Any], Mapping[str, Any]]]] = {}
    hint_by_acceptance: dict[str, Mapping[str, Any]] = {}
    for acceptance in acceptances:
        hint = _hint_for_acceptance(hints, acceptance)
        hint_by_acceptance[acceptance["acceptance_id"]] = hint
        owners = _validate_paths(hint.get("production_owners"), "production_owners", nonempty=True)
        allowed = _validate_paths(hint.get("allowed_write_paths"), "allowed_write_paths")
        snapshots = _validate_paths(hint.get("execution_snapshot_paths"), "execution_snapshot_paths", nonempty=True)
        planned = _validate_paths(hint.get("planned_new_files", []), "planned_new_files")
        lane = hint.get("verification_lane")
        if lane not in LANES:
            raise ValueError("slice hint verification_lane invalid")
        transition = hint.get("state_transition")
        if not isinstance(transition, str) or not transition:
            raise ValueError("slice hint state_transition missing")
        families = sorted({f["failure_family"] for f in failure_by_acceptance[acceptance["acceptance_id"]]})
        key = sha256_value({"owners": sorted(owners), "lane": lane, "transition": transition, "families": families, "snapshots": sorted(snapshots), "allowed": sorted(allowed), "planned": sorted(planned)})
        buckets.setdefault(key, []).append((acceptance, hint))
    slices: list[dict[str, Any]] = []
    for number, key in enumerate(sorted(buckets), start=1):
        pairs = buckets[key]
        acceptance_ids = sorted(a["acceptance_id"] for a, _ in pairs)
        obligation_ids = sorted({oid for a, _ in pairs for oid in a["obligation_ids"]})
        related_failures = [f for f in failures if set(f["acceptance_ids"]) & set(acceptance_ids)]
        first_hint = pairs[0][1]
        production_owners = sorted({p for _, h in pairs for p in _validate_paths(h.get("production_owners"), "production_owners", nonempty=True)})
        allowed_write_paths = sorted({p for _, h in pairs for p in _validate_paths(h.get("allowed_write_paths"), "allowed_write_paths")})
        execution_snapshot_paths = sorted({p for _, h in pairs for p in _validate_paths(h.get("execution_snapshot_paths"), "execution_snapshot_paths", nonempty=True)})
        planned_new_files = sorted({p for _, h in pairs for p in _validate_paths(h.get("planned_new_files", []), "planned_new_files")})
        affected = sorted({x for _, h in pairs for x in h.get("affected_subjects", []) if isinstance(x, str) and x})
        selectors = sorted({f["selector_intent"] for f in related_failures})
        assertions = sorted({x for a, _ in pairs for x in a["assertion_ids"]})
        rollback_paths = sorted({p for _, h in pairs for p in _validate_paths((h.get("rollback_scope") or {}).get("production_paths", []), "rollback.production_paths")})
        behavior_change = " | ".join(sorted({str(h.get("behavior_change") or "").strip() for _, h in pairs if str(h.get("behavior_change") or "").strip()}))
        terminal_values = {str(h.get("terminal_predicate") or "").strip() for _, h in pairs}
        if len(terminal_values) != 1 or not next(iter(terminal_values)):
            raise ValueError("bucket terminal predicates are incompatible")
        rollback_compat = {str((h.get("rollback_scope") or {}).get("state_or_schema_compatibility") or "").strip() for _, h in pairs}
        if len(rollback_compat) != 1 or not next(iter(rollback_compat)):
            raise ValueError("bucket rollback compatibility is incompatible")
        lane = first_hint["verification_lane"]
        transition = first_hint["state_transition"]
        slice_id = f"S{number}"
        slice_input_hash = sha256_value({"bucket": key, "acceptance_ids": acceptance_ids, "obligation_ids": obligation_ids})
        slices.append({
            "slice_id": slice_id, "slice_input_hash": slice_input_hash,
            "obligation_ids": obligation_ids, "acceptance_ids": acceptance_ids,
            "failure_intent_ids": sorted(f["failure_intent_id"] for f in related_failures),
            "production_owners": production_owners, "verification_lane": lane,
            "behavior_change": behavior_change or "Implement the bound Acceptance behaviors",
            "affected_subjects": affected or production_owners, "state_transition": transition,
            "proof": {"acceptance_ids": acceptance_ids, "selector_intents": selectors, "assertion_ids": assertions},
            "rollback_scope": {"production_paths": rollback_paths or production_owners, "state_or_schema_compatibility": next(iter(rollback_compat))},
            "allowed_write_paths": allowed_write_paths, "execution_snapshot_paths": execution_snapshot_paths,
            "planned_new_files": planned_new_files, "terminal_predicate": next(iter(terminal_values)),
        })
    return slices, hint_by_acceptance


def final_cover(pre_edges: Sequence[Mapping[str, Any]], slices: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    slice_for_acceptance: dict[str, Mapping[str, Any]] = {}
    for slice_item in slices:
        for aid in slice_item["acceptance_ids"]:
            if aid in slice_for_acceptance:
                raise ValueError("Acceptance appears in multiple slices")
            slice_for_acceptance[aid] = slice_item
    for edge in pre_edges:
        selected = slice_for_acceptance.get(edge["acceptance_id"])
        if selected is None:
            raise ValueError("V6A cannot bind V5 edge to slice")
        result.append({
            **dict(edge), "slice_id": selected["slice_id"], "verification_lane": selected["verification_lane"],
            "terminal_predicate": selected["terminal_predicate"], "stage_scope": list(STAGE_SCOPE),
        })
    if len(result) != len(pre_edges):
        raise ValueError("V6A does not preserve V5 cardinality")
    return result


def _validation_commands(hint: Mapping[str, Any]) -> list[list[str]]:
    commands = hint.get("validation_commands")
    if not isinstance(commands, list) or not commands:
        raise ValueError("slice hint validation_commands missing")
    normalized: list[list[str]] = []
    for command in commands:
        if not isinstance(command, list) or not command or any(not isinstance(part, str) or not part for part in command):
            raise ValueError("validation command must be argv array")
        normalized.append(list(command))
    return normalized


def feasibility(root: Path, slices: Sequence[Mapping[str, Any]], acceptances: Sequence[Mapping[str, Any]], failures: Sequence[Mapping[str, Any]], hints_by_acceptance: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    findings: list[str] = []
    acceptance_by_id = {a["acceptance_id"]: a for a in acceptances}
    failure_by_id = {f["failure_intent_id"]: f for f in failures}
    for slice_item in slices:
        sid = slice_item["slice_id"]
        allowed = set(slice_item["allowed_write_paths"])
        planned = set(slice_item["planned_new_files"])
        existing_owner = False
        for owner in slice_item["production_owners"]:
            if owner not in allowed and owner not in planned:
                findings.append(f"{sid}:owner-outside-write-set:{owner}")
            path = (root / owner).resolve()
            try:
                path.relative_to(root.resolve())
            except ValueError:
                findings.append(f"{sid}:owner-escape:{owner}")
                continue
            if path.is_file() and not path.is_symlink():
                existing_owner = True
            elif owner not in planned:
                findings.append(f"{sid}:owner-missing:{owner}")
        if not existing_owner:
            findings.append(f"{sid}:no-real-production-entry")
        for snapshot in slice_item["execution_snapshot_paths"]:
            path = (root / snapshot).resolve()
            if not path.is_file() or path.is_symlink():
                findings.append(f"{sid}:selector-target-missing:{snapshot}")
        for fid in slice_item["failure_intent_ids"]:
            selector = failure_by_id[fid]["selector_intent"].lower()
            if any(token in selector for token in ("assert false", "always fail", "exit 1", "raise assertionerror")):
                findings.append(f"{sid}:fixed-failure-selector:{fid}")
        for aid in slice_item["acceptance_ids"]:
            hint = hints_by_acceptance[aid]
            try:
                _validation_commands(hint)
            except ValueError as exc:
                findings.append(f"{sid}:{exc}")
            acceptance = acceptance_by_id[aid]
            if not acceptance.get("assertion_ids"):
                findings.append(f"{sid}:acceptance-unobservable:{aid}")
    return {"valid": not findings, "recommended_action": "plan-ready" if not findings else "repair-vdd", "findings": findings}


def agent_contexts(slices: Sequence[Mapping[str, Any]], obligations: Sequence[Mapping[str, Any]], acceptances: Sequence[Mapping[str, Any]], hints_by_acceptance: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    obligation_by_id = {o["obligation_id"]: o for o in obligations}
    acceptance_by_id = {a["acceptance_id"]: a for a in acceptances}
    result: list[dict[str, Any]] = []
    for slice_item in slices:
        source_refs = sorted({ref for oid in slice_item["obligation_ids"] for ref in obligation_by_id[oid]["source_refs"]})
        requirement_ids = sorted({obligation_by_id[oid]["requirement_id"] for oid in slice_item["obligation_ids"]})
        forbidden = sorted({p for aid in slice_item["acceptance_ids"] for p in _validate_paths(hints_by_acceptance[aid].get("forbidden_paths", []), "forbidden_paths")})
        commands: list[list[str]] = []
        for aid in slice_item["acceptance_ids"]:
            for command in _validation_commands(hints_by_acceptance[aid]):
                if command not in commands:
                    commands.append(command)
        result.append({
            "slice_id": slice_item["slice_id"], "requirement_ids": requirement_ids,
            "obligation_ids": list(slice_item["obligation_ids"]), "acceptance_ids": list(slice_item["acceptance_ids"]),
            "source_refs": source_refs, "contracts": ["vdd.semantic-plan-bundle.v1", slice_item["terminal_predicate"]],
            "allowed_paths": list(slice_item["allowed_write_paths"]), "forbidden_paths": forbidden,
            "selector_intents": list(slice_item["proof"]["selector_intents"]), "validation_commands": commands,
        })
    return result


def compile_plan(*, requirements: Path, out_dir: Path, companions: Sequence[Path] = (), profile: str = "standard", worker_cache: Mapping[str, Any] | None = None, recommendation_only: bool = False) -> dict[str, Any]:
    if profile not in {"standard", "resumable", "self-hosted"}:
        raise ValueError("VDD plan-shape profile is invalid")
    root = repository_root(requirements.parent)
    source_index = build_source_index(root, requirements, companions)
    preflight = source_preflight(root, source_index)
    if not preflight["valid"]:
        return {"status": "repair-vdd", "stage": "V0A", "source_index": source_index, "preflight": preflight}
    if recommendation_only:
        return {"status": "recommendation-only", "recommended_action": "compile-v1", "profile": profile, "source_index_sha256": source_index["sha256"], "model_called": False, "writes_performed": False}
    obligations = stage_call(out_dir, "V1", compile_obligations, root=root, out_dir=out_dir, source_index=source_index, worker_cache=worker_cache)
    guard = stage_call(out_dir, "V2", guard_obligations, source_index, obligations)
    if not guard["valid"]:
        return {"status": "repair-vdd", "stage": "V2", "findings": guard["findings"]}
    acceptances, failures, hints = stage_call(out_dir, "V3", compile_acceptances, root=root, out_dir=out_dir, obligations=obligations, worker_cache=worker_cache)
    plan_preflight = stage_call(out_dir, "V3A", semantic_preflight, obligations, acceptances, failures)
    if not plan_preflight["valid"]:
        return {"status": "repair-vdd", "stage": "V3A", "findings": plan_preflight["findings"]}
    alignment = stage_call(out_dir, "V4", semantic_align, root=root, out_dir=out_dir, source_index=source_index, obligations=obligations, acceptances=acceptances, failures=failures, worker_cache=worker_cache)
    if not alignment["valid"]:
        return {"status": "repair-vdd", "stage": "V4", "findings": alignment["findings"]}
    pre_edges = stage_call(out_dir, "V5", exact_cover, obligations, acceptances, failures)
    slices, hints_by_acceptance = stage_call(out_dir, "V6", partition_slices, obligations, acceptances, failures, hints)
    final_edges = stage_call(out_dir, "V6A", final_cover, pre_edges, slices)
    contexts = stage_call(out_dir, "agent-context", agent_contexts, slices, obligations, acceptances, hints_by_acceptance)
    feasibility_result = stage_call(out_dir, "V7", feasibility, root, slices, acceptances, failures, hints_by_acceptance)
    if not feasibility_result["valid"]:
        return {"status": "repair-vdd", "stage": "V7", "findings": feasibility_result["findings"]}
    plan_id = "PLAN-" + sha256_value({"source": source_index["sha256"], "profile": profile})[7:19].upper()
    bundle = {
        "schema_version": "vdd.semantic-plan-bundle.v1", "plan_id": plan_id, "profile": profile,
        "obligations": obligations, "acceptances": acceptances, "failure_intents": failures,
        "pre_slice_coverage": pre_edges, "slices": slices, "final_plan_coverage": final_edges,
        "agent_contexts": contexts,
    }
    # ADR-0041: project probe intent without claiming current behavior or running tests.
    from semantic_behavior_contract import SCHEMA, project_intents
    deferred_rows = [
        {
            "type": "implementation-resolvable",
            "reason": "deferred obligation requires implementation-time verification record",
            "resolution_owner": "Quick Dev",
            "resolution_stage": "implementation",
            "affected_obligation_ids": [item["obligation_id"]],
        }
        for item in bundle["obligations"]
        if item.get("status") == "deferred"
    ]
    bundle["behavior_routing"] = {"schema": SCHEMA, "intents": project_intents(bundle), "deferred": deferred_rows}
    valid, findings = stage_call(out_dir, "final-validation", validate_semantic_bundle, bundle)
    if not valid:
        return {"status": "repair-vdd", "stage": "final-validation", "findings": findings}
    atomic_json(out_dir / "source-index.v1.json", source_index)
    atomic_json(out_dir / "obligations.v1.json", obligations)
    atomic_json(out_dir / "acceptances.v1.json", acceptances)
    atomic_json(out_dir / "failure-intents.v1.json", failures)
    atomic_json(out_dir / "pre-slice-coverage.v1.json", pre_edges)
    atomic_json(out_dir / "slices.v1.json", slices)
    atomic_json(out_dir / "final-plan-coverage.v1.json", final_edges)
    atomic_json(out_dir / "semantic-alignment.v1.json", alignment)
    atomic_json(out_dir / "feasibility.v1.json", feasibility_result)
    for context in contexts:
        atomic_json(out_dir / "agent-context" / context["slice_id"] / "agent-context.json", context)
    atomic_json(out_dir / "semantic-plan-bundle.v1.json", bundle)
    state = {"schema": "vdd.compiler-state.v1", "plan_id": plan_id, "state": "plan-ready", "completed_stages": ["V0", "V0A", "V1", "V2", "V3", "V3A", "V4", "V5", "V6", "V6A", "V7"], "semantic_plan_sha256": sha256_value(bundle)}
    atomic_json(out_dir / "compiler-state.v1.json", state)
    return {"status": "plan-ready", "plan_id": plan_id, "semantic_plan_sha256": sha256_value(bundle), "slices": [s["slice_id"] for s in slices]}
