"""Read-only restart inventory check; no compiler or lifecycle publication."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
ROOT = next(p for p in HERE.parents if (p / "AGENTS.md").is_file())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-backend", action="store_true")
    args = parser.parse_args()
    inventory = json.loads((HERE / "restart-inputs.json").read_text(encoding="utf-8"))
    findings = []
    for row in inventory["files"]:
        path = ROOT / row["path"]
        if not path.is_file():
            findings.append("missing-input:" + row["path"])
        elif "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
            findings.append("changed-input:" + row["path"])
    bundle = HERE.parent / "current-plan/semantic-plan-bundle.v1.json"
    if not bundle.is_file():
        findings.append("missing-reviewed-bundle")
    elif "sha256:" + hashlib.sha256(bundle.read_bytes()).hexdigest() != inventory["reviewed_bundle_sha256"]:
        findings.append("changed-reviewed-bundle")
    backend = os.environ.get("SC_LLM_BACKEND", "codex-cli").strip().lower() or "codex-cli"
    # Presence check only. Never print credentials/configuration contents or
    # claim authentication/network readiness without an actual backend call.
    backend_findings = []
    if backend == "codex-cli":
        if shutil.which("codex") is None:
            backend_findings.append("codex-not-on-PATH")
    elif backend == "openai-api":
        if importlib.util.find_spec("openai") is None:
            backend_findings.append("openai-sdk-missing")
        if not os.environ.get("OPENAI_API_KEY", "").strip():
            backend_findings.append("OPENAI_API_KEY-not-configured")
    else:
        backend_findings.append("unsupported-SC_LLM_BACKEND")
    failed = bool(findings or (args.require_backend and backend_findings))
    print(json.dumps({"status": "blocked" if failed else "inputs-verified", "input_findings": findings, "backend": backend, "backend_presence_findings": backend_findings, "backend_authentication_and_network": "not-tested", "canonical_compiler_ran": False, "authorizes": []}, sort_keys=True))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
