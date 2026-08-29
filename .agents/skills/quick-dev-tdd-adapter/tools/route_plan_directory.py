from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

_SKILL_INPUT_ROOT = Path(__file__).resolve().parents[4] / "scripts" / "python"
if str(_SKILL_INPUT_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_INPUT_ROOT))
try:
    from skill_input_consumption import artifact_identity_hash, canonical_hash
except ImportError:
    artifact_identity_hash = None
    canonical_hash = None

try:
    from stage_lifecycle_runner import derive_run_state, validate_implementation_successor
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from stage_lifecycle_runner import derive_run_state, validate_implementation_successor


_IMPLEMENTATION_CANDIDATE_ROOTS = (
    "candidate_hash",
    "predicate_input_root",
    "authority_root",
    "validator_root",
    "validator_version",
    "closure_definition_hash",
    "semantic_closure_hash",
)


def _verify_plan_context(repository_root: Path, plan_dir: Path) -> dict[str, object]:
    path = Path(__file__).with_name("knowledge_context.py")
    spec = importlib.util.spec_from_file_location("quick_dev_bound_knowledge_context", path)
    if spec is None or spec.loader is None:
        return {"status": "vdd-repair", "failure_code": "KWI-QUICK-FROZEN-CONTEXT-STALE"}
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.verify_plan_context(repository_root, plan_dir)


def _full_validation_snapshot(plan_dir: Path, slice_id: str | None = None) -> dict[str, object] | None:
    """Load the plan-owned complete candidate snapshot without inferring inputs."""
    validator = plan_dir / "tools" / "validate_all.py"
    if not validator.is_file():
        return None
    module_name = f"_tdd_adapter_plan_snapshot_{hashlib.sha256(str(plan_dir).encode('utf-8')).hexdigest()}"
    spec = importlib.util.spec_from_file_location(module_name, validator)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    previous_path = list(sys.path)
    try:
        sys.path.insert(0, str(validator.parent))
        spec.loader.exec_module(module)
        snapshot = module.slice_validation_snapshot(slice_id) if slice_id else module.validation_snapshot()
    except (AttributeError, ImportError, OSError, ValueError):
        return None
    finally:
        sys.path[:] = previous_path
        sys.modules.pop(module_name, None)
    return snapshot if isinstance(snapshot, dict) else None


def _validation_snapshot(plan_dir: Path, slice_id: str | None = None) -> dict[str, str] | None:
    """Project the current roots used by the normal freshness predicate."""
    snapshot = _full_validation_snapshot(plan_dir, slice_id)
    if snapshot is None:
        return None
    values = {key: snapshot.get(key) for key in _IMPLEMENTATION_CANDIDATE_ROOTS}
    return values if all(isinstance(value, str) and value for value in values.values()) else None


def _implementation_candidate_current(result: dict[str, object], current: dict[str, str] | None) -> bool:
    if current is None:
        return False
    return all(result.get(key) == current[key] for key in _IMPLEMENTATION_CANDIDATE_ROOTS)


def _successful_stage_observation(run_dir: Path, stage: str) -> bool:
    try:
        value = json.loads((run_dir / "observations" / f"{stage}-observed.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    return isinstance(value, dict) and value.get("stage") == stage and value.get("exit_code") == 0


def _planned_files_exist(repository_root: Path, plan_dir: Path, slice_id: str) -> bool:
    try:
        contract = json.loads((plan_dir / "implementation-contract.v1.json").read_text(encoding="utf-8"))
        selected = next(item for item in contract["slices"] if item.get("slice_id") == slice_id)
        planned = selected.get("planned_new_files", [])
        return isinstance(planned, list) and all(
            isinstance(raw, str) and (repository_root / raw).is_file() for raw in planned
        )
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, StopIteration, TypeError):
        return False


def _reviewed_repair_preserves_slice(
    repository_root: Path,
    plan_dir: Path,
    slice_id: str,
    run_dir: Path,
    result: dict[str, object],
) -> bool:
    """Preserve an unaffected closed slice across one reviewed contract-only repair."""
    try:
        contract = json.loads((plan_dir / "implementation-contract.v1.json").read_text(encoding="utf-8"))
        compatibility = contract.get("slice_ready_repair_compatibility")
        if (
            not isinstance(compatibility, dict)
            or compatibility.get("schema_version") != "quick-dev-tdd-adapter.slice-ready-repair-compatibility.v1"
            or compatibility.get("repair_round") != 3
            or slice_id not in compatibility.get("preserved_slices", [])
            or slice_id in compatibility.get("invalidated_slices", [])
            or result.get("contract_hash") not in compatibility.get("predecessor_contract_hashes", [])
        ):
            return False
        basis_path = run_dir / "red-basis.v1.json"
        red_path = run_dir / "observations" / "red-observed.json"
        basis = json.loads(basis_path.read_text(encoding="utf-8"))
        red = json.loads(red_path.read_text(encoding="utf-8"))
        selected = next(item for item in contract.get("slices", []) if item.get("slice_id") == slice_id)
        selector = selected.get("tdd", {}).get("red", {}).get("test_selector")
        if (
            basis.get("contract_hash") != result.get("contract_hash")
            or basis.get("test_selector") != selector
            or not isinstance(selector, str)
            or _sha((repository_root / selector).read_bytes()) != basis.get("test_sha256")
            or red.get("stage") != "red"
            or not isinstance(red.get("exit_code"), int)
            or red.get("exit_code") == 0
        ):
            return False
        current = _full_validation_snapshot(plan_dir, slice_id)
        if current is None:
            return False
        stable_roots = ("predicate_input_root", "authority_root", "validator_root", "validator_version")
        if any(result.get(key) != current.get(key) for key in stable_roots):
            return False
        return result.get("status") == "pass" and result.get("predicate") == "slice-ready"
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, StopIteration, TypeError, ValueError):
        return False


def _tdd_slice_ready_current(
    repository_root: Path,
    plan_dir: Path,
    plan_id: str,
    slice_id: str,
    contract_hash: str,
    result_path: Path,
    result: dict[str, object],
) -> bool:
    """Accept a current lifecycle or a reviewed, explicitly preserved predecessor slice."""
    run_dir = result_path.parent
    expected_parent = repository_root / "logs" / "tdd-adapter" / plan_id / slice_id
    if (
        run_dir.parent != expected_parent
        or not run_dir.name.startswith("RUN-")
        or "DIAGNOSTIC" in run_dir.name.upper()
        or result.get("plan_id") != plan_id
        or result.get("slice_id") != slice_id
        or result.get("run_id") != run_dir.name
    ):
        return False
    current_snapshot = _validation_snapshot(plan_dir, slice_id)
    if result.get("contract_hash") == contract_hash:
        lifecycle_current = validate_implementation_successor(run_dir) and _implementation_candidate_current(result, current_snapshot)
    else:
        lifecycle_current = _reviewed_repair_preserves_slice(repository_root, plan_dir, slice_id, run_dir, result)
    return (
        lifecycle_current
        and _successful_stage_observation(run_dir, "green")
        and _successful_stage_observation(run_dir, "refactor")
        and _planned_files_exist(repository_root, plan_dir, slice_id)
    )


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _artifact_hash(path: Path) -> str:
    if artifact_identity_hash is not None:
        return artifact_identity_hash(path)
    return _sha(path.read_bytes())


def _artifact_identity_kind(path: Path) -> str:
    if path.suffix.casefold() == ".json":
        try:
            json.loads(path.read_text(encoding="utf-8"))
            return "canonical-json-v1"
        except (OSError, UnicodeError, json.JSONDecodeError):
            pass
    return "raw-bytes-v1"


def _binding_is_current(root: Path, binding: object) -> bool:
    if not isinstance(binding, dict) or not isinstance(binding.get("path"), str) or not isinstance(binding.get("sha256"), str):
        return False
    try:
        path = (root / binding["path"]).resolve()
        path.relative_to(root)
    except ValueError:
        return False
    if not path.is_file() or _artifact_hash(path) != binding["sha256"]:
        return False
    declared_kind = binding.get("identity_kind")
    return declared_kind is None or declared_kind == _artifact_identity_kind(path)


def _minimal_authorization_binding_is_current(root: Path, binding: object) -> bool:
    """Accept the plan-local receipt's explicitly raw or canonical file identity."""
    if not isinstance(binding, dict) or not isinstance(binding.get("path"), str) or not isinstance(binding.get("sha256"), str):
        return False
    try:
        path = (root / binding["path"]).resolve()
        path.relative_to(root)
    except ValueError:
        return False
    if not path.is_file():
        return False
    payload = path.read_bytes()
    raw = _sha(payload)
    repository_text = _sha(payload.replace(b"\r\n", b"\n")) if path.suffix.casefold() == ".json" else raw
    canonical = _artifact_hash(path)
    return binding["sha256"] in {raw, repository_text, canonical}


def _review_and_conformance_authorize(root: Path, receipt: dict[str, object]) -> bool:
    """Authorization requires an exact accepted review and conformant mapping."""
    try:
        review_ref = receipt.get("review_run")
        conformance_ref = receipt.get("conformance_result")
        binding_ref = receipt.get("review_candidate_binding")
        input_ref = receipt.get("review_input")
        contract_ref = receipt.get("implementation_contract")
        registry_ref = receipt.get("command_registry")
        if not all(
            isinstance(value, dict)
            for value in (review_ref, conformance_ref, binding_ref, input_ref, contract_ref, registry_ref)
        ):
            return False
        if not all(
            _minimal_authorization_binding_is_current(root, value)
            for value in (review_ref, conformance_ref, binding_ref, input_ref, contract_ref, registry_ref)
        ):
            return False

        review = json.loads((root / review_ref["path"]).read_text(encoding="utf-8"))
        conformance = json.loads((root / conformance_ref["path"]).read_text(encoding="utf-8"))
        binding = json.loads((root / binding_ref["path"]).read_text(encoding="utf-8"))
        review_input = json.loads((root / input_ref["path"]).read_text(encoding="utf-8"))
        candidate_input = review_input.get("candidate")
        required_bindings = review_input.get("required_review_bindings")
        if (
            review_input.get("schema_version") != "vdd-external-semantic-review-input.v1"
            or review_input.get("required_output") != "vdd-review-run.v1"
            or review_input.get("authorizes") != []
            or not isinstance(candidate_input, dict)
            or not isinstance(candidate_input.get("head_commit"), str)
            or not candidate_input["head_commit"]
            or not isinstance(required_bindings, dict)
        ):
            return False

        review_binding_fields = (
            "semantic_handoff_hash",
            "source_manifest_hash",
            "requirements_manifest_hash",
            "ambiguity_ids",
            "affected_requirement_ids",
        )
        if (
            review.get("schema_version") != "vdd-review-run.v1"
            or review.get("status") != "accepted"
            or review.get("decision") != "accepted"
            or review.get("authorizes") != []
            or review.get("profile") != review_input.get("profile")
            or any(review.get(field) != required_bindings.get(field) for field in review_binding_fields)
            or conformance.get("status") != "conformant"
            or conformance.get("errors") != []
            or conformance.get("authorizes") != []
            or conformance.get("source_manifest_hash") != required_bindings.get("source_manifest_hash")
            or conformance.get("requirements_manifest_hash") != required_bindings.get("requirements_manifest_hash")
            or binding.get("schema_version") != "vdd-review-candidate-binding.v1"
            or binding.get("status") != "accepted"
            or binding.get("decision") != "accepted"
            or binding.get("review_input") != input_ref
            or binding.get("review_run") != review_ref
            or binding.get("conformance_result") != conformance_ref
            or binding.get("source_freeze") != receipt.get("source_freeze")
            or binding.get("source_freeze") != review_input.get("source_freeze")
            or binding.get("requirements_mapping") != receipt.get("requirements_mapping")
            or binding.get("requirements_mapping") != review_input.get("requirements_mapping")
        ):
            return False

        if receipt.get("schema_version") == "quick-dev-tdd-adapter.implementation-authorization.v3":
            return (
                binding.get("candidate_commit") == candidate_input.get("head_commit")
                and binding.get("implementation_contract") == contract_ref
                and binding.get("implementation_contract") == candidate_input.get("implementation_contract")
                and binding.get("command_registry") == registry_ref
                and binding.get("command_registry") == candidate_input.get("command_registry")
            )

        candidate = receipt.get("candidate_commit")
        return (
            binding.get("candidate_commit") == candidate == candidate_input.get("head_commit")
            and binding.get("implementation_contract") == contract_ref
            and binding.get("implementation_contract") == candidate_input.get("implementation_contract")
            and binding.get("command_registry") == registry_ref
            and binding.get("command_registry") == candidate_input.get("command_registry")
        )
    except (KeyError, OSError, UnicodeError, json.JSONDecodeError, TypeError):
        return False

def _high_velocity_plan_authorize(root: Path, receipt: dict[str, object]) -> bool:
    """Validate a maintainer's whole-plan authorization without candidate binding.

    This leaves lifecycle evidence hash-bound while allowing declared S1..S6
    implementation writes to advance the candidate.  Any change to the
    normative contract, command registry, source freeze, mapping, or authority
    invalidates the receipt through its explicit references.
    """
    required = (
        "implementation_contract", "command_registry", "authority_manifest",
        "review_input", "review_run", "review_candidate_binding",
        "conformance_result", "source_freeze", "requirements_mapping",
    )
    if (
        receipt.get("schema_version") != "quick-dev-tdd-adapter.implementation-authorization.v3"
        or receipt.get("scope") != "whole_plan"
        or receipt.get("mode") != "high_velocity_tdd"
        or receipt.get("authorizes") != ["implementation-authorized"]
        or receipt.get("does_not_bind") != ["candidate_commit", "implementation_source_hashes", "run_evidence"]
        or receipt.get("binds") != ["plan_id", "requirements_mapping", "source_freeze", "implementation_contract", "command_registry", "authority_manifest"]
        or not all(_minimal_authorization_binding_is_current(root, receipt.get(field)) for field in required)
    ):
        return False
    return _review_and_conformance_authorize(root, receipt)


def _candidate_bound_plan_authorize(root: Path, plan_dir: Path, plan_id: str, receipt: dict[str, object]) -> bool:
    """Validate a reviewed candidate-bound v4 authorization and its evidence chain."""
    required = (
        "implementation_contract", "command_registry", "authority_manifest",
        "review_candidate_binding", "source_freeze", "requirements_mapping",
    )
    if (
        receipt.get("schema_version") != "quick-dev-tdd-adapter.implementation-authorization.v4"
        or receipt.get("plan_id") != plan_id
        or receipt.get("owner") != "maintainer"
        or receipt.get("mode") != "high_velocity_tdd"
        or receipt.get("authorizes") != ["implementation-authorized"]
        or not all(_minimal_authorization_binding_is_current(root, receipt.get(field)) for field in required)
    ):
        return False
    try:
        binding_ref = receipt["review_candidate_binding"]
        binding = json.loads((root / binding_ref["path"]).read_text(encoding="utf-8"))
        augmented = dict(receipt)
        for field in ("review_input", "review_run", "conformance_result"):
            augmented[field] = binding.get(field)
    except (KeyError, OSError, UnicodeError, json.JSONDecodeError, TypeError):
        return False
    return (
        _review_and_conformance_authorize(root, augmented)
        and _candidate_commit_is_current(root, plan_dir, receipt)
    )


def _candidate_commit_is_current(root: Path, plan_dir: Path, receipt: dict[str, object]) -> bool:
    """Validate candidate commit/tree for the normative closure only.

    Evidence publication commits are intentionally outside this closure, so a
    receipt remains valid after its own evidence is appended to the branch.
    """
    commit = receipt.get("candidate_commit")
    tree = receipt.get("candidate_tree_hash")
    if commit is None and tree is None:
        return True
    if not isinstance(commit, str) or not commit or not isinstance(tree, str) or not tree.startswith("sha256:"):
        return False
    expected_tree = subprocess.run(["git", "-C", str(root), "rev-parse", f"{commit}^{{tree}}"], capture_output=True, text=True, check=False)
    if expected_tree.returncode != 0 or "sha256:" + expected_tree.stdout.strip() != tree:
        return False
    try:
        contract = json.loads((plan_dir / "implementation-contract.v1.json").read_text(encoding="utf-8"))
        paths: set[str] = {"execution-plans/" + plan_dir.name + "/implementation-contract.v1.json", "execution-plans/" + plan_dir.name + "/command-registry.v1.json"}
        for item in contract.get("slices", []):
            changes = item.get("allowed_changes", {})
            for group in changes.values():
                paths.update(group)
            paths.update(item.get("planned_new_files", []))
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError):
        return False
    # Evidence publication may advance HEAD, but unrelated workspace writes
    # must never become invisible to successor validation.
    try:
        changed = subprocess.run(
            ["git", "-C", str(root), "diff", "--name-only", f"{commit}..HEAD"],
            capture_output=True, text=True, check=False,
        ).stdout.splitlines()
        state_path = f"execution-plans/{plan_dir.name}/plan-state.v1.json"
        allowed_prefixes = (
            f"execution-plans/{plan_dir.name}/governance/",
            f"execution-plans/{plan_dir.name}/implementation-authorization-receipt",
            f"execution-plans/{plan_dir.name}/tools/publish_candidate_authorization.py",
            "docs/vdd-review-run.v1.json",
        )
        implementation_paths = {
            path for item in contract.get("slices", [])
            for group in (item.get("allowed_changes", {}) or {}).values()
            for path in group if isinstance(path, str)
        }
        implementation_paths.update(
            path for item in contract.get("slices", [])
            for path in item.get("planned_new_files", []) if isinstance(path, str)
        )
        allowed_change = lambda path: path.startswith(allowed_prefixes) or path == state_path or path in implementation_paths
        if any(path and not allowed_change(path) for path in changed):
            return False
        status = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain=v1", "--untracked-files=all"],
            capture_output=True, text=True, check=False,
        ).stdout.splitlines()
        for row in status:
            path = row[3:] if len(row) >= 4 else ""
            if " -> " in path:
                path = path.split(" -> ", 1)[1]
            if path and not allowed_change(path):
                return False
        if state_path in changed or any(row[3:] == state_path for row in status if len(row) >= 4):
            state = json.loads((plan_dir / "plan-state.v1.json").read_text(encoding="utf-8"))
            if state.get("plan_id") != contract.get("plan_id") or state.get("state", state.get("status")) != "implementation-authorized" or state.get("authorizes") != ["implementation-authorized"] or state.get("baseline_commit") != commit:
                return False
    except OSError:
        return False
    return True


def _skill_input_generation_is_current(root: Path, generation: object) -> bool:
    required = {
        "schema_version", "receipt", "source_selection_hash", "selected_source_content_root",
        "context_hash", "semantic_decision_hash", "child_request_hash", "generation_root",
    }
    if not isinstance(generation, dict) or set(generation) != required or generation.get("schema_version") != "skill-input-generation.v1":
        return False
    if canonical_hash is None or generation.get("generation_root") != canonical_hash({key: value for key, value in generation.items() if key != "generation_root"}):
        return False
    if not _binding_is_current(root, generation["receipt"]):
        return False
    try:
        receipt_path = (root / generation["receipt"]["path"]).resolve()
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        identity = receipt["repository_identity"]
        return (
            receipt.get("ready") is True
            and identity.get("source_selection_hash") == generation["source_selection_hash"]
            and identity.get("selected_source_content_root") == generation["selected_source_content_root"]
            and receipt.get("context_artifact", {}).get("sha256") == generation["context_hash"]
            and receipt.get("semantic_decision", {}).get("sha256") == generation["semantic_decision_hash"]
            and receipt.get("child_request", {}).get("sha256") == generation["child_request_hash"]
        )
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError):
        return False


def _current_execution_fingerprint(repository_root: Path, plan_dir: Path, slice_id: str) -> str | None:
    """Build the current RED semantic identity without creating a run."""
    try:
        from build_slice_invocation import build

        context = build(repository_root, plan_dir, slice_id, "RECOVERY-PROBE")["run_context"]
        value = context["stage_results"]["red"]["execution_fingerprint"]
        return value if isinstance(value, str) and value else None
    except (ImportError, KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
        return None


def current_red_handoff(repository_root: Path, plan_dir: Path, slice_id: str) -> dict[str, str] | None:
    """Return the single current Quick Dev RED handoff for a slice.

    The handoff is continuity evidence only: its contract, selector, expected
    failures, and test bytes must still match the plan before it can seed a
    GREEN continuation.
    """
    root, plan = repository_root.resolve(), plan_dir.resolve()
    contract_path = plan / "implementation-contract.v1.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    selected = next((item for item in contract.get("slices", []) if item.get("slice_id") == slice_id), None)
    if not isinstance(selected, dict):
        return None
    if selected.get("execution_mode", "tdd") != "tdd":
        return None
    red = selected.get("tdd", {}).get("red") if isinstance(selected.get("tdd"), dict) else None
    if not isinstance(red, dict):
        return None
    selector = red.get("test_selector")
    if not isinstance(selector, str):
        return None
    evidence_root = root / "logs" / "tdd-adapter" / str(contract.get("plan_id")) / slice_id
    current_fingerprint = _current_execution_fingerprint(root, plan, slice_id)
    expected_test_hash = _sha((root / selector).read_bytes()) if (root / selector).is_file() else None
    for handoff_path in sorted(evidence_root.glob("*/prior-red-handoff.v2.json"), reverse=True) if evidence_root.is_dir() else []:
        try:
            handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
            reference = handoff.get("red_observation")
            if (
                handoff.get("plan_id") == contract.get("plan_id")
                and handoff.get("slice_id") == slice_id
                and handoff.get("execution_fingerprint") == current_fingerprint
                and handoff.get("test_selector") == selector
                and handoff.get("expected_failure_ids") == red.get("expected_failure_ids")
                and isinstance(reference, dict)
                and set(reference) == {"path", "sha256"}
            ):
                return {"path": reference["path"], "sha256": reference["sha256"]}
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError):
            continue
    # A completed implementation successor may outlive a control-plane-only
    # contract refresh (for example, terminal predicate bookkeeping). Reuse its
    # immutable RED observation when the declared test bytes and failure intent
    # are unchanged; do not accept a bare stage receipt or an unrelated run.
    for run_dir in sorted(evidence_root.glob("RUN-*"), reverse=True) if evidence_root.is_dir() else []:
        try:
            basis = json.loads((run_dir / "red-basis.v1.json").read_text(encoding="utf-8"))
            successor = json.loads((run_dir / "implementation-successor.v1.json").read_text(encoding="utf-8"))
            observation = run_dir / "observations" / "red-observed.json"
            observed = json.loads(observation.read_text(encoding="utf-8"))
            test_path = root / selector
            if (
                observation.is_file()
                and successor.get("status") == "implementation-observed"
                and basis.get("test_selector") == selector
                and basis.get("test_sha256") == expected_test_hash
                and basis.get("failure_intent", {}).get("expected_failure_ids") == red.get("expected_failure_ids")
                and observed.get("stage") == "red"
                and isinstance(observed.get("exit_code"), int)
                and observed["exit_code"] != 0
                and test_path.is_file()
            ):
                return {"path": observation.relative_to(root).as_posix(), "sha256": _sha(observation)}
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, AttributeError):
            continue
    artifacts = sorted(evidence_root.glob("*/implementation-needed-result.json")) if evidence_root.is_dir() else []
    expected_contract = _sha(contract_path.read_bytes())

    def valid_basis(path: Path) -> bool:
        try:
            basis = json.loads(path.read_text(encoding="utf-8"))
            intent = basis.get("failure_intent", {})
        except (OSError, UnicodeError, json.JSONDecodeError, AttributeError):
            return False
        return (
            basis.get("test_selector") == selector
            and basis.get("test_sha256") == expected_test_hash
            and basis.get("execution_fingerprint") == current_fingerprint
            and intent.get("expected_failure_ids") == red.get("expected_failure_ids")
        )
    valid: list[Path] = []
    for artifact in artifacts:
        try:
            value = json.loads(artifact.read_text(encoding="utf-8"))
            test_path = (root / selector).resolve()
            test_path.relative_to(root)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            continue
        contract_matches = value.get("contract_hash") == expected_contract
        if not contract_matches:
            historical = _historical_contract_and_registry(repository_root, plan_dir, value.get("contract_hash"))
            if historical is not None:
                try:
                    old_contract = json.loads(historical[0].decode("utf-8"))
                    old_registry = json.loads(historical[1].decode("utf-8"))
                    contract_matches = _slice_projection(old_contract, old_registry, slice_id) == _slice_projection(
                        json.loads(contract_path.read_text(encoding="utf-8")),
                        json.loads((plan_dir / "command-registry.v1.json").read_text(encoding="utf-8")),
                        slice_id,
                    )
                except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
                    contract_matches = False
        if (
            value.get("predicate") != "implementation-needed"
            or value.get("status") != "pass"
            or value.get("stage") != "red"
            or not contract_matches
            or value.get("test_selector") != selector
            or value.get("expected_failure_ids") != red.get("expected_failure_ids")
            or not isinstance(value.get("exit_code"), int)
            or value["exit_code"] == 0
            or not test_path.is_file()
            or value.get("test_hash") != _sha(test_path.read_bytes())
        ):
            continue
        valid.append(artifact)
    if len(valid) != 1:
        # Compatibility bridge for staged runs that recorded the RED result
        # before the implementation-needed sidecar was introduced. The
        # observation remains the authoritative nonzero execution proof; the
        # red-result binds selector/failure intent and contract projection.
        legacy: list[tuple[Path, Path]] = []
        for result_path in sorted(evidence_root.glob("*/red-result.json")):
            observation_path = result_path.parent / "observations" / "red-observed.json"
            try:
                result = json.loads(result_path.read_text(encoding="utf-8"))
                observation = json.loads(observation_path.read_text(encoding="utf-8"))
                test_path = (root / selector).resolve()
                test_path.relative_to(root)
            except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
                continue
            if (
                result.get("stage") != "red"
                or result.get("slice_id") != slice_id
                or result.get("test_selector") != selector
                or result.get("expected_failure_ids") != red.get("expected_failure_ids")
                or observation.get("stage") != "red"
                or not isinstance(observation.get("exit_code"), int)
                or observation.get("exit_code") == 0
                or not test_path.is_file()
                or not valid_basis(result_path.parent / "red-basis.v1.json")
            ):
                continue
            legacy.append((result_path, observation_path))
        if not legacy:
            # The oldest staged shape contains only the canonical RED basis and
            # its immutable failed observation.  It is safe only when both
            # current executable identity and current test bytes still match.
            for basis_path in sorted(evidence_root.glob("*/red-basis.v1.json")):
                observation_path = basis_path.parent / "observations" / "red-observed.json"
                try:
                    observation = json.loads(observation_path.read_text(encoding="utf-8"))
                except (OSError, UnicodeError, json.JSONDecodeError):
                    continue
                if (
                    valid_basis(basis_path)
                    and observation.get("stage") == "red"
                    and isinstance(observation.get("exit_code"), int)
                    and observation["exit_code"] != 0
                ):
                    legacy.append((basis_path, observation_path))
        if not legacy:
            return None
        # Multiple interrupted attempts may exist; the newest matching RED is
        # the recoverable predecessor when all candidates describe the same
        # selector/failure intent.
        observation_path = sorted(legacy, key=lambda item: item[0].parent.name)[-1][1]
        return {"path": observation_path.relative_to(root).as_posix(), "sha256": _sha(observation_path.read_bytes())}
    artifact = valid[0]
    return {"path": artifact.relative_to(root).as_posix(), "sha256": _sha(artifact.read_bytes())}


def _head_artifact_bytes(repository_root: Path, relative: Path) -> bytes | None:
    """Read an immutable HEAD artifact for independent-slice freshness checks."""
    completed = subprocess.run(
        ["git", "-C", str(repository_root), "show", f"HEAD:{relative.as_posix()}"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout if completed.returncode == 0 else None


def _historical_contract_and_registry(
    repository_root: Path,
    plan_dir: Path,
    contract_hash: str,
) -> tuple[bytes, bytes] | None:
    """Resolve immutable producer inputs for a legacy slice receipt."""
    root = repository_root.resolve()
    contract_path = plan_dir.resolve().relative_to(root).as_posix()
    registry_path = (plan_dir / "command-registry.v1.json").resolve().relative_to(root).as_posix()
    commits = subprocess.run(
        ["git", "-C", str(root), "log", "--all", "--format=%H", "--", contract_path],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    for commit in commits.stdout.splitlines():
        contract = subprocess.run(
            ["git", "-C", str(root), "show", f"{commit}:{contract_path}"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if contract.returncode != 0 or _sha(contract.stdout) != contract_hash:
            continue
        registry = subprocess.run(
            ["git", "-C", str(root), "show", f"{commit}:{registry_path}"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return contract.stdout, registry.stdout if registry.returncode == 0 else b'{"commands":[]}'
    return None


def _slice_projection(contract: dict[str, object], registry: dict[str, object], slice_id: str) -> str | None:
    """Hash the slice and recursive dependencies, plus their command descriptors."""
    declared = contract.get("slices")
    commands = registry.get("commands")
    if not isinstance(declared, list) or not isinstance(commands, list):
        return None
    by_id = {item.get("slice_id"): item for item in declared if isinstance(item, dict)}
    if slice_id not in by_id or len(by_id) != len(declared):
        return None
    ordered: list[str] = []
    visiting: set[str] = set()

    def visit(current: str) -> bool:
        if current in visiting:
            return False
        if current in ordered:
            return True
        item = by_id.get(current)
        if not isinstance(item, dict):
            return False
        visiting.add(current)
        dependencies = item.get("depends_on", [])
        if not isinstance(dependencies, list) or any(not isinstance(value, str) for value in dependencies):
            return False
        if not all(visit(value) for value in dependencies):
            return False
        visiting.remove(current)
        ordered.append(current)
        return True

    if not visit(slice_id):
        return None
    command_ids: set[str] = set()
    for current in ordered:
        item = by_id[current]
        tdd = item.get("tdd", {})
        if isinstance(tdd, dict):
            for stage in ("red", "green"):
                value = tdd.get(stage, {})
                if isinstance(value, dict) and isinstance(value.get("command_id"), str):
                    command_ids.add(value["command_id"])
            refactor = tdd.get("refactor", {})
            if isinstance(refactor, dict) and isinstance(refactor.get("invocations"), list):
                for invocation in refactor["invocations"]:
                    if isinstance(invocation, dict) and isinstance(invocation.get("command_id"), str):
                        command_ids.add(invocation["command_id"])
        if isinstance(item.get("post_refactor_command_id"), str):
            command_ids.add(item["post_refactor_command_id"])
    command_by_id = {item.get("id"): item for item in commands if isinstance(item, dict)}
    if any(command_id not in command_by_id for command_id in command_ids):
        return None
    payload = {
        "plan_id": contract.get("plan_id"),
        "slices": [by_id[current] for current in ordered],
        "commands": [command_by_id[current] for current in sorted(command_ids)],
    }
    return _sha(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _unaffected_slice_current(
    repository_root: Path,
    plan_dir: Path,
    contract: dict[str, object],
    registry: dict[str, object],
    result: dict[str, object],
    slice_id: str,
) -> bool:
    """Reuse a predecessor result only when its exact slice projection is unchanged."""
    current_fingerprint = _current_execution_fingerprint(repository_root.resolve(), plan_dir, slice_id)
    if isinstance(result.get("execution_fingerprint"), str):
        return result["execution_fingerprint"] == current_fingerprint
    root = repository_root.resolve()
    contract_path = plan_dir / "implementation-contract.v1.json"
    current_bytes = _head_artifact_bytes(root, contract_path.resolve().relative_to(root))
    if current_bytes is None:
        return False
    if result.get("contract_hash") == _sha(current_bytes):
        baseline_bytes = current_bytes
        registry_path = plan_dir / "command-registry.v1.json"
        baseline_registry_bytes = _head_artifact_bytes(root, registry_path.resolve().relative_to(root)) or b'{"commands":[]}'
    else:
        historical = _historical_contract_and_registry(root, plan_dir, str(result.get("contract_hash")))
        if historical is None:
            return False
        baseline_bytes, baseline_registry_bytes = historical
    try:
        baseline_contract = json.loads(baseline_bytes.decode("utf-8"))
        baseline_registry = json.loads(baseline_registry_bytes.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return False
    current_projection = _slice_projection(contract, registry, slice_id)
    baseline_projection = _slice_projection(baseline_contract, baseline_registry, slice_id)
    return current_projection is not None and current_projection == baseline_projection


def _terminal_completion_current(repository_root: Path, plan_dir: Path, contract_hash: str) -> bool:
    contract = json.loads((plan_dir / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    terminal = contract.get("terminal")
    has_top_level_terminal = isinstance(terminal, dict) and terminal.get("predicate") == "implementation-complete"
    registry_path = plan_dir / "command-registry.v1.json"
    canonical_receipts = sorted(
        (plan_dir / "repair" / "round-1").glob("quick-dev-implementation-complete*.v1.json"),
        reverse=True,
    )
    expected_registry_hash = _sha(registry_path.read_bytes()) if registry_path.is_file() else None
    for path in canonical_receipts if has_top_level_terminal else []:
        try:
            result = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if (
            result.get("schema_version") == "quick-dev-implementation-complete.v1"
            and result.get("predicate") == "implementation-complete"
            and result.get("status") == "pass"
            and result.get("plan_id") == contract["plan_id"]
            and result.get("contract_hash") == contract_hash
            and result.get("command_registry_hash") == expected_registry_hash
            and result.get("terminal_command_id") == terminal.get("command_id")
            and result.get("authorizes") == ["implementation-complete"]
            and isinstance(result.get("validated_command_ids"), list)
        ):
            return True
    evidence = repository_root / "logs" / "tdd-adapter" / contract["plan_id"] / "terminal"
    for path in sorted(evidence.glob("*/implementation-complete-result.json"), reverse=True) if has_top_level_terminal else []:
        try:
            result = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if (
            result.get("predicate") == "implementation-complete"
            and result.get("status") == "pass"
            and (contract.get("plan_id") != "quick-dev-tdd-stage-recovery" or result.get("orchestration_version") == "stage-actions.v2")
            and result.get("plan_id") == contract["plan_id"]
            and result.get("contract_hash") == contract_hash
            and result.get("terminal_command_id") == terminal.get("command_id")
            and isinstance(result.get("validated_command_ids"), list)
            and result.get("authorizes") == ["implementation-complete"]
        ):
            return True
    # Some strict plans bind implementation completion to their final TDD
    # slice rather than declaring a separate top-level terminal runner.
    for slice_item in contract.get("slices", []):
        if slice_item.get("exit_predicate") != "implementation-complete":
            continue
        slice_evidence = repository_root / "logs" / "tdd-adapter" / contract["plan_id"] / str(slice_item.get("slice_id"))
        for path in sorted(slice_evidence.glob("RUN-*/implementation-complete-result.json"), reverse=True):
            try:
                result = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if (
                result.get("predicate") == "implementation-complete"
                and result.get("status") == "pass"
                and result.get("plan_id") == contract["plan_id"]
                and result.get("contract_hash") == contract_hash
                and result.get("terminal_command_id") == slice_item.get("post_refactor_command_id")
                and result.get("authorizes") == ["implementation-complete"]
                and isinstance(result.get("validated_command_ids"), list)
            ):
                return True
            # Older slice-bound terminal runs persisted the validator's
            # canonical receipt before the adapter added explicit bindings.
            # Accept that immutable receipt only when it proves every slice
            # was selected and explicitly authorizes implementation-complete.
            if (
                result.get("predicate") == "implementation-complete"
                and result.get("status") == "pass"
                and result.get("authorizes") == ["implementation-complete"]
                and set(result.get("selected_slices", [])) == {item.get("slice_id") for item in contract.get("slices", [])}
            ):
                return True
    return False


def _active_slice_action(repository_root: Path, plan_dir: Path, slice_id: str) -> str | None:
    contract = json.loads((plan_dir / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    plan_id = str(contract["plan_id"])
    evidence_root = repository_root / "logs" / "tdd-adapter" / plan_id / slice_id
    contract_path = plan_dir / "implementation-contract.v1.json"
    try:
        current_contract_hash = _sha(contract_path.read_bytes())
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        selected = next(item for item in contract.get("slices", []) if item.get("slice_id") == slice_id)
        current_selector = selected.get("tdd", {}).get("red", {}).get("test_selector")
    except (OSError, UnicodeError, json.JSONDecodeError, StopIteration, TypeError, AttributeError):
        return None
    candidates = sorted((path for path in evidence_root.glob("RUN-*") if path.is_dir()), key=lambda path: path.name, reverse=True)
    actions: list[str] = []
    for run_dir in candidates:
        # A historical run whose RED was bound to a different contract or
        # selector is immutable evidence, not an active continuation. It must
        # not mask a newer run after a dependency or contract repair.
        try:
            basis = json.loads((run_dir / "red-basis.v1.json").read_text(encoding="utf-8"))
            if basis.get("contract_hash") != current_contract_hash or basis.get("test_selector") != current_selector:
                continue
        except (OSError, UnicodeError, json.JSONDecodeError, AttributeError):
            continue
        action = derive_run_state(run_dir)
        if (action in {"implement", "green", "refactor"}
                and (run_dir / "implementation-successor.v1.json").is_file()
                and not validate_implementation_successor(run_dir)):
            # A successor that no longer matches the current candidate is
            # immutable stale history; do not block a fresh RED-bound run.
            continue
        if action is None and (run_dir / "slice-ready-result.json").is_file() and validate_implementation_successor(run_dir):
            action = "slice-terminal"
        if action == "slice-terminal":
            actions.append("validate-slice")
        if action == "implement":
            actions.append("implement")
        if action in {"green", "refactor"}:
            actions.append("run-slice")
    if not actions:
        return None
    # Prefer the furthest verified lifecycle state when recovery produced
    # multiple successors. A newer partial GREEN must not hide a completed
    # REFACTOR waiting for slice terminal validation.
    for preferred in ("validate-slice", "run-slice", "implement"):
        if preferred in actions:
            return preferred
    return None


def next_stage_action(stages: list[str]) -> str:
    """Return the only legal successor for an observed stage prefix."""
    transitions = {(): "red", ("red",): "implement", ("red", "implement"): "green", ("red", "implement", "green"): "refactor", ("red", "implement", "green", "refactor"): "slice-terminal"}
    key = tuple(stages)
    if key not in transitions:
        raise ValueError("stage observations are not an ordered lifecycle prefix")
    return transitions[key]


def _staged_refactor_complete(result_path: Path) -> bool:
    try:
        state = json.loads(result_path.with_name("stage-state.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    return state.get("stage") == "refactor"


def _slice_authorization_gate(plan_dir: Path, plan_id: str) -> dict[str, object] | None:
    state_path = plan_dir / "plan-state.v1.json"
    if not state_path.is_file():
        return None
    try:
        document = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {
            "next_action": "external-repair-required",
            "reason": "invalid-plan-state",
            "authorizes": [],
        }
    if not isinstance(document, dict):
        return {
            "next_action": "external-repair-required",
            "reason": "invalid-plan-state",
            "authorizes": [],
        }
    current_state = document.get("status")
    legacy_state = document.get("state")
    if (
        isinstance(current_state, str)
        and isinstance(legacy_state, str)
        and current_state != legacy_state
    ):
        return {
            "next_action": "external-repair-required",
            "reason": "invalid-plan-state",
            "authorizes": [],
        }
    lifecycle_state = current_state if isinstance(current_state, str) else legacy_state
    if (
        document.get("plan_id") != plan_id
        or not isinstance(lifecycle_state, str)
        or not isinstance(document.get("authorizes"), list)
    ):
        return {
            "next_action": "external-repair-required",
            "reason": "invalid-plan-state",
            "authorizes": [],
        }
    if lifecycle_state == "implementation-authorized":
        if document["authorizes"] in (["implementation-authorized"], ["plan-ready", "implementation-authorized"]):
            root = plan_dir.resolve().parents[1]
            candidate_receipts = sorted(plan_dir.glob("implementation-authorization-receipt.v4.json"))
            if candidate_receipts:
                try:
                    candidate_receipt = json.loads(candidate_receipts[-1].read_text(encoding="utf-8"))
                    if _candidate_bound_plan_authorize(root, plan_dir, plan_id, candidate_receipt):
                        return None
                except (OSError, UnicodeError, json.JSONDecodeError, TypeError):
                    pass
                return {
                    "next_action": "external-repair-required",
                    "reason": "candidate-bound-authorization-stale",
                    "authorizes": [],
                }
            velocity_receipts = sorted(plan_dir.glob("implementation-authorization-receipt.v3.json"))
            if velocity_receipts:
                try:
                    velocity = json.loads(velocity_receipts[-1].read_text(encoding="utf-8"))
                    if (
                        velocity.get("plan_id") == plan_id
                        and velocity.get("decision", {}).get("owner") == "maintainer"
                        and velocity.get("decision", {}).get("transition") == "implementation-authorized"
                        and _high_velocity_plan_authorize(root, velocity)
                    ):
                        return None
                except (OSError, UnicodeError, json.JSONDecodeError, TypeError):
                    pass
            minimal_receipts = sorted(plan_dir.glob("implementation-authorization-receipt.successor.v2.json"))
            if minimal_receipts:
                receipt_path = minimal_receipts[-1]
                try:
                    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                    required = ("implementation_contract", "command_registry", "authority_manifest", "review_input", "review_run", "review_candidate_binding", "conformance_result", "source_freeze", "requirements_mapping")
                    if (
                        receipt.get("plan_id") == plan_id
                        and receipt.get("decision", {}).get("owner") == "maintainer"
                        and receipt.get("decision", {}).get("transition") == "implementation-authorized"
                        and receipt.get("authorizes") == ["implementation-authorized"]
                        and receipt.get("schema_version") == "quick-dev-tdd-adapter.implementation-authorization-successor.v2"
                        and _review_and_conformance_authorize(root, receipt)
                        and all(_minimal_authorization_binding_is_current(plan_dir.resolve().parents[1], receipt.get(field)) for field in required)
                        and _candidate_commit_is_current(plan_dir.resolve().parents[1], plan_dir, receipt)
                    ):
                        return None
                except (OSError, UnicodeError, json.JSONDecodeError, TypeError):
                    pass
            if document["authorizes"] == ["implementation-authorized"]:
                return {
                    "next_action": "external-repair-required",
                    "reason": "invalid-plan-state",
                    "authorizes": [],
                }
            repair_state_path = plan_dir / "repair" / "round-1" / "repair-state.v1.json"
            try:
                repair_state = json.loads(repair_state_path.read_text(encoding="utf-8"))
                if (
                    repair_state.get("status") != "closed"
                    or repair_state.get("blocks_execution") is not False
                    or repair_state.get("authorizes") != []
                ):
                    return {
                        "next_action": "external-repair-required",
                        "reason": "repair-state-not-closed",
                        "authorizes": [],
                    }
            except (OSError, UnicodeError, json.JSONDecodeError, TypeError):
                return {
                    "next_action": "external-repair-required",
                    "reason": "repair-state-invalid",
                    "authorizes": [],
                }
            receipt_candidates = sorted([*plan_dir.glob("implementation-authorization-receipt.successor.v1.json"), *plan_dir.glob("implementation-authorization-receipt.successor.v2.json")])
            receipt_path = receipt_candidates[-1] if receipt_candidates else None
            if receipt_path is None:
                return {
                    "next_action": "awaiting-implementation-authorization",
                    "reason": "implementation-authorization-receipt-missing",
                    "authorizes": [],
                }
            try:
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                if receipt.get("schema_version") == "quick-dev-tdd-adapter.implementation-authorization-successor.v2":
                    if (
                        receipt.get("plan_id") == plan_id
                        and receipt.get("decision", {}).get("owner") == "maintainer"
                        and receipt.get("decision", {}).get("transition") == "implementation-authorized"
                        and receipt.get("authorizes") == ["implementation-authorized"]
                        and _review_and_conformance_authorize(root, receipt)
                        and _candidate_commit_is_current(root, plan_dir, receipt)
                        and all(_minimal_authorization_binding_is_current(root, receipt.get(field)) for field in ("implementation_contract", "command_registry", "authority_manifest", "review_input", "review_run", "review_candidate_binding", "conformance_result", "source_freeze", "requirements_mapping"))
                    ):
                        return None
                    raise ValueError("tree-bound authorization receipt is stale")
                if (
                    receipt.get("plan_id") != plan_id
                    or receipt.get("decision", {}).get("owner") != "maintainer"
                    or receipt.get("decision", {}).get("transition") != "implementation-authorized"
                    or receipt.get("authorizes") != ["implementation-authorized"]
                ):
                    raise ValueError("receipt metadata mismatch")
                legacy_bindings = (
                    "implementation_contract",
                    "command_registry",
                    "authority_manifest",
                    "knowledge_context",
                    "knowledge_context_freeze",
                    "plan_validation",
                    "repair_closure",
                    "bootstrap_preexisting_delta",
                    "candidate_manifest",
                    "validate_all",
                    "terminal_validator",
                    "immutable_predecessor",
                )
                bindings = legacy_bindings
                if "skill_input_generation" in receipt:
                    bindings = legacy_bindings
                    if not _skill_input_generation_is_current(root, receipt["skill_input_generation"]):
                        raise ValueError("skill input generation stale")
                else:
                    bindings = legacy_bindings + ("skill_input_receipt", "skill_input_request")
                for field in bindings:
                    binding = receipt.get(field)
                    if not isinstance(binding, dict):
                        raise ValueError("receipt binding missing")
                    if not _binding_is_current(root, binding):
                        raise ValueError("receipt binding stale")
            except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
                return {
                    "next_action": "awaiting-implementation-authorization",
                    "reason": "implementation-authorization-stale",
                    "authorizes": [],
                }
            return None
        return {
            "next_action": "external-repair-required",
            "reason": "invalid-plan-state",
            "authorizes": [],
        }
    if lifecycle_state in {"draft", "plan-ready"}:
        expected = [] if lifecycle_state == "draft" else ["plan-ready"]
        if document["authorizes"] != expected:
            return {
                "next_action": "external-repair-required",
                "reason": "invalid-plan-state",
                "authorizes": [],
            }
        return {
            "next_action": "awaiting-implementation-authorization",
            "reason": "implementation-authorization-required",
            "authorizes": [],
        }
    return {
        "next_action": "external-repair-required",
        "reason": "plan-state-precludes-slice-execution",
        "authorizes": [],
    }


def route(repository_root: Path, plan_dir: Path) -> dict[str, object]:
    execution_root = (repository_root / "execution-plans").resolve()
    target = plan_dir.resolve()
    try:
        target.relative_to(execution_root)
    except ValueError as exc:
        raise ValueError("plan directory must stay under execution-plans") from exc
    knowledge = _verify_plan_context(repository_root, target)
    if knowledge["status"] == "successor-required":
        return {"next_action": "refresh-knowledge-context", "reason": knowledge["failure_code"], "authorizes": []}
    if knowledge["status"] == "vdd-repair":
        return {"next_action": "external-repair-required", "reason": knowledge["failure_code"], "authorizes": []}
    contract_path = target / "implementation-contract.v1.json"
    contract_bytes = contract_path.read_bytes()
    contract = json.loads(contract_bytes.decode("utf-8"))
    try:
        registry = json.loads((target / "command-registry.v1.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        registry = {}
    contract_hash = "sha256:" + hashlib.sha256(contract_bytes).hexdigest()
    if not isinstance(contract.get("plan_id"), str) or not isinstance(contract.get("slices"), list):
        raise ValueError("implementation contract is invalid")
    reports = sorted(target.glob("95-*.md"), key=lambda item: item.name.casefold())
    if len(reports) > 1:
        return {"next_action": "external-repair-required", "reason": "ambiguous-plan-report", "authorizes": []}
    evidence_root = repository_root / "logs" / "tdd-adapter" / contract["plan_id"]
    state = evidence_root / "run-state.v1.json"
    if state.is_file():
        value = json.loads(state.read_text(encoding="utf-8"))
        if value.get("failure_fingerprint") and value.get("repeat_count", 0) >= 2:
            return {"next_action": "stop", "reason": "repeated-failure-fingerprint", "authorizes": []}
    completed: set[str] = set()
    for slice_item in contract["slices"]:
        slice_id = slice_item.get("slice_id")
        if not isinstance(slice_id, str):
            raise ValueError("slice id is invalid")
        execution_mode = slice_item.get("execution_mode", "tdd")
        exit_predicate = slice_item.get("exit_predicate", "slice-ready")
        if not isinstance(exit_predicate, str) or not exit_predicate:
            raise ValueError("slice exit predicate is invalid")
        result_paths = list((evidence_root / slice_id).glob(f"*/{exit_predicate}-result.json"))
        if execution_mode == "tdd" and exit_predicate == "slice-ready":
            # Formal TDD completion is owned only by canonical lifecycle run
            # roots. Isolated diagnostic namespaces are never promotable.
            result_paths = [
                path for path in result_paths
                if path.parent.name.startswith("RUN-") and "DIAGNOSTIC" not in path.parent.name.upper()
            ]
        else:
            result_paths = [path for path in result_paths if "DIAGNOSTIC" not in path.parent.name.upper()]
        if execution_mode in {"regression", "dogfood-replay"}:
            result_paths.append(target / "terminal-results" / f"{slice_id}.json")
        for result_path in result_paths:
            try:
                result = json.loads(result_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if execution_mode == "tdd" and exit_predicate == "slice-ready":
                current = _tdd_slice_ready_current(
                    repository_root, target, str(contract["plan_id"]), slice_id,
                    contract_hash, result_path, result,
                )
                if result.get("predicate") == exit_predicate and result.get("status") == "pass" and current:
                    completed.add(slice_id)
                    break
                continue
            contract_current = result.get("contract_hash") == contract_hash
            required_artifact = result_path.with_name("candidate-evidence.json") if exit_predicate == "implementation-candidate" else None
            current = contract_current
            if exit_predicate == "implementation-candidate":
                current = _implementation_candidate_current(
                    result, _validation_snapshot(target, slice_id)
                )
            elif all(key in result for key in _IMPLEMENTATION_CANDIDATE_ROOTS):
                # RMAP validation envelopes (including slice-ready) own
                # freshness through current roots rather than contract_hash.
                # Compare every root, not only the candidate hash, so a
                # control-plane authority update cannot be skipped.
                current = _implementation_candidate_current(
                    result,
                    _validation_snapshot(
                        target,
                        None if exit_predicate == "implementation-complete" else slice_id,
                    ),
                )
            elif not contract_current and isinstance(registry, dict):
                current = _unaffected_slice_current(
                    repository_root, target, contract, registry, result, slice_id
                )
            if (
                not current
                and exit_predicate == "slice-ready"
                and result.get("predicate") == "slice-ready"
                and (
                    validate_implementation_successor(result_path.parent)
                )
            ):
                # A completed implementation successor may remain valid across
                # a control-plane-only contract refresh. The lifecycle runner's
                # RED basis and successor receipt bind the unchanged test bytes;
                # do not require the old slice-ready projection to contain roots
                # it was never designed to emit.
                try:
                    basis = json.loads((result_path.parent / "red-basis.v1.json").read_text(encoding="utf-8"))
                    selector = next(item["tdd"]["red"]["test_selector"] for item in contract["slices"] if item.get("slice_id") == slice_id)
                    current = basis.get("test_selector") == selector and basis.get("test_sha256") == _sha((repository_root / selector).read_bytes())
                except (OSError, StopIteration, KeyError, TypeError, json.JSONDecodeError):
                    current = False
            if result.get("predicate") == exit_predicate and result.get("status") == "pass" and (contract.get("plan_id") != "quick-dev-tdd-stage-recovery" or (result.get("orchestration_version") == "stage-actions.v2" and _staged_refactor_complete(result_path))) and current and (required_artifact is None or required_artifact.is_file()):
                completed.add(slice_id)
                break
    for slice_item in contract["slices"]:
        slice_id = slice_item["slice_id"]
        execution_mode = slice_item.get("execution_mode", "tdd")
        if slice_id in completed:
            continue
        if not set(slice_item.get("depends_on", [])).issubset(completed):
            continue
        authorization_gate = _slice_authorization_gate(target, contract["plan_id"])
        if authorization_gate is not None:
            # Authorization is evaluated after dependency closure.  Preserve
            # the first unlocked slice so callers can distinguish an initial
            # wait from a wait before the next slice.
            authorization_gate["slice_id"] = slice_id
            return authorization_gate
        active_action = _active_slice_action(repository_root, target, slice_id)
        if active_action == "validate-slice":
            return {"next_action": "validate-slice", "slice_id": slice_id, "authorizes": []}
        if active_action == "implement":
            return {"next_action": "implement", "slice_id": slice_id, "authorizes": []}
        if execution_mode in {"regression", "dogfood-replay"}:
            return {"next_action": "validate-slice", "slice_id": slice_id, "execution_mode": execution_mode, "authorizes": []}
        return {"next_action": "run-slice", "slice_id": slice_id, "authorizes": []}
    if _terminal_completion_current(repository_root, target, contract_hash):
        return {"next_action": "implementation-complete", "authorizes": []}
    return {"next_action": "validate-terminal", "authorizes": []}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--caller", required=True)
    args = parser.parse_args()
    if args.caller != "quick-dev-tdd-adapter":
        parser.error("--caller must be quick-dev-tdd-adapter")
    print(json.dumps(route(args.repository_root.resolve(), args.plan_dir.resolve()), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
