"""Current caller's explicitly authored V3 inputs; no native state is written."""
from pathlib import Path
import json,sys
B=Path(__file__).resolve().parent
ROOT=B.parents[1]
PACKAGES=['vdd-execution-plan','quick-dev-tdd-adapter','run-phase-bootstrap-review','run-refactor-implementation-acceptance','maintain-knowledge-base']
MAINS=[f'.agents/skills/{n}/SKILL.md' for n in PACKAGES]
SIDECARS=[f'.agents/skills/{n}/skill-quality.v1.json' for n in PACKAGES]
DEPS=[f'.agents/skills/{n}/references/package-dependencies.v1.json' for n in PACKAGES]
TEST='scripts/sc/tests/test_skill_quality_package_b.py'
OWNERS=MAINS+SIDECARS+DEPS
# Explicit proof specifications are authored before submission, not inferred from status.
SPECS={
'O-1370E773AD67':('Inspect the five package main dependency tables and quality dependency records during current package validation.','Every package identifies its actual prerequisite owner/version and missing/mismatch response; legitimate child dependencies remain explicit.','dependency_documentation','expected-red'),
'O-1A7456E604BF':('Resolve each moved detail reference from its package main and inspect the referenced local file/anchor during package validation.','Moved operational details are reachable by a direct first-level link; no missing file, missing anchor or nested-only discovery is accepted.','first_level_references','target-binding-failure'),
'O-26F529A9E55D':('Inspect standalone entry preflights and adopted child dependency declarations against the existing native caller contracts.','Independent invocation retains every required child dependency and typed missing response rather than declaring dependency-free execution.','child_dependency_preservation','semantic-contract-gap'),
'O-516E31393C6B':('Invoke the adopted strict validator on all five real current packages and run the focused migration positive/negative fixtures.','The public Package A validator is reused unchanged and focused tests distinguish compliant packages from broken routing, dependencies or authority declarations.','focused_verification','test-harness-failure'),
}

from v3_specs import SPECS as REMAINING_SPECS
SPECS.update(REMAINING_SPECS)
OLD_OBLIGATIONS={o['obligation_id']:o for o in json.loads((ROOT/'execution-plans/2026-10-28-skill-compliance-package-b-rebuild/obligations.v1.json').read_text())}

def build_contracts(obligations):
 out={}
 for o in obligations:
  oid=o['obligation_id'];spec_key=oid if oid in SPECS else next(old_id for old_id, old in OLD_OBLIGATIONS.items() if old['subject']==o['subject'] and old['expected_behavior']==o['expected_behavior']);when,expected,label,family=SPECS[spec_key];assertion='PKGB_'+spec_key[2:]
  a={'source_refs':o['source_refs'],'given':'The current repository and the five existing governed packages; declarations may be incomplete and no validation result is assumed.','when':when,'then':expected,'oracle':{'observable':when,'expected':expected,'forbidden':o['forbidden_result']},'assertion_ids':[assertion]}
  hint={'production_owners':OWNERS,'verification_lane':'unit','behavior_change':'Migrate the five existing control-plane packages to the adopted quality declaration contract while preserving their native workflow ownership.','affected_subjects':['Five existing Skill quality packages'],'state_transition':'Existing workflow declarations to strict-valid package quality declarations; native runtime and lifecycle ownership unchanged.','rollback_scope':{'production_paths':OWNERS,'state_or_schema_compatibility':'Revert only package prose/quality metadata together; never rewrite historical workflow evidence or alter accepted Package A validation semantics.'},'allowed_write_paths':OWNERS+[TEST],'execution_snapshot_paths':[TEST,'scripts/sc/validate_skill_quality.py','scripts/sc/config/skill-authoring-standard.v1.json','scripts/sc/schemas/skill-quality-contract.v1.schema.json','scripts/sc/skill_quality_examples.py'],'planned_new_files':SIDECARS+DEPS+[TEST],'terminal_predicate':'The current complete migration test module passes, all five native strict package checks pass and frozen owner/authority boundaries remain intact.','forbidden_paths':['PhaseA.Platform/','runtime/phase-a/','_bmad/','.agents/skills/jimuyun-spec/','.agents/skills/jimuyun-architecture/','scripts/sc/_llm_backend.py'],'validation_commands':[['python','-B','-m','pytest',TEST,'-q'],['python','-B','-m','pytest','.agents/skills/vdd-execution-plan/scripts/tests/test_validate_skill_contract.py','.agents/skills/quick-dev-tdd-adapter/tools/tests/test_skill_contract.py','.agents/skills/run-phase-bootstrap-review/tests/test_direct_script_startup.py','.agents/skills/run-refactor-implementation-acceptance/tests/test_package.py::PackageTests::test_package_validator_requires_all_slice_modules','.agents/skills/run-refactor-implementation-acceptance/tests/test_package.py::PackageTests::test_fixture_catalog_covers_required_execution_contexts','.agents/skills/run-refactor-implementation-acceptance/tests/test_package.py::PackageTests::test_cli_exposes_required_workflow_transitions','.agents/skills/maintain-knowledge-base/tests/test_prepare_publication_request.py','-q']]}
  out[oid]={'acceptance':a,'failure_intents':[{'failure_family':family,'selector_intent':TEST+'::test_'+label,'expected_outcome':'fail','failure_id':'PKGB_'+spec_key[2:]+'_FAIL'}],'slice_hint':hint}
 return {'obligation_contracts':out}

def author(request_id):
 q=json.loads((B/'vdd-host-session'/request_id/'request.json').read_text());x,_end=json.JSONDecoder().raw_decode(q['prompt'].split('INPUT:\n',1)[1]);inp=x.get('input',x)
 path=B/'model-inputs'/('v3-'+request_id+'.json');path.write_text(json.dumps(build_contracts(inp['obligations']),indent=2)+'\n');print(path)
if __name__=='__main__':author(sys.argv[1])
