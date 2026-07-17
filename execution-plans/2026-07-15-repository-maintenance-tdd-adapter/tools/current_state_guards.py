from __future__ import annotations

import json
from pathlib import Path


def _finding(target: str, message: str) -> dict[str, str]:
    return {"rule_id": "RMAP-DOC-CURRENT-STATE", "target": target, "message": message}


def validate_current_state_projection(plan_root: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    intent = (plan_root / "01-intent-authority-and-non-goals.md").read_text(encoding="utf-8")
    slices = (plan_root / "04-behavior-slices-and-implementation-order.md").read_text(encoding="utf-8")
    audit = (plan_root / "98-source-to-split-audit.md").read_text(encoding="utf-8")
    requirements = json.loads((plan_root / "schemas" / "requirements.v1.json").read_text(encoding="utf-8"))
    stale_intent = {
        "Current 555 repair baseline",
        "separate uncommitted upstream changes",
        "must be included in the eventual plan commit",
    }
    required_intent = {
        "555 repair started from HEAD `6adab7f741b9080a7e14758a815d02403d13a7b2`",
        "landed in commit `3d9868dc464284ecb4f6793b51fef7874002f4ed`",
        "run-scoped observations",
    }
    if stale_intent & set(fragment for fragment in stale_intent if fragment in intent) or not all(fragment in intent for fragment in required_intent):
        findings.append(_finding("01-intent-authority-and-non-goals.md", "repair history or observed validation prose is stale"))
    if "RED: deliberate duplicate ownership" not in slices or "ADR-ID collision remains an independent negative fixture" not in slices:
        findings.append(_finding("04-behavior-slices-and-implementation-order.md", "S0 observed RED differs from the machine contract"))
    if "`ADDED`: one framework ADR" in audit or "reuse accepted ADR-0041 as the shared control-plane ownership precedent" not in audit:
        findings.append(_finding("98-source-to-split-audit.md", "ADR reuse delta is stale"))
    rmap_001 = next((item for item in requirements.get("requirements", []) if item.get("id") == "RMAP-001"), {})
    expected = "ADR-0041 owns the shared control-plane ownership pattern and Bootstrap execution boundary without defining TDD Adapter semantics or allocating a colliding ADR ID."
    if rmap_001.get("summary") != expected:
        findings.append(_finding("schemas/requirements.v1.json:RMAP-001", "ADR-0041 ownership summary is overbroad"))
    return findings
