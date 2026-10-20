"""ADR-0041: disposable Package A fixtures with independent expected values."""
from copy import deepcopy
import json
from pathlib import Path
import shutil

REPOSITORY = Path(__file__).resolve().parents[3]
POLICY = 'scripts/sc/config/skill-authoring-standard.v1.json'
SCHEMAS = (
    'scripts/sc/schemas/skill-quality-contract.v1.schema.json',
    'scripts/sc/schemas/skill-quality-result.v1.schema.json',
)


def dependency_package(tmp_path):
    """Copy actual candidate inputs; never synthesize a passing policy/schema."""
    root = tmp_path / 'inspection'
    package = root / 'packages' / 'reference-skill'
    package.mkdir(parents=True)
    for relative in (POLICY, *SCHEMAS):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPOSITORY / relative, target)
    (package / 'SKILL.md').write_text(
        '---\nname: reference-skill\ndescription: Inspect a local example.\n---\n'
        '# Reference Skill\n\nInspect contained input and return a local report.\n',
        encoding='utf-8')
    contract = {
        'schema': 'skill-quality.v1', 'name': 'reference-skill',
        'responsibility': 'Inspect a contained local example and return its report.',
        'triggers': ['A caller requests a local example inspection.'],
        'non_goals': ['Executing dependencies or granting permissions.'],
        'inputs': ['A contained example path.'], 'outputs': ['A structured report.'],
        'references': [], 'tests': ['Local package declaration checks.'],
        'evidence': 'The caller owns real execution evidence.',
        'lifecycle': {'owner': 'repository-maintainer', 'completion_owner': 'caller'},
        'capabilities': {},
        'entrypoints': [{'id': 'inspect', 'dependencies': ['local-parser'],
                         'preflight': 'Check the declared local parser record.'}],
        'dependencies': [{'id': 'local-parser', 'required': True, 'version': '1.2.3',
                          'authority': 'references/parser.json',
                          'when_missing': 'block'}],
    }
    authority = package / 'references' / 'parser.json'
    authority.parent.mkdir()
    authority.write_text(json.dumps({'id': 'local-parser', 'version': '1.2.3'}), encoding='utf-8')
    write_contract(package, contract)
    return root, package, deepcopy(contract)


def write_contract(package, value):
    (package / 'skill-quality.v1.json').write_text(json.dumps(value, sort_keys=True), encoding='utf-8')
