import importlib.util
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[3] / "tools"
spec = importlib.util.spec_from_file_location("validate_all", TOOLS / "validate_all.py")
validate_all = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validate_all)


def test_identity_is_stable_and_slice_bound():
    first = validate_all.current_candidate_identity("W0")
    second = validate_all.current_candidate_identity("W0")
    assert first == second
    assert first["candidate_hash"].startswith("sha256:")
    assert first["candidate_hash"] != validate_all.current_candidate_identity("W1")["candidate_hash"]
    assert {"candidate_hash", "predicate_input_root", "authority_root", "validator_root", "validator_version", "closure_definition_hash", "validator_hash"} <= set(first)


def test_aggregate_snapshot_contains_all_router_roots():
    snapshot = validate_all.validation_snapshot()
    assert {"candidate_hash", "predicate_input_root", "authority_root", "validator_root", "validator_version", "closure_definition_hash", "validator_hash"} == set(snapshot)


def test_unknown_slice_is_rejected():
    try:
        validate_all.current_candidate_identity("unknown")
    except ValueError as exc:
        assert "unknown slice" in str(exc)
    else:
        raise AssertionError("unknown slice was accepted")
