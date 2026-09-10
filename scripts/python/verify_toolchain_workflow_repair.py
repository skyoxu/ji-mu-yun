#!/usr/bin/env python3
"""Run the direct 8-18 regression set and append non-authorizing evidence.

No VDD, Quick Dev, Acceptance, model invocation, or real evidence deletion.
ADR-0060. Windows runs include the existing junction regression.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[2]
TESTS = [
    'scripts/python/tests/test_knowledge_successor_v2.py',
    'scripts/python/tests/test_skill_input_consumer_migration.py',
    'scripts/python/tests/test_toolchain_workflow_repair_e2e.py',
    'scripts/python/tests/test_skill_input_selection_v2.py',
    'scripts/python/tests/test_skill_input_transport_auto.py',
    'scripts/python/tests/test_skill_input_coverage_v2.py',
    'scripts/python/tests/test_skill_input_generation_pointer.py',
    'scripts/python/tests/test_skill_input_retention.py',
    'scripts/python/tests/test_knowledge_gate_matrix.py',
    'scripts/python/tests/test_skill_input_consumption.py',
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out-dir', type=Path)
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    output = (args.out_dir or ROOT / 'logs' / 'toolchain-workflow-repair-direct' / stamp).resolve()
    output.relative_to((ROOT / 'logs').resolve())
    output.mkdir(parents=True, exist_ok=False)
    command = [sys.executable, '-m', 'pytest', *TESTS, '-q', '--junitxml=' + str(output / 'junit.xml')]
    excluded = []
    if os.name != 'nt':
        excluded = ['test_intermediate_junction_is_rejected_when_supported']
        command.extend(['-k', 'not ' + excluded[0]])
    before = {}
    from skill_input_v2 import MODULES
    files = sorted(set(TESTS + ['scripts/python/' + p for p in MODULES] + [
        'scripts/python/skill_input_gate.py', 'scripts/python/prepare_skill_input_consumption.py',
        'scripts/python/validate_skill_input_consumption.py', 'scripts/python/launch_skill_input_consumer.py',
        'scripts/python/verify_toolchain_workflow_repair.py', 'scripts/sc/_llm_backend.py',
        'execution-plans/2026-08-18-toolchain-workflow-repair/tools/terminal_full.py']))
    for consumer in ('vdd-execution-plan', 'quick-dev-tdd-adapter', 'run-phase-bootstrap-review', 'run-refactor-implementation-acceptance'):
        skill = ROOT / '.agents' / 'skills' / consumer
        for subdir in ('scripts', 'tools'):
            files.extend(p.relative_to(ROOT).as_posix() for p in (skill / subdir).glob('*.py'))
        files.append((skill / 'references' / 'skill-input-contract.v1.json').relative_to(ROOT).as_posix())
    files.extend(p.relative_to(ROOT).as_posix() for p in (ROOT / 'scripts' / 'toolchain').rglob('*.py') if 'tests' not in p.parts)
    files.append('.agents/skills/run-phase-bootstrap-review/policies/bootstrap-runtime/runtime-policy.v1.json')
    files = sorted(set(files))
    for path in files:
        before[path] = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True, shell=False)
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace', shell=False)
    (output / 'stdout.txt').write_text(result.stdout, encoding='utf-8')
    (output / 'stderr.txt').write_text(result.stderr, encoding='utf-8')
    stable = all(hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest for path, digest in before.items())
    import xml.etree.ElementTree as ET
    junit = ET.parse(output / 'junit.xml').getroot() if (output / 'junit.xml').is_file() else None
    cases = list(junit.iter('testcase')) if junit is not None else []
    skipped = sum(case.find('skipped') is not None for case in cases)
    passed = result.returncode == 0 and stable and len(cases) > 0
    report = {'schema_version': 'toolchain-workflow-repair.direct-validation.v1',
              'status': 'passed' if passed else 'failed', 'platform': platform.platform(),
              'python': sys.version, 'source_head': head.stdout.strip() if head.returncode == 0 else None,
              'source_hashes': before, 'source_stable': stable, 'command': command,
              'exit_code': result.returncode, 'test_cases': len(cases), 'skipped_cases': skipped, 'platform_exclusions': excluded,
              'windows_verification_pending': os.name != 'nt', 'authorizes': [],
              'formal_workflow_invoked': False, 'live_backend_calls': 0}
    (output / 'validation.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(result.stdout, end='')
    print(json.dumps({'status': report['status'], 'evidence': str(output), 'windows_verification_pending': report['windows_verification_pending']}))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
