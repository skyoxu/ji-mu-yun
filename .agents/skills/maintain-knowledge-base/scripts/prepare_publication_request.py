"""Create an append-only, main-bound knowledge publication authorization request."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path


def _canonical_hash(value: dict) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _main_commit(root: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "refs/heads/main"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    commit = completed.stdout.strip()
    if completed.returncode or len(commit) != 40:
        raise SystemExit("main commit is unavailable")
    return commit


def _target_plan(root: Path, raw: Path) -> str:
    if raw.is_absolute() or ".." in raw.parts:
        raise SystemExit("--target-plan must be repository-relative")
    target = (root / raw).resolve()
    try:
        relative = target.relative_to(root)
    except ValueError as exc:
        raise SystemExit("--target-plan must stay inside the repository") from exc
    if len(relative.parts) != 2 or relative.parts[0] != "execution-plans":
        raise SystemExit("--target-plan must name one direct execution-plan directory")
    return relative.as_posix()


def _target_exists_at_main(root: Path, main_commit: str, target_plan: str) -> bool:
    completed = subprocess.run(
        ["git", "-C", str(root), "cat-file", "-e", f"{main_commit}:{target_plan}/00-index.md"],
        capture_output=True,
        check=False,
    )
    return completed.returncode == 0


def _source_route(root: Path, raw: Path, target_plan: str) -> dict[str, str]:
    if raw.is_absolute() or ".." in raw.parts:
        raise SystemExit("--source-route must be repository-relative")
    route_path = (root / raw).resolve()
    if route_path.suffix != ".json" or len(route_path.stem) != 64 or any(character not in "0123456789abcdef" for character in route_path.stem):
        raise SystemExit("--source-route must name a hash-addressed JSON route")
    target_root = (root / target_plan / "knowledge-context-routes").resolve()
    try:
        route_path.relative_to(target_root)
    except ValueError as exc:
        raise SystemExit("--source-route must stay inside the target plan knowledge-context-routes directory") from exc
    try:
        route = json.loads(route_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SystemExit("source maintenance route is unavailable") from exc
    route_without_hash = {key: value for key, value in route.items() if key != "route_sha256"}
    expected = {
        "schema_version": "jimuyun.acceptance-knowledge-maintenance-route.v1",
        "status": "blocked",
        "failure_code": "catalog_stale",
        "next_action": "knowledge-maintenance-required",
        "target_plan": target_plan,
        "automatic_publication_allowed": False,
        "requires_explicit_maintainer_confirmation": True,
        "authorizes": [],
        "route_output": raw.as_posix(),
    }
    if any(route.get(key) != value for key, value in expected.items()) or route.get("route_sha256") != _canonical_hash(route_without_hash):
        raise SystemExit("source maintenance route is invalid")
    return {"path": raw.as_posix(), "sha256": route["route_sha256"]}


def _output(root: Path, raw: Path) -> Path:
    if raw.is_absolute() or ".." in raw.parts:
        raise SystemExit("--output must be repository-relative")
    output = (root / raw).resolve()
    allowed = (root / "logs/knowledge-context/publication-requests").resolve()
    try:
        output.relative_to(allowed)
    except ValueError as exc:
        raise SystemExit("--output must stay under logs/knowledge-context/publication-requests") from exc
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--request-id")
    parser.add_argument("--trigger", choices=("operator-requested", "catalog-stale-maintenance"), required=True)
    parser.add_argument("--target-plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-route", type=Path)
    parser.add_argument("--ack-maintainer", action="store_true")
    args = parser.parse_args()
    if not args.ack_maintainer:
        raise SystemExit("explicit maintainer confirmation requires --ack-maintainer")
    root = args.repository_root.resolve()
    request_id = args.request_id or uuid.uuid4().hex
    main_commit = _main_commit(root)
    target_plan = _target_plan(root, args.target_plan)
    if not _target_exists_at_main(root, main_commit, target_plan):
        raise SystemExit("target plan must exist at current main with 00-index.md")
    if args.trigger == "catalog-stale-maintenance" and args.source_route is None:
        raise SystemExit("catalog-stale-maintenance requires --source-route")
    if args.trigger == "operator-requested" and args.source_route is not None:
        raise SystemExit("operator-requested must not declare --source-route")
    source_route = _source_route(root, args.source_route, target_plan) if args.source_route is not None else None
    payload = {
        "schema_version": "jimuyun.knowledge-publication-request.v1",
        "request_id": request_id,
        "caller": "maintain-knowledge-base",
        "trigger": args.trigger,
        "target_plan": target_plan,
        "main_commit": main_commit,
        "automatic": False,
        "maintainer_confirmation": True,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "authorizes": ["knowledge-publication"],
        "source_route": source_route,
    }
    output = _output(root, args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    except FileExistsError as exc:
        raise SystemExit("publication request output is append-only") from exc
    print(json.dumps({"status": "authorized", "request": output.relative_to(root).as_posix(), "authorizes": ["knowledge-publication"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
