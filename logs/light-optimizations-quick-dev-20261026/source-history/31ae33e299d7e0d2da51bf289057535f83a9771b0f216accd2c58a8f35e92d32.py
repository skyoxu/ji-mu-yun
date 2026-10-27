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


def inspect_admission(sc, root, requirements, companions=(), *, profile="standard",
                      execution_profile="standard", recovery=None):
    """ADR-0041: compose owning read-only checks; future contracts stay pending.

    This result never publishes a plan or evaluates execution proof. An unfinished
    native recovery still revalidates its content caches at their owning stages.
    """
    import ast
    root = Path(root).resolve()
    checks = {name: {"status": "pending"} for name in
              ("inputs", "recovery", "dependencies", "quick_dev")}
    checks["recovery"] = {"status": "not-selected"}
    findings = []
    result = {"schema": "vdd.admission.v1", "plan_profile": profile,
              "execution_profile": execution_profile, "checks": checks,
              "findings": findings, "authorizes": []}
    try:
        if profile not in {"standard", "resumable", "self-hosted"}:
            raise ValueError("VDD plan-shape profile is invalid")
        for raw in [requirements, *companions]:
            path = Path(raw)
            path.resolve().relative_to(root)
            if path.is_symlink() or not path.is_file():
                raise ValueError("source is missing or unsafe: " + str(path))
        source = sc.build_source_index(root, Path(requirements), companions)
        source_result = sc.source_preflight(root, source)
        checks["inputs"] = {"status": "passed" if source_result["valid"] else "blocked",
                            "source_index_sha256": source["sha256"],
                            "findings": source_result["findings"]}
        if not source_result["valid"]:
            raise ValueError("source preflight failed")
        tools = root / ".agents/skills/quick-dev-tdd-adapter/tools"
        # Do not execute the public CLI, import tests, or probe the environment.
        # Resolve the real entry and the same consumer-owned pure reader instead.
        for path in (root / "scripts/quick_dev/run.py", tools / "stable_runner.py",
                     tools / "q1_planned_preflight.py"):
            if path.is_symlink() or not path.is_file():
                raise ValueError("Quick Dev entry is missing or unsafe: " + str(path))
            ast.parse(path.read_text(encoding="utf-8-sig"))
        if str(tools) not in sys.path:
            sys.path.insert(0, str(tools))
        from current_router import profile_contract
        from q1_planned_preflight import validate_planned_preflight
        profile_contract(execution_profile)
        checks["quick_dev"] = {"status": "passed", "entry": "scripts/quick_dev/run.py",
                               "consumer": "validate_planned_preflight"}
        if recovery is not None:
            recovery = Path(recovery)
            recovery.resolve().relative_to(root)
            if recovery.is_symlink() or not recovery.is_dir():
                raise ValueError("selected recovery is missing or unsafe")
            from semantic_compiler_gate import _completed_resume
            from semantic_compiler_authority import _published_recall_matches_obligations
            from semantic_chain_audit import audit_bundle
            completed = _completed_resume(recovery, source_index_sha256=source["sha256"], profile=profile)
            if completed is None:
                # A partial candidate is not current plan authority. Syntax-check
                # explicit current state if present; native caches retain ownership.
                state = recovery / "compiler-state.v1.json"
                if state.exists():
                    value = json.loads(state.read_text(encoding="utf-8"))
                    if not isinstance(value, dict):
                        raise ValueError("selected recovery state is malformed")
                    if value.get("state") == "plan-ready":
                        raise ValueError("selected completed recovery is missing required artifacts")
                checks["recovery"] = {"status": "pending", "reason": "native-candidate-revalidation-required"}
            else:
                if completed.get("status") != "plan-ready":
                    raise ValueError(completed.get("reason", "selected recovery is invalid"))
                if not _published_recall_matches_obligations(recovery):
                    raise ValueError("selected recovery source recall is invalid")
                bundle = json.loads((recovery / "semantic-plan-bundle.v1.json").read_text(encoding="utf-8"))
                audit = audit_bundle(bundle)
                if not audit["valid"]:
                    raise ValueError("selected recovery semantic chain is invalid")
                for item in bundle["slices"]:
                    validate_planned_preflight(workspace=root, bundle=bundle,
                        slice_id=item["slice_id"], timeout_seconds=1800, plan_dir=recovery)
                checks["recovery"] = {"status": "passed", "plan_id": bundle["plan_id"]}
                checks["dependencies"] = {"status": "passed", "scope": "selected-materialized-plan"}
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, ImportError, SyntaxError) as exc:
        findings.append(str(exc))
    result["status"] = ("blocked" if findings else "pending" if
                        any(check["status"] == "pending" for check in checks.values()) else "passed")
    return result
