"""ADR-0058: real owner Q8 still rejects bad proofs during budget transfer."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / '.agents/skills/quick-dev-tdd-adapter/tools'
sys.path[:0] = [str(TOOLS), str(TOOLS / 'tests'), str(ROOT / 'scripts/quick_dev')]
import approved_budget_replay as compatibility
from test_approved_budget_replay import materialize, binding
from test_cer_behavior_routing import fixture, execute
from coverage_predicates import publish_implementation_complete, validate_slice_ready
from runtime_evidence import sha256_value


def test_owner_q8_reuses_success_but_rejects_failed_stale_and_changed_cases(tmp_path, monkeypatch):
    semantic, roots = fixture(tmp_path)
    materialize(tmp_path)
    original_blob = compatibility._blob
    monkeypatch.setattr(compatibility, '_blob', lambda _root, revision, path: original_blob(str(ROOT), revision, path))
    # Execute a real small CER regression once; this does not rerun 08-05 tests.
    probe = execute(tmp_path, semantic, 'probe')
    assert execute(tmp_path, semantic, 'regression', probe)['predicate_result']
    execute(tmp_path, semantic, 'terminal', probe, materialize_only=True)
    old_roots = json.loads(json.dumps(roots))
    for row in old_roots:
        if row['root_kind'] == 'candidate_tree':
            row.pop('repository_relative_posix_path')
            row['repository_relative_posix_paths'] = ['candidate.py', 'scripts/sc/skill_replay_runtime.py']
    path = tmp_path / 'scripts/sc/skill_replay_runtime.py'
    current = path.read_bytes()
    path.write_bytes(original_blob(str(ROOT), compatibility.TRANSITION + '^', 'scripts/sc/skill_replay_runtime.py'))
    ready_path = tmp_path / 'RUN-1/ready.json'
    ready = validate_slice_ready(workspace=tmp_path, semantic_plan=semantic, run_root=tmp_path/'RUN-1',
        slice_id='S1', snapshot_roots=old_roots, source_commit='TEST', out=ready_path)
    assert execute(tmp_path, semantic, 'terminal', probe)['predicate_result']
    path.write_bytes(current)
    predecessor = {'slice_id': 'S1', 'run_root': 'RUN-1', 'result_ref': 'RUN-1/ready.json',
                   'result_sha256': sha256_value(ready), 'budget_compatibility': binding()}
    args = dict(workspace=tmp_path, semantic_plan=semantic, predecessors=[predecessor],
                snapshot_roots=roots, source_commit='TEST', out=tmp_path/'Q8/complete.json')
    assert publish_implementation_complete(**args)['status'] == 'pass'
    assert publish_implementation_complete(**args, verify_existing=True)['status'] == 'pass'
    terminal_path = tmp_path/'RUN-1/canonical-evidence/terminal/stage-result.v2.json'
    terminal_bytes = terminal_path.read_bytes()
    failed = json.loads(terminal_bytes)
    failed.update(predicate_result=False, verification_outcome='fail', failure_family='timeout')
    terminal_path.write_text(json.dumps(failed), encoding='utf-8')
    with pytest.raises(ValueError, match='terminal stage not current process pass'):
        publish_implementation_complete(**args, verify_existing=True)
    terminal_path.write_bytes(terminal_bytes)
    stdout = tmp_path/'RUN-1/canonical-evidence/probe/stdout.bin'
    output_bytes = stdout.read_bytes()
    stdout.write_bytes(output_bytes + b' altered')
    with pytest.raises(ValueError, match='stale-probe-output'):
        publish_implementation_complete(**args, verify_existing=True)
    stdout.write_bytes(output_bytes)
    selector = tmp_path/'tests/test_one.py'
    selector.write_bytes(selector.read_bytes() + b'\n# changed semantic input\n')
    with pytest.raises(ValueError, match='probe-selector-or-fixture-changed'):
        publish_implementation_complete(**args, verify_existing=True)
    assert path.read_bytes() == current
