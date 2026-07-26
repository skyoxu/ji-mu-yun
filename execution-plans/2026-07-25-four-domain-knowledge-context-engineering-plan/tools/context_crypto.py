#!/usr/bin/env python3
"""Plan-local RFC 8785 canonicalization subset and HMAC helpers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any


def _validate_unicode(value: str) -> None:
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise ValueError("JCS input contains an unpaired surrogate")


def _utf16_sort_key(value: str) -> bytes:
    _validate_unicode(value)
    return value.encode("utf-16-be")


def _emit(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        raise ValueError("Floating-point values are outside the manifest JCS profile")
    if isinstance(value, str):
        _validate_unicode(value)
        return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    if isinstance(value, list):
        return "[" + ",".join(_emit(item) for item in value) + "]"
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise ValueError("JCS object keys must be strings")
        ordered = sorted(value, key=_utf16_sort_key)
        return "{" + ",".join(_emit(key) + ":" + _emit(value[key]) for key in ordered) + "}"
    raise ValueError(f"Unsupported JCS value type: {type(value).__name__}")


def canonicalize_jcs(value: Any) -> bytes:
    """Return RFC 8785 bytes for the manifest profile (no floating-point fields)."""
    return _emit(value).encode("utf-8")


def sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def hmac_sha256_base64(key: bytes, value: bytes) -> str:
    return base64.b64encode(hmac.new(key, value, hashlib.sha256).digest()).decode("ascii")
