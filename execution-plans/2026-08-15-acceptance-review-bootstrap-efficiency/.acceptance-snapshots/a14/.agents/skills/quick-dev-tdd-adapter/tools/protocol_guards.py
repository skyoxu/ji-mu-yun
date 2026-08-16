from __future__ import annotations

import fnmatch
import hashlib
import sys
from pathlib import PurePosixPath
from typing import Any
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))
from scripts.toolchain.canonical_evidence import canonical_bytes


STAGES = ["red", "green", "refactor"]
STAGE_GOALS = {"red": "observe-red", "green": "make-red-green", "refactor": "preserve-green-refactor"}
STAGE_STATES = {"red": "red-observed", "green": "green-observed", "refactor": "refactor-verified"}


def bytes_hash(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def value_hash(value: Any) -> str:
    # Existing protocol schemas retain this legacy envelope until their owner versions them.
    return bytes_hash(canonical_bytes(value))


def safe_relative(value: Any) -> bool:
    if not isinstance(value, str) or not value or "\x00" in value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts and not any(":" in part for part in path.parts)


def _matches_any(path: str, patterns: list[str]) -> bool:
    normalized = path.replace("\\", "/").casefold()
    return any(fnmatch.fnmatchcase(normalized, pattern.replace("\\", "/").casefold()) for pattern in patterns)


def classify_scope(path: str, boundaries: dict[str, Any]) -> str:
    if _matches_any(path, boundaries.get("forbidden_write_set", [])):
        return "forbidden"
    if _matches_any(path, boundaries.get("allowed_write_set", [])):
        return "allowed"
    return "unrelated"
