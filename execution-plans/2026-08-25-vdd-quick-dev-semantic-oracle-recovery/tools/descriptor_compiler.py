"""Descriptor owner for the Quick Dev boundary."""
from __future__ import annotations

from typing import Any


def validate_descriptor(value: dict[str, Any]) -> tuple[bool, str]:
    required = {"target", "argv", "cwd", "timeout_seconds", "shell", "case_source_refs", "case_producer_ref"}
    if not isinstance(value, dict) or not required.issubset(value):
        return False, "QD-DESCRIPTOR-RED"
    if value.get("shell") is not False or not isinstance(value.get("argv"), list) or not value["argv"]:
        return False, "QD-DESCRIPTOR-RED"
    if not isinstance(value.get("case_source_refs"), list) or not value["case_source_refs"] or not isinstance(value.get("case_producer_ref"), str) or not value["case_producer_ref"].strip():
        return False, "QD-DESCRIPTOR-BINDING-INCOMPLETE"
    if not all(isinstance(item, str) and item for item in value["argv"]):
        return False, "QD-DESCRIPTOR-RED"
    return isinstance(value.get("timeout_seconds"), int) and value["timeout_seconds"] > 0, "QD-DESCRIPTOR-RED"
