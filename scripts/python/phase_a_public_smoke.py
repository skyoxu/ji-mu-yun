from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
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
    parser.add_argument("--web-preview-url", default=os.environ.get("PHASEA_WEB_PREVIEW_SMOKE_URL", ""))
    parser.add_argument("--web-preview-project-id", default=os.environ.get("PHASEA_WEB_PREVIEW_SMOKE_PROJECT_ID", ""))
    parser.add_argument("--web-preview-preview-id", default=os.environ.get("PHASEA_WEB_PREVIEW_SMOKE_PREVIEW_ID", ""))
    parser.add_argument("--web-preview-package-file", default=os.environ.get("PHASEA_WEB_PREVIEW_SMOKE_PACKAGE_FILE", ""))
    parser.add_argument("--web-preview-package-sha256", default=os.environ.get("PHASEA_WEB_PREVIEW_SMOKE_PACKAGE_SHA256", ""))
    parser.add_argument("--require-web-preview", action="store_true", default=os.environ.get("PHASEA_REQUIRE_WEB_PREVIEW_SMOKE", "") == "1")
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
        if "Game Ren" not in payload and "Phase A Prototype Console" not in payload:
            raise AssertionError("browser console did not include expected title")
        events.append({"event": "browser_console_ok", "status": status})

        status, payload = request_json("GET", f"{base_url}/api/projects", timeout=args.timeout_seconds)
        assert_status(status, 401, payload, "unauthorized project list")
        if payload.get("error") != "authentication_required":
            raise AssertionError(f"expected authentication_required, got {payload}")
        events.append({"event": "unauthorized_rejected", "status": status})

        project_list: list[dict[str, Any]] = []
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
            project_list = [item for item in payload if isinstance(item, dict)]
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

        web_preview = {
            "url": args.web_preview_url,
            "preview_id": args.web_preview_preview_id,
            "package_file": args.web_preview_package_file,
            "package_sha256": args.web_preview_package_sha256,
        }
        if not web_preview["url"] and args.admin_token:
            web_preview = discover_latest_web_preview(
                base_url,
                headers={"Authorization": f"Bearer {args.admin_token}"},
                projects=project_list,
                preferred_project_id=args.web_preview_project_id,
                timeout=args.timeout_seconds,
                events=events,
            )

        if web_preview["url"]:
            web_preview_smoke = repository_root / "scripts" / "python" / "web_preview_playwright_smoke.py"
            smoke_command = [
                sys.executable,
                str(web_preview_smoke),
                web_preview["url"],
                "--timeout-ms",
                str(int(args.timeout_seconds * 1000)),
                "--settle-ms",
                str(int(min(max(args.timeout_seconds, 45), 60) * 1000)),
                "--click-canvas",
                "--mobile-check",
            ]
            if web_preview["preview_id"]:
                smoke_command.extend(["--expect-preview-id", web_preview["preview_id"]])
            if web_preview["package_file"]:
                smoke_command.extend(["--expect-package-file", web_preview["package_file"]])
            if web_preview["package_sha256"]:
                smoke_command.extend(["--expect-package-sha256", web_preview["package_sha256"]])
            result = subprocess.run(
                smoke_command,
                cwd=repository_root,
                text=True,
                capture_output=True,
                timeout=max((args.timeout_seconds * 2.0) + 120.0, 180.0),
                check=False,
            )
            (run_dir / "web-preview-smoke.stdout.txt").write_text(result.stdout, encoding="utf-8", newline="\n")
            (run_dir / "web-preview-smoke.stderr.txt").write_text(result.stderr, encoding="utf-8", newline="\n")
            events.append(
                {
                    "event": "web_preview_smoke",
                    "exit_code": result.returncode,
                    "url": web_preview["url"],
                    "preview_id": web_preview["preview_id"],
                    "package_file": web_preview["package_file"],
                }
            )
            if result.returncode != 0:
                raise AssertionError(f"web preview smoke failed with exit code {result.returncode}")
        else:
            events.append({"event": "web_preview_smoke_skipped", "reason": "web preview URL was not supplied"})
            if args.require_web_preview:
                raise AssertionError("web preview smoke was required but no web preview URL was supplied or discovered")

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


def discover_latest_web_preview(
    base_url: str,
    *,
    headers: dict[str, str],
    projects: list[dict[str, Any]],
    preferred_project_id: str,
    timeout: float,
    events: list[dict[str, Any]],
) -> dict[str, str]:
    ordered_projects = projects
    if preferred_project_id:
        ordered_projects = sorted(
            projects,
            key=lambda item: 0 if str(item.get("projectId") or item.get("project_id") or "") == preferred_project_id else 1,
        )

    for project in ordered_projects:
        project_id = str(project.get("projectId") or project.get("project_id") or "")
        if not project_id:
            continue
        status, payload = request_json(
            "GET",
            f"{base_url}/api/projects/{urllib.parse.quote(project_id)}/packages",
            headers=headers,
            timeout=timeout,
        )
        if status != 200 or not isinstance(payload, dict):
            events.append({"event": "web_preview_discovery_package_list_failed", "project_id": project_id, "status": status})
            continue
        packages = payload.get("packages")
        if not isinstance(packages, list):
            continue
        ready = [
            item
            for item in packages
            if isinstance(item, dict)
            and isinstance(item.get("webPreview"), dict)
            and item["webPreview"].get("status") == "ready"
            and item["webPreview"].get("previewUrl")
        ]
        ready.sort(key=lambda item: str(item.get("webPreview", {}).get("createdUtc") or ""), reverse=True)
        if ready:
            preview = ready[0]["webPreview"]
            url = str(preview["previewUrl"])
            absolute_url = urllib.parse.urljoin(base_url + "/", url.lstrip("/"))
            events.append(
                {
                    "event": "web_preview_discovered",
                    "project_id": project_id,
                    "file_name": ready[0].get("fileName", ""),
                    "url": absolute_url,
                    "mode": preview.get("mode", ""),
                    "fidelity_tier": preview.get("fidelityTier", ""),
                }
            )
            return {
                "url": absolute_url,
                "preview_id": str(preview.get("previewId") or ""),
                "package_file": str(ready[0].get("fileName") or ""),
                "package_sha256": str(ready[0].get("packageSha256") or ready[0].get("package_sha256") or ""),
            }

    events.append({"event": "web_preview_discovery_empty"})
    return {"url": "", "preview_id": "", "package_file": "", "package_sha256": ""}


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
