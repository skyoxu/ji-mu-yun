"""ADR-0057: native VDD plans remain main facts, never publication authority."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid
from unittest import mock

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'scripts/python'))
from _knowledge_catalog_builder import CatalogBuilder, MainSnapshot
import publish_knowledge_catalog as publication

spec=importlib.util.spec_from_file_location('v3_publication_request_helper',
    ROOT/'.agents/skills/maintain-knowledge-base/scripts/prepare_publication_request.py')
helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)

def native_bytes(value):
    # Existing semantic_compiler canonical identity includes its final LF.
    return (json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode('utf-8')

class NativeV3PlanAdapterTests(unittest.TestCase):
    def setUp(self):
        owned=os.environ.get('JIMUYUN_UNIT_FIXTURE_ROOT')
        if owned:
            # Managed Windows sessions may reject mkdtemp's private-mode ACL.
            # Use only new inherited-permission objects; retain them as evidence.
            self.base=Path(owned)/('knowledge-v3-'+uuid.uuid4().hex)
            self.base.mkdir()
        else:
            self.temporary=tempfile.TemporaryDirectory()
            self.addCleanup(self.temporary.cleanup)
            self.base=Path(self.temporary.name)
        self.target='execution-plans/native-v3-example'
        self.count=0

    def git(self,root,*args):
        return subprocess.check_output(['git','-c','core.autocrlf=false','-c','user.name=Knowledge Fixture',
            '-c','user.email=fixture@example.invalid','-C',str(root),*args],stderr=subprocess.PIPE)

    def repository(self,mutate=None,legacy=False,commit_plan=True):
        self.count+=1;root=self.base/('repo'+str(self.count));root.mkdir()
        bundle={'schema_version':'vdd.semantic-plan-bundle.v1','plan_id':'PLAN-NATIVE-FIXTURE','profile':'resumable',
            'obligations':[{'obligation_id':'O-NATIVE','subject':'Owned metadata persistence','expected_behavior':'Retain the account binding.'}],
            'acceptances':[{'acceptance_id':'A-NATIVE','obligation_ids':['O-NATIVE'],'oracle':'Read the persisted owned binding.'}],
            'failure_intents':[{'failure_intent_id':'FI-NATIVE','obligation_id':'O-NATIVE','marker':'OWNED_BINDING_MISSING'}],
            'agent_contexts':[{'private_context':'CONTEXT_MUST_NOT_ENTER_GLOBAL_SEMANTICS'}],
            'source_scope':{'authority_record':'AUTHORITY_MUST_NOT_ENTER_GLOBAL_SEMANTICS'}}
        state={'schema':'vdd.compiler-state.v1','state':'plan-ready','plan_id':bundle['plan_id'],
            'completed_stages':['V0','V1','V2','V3','V4','V5','V6','V6A','V7'],
            'semantic_plan_sha256':'sha256:'+hashlib.sha256(native_bytes(bundle)).hexdigest()}
        files={self.target+'/semantic-plan-bundle.v1.json':native_bytes(bundle),
            self.target+'/compiler-state.v1.json':native_bytes(state),
            self.target+'/obligations.v1.json':native_bytes(bundle['obligations']),
            self.target+'/acceptances.v1.json':native_bytes(bundle['acceptances']),
            self.target+'/failure-intents.v1.json':native_bytes(bundle['failure_intents']),
            self.target+'/authority-manifest.v1.json':b'{"authority":"NOT_A_SEMANTIC_SOURCE"}\n',
            self.target+'/knowledge-context.v1.json':b'{"catalog":"NO_RECURSIVE_IMPORT"}\n',
            'README.md':b'# Fixture repository\n'}
        if mutate:mutate(files,bundle,state)
        if legacy:files[self.target+'/00-index.md']=b'# Legacy plan\n\n- Status: plan-ready\n'
        for relative,raw in files.items():
            path=root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
        self.git(root,'init','--initial-branch=main')
        self.git(root,'add','--','README.md' if not commit_plan else '.')
        self.git(root,'commit','-m','Commit synthetic native plan facts')
        commit=self.git(root,'rev-parse','refs/heads/main').decode().strip()
        return root,commit

    def request(self,commit):
        return {'schema_version':publication.PUBLICATION_REQUEST_SCHEMA_VERSION,'request_id':'fixture-request',
            'caller':'maintain-knowledge-base','trigger':'operator-requested','target_plan':self.target,
            'main_commit':commit,'automatic':False,'maintainer_confirmation':True,
            'recorded_at':'2026-11-05T00:00:00+00:00','authorizes':['knowledge-publication'],'source_route':None}

    def catalog(self,root,exclusions=None):
        snapshot=MainSnapshot(root)
        builder=CatalogBuilder(snapshot,{'policy_revision':'fixture-policy'},exclusions or {'policy_revision':'fixture-exclusions','rules':[]})
        builder.add_execution_plans()
        return builder

    def test_owner_helper_recognizes_committed_native_plan_without_fabricated_index(self):
        root,commit=self.repository()
        self.assertTrue(helper._target_exists_at_main(root,commit,self.target))
        self.assertFalse((root/self.target/'00-index.md').exists())

    def test_publication_target_validation_accepts_same_native_identity(self):
        root,commit=self.repository()
        try:
            result=publication._validate_publication_request(self.request(commit),expected_main=commit,repository_root=root)
        except ValueError as error:
            self.fail('Committed native V3 target rejected: '+str(error))
        self.assertEqual(self.target,result['target_plan'])
        self.assertFalse((root/'knowledge/indexes/current.json').exists())

    def test_catalog_exposes_stable_semantics_and_hashes_discovery_witnesses_only(self):
        root,_=self.repository();builder=self.catalog(root)
        self.assertEqual(1,len(builder.modules));module=builder.modules[0]
        self.assertEqual(self.target+'/obligations.v1.json',module['source_path'])
        self.assertEqual('conditional',module['status'])
        semantic_paths={module['source_path'],*[row['path'] for row in module['resources']]}
        self.assertEqual({self.target+'/'+name for name in ['obligations.v1.json','acceptances.v1.json','failure-intents.v1.json']},semantic_paths)
        for path in semantic_paths:
            raw=MainSnapshot(root).read_text(path)
            self.assertNotIn('MUST_NOT_ENTER_GLOBAL_SEMANTICS',raw)
        sources={row['path']:row for row in builder.source_snapshot()['sources']}
        for name in ['semantic-plan-bundle.v1.json','compiler-state.v1.json']:
            self.assertEqual('integrity-only',sources[self.target+'/'+name]['source_role'])
        self.assertFalse(any('authority-manifest' in path or 'knowledge-context' in path for path in sources))

    def test_worktree_dirt_cannot_change_main_recognition_or_import_uncommitted_plan(self):
        root,commit=self.repository()
        (root/self.target/'compiler-state.v1.json').write_text('{"state":"draft"}',encoding='utf-8')
        (root/self.target/'obligations.v1.json').write_text('[]',encoding='utf-8')
        self.assertTrue(helper._target_exists_at_main(root,commit,self.target))
        self.assertEqual(1,len(self.catalog(root).modules))
        other,other_commit=self.repository(commit_plan=False)
        self.assertFalse(helper._target_exists_at_main(other,other_commit,self.target))
        self.assertEqual([],self.catalog(other).modules)

    def test_draft_corruption_or_unbound_semantics_are_not_native_plan_targets(self):
        def mutation(kind):
            def change(files,bundle,state):
                if kind=='draft':state['state']='draft'
                elif kind=='pending':state['state']='semantic-validated-pending-handoff'
                elif kind=='hash':state['semantic_plan_sha256']='sha256:'+'0'*64
                elif kind=='plan-id':state['plan_id']='PLAN-FOREIGN'
                elif kind=='state-schema':state['schema']='unknown-state'
                elif kind=='bundle-schema':bundle['schema_version']='unknown-bundle'
                elif kind=='missing-state':files.pop(self.target+'/compiler-state.v1.json');return
                elif kind=='missing-semantics':files.pop(self.target+'/acceptances.v1.json');return
                elif kind=='unbound-semantics':files[self.target+'/obligations.v1.json']=b'[]\n';return
                elif kind=='malformed-json':files[self.target+'/compiler-state.v1.json']=b'{';return
                elif kind=='invalid-utf8':files[self.target+'/semantic-plan-bundle.v1.json']=b'\xff';return
                elif kind=='hash-without-native-lf':state['semantic_plan_sha256']='sha256:'+hashlib.sha256(native_bytes(bundle).rstrip(b'\n')).hexdigest()
                files[self.target+'/compiler-state.v1.json']=native_bytes(state)
                files[self.target+'/semantic-plan-bundle.v1.json']=native_bytes(bundle)
            return change
        for kind in ['draft','pending','hash','plan-id','state-schema','bundle-schema','missing-state','missing-semantics','unbound-semantics','malformed-json','invalid-utf8','hash-without-native-lf']:
            with self.subTest(kind=kind):
                root,commit=self.repository(mutate=mutation(kind))
                self.assertFalse(helper._target_exists_at_main(root,commit,self.target))
                with self.assertRaisesRegex(ValueError,'target_invalid'):
                    publication._validate_publication_request(self.request(commit),expected_main=commit,repository_root=root)
                self.assertEqual([],self.catalog(root).modules)

    def test_policy_exclusion_of_semantics_or_identity_excludes_entire_native_module(self):
        root,_=self.repository()
        for name in ['obligations.v1.json','acceptances.v1.json','failure-intents.v1.json',
                     'semantic-plan-bundle.v1.json','compiler-state.v1.json']:
            with self.subTest(name=name):
                policy={'rules':[{'disposition':'excluded','applies_to':['source-snapshot'],
                                  'path_pattern':self.target+'/'+name}]}
                builder=self.catalog(root,policy)
                self.assertEqual([],builder.modules)
                self.assertEqual([],builder.source_snapshot()['sources'])

    def test_nested_fixture_plan_is_not_discovered_as_a_global_native_module(self):
        self.target='execution-plans/example/fixtures/nested-native'
        root,commit=self.repository()
        self.assertFalse(helper._target_exists_at_main(root,commit,self.target))
        self.assertEqual([],self.catalog(root).modules)

    def test_legacy_index_keeps_precedence_and_compatibility(self):
        def broken(files,bundle,state):files[self.target+'/compiler-state.v1.json']=b'{}\n'
        root,commit=self.repository(mutate=broken,legacy=True)
        self.assertTrue(helper._target_exists_at_main(root,commit,self.target))
        publication._validate_publication_request(self.request(commit),expected_main=commit,repository_root=root)
        modules=self.catalog(root).modules
        self.assertEqual(1,len(modules));self.assertEqual(self.target+'/00-index.md',modules[0]['source_path'])

    def test_valid_native_plan_does_not_waive_confirmation_main_or_route_bindings(self):
        root,commit=self.repository()
        for field,value,error in [('maintainer_confirmation',False,'confirmation_required'),
            ('main_commit','0'*40,'main_mismatch'),('source_route',{},'route_invalid')]:
            with self.subTest(field=field):
                request=self.request(commit);request[field]=value
                with self.assertRaisesRegex(ValueError,error):
                    publication._validate_publication_request(request,expected_main=commit,repository_root=root)
        with mock.patch.object(publication,'_single_writer',side_effect=AssertionError('No real publication lock in this test')):
            result=publication.run(root,publish=True,repeat=1)
        self.assertEqual('knowledge_publication_request_required',result['error'])
        self.assertFalse((root/'knowledge/indexes/current.json').exists())

    def test_native_helper_cli_still_requires_explicit_ack_before_request_write(self):
        root,_=self.repository();output='logs/knowledge-context/publication-requests/synthetic.json'
        completed=subprocess.run([sys.executable,'-B',str(ROOT/'.agents/skills/maintain-knowledge-base/scripts/prepare_publication_request.py'),
            '--repository-root',str(root),'--trigger','operator-requested','--target-plan',self.target,'--output',output],capture_output=True,text=True)
        self.assertNotEqual(0,completed.returncode)
        self.assertIn('explicit maintainer confirmation',completed.stderr)
        self.assertFalse((root/output).exists())

if __name__=='__main__':unittest.main()
