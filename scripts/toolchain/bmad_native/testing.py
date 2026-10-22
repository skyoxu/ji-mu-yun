"""ADR-0062: isolated local transport fixtures, never native semantic evidence."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from . import RECEIPT, load_lock, verify, write_config

REPO = Path(__file__).resolve().parents[3]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, REPO / relative)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str((REPO / relative).parent))
    spec.loader.exec_module(module)
    return module


def fixture(root):
    verify(REPO)
    root.mkdir(parents=True, exist_ok=True)
    lock = load_lock()
    for path in {**lock['files'], **lock['runtime']}:
        dest = root/path; dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes((REPO/path).read_bytes())
    (root/RECEIPT).write_text(json.dumps({'version': lock['version']})+'\n',encoding='utf-8')
    write_config(root)
    for path in ['.agents/skills/jimuyun-spec/scripts/canonical_package.py']:
        dest=root/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((REPO/path).read_bytes())
    (root/'AGENTS.md').write_text('# Fixture authority\nLocal deterministic transport fixture only.\n',encoding='utf-8')
    return root


def command(argv, cwd):
    env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONUTF8':'1','UV_OFFLINE':'1'}
    return subprocess.run(argv,cwd=cwd,env=env,shell=False,capture_output=True,text=True,encoding='utf-8',timeout=30)
