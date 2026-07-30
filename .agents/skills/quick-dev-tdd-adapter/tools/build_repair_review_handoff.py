"""Build the non-authorizing repair request consumed by Acceptance."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any


class HandoffError(ValueError):
    pass


_LINEAGE_ID = re.compile(r"[a-z0-9][a-z0-9._-]{2,63}$")


def _relative_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HandoffError(f"{label} is invalid")
    normalized = value.strip().replace("\\", "/")
    parts = PurePosixPath(normalized).parts
    if (
        normalized.startswith("/")
        or re.match(r"^[A-Za-z]:", normalized)
        or any(part in {"", ".", ".."} for part in parts)
        or any(character in normalized for character in "*?[]")
    ):
        raise HandoffError(f"{label} must be an explicit repository-relative path")
    return PurePosixPath(normalized).as_posix()


def _file_list(root: Path, values: Any, label: str) -> list[str]:
    if not isinstance(values, list) or not values:
        raise HandoffError(f"{label} must be a non-empty list")
    normalized = sorted({_relative_path(value, label) for value in values})
    for relative in normalized:
        candidate = (root / relative).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise HandoffError(f"{label} escapes the repository root") from exc
        if not candidate.is_file():
            raise HandoffError(f"{label} does not exist: {relative}")
    return normalized


def _path_list(values: Any, label: str) -> list[str]:
    if not isinstance(values, list) or not values:
        raise HandoffError(f"{label} must be a non-empty list")
    normalized = [_relative_path(value, label) for value in values]
    if len(normalized) != len(set(normalized)):
        raise HandoffError(f"{label} contains duplicate paths")
    return sorted(normalized)


def _bound_json_path(root: Path, value: Any, digest: Any, label: str) -> str:
    relative = _relative_path(value, label)
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise HandoffError(f"{label} escapes the repository root") from exc
    if not path.is_file() or not isinstance(digest, str) or not re.fullmatch(r"sha256:[a-f0-9]{64}", digest):
        raise HandoffError(f"{label} binding is invalid")
    actual = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != digest:
        raise HandoffError(f"{label} binding is stale")
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HandoffError(f"{label} is unreadable") from exc
    if not isinstance(parsed, dict):
        raise HandoffError(f"{label} is invalid")
    return relative


def build_handoff(value: Any) -> dict[str, Any]:
    required = {
        "schemaVersion", "repositoryRoot", "acceptanceTarget", "lineageFamilyId",
        "semanticRoundsConsumed", "predecessorRun", "baselineManifestPath",
        "baselineManifestHash", "candidateManifestPath", "candidateManifestHash",
        "changedFiles", "directConsumers",
        "targetedTests", "validationRefs", "rootCauseInventories",
        "compositionChecks", "novelP0P1FindingIds", "authorityGraphChanged",
        "highRiskBoundaryChanged", "authorizes",
    }
    if (
        not isinstance(value, dict)
        or set(value) != required
        or value.get("schemaVersion") != "quick-dev-repair-review-handoff-input.v1"
        or value.get("authorizes") != []
    ):
        raise HandoffError("repair review handoff input fields are invalid")
    root_value = value.get("repositoryRoot")
    if not isinstance(root_value, str) or not root_value.strip():
        raise HandoffError("repository root is invalid")
    root = Path(root_value).resolve()
    if not root.is_dir():
        raise HandoffError("repository root does not exist")
    target = _relative_path(value["acceptanceTarget"], "acceptance target")
    if not target.startswith("execution-plans/") or not (root / target).resolve().exists():
        raise HandoffError("acceptance target must exist under execution-plans")
    family = value["lineageFamilyId"]
    rounds = value["semanticRoundsConsumed"]
    if not isinstance(family, str) or _LINEAGE_ID.fullmatch(family) is None:
        raise HandoffError("lineage family is invalid")
    if not isinstance(rounds, int) or isinstance(rounds, bool) or not 0 <= rounds <= 3:
        raise HandoffError("repair handoff requires zero to three consumed semantic rounds")
    predecessor_value = value["predecessorRun"]
    predecessor = (
        _relative_path(predecessor_value, "repair predecessor")
        if predecessor_value is not None
        else None
    )
    if (rounds == 0) != (predecessor is None):
        raise HandoffError("repair predecessor must match the consumed semantic round state")
    baseline_path = _bound_json_path(
        root, value["baselineManifestPath"], value["baselineManifestHash"], "baseline manifest"
    )
    candidate_path = _bound_json_path(
        root, value["candidateManifestPath"], value["candidateManifestHash"], "candidate manifest"
    )
    inventories = value["rootCauseInventories"]
    checks = value["compositionChecks"]
    if not isinstance(inventories, list) or not inventories:
        raise HandoffError("repair handoff requires a root-cause inventory")
    if not isinstance(checks, list) or not checks:
        raise HandoffError("repair handoff requires a composition check")
    novel = value["novelP0P1FindingIds"]
    if not isinstance(novel, list) or len(novel) != len(set(novel)):
        raise HandoffError("novel P0/P1 finding identities are invalid")
    if not all(
        isinstance(value[field], bool)
        for field in ("authorityGraphChanged", "highRiskBoundaryChanged")
    ):
        raise HandoffError("repair escalation flags are invalid")
    return {
        "schemaVersion": "acceptance-repair-completeness-request.v1",
        "repositoryRoot": str(root),
        "acceptanceTarget": target,
        "lineageFamilyId": family,
        "semanticRoundsConsumed": rounds,
        "predecessorRun": predecessor,
        "baselineManifestPath": baseline_path,
        "baselineManifestHash": value["baselineManifestHash"],
        "candidateManifestPath": candidate_path,
        "candidateManifestHash": value["candidateManifestHash"],
        "changedPaths": _path_list(value["changedFiles"], "changed file"),
        "directConsumers": _file_list(root, value["directConsumers"], "direct consumer"),
        "targetedTests": _file_list(root, value["targetedTests"], "targeted test"),
        "validationRefs": _file_list(root, value["validationRefs"], "validation reference"),
        "rootCauseInventories": inventories,
        "compositionChecks": checks,
        "novelP0P1FindingIds": novel,
        "authorityGraphChanged": value["authorityGraphChanged"],
        "highRiskBoundaryChanged": value["highRiskBoundaryChanged"],
        "authorizes": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    result = build_handoff(json.loads(args.request.read_text(encoding="utf-8")))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    try:
        with args.out.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(result, sort_keys=True, indent=2) + "\n")
    except FileExistsError as exc:
        raise HandoffError("repair review handoff output is append-only") from exc
    print(json.dumps({"status": "prepared", "output": str(args.out), "authorizes": []}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
