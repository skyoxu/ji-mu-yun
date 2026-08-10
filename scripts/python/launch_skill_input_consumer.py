#!/usr/bin/env python
"""Validate the typed boundary for a semantic Skill input child.

This helper does not select an LLM, provider, or executable. The owning route
may pass the emitted request to its already-authorized child runner.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from skill_input_consumption import read_json, sha256_bytes, write_json_atomic
from validate_skill_input_consumption import _validate_context, _validate_decision

SC_ROOT = Path(__file__).resolve().parents[2] / "scripts" / "sc"
if str(SC_ROOT) not in sys.path:
    sys.path.insert(0, str(SC_ROOT))
from _llm_backend import run_llm_exec  # noqa: E402


SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
CAPABILITIES = {"read-frozen-snapshot", "write-context-output"}
OPERATIONS = {"create", "repair", "review", "execute", "acceptance"}


class ChildRequestError(ValueError):
    pass


def _relative_root(binding_root: Path, raw: Any, label: str, *, create: bool = False) -> Path:
    if not isinstance(raw, str) or not raw or Path(raw).is_absolute() or raw.startswith(("/", "\\")):
        raise ChildRequestError(f"{label} must be a relative path")
    root = binding_root.resolve()
    resolved = (root / raw).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ChildRequestError(f"{label} escapes binding root") from exc
    if resolved.is_symlink():
        raise ChildRequestError(f"{label} may not be a symlink")
    if create:
        resolved.mkdir(parents=True, exist_ok=True)
    elif not resolved.is_dir():
        raise ChildRequestError(f"{label} is not an existing directory")
    return resolved


def validate_child_request(request: Any, binding_root: Path, expected_contract_hash: str | None = None, expected_execution_identity: str | None = None) -> dict[str, Any]:
    if not isinstance(request, dict):
        raise ChildRequestError("child request must be a JSON object")
    required = {"schema_version", "consumer", "operation", "contract_hash", "source_manifest_hash", "snapshot_root", "output_root", "execution_identity", "allowed_capabilities", "authorizes"}
    if set(request) != required:
        raise ChildRequestError("child request fields do not match schema")
    if request["schema_version"] != "skill-input-child-request.v1" or not isinstance(request["consumer"], str) or not request["consumer"]:
        raise ChildRequestError("child request schema or consumer is invalid")
    if request["operation"] not in OPERATIONS or request["authorizes"] != []:
        raise ChildRequestError("child request operation or authorizes is invalid")
    for key in ("contract_hash", "source_manifest_hash", "execution_identity"):
        if not isinstance(request[key], str) or not SHA256_RE.fullmatch(request[key]):
            raise ChildRequestError(f"child request {key} is invalid")
    if expected_contract_hash and request["contract_hash"] != expected_contract_hash:
        raise ChildRequestError("child request contract hash does not match binding")
    if expected_execution_identity and request["execution_identity"] != expected_execution_identity:
        raise ChildRequestError("child request execution identity does not match binding")
    capabilities = request["allowed_capabilities"]
    if not isinstance(capabilities, list) or not capabilities or len(set(capabilities)) != len(capabilities) or any(item not in CAPABILITIES for item in capabilities):
        raise ChildRequestError("child request capabilities are outside the allowlist")
    snapshot = _relative_root(binding_root, request["snapshot_root"], "snapshot_root")
    output = _relative_root(binding_root, request["output_root"], "output_root", create=True)
    manifest = snapshot / "source-manifest.v1.json"
    if not manifest.is_file() or sha256_bytes(manifest.read_bytes()) != request["source_manifest_hash"]:
        raise ChildRequestError("snapshot manifest is missing or hash-mismatched")
    return {"status": "validated", "consumer": request["consumer"], "operation": request["operation"], "snapshot_root": snapshot.as_posix(), "output_root": output.as_posix(), "execution_identity": request["execution_identity"]}


def run_semantic_child(
    request: Any,
    binding_root: Path,
    *,
    backend: str,
    model: str,
    timeout_sec: int = 300,
    reasoning_effort: str | None = None,
    runner=run_llm_exec,
) -> dict[str, Any]:
    """Run one isolated semantic child and publish only typed sidecars."""
    if not backend or not model:
        raise ChildRequestError("semantic child requires explicit backend and model")
    validated = validate_child_request(request, binding_root)
    snapshot_root = Path(validated["snapshot_root"])
    output_root = Path(validated["output_root"])
    if any(item.is_symlink() for item in snapshot_root.rglob("*")):
        raise ChildRequestError("snapshot contains a symlink")
    manifest_path = snapshot_root / "source-manifest.v1.json"
    manifest_hash = sha256_bytes(manifest_path.read_bytes())
    with tempfile.TemporaryDirectory(prefix="skill-semantic-child-", dir=str(output_root)) as temporary:
        child_root = Path(temporary)
        child_snapshot = child_root / "snapshot"
        shutil.copytree(snapshot_root, child_snapshot)
        prompt = (
            "You are a controlled semantic Skill input consumer. Read only the files under "
            "snapshot/. Do not read parent directories, logs, live sources, or execute writes. "
            "Return one JSON object with exactly two keys: context and decision. "
            "context must be a skill-input-context.v1 object with source_manifest_hash="
            f"{manifest_hash}. decision must be a skill-semantic-decision.v1 object with "
            f"source_manifest_hash={manifest_hash}, execution_identity={request['execution_identity']}, "
            "authorizes=[] and context_artifact_hash set to sha256:0 followed by 64 zeros. "
            "Use bounded, redacted summaries only; if insufficient, return status=insufficient."
        )
        output_path = child_root / "child-output.json"
        configs = [f"model_reasoning_effort={reasoning_effort}"] if reasoning_effort else []
        exit_code, _trace, _command = runner(
            backend=backend,
            root=child_root,
            prompt=prompt,
            output_last_message=output_path,
            timeout_sec=timeout_sec,
            codex_configs=configs,
            codex_model=model,
            codex_json=True,
            codex_sandbox="workspace-write",
        )
        if exit_code != 0 or not output_path.is_file():
            raise ChildRequestError("semantic child failed without a typed output")
        try:
            child_output = json.loads(output_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ChildRequestError("semantic child output is not valid JSON") from exc
        if not isinstance(child_output, dict) or set(child_output) != {"context", "decision"}:
            raise ChildRequestError("semantic child output must contain exactly context and decision")
        context = child_output["context"]
        decision = child_output["decision"]
        if not isinstance(context, dict) or not isinstance(decision, dict):
            raise ChildRequestError("semantic child context or decision is invalid")
        context_path = output_root / "skill-input-context.v1.json"
        write_json_atomic(context_path, context)
        context_bytes = context_path.read_bytes()
        context_hash = sha256_bytes(context_bytes)
        if decision.get("execution_identity") != request["execution_identity"]:
            raise ChildRequestError("semantic decision execution identity does not match child request")
        decision["context_artifact_hash"] = context_hash
        if not isinstance(decision.get("source_statuses"), dict):
            raise ChildRequestError("semantic decision source_statuses is missing")
        _validate_context(context, manifest_hash)
        _validate_decision(decision, manifest_hash, context_hash, decision["source_statuses"])
        decision_path = output_root / "semantic-decision.v1.json"
        write_json_atomic(decision_path, decision)
        return {
            "status": "complete",
            "context_artifact": context_path.as_posix(),
            "semantic_decision": decision_path.as_posix(),
            "source_manifest_hash": manifest_hash,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--binding-root", required=True, type=Path)
    parser.add_argument("--contract-hash")
    parser.add_argument("--execution-identity")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--run-semantic-child", action="store_true")
    parser.add_argument("--backend")
    parser.add_argument("--model")
    parser.add_argument("--reasoning-effort")
    parser.add_argument("--timeout-sec", type=int, default=300)
    args = parser.parse_args()
    try:
        request = read_json(args.request)
        if args.run_semantic_child:
            if not args.backend or not args.model:
                raise ChildRequestError("--run-semantic-child requires --backend and --model")
            result = run_semantic_child(request, args.binding_root.resolve(), backend=args.backend, model=args.model, timeout_sec=args.timeout_sec, reasoning_effort=args.reasoning_effort)
        else:
            result = validate_child_request(request, args.binding_root.resolve(), args.contract_hash, args.execution_identity)
        if args.output:
            write_json_atomic(args.output.resolve(), result)
    except (OSError, ChildRequestError) as exc:
        print(f"skill input child launch validation failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
