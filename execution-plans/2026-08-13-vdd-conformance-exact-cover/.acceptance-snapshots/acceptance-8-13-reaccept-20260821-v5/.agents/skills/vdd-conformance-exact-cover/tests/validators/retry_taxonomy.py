from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / ".agents/skills/vdd-conformance-exact-cover/scripts"))
from conformance import resolve_runtime_policy, retry_decision  # noqa: E402


def main() -> int:
    text = (ROOT / "_bmad-output/specs/spec-vdd-conformance-exact-cover/execution-policy.md").read_text(encoding="utf-8")
    families = re.findall(r"\| `([^`]+)` \| (\d+) \| `([^`]+)`", text)
    if not families or any(int(ceiling) <= 0 or not action for _family, ceiling, action in families):
        return 2
    if "deterministic failure" not in text.casefold() or "attempt counter" not in text.casefold():
        return 2
    policy = resolve_runtime_policy(ROOT / ".agents/skills/vdd-conformance-exact-cover/references/runtime-policy-registry.v1.json")
    retry = retry_decision("timeout", 1, policy["retry_maximums"]["timeout"], "extract:S1", policy["exhaustion_actions"]["timeout"])
    exhausted = retry_decision("timeout", policy["retry_maximums"]["timeout"], policy["retry_maximums"]["timeout"], "extract:S1", policy["exhaustion_actions"]["timeout"])
    deterministic = retry_decision("schema_error", 1, 2, "extract:S1")
    return 0 if retry["status"] == "retry" and exhausted["status"] == "blocked" and deterministic["status"] == "blocked" else 2


if __name__ == "__main__":
    raise SystemExit(main())
