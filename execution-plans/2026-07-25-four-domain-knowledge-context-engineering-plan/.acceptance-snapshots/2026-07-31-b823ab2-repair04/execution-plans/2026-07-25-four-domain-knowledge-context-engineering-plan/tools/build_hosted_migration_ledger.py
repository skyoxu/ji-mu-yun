#!/usr/bin/env python3
"""Derive a conservative Hosted-reachability ledger from the frozen inventories."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


PLAN_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = PLAN_DIR.parents[1]
INVENTORY_NAMES = (
    "codex-hosted-callers.v1.json",
    "llm-route-engine-callers.v1.json",
    "python-llm-backend-callers.v1.json",
)
MAP_START = re.compile(r'app\.Map(?:Get|Post|Put|Delete|Methods)\(\s*"([^\"]+)"')
SERVICE = re.compile(r"\[FromServices\]\s+([A-Za-z_]\w*)")
ENFORCE_OVERRIDE = re.compile(r'\["([^\"]+)"\]\s*=\s*HostedContextGateMode\.Enforce')
OPERATION_KEY = re.compile(r'OperationKey:\s*"([^\"]+)"')


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def hosted_routes_by_service(program_text: str) -> dict[str, list[str]]:
    starts = list(MAP_START.finditer(program_text))
    routes: dict[str, list[str]] = {}
    for index, match in enumerate(starts):
        block_end = starts[index + 1].start() if index + 1 < len(starts) else len(program_text)
        route = match.group(1)
        for service in SERVICE.findall(program_text[match.start() : block_end]):
            routes.setdefault(service, []).append(route)
    return {key: sorted(set(value)) for key, value in sorted(routes.items())}


def transitive_routes(repo_root: Path, direct_routes: dict[str, list[str]], targets: set[str]) -> dict[str, list[str]]:
    class_files: dict[str, str] = {}
    for path in (repo_root / "PhaseA.Platform").rglob("*.cs"):
        class_files[path.stem] = path.read_text(encoding="utf-8")
    referencers: dict[str, list[str]] = {name: [] for name in class_files}
    for consumer, text in class_files.items():
        for dependency in class_files:
            if dependency != consumer and dependency in text:
                referencers[dependency].append(consumer)
    result: dict[str, list[str]] = {}
    for target in sorted(targets):
        pending = [target]
        visited: set[str] = set()
        resolved: set[str] = set()
        while pending:
            current = pending.pop()
            if current in visited:
                continue
            visited.add(current)
            resolved.update(direct_routes.get(current, []))
            for consumer in referencers.get(current, []):
                if consumer not in visited:
                    pending.append(consumer)
        result[target] = sorted(resolved)
    return result


def gate_state_for_callsite(entrypoint_family: str, caller: dict[str, object], source: str, enforced_operation_keys: set[str]) -> tuple[str, str]:
    if entrypoint_family not in {"llm-route-engine", "codex-hosted"}:
        return "legacy", "pending"
    line = int(caller.get("line", 0))
    start = sum(len(item) + 1 for item in source.splitlines()[: max(0, line - 1)])
    operation = OPERATION_KEY.search(source, start)
    if operation is not None and operation.group(1) in enforced_operation_keys:
        return "enforce", "enforced"
    return "legacy", "pending"


def build(repo_root: Path, inventory_dir: Path) -> dict[str, object]:
    program = (repo_root / "PhaseA.Platform/Program.cs").read_text(encoding="utf-8")
    enforced_operation_keys = set(ENFORCE_OVERRIDE.findall(program))
    csharp_targets: set[str] = set()
    for name in INVENTORY_NAMES[:2]:
        inventory = load_json(inventory_dir / name)
        csharp_targets.update(Path(str(item["path"])).stem for item in inventory["callers"])
    service_routes = transitive_routes(repo_root, hosted_routes_by_service(program), csharp_targets)
    phase_sources = [path.read_text(encoding="utf-8") for path in (repo_root / "PhaseA.Platform").rglob("*.cs")]
    entries: list[dict[str, object]] = []
    snapshot_id = ""
    for name in INVENTORY_NAMES:
        inventory = load_json(inventory_dir / name)
        current_snapshot = str(inventory["source_snapshot_id"])
        if snapshot_id and snapshot_id != current_snapshot:
            raise ValueError("inventory source snapshots differ")
        snapshot_id = current_snapshot
        for caller in list(inventory["callers"]) + list(inventory["excluded_candidates"]):
            path = str(caller["path"])
            if path.endswith(".py"):
                source_name = Path(path).name
                referenced_by_platform = source_name in program
                entries.append({
                    "callsite_id": caller["callsite_id"],
                    "entrypoint_family": inventory["entrypoint_family"],
                    "path": path,
                    "reachability": "unknown" if referenced_by_platform else "toolchain",
                    "reachability_evidence": "PhaseA.Platform/Program.cs script-name scan",
                    "routes": [],
                    "initial_gate_mode": "not-applicable" if not referenced_by_platform else "unknown",
                    "migration_status": "excluded" if not referenced_by_platform else "blocked",
                })
                continue
            service = Path(path).stem
            routes = service_routes.get(service, [])
            source = (repo_root / path).read_text(encoding="utf-8")
            external_mentions = sum(text.count(service) for text in phase_sources) - (repo_root / path).read_text(encoding="utf-8").count(service)
            unreachable = not routes and external_mentions == 1 and f"AddSingleton<{service}>" in program
            gate_mode, migration_status = gate_state_for_callsite(str(inventory["entrypoint_family"]), caller, source, enforced_operation_keys)
            entries.append({
                "callsite_id": caller["callsite_id"],
                "entrypoint_family": inventory["entrypoint_family"],
                "path": path,
                "reachability": "hosted-route" if routes else "unreachable" if unreachable else "unknown",
                "reachability_evidence": "Program endpoint binding plus static PhaseA.Platform service dependency closure" if routes else "sole Program DI registration without endpoint or source caller" if unreachable else "no complete source reachability proof",
                "routes": routes,
                "initial_gate_mode": gate_mode if routes else "not-applicable" if unreachable else "unknown",
                "migration_status": migration_status if routes else "excluded" if unreachable else "blocked",
            })
    entries.sort(key=lambda item: (str(item["path"]), str(item["callsite_id"])))
    return {
        "schema_version": "jimuyun.hosted-callsite-migration-ledger.v1",
        "generated_by": "tools/build_hosted_migration_ledger.py@v1",
        "source_snapshot_id": snapshot_id,
        "entries": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--inventory-dir", type=Path, default=PLAN_DIR / "inventories")
    parser.add_argument("--output", type=Path, default=PLAN_DIR / "inventories/hosted-callsite-migration-ledger.v1.json")
    args = parser.parse_args()
    payload = build(args.repo_root.resolve(), args.inventory_dir.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    unknown = sum(1 for item in payload["entries"] if item["reachability"] == "unknown")
    print(f"MIGRATION_LEDGER PASS entries={len(payload['entries'])} unknown={unknown}")
    return 0 if unknown == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
