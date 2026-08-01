from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


EXPECTED_SHA256 = "91e795353f0df8e19433753fb355e9a95fd0eadf891685ceddf213cba02fe4a9"
SOURCE = ".agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_core.py"
DEFAULT_OUTPUT = "repair/round-1/baseline-overlays/acceptance_core.py"


def replace_once(text: str, current: str, baseline: str) -> str:
    if text.count(current) != 1:
        raise ValueError("candidate extension block is missing or ambiguous")
    return text.replace(current, baseline, 1)


def materialize(repository_root: Path, output: Path) -> str:
    source = repository_root / SOURCE
    text = source.read_text(encoding="utf-8")
    text = replace_once(text, '_CODE_REVIEW_DOMAINS = {"phase_service", "toolchain"}\n', "")
    text = replace_once(
        text,
        '    if parsed.get("code_review_domain") not in _CODE_REVIEW_DOMAINS:\n',
        '    if parsed.get("code_review_domain") != "phase_service":\n',
    )
    text = replace_once(
        text,
        "    # Every path component was checked for links/reparse points above. Keep the\n"
        "    # lexical absolute spelling so Windows 8.3 temp roots do not compare\n"
        "    # unequal to their expanded spelling after Path.resolve().\n"
        "    target_root = target_root.absolute()\n"
        "    snapshot_root = unresolved_snapshot_root.absolute()\n",
        "    snapshot_root = unresolved_snapshot_root.resolve()\n",
    )
    current = '''def validate_policy_pack(value: Any) -> None:
    if not isinstance(value, dict) or value.get("schemaVersion") != "code-review-policy-pack.v1":
        raise InputError("policy pack schemaVersion is invalid")
    required = {"schemaVersion", "policyId", "targetDomain", "authorityRefs", "checks", "policyRevision"}
    if set(value) not in {frozenset(required), frozenset(required | {"pathRules"})}:
        raise InputError("policy pack fields are invalid")
    identities = {
        "phase_service": ("phase-service-code-review", "PHASE-CR-"),
        "toolchain": ("toolchain-code-review", "TOOLCHAIN-CR-"),
    }
    target_domain = value.get("targetDomain")
    identity = identities.get(target_domain)
    if identity is None or value.get("policyId") != identity[0]:
        raise InputError("policy pack identity is invalid")
    path_rules = value.get("pathRules")
    if target_domain == "toolchain":
        if not isinstance(path_rules, dict) or set(path_rules) != {"ownedPrefixes", "crossDomainPaths"}:
            raise InputError("toolchain policy path rules are invalid")
        owned = path_rules.get("ownedPrefixes")
        cross_domain = path_rules.get("crossDomainPaths")
        if (
            not isinstance(owned, list) or not owned
            or not isinstance(cross_domain, list) or not cross_domain
            or any(not isinstance(path, str) or not path for path in [*owned, *cross_domain])
            or len(owned) != len(set(owned))
            or len(cross_domain) != len(set(cross_domain))
        ):
            raise InputError("toolchain policy path rules are invalid")
    elif path_rules is not None:
        raise InputError("Phase policy cannot declare toolchain path rules")
    revision = value.get("policyRevision")
    core = {key: item for key, item in value.items() if key != "policyRevision"}
    if revision != canonical_hash(core):
        raise InputError("policy pack revision is stale")
    checks = value.get("checks")
    if not isinstance(checks, list) or not checks:
        raise InputError("policy pack checks are invalid")
    if any(not isinstance(item, dict) or set(item) != {"policyCheckId", "evaluationMode"} for item in checks):
        raise InputError("policy pack check fields are invalid")
    ids = [item.get("policyCheckId") for item in checks if isinstance(item, dict)]
    if len(ids) != len(checks) or len(set(ids)) != len(ids) or any(not isinstance(item, str) or not item.startswith(identity[1]) for item in ids):
        raise InputError("policy pack check ids are invalid")
    if any(item.get("evaluationMode") not in {"deterministic", "review_gate", "hybrid", "conditional_gate"} for item in checks):
        raise InputError("policy pack evaluation mode is invalid")


def resolve_code_review_policy(policy: Any, candidate_manifest: Any, baseline_manifest: Any, adapter_hash: str) -> dict[str, Any]:
    validate_policy_pack(policy)
    validate_candidate_manifest(candidate_manifest, baseline_manifest)
    _hash(adapter_hash, "adapter_hash")
    paths = [_normalized_relative(path, "Changed path") for path in candidate_changed_paths(candidate_manifest)]
    cross_domain_paths: list[str] = []
    if policy["targetDomain"] == "phase_service":
        triggered_paths = phase_changed_paths(candidate_manifest)
        external_paths = sorted(path for path in paths if path not in triggered_paths)
        if external_paths and not triggered_paths:
            raise InputError("unsupported_code_review_domain")
        if not triggered_paths:
            raise InputError("phase policy was not triggered")
    else:
        rules = policy["pathRules"]
        owned = tuple(rules["ownedPrefixes"])
        cross_domain = set(rules["crossDomainPaths"])
        triggered_paths = sorted(
            path for path in paths if path.startswith(owned) or path in cross_domain
        )
        uncovered = sorted(path for path in paths if path not in triggered_paths)
        if uncovered:
            raise InputError("toolchain policy changed-path coverage is incomplete")
        if not triggered_paths:
            raise InputError("toolchain policy was not triggered")
        external_paths = []
        cross_domain_paths = sorted(path for path in triggered_paths if path in cross_domain)
    binding = {"schemaVersion": "code-review-policy-binding.v1", "policyId": policy["policyId"], "policyRevision": policy["policyRevision"], "policyHash": canonical_hash(policy), "candidateManifestHash": canonical_hash(candidate_manifest), "adapterHash": adapter_hash, "triggeredPaths": triggered_paths, "unreviewedExternalDomainPaths": external_paths, "activatedCheckIds": [item["policyCheckId"] for item in policy["checks"]], "authorizes": []}
    if policy["targetDomain"] == "toolchain":
        binding["crossDomainDependencyPaths"] = cross_domain_paths
    binding["bindingHash"] = canonical_hash(binding)
    return binding


def resolve_phase_policy(policy: Any, candidate_manifest: Any, baseline_manifest: Any, adapter_hash: str) -> dict[str, Any]:
    """Backward-compatible Phase policy entrypoint."""
    if isinstance(policy, dict) and policy.get("targetDomain") != "phase_service":
        raise InputError("phase policy entrypoint requires phase_service")
    return resolve_code_review_policy(policy, candidate_manifest, baseline_manifest, adapter_hash)
'''
    baseline = '''def validate_policy_pack(value: Any) -> None:
    if not isinstance(value, dict) or value.get("schemaVersion") != "code-review-policy-pack.v1":
        raise InputError("policy pack schemaVersion is invalid")
    if set(value) != {"schemaVersion", "policyId", "targetDomain", "authorityRefs", "checks", "policyRevision"}:
        raise InputError("policy pack fields are invalid")
    if value.get("policyId") != "phase-service-code-review" or value.get("targetDomain") != "phase_service":
        raise InputError("policy pack identity is invalid")
    revision = value.get("policyRevision")
    core = {key: item for key, item in value.items() if key != "policyRevision"}
    if revision != canonical_hash(core):
        raise InputError("policy pack revision is stale")
    checks = value.get("checks")
    if not isinstance(checks, list) or not checks:
        raise InputError("policy pack checks are invalid")
    if any(not isinstance(item, dict) or set(item) != {"policyCheckId", "evaluationMode"} for item in checks):
        raise InputError("policy pack check fields are invalid")
    ids = [item.get("policyCheckId") for item in checks if isinstance(item, dict)]
    if len(ids) != len(checks) or len(set(ids)) != len(ids) or any(not isinstance(item, str) or not item.startswith("PHASE-CR-") for item in ids):
        raise InputError("policy pack check ids are invalid")
    if any(item.get("evaluationMode") not in {"deterministic", "review_gate", "hybrid", "conditional_gate"} for item in checks):
        raise InputError("policy pack evaluation mode is invalid")


def resolve_phase_policy(policy: Any, candidate_manifest: Any, baseline_manifest: Any, adapter_hash: str) -> dict[str, Any]:
    validate_policy_pack(policy)
    validate_candidate_manifest(candidate_manifest, baseline_manifest)
    _hash(adapter_hash, "adapter_hash")
    paths = [_normalized_relative(path, "Changed path") for path in candidate_changed_paths(candidate_manifest)]
    phase_paths = phase_changed_paths(candidate_manifest)
    external_paths = sorted(path for path in paths if path not in phase_paths)
    if external_paths and not phase_paths:
        raise InputError("unsupported_code_review_domain")
    if not phase_paths:
        raise InputError("phase policy was not triggered")
    binding = {"schemaVersion": "code-review-policy-binding.v1", "policyId": policy["policyId"], "policyRevision": policy["policyRevision"], "policyHash": canonical_hash(policy), "candidateManifestHash": canonical_hash(candidate_manifest), "adapterHash": adapter_hash, "triggeredPaths": phase_paths, "unreviewedExternalDomainPaths": external_paths, "activatedCheckIds": [item["policyCheckId"] for item in policy["checks"]], "authorizes": []}
    binding["bindingHash"] = canonical_hash(binding)
    return binding
'''
    text = replace_once(text, current, baseline)
    payload = text.encode("utf-8")
    observed = hashlib.sha256(payload).hexdigest()
    if observed != EXPECTED_SHA256:
        raise ValueError(f"reconstructed baseline hash mismatch: {observed}")
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and output.read_bytes() != payload:
        raise ValueError("existing baseline overlay differs from reconstructed bytes")
    output.write_bytes(payload)
    return observed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.repository_root.resolve()
    target = root / "execution-plans/2026-08-01-workflow-model-routing-control-plane"
    output = args.output.resolve() if args.output else target / DEFAULT_OUTPUT
    observed = materialize(root, output)
    print(f"sha256:{observed} {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
