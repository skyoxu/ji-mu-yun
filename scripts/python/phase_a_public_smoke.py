from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any


LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase A public endpoint smoke checks.")
    parser.add_argument("--base-url", default=os.environ.get("PUBLIC_BASE_URL", ""))
    parser.add_argument("--admin-token", default=os.environ.get("PHASEA_ADMIN_TOKEN", ""))
    parser.add_argument("--repository-root", default=str(Path.cwd()))
    parser.add_argument("--allow-http", action="store_true")
    parser.add_argument("--create-project", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=15.0)
    args = parser.parse_args()

    repository_root = Path(args.repository_root).resolve()
    run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    run_dir = repository_root / "logs" / "ci" / dt.date.today().isoformat() / "phase-a-public-smoke" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    events: list[dict[str, Any]] = []
    exit_code = 1
    base_url = normalize_base_url(args.base_url)
    try:
        validate_public_url(base_url, allow_http=args.allow_http)
        events.append({"event": "base_url_validated", "base_url": base_url})

        status, payload = request_json("GET", f"{base_url}/healthz", timeout=args.timeout_seconds)
        assert_status(status, 200, payload, "healthz")
        if payload.get("status") != "ok":
            raise AssertionError(f"healthz returned unexpected payload: {payload}")
        events.append({"event": "healthz_ok", "status": status})

        status, payload = request_text("GET", f"{base_url}/", timeout=args.timeout_seconds)
        assert_status(status, 200, payload, "browser console")
        if "Phase A Prototype Console" not in payload:
            raise AssertionError("browser console did not include expected title")
        events.append({"event": "browser_console_ok", "status": status})

        status, payload = request_json("GET", f"{base_url}/api/projects", timeout=args.timeout_seconds)
        assert_status(status, 401, payload, "unauthorized project list")
        if payload.get("error") != "authentication_required":
            raise AssertionError(f"expected authentication_required, got {payload}")
        events.append({"event": "unauthorized_rejected", "status": status})

        if args.admin_token:
            headers = {"Authorization": f"Bearer {args.admin_token}"}
            status, payload = request_json(
                "GET",
                f"{base_url}/api/projects",
                headers=headers,
                timeout=args.timeout_seconds,
            )
            assert_status(status, 200, payload, "authorized project list")
            if not isinstance(payload, list):
                raise AssertionError(f"expected project list array, got {payload}")
            events.append({"event": "authorized_project_list_ok", "count": len(payload)})

            if args.create_project:
                project_name = f"public-smoke-{run_id}"
                status, payload = request_json(
                    "POST",
                    f"{base_url}/api/projects",
                    headers=headers,
                    body={"projectName": project_name, "gameName": "Public Smoke Game", "gameTypeSource": "public-smoke"},
                    timeout=args.timeout_seconds,
                )
                assert_status(status, 200, payload, "create public smoke project")
                if not payload.get("succeeded"):
                    raise AssertionError(f"project creation did not succeed: {payload}")
                events.append(
                    {
                        "event": "project_created",
                        "project_id": payload.get("projectId"),
                        "project_name": project_name,
                    }
                )
        else:
            events.append({"event": "authorized_checks_skipped", "reason": "admin token was not supplied"})

        exit_code = 0
        return 0
    except Exception as ex:
        events.append({"event": "public_smoke_failed", "error": str(ex), "type": type(ex).__name__})
        print(f"PHASE_A_PUBLIC_SMOKE status=failed run_dir={run_dir} error={ex}", file=sys.stderr)
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
            print(f"PHASE_A_PUBLIC_SMOKE status=ok run_dir={run_dir}")


def normalize_base_url(value: str) -> str:
    if not value or not value.strip():
        raise ValueError("--base-url or PUBLIC_BASE_URL is required")
    return value.strip().rstrip("/")


def validate_public_url(base_url: str, *, allow_http: bool) -> None:
    parsed = urllib.parse.urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("base URL must be an absolute HTTP/HTTPS URL")
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" and not allow_http and host not in LOCAL_HOSTS:
        raise ValueError("public smoke requires HTTPS for non-localhost endpoints; pass --allow-http only for local checks")


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
