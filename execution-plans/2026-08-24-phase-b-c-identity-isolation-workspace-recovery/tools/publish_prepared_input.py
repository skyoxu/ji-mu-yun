"""ADR-0041: one-time publication of verified input, never product completion."""
from pathlib import Path
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
PLAN = Path(__file__).resolve().parents[1]


def main():
    subprocess.run([sys.executable, "-B", str(PLAN / "tools/rebuild_current_input.py")],
                   cwd=ROOT, shell=False, check=True)
    marker_path = PLAN / "input-repair-materialization.v1.json"
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    marker["status"] = "input-checks-passed"
    marker_path.write_text(json.dumps(marker, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    handoff_path = PLAN / "LOCAL-HANDOFF.md"
    text = handoff_path.read_text(encoding="utf-8")
    start = text.index("## One deterministic preparation step")
    end = text.index("## Current input and order")
    replacement = """## Prepared input

The current semantic bundle, coverage, agent-context, dependency order and case
map are already assembled and committed. Synchronize this branch, then use the
current Quick Dev Skill directly from S12. Do not rerun VDD or the reconstruction
script. The rebuild transport and script remain recovery provenance only.

Preparation ran the guard regressions, native semantic/routing and CER contracts,
all 73 public Q1 preflights, and source-reference checks before publication.
Evidence is under logs/phase-b-c-input-repair/local-rebuild/. These checks establish
input readiness only. No Phase behavior test, model or formal TDD stage ran.

"""
    text = text[:start] + replacement + text[end:]
    handoff_path.write_text(text, encoding="utf-8", newline="\n")
    index = """# 8-24 Phase B/C Identity Isolation and Workspace Recovery

Start with [LOCAL-HANDOFF.md](LOCAL-HANDOFF.md). Current machine projections are
materialized and checked. No VDD rerun or input assembly is required.

- [Implementation input](implementation-repair-input.md)
- [73-slice navigation](implementation-slices.md)
- [Execution order](implementation-order.v1.json)
- [Atomic case map](implementation-case-map.v1.json)
- [Explicit dispositions](input-repair-dispositions.v1.json)

Start S12 with the current Quick Dev standard profile, governance off.
Historical compiler and execution evidence do not prove this revision or
Phase completion. Current Q7/Q8 and separate Acceptance remain required.
"""
    (PLAN / "00-index.md").write_text(index, encoding="utf-8", newline="\n")
    # Remove the one-time publisher and its trigger after successful verification.
    (ROOT / ".github/workflows/prepare-8-24-input-once.yml").unlink()
    Path(__file__).unlink()


if __name__ == "__main__":
    main()
