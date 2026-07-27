"""Deterministic extraction of heading-scoped authority clauses."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from acceptance_core import InputError


_HEADING = re.compile(r"^###\s+(?P<identity>[^:：]+?)(?:[:：]\s*(?P<title>.*))?\s*$")


def _hash(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _clause_id(source_path: str, identity: str, title: str) -> str:
    stable = source_path + "\0" + identity.strip() + "\0" + re.sub(r"\s+", " ", title.strip())
    return "CLAUSE-" + hashlib.sha256(stable.encode("utf-8")).hexdigest()[:18].upper()


def extract_heading_clauses(source: Path, repository_relative_path: str) -> dict[str, Any]:
    if not source.is_file() or not isinstance(repository_relative_path, str) or not repository_relative_path:
        raise InputError("source clause authority is invalid")
    raw = source.read_bytes()
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise InputError("source clauses require UTF-8 authority") from exc
    clauses: list[dict[str, Any]] = []
    for index, line in enumerate(lines, start=1):
        match = _HEADING.match(line)
        if not match:
            continue
        identity, title = match.group("identity").strip(), (match.group("title") or "").strip()
        if not identity:
            raise InputError("source clause heading identity is invalid")
        clauses.append({
            "clauseId": _clause_id(repository_relative_path, identity, title), "sourcePath": repository_relative_path,
            "sourceHash": _hash(raw), "sourceIdentity": identity, "title": title, "startLine": index,
            "textSignature": "sha256:" + hashlib.sha256(line.encode("utf-8")).hexdigest(),
        })
    if not clauses or len({item["clauseId"] for item in clauses}) != len(clauses):
        raise InputError("source clauses are empty or not uniquely stable")
    return {"schemaVersion": "acceptance-source-clauses.v1", "sources": [{"path": repository_relative_path, "sha256": _hash(raw)}], "clauses": clauses, "authorizes": []}
