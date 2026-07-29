"""Create a VDD-owned, Locator-bound knowledge context before plan freeze."""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
if str(REPOSITORY_ROOT / "scripts" / "python") not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT / "scripts" / "python"))

from knowledge_context_validation import canonical_hash, validate_context  # noqa: E402


def _policy_revision(root: Path) -> str:
    policy = json.loads((root / "knowledge/policies/consumer-policies.v2.json").read_text(encoding="utf-8"))
    revision = policy.get("policy_revision")
    if not isinstance(revision, str) or not revision:
        raise SystemExit("canonical consumer policy revision is invalid")
    return revision


def _render(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--catalog", type=Path, default=Path("knowledge/catalogs/repository-knowledge-catalog.v2.json"))
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--required-module", action="append", default=[])
    parser.add_argument("--accept", action="append", default=[], help="candidate-path=module[,module]")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.repository_root.resolve()
    catalog_path = args.catalog if args.catalog.is_absolute() else root / args.catalog
    canonical_catalog = root / "knowledge/catalogs/repository-knowledge-catalog.v2.json"
    if catalog_path.resolve() != canonical_catalog.resolve():
        raise SystemExit("--catalog must name the canonical repository knowledge catalog")
    snapshot = json.loads(catalog_path.read_text(encoding="utf-8")).get("source_snapshot", {})
    request = {"schema_version": "jimuyun.knowledge-locator-request.v1", "request_id": args.request_id, "consumer": "vdd", "query": args.query, "snapshot": {"ref": snapshot.get("ref"), "commit": snapshot.get("commit")}, "policy_revision": _policy_revision(root)}
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
    decisions = [{"owner": "adapter", "candidate": {"path": item.get("path"), "source_sha256": item.get("source_sha256")}, "decision": "accepted" if accepted.get(item.get("path")) else "rejected", "satisfies": accepted.get(item.get("path"), []), "rejection_reason": None if accepted.get(item.get("path")) else "insufficient_specificity"} for item in result.get("candidates", [])]
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
        expected_consumer="vdd",
    )
    payload["preflight"] = {
        "status": "blocked" if failure_code else "ready",
        "failure_code": failure_code,
        "context_sha256": canonical_hash(payload),
    }
    output = args.output if args.output.is_absolute() else root / args.output
    if output.name != "knowledge-context.v1.json":
        raise SystemExit("VDD knowledge context output must be named knowledge-context.v1.json")
    freeze = output.with_name("knowledge-context.freeze.v1.json")
    context_bytes = _render(payload)
    accepted_decisions = [
        {
            "path": decision["candidate"]["path"],
            "source_sha256": decision["candidate"]["source_sha256"],
            "satisfies": sorted(decision["satisfies"]),
        }
        for decision in decisions
        if decision["decision"] == "accepted"
    ]
    receipt = {
        "schema_version": "jimuyun.vdd-knowledge-freeze.v1",
        "context_path": output.name,
        "context_sha256": "sha256:" + hashlib.sha256(context_bytes).hexdigest(),
        "canonical_context_sha256": canonical_hash(payload),
        "request_sha256": payload["request_sha256"],
        "result_sha256": payload["result_sha256"],
        "snapshot": request["snapshot"],
        "source_snapshot_id": result.get("source_snapshot_id"),
        "policy_revision": request["policy_revision"],
        "accepted": accepted_decisions,
        "authorizes": [],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open("xb") as stream:
            stream.write(context_bytes)
        try:
            with freeze.open("xb") as stream:
                stream.write(_render(receipt))
        except Exception:
            output.unlink(missing_ok=True)
            raise
    except FileExistsError as exc:
        raise SystemExit("knowledge context and freeze receipt are append-only") from exc
    print(json.dumps({"status": payload["preflight"]["status"], "output": str(output), "freeze": str(freeze), "authorizes": []}))
    return 0 if failure_code is None else 2

if __name__ == "__main__":
    raise SystemExit(main())
