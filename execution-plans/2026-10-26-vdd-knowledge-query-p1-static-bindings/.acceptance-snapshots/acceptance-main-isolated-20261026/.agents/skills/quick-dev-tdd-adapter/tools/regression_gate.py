"""Deterministic Q6 regression/schema validation gate."""
from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Any, Mapping, Sequence

from current_router import profile_contract
from process_executor_v2 import _counts
from runtime_evidence import create_json,sha256_bytes,sha256_value


def _pytest_path_arguments(argv: Sequence[str]):
    """Keep expression/configuration values distinct from possible file inputs.

    Unknown options do not consume their next token: a real file dependency
    must not disappear merely because an option is unfamiliar. File operands
    such as ``-c pytest.ini`` remain eligible for the existing containment and
    dependency checks. This does not change argv, selection or reuse identity.
    """
    values = {"-k", "-m", "-o", "--override-ini", "--keyword", "--markexpr"}
    start = next(i for i, part in enumerate(argv) if part.lower() == "pytest")
    parts = iter(argv[start + 1:])
    positional = False
    for part in parts:
        if not positional and part == "--":
            positional = True
            continue
        if not positional and part in values:
            if next(parts, None) is None:
                raise ValueError(f"Q6 pytest option missing value: {part}")
            continue
        if positional or not part.startswith("-"):
            yield part.split("::", 1)[0]


def _terminal_scope_command(argv: Sequence[str]) -> bool:
    """Keep whole-tree pytest commands out of slice-local Q6.

    A command targeting a repository test directory (for example ``scripts/sc``)
    is terminal-plan validation, not evidence for the current slice.  Running
    it for every slice lets an unrelated failure reopen or block local work.
    """
    if not any(part.lower() == "pytest" for part in argv):
        return False
    targets = list(_pytest_path_arguments(argv))
    normalized = {Path(target).as_posix().rstrip("/") for target in targets}
    if normalized & {"scripts/sc", ".agents/skills/quick-dev-tdd-adapter/tools/tests"}:
        return True
    # The shared Acceptance/control-plane test tree is terminal validation,
    # not evidence owned by one product slice. Running it during every Q6
    # lets unrelated historical failures block local present-behavior work.
    if normalized & {
        ".agents/skills/run-refactor-implementation-acceptance/tests",
        ".agents/skills/run-refactor-implementation-acceptance",
        ".agents/skills/vdd-conformance-exact-cover/tests",
        ".agents/skills/vdd-conformance-exact-cover",
    }:
        return True
    # These shared consumer-contract suites are not owned by an individual
    # slice.  Running them as every slice's Q6 regression lets an unrelated
    # consumer failure reopen local work; they belong to terminal validation.
    # A single explicitly declared test file may be a slice fixture (S45 is
    # such a case); only the cross-slice candidate-review suite is deferred.
    return bool(normalized & {
        ".agents/skills/quick-dev-tdd-adapter/tools/tests/test_candidate_review_binding.py",
    })


def _context(bundle:Mapping[str,Any],slice_id:str)->Mapping[str,Any]|None:
    contexts=bundle.get("agent_contexts")
    if not isinstance(contexts,list):
        return None
    matches=[item for item in contexts if isinstance(item,Mapping) and item.get("slice_id")==slice_id]
    if len(matches)>1:
        raise ValueError("agent context slice identity ambiguous")
    return matches[0] if matches else None


def run_regression_gate(*,workspace:Path,bundle:Mapping[str,Any],slice_id:str,profile:str,primary_argv:Sequence[str],primary_receipt:Mapping[str,Any],timeout_seconds:int,out:Path,semantic_plan:Path|None=None,primary_descriptor:Mapping[str,Any]|None=None)->dict[str,Any]:
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
    deferred = [argv for argv in declared if argv != primary and _terminal_scope_command(argv)]
    commands_to_run = [argv for argv in (declared if required else [argv for argv in declared if argv == primary]) if argv not in deferred]
    records=[]
    for argv in commands_to_run:
        if argv==primary:
            executions=primary_receipt.get("test_executions")
            cases=primary_receipt.get("cases")
            if primary_receipt.get("timed_out") is True or primary_receipt.get("exit_code")!=0 or not isinstance(executions,int) or executions<1 or not isinstance(cases,int) or cases<1:
                raise ValueError("Q6 primary refactor selector is not admissible regression evidence")
            records.append({"argv":argv,"status":"covered-by-primary-refactor-selector","exit_code":0,"timed_out":False,"test_executions":executions,"cases":cases,"stdout_sha256":primary_receipt.get("stdout_sha256"),"stderr_sha256":primary_receipt.get("stderr_sha256")})
            continue
        if semantic_plan is not None and primary_descriptor is not None:
            from shared_execution import command_identity, execute_with_reuse, admissible
            from copy import deepcopy
            try:
                command_identity(argv)
            except ValueError:
                pass  # Existing non-pytest commands remain executable, never reusable.
            else:
                command_run = out.parent / "q6-executions" / ("command-" + sha256_bytes(str(argv).encode())[7:23])
                descriptor = deepcopy(primary_descriptor)
                descriptor.update(run_id=command_run.name, stage="regression", argv=argv, timeout_seconds=timeout_seconds)
                targets = set(descriptor["target_refs"])
                for raw in _pytest_path_arguments(argv):
                    candidate = workspace / descriptor["cwd"] / raw
                    if candidate.is_file():
                        targets.add(candidate.relative_to(workspace).as_posix())
                descriptor["target_refs"] = sorted(targets)
                receipt = execute_with_reuse(workspace=workspace, bundle=bundle, semantic_plan=semantic_plan,
                    run_dir=command_run, descriptor=descriptor, profile=profile)
                admissible(receipt)
                records.append({"argv":argv, "status":"covered-by-shared-execution" if receipt.get("execution_reference") else "pass",
                    "exit_code":0, "timed_out":False, "test_executions":receipt["test_executions"], "cases":receipt["cases"],
                    "receipt_ref":(command_run / "canonical-evidence/regression/process-receipt.v2.json").relative_to(workspace).as_posix(),
                    "receipt_sha256":sha256_value(receipt), "descriptor":descriptor,
                    "semantic_plan":semantic_plan.resolve().relative_to(workspace.resolve()).as_posix()})
                continue
        try:
            from workflow_unit_budget import run_command
            proc=run_command(argv,cwd=workspace,timeout=timeout_seconds)
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
    result={"schema":"quick-dev.q6-regression-gate.v1","slice_id":slice_id,"profile":profile,"regression_required":required,"declared_command_count":len(declared),"deferred_terminal_command_count":len(deferred),"deferred_terminal_commands":deferred,"commands":records,"status":"pass","authorizes":[]}
    create_json(out,result)
    return result


def validate_regression_references(workspace, gate, *, _saved_request_validator=None):
    """Q7/Q8 and reentry reread original Q6 executions, not only a gate digest."""
    from runtime_evidence import load_json, resolve_file, sha256_value
    from shared_execution import admissible
    for row in gate.get("commands", []):
        if "receipt_ref" not in row:
            continue
        path = resolve_file(workspace, row["receipt_ref"])
        receipt = load_json(path)
        if sha256_value(receipt) != row["receipt_sha256"]:
            raise ValueError("Q6 original receipt changed")
        admissible(receipt)
        for name in ("stdout", "stderr"):
            if sha256_bytes((path.parent / (name + ".bin")).read_bytes()) != receipt[name + "_sha256"]:
                raise ValueError("Q6 original output changed")
        from shared_execution import validate_saved_request
        (_saved_request_validator or validate_saved_request)(workspace, path.parent, row["descriptor"], receipt)
