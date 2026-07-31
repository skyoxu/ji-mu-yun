"""Create a publication-bound Refactor Acceptance knowledge context."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
PYTHON_ROOT = REPOSITORY_ROOT / "scripts" / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from knowledge_context_validation import canonical_hash, validate_context  # noqa: E402


def _accepted(values: list[str]) -> dict[str, list[str]]:
    accepted: dict[str, list[str]] = {}
    for value in values:
        path, separator, modules = value.partition("=")
        selected = [item for item in modules.split(",") if item]
        if not separator or not path or not selected:
            raise ValueError("--accept must be candidate-path=module[,module]")
        accepted[path] = selected
    return accepted


def _policy_revision(root: Path) -> str:
    policy = json.loads((root / "knowledge/policies/consumer-policies.v2.json").read_text(encoding="utf-8"))
    revision = policy.get("policy_revision")
    if not isinstance(revision, str) or not revision:
        raise SystemExit("canonical consumer policy revision is invalid")
    return revision


def _output_path(root: Path, raw: Path) -> Path:
    if raw.is_absolute() or ".." in raw.parts:
        raise ValueError("knowledge context output must be repository-relative")
    output = (root / raw).resolve()
    execution_root = (root / "execution-plans").resolve()
    try:
        output.relative_to(execution_root)
    except ValueError as exc:
        raise ValueError("knowledge context output must stay under execution-plans") from exc
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--required-module", action="append", default=[])
    parser.add_argument("--accept", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.repository_root.resolve()
    catalog_path = root / "knowledge" / "catalogs" / "repository-knowledge-catalog.v2.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    snapshot = catalog.get("source_snapshot", {})
    request = {
        "schema_version": "jimuyun.knowledge-locator-request.v1",
        "request_id": args.request_id,
        "consumer": "refactor-acceptance",
        "query": args.query,
        "snapshot": {"ref": snapshot.get("ref"), "commit": snapshot.get("commit")},
        "policy_revision": _policy_revision(root),
    }
    completed = subprocess.run(
        [sys.executable, "-B", str(root / "scripts" / "python" / "knowledge_locator.py"), "--repository-root", str(root)],
        input=json.dumps(request, ensure_ascii=False),
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        raise SystemExit(completed.stderr or "knowledge locator failed")
    result = json.loads(completed.stdout)
    accepted = _accepted(args.accept)
    returned_paths = {item.get("path") for item in result.get("candidates", []) if isinstance(item, dict)}
    if set(accepted) - returned_paths:
        raise SystemExit("--accept names a path absent from the Locator result")
    decisions = [
        {
            "owner": "adapter",
            "candidate": {"path": item.get("path"), "source_sha256": item.get("source_sha256")},
            "decision": "accepted" if item.get("path") in accepted else "rejected",
            "satisfies": accepted.get(item.get("path"), []),
            "rejection_reason": None if item.get("path") in accepted else "insufficient_specificity",
        }
        for item in result.get("candidates", [])
        if isinstance(item, dict)
    ]
    payload = {
        "schema_version": "jimuyun.knowledge-consumer-context.v1",
        "consumer": "refactor-acceptance",
        "locator_request": request,
        "locator_result": result,
        "required_modules": args.required_module,
        "decisions": decisions,
        "request_sha256": canonical_hash(request),
        "result_sha256": canonical_hash(result),
    }
    failure_code = validate_context(
        payload,
        repository_root=root,
        verify_catalog=True,
        verify_sources=True,
        expected_consumer="refactor-acceptance",
        require_selection=True,
    )
    payload["preflight"] = {
        "status": "blocked" if failure_code else "ready",
        "failure_code": failure_code,
        "context_sha256": canonical_hash(payload),
    }
    try:
        output = _output_path(root, args.output)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    except FileExistsError as exc:
        raise SystemExit("knowledge context output is append-only") from exc
    print(json.dumps({"status": payload["preflight"]["status"], "output": str(output), "authorizes": []}, sort_keys=True))
    return 0 if failure_code is None else 2


if __name__ == "__main__":
    raise SystemExit(main())
