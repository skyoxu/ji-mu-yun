"""Independent observation/classification trust zone."""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from runtime_evidence import create_json, sha256_bytes, sha256_value, selector_identity_from_descriptor, validate_descriptor

HARNESS_RE = re.compile(r"ERROR collecting|collected 0 items|no tests ran|ImportError while importing test module|ModuleNotFoundError", re.I)


def normalized_failure_fingerprint(*, descriptor: Mapping[str, Any], receipt: Mapping[str, Any], family: str, observed_failure_ids: Sequence[str], expected_failure_ids: Sequence[str]) -> str:
    """Hash only stable semantic failure inputs, never run timing/output-byte noise."""
    observed_assertions = receipt.get("observed_assertion_ids", [])
    if not isinstance(observed_assertions, list):
        observed_assertions = []
    return sha256_value({
        "taxonomy":"quick-dev.failure-taxonomy.v1",
        "family":family,
        "selector_identity":selector_identity_from_descriptor(descriptor),
        "candidate_hash":receipt.get("candidate_hash"),
        "stage":receipt.get("stage"),
        "exit_code":receipt.get("exit_code"),
        "timed_out":receipt.get("timed_out"),
        "test_executions":receipt.get("test_executions"),
        "cases":receipt.get("cases"),
        "target_hashes":receipt.get("target_hashes",{}),
        "fixture_hashes":receipt.get("fixture_hashes",{}),
        "acceptance_assertions":descriptor.get("acceptance_assertions",[]),
        "observed_assertion_ids":sorted(set(str(x) for x in observed_assertions)),
        "observed_failure_ids":sorted(set(observed_failure_ids)),
        "expected_failure_ids":sorted(set(expected_failure_ids)),
    })


def judge_receipt(run_dir: Path, stage: str, descriptor: Mapping[str, Any], receipt: Mapping[str, Any], *, expected_failure_ids: Sequence[str] = (), probe_dispositions=None, behavior_route=None) -> dict[str, Any]:
    evidence = run_dir.resolve()/"canonical-evidence"/stage; integrity_error=False
    try:
        validate_descriptor(descriptor)
        if descriptor["stage"] != stage or receipt.get("schema") != "quick-dev.process-receipt.v2" or receipt.get("stage") != stage: raise ValueError
        if receipt.get("descriptor_sha256") != sha256_value(dict(descriptor)) or receipt.get("candidate_hash") != descriptor["candidate_hash"]: raise ValueError
        if receipt.get("argv") != descriptor["argv"] or receipt.get("cwd") != descriptor["cwd"]: raise ValueError
        stdout_path,stderr_path=evidence/"stdout.bin",evidence/"stderr.bin"
        if not stdout_path.is_file() or not stderr_path.is_file(): raise ValueError
        if sha256_bytes(stdout_path.read_bytes()) != receipt.get("stdout_sha256") or sha256_bytes(stderr_path.read_bytes()) != receipt.get("stderr_sha256"): raise ValueError
    except (OSError,ValueError): integrity_error=True
    stdout=(evidence/"stdout.bin").read_bytes() if (evidence/"stdout.bin").is_file() else b""; stderr=(evidence/"stderr.bin").read_bytes() if (evidence/"stderr.bin").is_file() else b""
    output=(stdout+b"\n"+stderr).decode("utf-8",errors="replace"); observed=sorted(set(receipt.get("observed_failure_ids",[]))) if isinstance(receipt.get("observed_failure_ids"),list) else []
    declared=sorted(set(expected_failure_ids)); exit_code=receipt.get("exit_code"); timed_out=receipt.get("timed_out") is True; executions=receipt.get("test_executions"); cases=receipt.get("cases"); pre_error=receipt.get("pre_execution_error_code"); evidence_state="observed-run"
    from case_evidence import assertion_cases, reread_stage_cases
    case_error = None
    try:
        if stage == "probe":
            if not probe_dispositions or any(r["disposition"] == "unverifiable" for r in probe_dispositions):
                raise ValueError("behavior-routing:unverifiable:" + str(probe_dispositions))
            mapped_cases = {}
        else:
            mapped_cases = assertion_cases(descriptor, receipt)
            from behavior_routing import verify_case_continuity
            verify_case_continuity(descriptor, receipt, behavior_route)
        if stage in {"green", "refactor"} and mapped_cases != reread_stage_cases(run_dir, "red"):
            raise ValueError("case-set-changed-since-red")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        case_error = str(exc)
    if integrity_error or pre_error=="ARTIFACT_INTEGRITY": outcome,family,predicate,evidence_state="blocked","artifact-integrity",False,"invalid-run"
    elif pre_error=="TARGET_BINDING": outcome,family,predicate="blocked","target-binding-failure",False
    elif isinstance(receipt.get("repo_noise_paths"),list) and receipt.get("repo_noise_paths"): outcome,family,predicate="blocked","repo-noise",False
    elif timed_out: outcome,family,predicate="blocked","timeout-no-observation",False
    elif HARNESS_RE.search(output) or not isinstance(exit_code,int) or not isinstance(executions,int) or executions<1 or not isinstance(cases,int) or cases<1: outcome,family,predicate="blocked","test-harness-failure",False
    elif stage=="red" and exit_code==0: outcome,family,predicate="fail","unexpected-green",False
    elif case_error is not None: outcome,family,predicate="blocked","semantic-contract-gap",False
    elif stage=="probe": outcome,family,predicate="pass",None,True
    elif stage=="red" and declared and observed==declared and exit_code!=0: outcome,family,predicate="fail","expected-red",True
    elif stage=="red": outcome,family,predicate="fail","semantic-contract-gap",False
    elif exit_code==0: outcome,family,predicate="pass",None,True
    else: outcome,family,predicate="fail","task-implementation-failure",False
    failure_fingerprint=None if family is None else normalized_failure_fingerprint(descriptor=descriptor,receipt=receipt,family=family,observed_failure_ids=observed,expected_failure_ids=declared)
    failure_id=None if family is None else f"QD-{family.upper().replace('_','-')}-{failure_fingerprint[7:23].upper()}"
    observation={
        "schema":"quick-dev.observation.v2","observation_id":f"OBS-{stage.upper()}-{sha256_value(dict(receipt))[7:19].upper()}","receipt_ref":f"canonical-evidence/{stage}/process-receipt.v2.json","receipt_sha256":sha256_value(dict(receipt)),
        "stage":stage,"evidence_state":evidence_state,"verification_outcome":outcome,"process_attempts":receipt.get("process_attempts",0),"test_executions":executions if isinstance(executions,int) else 0,"cases":cases if isinstance(cases,int) else 0,
        "exit_code":exit_code,"timed_out":timed_out,"failure_family":family,"failure_id":failure_id,"failure_fingerprint":failure_fingerprint,"observed_failure_ids":observed,"observed_assertion_ids":receipt.get("observed_assertion_ids",[]),"expected_failure_ids":declared,"predicate_result":predicate,"judge_identity":"quick-dev-independent-judge.v2",
    }
    observation["case_evidence_error"] = case_error
    create_json(evidence/"observation.v2.json",observation); return observation
