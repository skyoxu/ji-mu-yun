"""Extract the immutable RA-SKILL inventory from its declared source contract."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any


_IDENTITY = re.compile(r"^###\s+(RA-SKILL-([0-9]{3}))\s*[：:]\s*(\S.*)$", re.MULTILINE)
_EXPECTED = tuple(range(1, 74))


class RequirementInventoryError(ValueError):
    pass


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def extract_requirement_inventory_text(text: str, source_path: str, *, source_hash: str | None = None) -> dict[str, Any]:
    if not isinstance(text, str) or not isinstance(source_path, str) or not source_path:
        raise RequirementInventoryError("source text and repository-relative source path are required")
    matches = list(_IDENTITY.finditer(text))
    observed: dict[int, tuple[str, str, int]] = {}
    duplicates: list[str] = []
    for match in matches:
        number = int(match.group(2))
        if number in observed:
            duplicates.append(match.group(1))
            continue
        observed[number] = (match.group(1), match.group(3), text.count("\n", 0, match.start()) + 1)
    if duplicates:
        raise RequirementInventoryError("duplicate RA requirement identity: " + ", ".join(sorted(duplicates)))
    missing = [f"RA-SKILL-{number:03d}" for number in _EXPECTED if number not in observed]
    extras = [f"RA-SKILL-{number:03d}" for number in sorted(observed) if number not in _EXPECTED]
    if missing or extras:
        detail = []
        if missing:
            detail.append("missing " + ", ".join(missing))
        if extras:
            detail.append("unexpected " + ", ".join(extras))
        raise RequirementInventoryError("atomic RA requirement set is invalid: " + "; ".join(detail))
    return {
        "schemaVersion": "refactor-acceptance.requirement-inventory.v1",
        "source": {"path": source_path, "sha256": source_hash or _sha256_bytes(text.encode("utf-8"))},
        "requirements": [
            {"id": observed[number][0], "title": observed[number][1], "sourceLine": observed[number][2]}
            for number in _EXPECTED
        ],
        "authorizes": [],
    }


def extract_requirement_inventory(source: Path, source_path: str) -> dict[str, Any]:
    data = source.read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RequirementInventoryError("requirement source must be UTF-8") from exc
    return extract_requirement_inventory_text(text, source_path, source_hash=_sha256_bytes(data))
