"""ADR-0041/ADR-0062: bind reviewer policy before invoking native architecture."""
import argparse
import json
from pathlib import Path, PurePosixPath
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from scripts.toolchain.bmad_native import NativeError, contained, invocation, new_workspace, verify


def prepare(root, run, inputs, intent="create", altitude=None, purpose=None):
    verify(root)
    if intent not in {"create", "update", "validate"}:
        raise ValueError("INVALID_INTENT")
    if altitude not in {None, "initiative", "feature", "epic"} or purpose not in {None, "build-substrate", "discussion"}:
        raise ValueError("INVALID_NATIVE_OPTION")
    root = Path(root).absolute()
    sources = [(relative, contained(root, relative)) for relative in inputs]
    if not sources or any(not path.is_file() for _, path in sources):
        raise ValueError("INPUT_REQUIRED")
    if any(relative.startswith((".agents/", "_bmad/")) for relative, _ in sources):
        raise ValueError("INPUT_RESOURCE_COLLISION")
    existing = [relative for relative, _ in sources if Path(relative).name == "ARCHITECTURE-SPINE.md"]
    if intent != "create" and len(existing) != 1:
        raise ValueError("EXISTING_SPINE_REQUIRED")
    if intent == "update" and (str(PurePosixPath(existing[0]).parent / ".memlog.md") not in inputs):
        raise ValueError("EXISTING_MEMLOG_REQUIRED")
    folder, native = new_workspace(root, run)
    for relative, path in sources:
        # Never let caller-supplied artifacts replace native resources/config.
        if relative.startswith((".agents/", "_bmad/")):
            raise ValueError("INPUT_RESOURCE_COLLISION")
        target = contained(native, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
    from scripts.toolchain.knowledge_query import adapter
    prepared_query = adapter.prepare_consumption({
        "stage": "architecture", "operation": "create" if intent == "create" else "update",
        "task_id": "architecture:" + "|".join(inputs), "inputs": inputs,
        "scope": inputs, "query": "Accepted ADR owner interface current implementation " + " ".join(inputs),
        "record_path": run + "/execution-record.md"}, root)
    if prepared_query["status"] == "blocked":
        raise ValueError("PLANNING_QUERY_BLOCKED:" + prepared_query["query_result"]["reason_code"])
    for row in prepared_query.get("query_result", {}).get("read_set", []):
        relative = row["path"]
        if relative.startswith((".agents/", "_bmad/")):
            continue  # Native resources must never be replaced by source context.
        target = contained(native, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(contained(root, relative).read_bytes())
    policy = Path(__file__).resolve().parents[1] / "references/reviewer-lifecycle.md"
    workspace = native / "_bmad-output/architecture" if intent == "create" else contained(native, existing[0]).parent
    instructions = policy.read_text(encoding="utf-8") + (
        f"\nForwarded native invocation: headless=true; intent={intent}.\n"
        + (f"altitude={altitude}\n" if altitude else "Infer altitude from inputs using the native method.\n")
        + (f"purpose={purpose}\n" if purpose else "Infer purpose from inputs using the native method.\n")
        + f"doc_workspace={workspace.as_posix()}\n"
        "Inputs (relative to the isolated project): " + json.dumps(inputs, ensure_ascii=False) + ".\n"
        "Read those inputs. Preserve approved repository decisions; do not expand scope.\n"
        "The original repository is read-only in this run. The native workflow owns the spine and memlog.\n"
        "Load native references from the verified skill-root below. The lifecycle policy above is effective\n"
        "from invocation, including every delegated reviewer. Do not invoke Bootstrap or Acceptance.\n"
    )
    instructions += adapter.consumption_instructions(prepared_query)
    prompt = invocation(root, folder, native, "bmad-architecture", instructions)
    return {"ok": True, "invocation": prompt.relative_to(root).as_posix(), "doc_workspace": workspace.relative_to(root).as_posix(), "authorizes": []}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "verify"])
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--input", action="append", default=[])
    parser.add_argument("--intent", default="create", choices=["create", "update", "validate"])
    parser.add_argument("--altitude", choices=["initiative", "feature", "epic"])
    parser.add_argument("--purpose", choices=["build-substrate", "discussion"])
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            result = prepare(args.repo_root, args.run, args.input, args.intent, args.altitude, args.purpose)
        else:
            if not args.run.startswith("logs/bmad-wrappers/"):
                raise ValueError("RUN_OUTSIDE_LOGS")
            verify(args.repo_root)
            verify(contained(args.repo_root, args.run + "/native"))
            result = {"ok": True, "native_trees_unchanged": True, "authorizes": []}
        print(json.dumps(result, ensure_ascii=True))
        return 0
    except NativeError as exc:
        print(json.dumps(exc.result()))
        return 2
    except (ValueError, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc) if isinstance(exc, ValueError) else "FILESYSTEM_ERROR", "authorizes": []}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
