from __future__ import annotations

import hashlib
import json
import re
from pathlib import PurePosixPath
from typing import Any

_DOMAIN = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*\.v[1-9][0-9]*$")
_INT64_MIN, _INT64_MAX = -(2**63), 2**63 - 1

def _reject_constant(_: str) -> None: raise ValueError("non-finite JSON number")
def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result: raise ValueError("duplicate JSON key")
        result[key] = value
    return result
def _integer(raw: str) -> int:
    if raw == "-0" or (len(raw) > 1 and raw[0] == "0") or (raw.startswith("-0") and len(raw) > 2): raise ValueError("non-canonical JSON integer")
    value = int(raw)
    if not _INT64_MIN <= value <= _INT64_MAX: raise ValueError("JSON integer outside int64")
    return value
def _validate(value: Any) -> None:
    if value is None or isinstance(value, bool): return
    if isinstance(value, int):
        if not _INT64_MIN <= value <= _INT64_MAX: raise ValueError("JSON integer outside int64")
        return
    if isinstance(value, str):
        if any(0xD800 <= ord(char) <= 0xDFFF for char in value): raise ValueError("lone surrogate")
        return
    if isinstance(value, list):
        for item in value: _validate(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str): raise ValueError("JSON object key must be string")
            _validate(key); _validate(item)
        return
    raise ValueError("canonical JSON rejects floats and unsupported values")
def parse_json_strict(raw: bytes | str) -> Any:
    if isinstance(raw, bytes):
        if raw.startswith(b"\xef\xbb\xbf"): raise ValueError("UTF-8 BOM is forbidden")
        raw = raw.decode("utf-8")
    value = json.loads(raw, object_pairs_hook=_pairs, parse_int=_integer, parse_float=lambda _: (_ for _ in ()).throw(ValueError("JSON fractions are forbidden")), parse_constant=_reject_constant)
    _validate(value); return value
def canonical_bytes(value: Any) -> bytes:
    _validate(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
def domain_hash(domain: str, projection: Any) -> str:
    if not _DOMAIN.fullmatch(domain): raise ValueError("invalid evidence domain")
    return "sha256:" + hashlib.sha256(canonical_bytes({"domain": domain, "payload": projection})).hexdigest()
def normalize_repository_path(root: str, path: str) -> str:
    if not isinstance(root, str) or not isinstance(path, str) or not root or not path: raise ValueError("repository root and path are required")
    raw = path.replace("\\", "/")
    if raw.startswith("/") or re.match(r"^[A-Za-z]:", raw) or raw.startswith("//"): raise ValueError("absolute path is forbidden")
    parts = []
    for part in raw.split("/"):
        if part in ("", "."): continue
        if part == "..":
            if not parts: raise ValueError("path escapes repository root")
            parts.pop()
        else: parts.append(part)
    if not parts: raise ValueError("repository-relative path is required")
    return "/".join(parts)
def validate_content_identity(domain: str, projection: Any, expected: str) -> bool:
    if not isinstance(expected, str): raise ValueError("expected identity is invalid")
    return domain_hash(domain, projection) == expected
