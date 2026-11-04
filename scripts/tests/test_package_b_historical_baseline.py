"""ADR-0041/ADR-0062: replay the unmodified Package B delivery assertions.

Its byte-preservation oracle is scoped to the actual published Package B tree,
not an eternal prohibition on later authorized VDD/Quick Dev maintenance.
Current implementations remain covered by the current native regression suites.
"""
import ast
import hashlib
import json
import os
import posixpath
from pathlib import Path, PurePosixPath
import subprocess
import re
import shutil
import stat
import sys
import tarfile
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
PUBLISHED = '5197679049e709ea9d22212aacc6c09067b50ec1'
HISTORICAL_TEST = 'scripts/sc/tests/test_skill_quality_package_b.py'
RECEIPT = 'logs/package-b-rebuild-20261028/LIBRARY-STAGE003-DURABLE-RECEIPT.json'


def _ordinary_metadata(path):
    metadata = path.lstat()
    if (getattr(metadata, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0)
            or not (stat.S_ISDIR(metadata.st_mode) or stat.S_ISREG(metadata.st_mode))):
        raise ValueError('Historical stage contains a reparse point or special file.')
    return metadata


def _directory_identity(path):
    metadata = _ordinary_metadata(path)
    if not stat.S_ISDIR(metadata.st_mode):
        raise ValueError('Historical stage requires an ordinary directory.')
    return {'st_dev': metadata.st_dev, 'st_ino': metadata.st_ino}


def _remove_owned_stage(stage, parent, canonical_parent, parent_identity, stage_identity):
    def check_anchors():
        if (parent.resolve(strict=True) != canonical_parent or stage.parent != parent
                or stage.resolve(strict=True).parent != canonical_parent
                or _directory_identity(parent) != parent_identity
                or _directory_identity(stage) != stage_identity):
            raise ValueError('Historical stage ownership changed before cleanup.')
    check_anchors()
    pending = [stage]
    while pending:
        directory = pending.pop()
        _directory_identity(directory)
        for child in directory.iterdir():
            if stat.S_ISDIR(_ordinary_metadata(child).st_mode):
                pending.append(child)
    check_anchors()
    shutil.rmtree(stage)


def test_all_original_package_b_assertions_replay_on_their_published_candidate(tmp_path, tmp_path_factory):
    stage_parent = ROOT / 'logs'
    parent_identity = _directory_identity(stage_parent)
    canonical_parent = stage_parent.resolve(strict=True)
    if canonical_parent != stage_parent:
        raise ValueError('Historical stage requires its canonical repository logs directory.')
    stage = Path(tempfile.mkdtemp(prefix='h', dir=stage_parent))
    stage_identity = _directory_identity(stage)
    if (stage.parent != stage_parent or stage.resolve(strict=True).parent != canonical_parent
            or stage_parent.resolve(strict=True) != canonical_parent
            or _directory_identity(stage_parent) != parent_identity):
        raise ValueError('Historical stage escaped its ordinary repository logs directory.')
    with (tmp_path / 'historical-stage-identity.json').open('x', encoding='utf-8') as evidence:
        json.dump({'authorizes': [], 'published_commit': PUBLISHED,
                   'stage_path': str(stage), 'stage_identity': stage_identity,
                   'parent_path': str(stage_parent), 'canonical_parent': str(canonical_parent),
                   'parent_identity': parent_identity}, evidence, indent=2)
        evidence.write('\n')
    def blob(relative):
        return subprocess.check_output(['git', 'show', PUBLISHED + ':' + relative], cwd=ROOT)
    receipt = json.loads(blob(RECEIPT))
    packages = ['vdd-execution-plan', 'quick-dev-tdd-adapter', 'run-phase-bootstrap-review',
                'run-refactor-implementation-acceptance', 'maintain-knowledge-base']
    paths = ['.agents/skills/' + name for name in packages]
    paths += ['scripts/sc', 'docs/standards/skill-authoring-standard.md',
        '.agents/skills/jimuyun-spec/SKILL.md', '.agents/skills/jimuyun-architecture/SKILL.md',
        'docs/adr/ADR-0062-repository-skill-authoring-contract.md',
        'docs/workflows/skill-control-plane-evolution-requirements.md',
        'docs/workflows/inputs/package-b-rebuild-20261028-r2',
        'execution-plans/2026-10-28-skill-compliance-package-b-rebuild-r3',
        'scripts/vdd/compile_plan.py', 'scripts/quick_dev/run.py',
        'scripts/toolchain/bmad_native/__init__.py', 'scripts/python/publish_knowledge_catalog.py',
        RECEIPT, receipt['local_archive']]
    for name in packages:
        base = '.agents/skills/' + name
        for reference in re.findall(r'\]\(([^)]+)\)', blob(base + '/SKILL.md').decode('utf-8')):
            if reference.startswith(('http:', 'https:', '#')):
                continue
            relative = posixpath.normpath(base + '/' + reference.split('#', 1)[0])
            assert not relative.startswith(('../', '/'))
            paths.append(relative)
    paths = sorted(set(paths))
    all_paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', PUBLISHED], cwd=ROOT, text=True).splitlines()
    paths += [p for p in all_paths if (p in ['scripts/__init__.py', 'scripts/sc/__init__.py']
              or (p.startswith('.agents/skills/workflow-chapter') and p.endswith('/SKILL.md')))]
    process = subprocess.Popen(['git', 'archive', '--format=tar', PUBLISHED, *paths],
                               cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    manifest, size = [], 0
    try:
        with tarfile.open(fileobj=process.stdout, mode='r|') as archive:
            for member in archive:
                relative = PurePosixPath(member.name)
                assert not relative.is_absolute() and '..' not in relative.parts
                target = stage.joinpath(*relative.parts)
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                assert member.isfile(), 'Historical fixtures never materialize links or devices.'
                size += member.size
                assert size <= 80 * 1024 * 1024, 'Historical fixture exceeds its bounded scope.'
                target.parent.mkdir(parents=True, exist_ok=True)
                raw = archive.extractfile(member).read()
                target.write_bytes(raw)
                manifest.append({'path': member.name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
        assert process.wait(timeout=30) == 0, process.stderr.read().decode(errors='replace')
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
    assert (stage / HISTORICAL_TEST).read_bytes() == blob(HISTORICAL_TEST)
    expected = {n.name for n in ast.parse(blob(HISTORICAL_TEST)).body
                if isinstance(n, ast.FunctionDef) and n.name.startswith('test_')}
    assert len(expected) == 77
    output = tmp_path_factory.getbasetemp().parent / 'historical-package-b-original-results'
    output.mkdir(exist_ok=False)
    (output / 'source-manifest.json').write_text(json.dumps({'commit': PUBLISHED, 'files': manifest}, indent=2))
    request = output / 'request.json'
    request.write_text(json.dumps({'stage': 'baseline-regression', 'nonce': 'package-b-historical-fixture'}))
    report = output / 'case-report.json'
    argv = [sys.executable, '-u', '-B', str(ROOT / 'scripts/skill_baseline.py'), '_collect', str(request),
        str(report), str(stage / HISTORICAL_TEST), '-v', '-p', 'no:cacheprovider',
        '--basetemp', str(tmp_path / 'child-pytest'), '-o', 'tmp_path_retention_policy=failed',
        '--junitxml', str(output / 'junit.xml')]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    with (output / 'stdout.log').open('wb') as stdout:
        result = subprocess.run(argv, cwd=stage, env=env, stdout=stdout, stderr=subprocess.STDOUT,
                                check=False, timeout=180)
    (output / 'exit.json').write_text(json.dumps({'argv': argv, 'exit_code': result.returncode}))
    assert result.returncode == 0, (output / 'stdout.log').read_text()[-10000:]
    native = json.loads(report.read_text())
    assert {n.rsplit('::', 1)[-1] for n in native['selected']} == expected
    assert len(native['selected']) == len(native['collected']) == 77
    assert native['complete'] and native['exit_code'] == 0 and native['errors'] == []
    assert all(e['outcome'] == 'passed' and not e['xfail'] for e in native['events'])
    assert len(native['events']) == 77 * 3
    junit = ET.parse(output / 'junit.xml')
    assert len(junit.findall('.//testcase')) == 77
    assert not junit.findall('.//failure') and not junit.findall('.//error') and not junit.findall('.//skipped')
    _remove_owned_stage(stage, stage_parent, canonical_parent, parent_identity, stage_identity)
