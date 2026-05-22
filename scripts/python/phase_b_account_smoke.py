from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase B account and LLM API smoke checks.")
    parser.add_argument("--base-url", default=os.environ.get("PHASEA_BASE_URL", "http://127.0.0.1:18080"))
    parser.add_argument("--admin-token", default=os.environ.get("PHASEA_ADMIN_TOKEN", ""))
    parser.add_argument("--repository-root", default=str(Path.cwd()))
    parser.add_argument("--timeout-seconds", type=float, default=15.0)
    args = parser.parse_args()

    repository_root = Path(args.repository_root).resolve()
    run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    run_dir = repository_root / "logs" / "ci" / dt.date.today().isoformat() / "phase-b-account-smoke" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    events: list[dict[str, Any]] = []
    exit_code = 1
    base_url = args.base_url.strip().rstrip("/")
    try:
        if not base_url:
            raise ValueError("base URL is required")

        status, payload = request_json("GET", f"{base_url}/healthz", timeout=args.timeout_seconds)
        assert_status(status, 200, payload, "healthz")
        events.append({"event": "healthz_ok", "status": status})

        for path in [
            "/api/session",
            "/api/account/llm-binding",
            "/api/account/llm-usage",
            "/api/admin/users",
            "/api/admin/llm-usage",
            "/api/admin/llm-runs",
            "/api/admin/account-audit",
            "/api/admin/account-audit.csv",
        ]:
            status, payload = request_json("GET", f"{base_url}{path}", timeout=args.timeout_seconds)
            assert_status(status, 401, payload, f"unauthorized {path}")
            events.append({"event": "unauthorized_rejected", "path": path, "status": status})

        if args.admin_token:
            run_authorized_checks(base_url, args.admin_token, args.timeout_seconds, events)
        else:
            events.append({"event": "authorized_checks_skipped", "reason": "admin token was not supplied"})

        exit_code = 0
        return 0
    except Exception as ex:
        events.append({"event": "phase_b_account_smoke_failed", "error": str(ex), "type": type(ex).__name__})
        print(f"PHASE_B_ACCOUNT_SMOKE status=failed run_dir={run_dir} error={ex}", file=sys.stderr)
        return 1
    finally:
        summary = {
            "status": "ok" if exit_code == 0 else "failed",
            "run_id": run_id,
            "base_url": base_url,
            "events": events,
        }
        (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8", newline="\n")
        if exit_code == 0:
            print(f"PHASE_B_ACCOUNT_SMOKE status=ok run_dir={run_dir}")


def run_authorized_checks(base_url: str, admin_token: str, timeout: float, events: list[dict[str, Any]]) -> None:
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    status, session = request_json("GET", f"{base_url}/api/session", headers=admin_headers, timeout=timeout)
    assert_status(status, 200, session, "admin session")
    if session.get("role") != "admin":
        raise AssertionError(f"expected admin role, got {session}")
    events.append({"event": "admin_session_ok", "account_id": session.get("accountId")})

    username = f"phase-b-smoke-{uuid.uuid4().hex[:8]}"
    status, created = request_json(
        "POST",
        f"{base_url}/api/admin/users",
        headers=admin_headers,
        body={"username": username, "projectLimit": 1},
        timeout=timeout,
    )
    assert_status(status, 200, created, "create smoke user")
    user_token = created.get("token")
    account_id = created.get("accountId")
    if not user_token or not account_id:
        raise AssertionError(f"created user payload did not include token/accountId: {created}")
    events.append({"event": "user_created", "account_id": account_id, "username": username})

    user_headers = {"Authorization": f"Bearer {user_token}"}
    status, user_session = request_json("GET", f"{base_url}/api/session", headers=user_headers, timeout=timeout)
    assert_status(status, 200, user_session, "user session")
    if user_session.get("role") != "user" or user_session.get("accountId") != account_id:
        raise AssertionError(f"unexpected user session: {user_session}")
    events.append({"event": "user_session_ok", "account_id": account_id})

    status, usage = request_json("GET", f"{base_url}/api/account/llm-usage", headers=user_headers, timeout=timeout)
    assert_status(status, 200, usage, "user llm usage")
    if "estimatedCostCny" not in usage or "recentRuns" not in usage:
        raise AssertionError(f"unexpected account llm usage payload: {usage}")
    events.append({"event": "user_llm_usage_ok", "call_count": usage.get("callCount")})

    status, payload = request_json("GET", f"{base_url}/api/admin/users", headers=user_headers, timeout=timeout)
    assert_status(status, 403, payload, "user cannot list admin users")
    events.append({"event": "user_admin_route_forbidden", "status": status})

    status, admin_usage = request_json("GET", f"{base_url}/api/admin/llm-usage", headers=admin_headers, timeout=timeout)
    assert_status(status, 200, admin_usage, "admin llm usage")
    if "accounts" not in admin_usage:
        raise AssertionError(f"unexpected admin llm usage payload: {admin_usage}")
    events.append({"event": "admin_llm_usage_ok", "account_count": admin_usage.get("accountCount")})

    status, admin_runs = request_json("GET", f"{base_url}/api/admin/llm-runs", headers=admin_headers, timeout=timeout)
    assert_status(status, 200, admin_runs, "admin llm runs")
    if "runs" not in admin_runs:
        raise AssertionError(f"unexpected admin llm runs payload: {admin_runs}")
    events.append({"event": "admin_llm_runs_ok", "count": admin_runs.get("count")})

    status, account_audit = request_json(
        "GET",
        f"{base_url}/api/admin/account-audit?limit=20&action=user_created",
        headers=admin_headers,
        timeout=timeout,
    )
    assert_status(status, 200, account_audit, "admin account audit")
    if "events" not in account_audit:
        raise AssertionError(f"unexpected account audit payload: {account_audit}")
    events.append({"event": "admin_account_audit_ok", "count": len(account_audit.get("events") or [])})

    status, audit_csv = request_text(
        "GET",
        f"{base_url}/api/admin/account-audit.csv?limit=20&action=user_created",
        headers=admin_headers,
        timeout=timeout,
    )
    if status != 200 or "event_id,actor_account_id,action,target_account_id,created_utc,metadata_json" not in audit_csv:
        raise AssertionError(f"unexpected account audit csv response: status={status}, body={audit_csv[:200]}")
    if "phasea_" in audit_csv.lower() or "token_hash" in audit_csv.lower():
        raise AssertionError("account audit csv leaked token material")
    events.append({"event": "admin_account_audit_csv_ok"})


def request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    timeout: float,
) -> tuple[int, Any]:
    data = None
    request_headers = dict(headers or {})
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        request_headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as ex:
        raw = ex.read().decode("utf-8")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw}
        return ex.code, payload


def request_text(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float,
) -> tuple[int, str]:
    request = urllib.request.Request(url, headers=dict(headers or {}), method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as ex:
        return ex.code, ex.read().decode("utf-8")


def assert_status(status: int, expected: int, payload: Any, label: str) -> None:
    if status != expected:
        raise AssertionError(f"{label}: expected HTTP {expected}, got {status}, payload={payload}")


if __name__ == "__main__":
    raise SystemExit(main())
