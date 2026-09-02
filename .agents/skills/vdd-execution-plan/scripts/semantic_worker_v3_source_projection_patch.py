"""Project the V0-frozen source index into V3 without rereading the worktree.

V1 obligations intentionally carry atomic semantics rather than every concrete
path contract. V3, however, must choose production owners, RED selectors,
fixtures, planned files, and validation commands. Those values are often stated
explicitly only in the canonical requirement text.

This patch captures the exact source-index.v1 value produced by V0, marks it
usable only after V0A succeeds, and adds only the source entries referenced by
the frozen obligations to the V3 worker payload. The one-shot
v3-schema-repair inherits the same enriched payload through its existing nested
`input` field. No source file is reread and no model output can mutate the
frozen source projection. The context is consumed by V3 and then cleared so it
cannot leak into another compile or direct worker invocation.
"""
from __future__ import annotations

from contextvars import ContextVar
from pathlib import Path
from typing import Any, Mapping

import semantic_compiler as sc
import semantic_compiler_gate as gate

_BASE_BUILD_SOURCE_INDEX = sc.build_source_index
_BASE_SOURCE_PREFLIGHT = sc.source_preflight
_BASE_NORMATIVE_INVOKE = gate.normative_invoke_worker
_FROZEN_SOURCE_CONTEXT: ContextVar[Mapping[str, Any] | None] = ContextVar(
    "ch456_frozen_source_context", default=None
)


def build_source_index_with_projection(root, *args, **kwargs) -> dict[str, Any]:
    source_index = _BASE_BUILD_SOURCE_INDEX(root, *args, **kwargs)
    _FROZEN_SOURCE_CONTEXT.set(
        {
            "root": str(Path(root).resolve()),
            "source_index": source_index,
            "validated": False,
        }
    )
    return source_index


def source_preflight_with_projection(root, source_index: Mapping[str, Any]) -> dict[str, Any]:
    result = _BASE_SOURCE_PREFLIGHT(root, source_index)
    current = _FROZEN_SOURCE_CONTEXT.get()
    same_context = (
        isinstance(current, Mapping)
        and current.get("root") == str(Path(root).resolve())
        and isinstance(current.get("source_index"), Mapping)
        and current["source_index"].get("sha256") == source_index.get("sha256")
    )
    if result.get("valid") and same_context:
        _FROZEN_SOURCE_CONTEXT.set({**dict(current), "validated": True})
    elif same_context:
        _FROZEN_SOURCE_CONTEXT.set(None)
    return result


def _source_contracts(root, payload: Mapping[str, Any]) -> tuple[str, list[dict[str, Any]]] | None:
    context = _FROZEN_SOURCE_CONTEXT.get()
    if not isinstance(context, Mapping) or context.get("validated") is not True:
        return None
    if context.get("root") != str(Path(root).resolve()):
        return None
    source_index = context.get("source_index")
    if not isinstance(source_index, Mapping):
        return None
    entries = source_index.get("entries")
    source_sha = source_index.get("sha256")
    obligations = payload.get("obligations")
    if not isinstance(entries, list) or not isinstance(source_sha, str) or not isinstance(obligations, list):
        return None

    refs: set[str] = set()
    for obligation in obligations:
        if not isinstance(obligation, Mapping):
            continue
        raw_refs = obligation.get("source_refs")
        if isinstance(raw_refs, list):
            refs.update(str(ref) for ref in raw_refs if isinstance(ref, str) and ref)
    if not refs:
        return None

    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in entries:
        if not isinstance(raw, Mapping):
            continue
        source_ref = raw.get("source_ref")
        if not isinstance(source_ref, str) or source_ref not in refs:
            continue
        source_text = raw.get("source_text")
        text_sha = raw.get("text_sha256")
        file_sha = raw.get("source_sha256")
        relative_path = raw.get("repository_relative_source_path")
        if not all(isinstance(value, str) and value for value in (source_text, text_sha, file_sha, relative_path)):
            raise ValueError(f"V3 frozen source contract is incomplete: {source_ref}")
        selected.append(
            {
                "requirement_id": raw.get("requirement_id"),
                "source_ref": source_ref,
                "repository_relative_source_path": relative_path,
                "source_text": source_text,
                "source_sha256": file_sha,
                "text_sha256": text_sha,
                "source_order": raw.get("source_order"),
            }
        )
        seen.add(source_ref)
    missing = sorted(refs - seen)
    if missing:
        raise ValueError("V3 frozen source projection is incomplete: " + ",".join(missing))
    selected.sort(key=lambda item: (int(item.get("source_order") or 0), str(item["source_ref"])))
    return source_sha, selected


def normative_invoke_worker_with_source_projection(
    *,
    root,
    out_dir,
    stage: str,
    payload: Mapping[str, Any],
    prompt: str,
    worker_cache: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    if stage != "v3":
        return _BASE_NORMATIVE_INVOKE(
            root=root,
            out_dir=out_dir,
            stage=stage,
            payload=payload,
            prompt=prompt,
            worker_cache=worker_cache,
        )

    projection = _source_contracts(root, payload)
    if projection is None:
        # Direct unit tests may invoke V3 without running V0/V0A first. Preserve
        # that compatibility path; real compile_plan execution reaches V3 only
        # after the validated frozen context has been created.
        return _BASE_NORMATIVE_INVOKE(
            root=root,
            out_dir=out_dir,
            stage=stage,
            payload=payload,
            prompt=prompt,
            worker_cache=worker_cache,
        )

    source_sha, contracts = projection
    enriched = dict(payload)
    enriched["frozen_source_index_sha256"] = source_sha
    enriched["source_contracts"] = contracts
    augmented_prompt = prompt + (
        "\n\nFROZEN SOURCE CONTRACTS: source_contracts are the exact V0/V0A-validated canonical "
        "requirement sections referenced by these obligations. Treat explicit repository-relative paths, production "
        "owners, test/fixture paths, write boundaries, lifecycle qualifiers, and validation commands in those frozen "
        "sections as authority. Do not guess a production owner from a fixture path. A missing selector/fixture that the "
        "frozen source explicitly requires to be authored must be listed verbatim in planned_new_files. A production "
        "owner must name a real implementation file when the source identifies one, must be writable, and must not be "
        "repeated in forbidden_paths. Do not invent paths not supported by the frozen source or repository reality."
    )
    try:
        return _BASE_NORMATIVE_INVOKE(
            root=root,
            out_dir=out_dir,
            stage=stage,
            payload=enriched,
            prompt=augmented_prompt,
            worker_cache=worker_cache,
        )
    finally:
        _FROZEN_SOURCE_CONTEXT.set(None)


def install() -> None:
    sc.build_source_index = build_source_index_with_projection
    sc.source_preflight = source_preflight_with_projection
    gate.normative_invoke_worker = normative_invoke_worker_with_source_projection
    sc.invoke_worker = normative_invoke_worker_with_source_projection


install()
