from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sqlite3
import sys
import uuid
from pathlib import Path
from typing import Any


FIXTURE_PATHS = [
    "PhaseA.Platform.Tests/Fixtures/route-action-descriptors.v1.json",
    "PhaseA.Platform.Tests/Fixtures/route-module-contracts.v1.json",
    "PhaseA.Platform.Tests/Fixtures/route-status-vocabulary.v1.json",
    "PhaseA.Platform.Tests/Fixtures/evidence-ref-kind.v1.json",
]

SECRET_MARKERS = [
    "PHASEA_ADMIN_TOKEN",
    "PHASEA_ADMIN_TOKEN_HASH",
    "OPENAI_API_KEY",
    "AICODEMIRROR_API_KEY",
    "Authorization",
    "Bearer ",
    "token_hash",
    "provider_key",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only Phase A GDD-to-module route governance audit.")
    parser.add_argument("--repository-root", default=os.environ.get("PHASEA_REPOSITORY_ROOT", str(Path.cwd())))
    parser.add_argument("--metadata-db", default=os.environ.get("PHASEA_METADATA_DB_PATH", ""))
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    repository_root = Path(args.repository_root).resolve()
    run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    out_dir = Path(args.out).resolve() if args.out else repository_root / "logs" / "phase-a-gdd-to-module-governance-audit" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    events: list[dict[str, Any]] = []
    status = "failed"
    try:
        fixture_summary = audit_fixtures(repository_root, failures)
        events.append({"event": "fixture_audit", **fixture_summary})
        if args.metadata_db:
            db_summary = audit_metadata_db(Path(args.metadata_db), failures)
            events.append({"event": "metadata_db_audit", **db_summary})
        else:
            events.append({"event": "metadata_db_audit_skipped", "reason": "--metadata-db was not supplied"})

        if failures:
            raise AssertionError("governance audit failed")
        status = "ok"
        return 0
    except Exception as ex:
        if not failures:
            failures.append(str(ex))
        events.append({"event": "governance_audit_failed", "type": type(ex).__name__, "error": str(ex)})
        print(f"PHASE_A_GDD_TO_MODULE_GOVERNANCE_AUDIT status=failed out={out_dir} error={ex}", file=sys.stderr)
        return 1
    finally:
        summary = {
            "schema_version": "phase-a-gdd-to-module-governance-audit.v1",
            "status": status,
            "run_id": run_id,
            "script": "scripts/python/phase_a_gdd_to_module_governance_audit.py",
            "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "repository_root": str(repository_root),
            "metadata_db": str(Path(args.metadata_db).resolve()) if args.metadata_db else "",
            "events": events,
            "failures": failures,
        }
        secret_violations = find_secret_markers(json.dumps(summary, ensure_ascii=False))
        if secret_violations:
            summary["status"] = "failed"
            summary["failures"] = [*summary["failures"], *secret_violations]
        (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8", newline="\n")
        if status == "ok":
            print(f"PHASE_A_GDD_TO_MODULE_GOVERNANCE_AUDIT status=ok out={out_dir}")


def audit_fixtures(repository_root: Path, failures: list[str]) -> dict[str, Any]:
    payloads: dict[str, dict[str, Any]] = {}
    for rel in FIXTURE_PATHS:
        path = repository_root / rel
        if not path.is_file():
            failures.append(f"fixture_missing:{rel}")
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            failures.append(f"fixture_root_not_object:{rel}")
            continue
        payloads[rel] = payload

    actions = payloads.get("PhaseA.Platform.Tests/Fixtures/route-action-descriptors.v1.json", {}).get("actions", [])
    contracts = payloads.get("PhaseA.Platform.Tests/Fixtures/route-module-contracts.v1.json", {}).get("contracts", [])
    action_ids = {str(action.get("actionId", "")) for action in actions if isinstance(action, dict)}
    for contract in contracts if isinstance(contracts, list) else []:
        if not isinstance(contract, dict):
            continue
        for action_id in contract.get("actionIds", []):
            if action_id not in action_ids:
                failures.append(f"contract_action_unmapped:{contract.get('routeId')}:{action_id}")
        if contract.get("promptSourceBoundaryRequired") is True and contract.get("recoverySourceOrderRef") != "hosted-route-recovery-order.v1":
            failures.append(f"contract_recovery_order_missing:{contract.get('routeId')}")

    return {
        "fixture_count": len(payloads),
        "action_count": len(action_ids),
        "contract_count": len(contracts) if isinstance(contracts, list) else 0,
    }


def audit_metadata_db(metadata_db: Path, failures: list[str]) -> dict[str, Any]:
    if not metadata_db.is_file():
        failures.append(f"metadata_db_missing:{metadata_db}")
        return {"status": "missing"}
    connection = sqlite3.connect(f"file:{metadata_db}?mode=ro", uri=True)
    try:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        required = {
            "project_admin_review_queue",
            "project_route_prompt_evidence_bindings",
            "project_diagnostic_spool",
            "project_delete_tombstones",
            "game_type_maintenance_records",
        }
        for table in sorted(required - tables):
            failures.append(f"metadata_table_missing:{table}")
        counts = {}
        for table in sorted(required & tables):
            counts[table] = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        return {"status": "checked", "tables": sorted(required & tables), "counts": counts}
    finally:
        connection.close()


def find_secret_markers(text: str) -> list[str]:
    violations: list[str] = []
    for marker in SECRET_MARKERS:
        if marker.lower() in text.lower():
            violations.append(f"secret_marker:{marker.strip()}")
    return sorted(set(violations))


if __name__ == "__main__":
    raise SystemExit(main())
