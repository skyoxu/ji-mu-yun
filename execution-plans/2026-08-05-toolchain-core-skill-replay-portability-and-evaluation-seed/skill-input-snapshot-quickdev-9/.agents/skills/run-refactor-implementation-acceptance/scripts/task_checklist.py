"""Parse only declared authority checklists and close them against current evidence."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from acceptance_core import InputError


_CHECKBOX = re.compile(r"^(?P<indent>\s*)[-*+]\s+\[(?P<checked>[ xX])\]\s+(?P<text>.+?)\s*$")
_HEADING = re.compile(r"^#{1,6}\s+(?P<text>.+?)\s*$")


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _anchor(text: str) -> str:
    normalized = re.sub(r"\s+", "-", text.strip().casefold())
    return re.sub(r"[^a-z0-9._-]", "", normalized) or "root"


def _item_id(source: str, anchor: str, text: str) -> str:
    # Checked state and whitespace do not participate, preserving identity after completion edits.
    identity = source + "\0" + anchor + "\0" + re.sub(r"\s+", " ", text.strip())
    return "TASK-CHECK-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16].upper()


def audit_task_checklist(
    *, repository_root: Path, acceptance_run_id: str, candidate_manifest_hash: str,
    sources: Any, evidence_by_item: Any, optional_items: Any = None,
) -> dict[str, Any]:
    if not isinstance(acceptance_run_id, str) or not acceptance_run_id or not isinstance(candidate_manifest_hash, str):
        raise InputError("task checklist run binding is invalid")
    if not isinstance(sources, list) or not sources:
        raise InputError("task checklist sources are required")
    if not isinstance(evidence_by_item, dict):
        raise InputError("task checklist evidence mapping is invalid")
    # Authority checklists currently have no contract-level optionality syntax.
    # A request must therefore not downgrade parsed source requirements.
    if optional_items not in (None, {}):
        raise InputError("request-controlled optional task checklist items are forbidden")
    root = repository_root.resolve()
    source_records: list[dict[str, str]] = []
    items: list[dict[str, Any]] = []
    for source in sources:
        if not isinstance(source, dict) or set(source) != {"path", "sha256"} or not isinstance(source["path"], str) or not isinstance(source["sha256"], str):
            raise InputError("task checklist source is invalid")
        path = (root / source["path"]).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise InputError("task checklist source escapes repository") from exc
        if not path.is_file() or _sha256(path) != source["sha256"]:
            raise InputError("task checklist source is stale or missing")
        source_records.append({"path": source["path"], "sha256": source["sha256"]})
        anchor = "root"
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            heading = _HEADING.match(line)
            if heading:
                anchor = _anchor(heading.group("text"))
                continue
            checkbox = _CHECKBOX.match(line)
            if not checkbox:
                continue
            text = checkbox.group("text")
            item_id = _item_id(source["path"], anchor, text)
            proof = evidence_by_item.get(item_id, {})
            if not isinstance(proof, dict):
                raise InputError("task checklist item evidence is invalid")
            requiredness = "required"
            checked = checkbox.group("checked").casefold() == "x"
            required_refs = ("matrixCheckIds", "implementationRefs", "testRefs", "evidenceIds")
            proof_complete = all(isinstance(proof.get(key), list) and proof[key] for key in required_refs)
            if checked and proof_complete:
                status = "verified"
            elif checked:
                status = "checked_without_evidence"
            else:
                status = "unchecked"
            items.append({
                "taskChecklistItemId": item_id, "sourceRef": f"{source['path']}:{line_number}",
                "sectionAnchor": anchor, "textSignature": hashlib.sha256(text.strip().encode("utf-8")).hexdigest(),
                "requiredness": requiredness, "checked": checked, "matrixCheckIds": proof.get("matrixCheckIds", []),
                "implementationRefs": proof.get("implementationRefs", []), "testRefs": proof.get("testRefs", []),
                "evidenceIds": proof.get("evidenceIds", []), "status": status,
            })
    if not items:
        raise InputError("declared task checklist sources contain no checklist items")
    required = [item for item in items if item["requiredness"] == "required"]
    status = "passed" if all(item["status"] == "verified" for item in required) else "failed"
    return {
        "schemaVersion": "task-checklist-closure.v1", "acceptanceRunId": acceptance_run_id,
        "candidateContentManifestHash": candidate_manifest_hash, "sources": source_records, "items": items,
        "requiredItemCount": len(required), "checkedRequiredItemCount": sum(item["checked"] for item in required),
        "verifiedRequiredItemCount": sum(item["status"] == "verified" for item in required),
        "status": status, "authorizes": [],
    }
