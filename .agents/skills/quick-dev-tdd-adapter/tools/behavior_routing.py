"""ADR-0041: runtime CER disposition and scope projection in the current pipeline."""
from __future__ import annotations

from pathlib import Path
import sys

from runtime_evidence import hash_refs, load_json, sha256_value, sha256_bytes

SCHEMA = "quick-dev.behavior-route.v1"


def validate_plan(bundle):
    if "behavior_routing" not in bundle:
        return
    vdd = Path(__file__).resolve().parents[2] / "vdd-execution-plan/scripts"
    if str(vdd) not in sys.path:
        sys.path.insert(0, str(vdd))
    from semantic_behavior_contract import validate_routing_intent
    from quick_dev_handoff import handoff_findings
    findings = [*validate_routing_intent(bundle), *handoff_findings(bundle)]
    expected = {o["obligation_id"] for o in bundle["obligations"] if o.get("status") != "not_applicable"}
    covered = {e.get("obligation_id") for e in bundle["final_plan_coverage"]}
    if covered != expected:
        findings.append("behavior-routing:current-obligation-coverage-gap")
    if findings:
        raise ValueError(";".join(findings))


def intents_for(bundle, slice_id):
    validate_plan(bundle)
    selected = next(s for s in bundle["slices"] if s["slice_id"] == slice_id)
    aids = set(selected["acceptance_ids"])
    return [i for i in bundle["behavior_routing"]["intents"] if aids & set(i["acceptance_ids"])]


def production_hashes(workspace, bundle, slice_id):
    intents = intents_for(bundle, slice_id)
    index = {i["obligation_id"]: i for i in bundle["behavior_routing"]["intents"]}
    todo = [i["obligation_id"] for i in intents]
    seen, paths = set(), set()
    while todo:
        oid = todo.pop()
        if oid in seen:
            continue
        if oid not in index:
            # `depends_on` also carries non-runtime requirement/governance
            # labels in compiled plans.  They have no behavior intent or
            # production owner and therefore cannot widen the runtime hash
            # closure.  Only projected obligation IDs participate here.
            continue
        seen.add(oid)
        paths.update(index[oid]["production_owners"])
        todo.extend(dep for dep in index[oid]["depends_on"] if dep in index)
    return hash_refs(workspace, sorted(paths))


def derive_dispositions(bundle, descriptor, receipt):
    """A hypothesis is admitted only by all of the obligation's actual cases."""
    from case_evidence import assertion_cases
    rows = []
    assertions = descriptor["acceptance_assertions"]
    for intent in intents_for(bundle, descriptor["slice_id"]):
        keys = {(a["acceptance_id"], a["assertion_id"]) for a in assertions
                if a["acceptance_id"] in intent["acceptance_ids"]}
        disposition, reason, cases = "unverifiable", "assertion-binding-gap", {}
        if keys:
            for expected, value in (("pass", "present"), ("red", "missing")):
                try:
                    if receipt.get("exit_code") not in {0, 1} or receipt.get("timed_out") or receipt.get("repo_noise_paths"):
                        raise ValueError("probe-environment-or-process-gap")
                    cases = assertion_cases(descriptor, receipt, keys=keys, expected=expected)
                    disposition, reason = value, "observed-cases"
                    break
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    reason = str(exc)
        rows.append({"obligation_id": intent["obligation_id"], "disposition": disposition,
                     "reason": reason, "acceptance_ids": intent["acceptance_ids"],
                     "cases": [{"acceptance_id": a, "assertion_id": s, "case_ids": nodes}
                               for (a, s), nodes in sorted(cases.items())] if disposition != "unverifiable" else []})
    return rows


def read_route(workspace, bundle, run_root, slice_id, *, current_production=False):
    descriptor = load_json(run_root / "descriptors/probe.json")
    base = run_root / "canonical-evidence/probe"
    receipt = load_json(base / "process-receipt.v2.json")
    observation = load_json(base / "observation.v2.json")
    result = load_json(base / "stage-result.v2.json")
    if (descriptor.get("stage") != "probe" or descriptor.get("run_id") != run_root.name
            or descriptor.get("slice_id") != slice_id or descriptor.get("plan_id") != bundle["plan_id"]
            or result.get("behavior_plan_sha256") != sha256_value(bundle)
            or result.get("descriptor_sha256") != sha256_value(descriptor)
            or result.get("receipt_sha256") != sha256_value(receipt)
            or result.get("observation_sha256") != sha256_value(observation)
            or observation.get("receipt_sha256") != sha256_value(receipt)
            or result.get("predicate_result") is not True or observation.get("predicate_result") is not True):
        raise ValueError("behavior-routing:stale-probe")
    for name in ("stdout", "stderr"):
        if sha256_bytes((base / (name + ".bin")).read_bytes()) != receipt.get(name + "_sha256"):
            raise ValueError("behavior-routing:stale-probe-output")
    if (hash_refs(workspace, descriptor["target_refs"]) != receipt.get("target_hashes")
            or hash_refs(workspace, descriptor["fixture_refs"]) != receipt.get("fixture_hashes")):
        raise ValueError("behavior-routing:probe-selector-or-fixture-changed")
    rows = derive_dispositions(bundle, descriptor, receipt)
    if rows != result.get("behavior_dispositions") or any(x["disposition"] == "unverifiable" for x in rows):
        raise ValueError("behavior-routing:unverifiable-or-mutated-disposition")
    if current_production and result.get("production_hashes") != production_hashes(workspace, bundle, slice_id):
        raise ValueError("behavior-routing:probe-production-changed")
    return result


def stage_assertions(bundle, slice_id, stage, route=None):
    aids = set(next(s for s in bundle["slices"] if s["slice_id"] == slice_id)["acceptance_ids"])
    if stage not in {"probe", "terminal"}:
        if not route:
            raise ValueError("behavior-routing:observed-probe-required")
        disposition = "present" if stage == "regression" else "missing"
        aids &= {a for row in route["behavior_dispositions"] if row["disposition"] == disposition for a in row["acceptance_ids"]}
    return {(a["acceptance_id"], sid) for a in bundle["acceptances"] if a["acceptance_id"] in aids for sid in a["assertion_ids"]}


def stage_map(bundle, slice_id, route):
    result = {}
    for row in route["behavior_dispositions"]:
        stages = ("red", "green", "refactor") if row["disposition"] == "missing" else ("regression",)
        if row["disposition"] not in {"missing", "present"}:
            raise ValueError("behavior-routing:unverifiable")
        for aid in row["acceptance_ids"]:
            result[aid] = stages
    expected = {a for a, _ in stage_assertions(bundle, slice_id, "terminal")}
    if set(result) != expected:
        raise ValueError("behavior-routing:stage-universe")
    return result


def verify_stage(workspace, bundle, run_root, descriptor, *, require_probe_current=True):
    """No user/model-authored disposition can bypass current probe rereading."""
    if "behavior_routing" not in bundle:
        if descriptor["stage"] in {"probe", "regression"} or "behavior_route" in descriptor:
            raise ValueError("behavior-routing:planning-capability-required")
        return None
    validate_plan(bundle)
    stage = descriptor["stage"]
    binding = descriptor.get("behavior_route")
    if not isinstance(binding, dict) or set(binding) != {"schema", "probe_result_sha256"} or binding.get("schema") != SCHEMA:
        raise ValueError("behavior-routing:descriptor-capability-missing")
    route = None if stage == "probe" else read_route(workspace, bundle, run_root, descriptor["slice_id"], current_production=require_probe_current and stage == "red")
    if binding["probe_result_sha256"] != (sha256_value(route) if route else None):
        raise ValueError("behavior-routing:descriptor-probe-binding")
    expected = stage_assertions(bundle, descriptor["slice_id"], stage, route)
    actual = {(a["acceptance_id"], a["assertion_id"]) for a in descriptor["acceptance_assertions"]}
    if not expected or actual != expected:
        raise ValueError("behavior-routing:stage-assertion-universe")
    if route and stage != "terminal":
        probe_descriptor = load_json(run_root / "descriptors/probe.json")
        for field in ("argv", "cwd", "target_refs", "fixture_refs"):
            if descriptor[field] != probe_descriptor[field]:
                raise ValueError("behavior-routing:probe-selector-drift")
        probe_bindings = {(r["acceptance_id"], r["assertion_id"]): r for r in probe_descriptor["case_contract"]["bindings"]}
        if any(r != probe_bindings.get((r["acceptance_id"], r["assertion_id"])) for r in descriptor["case_contract"]["bindings"]):
            raise ValueError("behavior-routing:probe-case-mapping-drift")
    return route


def verify_case_continuity(descriptor, receipt, route):
    if route and descriptor["stage"] != "terminal":
        from case_evidence import assertion_cases
        expected = {(c["acceptance_id"], c["assertion_id"]): c["case_ids"] for r in route["behavior_dispositions"] for c in r["cases"]}
        actual = assertion_cases(descriptor, receipt)
        if actual != {k: expected[k] for k in actual}:
            raise ValueError("behavior-routing:probe-case-set-drift")


def current_result(workspace, bundle, slice_id, result):
    if result.get("behavior_plan_sha256") != sha256_value(bundle) or result.get("production_hashes") != production_hashes(workspace, bundle, slice_id):
        raise ValueError("behavior-routing:current-production-or-plan-stale")


def next_action(workspace, bundle, run_root, route):
    """Recommend from explicit artifacts only; the executing gate rechecks authority."""
    rows = route["behavior_dispositions"]
    stages = []
    if any(r["disposition"] == "missing" for r in rows):
        stages.extend([("red", "run-red"), ("green", "implement"), ("refactor", "run-refactor")])
    if any(r["disposition"] == "present" for r in rows):
        stages.append(("regression", "run-regression"))
    for stage, action in stages:
        path = run_root / "canonical-evidence" / stage / "stage-result.v2.json"
        if not path.is_file():
            return action
        result = load_json(path)
        if result.get("predicate_result") is not True:
            return "repair-vdd"
        if stage in {"refactor", "regression"}:
            try:
                current_result(workspace, bundle, route["slice_id"], result)
            except ValueError:
                return "author-red"  # Fresh run/probe; never overwrite old proof.
    return "validate-slice"
