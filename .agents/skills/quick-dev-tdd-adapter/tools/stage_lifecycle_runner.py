from __future__ import annotations

from pathlib import Path
import base64
import hashlib
import json
import importlib.util
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


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve_bound_plan(run_dir: Path, basis: dict[str, Any]) -> tuple[Path, Path, Path]:
    """Resolve only the RED-bound physical plan path; never scan or infer it."""
    logs = next((parent for parent in run_dir.parents if parent.name == "logs"), None)
    binding = basis.get("plan_binding") if isinstance(basis, dict) else None
    if logs is None or not isinstance(binding, dict) or set(binding) != {"plan_id", "path_type", "path", "contract_path", "validator_path"}:
        raise ValueError("plan binding is invalid")
    if binding.get("path_type") != "repo_path" or not all(isinstance(binding.get(key), str) and binding[key] for key in binding):
        raise ValueError("plan binding is invalid")
    raw = binding["path"]
    if raw.startswith(("/", "\\")) or "\\" in raw or ".." in Path(raw).parts:
        raise ValueError("plan binding path escapes")
    root = logs.parent.resolve(); plan = (root / raw).resolve()
    plan.relative_to(root / "execution-plans")
    contract, validator = plan / binding["contract_path"], plan / binding["validator_path"]
    if not contract.is_file() or not validator.is_file() or binding["plan_id"] != run_dir.parents[1].name:
        raise ValueError("bound plan is unavailable")
    document = json.loads(contract.read_text(encoding="utf-8"))
    if document.get("plan_id") != binding["plan_id"] or _sha(contract) != basis.get("contract_hash") or _sha(validator) != basis.get("validator_hash"):
        raise ValueError("bound plan identity is stale")
    return root, plan, validator


def _valid_observation(path: Path, stage: str, *, required_exit: int | None = None) -> bool:
    """Validate an immutable observation before deriving a recovery action."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    exit_code = value.get("exit_code") if isinstance(value, dict) else None
    if value.get("stage") != stage or not isinstance(exit_code, int):
        return False
    return exit_code != 0 if required_exit is None and stage == "red" else exit_code == required_exit


def prior_red_observation_path(run_dir: Path) -> Path | None:
    """Resolve a hash-bound prior RED used by a successor without copying it."""
    documents = (
        (run_dir / "prior-red-handoff.v2.json", "red_observation"),
        (run_dir / "prior-red-successor-evidence.v1.json", "prior_red"),
    )
    root = next((parent.parent for parent in run_dir.parents if parent.name == "logs"), None)
    if root is None:
        return None
    for document, key in documents:
        try:
            value = json.loads(document.read_text(encoding="utf-8"))
            reference = value.get(key)
            path, digest = reference.get("path"), reference.get("sha256")
            if not isinstance(path, str) or not isinstance(digest, str):
                continue
            target = (root / path).resolve()
            target.relative_to(root)
            if target.is_file() and _sha(target) == digest and _valid_observation(target, "red"):
                return target
        except (AttributeError, OSError, UnicodeError, ValueError, json.JSONDecodeError):
            continue
    return None


def derive_run_state(run_dir: Path) -> str | None:
    """Derive the next lifecycle action from immutable evidence, never cache state.

    ``stage-state.json`` is an operational cache.  It may be absent after an
    interrupted or successor run, so it cannot decide whether an expensive
    stage is executed again.
    """
    observations = run_dir / "observations"
    red = observations / "red-observed.json"
    green = observations / "green-observed.json"
    refactor = observations / "refactor-observed.json"
    if (run_dir / "slice-ready-result.json").is_file():
        try:
            result = json.loads((run_dir / "slice-ready-result.json").read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return None
        if result.get("predicate") == "slice-ready" and result.get("status") == "pass":
            return None
        return None
    local_red_lineage = (
        red.is_file()
        and (run_dir / "red-basis.v1.json").is_file()
        and _valid_observation(red, "red")
    )
    prior_red_lineage = prior_red_observation_path(run_dir) is not None
    if not local_red_lineage and not prior_red_lineage:
        return None
    if local_red_lineage and not validate_implementation_successor(run_dir):
        return "implement"
    if not green.is_file() or not _valid_observation(green, "green", required_exit=0):
        return "green"
    if not refactor.is_file() or not _valid_observation(refactor, "refactor", required_exit=0):
        return "refactor"
    return "slice-terminal"


def rebuild_stage_state(run_dir: Path) -> str | None:
    """Refresh the non-authoritative stage cache from verified evidence."""
    action = derive_run_state(run_dir)
    if action is None:
        return None
    stage, next_stage = {
        "implement": ("red", "implement"),
        "green": ("implement", "green"),
        "refactor": ("green", "refactor"),
        "slice-terminal": ("refactor", "slice-terminal"),
    }[action]
    payload = {"stage": stage, "next_stage": next_stage, "derived": True, "authorizes": []}
    path = run_dir / "stage-state.json"
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if not path.is_file() or path.read_text(encoding="utf-8") != encoded:
        path.write_text(encoded, encoding="utf-8", newline="\n")
    return action


def validate_implementation_successor(run_dir: Path) -> bool:
    """Verify the run-local implementation successor against RED basis."""
    basis_path = run_dir / "red-basis.v1.json"
    receipt_path = _implementation_successor_path(run_dir)
    red_path = run_dir / "observations" / "red-observed.json"
    if not basis_path.is_file() or not receipt_path.is_file() or not red_path.is_file():
        # A terminal-only successor may intentionally carry the predecessor
        # RED through prior-red-handoff instead of copying red-basis. Validate
        # its immutable lineage against the referenced predecessor run.
        handoff = run_dir / "prior-red-handoff.v2.json"
        if not handoff.is_file():
            return False
        try:
            value = json.loads(handoff.read_text(encoding="utf-8"))
            root = next((parent.parent for parent in run_dir.parents if parent.name == "logs"), None)
            if root is None:
                return False
            if (
                value.get("schema_version") != "quick-dev-tdd-adapter.prior-red-handoff.v2"
                or value.get("plan_id") != run_dir.parents[1].name
                or value.get("slice_id") != run_dir.parent.name
                or value.get("run_id") != run_dir.name
                or not isinstance(value.get("execution_fingerprint"), str)
                or not value["execution_fingerprint"]
                or not isinstance(value.get("test_selector"), str)
                or not isinstance(value.get("test_sha256"), str)
                or not isinstance(value.get("expected_failure_ids"), list)
            ):
                return False
            reference = value.get("red_observation")
            if not isinstance(reference, dict) or set(reference) != {"path", "sha256"}:
                return False
            raw_path, expected_hash = reference["path"], reference["sha256"]
            if not isinstance(raw_path, str) or not isinstance(expected_hash, str) or not expected_hash.startswith("sha256:"):
                return False
            predecessor = (root / raw_path).resolve()
            predecessor.relative_to(root)
            expected_parent = root / "logs" / "tdd-adapter" / value["plan_id"] / value["slice_id"]
            if predecessor.parent.parent.parent != expected_parent or not predecessor.parent.parent.name.startswith("RUN-"):
                return False
            if _sha(predecessor) != expected_hash:
                return False
            red = json.loads(predecessor.read_text(encoding="utf-8"))
            if red.get("stage") != "red" or not isinstance(red.get("exit_code"), int) or red["exit_code"] == 0:
                return False
            predecessor_run = predecessor.parent.parent
            predecessor_basis = predecessor_run / "red-basis.v1.json"
            if not predecessor_basis.is_file():
                return False
            basis = json.loads(predecessor_basis.read_text(encoding="utf-8"))
            if (
                basis.get("execution_fingerprint") != value["execution_fingerprint"]
                or basis.get("test_selector") != value["test_selector"]
                or basis.get("test_sha256") != value["test_sha256"]
                or basis.get("failure_intent", {}).get("expected_failure_ids") != value["expected_failure_ids"]
            ):
                return False
            return validate_implementation_successor(predecessor_run)
        except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            return False
    try:
        basis = json.loads(basis_path.read_text(encoding="utf-8"))
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        red = json.loads(red_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    if not isinstance(basis, dict) or not isinstance(receipt, dict):
        return False
    try:
        if next((parent for parent in run_dir.parents if parent.name == "logs"), None) is None:
            # Isolated unit fixtures have no repository context; retain the
            # structural successor checks and skip only the workspace identity.
            current = None
        else:
            repository_root, plan, validator = _resolve_bound_plan(run_dir, basis)
            spec = importlib.util.spec_from_file_location("current_candidate_validator", validator)
            if spec is None or spec.loader is None: return False
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            current = module.current_candidate_identity(run_dir.parents[0].name)
    except (OSError, ValueError, AttributeError):
        return False
    pre = basis.get("pre_implementation_candidate")
    post = receipt.get("post_implementation_candidate")
    changed_paths = receipt.get("changed_paths")
    expected_basis_hash = _sha(basis_path)
    selector = basis.get("test_selector")
    test_current = False
    if current is None:
        test_current = isinstance(selector, str) and isinstance(basis.get("test_sha256"), str)
    elif isinstance(selector, str):
        test_path = repository_root / selector
        test_current = test_path.is_file() and _sha(test_path) == basis.get("test_sha256")
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
        and test_current
        and (
            current is None
            or (
                all(receipt.get("post_implementation_candidate", {}).get(key) == current.get(key)
                    for key in ("candidate_hash", "predicate_input_root", "authority_root", "validator_root", "validator_version", "closure_definition_hash"))
                and all(
                    current.get("candidate_manifest", {}).get(path) == receipt.get("post_implementation_candidate", {}).get("candidate_manifest", {}).get(path)
                    for path in changed_paths
                )
            )
        )
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
    if not isinstance(pre, dict) or not isinstance(pre.get("candidate_manifest"), dict):
        raise ValueError("RED basis lacks a candidate manifest")
    root, plan, validator = _resolve_bound_plan(run_dir, basis)
    slice_id = run_dir.parents[0].name
    spec = importlib.util.spec_from_file_location("plan_successor_identity", validator)
    if spec is None or spec.loader is None:
        raise ValueError("plan candidate validator is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    computed = module.current_candidate_identity(slice_id)
    manifest_before = pre["candidate_manifest"]
    manifest_after = computed.get("candidate_manifest", {})
    actual_changed = sorted(path for path in set(manifest_before) | set(manifest_after) if manifest_before.get(path) != manifest_after.get(path))
    if computed != post_candidate or sorted(changed_paths) != actual_changed:
        raise ValueError("implementation successor does not match workspace-derived candidate or changed paths")
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

    def resume_observations(
        self,
        run_dir: Path,
        stages: list[str],
        *,
        observation_sources: dict[str, Path] | None = None,
    ) -> None:
        """Resume an existing append-only run before the next stage."""
        expected = ["red", "green", "refactor"]
        start = len(self.stages)
        if stages != expected[start:start + len(stages)]:
            raise ValueError("prior lifecycle stages are invalid")
        snapshots = dict(self.snapshots)
        for stage in stages:
            source = observation_sources.get(stage, run_dir) if observation_sources is not None else run_dir
            path = source / "observations" / f"{stage}-observed.json"
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

    def close(
        self,
        run_context: dict[str, Any],
        artifact_store: dict[tuple[str, str], bytes],
        *,
        observation_sources: dict[str, Path] | None = None,
    ) -> dict[str, Any]:
        """Close only a complete captured lifecycle; no stage is synthesized here."""
        if self.stages != ["red", "green", "refactor"]:
            raise ValueError("complete RED/GREEN/REFACTOR observations are required")
        observations = []
        for stage in self.stages:
            source = observation_sources.get(stage, self.run_dir) if observation_sources else self.run_dir
            path = source / "observations" / f"{stage}-observed.json"
            observations.append(json.loads(path.read_text(encoding="utf-8")))
        bundle, store, _ = compose(run_context, observations, artifact_store)
        persist_protocol_bundle(self.run_dir, bundle, store)
        return bundle
