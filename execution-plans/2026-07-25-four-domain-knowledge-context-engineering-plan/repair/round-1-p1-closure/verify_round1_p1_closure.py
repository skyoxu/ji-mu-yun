#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys

EXPECTED = [
    ".agents/skills/maintain-knowledge-base/scripts/test_maintain_knowledge.py",
    "PhaseA.Platform.Tests/Data/HostedContextManifestIssuerTests.cs",
    "PhaseA.Platform.Tests/Data/HostedContextManifestSignatureServiceTests.cs",
    "PhaseA.Platform.Tests/Data/HostedContextManifestStoreTests.cs",
    "PhaseA.Platform.Tests/Llm/LlmRouteEngineTests.cs",
    "PhaseA.Platform.Tests/Runs/CodexHostedProcessCommandFactoryTests.cs",
    "execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/tools/tests/test_plan_validator.py",
    "scripts/sc/tests/test_llm_backend.py",
    "scripts/sc/tests/test_llm_review_runtime_budget.py"
]
COMMANDS = [
    [sys.executable, ".agents/skills/maintain-knowledge-base/scripts/test_maintain_knowledge.py"],
    [sys.executable, "scripts/sc/tests/test_llm_backend.py"],
    [sys.executable, "scripts/sc/tests/test_llm_review_runtime_budget.py"],
    ["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--no-restore", "--filter", "FullyQualifiedName~HostedContextManifest|FullyQualifiedName~LlmRouteEngine|FullyQualifiedName~CodexHostedProcessCommandFactory"],
    [sys.executable, "execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/tools/validate_whole_directory.py"],
]

parser = argparse.ArgumentParser()
parser.add_argument("--bound-test", action="append", default=[])
args = parser.parse_args()
if sorted(args.bound_test) != EXPECTED:
    raise SystemExit("bound targeted test set mismatch")
for command in COMMANDS:
    result = subprocess.run(command, text=True, encoding="utf-8", errors="replace", capture_output=True, check=False)
    print("COMMAND", " ".join(command))
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        raise SystemExit(result.returncode)
print("7-25 ROUND 1 P1 REPAIR COMPOSITION PASS")
