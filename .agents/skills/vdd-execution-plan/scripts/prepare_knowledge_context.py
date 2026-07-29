"""Create a VDD-owned, Locator-bound knowledge context before plan freeze."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
def _policy_revision(root: Path) -> str:
    policy = json.loads((root / "knowledge/policies/consumer-policies.v2.json").read_text(encoding="utf-8"))
    revision = policy.get("policy_revision")
    if not isinstance(revision, str) or not revision:
        raise SystemExit("canonical consumer policy revision is invalid")
    return revision


def _render(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _write_staged(path: Path, payload: bytes) -> Path:
    with tempfile.NamedTemporaryFile("wb", delete=False, dir=path.parent, suffix=".tmp") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
        return Path(stream.name)


def _publish_staged(staged: Path, target: Path) -> None:
    try:
        os.link(staged, target)
    except FileExistsError as exc:
        raise SystemExit("knowledge context and freeze receipt are append-only") from exc


def _validator(root: Path):
    module_path = root / "scripts" / "python" / "knowledge_context_validation.py"
    for relative in ("scripts/python/knowledge_context_validation.py", "scripts/python/_knowledge_locator_core.py"):
        current = subprocess.run(
            ["git", "-C", str(root), "show", f"refs/heads/main:{relative}"],
            capture_output=True,
            check=False,
        )
        if current.returncode or (root / relative).read_bytes() != current.stdout:
            raise SystemExit("knowledge context validator must match current main")
    spec = importlib.util.spec_from_file_location("vdd_knowledge_context_validation", module_path)
    if spec is None or spec.loader is None:
        raise SystemExit("knowledge context validator is unavailable")
    module = importlib.util.module_from_spec(spec)
    previous_path = list(sys.path)
    try:
        sys.path.insert(0, str(module_path.parent))
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = previous_path
    return module

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
    validator = _validator(root)
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
        "request_sha256": validator.canonical_hash(request),
        "result_sha256": validator.canonical_hash(result),
    }
    failure_code = validator.validate_context(
        payload,
        repository_root=root,
        verify_catalog=True,
        verify_sources=True,
        expected_consumer="vdd",
    )
    payload["preflight"] = {
        "status": "blocked" if failure_code else "ready",
        "failure_code": failure_code,
        "context_sha256": validator.canonical_hash(payload),
    }
    output = (args.output if args.output.is_absolute() else root / args.output).resolve()
    if output.name != "knowledge-context.v1.json":
        raise SystemExit("VDD knowledge context output must be named knowledge-context.v1.json")
    try:
        relative_output = output.relative_to(root)
    except ValueError as exc:
        raise SystemExit("VDD knowledge context output must stay inside the repository") from exc
    if not relative_output.parts or relative_output.parts[0] != "execution-plans" or len(relative_output.parts) < 3:
        raise SystemExit("VDD knowledge context output must stay inside one execution-plan directory")
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
        "canonical_context_sha256": validator.canonical_hash(payload),
        "request_sha256": payload["request_sha256"],
        "result_sha256": payload["result_sha256"],
        "snapshot": request["snapshot"],
        "source_snapshot_id": result.get("source_snapshot_id"),
        "policy_revision": request["policy_revision"],
        "accepted": accepted_decisions,
        "authorizes": [],
    }
    if failure_code is not None:
        print(json.dumps({"status": "blocked", "failure_code": failure_code, "output": None, "freeze": None, "authorizes": []}))
        return 2
    output.parent.mkdir(parents=True, exist_ok=True)
    freeze_bytes = _render(receipt)
    if output.is_file() and not freeze.exists() and output.read_bytes() == context_bytes:
        staged_freeze = _write_staged(freeze, freeze_bytes)
        try:
            if freeze.exists():
                raise SystemExit("knowledge context and freeze receipt are append-only")
            _publish_staged(staged_freeze, freeze)
        finally:
            staged_freeze.unlink(missing_ok=True)
        print(json.dumps({"status": "ready", "output": str(output), "freeze": str(freeze), "recovered": True, "authorizes": []}))
        return 0
    if output.exists() or freeze.exists():
        raise SystemExit("knowledge context and freeze receipt are append-only")
    staged_context = _write_staged(output, context_bytes)
    staged_freeze = _write_staged(freeze, freeze_bytes)
    try:
        _publish_staged(staged_context, output)
        try:
            _publish_staged(staged_freeze, freeze)
        except Exception:
            if output.is_file() and output.read_bytes() == context_bytes:
                output.unlink()
            raise
    finally:
        staged_context.unlink(missing_ok=True)
        staged_freeze.unlink(missing_ok=True)
    print(json.dumps({"status": payload["preflight"]["status"], "output": str(output), "freeze": str(freeze), "authorizes": []}))
    return 0 if failure_code is None else 2

if __name__ == "__main__":
    raise SystemExit(main())
