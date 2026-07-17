from __future__ import annotations

import fnmatch
import os
import re
import subprocess
import uuid
from functools import lru_cache
from pathlib import Path, PureWindowsPath
from typing import Any


SCHEMA_ANNOTATIONS = {"$schema", "$id", "$defs", "title", "description"}
SCHEMA_ASSERTIONS = {"$ref", "type", "required", "additionalProperties", "properties", "const", "pattern", "minItems", "minLength", "uniqueItems", "items", "enum"}


def junction_escape_is_rejected(plan_root: Path) -> bool | None:
    repository_root = plan_root.parents[1]
    junction = repository_root / "logs" / f"rmap-junction-{uuid.uuid4().hex}"
    outside = Path(__file__).resolve().anchor + "Windows\\Temp"
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(outside)], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return None
    try:
        return not typed_path_is_safe(f"logs/{junction.name}/file.txt", "repo_path", plan_root)
    finally:
        junction.rmdir()


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return False


def schema_error(value: Any, schema: dict[str, Any], path: str = "$", root_schema: dict[str, Any] | None = None) -> str | None:
    root_schema = schema if root_schema is None else root_schema
    unsupported = set(schema) - SCHEMA_ANNOTATIONS - SCHEMA_ASSERTIONS
    if unsupported:
        return f"{path}: unsupported schema keywords {sorted(unsupported)}"
    reference = schema.get("$ref")
    if reference is not None:
        if not isinstance(reference, str) or not reference.startswith("#/$defs/"):
            return f"{path}: unsupported schema reference"
        definition = root_schema.get("$defs", {}).get(reference.removeprefix("#/$defs/"))
        if not isinstance(definition, dict):
            return f"{path}: missing schema definition {reference}"
        return schema_error(value, definition, path, root_schema)
    expected_type = schema.get("type")
    if expected_type is not None:
        allowed = expected_type if isinstance(expected_type, list) else [expected_type]
        if not all(isinstance(item, str) for item in allowed) or not any(_matches_type(value, item) for item in allowed):
            return f"{path}: expected type {allowed}"
    if "const" in schema and value != schema["const"]:
        return f"{path}: value does not match const"
    if "enum" in schema and value not in schema["enum"]:
        return f"{path}: value is not in enum"
    if isinstance(value, str) and "pattern" in schema and re.search(schema["pattern"], value) is None:
        return f"{path}: value does not match pattern"
    if isinstance(value, str) and "minLength" in schema:
        minimum = schema["minLength"]
        if not isinstance(minimum, int) or minimum < 0 or len(value) < minimum:
            return f"{path}: string is shorter than minLength"
    if isinstance(value, dict):
        required = schema.get("required", [])
        if not isinstance(required, list) or not all(isinstance(item, str) for item in required):
            return f"{path}: required must be a string list"
        missing = [item for item in required if item not in value]
        if missing:
            return f"{path}: missing required properties {missing}"
        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            return f"{path}: properties must be an object"
        if schema.get("additionalProperties") is False:
            extras = set(value) - set(properties)
            if extras:
                return f"{path}: unexpected properties {sorted(extras)}"
        for key, child_schema in properties.items():
            if key in value:
                if not isinstance(child_schema, dict):
                    return f"{path}.{key}: property schema must be an object"
                error = schema_error(value[key], child_schema, f"{path}.{key}", root_schema)
                if error:
                    return error
    if isinstance(value, list):
        minimum = schema.get("minItems")
        if minimum is not None and (not isinstance(minimum, int) or len(value) < minimum):
            return f"{path}: array has fewer than minItems"
        if schema.get("uniqueItems") is True:
            serialized = [repr(item) for item in value]
            if len(serialized) != len(set(serialized)):
                return f"{path}: array items are not unique"
        item_schema = schema.get("items")
        if item_schema is not None:
            if not isinstance(item_schema, dict):
                return f"{path}: items must be an object"
            for index, item in enumerate(value):
                error = schema_error(item, item_schema, f"{path}[{index}]", root_schema)
                if error:
                    return error
    return None


def typed_path_is_safe(value: Any, path_type: Any, plan_root: Path) -> bool:
    if not isinstance(value, str) or not value or "\x00" in value:
        return False
    path = PureWindowsPath(value.replace("/", "\\"))
    if path.is_absolute() or path.drive:
        return False
    if any(part not in {"."} and (part in {"..", ""} or ":" in part) for part in path.parts):
        return False
    repository_root = plan_root.parents[1]
    roots = {
        "repo_path": repository_root,
        "plan_path": plan_root,
        "run_path": repository_root / "logs",
    }
    root = roots.get(path_type)
    if root is None:
        return False
    try:
        resolved_root = root.resolve(strict=True)
        resolved_candidate = resolved_root.joinpath(*path.parts).resolve(strict=False)
        resolved_candidate.relative_to(resolved_root)
    except (OSError, RuntimeError, ValueError):
        return False
    return True


def contained_file(root: Path, relative: Any, *, must_exist: bool = True) -> Path | None:
    if not isinstance(relative, str) or not relative or "\x00" in relative:
        return None
    windows_path = PureWindowsPath(relative.replace("/", "\\"))
    if windows_path.is_absolute() or windows_path.drive or any(
        part in {"", ".", ".."} or ":" in part for part in windows_path.parts
    ):
        return None
    try:
        resolved_root = root.resolve(strict=True)
        candidate = resolved_root.joinpath(*windows_path.parts)
        current = resolved_root
        for part in windows_path.parts:
            current = current / part
            if current.exists() and os.path.islink(current):
                return None
            if current.exists() and current.resolve(strict=True) != current.absolute():
                return None
        resolved_candidate = candidate.resolve(strict=must_exist)
        resolved_candidate.relative_to(resolved_root)
        if must_exist and not resolved_candidate.is_file():
            return None
    except (OSError, RuntimeError, ValueError):
        return None
    return resolved_candidate


def _normalize_glob(pattern: str) -> tuple[str, ...] | None:
    if not isinstance(pattern, str) or not pattern or "\x00" in pattern:
        return None
    normalized = pattern.replace("\\", "/").strip("/").casefold()
    parts = tuple(part for part in normalized.split("/") if part not in {"", "."})
    if not parts or ".." in parts or PureWindowsPath(pattern).drive:
        return None
    return parts


def _segment_intersects(left: str, right: str) -> bool:
    left_wild = any(marker in left for marker in "*?[")
    right_wild = any(marker in right for marker in "*?[")
    if not left_wild and not right_wild:
        return left == right
    if not left_wild:
        return fnmatch.fnmatchcase(left, right)
    if not right_wild:
        return fnmatch.fnmatchcase(right, left)
    if left == right or left == "*" or right == "*":
        return True
    return True


def glob_patterns_overlap(left: str, right: str) -> bool:
    left_parts = _normalize_glob(left)
    right_parts = _normalize_glob(right)
    if left_parts is None or right_parts is None:
        return True

    @lru_cache(maxsize=None)
    def intersects(left_index: int, right_index: int) -> bool:
        if left_index == len(left_parts) and right_index == len(right_parts):
            return True
        if left_index == len(left_parts):
            return all(part == "**" for part in right_parts[right_index:])
        if right_index == len(right_parts):
            return all(part == "**" for part in left_parts[left_index:])
        left_part = left_parts[left_index]
        right_part = right_parts[right_index]
        if left_part == "**" and right_part == "**":
            return intersects(left_index + 1, right_index) or intersects(left_index, right_index + 1)
        if left_part == "**":
            return intersects(left_index + 1, right_index) or intersects(left_index, right_index + 1)
        if right_part == "**":
            return intersects(left_index, right_index + 1) or intersects(left_index + 1, right_index)
        return _segment_intersects(left_part, right_part) and intersects(left_index + 1, right_index + 1)

    return intersects(0, 0)
