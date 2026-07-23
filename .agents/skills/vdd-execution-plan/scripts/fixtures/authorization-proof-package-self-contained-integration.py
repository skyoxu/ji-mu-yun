#!/usr/bin/env python3
"""Execute the VDD golden package as a self-contained integration sample."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
RUNNER = ROOT / ".agents" / "skills" / "vdd-execution-plan" / "scripts" / "authorization_proof_package.py"
PACKAGE = ROOT / ".agents" / "skills" / "vdd-execution-plan" / "scripts" / "fixtures" / "authorization-proof-package-golden.json"


def main() -> int:
    environment = dict(os.environ)
    environment.setdefault("VDD_AUTHORIZATION_PROOF_SIGNING_KEY", "vdd-self-contained-integration-key")
    completed = subprocess.run(
        [sys.executable, str(RUNNER), str(PACKAGE), "--orchestrate"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode == 0:
        result = json.loads(completed.stdout)
        result["current_candidate_hash"] = result["candidate_hash"]
        sys.stdout.write(json.dumps(result, indent=2) + "\n")
    else:
        sys.stdout.write(completed.stdout)
    sys.stderr.write(completed.stderr)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
