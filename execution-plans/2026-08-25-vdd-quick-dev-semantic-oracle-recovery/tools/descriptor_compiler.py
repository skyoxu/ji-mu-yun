"""Descriptor owner for the Quick Dev boundary."""
from __future__ import annotations

from typing import Any


def validate_descriptor(value: dict[str, Any]) -> tuple[bool, str]:
    required = {"target", "argv", "cwd", "timeout_seconds", "shell", "case_source_refs", "case_producer_ref"}
    if not isinstance(value, dict) or not required.issubset(value):
        return False, "QD-DESCRIPTOR-RED"
    if value.get("shell") is not False or not isinstance(value.get("argv"), list) or not value["argv"]:
        return False, "QD-DESCRIPTOR-RED"
    if not all(isinstance(item, str) and item for item in value["argv"]):
        return False, "QD-DESCRIPTOR-RED"
    if not isinstance(value.get("timeout_seconds"), int) or value["timeout_seconds"] <= 0:
        return False, "QD-DESCRIPTOR-RED"
    return True, ""
