"""Make the grouped V3 repair prompt state deterministic repair invariants."""
from __future__ import annotations

import json
from typing import Any, Mapping

import semantic_worker_v3_group_repair_patch as grouped

_BASE_LIVE_GROUP_REPAIR = grouped._live_group_repair


def _subject_domains(payload: Mapping[str, Any]) -> dict[str, list[str]]:
    domains: dict[str, list[str]] = {}
    for item in grouped._repair_obligations(payload):
        oid = item.get("obligation_id")
        subject = item.get("subject")
        if not isinstance(oid, str) or not oid or not isinstance(subject, str) or not subject.strip():
            continue
        domains.setdefault(subject.strip(), []).append(oid)
    return {
        subject: sorted(set(ids))
        for subject, ids in sorted(domains.items())
        if ids
    }


def _live_group_repair(*, root, out_dir, payload, prompt):
    domains = _subject_domains(payload)
    augmented = prompt + (
        "\n\nGROUPED REPAIR INVARIANTS: every active frozen obligation must appear in at least one Acceptance group; "
        "do not combine obligations with different subjects into one Acceptance. The exact frozen subject domains are: "
        + json.dumps(domains, ensure_ascii=False, sort_keys=True)
        + ". Each group's obligation_ids MUST be a non-empty subset of exactly one listed subject domain. "
        "Every existing production_owner that can be modified must also appear in allowed_write_paths. An "
        "execution_snapshot_path that does not yet exist is legal only when the frozen obligations require it to be "
        "authored and the exact same path is listed in planned_new_files. Do not use directories, generic logs paths, "
        "or evidence folders as selector snapshots. Honor explicit semantics that require compatible behaviors to share "
        "one bounded/cohesive slice or the same selector family; do not create artificial hint differences that fragment "
        "otherwise compatible work. Never weaken lifecycle, owner, write-set, oracle, or failure semantics merely to "
        "make grouping easier."
    )
    return _BASE_LIVE_GROUP_REPAIR(root=root, out_dir=out_dir, payload=payload, prompt=augmented)


def install() -> None:
    grouped._live_group_repair = _live_group_repair


install()
