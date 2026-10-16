from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


def validate_trx(path: Path, name: str, failure_id: str, returncode: int) -> None:
    document = ET.parse(path)
    ns = {"t": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}
    rows = document.findall(".//t:UnitTestResult", ns)
    if len(rows) != 1 or rows[0].get("testName") != name:
        raise RuntimeError("S25 missing, duplicate, or wrong-target test result")
    row = rows[0]
    counters = document.find(".//t:Counters", ns)
    if counters is None or counters.get("total") != "1" or counters.get("executed") != "1":
        raise RuntimeError("S25 test was not executed exactly once")
    if row.get("outcome") == "Passed" and returncode == 0:
        return
    message = row.findtext(".//t:Message", default="", namespaces=ns)
    stack = row.findtext(".//t:StackTrace", default="", namespaces=ns)
    if (row.get("outcome") == "Failed" and returncode == 1
            and (message.startswith(failure_id + ":") or message.startswith("Xunit.Sdk.XunitException: " + failure_id + ":"))
            and name in stack):
        # CER captures scoped failure IDs from this actual failed call, not TRX prose.
        print("FAILURE_ID:" + failure_id)
        raise AssertionError(message)
    raise RuntimeError("S25 harness failure; not a bound product assertion: " + message[:1000])


def verify_migration(root: Path, nonce: str, before_hash: str, after_hash: str) -> dict:
    """ADR-0061: inspect actual DB bytes read-only, never a producer pass flag."""
    def open_database(filename: str, expected_hash: str):
        path = root / filename
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
            raise ValueError("database-integrity-mismatch")
        return sqlite3.connect(path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)

    before = open_database("before.sqlite3", before_hash)
    try:
        after = open_database("metadata.sqlite3", after_hash)
        try:
            if after.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise ValueError("database-integrity-check-failed")
            def columns(db, table):
                return {row[1] for row in db.execute(f"PRAGMA table_info({table})")}
            if "is_disabled" in columns(before, "accounts"):
                raise ValueError("not-a-legacy-source")
            if not {"is_disabled", "valid_until_utc"} <= columns(after, "accounts"):
                raise ValueError("migration-not-executed")
            if not {"llm_binding_required", "bootstrap_status", "last_activity_utc"} <= columns(after, "projects"):
                raise ValueError("project-migration-incomplete")
            queries = [
                "SELECT id, username, is_admin, created_utc FROM accounts ORDER BY id",
                "SELECT id, account_id, name, game_name, created_utc FROM projects ORDER BY id",
                "SELECT id, project_id, run_type, status, created_utc FROM runs ORDER BY id",
                "SELECT id, run_id, project_id, artifact_type, relative_path, summary, created_utc FROM artifacts ORDER BY id",
            ]
            counts = []
            for query in queries:
                original = before.execute(query).fetchall()
                if not original or after.execute(query).fetchall() != original:
                    raise ValueError("migration-data-or-ownership-changed")
                counts.append(len(original))
            if before.execute("SELECT summary FROM artifacts").fetchall() != [(nonce,)]:
                raise ValueError("stale-invocation")
            return {"ok": True, "pid": os.getpid(), "retained_rows": counts,
                    "before_sha256": before_hash, "after_sha256": after_hash}
        finally:
            after.close()
    finally:
        before.close()


def verify_admin(config: dict) -> dict:
    """Exercise real HTTP authorization; inspect DB, audits and retained content."""
    root = Path(config["root"])
    account = config["account_id"]
    project = config["project_id"]
    records = []
    secrets = [config["admin_token"], config["user_token"], config["actor_token"]]
    db = sqlite3.connect((root / "metadata.sqlite3").resolve().as_uri() + "?mode=ro", uri=True)

    def require(condition, reason):
        if not condition:
            raise AssertionError(reason)

    def request(label, method, path, token, body=None):
        req = urllib.request.Request(config["address"] + path, method=method,
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
            data=None if body is None else json.dumps(body).encode())
        try:
            response = urllib.request.urlopen(req, timeout=10)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            raw = response.read().decode("utf-8")
            payload = json.loads(raw)
            records.append({"case": label, "method": method, "path": path,
                            "status": response.status, "cache_control": response.headers.get("Cache-Control")})
            (root / "http-observations.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
            require("no-store" in response.headers.get("Cache-Control", ""), "private-response-cacheable")
            return response.status, payload

    def state():
        row = db.execute("SELECT is_disabled, token_hash FROM accounts WHERE id=?", (account,)).fetchone()
        require(row is not None, "target-account-deleted")
        return row

    def retained():
        require(db.execute("SELECT account_id FROM projects WHERE id=?", (project,)).fetchall() == [(account,)], "project-ownership-lost")
        row = db.execute("SELECT repo_path FROM workspaces WHERE project_id=?", (project,)).fetchone()
        require(row is not None, "workspace-record-deleted")
        repo = Path(row[0]).resolve()
        require(repo.is_relative_to((root / "workspaces").resolve()), "fixture-workspace-outside-root")
        require((repo / "retained.txt").read_text(encoding="utf-8") == config["nonce"], "project-content-not-recoverable")

    try:
        try:
            initial_state = state()
            require(initial_state[0] == 0, "invalid-initial-account-state")
            retained()
        except AssertionError as error:
            raise RuntimeError("fixture-precondition-failed") from error
        for action, body in (("disable", {"disabled": True}), ("enable", {"disabled": False}), ("revoke", None)):
            path = f"/api/admin/users/{account}/" + ("rotate-token" if action == "revoke" else "status")
            before = state()
            status, _ = request(action + "-denied", "POST", path, config["actor_token"], body)
            require(status == 403 and state() == before, action + "-insufficient-role-mutated-state")
            status, payload = request(action + "-authorized", "POST", path, config["admin_token"], body)
            require(status == 200, action + "-admin-operation-rejected")
            retained()
            if action in ("disable", "enable"):
                require(state() == (int(action == "disable"), before[1]), action + "-wrong-persisted-state")
                # Existing auth contexts have a bounded five-second cache lifetime.
                time.sleep(5.1)
                status, _ = request(action + "-session", "GET", "/api/session", config["user_token"])
                require(status == (401 if action == "disable" else 200), action + "-session-not-updated")
            else:
                replacement = payload.get("token")
                require(isinstance(replacement, str) and bool(replacement), "rotation-missing-replacement")
                secrets.append(replacement)
                require(state()[1] != initial_state[1], "rotation-did-not-change-persisted-hash")
                time.sleep(5.1)
                status, _ = request("old-token-session", "GET", "/api/session", config["user_token"])
                require(status == 401, "revoked-credential-still-usable")
                status, _ = request("new-token-session", "GET", "/api/session", replacement)
                require(status == 200, "replacement-credential-not-usable")
        status, audit_payload = request("audit-denied", "GET", "/api/admin/account-audit", config["actor_token"])
        require(status == 403, "audit-access-not-controlled")
        status, audit_payload = request("audit-authorized", "GET", f"/api/admin/account-audit?targetAccountId={account}", config["admin_token"])
        require(status == 200, "audit-not-readable-by-admin")
        audit_rows = db.execute("SELECT actor_account_id, action, metadata_json FROM admin_account_audit_events WHERE target_account_id=?", (account,)).fetchall()
        expected = {(action, outcome) for action in ("user_disabled", "user_enabled", "user_token_rotated") for outcome in ("denied", "authorized")}
        observed = set()
        for actor, action, raw in audit_rows:
            metadata = json.loads(raw)
            if action not in {a for a, _ in expected}:
                continue
            outcome = metadata.get("outcome")
            require(metadata.get("account_id") == account and metadata.get("action") == action, "audit-target-or-action-mismatch")
            require(bool(metadata.get("operation_id")) and bool(metadata.get("correlation_id")), "audit-not-correlated")
            require(actor == (config["actor_id"] if outcome == "denied" else config["admin_id"]), "audit-actor-mismatch")
            observed.add((action, outcome))
        require(observed == expected, "missing-lifecycle-audit-outcomes")
        persisted_hash = state()[1]
        public_audit = json.dumps(audit_payload)
        audit_text = public_audit + json.dumps(audit_rows)
        require(all(secret not in audit_text for secret in secrets + [initial_state[1], persisted_hash]), "audit-secret-leak")
        require(all(action in public_audit for action, _ in expected), "public-audit-missing-actions")
        retained()
        return {"ok": True, "pid": os.getpid(), "http_cases": len(records), "audit_pairs": sorted(observed), "project_id": project}
    finally:
        db.close()


def verify_failures(config: dict) -> dict:
    """ADR-0061 / SM-A03: observe real faults; never backfill producer evidence."""
    root = Path(config["root"]).resolve()
    database = root / "metadata.sqlite3"
    account, project = config["account_id"], config["project_id"]
    records, issues = [], []
    secrets = [config["user_token"], config["actor_token"], config["admin_token"]]

    def request(method, path, token=None, body=None):
        headers = {"Content-Type": "application/json"}
        if token is not None:
            headers["Authorization"] = "Bearer " + token
        req = urllib.request.Request(config["address"] + path, method=method, headers=headers,
                                     data=None if body is None else json.dumps(body).encode())
        try:
            response = urllib.request.urlopen(req, timeout=10)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            payload = json.loads(response.read().decode("utf-8"))
            return response.status, payload

    def setup_request(path, body=None):
        status, payload = request("POST", path, config["admin_token"], body)
        if status != 200:
            raise RuntimeError("failure-fixture-setup-rejected")
        return payload

    def observe_http(family, method, path, token, expected_status):
        started = datetime.now(timezone.utc).isoformat()
        status, payload = request(method, path, token)
        if status != expected_status:
            issues.append(family + ":wrong-failure-status")
        serialized = json.dumps(payload)
        if any(secret in serialized for secret in secrets) or any(
                text in serialized for text in (str(root), "System.", "SqliteException", "StackTrace", "no such table")):
            issues.append(family + ":unsafe-public-envelope")
            # Keep dangerous content out of model-visible summaries and ordinary artifacts.
            payload = {"unsafe_payload_sha256": hashlib.sha256(serialized.encode()).hexdigest()}
        row = {"family": family, "boundary": path, "started_utc": started,
               "status": status, "public_envelope": payload}
        records.append(row)
        return row

    observe_http("unauthenticated", "GET", "/api/session", None, 401)
    observe_http("forbidden", "GET", "/api/admin/users", config["actor_token"], 403)
    observe_http("ownership_mismatch", "GET", f"/api/projects/{project}", config["actor_token"], 404)
    setup_request(f"/api/admin/users/{account}/status", {"disabled": True})
    try:
        time.sleep(5.1)
        observe_http("account_disabled", "GET", "/api/session", config["user_token"], 401)
    finally:
        setup_request(f"/api/admin/users/{account}/status", {"disabled": False})
    replacement = setup_request(f"/api/admin/users/{account}/rotate-token").get("token")
    if not isinstance(replacement, str) or not replacement:
        raise RuntimeError("failure-fixture-rotation-did-not-issue-token")
    secrets.append(replacement)
    time.sleep(5.1)
    observe_http("credential_revoked", "GET", "/api/session", config["user_token"], 401)

    # Induce a storage failure only in the current disposable server's DB.
    # Restore the fixture table even if the HTTP operation fails unexpectedly.
    with sqlite3.connect(database) as db:
        db.execute("ALTER TABLE project_limits RENAME TO s25_fault_project_limits")
    try:
        observe_http("internal_failure", "GET", "/api/admin/users", config["admin_token"], 500)
    finally:
        with sqlite3.connect(database) as db:
            db.execute("ALTER TABLE s25_fault_project_limits RENAME TO project_limits")

    status, _ = request("GET", "/api/admin/project-diagnostic-spool", config["actor_token"])
    if status != 403:
        issues.append("diagnostic-access:not-admin-only")
    status, _ = request("GET", "/api/admin/project-diagnostic-spool", config["admin_token"])
    if status != 200:
        issues.append("diagnostic-access:admin-readback-unavailable")

    # ADR-0061: request failures can precede project identity. Their producer
    # writes operator-only runtime diagnostics, never a project spool entry.
    # Read that file independently and bind each row to the public request ID.
    diagnostic_path = root.parent / "runtime" / "request-failure-diagnostics.jsonl"
    if not diagnostic_path.is_file():
        raise RuntimeError("request-diagnostic-source-unavailable")
    diagnostic_url = config["address"] + "/runtime/request-failure-diagnostics.jsonl"
    probe = urllib.request.Request(diagnostic_url, headers={"Authorization": "Bearer " + config["admin_token"]})
    try:
        exposed = urllib.request.urlopen(probe, timeout=10)
    except urllib.error.HTTPError as error:
        exposed = error
    with exposed:
        exposed_body = exposed.read()
        if exposed.status == 200 or any(secret.encode() in exposed_body for secret in secrets):
            issues.append("request-diagnostic-access:public-readback")
    try:
        diagnostics = [json.loads(line) for line in diagnostic_path.read_text(encoding="utf-8-sig").splitlines()]
    except (OSError, ValueError) as error:
        raise RuntimeError("request-diagnostic-source-invalid") from error
    for row in records:
        family = row["family"]
        payload = row["public_envelope"]
        correlation = payload.get("requestId") or payload.get("correlationId") or payload.get("diagnosticId")
        matching = [item for item in diagnostics if item.get("requestId") == correlation and
                    item.get("failureFamily") == family and item.get("statusCode") == row["status"]]
        row["producer_diagnostic_ids"] = [item["requestId"] for item in matching]
        if not payload.get("error", payload.get("code")):
            issues.append(family + ":missing-public-error-code")
        if len(matching) != 1:
            issues.append(family + ":missing-correlated-typed-diagnostic")
        if any(item.get("message") != "Request rejected or failed." or
               any(secret in json.dumps(item) for secret in secrets) for item in matching):
            issues.append(family + ":unsafe-controlled-diagnostic")

    service_rows = json.loads((root / "service-failure-observations.json").read_text(encoding="utf-8"))
    for row in service_rows:
        family, result = row["family"], row["result"]
        case_db = (root / row["database"]).resolve()
        if not case_db.is_relative_to(root) or not case_db.is_file():
            raise RuntimeError("service-evidence-path-invalid")
        failure_observed = {
            "path_escape": row["exception_type"] == "System.UnauthorizedAccessException",
            "acl_invalid": result is False,
            "quota_exceeded": row["exception_type"] == "System.IO.IOException",
            "restore_conflict": row["exception_type"] == "System.UnauthorizedAccessException",
            "stale_lease": row["exception_type"] == "System.InvalidOperationException",
            "snapshot_corrupt": isinstance(result, dict) and result.get("Status") == 3,
            "schema_unsupported": isinstance(result, dict) and result.get("Status") == 3,
            "restore_interrupted": isinstance(result, dict) and result.get("staged_files", 0) > 0 and result.get("worker_exit_code") != 0,
        }.get(family, False)
        if not failure_observed:
            issues.append(family + ":fault-not-rejected-at-owning-boundary")
        if family == "restore_interrupted" and result.get("recovered_status") not in ("Quarantined", "Failed"):
            issues.append(family + ":restart-left-interrupted-operation-nonterminal")
        with sqlite3.connect(case_db.as_uri() + "?mode=ro", uri=True) as db:
            attempt_key = ("interrupted-request" if family == "restore_interrupted" else
                           "control-request:conflict" if family == "restore_conflict" else row["correlation"])
            attempts = db.execute("SELECT attempt_id,failure_category,error_envelope,status FROM restore_attempts WHERE idempotency_key=?",
                                  (attempt_key,)).fetchall()
            if family == "restore_conflict":
                original = db.execute("SELECT attempt_id,status FROM restore_attempts WHERE idempotency_key='control-request'").fetchone()
                if original != (row["positive_control"]["AttemptId"], "Published"):
                    issues.append(family + ":published-attempt-overwritten")
            diagnostics = db.execute("SELECT diagnostic_id,failure_family,run_id,user_safe_summary FROM project_diagnostic_spool WHERE project_id=?",
                                     (row["project_id"],)).fetchall()
        typed = [item for item in attempts if item[1] == family]
        linked = [item for item in diagnostics if item[1] == family and
                  item[2] in {row["correlation"], *(attempt[0] for attempt in typed)}]
        if not typed and not linked:
            issues.append(family + ":missing-producer-failure-category")
        # Direct path/ACL/quota checks need no artificial Restore Attempt row.
        # Their correlated producer diagnostic can carry the safe public projection.
        envelopes = [item[2] for item in typed if item[2]] + [item[3] for item in linked if item[3]]
        if not envelopes:
            issues.append(family + ":missing-public-envelope")
        if any(any(text in envelope for text in (str(root), "System.", "StackTrace")) for envelope in envelopes):
            issues.append(family + ":unsafe-public-envelope")
        if not linked:
            issues.append(family + ":missing-controlled-diagnostic-link")
        records.append({"family": family, "boundary": "service", "fault_observed": failure_observed,
                        "attempts": attempts, "producer_diagnostic_ids": [item[0] for item in linked]})

    expected = {"unauthenticated", "forbidden", "account_disabled", "credential_revoked", "ownership_mismatch",
                "path_escape", "acl_invalid", "snapshot_corrupt", "schema_unsupported", "quota_exceeded",
                "restore_conflict", "restore_interrupted", "stale_lease", "internal_failure"}
    if {row["family"] for row in records} != expected or len(records) != len(expected):
        raise RuntimeError("failure-family-fixture-coverage-incomplete")
    report = {"ok": not issues, "pid": os.getpid(), "cases": records, "issues": issues}
    (root / "failure-family-validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return {"ok": not issues, "pid": os.getpid(), "family_count": len(records), "issues": issues}


def invoke_s25_boundary(tmp_path: Path, method: str, failure_id: str) -> bool:
    root = Path(__file__).resolve().parents[3]
    results = Path(tempfile.mkdtemp(prefix="s25-trx-", dir=tmp_path))
    name = f"PhaseA.Platform.Tests.PhaseB.Repair.S25BoundaryTests.{method}"
    environment = dict(os.environ)
    environment.pop("S25_INTERRUPTION_ROOT", None)
    # Literal exact selectors are required by the current .NET production-entry guard.
    if method == "O_4367428FF3D3":
        completed = subprocess.run(
            ["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--no-restore", "--filter",
             "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S25BoundaryTests.O_4367428FF3D3",
             "--logger", "trx", "--results-directory", str(results)],
            cwd=root, env=environment, shell=False, check=False, capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=180)
    elif method == "O_A28DE8F2511B":
        completed = subprocess.run(
            ["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--no-restore", "--filter",
             "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S25BoundaryTests.O_A28DE8F2511B",
             "--logger", "trx", "--results-directory", str(results)],
            cwd=root, env=environment, shell=False, check=False, capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=180)
    elif method == "O_E44EA22B607F":
        completed = subprocess.run(
            ["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--no-restore", "--filter",
             "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S25BoundaryTests.O_E44EA22B607F",
             "--logger", "trx", "--results-directory", str(results)],
            cwd=root, env=environment, shell=False, check=False, capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=180)
    else:
        raise RuntimeError("S25 unknown exact boundary selector")
    trx = list(results.glob("*.trx"))
    if len(trx) != 1:
        raise RuntimeError(f"{failure_id}: S25 invocation did not produce one fresh TRX")
    validate_trx(trx[0], name, failure_id, completed.returncode)
    return True


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] in ("verify-admin", "verify-failures"):
        try:
            config = json.load(sys.stdin)
            result = verify_admin(config) if sys.argv[1] == "verify-admin" else verify_failures(config)
        except AssertionError as error:
            print(json.dumps({"ok": False, "pid": os.getpid(), "error": str(error)}))
            raise SystemExit(2)
        except Exception as error:
            print(json.dumps({"ok": False, "pid": os.getpid(), "error": type(error).__name__}))
            raise SystemExit(3)
        print(json.dumps(result))
        raise SystemExit(0 if result["ok"] else 2)
    if len(sys.argv) != 6 or sys.argv[1] != "verify-migration":
        raise SystemExit("Expected verify-migration ROOT NONCE BEFORE_SHA256 AFTER_SHA256")
    try:
        result = verify_migration(Path(sys.argv[2]), *sys.argv[3:])
    except (OSError, ValueError, sqlite3.Error) as error:
        print(json.dumps({"ok": False, "pid": os.getpid(), "error": str(error)}))
        raise SystemExit(2)
    print(json.dumps(result))
