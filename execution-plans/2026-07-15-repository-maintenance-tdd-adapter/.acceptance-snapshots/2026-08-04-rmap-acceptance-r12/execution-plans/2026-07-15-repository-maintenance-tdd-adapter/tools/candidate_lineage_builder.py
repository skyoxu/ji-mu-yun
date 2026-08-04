from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from candidate_lineage_guards import value_hash
from validate_all import current_candidate_identity


def validate_baseline_bridge(value: dict[str, Any]) -> None:
    """Reject implicit or unhashed baseline transitions before lineage assembly."""
    required = {"schema_version", "from_slice_id", "to_slice_id", "from_baseline_hash", "to_baseline_hash", "transition_files", "transition_hash", "authorizes"}
    if (
        not isinstance(value, dict)
        or set(value) != required
        or value.get("schema_version") != "jimuyun.candidate-baseline-bridge.v1"
        or value.get("authorizes") != []
        or not isinstance(value.get("transition_files"), list)
        or not isinstance(value.get("from_slice_id"), str)
        or not isinstance(value.get("to_slice_id"), str)
        or any(not isinstance(value.get(key), str) or not value[key].startswith("sha256:") for key in ("from_baseline_hash", "to_baseline_hash", "transition_hash"))
    ):
        raise ValueError("baseline bridge must be explicit, hash bound, and non-authoritative")


def _bridge_matches(bridge: dict[str, Any], before: dict[str, Any], after: dict[str, Any]) -> bool:
    validate_baseline_bridge(bridge)
    return (
        bridge["from_baseline_hash"] == value_hash(before)
        and bridge["to_baseline_hash"] == value_hash(after)
        and bridge["transition_hash"] == value_hash({"from_baseline_hash": bridge["from_baseline_hash"], "to_baseline_hash": bridge["to_baseline_hash"], "transition_files": bridge["transition_files"]})
    )


def _hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def build(plan_root: Path, run_id: str, refs: list[tuple[str, Path]], bridges: list[tuple[dict[str, Any], Path]] | None = None, replay_baseline: Path | None = None) -> dict[str, Any]:
    root = plan_root.parents[1]
    current = current_candidate_identity("RMAP-S6")
    prior_id = prior_run = prior_hash = None
    baseline_identity: dict[str, str | None] = {}
    original: dict[str, str | None] = {}
    current_state: dict[str, str | None] = {}
    items = []
    bridges = list(bridges or [])
    bridge_refs: list[dict[str, str]] = []
    for slice_id, path in refs:
        document = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(document.get("effects"), list):
            raise ValueError(f"{slice_id} does not provide a projected effect list: {path}")
        effects = document["effects"]
        baseline = {str(entry["path"]): entry.get("sha256") for entry in document.get("baseline_files", [])}
        if not baseline_identity:
            baseline_identity = dict(baseline)
            original = dict(baseline_identity)
            current_state = dict(baseline_identity)
        elif baseline != baseline_identity:
            matches = [(bridge, path) for bridge, path in bridges if _bridge_matches(bridge, baseline_identity, baseline)]
            if len(matches) != 1:
                raise ValueError(f"{slice_id} baseline does not match the lineage baseline or an explicit bridge")
            bridge, bridge_path = matches[0]
            previous_index = int(prior_id.rsplit("S", 1)[1]) if prior_id else -1
            if bridge["from_slice_id"] != prior_id or bridge["to_slice_id"] != slice_id or int(slice_id.rsplit("S", 1)[1]) != previous_index + 1:
                raise ValueError(f"{slice_id} bridge does not join adjacent slice baselines")
            for transition in bridge["transition_files"]:
                transition_path = str(transition["path"])
                if current_state.get(transition_path) != transition["before_sha256"]:
                    raise ValueError(f"{slice_id} bridge does not continue accepted state for {transition_path}")
                current_state[transition_path] = transition["after_sha256"]
            for baseline_path, value in baseline.items():
                if baseline_path not in current_state:
                    original[baseline_path] = value
                    current_state[baseline_path] = value
            baseline_identity = dict(baseline)
            bridge_refs.append({
                "from_slice_id": bridge["from_slice_id"],
                "to_slice_id": bridge["to_slice_id"],
                "bridge_path": bridge_path.relative_to(root).as_posix(),
                "bridge_sha256": _hash(bridge_path),
            })
        for effect in effects:
            target = str(effect.get("candidate_path") or effect.get("baseline_path"))
            if target not in original:
                if effect.get("change_type") != "add" or effect.get("before_sha256") is not None:
                    raise ValueError(f"{slice_id} introduces {target} without an add transition")
                original[target] = None
                current_state[target] = None
            if effect.get("before_sha256") != current_state.get(target):
                raise ValueError(f"{slice_id} does not continue the accepted state for {target}")
            current_state[target] = effect.get("after_sha256")
        item = {"slice_id": slice_id, "run_id": document["run_id"], "previous_slice_id": prior_id, "previous_slice_run_id": prior_run, "previous_slice_effect_hash": prior_hash, "run_path": path.relative_to(plan_root.parents[1]).as_posix(), "run_artifact_sha256": _hash(path), "accepted_attempt_fold_hash": value_hash(effects), "final_event_hash": document["final_event_hash"]}
        items.append(item)
        prior_id, prior_run, prior_hash = slice_id, document["run_id"], item["run_artifact_sha256"]
    if len(bridge_refs) != len(bridges):
        raise ValueError("baseline bridge is unused or does not connect a declared transition")
    replay_ref = None if replay_baseline is None else {"path": replay_baseline.relative_to(root).as_posix(), "sha256": _hash(replay_baseline)}
    document = {"schema_version": "jimuyun.candidate-lineage-manifest.v1", "plan_id": "repository-maintenance-tdd-adapter", "candidate_run_id": run_id, "baseline_identity": {key: current[key] for key in ("head", "index_tree")}, "slice_runs": items, "baseline_bridges": bridge_refs, "replay_baseline_ref": replay_ref, "cumulative_fold_hash": ""}
    cumulative: list[dict[str, Any]] = []
    for path in sorted(set(original) | set(current_state), key=str.casefold):
        before, after = original.get(path), current_state.get(path)
        if before == after:
            continue
        change_type = "add" if before is None else "delete" if after is None else "modify"
        cumulative.append({"change_type": change_type, "baseline_path": None if change_type == "add" else path, "candidate_path": None if change_type == "delete" else path, "before_sha256": before, "after_sha256": after})
    document["cumulative_fold_hash"] = value_hash(cumulative)
    document["root_hash"] = value_hash(document)
    return document


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--run-id", required=True); parser.add_argument("--ref", action="append", required=True); parser.add_argument("--bridge", type=Path, action="append"); parser.add_argument("--replay-baseline", type=Path)
    args = parser.parse_args(); plan = Path(__file__).resolve().parents[1]
    refs = [(item.split("=", 1)[0], Path(item.split("=", 1)[1]).resolve()) for item in args.ref]
    bridges = [(json.loads(path.read_text(encoding="utf-8")), path.resolve()) for path in args.bridge or []]
    print(json.dumps(build(plan, args.run_id, refs, bridges, args.replay_baseline.resolve() if args.replay_baseline else None), indent=2))
    return 0


if __name__ == "__main__": raise SystemExit(main())
