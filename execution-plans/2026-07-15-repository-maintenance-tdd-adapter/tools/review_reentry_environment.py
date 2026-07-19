from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


VOLATILE_CODEX_ARG0 = re.compile(
    r"^[A-Za-z]:\\Users\\[^\\]+\\\.codex\\tmp\\arg0\\codex-arg0[^\\;]*$",
    re.IGNORECASE,
)


def stable_environment_evidence(
    bootstrap: Any,
    bootstrap_run_path: Path,
) -> tuple[dict[str, str], dict[str, str]]:
    proof = json.loads((bootstrap_run_path / "access-proof.json").read_text(encoding="utf-8"))
    handshake_path = bootstrap_run_path / str(proof.get("handshakePath", ""))
    request = json.loads((handshake_path.parent / "request.json").read_text(encoding="utf-8"))
    captured = request.get("environmentEvidence")
    if not isinstance(captured, dict) or proof.get("environmentEvidenceHash") != bootstrap.value_hash(captured):
        raise ValueError("captured review environment is missing or stale")
    current_child, current = bootstrap.child_environment()

    def normalized(evidence: dict[str, str]) -> dict[str, str]:
        result = dict(evidence)
        raw_path = result.get("PATH")
        if isinstance(raw_path, str):
            result["PATH"] = ";".join("<CODEX_ARG0>" if VOLATILE_CODEX_ARG0.fullmatch(item) else item for item in raw_path.split(";"))
        return result

    if normalized(captured) != normalized(current):
        raise ValueError("stable review environment identity has drifted")
    return current_child, captured
