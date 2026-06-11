#!/usr/bin/env python3
"""Generate images through the OpenAI SDK against the aiartmirror-compatible API.

This script is intentionally repo-local so prototype art workflows can be reused
without depending on the global Codex imagegen fallback CLI.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.request import urlopen


DEFAULT_BASE_URL = "https://www.aiartmirror.com/v1"
DEFAULT_MODEL = "gpt-image-2"
DEFAULT_SIZE = "1024x1024"
DEFAULT_QUALITY = "high"
DEFAULT_OUTPUT_FORMAT = "png"
DEFAULT_TIMEOUT = 120.0
DEFAULT_API_KEY_ENV = "AIARTMIRROR_API_KEY"
DEFAULT_RESPONSE_FORMAT = "b64_json"
DEFAULT_MODEL_ENV = "AIARTMIRROR_IMAGE_MODEL"
DEFAULT_GROUP_ENV = "AIARTMIRROR_IMAGE_GROUP"


def _read_env_anywhere(name: str) -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    if os.name != "nt":
        return ""
    try:
        import winreg

        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                with winreg.OpenKey(hive, r"Environment") as key:
                    raw, _ = winreg.QueryValueEx(key, name)
                    if raw:
                        return str(raw).strip()
            except FileNotFoundError:
                continue
            except OSError:
                continue
    except Exception:
        return ""
    return ""


def _die(message: str, code: int = 1) -> None:
    print(f"Error: {message}", file=sys.stderr)
    raise SystemExit(code)


def _read_text(path: Path) -> str:
    if not path.is_file():
        _die(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def _load_openai():
    try:
        from openai import OpenAI
    except ImportError as exc:
        _die(
            "Missing dependency: openai. Install it with `uv pip install openai` or `py -3 -m pip install openai`."
        )
        raise exc
    return OpenAI


def _resolve_api_key(args: argparse.Namespace) -> str:
    env_name = str(args.api_key_env or DEFAULT_API_KEY_ENV).strip()
    if args.api_key:
        return args.api_key
    value = _read_env_anywhere(env_name)
    if value:
        return value
    _die(
        f"API key not found. Set environment variable `{env_name}` or pass --api-key only in local shell history-safe contexts."
    )
    return ""


def _resolve_base_url(args: argparse.Namespace) -> str:
    return str(
        args.base_url
        or _read_env_anywhere("AIARTMIRROR_BASE_URL")
        or DEFAULT_BASE_URL
    ).strip()


def _resolve_model(args: argparse.Namespace) -> str:
    return str(
        args.model
        or _read_env_anywhere(DEFAULT_MODEL_ENV)
        or DEFAULT_MODEL
    ).strip()


def _resolve_group(args: argparse.Namespace) -> str:
    return str(
        args.group
        or _read_env_anywhere(DEFAULT_GROUP_ENV)
    ).strip()


def _decode_image_payload(item: Any) -> bytes:
    b64_data = getattr(item, "b64_json", None)
    if not b64_data and isinstance(item, dict):
        b64_data = item.get("b64_json")
    if not b64_data:
        _die("Image response did not contain b64_json payload.")
    return base64.b64decode(b64_data)


def _download_image(url: str) -> bytes:
    with urlopen(url, timeout=120.0) as response:
        return response.read()


def _write_manifest(manifest_path: Path, payload: dict[str, Any]) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate one image through OpenAI SDK against aiartmirror/OpenAI-compatible image API."
    )
    parser.add_argument("--prompt", default="", help="Inline prompt text.")
    parser.add_argument("--prompt-file", default="", help="UTF-8 prompt file path.")
    parser.add_argument("--out", required=True, help="Output image path. With --n > 1, numbered files are written next to this path.")
    parser.add_argument("--manifest-out", default="", help="Optional metadata json output path.")
    parser.add_argument("--reference-image", default="", help="Optional reference image path for image edit mode.")
    parser.add_argument("--n", type=int, default=1, help="Number of images to request, 1-4.")
    parser.add_argument("--model", default="")
    parser.add_argument("--group", default="", help="Optional provider-specific routing group passed via extra_body.")
    parser.add_argument("--size", default=DEFAULT_SIZE)
    parser.add_argument("--quality", default=DEFAULT_QUALITY)
    parser.add_argument("--output-format", default=DEFAULT_OUTPUT_FORMAT, choices=["png", "jpeg", "webp"])
    parser.add_argument("--response-format", default=DEFAULT_RESPONSE_FORMAT, choices=["b64_json", "url"])
    parser.add_argument("--background", default="", choices=["", "transparent", "opaque", "auto"])
    parser.add_argument("--style", default="", choices=["", "vivid", "natural"])
    parser.add_argument("--api-key", default="", help="Optional direct API key. Prefer env vars instead.")
    parser.add_argument("--api-key-env", default=DEFAULT_API_KEY_ENV, help="Environment variable holding the API key.")
    parser.add_argument("--base-url", default="", help="Override API base URL.")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--dry-run", action="store_true", help="Print the resolved request payload without making an API call.")
    return parser


def _resolve_prompt(args: argparse.Namespace) -> str:
    prompt = str(args.prompt or "").strip()
    prompt_file = str(args.prompt_file or "").strip()
    if prompt and prompt_file:
        _die("Use either --prompt or --prompt-file, not both.")
    if prompt_file:
        return _read_text(Path(prompt_file))
    if prompt:
        return prompt
    _die("Missing prompt. Use --prompt or --prompt-file.")
    return ""


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    prompt = _resolve_prompt(args)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    model = _resolve_model(args)
    group = _resolve_group(args)
    count = max(1, min(int(args.n or 1), 4))
    reference_image_path = Path(str(args.reference_image or "").strip()) if str(args.reference_image or "").strip() else None
    if reference_image_path is not None and not reference_image_path.is_file():
        _die(f"Reference image not found: {reference_image_path}")

    request_payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "n": count,
        "size": args.size,
        "quality": args.quality,
        "output_format": args.output_format,
        "response_format": args.response_format,
    }
    if args.background:
        request_payload["background"] = args.background
    if args.style:
        request_payload["style"] = args.style
    extra_body: dict[str, Any] | None = None
    if group:
        extra_body = {"group": group}

    metadata: dict[str, Any] = {
        "base_url": _resolve_base_url(args),
        "request": request_payload,
        "mode": "edit" if reference_image_path else "generation",
        "reference_image_name": reference_image_path.name if reference_image_path else "",
        "extra_body": extra_body or {},
        "out": str(out_path),
        "api_key_env": str(args.api_key_env or DEFAULT_API_KEY_ENV),
        "model_env": DEFAULT_MODEL_ENV,
        "group_env": DEFAULT_GROUP_ENV,
    }

    if args.dry_run:
        print(json.dumps(metadata, ensure_ascii=False, indent=2))
        return 0

    api_key = _resolve_api_key(args)
    OpenAI = _load_openai()
    client = OpenAI(
        base_url=metadata["base_url"],
        api_key=api_key,
        timeout=float(args.timeout),
    )

    if reference_image_path:
        with reference_image_path.open("rb") as image_file:
            response = client.images.edit(
                image=image_file,
                **request_payload,
                extra_body=extra_body,
            )
    else:
        response = client.images.generate(
            **request_payload,
            extra_body=extra_body,
        )
    data = getattr(response, "data", None)
    if not data:
        _die("Image response did not include any data entries.")

    written_paths: list[str] = []
    result_urls: list[str] = []
    for index, item in enumerate(data):
        target_path = out_path if len(data) == 1 else out_path.with_name(f"{out_path.stem}-{index + 1:02d}{out_path.suffix}")
        if args.response_format == "url":
            url = getattr(item, "url", None)
            if not url and isinstance(item, dict):
                url = item.get("url")
            if not url:
                _die("Image response did not contain url payload.")
            image_bytes = _download_image(url)
            result_urls.append(url)
        else:
            image_bytes = _decode_image_payload(item)
        target_path.write_bytes(image_bytes)
        written_paths.append(str(target_path))

    metadata["written_files"] = written_paths
    if result_urls:
        metadata["result_urls"] = result_urls
    metadata["result_count"] = len(data)
    if args.manifest_out:
        _write_manifest(Path(args.manifest_out), metadata)

    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
