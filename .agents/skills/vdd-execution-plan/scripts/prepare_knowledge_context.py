"""Create a VDD-owned, Locator-bound knowledge context before plan freeze."""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
if str(REPOSITORY_ROOT / "scripts" / "python") not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT / "scripts" / "python"))

from knowledge_context_validation import canonical_hash, validate_context  # noqa: E402

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--catalog", type=Path, default=Path("knowledge/catalogs/repository-knowledge-catalog.v1.json"))
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--required-module", action="append", default=[])
    parser.add_argument("--accept", action="append", default=[], help="candidate-path=module[,module]")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.repository_root.resolve()
    catalog_path = args.catalog if args.catalog.is_absolute() else root / args.catalog
    canonical_catalog = root / "knowledge/catalogs/repository-knowledge-catalog.v1.json"
    if catalog_path.resolve() != canonical_catalog.resolve():
        raise SystemExit("--catalog must name the canonical repository knowledge catalog")
    snapshot = json.loads(catalog_path.read_text(encoding="utf-8")).get("source_snapshot", {})
    request = {"schema_version": "jimuyun.knowledge-locator-request.v1", "request_id": args.request_id, "consumer": "vdd", "query": args.query, "snapshot": {"ref": snapshot.get("ref"), "commit": snapshot.get("commit")}, "policy_revision": "knowledge-consumer-policies.v1"}
    completed = subprocess.run(
        [
            sys.executable, "-B", str(root / "scripts/python/knowledge_locator.py"),
            "--repository-root", str(root), "--catalog", str(catalog_path),
        ],
        input=json.dumps(request), text=True, encoding="utf-8", capture_output=True, check=False,
    )
    if completed.returncode:
        raise SystemExit(completed.stderr or "knowledge locator failed")
    result = json.loads(completed.stdout)
    accepted: dict[str, list[str]] = {}
    for value in args.accept:
        path, separator, modules = value.partition("=")
        if not separator or not path or not modules:
            raise SystemExit("--accept must be candidate-path=module[,module]")
        accepted[path] = [item for item in modules.split(",") if item]
    decisions = [{"owner": "adapter", "candidate": {"path": item.get("path"), "source_sha256": item.get("source_sha256")}, "decision": "accepted" if accepted.get(item.get("path")) else "rejected", "satisfies": accepted.get(item.get("path"), []), "rejection_reason": None if accepted.get(item.get("path")) else "not-selected-by-vdd-adapter"} for item in result.get("candidates", [])]
    payload = {
        "schema_version": "jimuyun.vdd-knowledge-context.v1",
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
    )
    payload["preflight"] = {
        "status": "blocked" if failure_code else "ready",
        "failure_code": failure_code,
        "context_sha256": canonical_hash(payload),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": payload["preflight"]["status"], "output": str(args.output), "authorizes": []}))
    return 0 if failure_code is None else 2

if __name__ == "__main__":
    raise SystemExit(main())
