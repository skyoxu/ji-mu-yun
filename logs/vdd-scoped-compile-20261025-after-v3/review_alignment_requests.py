"""Caller V4 task: exact contract-retention proof over genuine source partitions.

No author output is treated as its own authority. Frozen obligations already
have a valid separate native source-recall witness. Each new response requires
current exact source text, whole precondition/trigger/outcome/oracle retention,
and complete per-Acceptance failure links. A mismatch blocks for caller review.
No compiler cache, receipt, contract or lifecycle state is written here.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
SESSION = ROOT/'logs/vdd-scoped-compile-20261025-host-after-v3'
sys.path.insert(0,str(ROOT/'scripts/sc'))
import host_session as host

GIVEN = ' Test authoring must scope this retained assertion to VDD/QuickDev/shared behavior; historical BMAD fixtures or reviewer/generation calls are not an admitted setup.'
WHEN = ' Evaluate with the current controlled assertion after test-only scope reconciliation; native probe, RED or regression determines current behavior, never this plan.'


def service():
    obligations = json.loads((ROOT/'logs/vdd-scoped-compile-20261024-r3/authoring/v1-source-recall-caller-assessment.json').read_text())['current_candidates']
    index = json.loads((ROOT/'logs/scoped-input-preparation-20261024-v3/input-source-index.json').read_text())
    sources = {e['source_ref']:e['source_text'] for e in index['entries']}
    recall_path = ROOT/'execution-plans/2026-10-24-vdd-knowledge-query-scoped-v3-r3/atomic-recall-alignment.v1.json'
    recall = json.loads(recall_path.read_text())
    assert recall['valid'] and not recall['findings'] and recall['metrics']['source_gap_count']==0
    assert set(recall['worker']['supported_obligation_ids']) == set(obligations)
    journal=OUT/'v4-decisions.jsonl'
    prior=[json.loads(s) for s in journal.read_text().splitlines()] if journal.exists() else []
    handled={r['request_id'] for r in prior}
    count=0
    for row in host.pending(SESSION):
        if row['request_id'] in handled:continue
        request=json.loads(Path(row['request_path']).read_text());name=Path(request['output_path']).name
        assert name.startswith('v4-source-chunk-'), ('unexpected worker task requires caller review',name)
        payload=json.loads(request['prompt'].rsplit('\n\nINPUT:\n',1)[1])
        assert payload['alignment_scope']=='active-obligation-acceptance-coverage.v1'
        source_entries=payload['source_index']['entries']
        assert source_entries and all(e['source_text']==sources[e['source_ref']] for e in source_entries)
        allowed_refs={e['source_ref'] for e in source_entries}
        active=payload['obligations'];aids={a['acceptance_id']:a for a in payload['acceptances']}
        per_ob={}
        for a in aids.values():
            assert len(a['obligation_ids'])==1 and a['obligation_ids'][0] not in per_ob
            per_ob[a['obligation_ids'][0]]=a
        failures={f['failure_intent_id']:f for f in payload['failure_intents']}
        proof=[]
        for ob in active:
            oid=ob['obligation_id'];assert ob==obligations[oid]
            assert ob['status']=='active' and set(ob['source_refs'])<=allowed_refs
            a=per_ob[oid];linked=a['red_intent_ids']
            checks={'source_refs':a['source_refs']==ob['source_refs'],
                    'given_entire_precondition':a['given']==ob['state_before']+GIVEN,
                    'when_entire_trigger':a['when']==ob['trigger']+WHEN,
                    'then_entire_postcondition':a['then']==ob['state_after'],
                    'oracle_entire_required_behavior':a['oracle']['expected']==ob['expected_behavior']+' Required resulting state: '+ob['state_after'],
                    'oracle_entire_observable_and_scenario':a['oracle']['observable']==ob['observable_result']+' Required scenario and trigger: '+ob['state_before']+' / '+ob['trigger'],
                    'all_forbidden_outcomes':a['oracle']['forbidden']==ob['forbidden_result'],
                    'assertions_nonempty':bool(a['assertion_ids']),
                    'exact_failure_links':bool(linked) and set(linked)<=set(failures)}
            for fid in linked:
                f=failures[fid]
                assert f['acceptance_ids']==[a['acceptance_id']]
                assert f['expected_outcome']=='fail' and f['failure_id']
                assert f['selector_intent'] and 'Never invoke any BMAD skill or reviewer.' in f['selector_intent']
                if f['failure_family']=='expected-red':
                    assert ob['obligation_kind'] in {'behavior','quality'} and ob['requirement_type']!='Governance'
            assert all(checks.values()), (oid,checks)
            proof.append({'obligation_id':oid,'acceptance_id':a['acceptance_id'],'checks':checks,'failure_intent_ids':linked,'failure_families':[failures[fid]['failure_family'] for fid in linked]})
        assert set(per_ob)=={o['obligation_id'] for o in active}
        assert set(failures)=={fid for a in aids.values() for fid in a['red_intent_ids']}
        decision={'covered_obligation_ids':[o['obligation_id'] for o in active],'missing_obligation_ids':[],
                  'invented_obligation_ids':[],'misaligned_acceptance_ids':[],
                  'oracle_alignment':{'status':'aligned','reason':'For each source-supported frozen obligation, the bound Acceptance retains its entire precondition, trigger, resulting state, required behavior, observable/scenario and all forbidden outcomes exactly. The only added text limits test setup to retained scope and leaves current probe/RED/regression to execution. Every intent binds that exact Acceptance; constraints are not promoted to expected RED. Separate native source recall covers the frozen source domain. This is plan alignment, not runtime proof.'},'repairs':[]}
        response=host.respond(SESSION,request['request_id'],host.digest(request),json.dumps(decision,ensure_ascii=False))
        entry={'timestamp':datetime.now(timezone.utc).isoformat(),'request_id':request['request_id'],
               'request_sha256':host.digest(request),'source_refs':sorted(allowed_refs),'decision':decision,
               'review_method':'Current caller V4 judgment by verified whole-field retention and exact failure binding, using separate valid current native source-recall witness; no separate process/model reviewer claim.',
               'source_recall_sha256':hashlib.sha256(recall_path.read_bytes()).hexdigest(),'per_obligation_proof':proof,'host_response':response}
        with journal.open('a',encoding='utf-8') as f:f.write(json.dumps(entry,ensure_ascii=False)+'\n');f.flush()
        count+=1
        print(json.dumps({'event':'v4-alignment-response','request_id':request['request_id'],'obligations':len(active),'source_refs':sorted(allowed_refs)}),flush=True)
    return count


if __name__=='__main__':service()
