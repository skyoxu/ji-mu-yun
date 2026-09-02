"""Project the V0-frozen source index into V3 without rereading the worktree.

V1 obligations intentionally carry atomic semantics rather than every concrete
path contract. V3, however, must choose production owners, RED selectors,
fixtures, planned files, and validation commands. Those values are often stated
explicitly only in the canonical requirement text.

This patch captures the exact source-index.v1 value produced by V0 and already
validated by V0A, then adds only the source entries referenced by the frozen
obligations to the V3 worker payload. The one-shot v3-schema-repair inherits the
same enriched payload through its existing nested `input` field. No source file
is reread and no model output can mutate the frozen source projection.
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Mapping

import semantic_compiler as sc
import semantic_compiler_gate as gate

_BASE_BUILD_SOURCE_INDEX = sc.build_source_index
_BASE_NORMATIVE_INVOKE = gate.normative_invoke_worker
_FROZEN_SOURCE_INDEX: ContextVar[Mapping[str, Any] | None] = ContextVar(
    "ch456_frozen_source_index", default=None
)


def build_source_index_with_projection(*args, **kwargs) -> dict[str, Any]:
    source_index = _BASE_BUILD_SOURCE_INDEX(*args, **kwargs)
    _FROZEN_SOURCE_INDEX.set(source_index)
    return source_index


def _source_contracts(payload: Mapping[str, Any]) -> tuple[str, list[dict[str, Any]]] | None:
    source_index = _FROZEN_SOURCE_INDEX.get()
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

    projection = _source_contracts(payload)
    if projection is None:
        # Direct unit tests may invoke V3 without running V0 first. Preserve that
        # compatibility path; real compile_plan execution always builds V0 first.
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
    return _BASE_NORMATIVE_INVOKE(
        root=root,
        out_dir=out_dir,
        stage=stage,
        payload=enriched,
        prompt=augmented_prompt,
        worker_cache=worker_cache,
    )


def install() -> None:
    sc.build_source_index = build_source_index_with_projection
    gate.normative_invoke_worker = normative_invoke_worker_with_source_projection
    sc.invoke_worker = normative_invoke_worker_with_source_projection


install()
