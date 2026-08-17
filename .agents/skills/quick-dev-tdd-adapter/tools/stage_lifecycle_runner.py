from __future__ import annotations

from pathlib import Path
import base64
import hashlib
import json
import sys
from typing import Any

_TOOLS = Path(__file__).resolve().parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from stage_observation_runner import freeze, record_observation, run
from stage_artifact_composer import compose
from adapter import persist_protocol_bundle


def _implementation_successor_path(run_dir: Path) -> Path:
    return run_dir / "implementation-successor.v1.json"


def validate_implementation_successor(run_dir: Path) -> bool:
    """Verify the run-local implementation successor against RED basis."""
    basis_path = run_dir / "red-basis.v1.json"
    receipt_path = _implementation_successor_path(run_dir)
    red_path = run_dir / "observations" / "red-observed.json"
    if not basis_path.is_file() or not receipt_path.is_file() or not red_path.is_file():
        return False
    try:
        basis = json.loads(basis_path.read_text(encoding="utf-8"))
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        red = json.loads(red_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    if not isinstance(basis, dict) or not isinstance(receipt, dict):
        return False
    pre = basis.get("pre_implementation_candidate")
    post = receipt.get("post_implementation_candidate")
    changed_paths = receipt.get("changed_paths")
    expected_basis_hash = "sha256:" + hashlib.sha256(basis_path.read_bytes()).hexdigest()
    return (
        receipt.get("schema_version") == "quick-dev-tdd-adapter.implementation-successor.v1"
        and receipt.get("status") == "implementation-observed"
        and red.get("stage") == "red"
        and isinstance(red.get("exit_code"), int)
        and red["exit_code"] != 0
        and receipt.get("red_basis_sha256") == expected_basis_hash
        and receipt.get("contract_hash") == basis.get("contract_hash")
        and receipt.get("validator_hash") == basis.get("validator_hash")
        and receipt.get("pre_implementation_candidate") == pre
        and isinstance(post, dict)
        and post != pre
        and isinstance(changed_paths, list)
        and bool(changed_paths)
        and all(isinstance(path, str) and path for path in changed_paths)
        and receipt.get("authorizes") == []
    )


def publish_implementation_successor(run_dir: Path, post_candidate: dict[str, Any], changed_paths: list[str]) -> dict[str, Any]:
    """Persist one RED-bound implementation successor and advance its route."""
    basis_path = run_dir / "red-basis.v1.json"
    state_path = run_dir / "stage-state.json"
    red_path = run_dir / "observations" / "red-observed.json"
    if not basis_path.is_file() or not state_path.is_file() or not red_path.is_file() or not isinstance(post_candidate, dict) or not post_candidate or not changed_paths:
        raise ValueError("implementation successor input is invalid")
    basis = json.loads(basis_path.read_text(encoding="utf-8"))
    state = json.loads(state_path.read_text(encoding="utf-8"))
    red = json.loads(red_path.read_text(encoding="utf-8"))
    pre = basis.get("pre_implementation_candidate")
    if state.get("stage") != "red" or red.get("stage") != "red" or not isinstance(red.get("exit_code"), int) or red["exit_code"] == 0 or not isinstance(pre, dict) or post_candidate == pre or any(not isinstance(path, str) or not path for path in changed_paths):
        raise ValueError("implementation successor does not advance RED candidate")
    receipt = {
        "schema_version": "quick-dev-tdd-adapter.implementation-successor.v1",
        "status": "implementation-observed",
        "run_id": run_dir.name,
        "red_basis_sha256": "sha256:" + hashlib.sha256(basis_path.read_bytes()).hexdigest(),
        "contract_hash": basis.get("contract_hash"),
        "validator_hash": basis.get("validator_hash"),
        "pre_implementation_candidate": pre,
        "post_implementation_candidate": post_candidate,
        "changed_paths": list(changed_paths),
        "authorizes": [],
    }
    destination = _implementation_successor_path(run_dir)
    payload = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if destination.exists() and destination.read_text(encoding="utf-8") != payload:
        raise ValueError("implementation successor already has different bytes")
    if not destination.exists():
        destination.write_text(payload, encoding="utf-8", newline="\n")
    (run_dir / "stage-state.json").write_text(json.dumps({"stage": "implement", "next_stage": "green", "authorizes": []}, indent=2) + "\n", encoding="utf-8", newline="\n")
    return receipt


class LifecycleRunner:
    """Caller-owned, append-only capture state for one future TDD lifecycle."""

    def __init__(self, workspace: Path, run_dir: Path, paths: list[str]) -> None:
        self.workspace = workspace
        self.run_dir = run_dir
        self.paths = list(paths)
        self.snapshots = freeze(workspace, paths)
        self.stages: list[str] = []

    def observe(self, stage: str, command: dict[str, Any], summary: str) -> dict[str, Any]:
        expected = ("red", "green", "refactor")
        if stage not in expected or self.stages != list(expected[:len(self.stages)]):
            raise ValueError("lifecycle stage order is invalid")
        if stage != expected[len(self.stages)]:
            raise ValueError("lifecycle stage is not next")
        observation = run(self.workspace, stage, command, self.paths, summary, before_snapshots=self.snapshots)
        record_observation(self.run_dir, observation)
        self.snapshots = {item["path"]: item["after_bytes_base64"] for item in observation["changed_files"]}
        self.stages.append(stage)
        return observation

    def import_prior_red(self, path: Path, expected_hash: str) -> dict[str, Any]:
        if self.stages:
            raise ValueError("prior RED must be the first lifecycle stage")
        raw = path.read_bytes()
        actual = "sha256:" + hashlib.sha256(raw).hexdigest()
        if actual != expected_hash:
            raise ValueError("prior RED evidence hash is stale")
        observation = json.loads(raw.decode("utf-8"))
        if not isinstance(observation, dict) or observation.get("stage") != "red" or observation.get("exit_code") == 0:
            raise ValueError("prior RED evidence is invalid")
        changed = observation.get("changed_files")
        if not isinstance(changed, list):
            raise ValueError("prior RED snapshots are invalid")
        snapshots: dict[str, str | None] = {}
        for item in changed:
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                raise ValueError("prior RED snapshot is invalid")
            observed_path = item["path"]
            matches = [path for path in self.paths if path == observed_path or path.endswith("/" + observed_path)]
            if len(matches) != 1:
                raise ValueError("prior RED snapshot path is ambiguous")
            current_path = matches[0]
            after = item.get("after_bytes_base64")
            if after is not None and not isinstance(after, str):
                raise ValueError("prior RED snapshot is invalid")
            current = (self.workspace / current_path).read_bytes() if (self.workspace / current_path).is_file() else None
            # A VDD-declared successor may add only its predecessor binding to the
            # plan contract; all command-registry and implementation snapshots stay exact.
            if current_path.endswith("/implementation-contract.v1.json"):
                snapshots[current_path] = after
                continue
            if (None if after is None else base64.b64decode(after, validate=True)) != current:
                raise ValueError("prior RED snapshot continuity is stale")
            snapshots[current_path] = after
        destination = self.run_dir / "observations" / "red-observed.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
        (self.run_dir / "predecessor-red-observation.v1.json").write_text(
            json.dumps({"path": path.as_posix(), "sha256": expected_hash, "authorizes": []}, sort_keys=True) + "\n",
            encoding="utf-8", newline="\n",
        )
        self.snapshots = snapshots
        self.stages.append("red")
        return observation

    def begin_after_prior_red(self) -> None:
        """Permit successor GREEN without copying predecessor RED observation data."""
        if self.stages:
            raise ValueError("prior RED successor must begin from an empty lifecycle")
        self.stages.append("red")

    def resume_observations(self, run_dir: Path, stages: list[str]) -> None:
        """Resume an existing append-only run before the next stage."""
        expected = ["red", "green", "refactor"]
        if stages != expected[:len(stages)] or self.stages:
            raise ValueError("prior lifecycle stages are invalid")
        snapshots = dict(self.snapshots)
        for stage in stages:
            path = run_dir / "observations" / f"{stage}-observed.json"
            if not path.is_file():
                raise ValueError("prior lifecycle observation is missing")
            observation = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(observation, dict) or observation.get("stage") != stage:
                raise ValueError("prior lifecycle observation is invalid")
            changed = observation.get("changed_files")
            if not isinstance(changed, list):
                raise ValueError("prior lifecycle snapshots are invalid")
            for item in changed:
                if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                    raise ValueError("prior lifecycle snapshot is invalid")
                observed_path = item["path"]
                matches = [path for path in self.paths if path == observed_path or path.endswith("/" + observed_path)]
                if len(matches) != 1:
                    raise ValueError("prior lifecycle snapshot path is ambiguous")
                after = item.get("after_bytes_base64")
                if after is not None and not isinstance(after, str):
                    raise ValueError("prior lifecycle snapshot is invalid")
                snapshots[matches[0]] = after
            self.stages.append(stage)
        self.snapshots = snapshots

    def close(self, run_context: dict[str, Any], artifact_store: dict[tuple[str, str], bytes]) -> dict[str, Any]:
        """Close only a complete captured lifecycle; no stage is synthesized here."""
        if self.stages != ["red", "green", "refactor"]:
            raise ValueError("complete RED/GREEN/REFACTOR observations are required")
        observations = []
        for stage in self.stages:
            path = self.run_dir / "observations" / f"{stage}-observed.json"
            observations.append(json.loads(path.read_text(encoding="utf-8")))
        bundle, store, _ = compose(run_context, observations, artifact_store)
        persist_protocol_bundle(self.run_dir, bundle, store)
        return bundle
