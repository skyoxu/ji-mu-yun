"""Small Draft 2020-12 subset used by repository-owned Quick Dev contracts."""

from __future__ import annotations

import json
import re
from typing import Any


def _type_matches(expected: str, instance: Any) -> bool:
    return {
        "object": isinstance(instance, dict),
        "array": isinstance(instance, list),
        "string": isinstance(instance, str),
        "integer": isinstance(instance, int) and not isinstance(instance, bool),
        "number": isinstance(instance, (int, float)) and not isinstance(instance, bool),
        "boolean": isinstance(instance, bool),
        "null": instance is None,
    }.get(expected, True)


def schema_errors(
    schema: dict[str, Any],
    instance: Any,
    *,
    path: str = "$",
    root_schema: dict[str, Any] | None = None,
) -> list[str]:
    root = schema if root_schema is None else root_schema
    errors: list[str] = []
    reference = schema.get("$ref")
    if isinstance(reference, str):
        if not reference.startswith("#/$defs/"):
            return [f"{path}: unsupported reference {reference}"]
        target = root.get("$defs", {}).get(reference.removeprefix("#/$defs/"))
        if not isinstance(target, dict):
            return [f"{path}: unresolved reference {reference}"]
        return schema_errors(target, instance, path=path, root_schema=root)
    expected_type = schema.get("type")
    if isinstance(expected_type, str) and not _type_matches(expected_type, instance):
        return [f"{path}: expected {expected_type}"]
    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: const mismatch")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: enum mismatch")
    if isinstance(instance, str):
        if len(instance) < schema.get("minLength", 0):
            errors.append(f"{path}: shorter than minLength")
        if "pattern" in schema and re.search(schema["pattern"], instance) is None:
            errors.append(f"{path}: pattern mismatch")
    if isinstance(instance, list):
        if len(instance) < schema.get("minItems", 0):
            errors.append(f"{path}: fewer than minItems")
        if schema.get("uniqueItems") and len({json.dumps(item, sort_keys=True) for item in instance}) != len(instance):
            errors.append(f"{path}: duplicate items")
        child = schema.get("items")
        if isinstance(child, dict):
            for index, item in enumerate(instance):
                errors.extend(schema_errors(child, item, path=f"{path}[{index}]", root_schema=root))
    if isinstance(instance, dict):
        properties = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}: missing required {key}")
        if schema.get("additionalProperties") is False:
            errors.extend(f"{path}: unexpected property {key}" for key in instance if key not in properties)
        for key, child in properties.items():
            if key in instance and isinstance(child, dict):
                errors.extend(schema_errors(child, instance[key], path=f"{path}.{key}", root_schema=root))
    for child in schema.get("allOf", []):
        errors.extend(schema_errors(child, instance, path=path, root_schema=root))
    if "anyOf" in schema and all(
        schema_errors(child, instance, path=path, root_schema=root)
        for child in schema["anyOf"]
    ):
        errors.append(f"{path}: no anyOf branch matched")
    if "not" in schema and not schema_errors(schema["not"], instance, path=path, root_schema=root):
        errors.append(f"{path}: prohibited schema matched")
    if "if" in schema:
        branch = "then" if not schema_errors(schema["if"], instance, path=path, root_schema=root) else "else"
        errors.extend(schema_errors(schema.get(branch, {}), instance, path=path, root_schema=root))
    return errors
