#!/usr/bin/env python3
"""Probe the repository-shared real semantic worker backend without mutating sources."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
SC=ROOT/"scripts"/"sc"
if str(SC) not in sys.path:
    sys.path.insert(0,str(SC))
from _llm_backend import inspect_llm_backend, resolve_llm_backend, run_llm_exec


def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--backend")
    parser.add_argument("--out",type=Path)
    args=parser.parse_args()
    backend=resolve_llm_backend(args.backend)
    info=inspect_llm_backend(backend)
    result={
        "schema":"vdd.real-worker-probe.v1",
        "backend":backend,
        "availability":info,
        "status":"environment-blocked",
        "execution_attempted":False,
        "execution_succeeded":False,
        "authorizes":[],
    }
    exit_code=0
    if info.get("available") is not True:
        exit_code=1
    if info.get("available") is True:
        output=(args.out.parent if args.out else ROOT/".tmp-vdd-worker-probe")/"worker-last-message.json"
        prompt='Return exactly this JSON object and nothing else: {"probe":"ok","read_only":true}'
        code,trace,argv=run_llm_exec(
            backend=backend,
            root=ROOT,
            prompt=prompt,
            output_last_message=output,
            timeout_sec=120,
            codex_configs=['model_reasoning_effort="high"'],
            codex_sandbox="read-only",
        )
        result["execution_attempted"]=True
        result["backend_exit_code"]=code
        result["backend_argv_head"]=argv[:3]
        result["trace_tail"]=trace[-2000:]
        try:
            value=json.loads(output.read_text(encoding="utf-8")) if output.is_file() else None
        except (OSError,UnicodeError,json.JSONDecodeError):
            value=None
        if code==0 and value=={"probe":"ok","read_only":True}:
            result["status"]="pass"
            result["execution_succeeded"]=True
        else:
            result["status"]="worker-failed"
            exit_code=1
    payload=json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n"
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(payload,encoding="utf-8")
    print(payload,end="")
    return exit_code


if __name__=="__main__":
    raise SystemExit(main())
