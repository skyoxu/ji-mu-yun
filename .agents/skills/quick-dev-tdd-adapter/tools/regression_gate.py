"""Deterministic Q6 regression/schema validation gate."""
from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Any, Mapping, Sequence

from current_router import profile_contract
from process_executor_v2 import _counts
from runtime_evidence import create_json,sha256_bytes


def _context(bundle:Mapping[str,Any],slice_id:str)->Mapping[str,Any]|None:
    contexts=bundle.get("agent_contexts")
    if not isinstance(contexts,list):
        return None
    matches=[item for item in contexts if isinstance(item,Mapping) and item.get("slice_id")==slice_id]
    if len(matches)>1:
        raise ValueError("agent context slice identity ambiguous")
    return matches[0] if matches else None


def run_regression_gate(*,workspace:Path,bundle:Mapping[str,Any],slice_id:str,profile:str,primary_argv:Sequence[str],primary_receipt:Mapping[str,Any],timeout_seconds:int,out:Path)->dict[str,Any]:
    """Run declared Q6 validations after the primary REFACTOR selector passed."""
    policy=profile_contract(profile)
    required=policy.get("regression_required") is True
    context=_context(bundle,slice_id)
    commands=context.get("validation_commands") if isinstance(context,Mapping) else []
    if commands is None:
        commands=[]
    if not isinstance(commands,list) or any(not isinstance(cmd,list) or not cmd or any(not isinstance(part,str) or not part for part in cmd) for cmd in commands):
        raise ValueError("Q6 validation_commands invalid")
    primary=list(primary_argv)
    declared=[list(cmd) for cmd in commands]
    if required and context is None:
        raise ValueError("Q6 standard/self-hosted profile requires agent-context regression projection")
    # fast-ship keeps the primary selector truth floor but explicitly omits
    # additional agent-context regression commands.  Standard/self-hosted
    # retain the complete declared command set.
    commands_to_run = declared if required else [argv for argv in declared if argv == primary]
    records=[]
    for argv in commands_to_run:
        if argv==primary:
            executions=primary_receipt.get("test_executions")
            cases=primary_receipt.get("cases")
            if primary_receipt.get("timed_out") is True or primary_receipt.get("exit_code")!=0 or not isinstance(executions,int) or executions<1 or not isinstance(cases,int) or cases<1:
                raise ValueError("Q6 primary refactor selector is not admissible regression evidence")
            records.append({"argv":argv,"status":"covered-by-primary-refactor-selector","exit_code":0,"timed_out":False,"test_executions":executions,"cases":cases,"stdout_sha256":primary_receipt.get("stdout_sha256"),"stderr_sha256":primary_receipt.get("stderr_sha256")})
            continue
        try:
            proc=subprocess.run(argv,cwd=workspace,shell=False,check=False,capture_output=True,timeout=timeout_seconds)
            stdout,stderr=proc.stdout,proc.stderr
            timed_out=False; exit_code=proc.returncode
        except subprocess.TimeoutExpired as exc:
            stdout,stderr=exc.stdout or b"",exc.stderr or b""; timed_out=True; exit_code=None
            if isinstance(stdout,str): stdout=stdout.encode("utf-8",errors="replace")
            if isinstance(stderr,str): stderr=stderr.encode("utf-8",errors="replace")
        text=(stdout+b"\n"+stderr).decode("utf-8",errors="replace")
        pytest_like=any("pytest" in part.lower() for part in argv)
        executions,cases=_counts(text,timed_out=timed_out) if pytest_like else (None,None)
        passed=(not timed_out and exit_code==0 and (not pytest_like or (isinstance(executions,int) and executions>=1 and isinstance(cases,int) and cases>=1)))
        records.append({"argv":argv,"status":"pass" if passed else "fail","exit_code":exit_code,"timed_out":timed_out,"test_executions":executions,"cases":cases,"stdout_sha256":sha256_bytes(stdout),"stderr_sha256":sha256_bytes(stderr)})
        if not passed:
            raise ValueError("Q6 regression/schema command failed")
    if required and not declared:
        raise ValueError("Q6 regression-required profile has no validation commands")
    result={"schema":"quick-dev.q6-regression-gate.v1","slice_id":slice_id,"profile":profile,"regression_required":required,"declared_command_count":len(declared),"commands":records,"status":"pass","authorizes":[]}
    create_json(out,result)
    return result
