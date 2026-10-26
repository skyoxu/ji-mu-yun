"""ADR-0041: deterministic projected-candidate checks before V4 alignment.

No tests or publication. Final gates still check the candidate after semantic
repair. Diagnostics cannot authorize Quick Dev or manufacture behavioral RED.
"""
from copy import deepcopy
import json
from pathlib import Path
import sys


def inspect_candidate(sc, root, obligations, acceptances, failures, hints, *, profile="standard"):
    from semantic_behavior_contract import SCHEMA, project_deferred, project_intents
    from quick_dev_handoff import handoff_findings
    findings, warnings = [], []
    try:
        # Legacy partition adapters may mutate their inputs. Preview on copies.
        obligations, acceptances, failures, hints = deepcopy((obligations, acceptances, failures, hints))
        edges = sc.exact_cover(obligations, acceptances, failures)
        slices, by_acceptance = sc.partition_slices(obligations, acceptances, failures, hints)
        bundle = {"schema_version": "vdd.semantic-plan-bundle.v1", "plan_id": "PREFLIGHT",
                  "profile": profile, "obligations": obligations, "acceptances": acceptances,
                  "failure_intents": failures, "pre_slice_coverage": edges, "slices": slices,
                  "final_plan_coverage": sc.final_cover(edges, slices),
                  "agent_contexts": sc.agent_contexts(slices, obligations, acceptances, by_acceptance)}
        bundle["behavior_routing"] = {"schema": SCHEMA, "intents": project_intents(bundle),
                                      "deferred": project_deferred(bundle)}
        findings.extend(sc.feasibility(root, slices, acceptances, failures, by_acceptance)["findings"])
        findings.extend(sc.validate_semantic_bundle(bundle)[1])
        findings.extend(handoff_findings(bundle, workspace=root))
        tools = Path(__file__).resolve().parents[2] / "quick-dev-tdd-adapter" / "tools"
        if str(tools) not in sys.path:
            sys.path.insert(0, str(tools))
        from q1_planned_preflight import validate_planned_preflight
        for item in slices:
            validate_planned_preflight(workspace=root, bundle=bundle,
                slice_id=item["slice_id"], timeout_seconds=1800)
        for item in slices:
            absent = sorted(owner for owner in item["production_owners"]
                            if owner in item["planned_new_files"] and not (root / owner).is_file())
            if absent:
                warnings.append({"slice_id": item["slice_id"], "code": "planned-production-first-use",
                                 "paths": absent, "owner": "quick-dev",
                                 "action": "Confirm a real behavioral RED route before implementation; Q2 cannot seed production."})
    except (ValueError, KeyError, TypeError) as exc:
        findings.append("candidate-projection:" + str(exc))
    return {"valid": not findings, "findings": sorted(set(findings)),
            "consumer_warnings": warnings, "authorizes": []}


def check_candidate(sc, root, out_dir, source_index, obligations, acceptances, failures, hints, *, profile="standard"):
    result = inspect_candidate(sc, root, obligations, acceptances, failures, hints, profile=profile)
    if result["findings"] or result["consumer_warnings"]:
        diagnostic = {"schema": "vdd.execution-preflight.v1", "source_index_sha256": source_index["sha256"],
                      "obligations": obligations, "acceptances": acceptances, "failure_intents": failures,
                      "slice_hints": hints, **result}
        digest = sc.sha256_value(diagnostic)
        path = out_dir / ".compiler-work" / "execution-preflight" / (digest[7:] + ".json")
        if not path.exists():
            sc.atomic_json(path, diagnostic)
        elif json.loads(path.read_text(encoding="utf-8")) != diagnostic:
            raise ValueError("execution preflight diagnostic collision")
        result["diagnostic"] = {"path": path.relative_to(out_dir).as_posix(), "sha256": digest}
    return result
