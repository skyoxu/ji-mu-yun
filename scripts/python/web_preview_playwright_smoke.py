#!/usr/bin/env python3
"""Run a browser smoke check against a generated Godot web preview URL."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Web preview index.html URL to open.")
    parser.add_argument("--timeout-ms", type=int, default=60000)
    parser.add_argument("--settle-ms", type=int, default=15000)
    parser.add_argument("--expect-text", action="append", default=[], help="Text expected in the loaded preview document.")
    parser.add_argument("--click-canvas", action="store_true", help="Click the center of the Godot canvas and collect post-click text.")
    parser.add_argument("--after-click-expect-text", action="append", default=[], help="Text expected after clicking the canvas.")
    parser.add_argument("--allow-console-errors", action="store_true")
    parser.add_argument("--mobile-check", action="store_true", help="Also load the preview once in a mobile-sized viewport.")
    parser.add_argument("--no-node-fallback", action="store_true", help="Do not fall back to the local Node Playwright smoke runner.")
    parser.add_argument("--expect-preview-id", default="", help="Expected preview id from the package API or generation result.")
    parser.add_argument("--expect-package-file", default="", help="Expected package file recorded by preview-contract.json.")
    parser.add_argument("--expect-package-sha256", default="", help="Expected package SHA-256 recorded by preview-contract.json.")
    return parser.parse_args()


def print_dependency_failure(error: BaseException) -> int:
    output = {
        "ok": False,
        "checks": {
            "playwrightAvailable": False,
        },
        "error": {
            "type": type(error).__name__,
            "message": str(error),
        },
        "hint": (
            "Install or repair Playwright for this Python environment with: "
            "py -3 -m pip install playwright && py -3 -m playwright install chromium"
        ),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2), file=sys.stderr)
    return 2


def run_node_fallback(args: argparse.Namespace, error: BaseException) -> int | None:
    if args.no_node_fallback:
        return None
    repo_root = Path(__file__).resolve().parents[2]
    fallback_script = repo_root / "scripts" / "python" / "web_preview_node_smoke.js"
    if not fallback_script.exists():
        return None
    fallback_env = ensure_node_playwright(repo_root)

    command = [
        "node",
        str(fallback_script),
        args.url,
        "--timeout-ms",
        str(args.timeout_ms),
        f"--settle-ms={args.settle_ms}",
    ]
    if args.click_canvas:
        command.append("--click-canvas")
    if args.allow_console_errors:
        command.append("--allow-console-errors")
    if args.mobile_check:
        command.append("--mobile-check")
    for text in args.expect_text:
        command.extend(["--expect-text", text])
    for text in args.after_click_expect_text:
        command.extend(["--after-click-expect-text", text])
    if args.expect_preview_id:
        command.extend(["--expect-preview-id", args.expect_preview_id])
    if args.expect_package_file:
        command.extend(["--expect-package-file", args.expect_package_file])
    if args.expect_package_sha256:
        command.extend(["--expect-package-sha256", args.expect_package_sha256])
    if "error" in fallback_env:
        payload = {
            "ok": False,
            "checks": {"nodeFallbackDependencyReady": False},
            "nodeFallbackDependencyError": fallback_env["error"],
            "pythonPlaywrightError": {
                "type": type(error).__name__,
                "message": str(error),
            },
            "usedNodeFallback": True,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 2

    process = subprocess.run(
        command,
        cwd=str(repo_root),
        env=fallback_env["env"],
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    try:
        payload = json.loads(process.stdout)
    except json.JSONDecodeError:
        payload = {
            "ok": False,
            "checks": {"nodeFallback": False},
            "stdout": process.stdout,
            "stderr": process.stderr,
        }
    payload["pythonPlaywrightError"] = {
        "type": type(error).__name__,
        "message": str(error),
    }
    payload["usedNodeFallback"] = True
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return process.returncode


def ensure_node_playwright(repo_root: Path) -> dict[str, Any]:
    install_root = repo_root / "logs" / "phase-a-innernet" / "runtime" / "node-playwright-smoke"
    node_modules = install_root / "node_modules"
    env = dict(os.environ)
    env["NODE_PATH"] = str(node_modules)

    if node_playwright_available(repo_root, env):
        return {"env": env}

    install_root.mkdir(parents=True, exist_ok=True)
    package_name = os.environ.get("PHASEA_NODE_PLAYWRIGHT_PACKAGE", "playwright@1.60.0")
    process = subprocess.run(
        ["npm", "install", "--prefix", str(install_root), package_name],
        cwd=str(repo_root),
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=180,
        check=False,
    )
    if process.returncode != 0:
        return {
            "error": {
                "type": "npm_install_failed",
                "package": package_name,
                "exitCode": process.returncode,
                "stdoutTail": process.stdout[-4000:],
                "stderrTail": process.stderr[-4000:],
            }
        }
    if not node_playwright_available(repo_root, env):
        return {
            "error": {
                "type": "playwright_unavailable_after_install",
                "package": package_name,
            }
        }
    return {"env": env}


def node_playwright_available(repo_root: Path, env: dict[str, str]) -> bool:
    process = subprocess.run(
        ["node", "-e", "require.resolve('playwright')"],
        cwd=str(repo_root),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return process.returncode == 0


def print_smoke_failure(error: BaseException) -> int:
    output = {
        "ok": False,
        "checks": {
            "playwrightAvailable": True,
            "pageLoaded": False,
        },
        "error": {
            "type": type(error).__name__,
            "message": str(error),
        },
    }
    print(json.dumps(output, ensure_ascii=False, indent=2), file=sys.stderr)
    return 1


def collect_page_check(playwright: Any, args: argparse.Namespace, viewport: dict[str, int], label: str) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    assets: list[dict[str, Any]] = []
    console_messages: list[dict[str, str]] = []

    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport=viewport)
    page.on("console", lambda msg: console_messages.append({"type": msg.type, "text": msg.text}))
    page.on("pageerror", lambda err: failures.append({"type": "pageerror", "text": str(err)}))
    page.on(
        "requestfailed",
        lambda req: failures.append(
            {
                "type": "requestfailed",
                "url": req.url,
                "failure": req.failure or "",
            }
        ),
    )

    def on_response(response: Any) -> None:
        url = response.url
        if any(token in url for token in ("index.js", "index.wasm", "index.pck", "worker", "worklet")):
            headers = response.headers
            assets.append(
                {
                    "url": url,
                    "status": response.status,
                    "contentType": headers.get("content-type", ""),
                    "cache": headers.get("cache-control", ""),
                }
            )

    page.on("response", on_response)
    page.goto(args.url, wait_until="domcontentloaded", timeout=args.timeout_ms)
    page.wait_for_selector("canvas", timeout=args.timeout_ms)
    page.wait_for_timeout(args.settle_ms)
    contract = page.evaluate(
        """async () => {
            const url = new URL('preview-contract.json', window.location.href).href;
            try {
                const response = await fetch(url, { cache: 'no-store' });
                const contentType = response.headers.get('content-type') || '';
                const text = await response.text();
                let body = null;
                try { body = text ? JSON.parse(text) : null; } catch {}
                return { url, status: response.status, contentType, body, text };
            } catch (error) {
                return { url, status: 0, contentType: '', body: null, text: String(error) };
            }
        }"""
    )
    try:
        page.wait_for_function(
            """({ width, height }) => {
                const canvas = document.querySelector('canvas');
                if (!canvas) return false;
                const loading = document.querySelector('#phasea-loading-estimate');
                const loadingHidden = !loading ||
                    loading.style.display === 'none' ||
                    loading.style.visibility === 'hidden' ||
                    !loading.textContent ||
                    loading.offsetParent === null;
                const canvasSized = canvas.clientWidth >= Math.floor(width * 0.75) &&
                    canvas.clientHeight >= Math.floor(height * 0.5);
                return loadingHidden && canvasSized;
            }""",
            viewport,
            timeout=args.timeout_ms,
        )
    except Exception:
        pass
    before_click_text = page.locator("body").inner_text(timeout=args.timeout_ms)
    after_click_text = before_click_text
    if args.click_canvas:
        canvas_box = page.locator("canvas").bounding_box(timeout=args.timeout_ms)
        if canvas_box:
            page.mouse.click(canvas_box["x"] + canvas_box["width"] / 2, canvas_box["y"] + canvas_box["height"] / 2)
            page.wait_for_timeout(1000)
            after_click_text = page.locator("body").inner_text(timeout=args.timeout_ms)
    result = page.evaluate(
        """() => {
            const canvas = document.querySelector('canvas');
            const gl = canvas && (
                canvas.getContext('webgl') ||
                canvas.getContext('experimental-webgl') ||
                canvas.getContext('webgl2')
            );
            let canvasDataUrlLength = 0;
            try {
                canvasDataUrlLength = canvas ? canvas.toDataURL('image/png').length : 0;
            } catch {
                canvasDataUrlLength = -1;
            }
            const loading = document.querySelector('#phasea-loading-estimate');
            let localStorageReadable = true;
            try { window.localStorage.getItem('phaseAAccessToken'); } catch { localStorageReadable = false; }
            return {
                title: document.title,
                canvas: canvas ? {
                    width: canvas.width,
                    height: canvas.height,
                    clientWidth: canvas.clientWidth,
                    clientHeight: canvas.clientHeight,
                    dataUrlLength: canvasDataUrlLength
                } : null,
                webgl: !!gl,
                loadingText: loading?.textContent || '',
                loadingDisplay: loading?.style.display || '',
                loadingVisible: !!loading && loading.style.display !== 'none' && loading.offsetParent !== null,
                localStorageReadable,
                bodyText: document.body?.innerText || ''
            };
        }"""
    )
    result["bodyTextBeforeClick"] = before_click_text
    result["bodyTextAfterClick"] = after_click_text
    browser.close()

    required_assets = ("index.js", "index.wasm", "index.pck")
    missing_assets = [
        name
        for name in required_assets
        if not any(name in item["url"] and item["status"] == 200 for item in assets)
    ]
    canvas = result.get("canvas") or {}
    contract_body = contract.get("body") or {}
    url_preview_id = preview_id_from_url(args.url)
    checks = {
        "hasCanvas": bool(result.get("canvas")),
        "canvasHasClientSize": canvas.get("clientWidth", 0) > 0 and canvas.get("clientHeight", 0) > 0,
        "canvasHasLoadedSize": canvas.get("clientWidth", 0) >= int(viewport["width"] * 0.75)
        and canvas.get("clientHeight", 0) >= int(viewport["height"] * 0.5),
        "canvasSnapshotReadable": canvas.get("dataUrlLength", 0) > 100,
        "hasWebGl": bool(result.get("webgl")),
        "loadingComplete": not result.get("loadingVisible"),
        "noRequestFailures": len(failures) == 0,
        "requiredAssetsLoaded": len(missing_assets) == 0,
        "localStorageBlocked": result.get("localStorageReadable") is False,
        "expectedTextPresent": all(text in result.get("bodyText", "") for text in args.expect_text),
        "afterClickExpectedTextPresent": all(text in result.get("bodyTextAfterClick", "") for text in args.after_click_expect_text),
        "noConsoleErrors": args.allow_console_errors or not any(item["type"] == "error" for item in console_messages),
        "previewContractLoaded": contract.get("status") == 200,
        "previewContractSchema": contract_body.get("schema_version") == "phasea-web-preview-contract-v1",
        "previewContractPackagePresent": bool(contract_body.get("package_file")),
        "previewContractPackageShaPresent": is_sha256(contract_body.get("package_sha256")),
        "previewContractModePresent": bool(contract_body.get("mode")),
        "previewContractGuideCoherent": preview_contract_guide_coherent(contract_body),
        "previewContractPreviewIdMatchesUrl": bool(url_preview_id) and contract_body.get("preview_id") == url_preview_id,
        "previewContractExpectedPreviewId": not args.expect_preview_id or contract_body.get("preview_id") == args.expect_preview_id,
        "previewContractExpectedPackageFile": not args.expect_package_file or contract_body.get("package_file") == args.expect_package_file,
        "previewContractExpectedPackageSha256": not args.expect_package_sha256 or contract_body.get("package_sha256") == args.expect_package_sha256.lower(),
    }
    return {
        "label": label,
        "ok": all(checks.values()),
        "checks": checks,
        "missingAssets": missing_assets,
        "result": result,
        "previewContract": contract,
        "assets": assets,
        "failures": failures,
        "consoleTail": console_messages[-20:],
    }


def is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdefABCDEF" for char in value)


def preview_id_from_url(url: str) -> str:
    parts = [unquote(part) for part in urlparse(url).path.split("/") if part]
    for index, part in enumerate(parts):
        if part == "web-previews" and index + 1 < len(parts):
            return parts[index + 1]
    return ""


def preview_contract_guide_coherent(contract: dict[str, Any]) -> bool:
    game_type_id = contract.get("game_type_id")
    guide = contract.get("game_type_guide")
    if not guide:
        return True
    return (
        isinstance(game_type_id, str)
        and bool(game_type_id)
        and isinstance(guide, str)
        and guide.startswith("docs/game-type-guides/")
        and guide.endswith(".md")
    )


def main() -> int:
    args = parse_args()
    try:
        from playwright.sync_api import sync_playwright
    except Exception as error:
        fallback = run_node_fallback(args, error)
        if fallback is not None:
            return fallback
        return print_dependency_failure(error)

    try:
        with sync_playwright() as playwright:
            checks = [collect_page_check(playwright, args, {"width": 1280, "height": 720}, "desktop")]
            if args.mobile_check:
                checks.append(collect_page_check(playwright, args, {"width": 390, "height": 844}, "mobile"))
    except Exception as error:
        return print_smoke_failure(error)

    output = {
        "ok": all(item["ok"] for item in checks),
        "checks": checks,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
